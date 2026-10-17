"""Sign-bit recovery attack (Lin et al., JVCIR 2024, refs.bib lin2024) against the protection levels.

    python experiments/sign_recovery.py                                  # scikit-image test photos
    python experiments/sign_recovery.py --video data/kodak --frames 24 --stride 1 --name kodak
    python experiments/sign_recovery.py --video clip.mp4 --frames 8 --size 160x128 --name clip

Why: E1 and E2 encrypt only signs. Lin et al. recover unknown DCT signs by solving a linear program:
the magnitudes are known, so each unknown coefficient becomes a variable in [-|c|, |c|], and the LP
minimises the total variation (sum of |differences| of neighbouring pixels) subject to the pixels
staying in [0, 255]; the sign of each LP value is the recovered sign. This is their first method (LP
relaxation of the MILP); we do not implement their second (split MILP), so our numbers are a LOWER
bound on what their attack achieves.

What the attacker knows comes from the ciphertext only (huffman_decode of the encrypted scan), per level:
  E1   AC signs unknown, |AC| and DC exact                      -> Lin's setting
  E2   + the signs of the DC differences unknown                -> DC values become LP variables too
       (D_k - D_(k-1) = w_k, w_k in [-|d_k|, |d_k|]) -- our extension of the same LP
  E3   + AC amplitude bits unknown: only the size category s    -> v in [-(2^s - 1), 2^s - 1]
  E4   + DC difference amplitude unknown (size category only)   -> w_k in [-(2^s - 1), 2^s - 1]
  E5   shuffles the MCUs as well; not attacked here (the restart segments are permuted per frame,
       see restart_interval.py / chosen_plaintext.py)
Luma only (as Lin et al.), contract v2 (one scan). The recovered picture is the IDCT of the coefficients
with every unknown taken from the LP solution, projected onto what the attacker knows (sign * |c| for
sign-only fields, the size-category interval for all-bits fields).

Check of the implementation (rows LinU3 / LinU6): Lin et al.'s own setting on the plain stream, only the
signs of the first U AC coefficients in zig-zag order unknown. Their method recovers most of those signs;
ours must too before its E1-E4 numbers mean anything.

Metrics, against the original luma: SSIM, edge correlation (Pearson of Sobel magnitudes, the paper's
leakage measure) and, for E1/E2, the share of AC signs recovered (weighted by |c|). Compared with the
two attacker views the paper already reports: the no-key decode and the replacement attack.
Writes sim_out/sign_recovery/<name>.json / .md.
"""
import argparse
import io
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import scipy.sparse as sp
from PIL import Image
from scipy.optimize import linprog
from skimage.metrics import structural_similarity

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "experiments"))
from model.container import parse_jpeg                                   # noqa: E402
from model.entropy import COMP_OF_BLOCK, ZIGZAG, huffman_decode          # noqa: E402
from model.jpeg import analyse_frame, package_frame, replacement_attack_jpeg   # noqa: E402
from model.selective import MODES                                        # noqa: E402
from learned_attack import bootstrap_ci                                  # noqa: E402

KEY = bytes(range(16))
LEVELS = ("LinU3", "LinU6", "E1", "E2", "E3", "E4")   # LinU*: Lin et al.'s own setting (check)

# orthonormal 8x8 IDCT basis as a decoder uses it: pixel(y, x) = sum_{v,u} B[y, x, v, u] * F[v, u]
_c = np.array([np.sqrt(1 / 8)] + [np.sqrt(2 / 8)] * 7)
_cos = np.array([[np.cos((2 * x + 1) * u * np.pi / 16) for u in range(8)] for x in range(8)])  # [x, u]
BASIS = np.einsum("v,u,yv,xu->yxvu", _c, _c, _cos, _cos).reshape(64, 64)   # [pixel y*8+x, coef v*8+u]


def luma(rgb):
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(np.float64)


def decode(jpeg):
    return np.asarray(Image.open(io.BytesIO(jpeg)).convert("RGB"))


def edge_corr(a, b):
    g = lambda y: np.hypot(cv2.Sobel(y, cv2.CV_64F, 1, 0), cv2.Sobel(y, cv2.CV_64F, 0, 1)).ravel()
    ea, eb = g(a), g(b)
    if ea.std() == 0 or eb.std() == 0:
        return 0.0
    return float(np.corrcoef(ea, eb)[0, 1])


def ssim(a, b):
    return float(max(0.0, structural_similarity(a, b, data_range=255)))


