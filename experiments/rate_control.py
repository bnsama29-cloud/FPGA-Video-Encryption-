"""R3 -- bitrate regulation like motor speed control (research suite).

    python experiments/rate_control.py                                 # synthetic scene, 120 frames
    python experiments/rate_control.py --video clips/x.mp4 --frames 150 --stride 2

A motor drive holds its speed while the load changes by adjusting the voltage. Here the controlled
quantity is the size of each protected frame (bytes), the set point is a byte budget that follows
the available network bandwidth, and the actuator is the JPEG quality factor (5..95). The budget
steps down to 60 % (bandwidth drop) after a third of the clip and up to 120 % after two thirds.

Controllers (all causal: frame t is coded with the quality decided from frames < t):
  fixed      quality 75, no control (today's encoder)
  bang-bang  +-5 quality when the frame is more than 10 % off the budget (a thermostat)
  (error = 100 ln(budget/size), quality changes limited to DQ_MAX per frame by the feedback loops)
  I          incremental integral control: dq = Ki * error (what is often called "P" on a quality knob)
  PI         velocity-form PI, dq = Kp*(e - e_prev) + Ki*e, the usual form in motor drives
  FF+PI      PI plus feed-forward: an online model ln(bytes) = a + b*quality (recursive least squares,
             forgetting factor 0.8) jumps the quality when the budget changes -- the drive pattern of
             a feed-forward torque estimate plus a PI loop
The controllers are told the next frame's budget (the link reports its bandwidth), but measure the
frame size only after coding. Gains were set on the synthetic scene only; the real clips are the test.
The nominal budget is the median frame size at quality 75 over the whole clip (the link is sized for
the clip's typical rate). It used to be the median of the first 5 frames, which made the set point
"a black frame" for clips that open on black (bug #22); frames whose budget is below their size at
the lowest quality cannot be met by any controller and are reported as infeasible.

Metrics: mean |error| %, error after settling (5 frames after each step and infeasible frames
excluded), frames more than
10 % over budget (each one is a latency/queueing risk on the link), settling time after the drop,
overshoot from the second frame after the drop (the first is unavoidable), mean quality, mean SSIM against the original (key holder's picture).
Frames are protected with E2 (the APP11 segment is included in the byte count).
Writes sim_out/rate_control/<name>.json and .md (+ a plot for open/synthetic sources with --plot).
"""
import argparse
import io
import json
import math
import statistics
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from skimage.metrics import structural_similarity

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from link.sources import open_source                       # noqa: E402
from model.jpeg import analyse_frame, package_frame        # noqa: E402

OUT = ROOT / "sim_out" / "rate_control"
KEY = bytes(range(16))
QMIN, QMAX, Q0 = 5, 95, 75
KP, KI, KI_INC = 0.15, 0.20, 0.25   # set on the synthetic scene only; real clips are the test
B_MIN, B_MAX, FF_MAX = 0.005, 0.08, 30.0   # d ln(bytes)/d quality is ~0.015 at 320x240; FF jump bound
DQ_MAX = 15.0                       # slew limit of the feedback loop (quality steps per frame), bug #25


def err(size, target):
    """Control error in the log domain, 100 ln(target/size): symmetric (twice too big = half too
    small) and matched to the plant, whose bytes grow roughly exponentially with quality. The linear
    error 100 (target - size)/target is bounded at -100 % but unbounded above (+900 % after a cut to
    a detailed scene), which drove PI into a limit cycle between quality 5 and 95 (bug #25)."""
    return 100.0 * math.log(target / size)


def step(q, dq):
    return min(QMAX, max(QMIN, q + max(-DQ_MAX, min(DQ_MAX, dq))))


def encode(rgb, q, ctr):
    an = analyse_frame(rgb, int(round(q)))
    size = len(package_frame(an, KEY, 1, ctr, "E2").jpeg)
    pic = np.asarray(Image.open(io.BytesIO(package_frame(an).jpeg)).convert("L"))
    return size, pic


class Fixed:
    name = "fixed"

    def __init__(self):
        self.q = Q0

    def update(self, size, target):
        pass


