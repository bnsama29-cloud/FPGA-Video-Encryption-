"""Cost of protecting one frame: in-encoder hardware vs software selective vs full-stream.

    python experiments/benchmark_crypto.py                     # 320x240 and 640x480, 10 frames
    python experiments/benchmark_crypto.py --rtl               # + RTL cycle counts per mode (Icarus)

Per frame it reports how many bytes each method must encrypt and how long it takes:
  in-encoder (RTL)        cycles from the Verilog simulation; encryption runs inside the
                          pipeline, so the question is how many EXTRA cycles each mode costs
  software selective      model.jpeg.selective_encrypt_jpeg: parse + Huffman-decode +
                          XOR + re-encode a finished JPEG (what a CPU must do otherwise)
  full-stream Ascon       whole JPEG through Ascon-AEAD128 (pure Python, our model)
  full-stream AES-GCM /   whole JPEG through OpenSSL (the `cryptography` package):
  ChaCha20-Poly1305       the fair, optimised software baseline -- and unplayable output
PC timings are only comparable with each other. Board timings (ARM Cortex-A9) come
later with the same script on the PYNQ; hardware numbers come from the RTL.
Writes sim_out/benchmark/benchmark.json and benchmark.md.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from link.sources import open_source                                         # noqa: E402
from model import ascon                                                       # noqa: E402
from model.jpeg import analyse_frame, full_stream_encrypt, package_frame, selective_encrypt_jpeg  # noqa: E402

OUT = ROOT / "sim_out" / "benchmark"


def timed(fn, reps=1):
    t = time.perf_counter()
    for _ in range(reps):
        r = fn()
    return r, (time.perf_counter() - t) / reps * 1000


def rtl_cycles(size, modes):
    """Encode one frame per mode in the RTL (Icarus) and return cycles per frame."""
    w, h = size
    work = OUT / f"rtl_{w}x{h}"
    cmd = [sys.executable, str(ROOT / "vivado" / "gen_xsim_vectors.py"), "--image", str(work / "frame.png"),
           "--size", f"{w}x{h}", "--modes", *map(str, modes), "--out", str(work)]
    import cv2
    work.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(work / "frame.png"), cv2.cvtColor(open_source("synthetic", w, h).read(), cv2.COLOR_RGB2BGR))
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
    srcs = [l.split()[2].replace("../../", "").replace("../", "vivado/")
            for l in (ROOT / "vivado" / "xsim.prj").read_text().splitlines() if l.startswith("verilog")]
    vvp = work / "tb.vvp"
    subprocess.run(["iverilog", "-g2005", "-o", str(vvp), "-I", str(ROOT / "rtl" / "include")]
                   + [str(ROOT / s) for s in srcs], check=True)
    r = subprocess.run(["vvp", "-n", str(vvp), f"+VEC_DIR={work}"], capture_output=True, text=True, timeout=3600)
    if "XSIM RESULT: PASS" not in r.stdout:
        raise RuntimeError(r.stdout[-1500:])
    cyc = [int(m.group(1)) for m in re.finditer(r"in (\d+) cycles", r.stdout)]
    return dict(zip([f"E{m}" for m in modes], cyc))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", default="synthetic")
    ap.add_argument("--sizes", nargs="+", default=["320x240", "640x480"])
    ap.add_argument("--frames", type=int, default=10)
    ap.add_argument("--quality", type=int, default=75)
    ap.add_argument("--rtl", action="store_true", help="also measure RTL cycles (slow: minutes per size)")
    ap.add_argument("--rtl-size", default="160x128")
    ap.add_argument("--clock-mhz", type=float, default=100.0)
    a = ap.parse_args()
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM, ChaCha20Poly1305
    OUT.mkdir(parents=True, exist_ok=True)
    key = os.urandom(16)
    aes, chacha = AESGCM(os.urandom(16)), ChaCha20Poly1305(os.urandom(32))
    results = {}
    for sz in a.sizes:
        w, h = (int(v) for v in sz.split("x"))
        src = open_source(a.source, w, h, loop=True)
        rows = {}
        for i in range(a.frames):
            rgb = src.read()
            an, t_an = timed(lambda: analyse_frame(rgb, a.quality))
            plain, t_plain = timed(lambda: package_frame(an))
            rec = rows.setdefault("plain JPEG (no protection)", [])
            rec.append(dict(ms=t_an + t_plain, bytes_encrypted=0, out_bytes=len(plain.jpeg), playable=True))
            for m in ("E2", "E4", "E5"):
                enc, t = timed(lambda: package_frame(an, key, 7, i + 1, m))
                rows.setdefault(f"in-encoder {m} (golden model, Python)", []).append(
                    dict(ms=t_an + t, bytes_encrypted=enc.enc_bits / 8, out_bytes=len(enc.jpeg), playable=True))
                sw, t = timed(lambda: selective_encrypt_jpeg(plain.jpeg, key, 7, i + 1, m))
                rows.setdefault(f"software selective {m} after encoding", []).append(
                    dict(ms=t, bytes_encrypted=enc.enc_bits / 8, out_bytes=len(sw), playable=True))
            n = ascon.make_nonce(7, i + 1, 0)
            ct, t = timed(lambda: full_stream_encrypt(plain.jpeg, key, 7, i + 1))
            rows.setdefault("full-stream Ascon-AEAD128 (Python)", []).append(
                dict(ms=t, bytes_encrypted=len(plain.jpeg), out_bytes=len(ct), playable=False))
            ct, t = timed(lambda: aes.encrypt(n[:12], plain.jpeg, None), 20)
            rows.setdefault("full-stream AES-128-GCM (OpenSSL)", []).append(
                dict(ms=t, bytes_encrypted=len(plain.jpeg), out_bytes=len(ct), playable=False))
            ct, t = timed(lambda: chacha.encrypt(n[:12], plain.jpeg, None), 20)
            rows.setdefault("full-stream ChaCha20-Poly1305 (OpenSSL)", []).append(
                dict(ms=t, bytes_encrypted=len(plain.jpeg), out_bytes=len(ct), playable=False))
        results[sz] = {k: {f: float(np.mean([r[f] for r in v])) for f in ("ms", "bytes_encrypted", "out_bytes")}
                       | {"playable": v[0]["playable"]} for k, v in rows.items()}
        print(f"{sz}: done")
    if a.rtl:
        w, h = (int(v) for v in a.rtl_size.split("x"))
        cyc = rtl_cycles((w, h), [0, 1, 2, 3, 4])
        results["rtl"] = dict(size=a.rtl_size, clock_mhz=a.clock_mhz, cycles=cyc,
                              cycles_per_pixel={m: c / (w * h) for m, c in cyc.items()},
                              fps_640x480={m: a.clock_mhz * 1e6 / (c / (w * h) * 640 * 480) for m, c in cyc.items()},
                              extra_cycles_vs_E0={m: c - cyc["E0"] for m, c in cyc.items()})
    (OUT / "benchmark.json").write_text(json.dumps(results, indent=2))
    lines = []
    for sz, rows in results.items():
        if sz == "rtl":
            continue
        lines += [f"\n### {sz}, quality {a.quality}, mean of {a.frames} frames (PC)\n",
                  "| Method | ms / frame | Bytes encrypted | Output bytes | Plays in VLC |", "|---|---|---|---|---|"]
        for k, r in rows.items():
            lines.append(f"| {k} | {r['ms']:.2f} | {r['bytes_encrypted']:.0f} | {r['out_bytes']:.0f} | "
                         f"{'yes' if r['playable'] else 'no'} |")
    if "rtl" in results:
        r = results["rtl"]
        lines += [f"\n### RTL (Icarus), {r['size']}, {r['clock_mhz']:.0f} MHz\n",
                  "| Mode | Cycles / frame | Cycles / pixel | Extra cycles vs E0 | 640x480 fps |", "|---|---|---|---|---|"]
        for m in r["cycles"]:
            lines.append(f"| {m} | {r['cycles'][m]} | {r['cycles_per_pixel'][m]:.3f} | "
                         f"{r['extra_cycles_vs_E0'][m]} | {r['fps_640x480'][m]:.0f} |")
    (OUT / "benchmark.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"\nwritten {OUT}/")


if __name__ == "__main__":
    main()