def luma_blocks_from_cipher(jpeg, mode):
    """What an eavesdropper reads from the encrypted scan, per luma block in coding order:
    dict(pos=(by, bx), dc=(size, amp), ac=[(nat_index, size, amp), ...]). amp is the ENCRYPTED amplitude."""
    p = parse_jpeg(jpeg)
    W, H = p.width, p.height
    mcu_w = (W + 15) // 16
    n_mcu = mcu_w * ((H + 15) // 16)
    qy, _ = p.qtables()
    syms = huffman_decode(p.scan, n_mcu)
    out, blk, k, cur = [], -1, 64, None
    for s in syms:
        if s.is_dc:
            blk += 1
            m, b = divmod(blk, 6)
            cur = None
            if COMP_OF_BLOCK[b] == 0:
                my, mx = divmod(m, mcu_w)
                cur = dict(pos=(2 * my + b // 2, 2 * mx + b % 2), dc=(s.size, s.amp), ac=[])
                out.append(cur)
            k = 1
        elif s.eob:
            k = 64
        elif s.size == 0:
            k += 16
        else:
            k += s.run
            if cur is not None:
                cur["ac"].append((int(ZIGZAG[k]), s.size, s.amp))
            k += 1
    return out, W, H, np.asarray(qy, dtype=np.float64).reshape(64)


def sign_recovery(jpeg, mode, lin_u=0):
    """Lin et al.'s LP relaxation (method 1) generalised to E2-E4. Returns (luma image, info, F, ac_var).

    lin_u > 0 reproduces Lin et al.'s own setting on a PLAIN stream (pass mode="E0"): only the signs of
    the first lin_u AC coefficients in zig-zag order are unknown, every other value is known. Used to
    check this implementation against their reported behaviour."""
    cfg = MODES[mode]
    zz_pos = {int(n): i for i, n in enumerate(ZIGZAG)}
    blocks, W, H, q = luma_blocks_from_cipher(jpeg, mode)
    nby, nbx = (H + 15) // 16 * 2, (W + 15) // 16 * 2
    nb = len(blocks)
    # ---- variables: [AC unknowns][D_k (nb)][w_k (nb)][t edges] -------------------------------
    ac_var, lo, hi = [], [], []              # (block, nat index, size, encrypted amp)
    known = np.zeros((nb, 64))               # known coefficient values (quantised units), DC excluded
    for bi, b in enumerate(blocks):
        for (n, s, a) in b["ac"]:
            if lin_u and 1 <= zz_pos[n] <= lin_u:
                M = abs(a)
            elif cfg.ac_all:
                M = (1 << s) - 1
            elif cfg.ac_sign:
                M = abs(a)
            else:
                known[bi, n] = a
                continue
            ac_var.append((bi, n, s, a))
            lo.append(-M)
            hi.append(M)
    nv = len(ac_var)
    iD, iW = nv, nv + nb
    for b in blocks:                         # D_k: free (bounded by the pixel range anyway)
        lo.append(-2048)
        hi.append(2048)
    for b in blocks:
        s, a = b["dc"]
        if cfg.dc_all:
            M = (1 << s) - 1 if s else 0
            lo.append(-M)
            hi.append(M)
        elif cfg.dc_sign:
            lo.append(-abs(a))
            hi.append(abs(a))
        else:
            lo.append(a)
            hi.append(a)
    # pixel rows: x = c0 + P @ z, one row per pixel of the (padded) luma plane
    Hp, Wp = nby * 8, nbx * 8
    blk_at = -np.ones((nby, nbx), dtype=int)
    for bi, b in enumerate(blocks):
        blk_at[b["pos"]] = bi
    by_block = [[] for _ in range(nb)]
    for j, (bi, n, s, a) in enumerate(ac_var):
        by_block[bi].append((j, n))
    rows, cols, vals = [], [], []
    c0 = np.zeros(Hp * Wp)
    for bi, b in enumerate(blocks):
        by, bx = b["pos"]
        pix = ((by * 8 + np.arange(8))[:, None] * Wp + (bx * 8 + np.arange(8))[None, :]).ravel()
        c0[pix] = 128 + BASIS @ (known[bi] * q)
        for j, n in by_block[bi]:
            rows.append(pix)
            cols.append(np.full(64, j))
            vals.append(BASIS[:, n] * q[n])
        rows.append(pix)
        cols.append(np.full(64, iD + bi))
        vals.append(BASIS[:, 0] * q[0])
    nz = iW + nb
    npx = Hp * Wp
    P = sp.csr_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))),
                      shape=(npx, nz))
    # variables: [z (nz)][x pixels (npx)][t edges (ne)]; x = c0 + P z (equalities),
    # |x_a - x_b| <= t for horizontal and vertical neighbours, minimise sum t (TV-L1, Lin et al. eq. 3)
    idx = np.arange(npx).reshape(Hp, Wp)
    a_idx = np.concatenate([idx[:, :-1].ravel(), idx[:-1, :].ravel()])
    b_idx = np.concatenate([idx[:, 1:].ravel(), idx[1:, :].ravel()])
    ne = len(a_idx)
    nvar = nz + npx + ne
    e = np.arange(ne)
    Dx = sp.csr_matrix((np.concatenate([np.ones(ne), -np.ones(ne)]),
                        (np.concatenate([e, e]), np.concatenate([a_idx, b_idx]))), shape=(ne, npx))
    I = sp.identity(ne, format="csr")
    Z = sp.csr_matrix((ne, nz))
    A_ub = sp.vstack([sp.hstack([Z, Dx, -I]), sp.hstack([Z, -Dx, -I])]).tocsr()
    b_ub = np.zeros(2 * ne)
    # equalities: P z - x = -c0 ; DC chain D_k - D_(k-1) - w_k = 0 (prediction starts at 0)
    er, ec, ev = [], [], []
    for k in range(nb):
        er += [k, k]
        ec += [iD + k, iW + k]
        ev += [1.0, -1.0]
        if k:
            er.append(k)
            ec.append(iD + k - 1)
            ev.append(-1.0)
    chain = sp.csr_matrix((ev, (er, ec)), shape=(nb, nvar))
    A_eq = sp.vstack([sp.hstack([P, -sp.identity(npx, format="csr"), sp.csr_matrix((npx, ne))]),
                      chain]).tocsr()
    b_eq = np.concatenate([-c0, np.zeros(nb)])
    cost = np.concatenate([np.zeros(nz + npx), np.ones(ne)])
    # pixel range relaxed by the worst-case quantisation error, as Lin et al. do (Section 4):
    # x in [0 - (eps + 1), 255 + eps + 1], eps(i, j) = sum_kl |A(i, j, k, l)| Q(k, l) / 2
    eps = np.tile((np.abs(BASIS) @ q / 2 + 1).reshape(8, 8), (nby, nbx)).ravel()
    bounds = list(zip(lo, hi)) + list(zip(-eps, 255 + eps)) + [(0, None)] * ne
    t0 = time.time()
    # HiGHS interior point is ~15x faster than simplex when only signs are unknown (E1, Lin's setting);
    # with DC or amplitudes unknown dual simplex is ~2x faster. Both solve the same LP to optimality; an LP
    # with several optima may round to different signs, so the attack numbers are a lower bound.
    solver = "highs-ipm" if not (cfg.dc_sign or cfg.dc_all or cfg.ac_all) else "highs-ds"
    res = linprog(cost, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq, bounds=bounds, method=solver)
    secs = time.time() - t0
    if res.status != 0:
        raise RuntimeError(f"LP failed: {res.message}")
    z = res.x
    # ---- project onto what the attacker knows and rebuild the luma plane -----------------------
    F = known.copy()
    for j, (bi, n, s, a) in enumerate(ac_var):
        v = z[j]
        sign = 1 if v >= 0 else -1                 # 0 -> + (Lin et al.'s option 2)
        if cfg.ac_all:
            mag = min(max(abs(v), 1 << (s - 1)), (1 << s) - 1)
        else:
            mag = abs(a)
        F[bi, n] = sign * round(mag)
    Dk = np.round(z[iD:iD + nb])
    F[:, 0] = Dk
    img = np.zeros((Hp, Wp))
    for bi, b in enumerate(blocks):
        by, bx = b["pos"]
        img[by * 8:by * 8 + 8, bx * 8:bx * 8 + 8] = (128 + BASIS @ (F[bi] * q)).reshape(8, 8)
    img = np.clip(np.round(img), 0, 255)[:H, :W]
    return img, dict(lp_seconds=round(secs, 2), unknown_ac=nv, blocks=nb, solver=solver), F, ac_var


