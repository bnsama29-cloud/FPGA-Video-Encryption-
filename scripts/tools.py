"""The older golden-model tools in one file (until 17 Oct 2026 these were eight scripts).

    python scripts/tools.py <command> [options]        python scripts/tools.py <command> --help

    encode-image    encode one test image in every mode, save the pictures and metrics
    video-eval      golden model over a video: every metric, MJPEG files, comparison videos
    mjpeg-server    serve an encrypted MJPEG stream over HTTP (VLC plays it scrambled)
    receiver        decrypt and verify that stream, side-by-side window
    export-vectors  test vectors for the RTL / HLS from the golden model
    test-video      make a synthetic test video from scikit-image photos
    bundle          collect a failing test into debug_bundle.md for Claude (make bundle)

The live system is link/ (python -m link.run_all); these tools predate it and are kept for the
Phase-I demos (VLC playing the scrambled stream) and for test vectors. Each command's block below is
the original script, byte for byte apart from the indentation and the shared helpers above it.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ----------------------------------------------------------------- shared helpers (was _common.py)
# OpenCV and NumPy are imported inside the helpers, so `bundle` also works on a machine without them.
DEMO_KEY_HEX = "000102030405060708090a0b0c0d0e0f"   # Phase I pre-shared key (demo only!)


def parse_key(hexstr):
    key = bytes.fromhex(hexstr)
    if len(key) != 16:
        raise SystemExit("key must be 32 hex characters (128 bits)")
    return key


def parse_size(s):
    if not s:
        return None
    w, h = s.lower().split("x")
    return int(w), int(h)


def open_video(src):
    """src: path to a video file, or a webcam index such as '0'."""
    import cv2
    cap = cv2.VideoCapture(int(src) if str(src).isdigit() else str(src))
    if not cap.isOpened():
        raise SystemExit(f"could not open video source {src!r}")
    return cap


def read_frames(src, size=None, max_frames=None, stride=1, start=0):
    """Yields (index, RGB uint8 frame). Resizes to size=(w, h) when given."""
    import cv2
    cap = open_video(src)
    idx = 0
    out = 0
    try:
        while True:
            ok, bgr = cap.read()
            if not ok:
                break
            if idx >= start and (idx - start) % stride == 0:
                if size:
                    bgr = cv2.resize(bgr, size, interpolation=cv2.INTER_AREA)
                yield idx, cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
                out += 1
                if max_frames and out >= max_frames:
                    break
            idx += 1
    finally:
        cap.release()


def video_fps(src, default=30.0):
    import cv2
    cap = open_video(src)
    fps = cap.get(cv2.CAP_PROP_FPS) or default
    cap.release()
    return fps if fps > 1 else default


def label(img_rgb, text):
    import cv2
    out = img_rgb.copy()
    cv2.rectangle(out, (0, 0), (min(out.shape[1], 12 + 11 * len(text)), 26), (0, 0, 0), -1)
    cv2.putText(out, text, (6, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
    return out


def save_rgb(path, rgb):
    import cv2
    cv2.imwrite(str(path), cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))


def as_np(b):
    import numpy as np
    return np.frombuffer(b, np.uint8)

_common = sys.modules[__name__]          # the blocks below call the helpers as _common.<name>
COMMANDS = ['encode-image', 'video-eval', 'mjpeg-server', 'receiver', 'export-vectors', 'test-video', 'bundle']
CMD = sys.argv[1] if __name__ == "__main__" and len(sys.argv) > 1 else None
if __name__ == "__main__":
    if CMD not in COMMANDS:
        sys.exit(__doc__)
    sys.argv = [f"tools.py {CMD}"] + sys.argv[2:]

# ==================================================================================================
# encode-image   (was scripts/encode_image.py)
# ==================================================================================================
if CMD == "encode-image":
    """Quick single-image check: plain JPEG, E1-E4 scrambled JPEGs, decrypted JPEGs.

    python scripts/encode_image.py photo.jpg --out out_image
    python scripts/encode_image.py --sample astronaut --out out_image
