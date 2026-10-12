"""Run the golden model over a real video and collect every metric from section 8.

    python scripts/run_video_eval.py --video my_clip.mp4 --out results
    python scripts/run_video_eval.py --video 0 --max-frames 20          # webcam

Outputs in --out:
    frames.csv            one row per (frame, quality, mode) with every metric
    summary.csv/.json     mean and std per (quality, mode)  -> paper tables
    integrity.csv         tamper / replay / reorder / drop / insert detection
    plots/*.png           RQ1 security-vs-cost, visual security, attack, timing
    samples/              first frame: original, plain, scrambled, decrypted, attack images
    scrambled_<mode>.mjpeg   exactly what VLC receives (play it, see section 'videos')
    decrypted_<mode>.mjpeg   what the key holder recovers
    comparison_<mode>.mp4    original | no-key view | receiver output, side by side
    modes_grid.mp4           original + the no-key view of every mode

Timings are pure-Python on the PC. They are useful for relative comparisons and
for checking the scripts; the paper's speed/energy numbers must come from the board.
"""
import argparse
import csv
import json
import time
from pathlib import Path

import _common
import cv2
import numpy as np

from model import ascon
from model.container import build_jpeg, parse_jpeg
from model.entropy import huffman_encode
from model.jpeg import (ReplayGuard, analyse_frame, decode_pixels, full_stream_encrypt,
                        package_frame, receive_frame, selective_encrypt_jpeg)
from model.metrics import adjacent_correlation, entropy, npcr_uaci, psnr, ssim
from model.selective import MODE_ID, apply_keystream, replacement_attack

NUMERIC_SKIP = {"frame", "quality", "mode"}


def decodable(jpeg):
    """Format-compliance check with two independent decoders (Pillow and OpenCV/libjpeg)."""
    try:
        decode_pixels(jpeg)
        ok_pil = True
    except Exception:
        ok_pil = False
    ok_cv = cv2.imdecode(_common.as_np(jpeg), cv2.IMREAD_COLOR) is not None
    return ok_pil and ok_cv


def timed(fn, *args, **kw):
    t = time.perf_counter()
    r = fn(*args, **kw)
    return r, (time.perf_counter() - t) * 1000.0


def evaluate_frame(rgb, fidx, ctr, quality, modes, key, key2, session_base, deep):
    rows = []
    an, t_an = timed(analyse_frame, rgb, quality)
    plain, t_pack = timed(package_frame, an)
    pd = decode_pixels(plain.jpeg)
    _, t_full = timed(full_stream_encrypt, plain.jpeg, key, session_base, ctr)
    base = dict(frame=fidx, quality=quality, width=an.width, height=an.height)
    rows.append(dict(base, mode="PLAIN", bytes=len(plain.jpeg), scan_bytes=len(plain.scan),
                     overhead_bytes=0, enc_bits_pct=0.0, psnr_vs_orig=psnr(rgb, pd),
                     ssim_vs_orig=ssim(rgb, pd), compliant=int(decodable(plain.jpeg)),
                     t_transform_ms=t_an, t_encrypt_entropy_ms=t_pack,
                     t_fullstream_ms=t_full))
    outputs = {"plain": plain, "plain_pixels": pd}
    for mode in modes:
        session = session_base + 16 * (quality % 256) + MODE_ID[mode]   # never reuse a nonce
        enc, t_enc = timed(package_frame, an, key, session, ctr, mode)
        sw, t_sw = timed(selective_encrypt_jpeg, plain.jpeg, key, session, ctr, mode)
        nk = decode_pixels(enc.jpeg)
        rx, t_rx = timed(receive_frame, enc.jpeg, key)
        att_syms = replacement_attack(enc.symbols, mode)
        att_scan, _ = huffman_encode(att_syms)
        att = decode_pixels(build_jpeg(an.width, an.height, an.qy, an.qc, att_scan))
        row = dict(base, mode=mode, bytes=len(enc.jpeg), scan_bytes=len(enc.scan),
                   overhead_bytes=len(enc.scan) - len(plain.scan),
                   enc_bits_pct=100.0 * enc.enc_bits / max(1, enc.payload_bits),
                   enc_bits=enc.enc_bits, keystream_blocks=enc.keystream_blocks,
                   psnr_nokey=psnr(rgb, nk), ssim_nokey=ssim(rgb, nk),
                   psnr_attack=psnr(rgb, att), ssim_attack=ssim(rgb, att),
                   compliant=int(decodable(enc.jpeg)),
                   tag_ok=int(rx.ok), bit_exact=int(rx.ok and rx.plain_jpeg == plain.jpeg),
                   sw_equals_hw=int(sw == enc.jpeg),
                   t_encrypt_entropy_ms=t_enc, t_sw_selective_ms=t_sw, t_receive_ms=t_rx)
        if deep:
            enc2 = package_frame(an, key2, session, ctr, mode)          # 1-bit key change
            nk2 = decode_pixels(enc2.jpeg)
            npcr, uaci = npcr_uaci(nk, nk2)
            ks_wrong = ascon.Keystream(key2, ascon.make_nonce(session, ctr, 0))
            wrong_syms, _ = apply_keystream(enc.symbols, ks_wrong, mode)
            wrong_scan, _ = huffman_encode(wrong_syms)
            wrong = decode_pixels(build_jpeg(an.width, an.height, an.qy, an.qc, wrong_scan))
            corr_o, corr_e = adjacent_correlation(rgb), adjacent_correlation(nk)
            row.update(npcr_keychange=npcr, uaci_keychange=uaci,
                       psnr_wrongkey=psnr(rgb, wrong), ssim_wrongkey=ssim(rgb, wrong),
                       entropy_orig=entropy(rgb), entropy_nokey=entropy(nk),
                       corr_h_orig=corr_o["h"], corr_v_orig=corr_o["v"], corr_d_orig=corr_o["d"],
                       corr_h_nokey=corr_e["h"], corr_v_nokey=corr_e["v"], corr_d_nokey=corr_e["d"])
        rows.append(row)
        outputs[mode] = dict(enc=enc, nokey=nk, attack=att,
                             clear=decode_pixels(rx.plain_jpeg) if rx.ok else None)
    return rows, outputs


