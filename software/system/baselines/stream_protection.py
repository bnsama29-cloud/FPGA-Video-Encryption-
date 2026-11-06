"""How the usual ways of protecting a video stream compare with ours, per frame (journal experiment X24).

    python -m system.baselines.stream_protection                      # this machine, synthetic 640x480
    sudo -E python3 -m system.baselines.stream_protection --sizes 320x240 640x480   # on the PYNQ-Z2 (ARM)

Every method protects the same JPEG frames (plain libjpeg-quality frames from the golden model) and is timed
for the protection only, not the JPEG encoding:
  SRTP, AES-128-GCM        RFC 7714: every RTP packet (1200-byte payload) encrypted and authenticated,
                           12-byte RTP header + 16-byte tag per packet
  DTLS 1.2 record, AES-GCM RFC 6347 / 5288: 13-byte record header + 8-byte explicit nonce + 16-byte tag per record
  ChaCha20-Poly1305 packets as SRTP, with ChaCha20-Poly1305 (the usual choice on CPUs without AES instructions)
  Ascon-AEAD128 whole frame the C Ascon of this repository (software/system/arm/native), one 16-byte tag per frame
  ours, E2 / E5 (software)  our C encoder (bit-exact with the RTL) in E2 / E5 minus the same encoder in E0: the
                           extra work of encrypting inside the coder on this CPU (left out if it cannot be built)
Bytes: the overhead each adds on the wire. Playable without key: only ours. Also reported: how many frames per
second the protection alone would allow. Writes sim_out/stream_protection/stream_protection.json and .md.
"""
import argparse
import json
import platform
import statistics
import time
from pathlib import Path

from link.sources import open_source
from model.jpeg import analyse_frame, package_frame

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "sim_out" / "stream_protection"
KEY, SID = bytes(range(16)), 0x5EC0_57A7
RTP_PAYLOAD, RTP_HDR, TAG = 1200, 12, 16
DTLS_HDR, DTLS_NONCE, DTLS_RECORD = 13, 8, 16384


def packets(data, size):
    return [data[i:i + size] for i in range(0, len(data), size)] or [b""]


def med_ms(fn, items, repeat=1):
    t = []
    for it in items:
        t0 = time.perf_counter()
        for _ in range(repeat):
            fn(it)
        t.append((time.perf_counter() - t0) / repeat)
    return 1000 * statistics.median(t)


def overhead_bytes(method, n):
    """Bytes a method adds to an n-byte frame on the wire (headers and tags it introduces)."""
    if method in ("srtp_aesgcm", "chacha20poly1305"):
        return len(packets(bytes(n), RTP_PAYLOAD)) * TAG       # RTP header is there anyway; SRTP adds the tag
    if method == "dtls_aesgcm":
        return len(packets(bytes(n), DTLS_RECORD)) * (DTLS_HDR + DTLS_NONCE + TAG)
    if method == "ascon_frame":
        return TAG
    raise ValueError(method)


def methods():
    """{name: (label, fn(frame bytes, counter) -> protected bytes)} of the methods available here."""
    out = {}
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM, ChaCha20Poly1305
        aes, cc = AESGCM(KEY), ChaCha20Poly1305(bytes(32))

        def srtp(f, i):
            return [aes.encrypt(i.to_bytes(4, "big") + k.to_bytes(8, "big"), p, b"\x80" * RTP_HDR)
                    for k, p in enumerate(packets(f, RTP_PAYLOAD))]

        def dtls(f, i):
            return [aes.encrypt(i.to_bytes(4, "big") + k.to_bytes(8, "big"), p, b"\x17" * DTLS_HDR)
                    for k, p in enumerate(packets(f, DTLS_RECORD))]

        def chacha(f, i):
            return [cc.encrypt(i.to_bytes(4, "big") + k.to_bytes(8, "big"), p, b"\x80" * RTP_HDR)
                    for k, p in enumerate(packets(f, RTP_PAYLOAD))]
        out["srtp_aesgcm"] = ("SRTP, AES-128-GCM (RFC 7714)", srtp)
        out["dtls_aesgcm"] = ("DTLS 1.2 records, AES-128-GCM", dtls)
        out["chacha20poly1305"] = ("RTP packets, ChaCha20-Poly1305", chacha)
    except ImportError:
        pass
    try:
        from model import ascon
        from system.arm import sw_encoder as sw
        if sw.available():
            out["ascon_frame"] = ("Ascon-AEAD128, whole frame (C)",
                                  lambda f, i: sw.ascon_encrypt(KEY, ascon.make_nonce(SID, i, 0), f))
    except Exception:                                    # no compiler / library: leave it out
        pass
    return out