"""
    import argparse
    from pathlib import Path

    import cv2
    from skimage import data

    from model.jpeg import analyse_frame, decode_pixels, package_frame, receive_frame
    from model.metrics import psnr, ssim
    from model.selective import MODES


    def main():
        ap = argparse.ArgumentParser()
        ap.add_argument("image", nargs="?")
        ap.add_argument("--sample", default="astronaut", help="scikit-image sample if no image given")
        ap.add_argument("--out", default="out_image")
        ap.add_argument("--quality", type=int, default=75)
        ap.add_argument("--key", default=_common.DEMO_KEY_HEX)
        a = ap.parse_args()
        key = _common.parse_key(a.key)
        out = Path(a.out)
        out.mkdir(parents=True, exist_ok=True)

        if a.image:
            bgr = cv2.imread(a.image)
            if bgr is None:
                raise SystemExit(f"cannot read {a.image}")
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        else:
            rgb = getattr(data, a.sample)()[..., :3]
        _common.save_rgb(out / "original.png", rgb)

        an = analyse_frame(rgb, a.quality)
        plain = package_frame(an)
        (out / "plain.jpg").write_bytes(plain.jpeg)
        pd = decode_pixels(plain.jpeg)
        print(f"image {an.width}x{an.height}, quality {a.quality}")
        print(f"plain JPEG: {len(plain.jpeg)} bytes, PSNR {psnr(rgb, pd):.2f} dB, SSIM {ssim(rgb, pd):.4f}")
        print(f"{'mode':4} {'bytes':>7} {'enc bits %':>10} {'noKey PSNR':>10} {'noKey SSIM':>10}  receiver")
        for i, mode in enumerate(MODES):
            if mode == "E0":
                continue
            enc = package_frame(an, key, session_id=0x5EC0 + i, frame_ctr=0, mode=mode)
            (out / f"scrambled_{mode}.jpg").write_bytes(enc.jpeg)
            nk = decode_pixels(enc.jpeg)
            r = receive_frame(enc.jpeg, key)
            (out / f"decrypted_{mode}.jpg").write_bytes(r.plain_jpeg)
            print(f"{mode:4} {len(enc.jpeg):7d} {100 * enc.enc_bits / enc.payload_bits:10.2f} "
                  f"{psnr(rgb, nk):10.2f} {ssim(rgb, nk):10.4f}  tag {r.reason}, "
                  f"bit-exact={r.plain_jpeg == plain.jpeg}")
        print(f"files written to {out}/  (open scrambled_*.jpg in any viewer)")


    if __name__ == "__main__":
        main()

# ==================================================================================================
# video-eval   (was scripts/run_video_eval.py)
# ==================================================================================================
elif CMD == "video-eval":
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

# ==================================================================================================
# mjpeg-server   (was scripts/mjpeg_server.py)
# ==================================================================================================
elif CMD == "mjpeg-server":
    """HTTP MJPEG server on the PC -- the same thing the PYNQ-Z2 will run (section 4.1).

Encodes a video (or webcam) with the golden model and serves the encrypted frames as
multipart/x-mixed-replace. VLC plays it (scrambled); receiver.py decrypts it.

    python scripts/mjpeg_server.py --video test_video.mp4 --mode E2
    VLC:      Media > Open Network Stream > http://localhost:8080/stream.mjpg
    receiver: python scripts/receiver.py --url http://localhost:8080/stream.mjpg