def sign_accuracy(F, ac_var, truth_luma_blocks):
    """Share of unknown AC signs recovered, weighted by |c| (truth from the plain analysis)."""
    num = den = 0.0
    for (bi, n, s, a) in ac_var:
        t = truth_luma_blocks[bi][n]
        if t == 0:
            continue
        w = abs(t)
        den += w
        num += w * (np.sign(F[bi, n]) == np.sign(t))
    return num / den if den else float("nan")


def truth_blocks(an, W):
    """Plain quantised luma blocks (natural order, 64) in the same coding order as luma_blocks_from_cipher."""
    out = []
    for m in range(an.quant.shape[0]):
        for b in range(4):
            out.append(an.quant[m, b].reshape(64))
    return out


def frames_from(args):
    if args.video:
        from link.sources import open_source
        w, h = map(int, args.size.split("x"))
        src = open_source(args.video, w, h, loop=False)
        n = 0
        for i in range(args.frames * args.stride):
            f = src.read()
            if f is None:
                break
            if i % args.stride == 0:
                yield f"{args.name}#{i}", f
                n += 1
        return
    from skimage import data
    w, h = map(int, args.size.split("x"))
    names = ("astronaut", "coffee", "chelsea", "rocket", "camera", "cat", "immunohistochemistry", "motorcycle_left")
    if args.photos:
        names = tuple(args.photos.split(","))
    for nm in names[:args.frames]:
        try:
            im = getattr(data, nm)()
        except Exception:                           # some need pooch downloads
            continue
        if im.ndim == 2:
            im = np.stack([im] * 3, -1)
        im = im[..., :3]
        yield nm, cv2.resize(im, (w, h), interpolation=cv2.INTER_AREA)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", default=None, help="video file, folder of images or webcam (link.sources)")
    ap.add_argument("--frames", type=int, default=8)
    ap.add_argument("--stride", type=int, default=15)
    ap.add_argument("--size", default="128x96", help="WxH, multiple of 16 (LP size grows with the area)")
    ap.add_argument("--quality", type=int, default=75)
    ap.add_argument("--levels", nargs="+", default=list(LEVELS))
    ap.add_argument("--photos", default="", help="comma list of scikit-image photo names (default: all eight)")
    ap.add_argument("--name", default="skimage")
    ap.add_argument("--out", default=str(ROOT / "sim_out" / "sign_recovery"))
    a = ap.parse_args()

    rows = []
    for tag, rgb in frames_from(a):
        an = analyse_frame(rgb, quality=a.quality)
        y0 = luma(rgb)
        truth = truth_blocks(an, rgb.shape[1])
        for mode in a.levels:
            lin_u = int(mode[4:]) if mode.startswith("LinU") else 0
            jpeg = package_frame(an, KEY, 7, 1, "E0" if lin_u else mode).jpeg
            img, info, F, ac_var = sign_recovery(jpeg, "E0" if lin_u else mode, lin_u=lin_u)
            nokey = luma(decode(jpeg))
            repl = luma(decode(replacement_attack_jpeg(jpeg)))
            r = dict(frame=tag, mode=mode, **info,
                     ssim_lp=ssim(y0, img), edge_lp=edge_corr(y0, img),
                     ssim_nokey=ssim(y0, nokey), edge_nokey=edge_corr(y0, nokey),
                     ssim_repl=ssim(y0, repl), edge_repl=edge_corr(y0, repl))
            if lin_u or not MODES[mode].ac_all:
                r["sign_acc"] = sign_accuracy(F, ac_var, truth)
            rows.append(r)
            print(f"{tag:>22} {mode}: LP SSIM {r['ssim_lp']:.3f} edge {r['edge_lp']:.3f} | "
                  f"replacement SSIM {r['ssim_repl']:.3f} edge {r['edge_repl']:.3f}"
                  + (f" | signs {r['sign_acc']:.3f}" if "sign_acc" in r else "")
                  + f"  ({info['lp_seconds']} s, {info['unknown_ac']} unknown AC)", flush=True)

    summary = {}
    for mode in a.levels:
        rs = [r for r in rows if r["mode"] == mode]
        if not rs:
            continue
        s = {}
        for key in ("ssim_lp", "edge_lp", "ssim_repl", "edge_repl", "ssim_nokey", "edge_nokey", "sign_acc"):
            vals = [r[key] for r in rs if key in r]
            if vals:
                m = float(np.mean(vals))
                lo, hi = bootstrap_ci(vals)
                s[key] = dict(mean=round(m, 3), lo=round(lo, 3), hi=round(hi, 3))
        s["frames"] = len(rs)
        s["best_attack_edge"] = max(s["edge_lp"]["mean"], s["edge_repl"]["mean"], s["edge_nokey"]["mean"])
        summary[mode] = s

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    meta = dict(source=a.video or "scikit-image test photos", size=a.size, quality=a.quality,
                method="Lin et al. 2024 LP relaxation (method 1), luma, TV-L1 + pixel range; "
                       "E2-E4 generalised (DC chain, size-category intervals)")
    (out / f"{a.name}.json").write_text(json.dumps(dict(meta=meta, summary=summary, rows=rows), indent=1))
    lines = [f"# Sign-bit recovery attack ({a.name}, {a.size}, q{a.quality})", "",
             "| Level | frames | LP attack SSIM | LP attack edge | replacement edge | no-key edge | AC signs recovered |",
             "|---|---|---|---|---|---|---|"]
    fmt = lambda d: f"{d['mean']:.3f} [{d['lo']:.3f}, {d['hi']:.3f}]" if d else "-"
    for mode, s in summary.items():
        lines.append(f"| {mode} | {s['frames']} | {fmt(s['ssim_lp'])} | {fmt(s['edge_lp'])} | "
                     f"{fmt(s['edge_repl'])} | {fmt(s['edge_nokey'])} | {fmt(s.get('sign_acc'))} |")
    (out / f"{a.name}.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