# ------------------------------------------------------------- integrity ----
def integrity_tests(frames, key, seed=0):
    """frames: list of consecutive encrypted JPEGs (same session, counters 0,1,2...)."""
    rng = np.random.default_rng(seed)
    bad_key = bytes(16)
    results = {}

    def rec(name, detected):
        results.setdefault(name, []).append(bool(detected))

    for jpeg in frames:
        p = parse_jpeg(jpeg)
        scan_start = len(jpeg) - 2 - len(p.scan)
        rec("clean frame accepted (should be 100%)", receive_frame(jpeg, key).ok)
        b = bytearray(jpeg)
        b[int(rng.integers(scan_start, len(b) - 2))] ^= 1 << int(rng.integers(0, 8))
        rec("1-bit flip in scan data", not receive_frame(bytes(b), key).ok)
        b = bytearray(jpeg)
        k = jpeg.find(b"SJV1")
        b[k + 5] ^= 0x01
        rec("mode byte changed", not receive_frame(bytes(b), key).ok)
        b = bytearray(jpeg)
        b[k + 22 + int(rng.integers(0, 16))] ^= 0x80
        rec("tag modified", not receive_frame(bytes(b), key).ok)
        b = bytearray(jpeg)
        sof = jpeg.find(b"\xff\xc0", k + 38)
        b[sof + 8] ^= 0x01                                   # width LSB
        rec("picture size changed (SOF)", not receive_frame(bytes(b), key).ok)
        b = bytearray(jpeg)
        b[k + 21] ^= 0x01                                    # counter LSB
        rec("frame counter changed", not receive_frame(bytes(b), key).ok)

    # sequence-level attacks with the replay guard
    def run(seq):
        g = ReplayGuard()
        return [receive_frame(f, key, g).reason for f in seq]

    n = len(frames)
    for i in range(1, n - 1):
        r = run(frames[:i + 1] + [frames[i - 1]])
        rec("replayed old frame", r[-1] == "replay")
        seq = frames[:i] + [frames[i + 1], frames[i]]
        r = run(seq)
        rec("reordered frames (late frame rejected)", r[-1] == "replay")
        r = run(frames[:i] + frames[i + 1:i + 2])
        rec("dropped frame (counter gap flagged)", r[-1] == "gap")
        p = parse_jpeg(frames[i])
        sec = p.secure()
        forged = bytearray(frames[i])
        k = frames[i].find(b"SJV1")
        fake_tag = ascon.mac(bad_key, ascon.make_nonce(sec[2], sec[3], 1), b"guess")
        forged[k + 22:k + 38] = fake_tag
        rec("inserted forged frame", not receive_frame(bytes(forged), key).ok)
    return {name: (100.0 * sum(v) / len(v), len(v)) for name, v in results.items()}


