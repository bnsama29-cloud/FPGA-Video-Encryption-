"""N16: simulated leakage assessment (TVLA) of the masked Ascon round against the unmasked one.

Usage:
    python experiments/neuro_tvla_sim.py [--traces 50000] [--quick]

Method, fixed before the run. A simulation, not a measurement: no glitches, no coupling, no real noise model.
  * Register-level model of hardware/rtl/neuro/nv_ascon_round_dom.v (the 20 registered 64-bit partial products
    p00, p01, p10, p11 of the five ANDs and the 10 registered linear terms l0, l1) and of nv_ascon_round_reg.v
    (input and output registers). The model is checked against software/model/ascon.py (the shares recombine to one
    Ascon round) before any trace is simulated.
  * Leakage per clock: for every 64-bit register, its Hamming weight (value model) and the Hamming distance to the
    previous trace's value in the same register (transition model, traces back to back), plus Gaussian noise of
    standard deviation --noise bits. One sample per register and model.
  * Non-specific fixed-vs-random test (TVLA, ISO 17825 style): fixed state against uniformly random states, classes
    interleaved at random, fresh mask and fresh 320 bits of DOM randomness per trace; Welch's t per sample; the
    usual threshold |t| > 4.5. First order only: a first-order masking is expected to leak at second order.
Writes sim_out/neuro/n16/tvla_sim.{json,md}.
"""
import argparse

import numpy as np

import neuro_common as C
from model import ascon

M64 = np.uint64(0xFFFFFFFFFFFFFFFF)
RC = 0x4B                                  # round constant of the last round (ascon.permutation(S, 1))


def ror(v, n):
    n = np.uint64(n)
    return (v >> n) | (v << (np.uint64(64) - n))


def pre_sbox(x0, x1, x2, x3, x4, rc):
    x2 = x2 ^ np.uint64(rc)
    return x0 ^ x4, x1, x2 ^ x1, x3, x4 ^ x3           # a0, x1, a2, x3, a4


def and_operands(a0, x1, a2, x3, a4):
    """(u, v) of the five ANDs ~u & v, in the order of nv_ascon_round_dom.v: b_i = l_i ^ (~u_i & v_i)."""
    return [(x1, a2), (a2, x3), (x3, a4), (a4, a0), (a0, x1)], [a0, x1, a2, x3, a4]


def post(b, share0=True):
    """Post-S-box affine layer and linear diffusion; the inversion of c2 belongs to share 0 only."""
    c1, c0, c3, c2, c4 = b[1] ^ b[0], b[0] ^ b[4], b[3] ^ b[2], (~b[2] if share0 else b[2]), b[4]
    return [c0 ^ ror(c0, 19) ^ ror(c0, 28), c1 ^ ror(c1, 61) ^ ror(c1, 39), c2 ^ ror(c2, 1) ^ ror(c2, 6),
            c3 ^ ror(c3, 10) ^ ror(c3, 17), c4 ^ ror(c4, 7) ^ ror(c4, 41)]


def dom_registers(S0, S1, R, rc=RC):
    """Registered values of nv_ascon_round_dom for share arrays S0, S1 (5 x n uint64) and randomness R (5 x n).
    Returns (regs: list of 30 arrays, out0, out1). Constants and inversions on share 0 only, as in the RTL."""
    a_0 = pre_sbox(*S0, rc)
    a_1 = pre_sbox(*S1, 0)
    ops0, lin0 = and_operands(*a_0)
    ops1, lin1 = and_operands(*a_1)
    regs, b0, b1 = [], [], []
    for i in range(5):
        u0, v0 = ops0[i]
        u1, v1 = ops1[i]
        u0 = ~u0                                       # ~u = (~u0) ^ u1
        p00, p11 = u0 & v0, u1 & v1
        p01, p10 = (u0 & v1) ^ R[i], (u1 & v0) ^ R[i]
        regs += [p00, p01, p10, p11]
        b0.append(lin0[i] ^ p00 ^ p01)
        b1.append(lin1[i] ^ p11 ^ p10)
    regs += lin0 + lin1
    out0 = post(b0)
    out1 = post(b1, share0=False)
    return regs, out0, out1


def plain_registers(S, rc=RC):
    """Registered values of nv_ascon_round_reg: input register and output register (10 words)."""
    a = pre_sbox(*S, rc)
    ops, lin = and_operands(*a)
    b = [lin[i] ^ (~ops[i][0] & ops[i][1]) for i in range(5)]
    return list(S) + post(b)


