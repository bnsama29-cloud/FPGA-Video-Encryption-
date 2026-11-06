"""Bytes on the wire per protection level (journal experiment X7).

    python experiments/size_overhead.py                                   # synthetic scene, 640x480
    python experiments/size_overhead.py --source clip.mp4 --frames 60 --quality 50 75 90

For every frame and quality it encodes the frame as a plain JPEG (no key, no secure segment) and in every
mode E0..E5, in both containers: contract v2 (one keystream per frame, E5 with one restart marker per MCU)
and contract v3 (one restart segment per MCU in every mode, the board's form). It reports:
  * the coded payload (Huffman codes + value bits, before byte stuffing): E1-E4 only XOR value bits, so it
    has exactly the plain payload's length in bits; the scan in bytes can still differ by a few bytes,
    because XORed bytes that become 0xFF need a stuffed 0x00 (ITU-T T.81, F.1.2.3);
  * the whole frame: the secure APP11 segment (metadata + 128-bit tag) and, for E5 / v3, the restart markers;
  * link padding (software/link/wire.py, SizePadder) on the E5 v3 stream: what hiding the frame size costs.
Writes sim_out/size_overhead/size_overhead.json and .md.
"""
import argparse
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "software")]
from link.sources import open_source                       # noqa: E402
from link.wire import SizePadder                            # noqa: E402
from model.jpeg import analyse_frame, package_frame        # noqa: E402
from model.selective import MODES                           # noqa: E402

KEY, SID = bytes(range(16)), 0x5EC0_0001
PAD_POLICIES = ["none", "bucket:1024", "window:100", "runmax"]


def frame_sizes(rgb, quality, ctr):
    """{'plain': (frame bytes, scan bytes, payload bits), 'v2 E0': ..., 'v3 E5': ...} for one frame."""
    an = analyse_frame(rgb, quality)
    p = package_frame(an)
    out = {"plain": (len(p.jpeg), len(p.scan), p.payload_bits)}
    for seg in (False, True):
        for mode in MODES:
            f = package_frame(an, KEY, SID, ctr, mode, segmented=seg)
            out[f"{'v3' if seg else 'v2'} {mode}"] = (len(f.jpeg), len(f.scan), f.payload_bits)
    return out


def base(name):
    """The unencrypted stream a mode is compared with bit for bit: the plain JPEG for contract v2 (one
    scan), v3 E0 for contract v3 (one restart segment per MCU, each padded to a byte boundary)."""
    return "v3 E0" if name.startswith("v3") else "plain"


def summarise(per_frame):
    """per_frame: list of frame_sizes() dicts -> {name: {frame_mean, scan_mean, frame_over_pct, scan_over_pct,
    payload_equal_share}} relative to plain, per frame then averaged."""
    names = list(per_frame[0])
    res = {}
    for n in names:
        fr = [d[n][0] for d in per_frame]
        sc = [d[n][1] for d in per_frame]
        fo = [100 * (d[n][0] - d["plain"][0]) / d["plain"][0] for d in per_frame]
        so = [100 * (d[n][1] - d["plain"][1]) / d["plain"][1] for d in per_frame]
        res[n] = dict(frame_mean=statistics.mean(fr), scan_mean=statistics.mean(sc),
                      frame_over_pct=statistics.mean(fo), scan_over_pct=statistics.mean(so),
                      frame_over_bytes=statistics.mean(d[n][0] - d["plain"][0] for d in per_frame),
                      payload_equal_share=sum(d[n][2] == d[base(n)][2] for d in per_frame) / len(per_frame))
    return res


def padding_cost(sizes):
    """Mean padded size and overhead (%) of a sequence of frame sizes under each link.pad policy."""
    out = {}
    for pol in PAD_POLICIES:
        sp = SizePadder(pol)
        padded = [sp.target(n) for n in sizes]
        out[pol] = dict(mean_bytes=statistics.mean(padded),
                        over_pct=100 * (sum(padded) - sum(sizes)) / sum(sizes),
                        distinct_sizes=len(set(padded)))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", default="synthetic", help="synthetic | video file | folder of images")
    ap.add_argument("--size", default="640x480")
    ap.add_argument("--frames", type=int, default=30)
    ap.add_argument("--stride", type=int, default=1, help="use every Nth frame of the source")
    ap.add_argument("--quality", nargs="+", type=int, default=[50, 75, 90])
    ap.add_argument("--name", default="synthetic")
    ap.add_argument("--out", default=str(ROOT / "sim_out" / "size_overhead"))
    a = ap.parse_args()
    w, h = (int(x) for x in a.size.split("x"))
    src = open_source(a.source, w, h, loop=True)
    frames = []
    for i in range(a.frames * a.stride):
        f = src.read()
        if i % a.stride == 0:
            frames.append(f)
    res = dict(source=a.source, name=a.name, size=a.size, frames=len(frames), qualities={})
    md = [f"# Bytes per protection level: {a.name}, {a.size}, {len(frames)} frames", "",
          "Overhead relative to the plain JPEG of the same frame (no key, no secure segment), mean over frames.",
          "`payload equal` = share of frames whose coded payload (bits before byte stuffing) has exactly the length",
          "of the same frame unencrypted in the same container (plain JPEG for v2, v3 E0 for v3); the scan in bytes",
          "may still differ by stuffed 0x00 bytes. E5 reorders restart segments, which adds markers in v2."]
    for q in a.quality:
        per = [frame_sizes(f, q, i) for i, f in enumerate(frames)]
        s = summarise(per)
        pad = padding_cost([d["v3 E5"][0] for d in per])
        res["qualities"][str(q)] = dict(modes=s, padding_v3_E5=pad)
        md += ["", f"## Quality {q}", "", "| Stream | frame bytes | scan bytes | frame overhead | scan overhead | payload equal |",
               "|---|---|---|---|---|---|"]
        for n, r in s.items():
            md.append(f"| {n} | {r['frame_mean']:.0f} | {r['scan_mean']:.0f} | {r['frame_over_bytes']:+.0f} B "
                      f"({r['frame_over_pct']:+.2f} %) | {r['scan_over_pct']:+.2f} % | {100 * r['payload_equal_share']:.0f} % |")
        md += ["", "Link padding on the v3 E5 stream (frame-size hiding, `link.pad`):", "",
               "| Policy | mean bytes | overhead | distinct sizes |", "|---|---|---|---|"]
        md += [f"| {p} | {r['mean_bytes']:.0f} | {r['over_pct']:+.1f} % | {r['distinct_sizes']} |" for p, r in pad.items()]
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{a.name}.json").write_text(json.dumps(res, indent=2))
    (out / f"{a.name}.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))
    print(f"\nwritten {out}/{a.name}.json and .md")


if __name__ == "__main__":
    main()