Pure-Python encoding is slow (a few fps at 320x240). On the board the fabric does
this in hardware; here we only need it to behave identically.
--tamper N corrupts every Nth frame so you can watch the receiver catch it.
"""
    import argparse
    import threading
    import time
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    import numpy as np

    from model.jpeg import encode_frame

    BOUNDARY = b"frameboundary"


    class Broadcaster:
        def __init__(self):
            self.cond = threading.Condition()
            self.frame = None
            self.seq = 0

        def publish(self, jpeg):
            with self.cond:
                self.frame = jpeg
                self.seq += 1
                self.cond.notify_all()

        def wait(self, last_seq, timeout=5.0):
            with self.cond:
                self.cond.wait_for(lambda: self.seq != last_seq, timeout)
                return self.seq, self.frame


    def producer(a, key, bc, stop):
        size = _common.parse_size(a.size)
        session = a.session if a.session is not None else int.from_bytes(np.random.bytes(8), "big")
        ctr = 0
        rng = np.random.default_rng()
        print(f"session id 0x{session:016x}, mode {a.mode}, key {key.hex()}")
        while not stop.is_set():
            for _, rgb in _common.read_frames(a.video, size):
                if stop.is_set():
                    return
                t0 = time.perf_counter()
                jpeg = encode_frame(rgb, key, session, ctr, a.mode, a.quality).jpeg
                if a.tamper and ctr % a.tamper == a.tamper - 1:
                    b = bytearray(jpeg)
                    b[int(rng.integers(len(b) // 2, len(b) - 2))] ^= 0x10   # attacker flips a bit
                    jpeg = bytes(b)
                    print(f"  frame {ctr}: TAMPERED on purpose")
                bc.publish(jpeg)
                dt = time.perf_counter() - t0
                if ctr % 10 == 0:
                    print(f"frame {ctr}: {len(jpeg)} bytes, encode {dt * 1000:.0f} ms "
                          f"({1 / max(dt, 1e-6):.1f} fps)")
                ctr += 1
                if a.fps:
                    time.sleep(max(0.0, 1.0 / a.fps - dt))
            # the file ended: loop it. Counters keep increasing, so nothing looks like a replay.


    def make_handler(bc):
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                if not self.path.startswith("/stream"):
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html")
                    self.end_headers()
                    self.wfile.write(b'<html><body><img src="/stream.mjpg"></body></html>')
                    return
                self.send_response(200)
                self.send_header("Content-Type", f"multipart/x-mixed-replace; boundary={BOUNDARY.decode()}")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                print(f"client connected: {self.client_address[0]}")
                seq = -1
                try:
                    while True:
                        seq, frame = bc.wait(seq)
                        if frame is None:
                            continue
                        self.wfile.write(b"--" + BOUNDARY + b"\r\nContent-Type: image/jpeg\r\n"
                                         b"Content-Length: " + str(len(frame)).encode() + b"\r\n\r\n")
                        self.wfile.write(frame + b"\r\n")
                except (BrokenPipeError, ConnectionResetError):
                    print(f"client left: {self.client_address[0]}")
        return Handler


    def main():
        ap = argparse.ArgumentParser()
        ap.add_argument("--video", required=True, help="video file or webcam index")
        ap.add_argument("--mode", default="E2", choices=["E0", "E1", "E2", "E3", "E4"])
        ap.add_argument("--quality", type=int, default=75)
        ap.add_argument("--size", default="320x240")
        ap.add_argument("--fps", type=float, default=0, help="cap frame rate (0 = as fast as possible)")
        ap.add_argument("--port", type=int, default=8080)
        ap.add_argument("--key", default=_common.DEMO_KEY_HEX)
        ap.add_argument("--session", type=lambda s: int(s, 0), default=None,
                        help="session id (default: random, like the board after each boot)")
        ap.add_argument("--tamper", type=int, default=0, help="corrupt every Nth frame")
        a = ap.parse_args()
        key = _common.parse_key(a.key)
        bc = Broadcaster()
        stop = threading.Event()
        threading.Thread(target=producer, args=(a, key, bc, stop), daemon=True).start()
        srv = ThreadingHTTPServer(("0.0.0.0", a.port), make_handler(bc))
        print(f"serving http://localhost:{a.port}/stream.mjpg  (Ctrl+C to stop)")
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            stop.set()
            srv.server_close()


    if __name__ == "__main__":
        main()

# ==================================================================================================
# receiver   (was scripts/receiver.py)
# ==================================================================================================
elif CMD == "receiver":
    """Key-holder receiver: verify tag -> replay check -> decrypt -> show clear video.

From the live stream (PC server now, PYNQ-Z2 later):
    python scripts/receiver.py --url http://localhost:8080/stream.mjpg
    python scripts/receiver.py --url http://192.168.2.99:8080/stream.mjpg      # the board

From a recorded file (e.g. results/scrambled_E2.mjpeg):
    python scripts/receiver.py --file results/scrambled_E2.mjpeg --save-dir rx_out

