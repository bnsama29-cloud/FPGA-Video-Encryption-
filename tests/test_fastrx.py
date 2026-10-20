"""link/fastrx.py (receiver with the heavy work in C) must return exactly what the golden model's
receive_frame / verify_frame return: same reason, mode, session, counter, plain JPEG and plain scan,
for valid frames of every level and both contracts (incl. the board's E5 frames after the ARM shuffle),
and for tampered, truncated, wrong-key and replayed frames."""
import random

import pytest

from link import fastrx
from model import hw
from model import jpeg as mj
from model.testimage import make_image

KEY, SID = bytes(range(16)), 0x5EC0_1234_5678
pytestmark = pytest.mark.skipif(not fastrx.available(), reason="no C compiler")


def _frames():
    out = []
    for n, (w, h, kind) in enumerate([(16, 16, "scene"), (64, 48, "noise"), (48, 96, "scene"), (160, 128, "scene")]):
        rgb = make_image(w, h, kind, seed=n) if kind == "noise" else make_image(w, h, kind)
        for m in range(6):                                            # contract v3 as the fabric + ARM make it
            j = hw.encode_frame_v3(rgb, 75, m, KEY, 100 + m, SID)["jpeg"]
            out.append((f"v3 {w}x{h} E{m}", hw.arm_shuffle(j, KEY, SID, 100 + m) if m == 5 else j))
        for m in range(5):                                            # contract v2 (single pipeline)
            out.append((f"v2-hw {w}x{h} E{m}", hw.encode_frame(rgb, 75, m, KEY, 200 + m, SID)["jpeg"]))
        for m in ("E0", "E2", "E4", "E5"):                            # frame-level model (laptop sender)
            out.append((f"model {w}x{h} {m}", mj.encode_frame(rgb, KEY, SID, 300 + n, m).jpeg))
            out.append((f"model-seg {w}x{h} {m}", mj.encode_frame(rgb, KEY, SID, 400 + n, m, segmented=True).jpeg))
    return out


FRAMES = _frames()


def _same(a, b, what):
    for f in ("ok", "reason", "mode", "session_id", "frame_ctr", "plain_scan", "plain_jpeg"):
        x, y = getattr(a, f), getattr(b, f)
        if x != y:
            if isinstance(x, bytes) and isinstance(y, bytes):
                i = next((k for k, (p, q) in enumerate(zip(x, y)) if p != q), min(len(x), len(y)))
                raise AssertionError(f"{what}: {f} differs at byte {i} (got {len(x)} B, expected {len(y)} B)")
            raise AssertionError(f"{what}: {f} = {x!r}, expected {y!r}")


@pytest.mark.parametrize("name,jpeg", FRAMES, ids=[f[0] for f in FRAMES])
def test_valid_frames_match_model(name, jpeg):
    exp = mj.receive_frame(jpeg, KEY)
    assert exp.ok, name
    _same(fastrx.receive_frame(jpeg, KEY), exp, name)
    assert fastrx.verify_frame(jpeg, KEY) == mj.verify_frame(jpeg, KEY)


def test_tampered_truncated_and_wrong_key_frames_match_model():
    rnd = random.Random(7)
    for name, jpeg in FRAMES[::3]:
        cases = [("wrong key", jpeg, bytes(16))]
        for _ in range(6):
            b = bytearray(jpeg)
            i = rnd.randrange(len(b))
            b[i] ^= 1 << rnd.randrange(8)
            cases.append((f"bit flip at {i}", bytes(b), KEY))
        cases.append(("truncated", jpeg[: len(jpeg) * 2 // 3] + b"\xff\xd9", KEY))
        cases.append(("garbage", b"\xff\xd8" + bytes(40), KEY))
        for what, j, k in cases:
            _same(fastrx.receive_frame(j, k), mj.receive_frame(j, k), f"{name}, {what}")
            assert fastrx.verify_frame(j, k) == mj.verify_frame(j, k), f"{name}, {what}"


def test_replay_guard_same_as_model():
    g1, g2 = mj.ReplayGuard(), mj.ReplayGuard()
    seq = [FRAMES[1][1], FRAMES[2][1], FRAMES[1][1], FRAMES[4][1]]     # counters 101, 102, 101 (replay), 104 (gap)
    for i, j in enumerate(seq):
        _same(fastrx.receive_frame(j, KEY, g1), mj.receive_frame(j, KEY, g2), f"frame {i}")


def test_fast_enough_for_the_board_stream():
    """The reason for fastrx: a 320x240 contract-v3 E5 frame must be received well within the 100 ms
    between frames at 10 fps (the model needs ~160 ms on a laptop)."""
    import time
    j = hw.encode_frame_v3(make_image(320, 240, "scene"), 75, 5, KEY, 9, SID)["jpeg"]
    j = hw.arm_shuffle(j, KEY, SID, 9)
    fastrx.receive_frame(j, KEY)
    t = time.perf_counter()
    for _ in range(5):
        assert fastrx.receive_frame(j, KEY).ok
    assert (time.perf_counter() - t) / 5 < 0.03
