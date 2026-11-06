"""Faults before and after the tag (journal experiment X16): what the frame tag can and cannot catch.

    python experiments/fault_pre_tag.py                         # synthetic scene, 320x240, E2, 200 faults each
    python experiments/fault_pre_tag.py --source clip.mp4 --mode E5 --faults 500

The tag is computed over the scan as the encoder produced it. A fault AFTER the tag (DMA, memory, ARM,
network; experiments/hw_tamper.py does this on the board) changes bytes the tag covers, so the receiver
must reject the frame. A fault BEFORE the tag (inside the encoder's data path) is authenticated together with
the data, so the receiver accepts the frame and shows a slightly wrong picture. Three fault sites, one
random single-bit fault per trial, contract v2:
  coefficient   one quantised DCT coefficient off by one bit (DCT / quantiser datapath)
  ciphertext    one coded value bit flipped after encryption, before the tag unit (tag recomputed)
  after_tag     one scan bit flipped after the tag (the board's tamper injector)
For each: share of faulty frames the receiver accepts, and the PSNR of the accepted picture against the
fault-free decode (higher = less visible). Writes sim_out/fault_pre_tag/<name>.json and .md.
"""
import argparse
import json
import random
import statistics
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "software")]
from link.sources import open_source                                        # noqa: E402
from model import ascon                                                     # noqa: E402
from model.container import auth_data, build_jpeg, secure_meta             # noqa: E402
from model.entropy import run_length_encode                                 # noqa: E402
from model.jpeg import analyse_frame, decode_pixels, package_frame, receive_frame   # noqa: E402
from model.selective import MODE_ID                                         # noqa: E402

KEY, SID = bytes(range(16)), 0x5EC0_F417
SITES = ("coefficient", "ciphertext", "after_tag")


def safe_bit(scan, rng):
    """(byte index, bit) whose flip keeps the scan free of new 0xFF / marker bytes, so the fault stays a
    data error and not a framing error (the injector on the board picks bits the same way)."""
    for _ in range(1000):
        i = rng.randrange(1, len(scan) - 1)
        if scan[i] == 0xFF or scan[i - 1] == 0xFF:
            continue
        b = rng.randrange(8)
        if scan[i] ^ (1 << b) != 0xFF:
            return i, b
    raise ValueError("no safe bit found")


def flip(scan, i, b):
    out = bytearray(scan)
    out[i] ^= 1 << b
    return bytes(out)


def with_tag(an, scan, mode, ctr):
    """The frame as the encoder would emit it if `scan` came out of its datapath: tag over this scan."""
    meta = secure_meta(MODE_ID[mode], SID, ctr)
    tag = ascon.mac(KEY, ascon.make_nonce(SID, ctr, 1), auth_data(meta, an.width, an.height, scan))
    return build_jpeg(an.width, an.height, an.qy, an.qc, scan, secure_segment=meta + tag)


def psnr(a, b):
    mse = float(np.mean((a.astype(np.float64) - b.astype(np.float64)) ** 2))
    return float("inf") if mse == 0 else float(10 * np.log10(255 ** 2 / mse))


def trial(an, mode, ctr, site, rng):
    """One fault -> (accepted, psnr of the accepted picture vs the fault-free one, or the receiver's
    reason for rejecting it: 'tag-mismatch' or 'malformed: ...')."""
    good = package_frame(an, KEY, SID, ctr, mode)
    ref = decode_pixels(receive_frame(good.jpeg, KEY).plain_jpeg)
    if site == "coefficient":
        q = an.quant.copy()
        m, blk, r, c = (rng.randrange(n) for n in q.shape)
        q[m, blk, r, c] ^= 1                                  # lowest bit of one coefficient
        bad_an = type(an)(an.width, an.height, an.quality, an.qy, an.qc, run_length_encode(q), an.n_mcu, {}, q)
        jpeg = package_frame(bad_an, KEY, SID, ctr, mode).jpeg
    elif site == "ciphertext":
        jpeg = with_tag(an, flip(good.scan, *safe_bit(good.scan, rng)), mode, ctr)
    else:
        i, b = safe_bit(good.scan, rng)
        k = good.jpeg.index(good.scan)
        jpeg = good.jpeg[:k] + flip(good.scan, i, b) + good.jpeg[k + len(good.scan):]
    rx = receive_frame(jpeg, KEY)
    if not rx.ok:
        return False, rx.reason.split(":")[0]
    try:
        return True, psnr(ref, decode_pixels(rx.plain_jpeg))
    except Exception:                                         # accepted but undecodable
        return True, 0.0


def summarise(results):
    out = {}
    for site, rs in results.items():
        acc = [p for ok, p in rs if ok]
        why = [p for ok, p in rs if not ok]
        finite = [p for p in acc if p != float("inf")]
        out[site] = dict(trials=len(rs), accepted=len(acc), accepted_share=len(acc) / len(rs),
                         identical=sum(p == float("inf") for p in acc),
                         rejected_tag=why.count("tag-mismatch"), rejected_malformed=why.count("malformed"),
                         psnr_median=statistics.median(finite) if finite else None,
                         psnr_min=min(finite) if finite else None)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", default="synthetic")
    ap.add_argument("--size", default="320x240")
    ap.add_argument("--frames", type=int, default=10)
    ap.add_argument("--faults", type=int, default=200, help="faults per site (spread over the frames)")
    ap.add_argument("--mode", default="E2", choices=["E1", "E2", "E3", "E4"])
    ap.add_argument("--quality", type=int, default=75)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--name", default="synthetic")
    ap.add_argument("--out", default=str(ROOT / "sim_out" / "fault_pre_tag"))
    a = ap.parse_args()
    w, h = (int(x) for x in a.size.split("x"))
    src = open_source(a.source, w, h, loop=True)
    ans = [analyse_frame(src.read(), a.quality) for _ in range(a.frames)]
    rng = random.Random(a.seed)
    results = {s: [] for s in SITES}
    for site in SITES:
        for t in range(a.faults):
            results[site].append(trial(ans[t % len(ans)], a.mode, t + 1, site, rng))
    s = summarise(results)
    res = dict(source=a.source, size=a.size, mode=a.mode, quality=a.quality, seed=a.seed, sites=s)
    md = [f"# Faults before and after the tag: {a.name}, {a.size}, {a.mode}, {a.faults} faults per site", "",
          "| Fault site | trials | accepted by the receiver | rejected: tag / undecodable | picture identical | "
          "PSNR of accepted (median / min, dB) |", "|---|---|---|---|---|---|"]
    for site, r in s.items():
        ps = "-" if r["psnr_median"] is None else f"{r['psnr_median']:.1f} / {r['psnr_min']:.1f}"
        md.append(f"| {site} | {r['trials']} | {r['accepted']} ({100 * r['accepted_share']:.0f} %) | "
                  f"{r['rejected_tag']} / {r['rejected_malformed']} | {r['identical']} | {ps} |")
    md += ["", "A fault before the tag is authenticated with the data: the tag proves the frame left the encoder "
           "unchanged, not that the encoder computed it correctly. Detecting those needs redundancy inside "
           "the encoder (duplication or parity), which this design does not have."]
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{a.name}.json").write_text(json.dumps(res, indent=2))
    (out / f"{a.name}.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