Window shows: left = what VLC/an attacker sees, right = verified + decrypted.
Press q to quit. A log CSV records every frame's verdict and timing.
"""
    import argparse
    import csv
    import time
    import urllib.request
    from pathlib import Path

    import cv2
    import numpy as np

    from model.container import split_mjpeg
    from model.jpeg import ReplayGuard, decode_pixels, receive_frame


    def frames_from_http(url):
        """Parses multipart/x-mixed-replace; yields each JPEG body."""
        resp = urllib.request.urlopen(url, timeout=10)
        while True:
            line = resp.readline()
            if not line:
                return
            if not line.startswith(b"--"):
                continue
            length = None
            while True:
                h = resp.readline()
                if h in (b"\r\n", b"\n", b""):
                    break
                k, _, v = h.decode(errors="replace").partition(":")
                if k.strip().lower() == "content-length":
                    length = int(v.strip())
            if length is None:
                continue
            yield resp.read(length)


    def frames_from_file(path):
        yield from split_mjpeg(Path(path).read_bytes())


    def main():
        ap = argparse.ArgumentParser()
        src = ap.add_mutually_exclusive_group(required=True)
        src.add_argument("--url")
        src.add_argument("--file")
        ap.add_argument("--key", default=_common.DEMO_KEY_HEX)
        ap.add_argument("--no-display", action="store_true")
        ap.add_argument("--save-dir", help="write decrypted frames as clear .jpg files here")
        ap.add_argument("--log", default="receiver_log.csv")
        ap.add_argument("--max-frames", type=int, default=0)
        a = ap.parse_args()
        key = _common.parse_key(a.key)
        guard = ReplayGuard()
        save = Path(a.save_dir) if a.save_dir else None
        if save:
            save.mkdir(parents=True, exist_ok=True)
        source = frames_from_http(a.url) if a.url else frames_from_file(a.file)

        counts = {}
        t0 = time.time()
        last_clear = None
        with open(a.log, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["n", "bytes", "verdict", "mode", "session", "frame_ctr", "verify_decrypt_ms"])
            for n, jpeg in enumerate(source):
                t = time.perf_counter()
                r = receive_frame(jpeg, key, guard)
                ms = (time.perf_counter() - t) * 1000
                counts[r.reason] = counts.get(r.reason, 0) + 1
                w.writerow([n, len(jpeg), r.reason, r.mode, r.session_id, r.frame_ctr, f"{ms:.1f}"])
                print(f"frame {n:5d} ctr={r.frame_ctr} mode={r.mode} -> {r.reason.upper():14s} "
                      f"({ms:.0f} ms)", flush=True)
                if r.ok and save:
                    (save / f"frame_{r.frame_ctr:06d}.jpg").write_bytes(r.plain_jpeg)
                if not a.no_display:
                    try:
                        scr = decode_pixels(jpeg)
                    except Exception:
                        scr = np.zeros((240, 320, 3), np.uint8)
                    if r.ok:
                        last_clear = decode_pixels(r.plain_jpeg)
                        right = _common.label(last_clear, f"VERIFIED ctr={r.frame_ctr}")
                    else:
                        right = np.zeros_like(scr) if last_clear is None else (last_clear // 3)
                        right = _common.label(right, f"REJECTED: {r.reason}")
                    if right.shape != scr.shape:
                        right = cv2.resize(right, (scr.shape[1], scr.shape[0]))
                    view = np.hstack([_common.label(scr, "VLC view (no key)"), right])
                    cv2.imshow("secure MJPEG receiver", cv2.cvtColor(view, cv2.COLOR_RGB2BGR))
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        break
                if a.max_frames and n + 1 >= a.max_frames:
                    break
        dt = time.time() - t0
        total = sum(counts.values())
        print(f"\n{total} frames in {dt:.1f} s; verdicts: {counts}; log -> {a.log}")
        if not a.no_display:
            cv2.destroyAllWindows()


    if __name__ == "__main__":
        main()

# ==================================================================================================
# export-vectors   (was scripts/export_vectors.py)
# ==================================================================================================
elif CMD == "export-vectors":
    """Export every pipeline stage as test vectors for the RTL/HLS testbenches.

    python scripts/export_vectors.py --sample astronaut --size 64x64 --out vectors/astro64
    python scripts/export_vectors.py --image my.png --size 640x480 --out vectors/my640
    python scripts/export_vectors.py --video clip.mp4 --frame 10 --size 64x64 --out vectors/clip64

