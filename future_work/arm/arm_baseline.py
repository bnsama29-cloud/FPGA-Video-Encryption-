"""A3: the ARM baseline -- the same work on the PYNQ-Z2's processing system, next to the FPGA.

On the board (after first_contact.py has written the FPGA numbers):
    sudo -E python3 -m future_work.arm.arm_baseline --pl-json sim_out/board/first_contact.json
    CFLAGS="-mcpu=cortex-a9 -mfpu=neon" sudo -E python3 -m future_work.arm.arm_baseline ...   (tuned build)
On a laptop (tests the script; the numbers are the laptop's, not the board's):
    python -m future_work.arm.arm_baseline --sizes 64x48 --frames 2

What is timed, per size, median over --frames frames (wall clock on the PS, Python call included):
  ours on the PS, 1 core / 2 cores    native/sjpeg_sw.c: the identical encoder (contract v3, every byte
                                      equal to the PL's), E0, E2, E4, E5, incl. headers and the E5 order
  libjpeg-turbo                       cv2.imencode q75 4:2:0: the best software JPEG, no security
  + Ascon-AEAD128, whole file (C)     the obvious secure alternative: unplayable without the key
  + AES-128-GCM, whole file           OpenSSL via `cryptography` if installed (the A9 has no AES unit)
and, from --pl-json, the PL round trip and the fabric-only time (CYCLES register) of the same sizes, so
the speed-ups are like for like. Before timing, a gate checks that the PS encoder is bit-exact with the
golden model on a small frame in every mode (a fast wrong baseline is as worthless as a fast wrong FPGA).
Writes sim_out/board/arm_baseline.json and .md.
"""
import argparse
import json
import platform
import socket
import statistics
import time
from pathlib import Path

import numpy as np

from future_work.arm import sw_encoder as sw
from future_work.board.pynq_driver import SecureJpegIP
from model import ascon, hw
from model.testimage import make_image

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "sim_out" / "board"
KEY = bytes(range(16))
SID = 0x5EC0_1234_5678


def cpu_info():
    info = dict(machine=platform.machine(), host=socket.gethostname(), python=platform.python_version())
    try:
        lines = Path("/proc/cpuinfo").read_text().splitlines()
        names = [ln.split(":", 1)[1].strip() for ln in lines if ln.lower().startswith(("model name", "processor\t: arm"))]
        info["cpu"] = names[0] if names else platform.processor()
        info["cores"] = sum(1 for ln in lines if ln.startswith("processor"))
    except OSError:
        info["cpu"] = platform.processor()
    f = Path("/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_cur_freq")
    if f.exists():
        info["mhz"] = int(f.read_text()) / 1000
    info["cflags"] = " ".join(sw._compile_flags())
    return info


def gate(quality):
    """PS encoder vs golden model, 48x32, every mode of both contracts."""
    rgb = make_image(48, 32, "scene")
    luma, chroma = hw.quality_tables(quality)
    rec = [hw.reciprocal(q) for q in luma + chroma]
    for mode in range(5):
        ref = hw.encode_frame(rgb, quality, mode, KEY, 3, SID)
        if sw.encode_scan(rgb, rec, mode, KEY, SID, 3, contract=2) != (ref["scan"], ref["tag"]):
            return f"contract v2 E{mode}"
    for mode in range(6):
        ref = hw.encode_frame_v3(rgb, quality, mode, KEY, 3, SID)
        for th in (1, 2):
            if sw.encode_scan(rgb, rec, mode, KEY, SID, 3, contract=3, threads=th) != (ref["scan"], ref["tag"]):
                return f"contract v3 E{mode}, {th} threads"
    return None


def med_ms(fn, frames):
    fn(0)                                                    # warm-up (compile, caches)
    t = []
    for i in range(frames):
        t0 = time.perf_counter()
        fn(i + 1)
        t.append(time.perf_counter() - t0)
    return 1000 * statistics.median(t)


