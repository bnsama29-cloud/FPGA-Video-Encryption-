"""Generate the XSim testbench inputs (vivado/tb_secure_jpeg_top.v) from the golden model.

    python vivado/gen_xsim_vectors.py                       # default frame set (fast)
    python vivado/gen_xsim_vectors.py --image photo.jpg --size 320x240 --modes 2 4
    python vivado/gen_xsim_vectors.py --video clip.mp4 --frames 3 --size 160x128

Writes to vivado/xsim_work/ (or --out):
    commands.txt      register writes / reads, stream and check commands
    pixels.hex        32-bit words {pad, B, G, R}, one per line, all frames
    expect_scan.hex   expected scan bytes (one per line), all frames
    frames.json       what each frame is (for check_xsim_output.py)
The same files run in Icarus (make xsim-icarus) and in Vivado XSim (run_xsim.sh/.bat).
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from model import hw                      # noqa: E402
from model.testimage import make_image    # noqa: E402

CTRL, STATUS, VERSION = 0x00, 0x04, 0x08
WIDTH, HEIGHT, FRAME_CTR, SESSION_ID = 0x10, 0x14, 0x18, 0x1C
KEY0, OUT_BYTES, TAG0, QT_ADDR, QT_DATA = 0x20, 0x30, 0x34, 0x44, 0x48
SESSION_ID_HI, FRAME_CTR_HI = 0x4C, 0x50
DEFAULT_KEY = "000102030405060708090a0b0c0d0e0f"


def load_frames(a):
    w, h = (int(v) for v in a.size.lower().split("x"))
    if a.image or a.video:
        import cv2
        imgs = []
        if a.image:
            imgs.append(cv2.cvtColor(cv2.imread(a.image), cv2.COLOR_BGR2RGB))
        else:
            cap = cv2.VideoCapture(a.video)
            while len(imgs) < a.frames:
                ok, f = cap.read()
                if not ok:
                    break
                imgs.append(cv2.cvtColor(f, cv2.COLOR_BGR2RGB))
        imgs = [cv2.resize(i, (w, h), interpolation=cv2.INTER_AREA) for i in imgs]
        frames = []
        for k, img in enumerate(imgs):
            for m in a.modes:
                frames.append((img, a.quality, m, f"input{k}_E{m}"))
        return frames
    # default: small synthetic set covering every mode, two qualities, odd sizes
    return [(make_image(64, 48, "scene", 1), 75, 2, "scene64x48_E2"),
            (make_image(32, 32, "noise", 2), 75, 4, "noise32x32_E4"),
            (make_image(48, 32, "checker", 3), 75, 0, "checker48x32_E0"),
            (make_image(64, 64, "bars", 4), 50, 1, "bars64x64_q50_E1"),
            (make_image(80, 48, "scene", 5), 50, 3, "scene80x48_q50_E3")]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--image")
    ap.add_argument("--video")
    ap.add_argument("--frames", type=int, default=2, help="frames to take from --video")
    ap.add_argument("--size", default="64x48", help="WxH, multiples of 16 (with --image/--video)")
    ap.add_argument("--modes", type=int, nargs="+", default=[2])
    ap.add_argument("--quality", type=int, default=75)
    ap.add_argument("--key", default=DEFAULT_KEY)
    ap.add_argument("--session", type=lambda s: int(s, 0), default=0x5EC0_0001_C0FF_EE00)
    ap.add_argument("--ctr", type=lambda s: int(s, 0), default=(1 << 32) + 100)
    ap.add_argument("--out", default=str(ROOT / "vivado" / "xsim_work"))
    a = ap.parse_args()
    key = bytes.fromhex(a.key)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    cmds, pix, exp, meta = [], [], [], []
    w32 = lambda addr, val: cmds.append(f"W {addr:02x} {val & 0xFFFFFFFF:08x}")
    r32 = lambda addr, val: cmds.append(f"R {addr:02x} {val & 0xFFFFFFFF:08x}")

    # session setup + register sanity checks
    r32(VERSION, 0x5EC00200)
    for i in range(4):
        w32(KEY0 + 4 * i, int.from_bytes(key[4 * i:4 * i + 4], "little"))
        r32(KEY0 + 4 * i, 0)                                   # keys are write-only
    w32(SESSION_ID, a.session)
    w32(SESSION_ID_HI, a.session >> 32)
    r32(SESSION_ID_HI, a.session >> 32)
    loaded_q = None
    for n, (img, q, mode, name) in enumerate(load_frames(a)):
        h, w = img.shape[:2]
        assert w % 16 == 0 and h % 16 == 0, "width and height must be multiples of 16"
        if q != loaded_q:
            luma, chroma = hw.quality_tables(q)
            w32(QT_ADDR, 0)
            for v in luma + chroma:
                w32(QT_DATA, hw.reciprocal(v))
            loaded_q = q
        ctr = a.ctr + n
        e = hw.encode_frame(img, q, mode, key, ctr, a.session)
        cmds.append(f"F {n}")
        w32(WIDTH, w)
        w32(HEIGHT, h)
        w32(FRAME_CTR, ctr)
        w32(FRAME_CTR_HI, ctr >> 32)
        w32(CTRL, 1 | (mode << 1))
        cmds.append(f"S {w * h}")
        cmds.append(f"C {len(e['scan'])}")
        t = e["tag"]
        cmds.append("G " + " ".join(f"{int.from_bytes(t[4 * i:4 * i + 4], 'little'):08x}" for i in range(4)))
        p = img.astype(np.uint32)
        pix.extend((p[..., 0] | (p[..., 1] << 8) | (p[..., 2] << 16)).flatten().tolist())
        exp.extend(e["scan"])
        meta.append(dict(index=n, name=name, width=w, height=h, quality=q, mode=mode,
                         frame_ctr=ctr, scan_bytes=len(e["scan"]), tag=t.hex()))
    cmds.append("E")
    (out / "commands.txt").write_text("\n".join(cmds) + "\n")
    (out / "pixels.hex").write_text("".join(f"{v:08x}\n" for v in pix))
    (out / "expect_scan.hex").write_text("".join(f"{v:02x}\n" for v in exp))
    (out / "frames.json").write_text(json.dumps(dict(key=a.key, session_id=a.session, frames=meta), indent=2))
    write_abs_prj(out)
    print(f"{len(meta)} frames, {len(pix)} pixels, {len(exp)} scan bytes -> {out}/")
    if len(pix) > 640 * 480 * 4:
        print("NOTE: more pixels than the testbench's MAXPIX; raise it with -generic_top / -P")


def write_abs_prj(out):
    """xsim.prj with absolute paths (bug #18): xvlog on Windows resolves the relative paths
    of a .prj against the .prj file's folder, not the working folder, so the shared
    vivado/xsim.prj (relative to xsim_work/, also read by the Makefile and the tests) broke
    there. run_xsim.bat / run_xsim.sh use this generated copy instead."""
    base = ROOT / "vivado" / "xsim_work"           # what the paths in vivado/xsim.prj are relative to
    lines = []
    for line in (ROOT / "vivado" / "xsim.prj").read_text().splitlines():
        f = line.split()
        if len(f) == 3 and f[0] == "verilog":
            lines.append(f"verilog {f[1]} {(base / f[2]).resolve().as_posix()}")
    (out / "xsim_abs.prj").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