# --------------------------------------------------------------- reporting --
def summarise(rows):
    groups = {}
    for r in rows:
        groups.setdefault((r["quality"], r["mode"]), []).append(r)
    summary = []
    for (q, mode), rs in sorted(groups.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        s = {"quality": q, "mode": mode, "n_frames": len(rs)}
        keys = sorted({k for r in rs for k in r} - NUMERIC_SKIP)
        for k in keys:
            vals = [r[k] for r in rs if k in r and isinstance(r[k], (int, float))]
            if vals:
                s[k + "_mean"] = float(np.mean(vals))
                s[k + "_std"] = float(np.std(vals))
        summary.append(s)
    return summary


def write_csv(path, rows):
    keys = []
    for r in rows:
        for k in r:
            if k not in keys:
                keys.append(k)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow({k: (f"{v:.6g}" if isinstance(v, float) else v) for k, v in r.items()})


def print_summary(summary):
    print("\n=== Summary (mean +- std over frames) ===")
    hdr = (f"{'Q':>3} {'mode':5} {'bytes':>8} {'ovh B':>6} {'enc%':>6} {'PSNR noKey':>12} "
           f"{'SSIM noKey':>13} {'PSNR attack':>12} {'SSIM attack':>12} {'exact':>5} {'compl':>5}")
    print(hdr)
    print("-" * len(hdr))
    g = lambda s, k: s.get(k + "_mean", float("nan"))  # noqa: E731
    sd = lambda s, k: s.get(k + "_std", float("nan"))  # noqa: E731
    for s in summary:
        if s["mode"] == "PLAIN":
            print(f"{s['quality']:>3} {'PLAIN':5} {g(s, 'bytes'):8.0f} {'':>6} {'':>6} "
                  f"{g(s, 'psnr_vs_orig'):6.2f}+-{sd(s, 'psnr_vs_orig'):4.2f} "
                  f"{g(s, 'ssim_vs_orig'):6.4f}+-{sd(s, 'ssim_vs_orig'):5.3f}   (compression quality, no encryption)")
            continue
        print(f"{s['quality']:>3} {s['mode']:5} {g(s, 'bytes'):8.0f} {g(s, 'overhead_bytes'):6.1f} "
              f"{g(s, 'enc_bits_pct'):6.2f} {g(s, 'psnr_nokey'):6.2f}+-{sd(s, 'psnr_nokey'):4.2f} "
              f"{g(s, 'ssim_nokey'):6.4f}+-{sd(s, 'ssim_nokey'):5.3f} "
              f"{g(s, 'psnr_attack'):6.2f}+-{sd(s, 'psnr_attack'):4.2f} "
              f"{g(s, 'ssim_attack'):6.4f}+-{sd(s, 'ssim_attack'):4.2f} "
              f"{100 * g(s, 'bit_exact'):4.0f}% {100 * g(s, 'compliant'):4.0f}%")
    print("\nPC timing (ms per frame, pure Python; relative only):")
    for s in summary:
        if s["mode"] == "PLAIN":
            print(f"  Q{s['quality']} transform {g(s, 't_transform_ms'):.1f}, plain entropy "
                  f"{g(s, 't_encrypt_entropy_ms'):.1f}, full-stream Ascon {g(s, 't_fullstream_ms'):.1f}")
        else:
            print(f"  Q{s['quality']} {s['mode']}: in-encoder encrypt+entropy+tag "
                  f"{g(s, 't_encrypt_entropy_ms'):.1f}, software selective (post-hoc) "
                  f"{g(s, 't_sw_selective_ms'):.1f}, receiver {g(s, 't_receive_ms'):.1f}")
    deep = [s for s in summary if "npcr_keychange_mean" in s]
    if deep:
        print("\nKey sensitivity / statistics (deep frames):")
        for s in deep:
            print(f"  Q{s['quality']} {s['mode']}: NPCR {g(s, 'npcr_keychange'):.2f}%  "
                  f"UACI {g(s, 'uaci_keychange'):.2f}%  wrong-key PSNR {g(s, 'psnr_wrongkey'):.2f} dB  "
                  f"entropy {g(s, 'entropy_orig'):.3f}->{g(s, 'entropy_nokey'):.3f}  "
                  f"corr_h {g(s, 'corr_h_orig'):.3f}->{g(s, 'corr_h_nokey'):.3f}")


def make_plots(summary, outdir):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    outdir.mkdir(exist_ok=True)
    qualities = sorted({s["quality"] for s in summary})
    enc = [s for s in summary if s["mode"] != "PLAIN"]
    modes = sorted({s["mode"] for s in enc})

    def get(q, m, k, stat="mean"):
        for s in enc:
            if s["quality"] == q and s["mode"] == m:
                return s.get(f"{k}_{stat}", np.nan)
        return np.nan

    def bars(metric_pairs, title, ylabel, fname):
        fig, ax = plt.subplots(figsize=(7, 4))
        width = 0.8 / (len(qualities) * len(metric_pairs))
        x = np.arange(len(modes))
        i = 0
        for q in qualities:
            for key, lab in metric_pairs:
                ax.bar(x + i * width, [get(q, m, key) for m in modes], width,
                       yerr=[get(q, m, key, "std") for m in modes], capsize=3,
                       label=f"{lab} (Q{q})")
                i += 1
        ax.set_xticks(x + width * (i - 1) / 2)
        ax.set_xticklabels(modes)
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(outdir / fname, dpi=150)
        plt.close(fig)

    bars([("psnr_nokey", "no key"), ("psnr_attack", "replacement attack")],
         "Visual security: PSNR of what an attacker sees (lower = more secure)", "PSNR (dB)",
         "visual_security_psnr.png")
    bars([("ssim_nokey", "no key"), ("ssim_attack", "replacement attack")],
         "Visual security: SSIM of what an attacker sees (lower = more secure)", "SSIM",
         "visual_security_ssim.png")
    bars([("overhead_bytes", "scan size change")], "Size overhead per frame (byte stuffing only)",
         "bytes", "size_overhead.png")
    bars([("t_encrypt_entropy_ms", "in-encoder"), ("t_sw_selective_ms", "software post-hoc")],
         "PC Python time per frame (relative comparison only)", "ms", "timing_pc.png")

    fig, ax = plt.subplots(figsize=(6, 4.5))                  # RQ1 security vs cost
    for q in qualities:
        xs = [get(q, m, "enc_bits_pct") for m in modes]
        ys = [get(q, m, "ssim_attack") for m in modes]
        ax.plot(xs, ys, "o-", label=f"Q{q}")
        for m, x, y in zip(modes, xs, ys):
            ax.annotate(m, (x, y), textcoords="offset points", xytext=(5, 5))
    ax.set_xlabel("encrypted bits (% of scan payload)  = encryption cost")
    ax.set_ylabel("SSIM under replacement attack  (lower = more secure)")
    ax.set_title("RQ1: visual security per encrypted bit")
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(outdir / "rq1_security_vs_cost.png", dpi=150)
    plt.close(fig)


# -------------------------------------------------------------------- main --
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", required=True, help="video file, or webcam index like 0")
    ap.add_argument("--out", default="results")
    ap.add_argument("--modes", nargs="+", default=["E1", "E2", "E3", "E4"])
    ap.add_argument("--main-mode", default="E2", help="mode used for videos and integrity tests")
    ap.add_argument("--quality", nargs="+", type=int, default=[75])
    ap.add_argument("--size", default="640x480", help="WxH, or 'none' to keep the original size")
    ap.add_argument("--max-frames", type=int, default=30)
    ap.add_argument("--stride", type=int, default=1, help="use every Nth frame")
    ap.add_argument("--deep-every", type=int, default=10,
                    help="key-sensitivity/statistical tests every N frames (0 = never)")
    ap.add_argument("--tamper-frames", type=int, default=10)
    ap.add_argument("--key", default=_common.DEMO_KEY_HEX)
    ap.add_argument("--session", type=lambda s: int(s, 0), default=0x1000)
    ap.add_argument("--no-videos", action="store_true")
    a = ap.parse_args()

    key = _common.parse_key(a.key)
    key2 = bytes([key[0] ^ 0x01]) + key[1:]
    if a.main_mode not in a.modes:
        a.modes.append(a.main_mode)
    size = None if a.size.lower() == "none" else _common.parse_size(a.size)
    out = Path(a.out)
    (out / "samples").mkdir(parents=True, exist_ok=True)
    fps = _common.video_fps(a.video) / a.stride

    rows, main_stream = [], []
    writers = {}
    mjpeg = {}
    t_start = time.time()
    print(f"key {key.hex()}  modes {a.modes}  quality {a.quality}  size {a.size}")
    for n, (fidx, rgb) in enumerate(_common.read_frames(a.video, size, a.max_frames, a.stride)):
        deep = a.deep_every > 0 and n % a.deep_every == 0
        for qi, q in enumerate(a.quality):
            frows, o = evaluate_frame(rgb, fidx, n, q, a.modes, key, key2, a.session, deep)
            rows.extend(frows)
            if qi != 0:
                continue
            main = o[a.main_mode]
            main_stream.append(main["enc"].jpeg)
            if n == 0:
                s = out / "samples"
                _common.save_rgb(s / "original.png", rgb)
                (s / "plain.jpg").write_bytes(o["plain"].jpeg)
                for m in a.modes:
                    (s / f"scrambled_{m}.jpg").write_bytes(o[m]["enc"].jpeg)
                    _common.save_rgb(s / f"attack_{m}.png", o[m]["attack"])
                    if o[m]["clear"] is not None:
                        _common.save_rgb(s / f"decrypted_{m}.png", o[m]["clear"])
            if not a.no_videos:
                if not mjpeg:
                    for m in a.modes:
                        mjpeg[m] = open(out / f"scrambled_{m}.mjpeg", "wb")
                    mjpeg["clear"] = open(out / f"decrypted_{a.main_mode}.mjpeg", "wb")
                for m in a.modes:
                    mjpeg[m].write(o[m]["enc"].jpeg)
                rx = receive_frame(main["enc"].jpeg, key)
                mjpeg["clear"].write(rx.plain_jpeg)
                h, w = rgb.shape[:2]
                trip = np.hstack([_common.label(rgb, "original"),
                                  _common.label(main["nokey"], f"VLC / no key ({a.main_mode})"),
                                  _common.label(main["clear"], "receiver: verified + decrypted")])
                tiles = [_common.label(rgb, "original")] + \
                        [_common.label(o[m]["nokey"], f"{m} no key") for m in a.modes]
                while len(tiles) % 3:
                    tiles.append(np.zeros_like(rgb))
                grid = np.vstack([np.hstack(tiles[i:i + 3]) for i in range(0, len(tiles), 3)])
                for name, img in (("comparison", trip), ("grid", grid)):
                    if name not in writers:
                        fn = (f"comparison_{a.main_mode}.mp4" if name == "comparison" else "modes_grid.mp4")
                        writers[name] = cv2.VideoWriter(str(out / fn), cv2.VideoWriter_fourcc(*"mp4v"),
                                                        fps, (img.shape[1], img.shape[0]))
                    writers[name].write(cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
        last = [r for r in frows if r["mode"] == a.main_mode][0]
        print(f"frame {fidx:5d}: {last['width']}x{last['height']}  {a.main_mode} "
              f"noKey PSNR {last['psnr_nokey']:.2f} dB  SSIM {last['ssim_nokey']:.3f}  "
              f"tag {'OK' if last['tag_ok'] else 'FAIL'}  bit-exact {bool(last['bit_exact'])}  "
              f"({time.time() - t_start:.0f}s)", flush=True)
    for w in writers.values():
        w.release()
    for f in mjpeg.values():
        f.close()
    if not rows:
        raise SystemExit("no frames read")

    write_csv(out / "frames.csv", rows)
    summary = summarise(rows)
    write_csv(out / "summary.csv", summary)
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    print_summary(summary)

    if a.tamper_frames and len(main_stream) >= 3:
        integ = integrity_tests(main_stream[:a.tamper_frames], key)
        with open(out / "integrity.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["test", "detection_rate_pct", "trials"])
            for k, (rate, nt) in integ.items():
                w.writerow([k, f"{rate:.1f}", nt])
        print("\n=== Integrity (RQ3) ===")
        for k, (rate, nt) in integ.items():
            print(f"  {k:42s} {rate:6.1f}%  ({nt} trials)")

    make_plots(summary, out / "plots")
    print(f"\nall results in {out.resolve()}")


if __name__ == "__main__":
    main()