def pl_rows(path):
    """{size: {mode: row}} from a first_contact.json measured on the board (never the mock)."""
    if not path or not Path(path).exists():
        return {}
    d = json.loads(Path(path).read_text())
    if d.get("backend") != "pynq":
        return {}
    out = {}
    for r in d.get("speed", []):
        out.setdefault(r["size"], {})[r["mode"]] = r
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sizes", nargs="+", default=["320x240", "640x480"])
    ap.add_argument("--frames", type=int, default=20)
    ap.add_argument("--quality", type=int, default=75)
    ap.add_argument("--modes", nargs="+", type=int, default=[0, 2, 4, 5])
    ap.add_argument("--threads", nargs="+", type=int, default=[1, 2])
    ap.add_argument("--pl-json", default=str(OUT / "first_contact.json"),
                    help="first_contact.json of the board run with the bitstream (for the speed-ups)")
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    info = cpu_info()
    print(f"PS: {info.get('cpu')} x{info.get('cores')} ({info['machine']}), {info['cflags']}", flush=True)
    bad = gate(a.quality)
    if bad:
        print(f"GATE FAILED: the PS encoder differs from the golden model in {bad}. Nothing timed.")
        raise SystemExit(1)
    print("gate: PS encoder bit-exact with the golden model (v2 E0-E4, v3 E0-E5, 1 and 2 threads)", flush=True)
    try:
        import cv2
    except ImportError:
        cv2 = None
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        aes = AESGCM(bytes(16))
    except ImportError:
        aes = None
    on_arm = info["machine"].lower().startswith(("arm", "aarch"))
    pl = pl_rows(a.pl_json) if on_arm else {}          # never set laptop numbers against the board's
    res = dict(cpu=info, quality=a.quality, frames=a.frames, sizes={}, pl_json=a.pl_json if pl else None)
    md = [f"# A3: ARM baseline on `{info['host']}` ({info.get('cpu')}, {info.get('cores')} cores, "
          f"{info['machine']})", "", f"Compiler flags: `{info['cflags']}`. Median of {a.frames} frames, "
          "quality {}, wall clock incl. the Python call. Gate: PS encoder bit-exact with the model.".format(a.quality)]
    for sz in a.sizes:
        w, h = (int(v) for v in sz.split("x"))
        rgb = make_image(w, h, "scene")
        rows = {}
        for th in a.threads:
            ip = SecureJpegIP(sw.SoftwareBackend(contract=3, lanes=2, e5=True, threads=th))
            ip.setup_session(KEY, SID, a.quality)
            for mode in a.modes:
                def run(i, ip=ip, mode=mode):
                    scan, tag = ip.encode(rgb, mode, 10_000 + i)
                    return ip.build_jpeg(w, h, mode, 10_000 + i, scan, tag)
                ms = med_ms(run, a.frames)
                rows[f"ours on the PS, E{mode}, {th} core{'s' if th > 1 else ''}"] = dict(
                    kind="ps_ours", mode=mode, threads=th, ms=ms, playable=True, authenticated=True)   # the tag covers E0 too
                print(f"  {sz} PS ours E{mode} {th} thr: {ms:.1f} ms ({1000 / ms:.1f} fps)", flush=True)
        if cv2 is not None:
            bgr = rgb[..., ::-1].copy()
            enc = lambda i: cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, a.quality])[1].tobytes()
            jpg = enc(0)
            rows["libjpeg-turbo (no security)"] = dict(kind="libjpeg", ms=med_ms(enc, a.frames), playable=True,
                                                       authenticated=False, bytes=len(jpg))
            nonce = lambda i: ascon.make_nonce(SID, i, 0)
            rows["libjpeg-turbo + Ascon-AEAD128 whole file (C)"] = dict(
                kind="libjpeg_ascon", ms=med_ms(lambda i: sw.ascon_encrypt(KEY, nonce(i), enc(i)), a.frames),
                playable=False, authenticated=True)
            if aes is not None:
                rows["libjpeg-turbo + AES-128-GCM whole file (OpenSSL)"] = dict(
                    kind="libjpeg_aesgcm", ms=med_ms(lambda i: aes.encrypt(i.to_bytes(12, "little"), enc(i), None),
                                                     a.frames), playable=False, authenticated=True)
        for k in rows:
            if k.startswith("libjpeg"):
                print(f"  {sz} {k}: {rows[k]['ms']:.1f} ms", flush=True)
        p = pl.get(sz, {})
        for mode in a.modes:
            if mode in p:
                rows[f"PL (FPGA) round trip, E{mode}"] = dict(kind="pl_round_trip", mode=mode, ms=p[mode]["full_ms"],
                                                              playable=True, authenticated=True)
                if p[mode].get("fabric_ms"):
                    rows[f"PL fabric only, E{mode}"] = dict(kind="pl_fabric", mode=mode, ms=p[mode]["fabric_ms"],
                                                            playable=True, authenticated=True)
        for r in rows.values():
            r["fps"] = 1000 / r["ms"] if r["ms"] else None
        res["sizes"][sz] = rows
        md += ["", f"## {sz}", "", "| Method | ms / frame | fps | plays without key | authenticated |",
               "|---|---|---|---|---|"]
        md += [f"| {k} | {r['ms']:.2f} | {r['fps']:.1f} | {'yes' if r['playable'] else 'no'} | "
               f"{'yes' if r['authenticated'] else 'no'} |" for k, r in rows.items()]
        ps2 = rows.get(f"ours on the PS, E2, {max(a.threads)} cores") or rows.get("ours on the PS, E2, 1 core")
        for kind, label in (("pl_round_trip", "round trip"), ("pl_fabric", "fabric only")):
            plr = next((r for r in rows.values() if r["kind"] == kind and r["mode"] == 2), None)
            if ps2 and plr:
                md.append(f"\nSpeed-up of the PL ({label}) over our encoder on the PS ({ps2['threads']} cores), "
                          f"E2: **{ps2['ms'] / plr['ms']:.1f}x**")
    if not pl:
        md += ["", "No board FPGA run given (--pl-json): PL rows and speed-ups omitted."]
    if not on_arm:
        md += ["", f"NOT THE BOARD ({info['machine']}): these are laptop numbers. Do not report them as A3."]
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "arm_baseline.json").write_text(json.dumps(res, indent=1))
    (out / "arm_baseline.md").write_text("\n".join(md) + "\n")
    print("\n" + "\n".join(md) + f"\n\nwritten {out}/arm_baseline.json / .md")


if __name__ == "__main__":
    main()