def ours_extra_ms(frames, quality, mode):
    """Median extra time of our C encoder (software/system/arm/native, bit-exact with the RTL) for `mode`
    over the same encoder in E0 on the same frames: the software cost of encrypting inside the coder.
    None when the C library is not available (no compiler)."""
    from model import hw
    from system.arm import sw_encoder as sw
    if not sw.available():
        return None
    luma, chroma = hw.quality_tables(quality)
    rec = [hw.reciprocal(q) for q in luma + chroma]
    e0 = med_ms(lambda f: sw.encode_scan(f, rec, 0, KEY, SID, 1, contract=3), frames)
    em = med_ms(lambda f: sw.encode_scan(f, rec, int(mode[1]), KEY, SID, 1, contract=3), frames)
    return max(0.0, em - e0), em


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", default="synthetic")
    ap.add_argument("--sizes", nargs="+", default=["640x480"])
    ap.add_argument("--frames", type=int, default=20)
    ap.add_argument("--quality", type=int, default=75)
    ap.add_argument("--repeat", type=int, default=5, help="timing repeats per frame")
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    ms = methods()
    res = dict(machine=platform.machine(), python=platform.python_version(), frames=a.frames, sizes={})
    md = [f"# Stream protection per frame on `{platform.machine()}`", "",
          "Protection only (the JPEG frame is already encoded); median over frames.", ""]
    for sz in a.sizes:
        w, h = (int(x) for x in sz.split("x"))
        src = open_source(a.source, w, h, loop=True)
        frames = [src.read() for _ in range(a.frames)]
        ans = [analyse_frame(f, a.quality) for f in frames]
        jpegs = [package_frame(an).jpeg for an in ans]
        mean_bytes = statistics.mean(len(j) for j in jpegs)
        rows = {}
        for k, (label, fn) in ms.items():
            t = med_ms(lambda ij: fn(ij[1], ij[0]), list(enumerate(jpegs)), a.repeat)
            rows[k] = dict(label=label, ms=t, fps_limit=1000 / t if t else None,
                           overhead_bytes=statistics.mean(overhead_bytes(k, len(j)) for j in jpegs),
                           playable_without_key=False, authenticated=True)
        for mode in ("E2", "E5"):
            t = ours_extra_ms(frames, a.quality, mode)
            if t is None:
                continue
            extra, total = t
            sizes = [len(package_frame(an, KEY, SID, 1, mode, segmented=True).jpeg) - len(j)
                     for an, j in zip(ans, jpegs)]
            rows[f"ours_{mode}"] = dict(label=f"ours {mode}, C encoder on this CPU (extra over E0)",
                                        ms=extra, fps_limit=1000 / extra if extra else None,
                                        overhead_bytes=statistics.mean(sizes),
                                        playable_without_key=True, authenticated=True, total_encode_ms=total)
        res["sizes"][sz] = dict(mean_frame_bytes=mean_bytes, methods=rows)
        md += [f"## {sz} (mean frame {mean_bytes:.0f} bytes)", "",
               "| Method | ms / frame | frames/s (protection only) | bytes added | plays without key | authenticated |",
               "|---|---|---|---|---|---|"]
        for r in rows.values():
            fps = f"{r['fps_limit']:.0f}" if r["fps_limit"] else "-"
            md.append(f"| {r['label']} | {r['ms']:.3f} | {fps} | {r['overhead_bytes']:.0f} | "
                      f"{'yes' if r['playable_without_key'] else 'no'} | yes |")
        md += ["", "Ours in hardware adds no time (the encryption is in the encoder's pipeline: "
               "results/board/); the C rows give its cost when the same coder runs in software.", ""]
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "stream_protection.json").write_text(json.dumps(res, indent=2))
    (out / "stream_protection.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