Files (one value per line, hex, readable by $readmemh, cocotb or numpy):
    config.json              size, quality, key, session, counter, nonces, tag per mode
    pixels.hex               32-bit words {pad, B, G, R}: R in bits [7:0] (DDR byte order R,G,B,pad)
    blocks.hex               8-bit samples, 64 per block row-major, blocks Y0 Y1 Y2 Y3 Cb Cr per MCU
    coeffs.hex               16-bit two's complement DCT output, 64 per block row-major
    quant.hex                16-bit two's complement quantiser output, row-major
    qtable_luma.hex / qtable_chroma.hex   8-bit, row-major
    dct_matrix.hex           16-bit two's complement DCT_C (8x8, 2^13 scale) for the HLS ROM
    symbols_plain.hex        23-bit packed symbols (format below), coding order
    symbols_<mode>.hex       same, after selective encryption
    symbols_*.csv            human-readable version
    keystream.hex            first keystream bytes for N_enc (one byte per line;
                             bit i of the stream = bit i%8 of byte i//8)
    scan_plain.hex           stuffed scan bytes from the plain encoder
    scan_<mode>.hex          stuffed scan bytes after in-encoder encryption
    frame_<mode>.jpg / plain.jpg   complete JPEG files for viewing
    stages.npz               all stage arrays (np.load) for Python/cocotb testbenches

Packed symbol word (MSB first, 23 bits):
    [22] is_dc  [21:18] run  [17:14] size  [13:3] amplitude (11-bit two's complement)
    [2] eob  [1:0] comp
"""
    import argparse
    import json
    from pathlib import Path

    import cv2
    import numpy as np
    from skimage import data

    from model import ascon
    from model.dct_quant import DCT_C
    from model.jpeg import analyse_frame, package_frame
    from model.selective import MODE_ID, MODES


    def write_hex(path, values, bits):
        mask = (1 << bits) - 1
        digits = (bits + 3) // 4
        with open(path, "w") as f:
            for v in np.asarray(values).ravel().tolist():
                f.write(f"{int(v) & mask:0{digits}x}\n")


    def pack_symbol(s):
        return ((s.is_dc << 22) | (s.run << 18) | (s.size << 14) | ((s.amp & 0x7FF) << 3) |
                (s.eob << 2) | s.comp)


    def write_symbols(out, name, symbols):
        write_hex(out / f"symbols_{name}.hex", [pack_symbol(s) for s in symbols], 23)
        with open(out / f"symbols_{name}.csv", "w") as f:
            f.write("index,is_dc,run,size,amp,eob,comp\n")
            for i, s in enumerate(symbols):
                f.write(f"{i},{s.is_dc},{s.run},{s.size},{s.amp},{s.eob},{s.comp}\n")


    def main():
        ap = argparse.ArgumentParser()
        src = ap.add_mutually_exclusive_group()
        src.add_argument("--image")
        src.add_argument("--video")
        src.add_argument("--sample", default="astronaut")
        ap.add_argument("--frame", type=int, default=0)
        ap.add_argument("--size", default="64x64")
        ap.add_argument("--quality", type=int, default=75)
        ap.add_argument("--key", default=_common.DEMO_KEY_HEX)
        ap.add_argument("--session", type=lambda s: int(s, 0), default=0x1234)
        ap.add_argument("--ctr", type=int, default=0)
        ap.add_argument("--keystream-bytes", type=int, default=1024)
        ap.add_argument("--out", default="vectors/frame")
        a = ap.parse_args()
        key = _common.parse_key(a.key)
        size = _common.parse_size(a.size)

        if a.image:
            rgb = cv2.cvtColor(cv2.imread(a.image), cv2.COLOR_BGR2RGB)
        elif a.video:
            rgb = next(f for i, f in _common.read_frames(a.video, None, start=a.frame, max_frames=1))
        else:
            rgb = getattr(data, a.sample)()[..., :3]
        if size:
            rgb = cv2.resize(rgb, size, interpolation=cv2.INTER_AREA)
        out = Path(a.out)
        out.mkdir(parents=True, exist_ok=True)

        an = analyse_frame(rgb, a.quality, keep_stages=True)
        st = an.stages
        px = st["rgb_padded"].astype(np.uint32)
        write_hex(out / "pixels.hex", px[..., 0] | (px[..., 1] << 8) | (px[..., 2] << 16), 32)
        write_hex(out / "blocks.hex", st["blocks"], 8)
        write_hex(out / "coeffs.hex", st["coeffs"], 16)
        write_hex(out / "quant.hex", st["quant"], 16)
        write_hex(out / "qtable_luma.hex", an.qy, 8)
        write_hex(out / "qtable_chroma.hex", an.qc, 8)
        write_hex(out / "dct_matrix.hex", DCT_C, 16)
        np.savez(out / "stages.npz", **st)          # same data for Python testbenches
        write_symbols(out, "plain", an.symbols)

        plain = package_frame(an)
        write_hex(out / "scan_plain.hex", np.frombuffer(plain.scan, np.uint8), 8)
        (out / "plain.jpg").write_bytes(plain.jpeg)
        ks = ascon.keystream(key, ascon.make_nonce(a.session, a.ctr, 0), a.keystream_bytes)
        write_hex(out / "keystream.hex", np.frombuffer(ks, np.uint8), 8)

        cfg = dict(width=an.width, height=an.height, padded=list(st["rgb_padded"].shape[:2][::-1]),
                   n_mcu=an.n_mcu, n_blocks=an.n_mcu * 6, quality=a.quality, key=key.hex(),
                   session_id=a.session, frame_ctr=a.ctr,
                   nonce_enc=ascon.make_nonce(a.session, a.ctr, 0).hex(),
                   nonce_mac=ascon.make_nonce(a.session, a.ctr, 1).hex(),
                   plain_scan_bytes=len(plain.scan), plain_payload_bits=plain.payload_bits, modes={})
        for mode in MODES:
            enc = package_frame(an, key, a.session, a.ctr, mode)
            write_symbols(out, mode, enc.symbols)
            write_hex(out / f"scan_{mode}.hex", np.frombuffer(enc.scan, np.uint8), 8)
            (out / f"frame_{mode}.jpg").write_bytes(enc.jpeg)
            cfg["modes"][mode] = dict(mode_id=MODE_ID[mode], scan_bytes=len(enc.scan),
                                      encrypted_bits=enc.enc_bits, tag=enc.tag.hex())
        (out / "config.json").write_text(json.dumps(cfg, indent=2))
        print(f"vectors for {an.width}x{an.height} ({an.n_mcu} MCUs, {len(an.symbols)} symbols) -> {out}/")


    if __name__ == "__main__":
        main()

# ==================================================================================================
# test-video   (was scripts/make_test_video.py)
# ==================================================================================================
elif CMD == "test-video":
    """Creates a test video so you can run everything without your own footage.

Pans and zooms across scikit-image sample photos (faces, text-like detail, flat
areas, fine texture) with a moving overlay and a frame counter.

    python scripts/make_test_video.py --out test_video.mp4 --frames 90 --size 640x480
"""
    import argparse

    import cv2
    import numpy as np
    from skimage import data


    def main():
        ap = argparse.ArgumentParser()
        ap.add_argument("--out", default="test_video.mp4")
        ap.add_argument("--frames", type=int, default=90)
        ap.add_argument("--size", default="640x480")
        ap.add_argument("--fps", type=float, default=30)
        a = ap.parse_args()
        W, H = _common.parse_size(a.size)

        sources = [data.astronaut(), data.coffee(), data.rocket(), data.chelsea()]
        sources = [cv2.resize(s, (int(W * 1.4), int(H * 1.4)), interpolation=cv2.INTER_CUBIC)
                   for s in sources]
        per = max(1, a.frames // len(sources))
        vw = cv2.VideoWriter(a.out, cv2.VideoWriter_fourcc(*"mp4v"), a.fps, (W, H))
        for f in range(a.frames):
            src = sources[min(f // per, len(sources) - 1)]
            t = (f % per) / max(1, per - 1)
            sh, sw = src.shape[:2]
            x0 = int((sw - W) * t)
            y0 = int((sh - H) * (0.5 + 0.5 * np.sin(2 * np.pi * t)) )
            frame = src[y0:y0 + H, x0:x0 + W].copy()
            cx = int(W * (0.1 + 0.8 * t))
            cv2.circle(frame, (cx, H - 60), 30, (255, 220, 0), -1)
            cv2.putText(frame, f"FRAME {f:04d}  CAM-01", (12, 36), cv2.FONT_HERSHEY_SIMPLEX, 1.0,
                        (255, 255, 255), 2, cv2.LINE_AA)
            vw.write(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
        vw.release()
        print(f"wrote {a.out}: {a.frames} frames, {W}x{H} @ {a.fps} fps")


    if __name__ == "__main__":
        main()

# ==================================================================================================
# bundle   (was scripts/debug_bundle.py)
# ==================================================================================================
elif CMD == "bundle":
    """Re-run one failing test and package everything Claude needs into one file.

Usage:
    python scripts/debug_bundle.py tb/test_dct_quant.py::test_dct8x8
    python scripts/debug_bundle.py tb/test_top.py::test_secure_jpeg_top --seed 1234

Writes debug_bundle.md: environment, the exact command, seed, the failure
message (first mismatch), the log tail, the RTL under test, the matching
golden-model functions and the testbench. Paste or attach it to Claude
together with one sentence on what you changed last.
"""
    import argparse
    import datetime
    import importlib
    import inspect
    import os
    import platform
    import re
    import subprocess
    import sys
    from pathlib import Path

    ROOT = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "tb"))

    TEST_TO_TOP = {
        "test_ascon_core": "ascon_aead128_core", "test_keystream_gen": "keystream_gen",
        "test_tag_unit": "tag_unit", "test_rgb2ycbcr_block": "rgb2ycbcr_block",
        "test_dct8x8": "dct8x8", "test_quantiser": "quantiser",
        "test_zigzag_rle": "zigzag_rle", "test_selective_enc": "selective_enc",
        "test_huffman_packer": "huffman_packer", "test_secure_jpeg_top": "secure_jpeg_top",
    }
    SHARED = {"ascon_round.v", "ascon_aead128_core.v"}
    MAX_FILE_LINES = 400

    PROMPT = """\
I'm building a hardware JPEG encoder with in-loop selective encryption (Ascon-AEAD128)
for a PYNQ-Z2, verified with cocotb against a Python golden model (the model is
the referee; RTL must match it bit for bit). The test below fails.
What I changed last: <ONE SENTENCE>
Please (1) explain the most likely root cause, pointing at the exact RTL line,
(2) propose the smallest fix, and (3) say how to confirm it (which signal at
which cycle in the waveform). Don't change the golden model unless it disagrees
with the JPEG (ITU-T T.81) or Ascon (NIST SP 800-232) standard.
"""


    def sh(cmd):
        try:
            return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30).stdout.strip()
        except Exception as e:                      # noqa: BLE001
            return f"(failed: {e})"


    def model_refs(rtl_text):
        """Golden-model functions named in an RTL header: 'Golden model: model/x.py :: f(), g()'."""
        out = []
        for m in re.finditer(r"Golden model:\s*model/(\w+)\.py\s*::\s*([^\n]+)", rtl_text):
            mod = importlib.import_module("model." + m.group(1))
            for name in re.findall(r"(\w+)\(\)", m.group(2)):
                if hasattr(mod, name):
                    out.append((f"model/{m.group(1)}.py", name, inspect.getsource(getattr(mod, name))))
        return out


    def fenced(lang, text):
        lines = text.splitlines()
        if len(lines) > MAX_FILE_LINES:
            lines = lines[:MAX_FILE_LINES] + [f"... ({len(lines) - MAX_FILE_LINES} more lines cut)"]
        return f"```{lang}\n" + "\n".join(lines) + "\n```\n"


    def main():
        ap = argparse.ArgumentParser()
        ap.add_argument("test", help="pytest node id, e.g. tb/test_dct_quant.py::test_dct8x8")
        ap.add_argument("--seed", help="reproduce a specific random seed")
        ap.add_argument("--out", default="debug_bundle.md")
        a = ap.parse_args()

        env = dict(os.environ)
        if a.seed:
            env["SEED"] = a.seed
        cmd = [sys.executable, "-m", "pytest", "-x", "-s", "-q", a.test]
        print("running:", " ".join(cmd))
        res = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True)
        log = res.stdout + res.stderr
        (ROOT / "sim_build").mkdir(exist_ok=True)
        (ROOT / "sim_build" / "last_test.log").write_text(log)

        seeds = sorted(set(re.findall(r"re-run with SEED=(\d+)", log)))
        failure = [l for l in log.splitlines()
                   if re.search(r"Error|assert|mismatch|differ|FAIL|Timeout|expected|got ", l)]
        func = a.test.split("::")[-1]
        top = TEST_TO_TOP.get(func)

        parts = ["# Debug bundle\n", f"_Generated {datetime.datetime.now():%Y-%m-%d %H:%M}_\n\n",
                 "## Prompt (edit the first line)\n\n", PROMPT, "\n## Environment\n\n",
                 fenced("text", "\n".join([
                     f"OS: {platform.platform()}", f"Python: {sys.version.split()[0]}",
                     f"cocotb: {sh(sys.executable + ' -c \"import cocotb;print(cocotb.__version__)\"')}",
                     f"simulator: {os.getenv('SIM', 'icarus')} / {sh('iverilog -V 2>&1 | head -1')}",
                     f"git: {sh('git -C ' + str(ROOT) + ' log -1 --oneline 2>/dev/null') or '(not a git repo)'}",
                     f"uncommitted changes: {sh('git -C ' + str(ROOT) + ' status --short 2>/dev/null') or '(none / no git)'}"])),
                 "\n## Command\n\n", fenced("bash", ("SEED=" + a.seed + " " if a.seed else "") + " ".join(cmd[1:])),
                 f"\nResult: {'PASSED' if res.returncode == 0 else 'FAILED'}; random seed(s): {', '.join(seeds) or 'n/a'}\n",
                 "\n## Failure lines\n\n", fenced("text", "\n".join(failure[:40]) or "(none found)"),
                 "\n## Log tail\n\n", fenced("text", "\n".join(log.splitlines()[-60:]))]

        if top:
            import common
            files = common.SOURCES[top]
            if top == "secure_jpeg_top":
                files = ["secure_jpeg_top.v"]
                parts.append("\n> Full-system test: localise the failing stage first "
                             "(compare against vectors/ from `python -m model.gen_vectors`), "
                             "then make a bundle for that block's unit test.\n")
            elif top not in ("ascon_aead128_core", "keystream_gen", "tag_unit"):
                files = [f for f in files if f not in SHARED]
            parts.append("\n## RTL under test\n")
            refs = []
            for f in files:
                text = (ROOT / "rtl" / f).read_text()
                parts += [f"\n### rtl/{f}\n\n", fenced("verilog", text)]
                refs += model_refs(text)
            if refs:
                parts.append("\n## Golden model (the referee)\n")
                seen = set()
                for path, name, src in refs:
                    if name not in seen:
                        seen.add(name)
                        parts += [f"\n### {path} :: {name}()\n\n", fenced("python", src)]
        test_file = ROOT / a.test.split("::")[0]
        if test_file.exists():
            parts += [f"\n## Testbench {test_file.relative_to(ROOT)}\n\n", fenced("python", test_file.read_text())]

        out = ROOT / a.out
        out.write_text("".join(parts))
        print(f"{'PASSED' if res.returncode == 0 else 'FAILED'} -> wrote {out.relative_to(ROOT)} "
              f"({out.stat().st_size // 1024} KB). Attach it to Claude; full log in sim_build/last_test.log")


    if __name__ == "__main__":
        main()
