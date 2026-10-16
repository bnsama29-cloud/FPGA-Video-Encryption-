"""After an XSim (or Icarus) run: rebuild the JPEG files from what the simulated
hardware produced, run the real receiver on them and save images to look at.

    python vivado/check_xsim_output.py                 # reads vivado/xsim_work/
    python vivado/check_xsim_output.py --dir vivado/xsim_work_v3     # contract-v3 run
Writes xsim_work/frame<N>_scrambled.jpg (what VLC would show) and
xsim_work/frame<N>_decrypted.jpg (what the key holder sees).
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from model import hw                       # noqa: E402
from model.jpeg import ReplayGuard, receive_frame   # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=str(ROOT / "vivado" / "xsim_work"))
    a = ap.parse_args()
    d = Path(a.dir)
    info = json.loads((d / "frames.json").read_text())
    key, sid = bytes.fromhex(info["key"]), info["session_id"]
    scan_all = bytes(int(x, 16) for x in (d / "out_scan.hex").read_text().split())
    tags = {}
    for line in (d / "out_tags.txt").read_text().splitlines():
        f = line.split()
        tags[int(f[0])] = b"".join(int(w, 16).to_bytes(4, "little") for w in f[1:5])
    guard, pos, bad = ReplayGuard(), 0, 0
    for fr in info["frames"]:
        scan = scan_all[pos:pos + fr["scan_bytes"]]
        pos += fr["scan_bytes"]
        jpg = hw.build_frame(fr["width"], fr["height"], fr["quality"], fr["mode"],
                             fr["frame_ctr"], sid, scan, tags[fr["index"]], version=fr.get("version", 2))
        r = receive_frame(jpg, key, guard)
        (d / f"frame{fr['index']}_scrambled.jpg").write_bytes(jpg)
        if r.plain_jpeg:
            (d / f"frame{fr['index']}_decrypted.jpg").write_bytes(r.plain_jpeg)
        ok = r.ok and r.mode == f"E{fr['mode']}"
        bad += not ok
        print(f"frame {fr['index']} {fr['name']:<22} receiver: {r.reason:<13} mode {r.mode}  "
              f"{'OK' if ok else 'FAIL'}")
    print("CHECK RESULT:", "PASS" if bad == 0 else f"FAIL ({bad} frames)")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