def check_against_model(rng, n=64):
    S = rng.integers(0, 2 ** 63, size=(5, n), dtype=np.uint64) * np.uint64(2) + rng.integers(0, 2, (5, n),
                                                                                              dtype=np.uint64)
    m = rng.integers(0, 2 ** 63, size=(5, n), dtype=np.uint64) * np.uint64(2)
    R = rng.integers(0, 2 ** 63, size=(5, n), dtype=np.uint64)
    _, o0, o1 = dom_registers(S ^ m, m, R)
    plain = plain_registers(S)[5:]
    for k in range(n):
        exp = [int(w) for w in S[:, k]]
        ascon.permutation(exp, 1)
        got = [int(o0[i][k] ^ o1[i][k]) for i in range(5)]
        if got != exp or [int(plain[i][k]) for i in range(5)] != exp:
            raise AssertionError(f"leakage model != Ascon round at state {k}: got {got}, expected {exp}")


def traces(regs_fn, fixed, n, rng, noise, masked):
    """Return (samples n x 2r, labels n): HW and HD-to-previous per register, classes interleaved at random."""
    lab = rng.integers(0, 2, n).astype(bool)           # True = fixed
    S = rng.integers(0, 2 ** 63, size=(5, n), dtype=np.uint64) * np.uint64(2) + rng.integers(0, 2, (5, n),
                                                                                              dtype=np.uint64)
    S[:, lab] = np.asarray(fixed, dtype=np.uint64)[:, None]
    if masked:
        rnd = lambda: rng.integers(0, 2 ** 63, size=(5, n), dtype=np.uint64) * np.uint64(2) + rng.integers(
            0, 2, (5, n), dtype=np.uint64)
        m, R = rnd(), rnd()
        regs = regs_fn(S ^ m, m, R)[0]
    else:
        regs = regs_fn(S)
    X = []
    for r in regs:
        hw = np.bitwise_count(r).astype(np.float64)
        hd = np.bitwise_count(r ^ np.roll(r, 1)).astype(np.float64)
        X += [hw, hd]
    X = np.stack(X, axis=1)[1:]                         # the first trace has no predecessor
    X += rng.normal(0, noise, X.shape)
    return X, lab[1:]


def welch_t(X, lab):
    a, b = X[lab], X[~lab]
    va, vb = a.var(0, ddof=1), b.var(0, ddof=1)
    return (a.mean(0) - b.mean(0)) / np.sqrt(va / len(a) + vb / len(b) + 1e-300)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--traces", type=int, default=200_000)
    ap.add_argument("--noise", type=float, default=2.0, help="Gaussian noise per sample, in bits")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    n = 4000 if a.quick else a.traces
    rng = np.random.default_rng(a.seed)
    check_against_model(rng)
    fixed = [0x0123456789ABCDEF, 0xFEDCBA9876543210, 0x0F1E2D3C4B5A6978, 0x8796A5B4C3D2E1F0, 0x1122334455667788]
    res, rows = {}, []
    for name, fn, masked in (("unmasked round (nv_ascon_round_reg)", plain_registers, False),
                             ("DOM round (nv_ascon_round_dom)", dom_registers, True)):
        X, lab = traces(fn, fixed, n, rng, a.noise, masked)
        t = welch_t(X, lab)
        k = int(np.argmax(np.abs(t)))
        res[name] = {"max_abs_t": float(np.abs(t[k])), "samples": int(len(t)), "over_4_5": int((np.abs(t) > 4.5).sum()),
                     "worst_sample": k, "t": [float(v) for v in t]}
        rows.append((name, n, len(t), round(float(np.abs(t[k])), 2), res[name]["over_4_5"]))
    data = {"results": res, "meta": C.meta(a, traces=n, noise=a.noise, threshold=4.5, model="HW + HD per register")}
    md = ["# N16 simulated first-order TVLA (fixed vs random), register-level leakage model", "",
          f"Simulation, not a measurement: Hamming weight and Hamming distance per 64-bit register, Gaussian noise "
          f"{a.noise} bits, no glitches. Threshold |t| = 4.5.", "",
          C.table(["design", "traces", "samples", "max |t|", "samples over 4.5"], rows)]
    C.write("n16", "tvla_sim", data, "\n".join(md), a.out)
    return data


if __name__ == "__main__":
    main()