class BangBang(Fixed):
    name = "bang-bang"

    def update(self, size, target):
        if size > 1.1 * target:
            self.q = max(QMIN, self.q - 5)
        elif size < 0.9 * target:
            self.q = min(QMAX, self.q + 5)


class I(Fixed):
    """Incremental (integral-only) control: q += Ki_inc * error. Often mislabelled 'P'."""
    name = "I"

    def update(self, size, target):
        self.q = step(self.q, KI_INC * err(size, target))


class PI(Fixed):
    """Velocity-form PI (the usual form in drives): dq = Kp*(e - e_prev) + Ki*e; saturation of q
    is the anti-windup (nothing accumulates outside q)."""
    name = "PI"

    def __init__(self):
        super().__init__()
        self.e_prev = 0.0

    def update(self, size, target):
        e = err(size, target)
        self.q = step(self.q, KP * (e - self.e_prev) + KI * e)
        self.e_prev = e


class FFPI(PI):
    """Feed-forward from ln(bytes) = a + b*q (RLS with forgetting) plus the velocity-form PI: the
    model jumps the quality to the predicted value for a new budget, the PI removes the rest."""
    name = "FF+PI"

    def __init__(self, lam=0.8):
        super().__init__()
        self.th = np.array([math.log(5000.0), 0.02])      # a, b (b > 0: more quality, more bytes)
        self.Pm = np.eye(2) * 100.0
        self.lam = lam
        self.last_q = Q0
        self.prev_q = None                                # quality of the frame before last_q
        self.last_target = None

    def update(self, size, target):
        # Estimator windup (bug #23): with q pinned at a limit every regressor is the same, the
        # forgetting factor inflates the covariance by 1/lam per frame and b drifts to nonsense, so the
        # feed-forward then slams q between the limits. Standard remedies: update the model only when
        # the input moved (excitation), and keep b inside its physical range.
        if self.prev_q is None or abs(self.last_q - self.prev_q) >= 1.0:
            x = np.array([1.0, self.last_q])
            y = math.log(size)
            k = self.Pm @ x / (self.lam + x @ self.Pm @ x)
            self.th = self.th + k * (y - x @ self.th)
            self.Pm = (self.Pm - np.outer(k, x @ self.Pm)) / self.lam
            self.th[1] = min(B_MAX, max(B_MIN, self.th[1]))
        self.prev_q = self.last_q
        b = self.th[1]
        super().update(size, target)                      # PI step on the measured error
        if self.last_target is not None and target != self.last_target:
            # budget changed: jump by the model's predicted quality difference (feed-forward), bounded
            jump = (math.log(target) - math.log(self.last_target)) / b
            self.q = min(QMAX, max(QMIN, self.q + max(-FF_MAX, min(FF_MAX, jump))))
        self.last_target = target
        self.last_q = self.q


CONTROLLERS = [Fixed, BangBang, I, PI, FFPI]


