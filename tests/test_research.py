"""Research suite (experiments/parallel_lanes.py, rate_control.py, change_driven.py): the claims the
tables rest on, checked on small inputs. The RTL stall profile (R1) runs in experiments/stall_profile.py."""
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))
sys.path.insert(0, str(ROOT))

from model.jpeg import analyse_frame                     # noqa: E402
from model.testimage import make_image                   # noqa: E402


@pytest.fixture(scope="module")
def scene():
    return make_image(96, 64, "scene", seed=3)


# ---------------------------------------------------------------- R2 parallel lanes
def test_lanes_merge_to_the_sequential_bytes_and_decrypt(scene):
    """Lanes over restart segments are exact (plain and with per-segment keystreams), and the
    restart-row file decodes to the same pixels as the standard one."""
    import parallel_lanes as PL
    res = PL.check_exact(analyse_frame(scene), scene)
    bad = [k for k, v in res.items() if not v]
    assert not bad, f"first failing check: {bad[0]} (all: {res})"


def test_sequential_keystream_is_not_lane_safe(scene):
    """The reason for per-segment keystreams: with ONE keystream per frame, coding the second
    segment alone (fresh keystream) gives different bytes than in sequence."""
    import parallel_lanes as PL
    from model import ascon
    from model.entropy import huffman_encode, run_length_encode
    from model.selective import apply_keystream
    an = analyse_frame(scene)
    cols = (an.width + 15) // 16
    segs = PL.segments(len(an.quant), cols)
    sym = [run_length_encode(an.quant[g.start:g.stop]) for g in segs[:2]]
    ks = ascon.Keystream(PL.KEY, ascon.make_nonce(7, 3, 0))
    joint, _ = apply_keystream(sym[0] + sym[1], ks, "E4")
    second_in_sequence = joint[len(sym[0]):]
    alone, _ = apply_keystream(sym[1], ascon.Keystream(PL.KEY, ascon.make_nonce(7, 3, 0)), "E4")
    assert huffman_encode(second_in_sequence)[0] != huffman_encode(alone)[0]


def test_lane_model_reproduces_the_measured_rtl_law():
    """Event model, 1 lane / 2 buffers / 1 px per clock, against the RTL measurements of
    experiments/stall_profile.py (160x128: 1.639, 320x240: 1.570 cycles/pixel)."""
    import parallel_lanes as PL
    for (w, h), measured in (((160, 128), 1.639), ((320, 240), 1.570)):
        got = PL.simulate(w, h)
        assert abs(got - measured) < 0.02, f"{w}x{h}: model {got:.3f}, RTL {measured}"
    assert PL.simulate(640, 480, lanes=2, buffers=3, overlap=True) == pytest.approx(1.0, abs=0.01)


# ---------------------------------------------------------------- R3 rate control
def test_controllers_follow_a_budget_step():
    """On a synthetic sequence the regulated controllers end closer to the budget than a fixed
    quality, and FF+PI settles within a few frames after the drop."""
    import rate_control as RC
    frames = [make_image(96, 64, "scene", seed=s) for s in range(30)]
    res = {c.name: RC.metrics(RC.run(frames, c)) for c in RC.CONTROLLERS}
    assert res["FF+PI"]["settled_abs_err"] < res["fixed"]["settled_abs_err"], res
    assert res["PI"]["settled_abs_err"] < res["fixed"]["settled_abs_err"], res
    assert res["FF+PI"]["settle_frames_after_drop"] is not None and res["FF+PI"]["settle_frames_after_drop"] <= 6, res


# ---------------------------------------------------------------- R4 change-driven
def _moving(n=16):
    """A block over a static scene that is still for 4 frames, moves for 4, and so on, so the
    amount of motion varies over time (a correlation needs variation)."""
    base = make_image(96, 64, "scene", seed=5)
    out, x = [], 8
    for t in range(n):
        if (t // 4) % 2:
            x += 6
        f = base.copy()
        f[16:40, x:x + 12] = (200, 40, 40)
        out.append(f)
    return out


def test_static_scene_sends_nothing_after_the_first_frame():
    import change_driven as CD
    frames = [make_image(96, 64, "scene", seed=5)] * 6
    o, n = CD.run(frames, "map-visible")
    assert o["sent"][0] == n and all(s == 0 for s in o["sent"][1:]), o["sent"]
    assert len(set(o["psnr"])) == 1, f"the picture drifted: {o['psnr']}"   # no drift, no re-sends


def test_constant_rate_hides_the_count_and_padding_hides_the_size():
    import change_driven as CD
    frames = _moving()
    pre = CD.prepare(frames)
    o, n = CD.run(frames, "constant", rate=0.25, pre=pre)
    s = CD.summarise(o, n, "constant")
    assert s["count_corr"] == 0.0                       # the count is the same in every frame
    sp = CD.summarise(CD.pad_sizes(o), n, "constant")
    assert sp["size_corr"] == 0.0 and sp["bytes_ratio"] < 1.0
    ov, _ = CD.run(frames, "map-visible", pre=pre)
    assert CD.summarise(ov, n, "map-visible")["count_corr"] > 0.5   # visible counts do track motion
