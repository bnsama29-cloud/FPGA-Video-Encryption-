"""Encoder back-ends for the simulated camera node.

All of them return the same thing for one frame: the complete JPEG bytes
(headers + APP11 + scrambled scan + EOI), plus a little accounting.

    model : the golden Python model (fast enough for ~10 fps at 320x240)
    rtl   : the actual Verilog (rtl/*.v) simulated in Icarus for every frame,
            driven by vivado/tb_secure_jpeg_top.v -- hardware in the loop.
            Slow (seconds per frame): use small frames, e.g. 128x96 at 0.5 fps.
    board : the PYNQ-Z2 (later) -- runs board/sender.py on the ARM and sends the
            same UDP stream, so the receiver and dashboard do not change.
"""
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np

from model import hw
from model.jpeg import analyse_frame, package_frame
from model.selective import MODE_ID

ROOT = Path(__file__).resolve().parents[1]


class EncodedOut:
    def __init__(self, jpeg, payload_bits, enc_bits, scan_bytes):
        self.jpeg, self.payload_bits, self.enc_bits, self.scan_bytes = jpeg, payload_bits, enc_bits, scan_bytes


class ModelEncoder:
    name = "model"

    def __init__(self, quality):
        self.quality = quality

    def encode(self, rgb, key, session_id, frame_ctr, mode):
        e = package_frame(analyse_frame(rgb, self.quality), key, session_id, frame_ctr, mode)
        return EncodedOut(e.jpeg, e.payload_bits, e.enc_bits, len(e.scan))


class RtlEncoder:
    """Runs the Verilog testbench for one frame and builds the JPEG from what the RTL produced.

    The testbench itself checks the RTL against the golden model; if they ever
    differ, this backend raises instead of sending a frame."""
    name = "rtl"

    def __init__(self, quality):
        if not shutil.which("iverilog") or not shutil.which("vvp"):
            raise RuntimeError("encoder=rtl needs Icarus Verilog (iverilog, vvp) on the PATH")
        self.quality = quality
        self.work = Path(tempfile.mkdtemp(prefix="rtl_enc_"))
        srcs = [l.split()[2].replace("../../", "").replace("../", "vivado/")
                for l in (ROOT / "vivado" / "xsim.prj").read_text().splitlines() if l.startswith("verilog")]
        self.vvp = self.work / "tb.vvp"
        subprocess.run(["iverilog", "-g2005", "-o", str(self.vvp), "-I", str(ROOT / "rtl" / "include")]
                       + [str(ROOT / s) for s in srcs], check=True)

    def encode(self, rgb, key, session_id, frame_ctr, mode):
        h, w = rgb.shape[:2]
        if w % 16 or h % 16:
            raise ValueError("the RTL needs width and height that are multiples of 16")
        m = MODE_ID[mode]
        if m > 4:
            raise ValueError(f"{mode} needs restart markers, which the RTL does not produce yet")
        e = hw.encode_frame(rgb, self.quality, m, key, frame_ctr, session_id)
        cmds = ["W 20 %08x" % int.from_bytes(key[0:4], "little"),
                "W 24 %08x" % int.from_bytes(key[4:8], "little"),
                "W 28 %08x" % int.from_bytes(key[8:12], "little"),
                "W 2c %08x" % int.from_bytes(key[12:16], "little"),
                "W 1c %08x" % (session_id & 0xFFFFFFFF), "W 4c %08x" % (session_id >> 32),
                "W 44 00000000"]
        luma, chroma = hw.quality_tables(self.quality)
        cmds += ["W 48 %08x" % hw.reciprocal(v) for v in luma + chroma]
        cmds += ["F 0", "W 10 %08x" % w, "W 14 %08x" % h,
                 "W 18 %08x" % (frame_ctr & 0xFFFFFFFF), "W 50 %08x" % (frame_ctr >> 32),
                 "W 00 %08x" % (1 | (m << 1)), f"S {w * h}", f"C {len(e['scan'])}",
                 "G " + " ".join("%08x" % int.from_bytes(e["tag"][4 * i:4 * i + 4], "little") for i in range(4)),
                 "E"]
        (self.work / "commands.txt").write_text("\n".join(cmds) + "\n")
        p = rgb.astype(np.uint32)
        (self.work / "pixels.hex").write_text(
            "".join("%08x\n" % v for v in (p[..., 0] | (p[..., 1] << 8) | (p[..., 2] << 16)).ravel()))
        (self.work / "expect_scan.hex").write_text("".join("%02x\n" % b for b in e["scan"]))
        r = subprocess.run(["vvp", "-n", str(self.vvp), f"+VEC_DIR={self.work}"],
                           capture_output=True, text=True, timeout=600)
        if "XSIM RESULT: PASS" not in r.stdout:
            raise RuntimeError("RTL frame did not match the golden model:\n" + r.stdout[-2000:])
        scan = bytes(int(x, 16) for x in (self.work / "out_scan.hex").read_text().split())
        words = (self.work / "out_tags.txt").read_text().split()[1:5]
        tag = b"".join(int(x, 16).to_bytes(4, "little") for x in words)
        jpeg = hw.build_frame(w, h, self.quality, m, frame_ctr, session_id, scan, tag)
        payload = sum(hw.huffman_bits(s)[1] for s in e["symbols"])
        return EncodedOut(jpeg, payload, e["keystream_bits_used"], len(scan))


def make_encoder(name, quality):
    if name == "model":
        return ModelEncoder(quality)
    if name == "rtl":
        return RtlEncoder(quality)
    raise ValueError(f"unknown encoder {name!r} (model | rtl; the board runs board/sender.py)")