def budget(n, b0):
    return [b0 if t < n // 3 else (0.6 * b0 if t < 2 * n // 3 else 1.2 * b0) for t in range(n)]


def prepare(frames):
    """Nominal budget (median size at Q0 over the clip) and each frame's smallest possible size (QMIN)."""
    return dict(b0=statistics.median(encode(f, Q0, 0)[0] for f in frames),
                floor=[encode(f, QMIN, 0)[0] for f in frames])


def run(frames, ctrl_cls, prep=None):
    prep = prep or prepare(frames)
    c = ctrl_cls()
    tgt = budget(len(frames), prep["b0"])
    sizes, qs, ssims = [], [], []
    for t, f in enumerate(frames):
        if isinstance(c, FFPI):
            c.last_q = c.q
        q = c.q
        size, pic = encode(f, q, t + 1)
        sizes.append(size)
        qs.append(q)
        ref = np.asarray(Image.fromarray(f).convert("L"))
        ssims.append(structural_similarity(ref, pic, data_range=255))
        c.update(size, tgt[t + 1] if t + 1 < len(tgt) else tgt[t])   # next budget is known (link report)
    return dict(target=tgt, sizes=sizes, q=qs, ssim=ssims,
                feasible=[fl <= t for fl, t in zip(prep["floor"], tgt)])


def metrics(r):
    n = len(r["sizes"])
    err = [100 * (s - t) / t for s, t in zip(r["sizes"], r["target"])]
    steps = [n // 3, 2 * n // 3]
    feas = r.get("feasible", [True] * n)
    settled = [e for i, e in enumerate(err)
               if not any(st <= i < st + 5 for st in steps) and i >= 5 and feas[i]]
    drop = steps[0]
    settle = None
    for i in range(drop, steps[1] - 2):
        if all(abs(err[j]) <= 10 for j in range(i, i + 3)):
            settle = i - drop
            break
    return dict(mean_abs_err=statistics.mean(abs(e) for e in err),
                settled_abs_err=statistics.mean(abs(e) for e in settled) if settled else None,
                over_budget=sum(e > 10 for e in err) / n,
                settle_frames_after_drop=settle,
                overshoot_after_drop=max(err[drop + 1:steps[1]]),   # frame `drop` is unavoidable
                mean_q=statistics.mean(r["q"]), mean_ssim=statistics.mean(r["ssim"]),
                infeasible=1 - sum(feas) / n)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", default="synthetic")
    ap.add_argument("--frames", type=int, default=120)
    ap.add_argument("--stride", type=int, default=2)
    ap.add_argument("--size", default="320x240")
    ap.add_argument("--name", default=None)
    ap.add_argument("--plot", action="store_true", help="save bytes-vs-budget plot (open sources only)")
    a = ap.parse_args()
    w, h = (int(v) for v in a.size.split("x"))
    name = a.name or Path(a.video).stem
    src = open_source(a.video, w, h, loop=True)
    frames = []
    for i in range(a.frames * a.stride):
        f = src.read()
        if f is None:
            break
        if i % a.stride == 0:
            frames.append(f)
    res = {}
    prep = prepare(frames)
    for cls in CONTROLLERS:
        r = run(frames, cls, prep)
        res[cls.name] = dict(metrics=metrics(r), trace=r)
        print(cls.name, {k: (round(v, 3) if isinstance(v, float) else v) for k, v in res[cls.name]["metrics"].items()})
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}.json").write_text(json.dumps(dict(source=name, frames=len(frames), kp=KP, ki=KI, results=res)))
    f2 = lambda v, fmt: "--" if v is None else format(v, fmt)
    infeas = res["fixed"]["metrics"]["infeasible"]
    md = [f"### R3: bitrate regulation ({name}, {len(frames)} frames, budget 100 % -> 60 % -> 120 % of the "
          f"median size at quality 75; {100 * infeas:.0f} % of frames infeasible even at quality {QMIN})", "",
          "| Controller | Mean abs. error | Error after settling | Frames >10 % over | Settling after drop (frames) | "
          "Overshoot after drop | Mean quality | Mean SSIM |", "|---|---|---|---|---|---|---|---|"]
    for k, v in res.items():
        m = v["metrics"]
        md.append(f"| {k} | {m['mean_abs_err']:.1f} % | {f2(m['settled_abs_err'], '.1f')} % | "
                  f"{100 * m['over_budget']:.0f} % | {f2(m['settle_frames_after_drop'], 'd')} | "
                  f"{m['overshoot_after_drop']:+.0f} % | {m['mean_q']:.0f} | {m['mean_ssim']:.3f} |")
    (OUT / f"{name}.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))
    if a.plot:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(3.5, 2.2), dpi=200)
        t = range(len(frames))
        ax.plot(t, res["fixed"]["trace"]["target"], "k--", lw=1, label="budget")
        for k in ("fixed", "PI", "FF+PI"):
            ax.plot(t, res[k]["trace"]["sizes"], lw=0.9, label=k)
        ax.set_xlabel("frame", fontsize=7)
        ax.set_ylabel("bytes", fontsize=7)
        ax.tick_params(labelsize=6)
        ax.legend(fontsize=6, frameon=False)
        fig.tight_layout()
        fig.savefig(OUT / f"{name}.png")


if __name__ == "__main__":
    main()
