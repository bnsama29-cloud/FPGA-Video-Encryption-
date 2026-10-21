"""Frame-size padding (link/wire.py :: SizePadder, pad_jpeg): the side-channel defence of link.pad.

A padded frame must decode and verify exactly like the unpadded one (model receiver and the C fast
receiver), have exactly the size the policy chose, and the policies must behave as documented."""
import numpy as np
import pytest

from link import fastrx, wire
from model import jpeg as mj
from model.testimage import make_image

KEY = bytes(range(16))


def frames(n=6):
    out = []
    for t in range(n):
        an = mj.analyse_frame(make_image(64, 48, "scene" if t % 2 else "noise", t))
        out.append(mj.package_frame(an, KEY, 7, t + 1, "E5" if t % 3 == 0 else "E2").jpeg)
    return out


def test_pad_exact_size_and_decodes_identically():
    for j in frames():
        for extra in (0, 4, 5, 300, 70_000, 140_001):
            p = wire.pad_jpeg(j, len(j) + extra)
            assert len(p) == len(j) + extra, f"padded length {len(p)} != {len(j) + extra}"
            a, b = mj.receive_frame(j, KEY), mj.receive_frame(p, KEY)
            assert b.ok and b.reason == a.reason and b.plain_jpeg == a.plain_jpeg, f"padding {extra} changed the frame"
            c = fastrx.receive_frame(p, KEY)
            assert c.ok and c.plain_jpeg == a.plain_jpeg
            assert mj.verify_frame(p, KEY)


def test_pad_rejects_impossible():
    j = frames(1)[0]
    for extra in (1, 2, 3, -1):
        with pytest.raises(ValueError):
            wire.pad_jpeg(j, len(j) + extra)


def test_tampered_padding_is_harmless_and_tampered_scan_is_not():
    j = frames(1)[0]
    p = bytearray(wire.pad_jpeg(j, len(j) + 100))
    p[10] ^= 0xFF                                 # inside the COM payload
    assert mj.receive_frame(bytes(p), KEY).ok
    p = bytearray(wire.pad_jpeg(j, len(j) + 100))
    p[-10] ^= 0x04                                # inside the scan
    assert not mj.receive_frame(bytes(p), KEY).ok


@pytest.mark.parametrize("policy", ["none", "bucket:1024", "runmax", "window:3"])
def test_policies(policy):
    pad = wire.SizePadder(policy)
    sizes = [5000, 3000, 7000, 7001, 2000, 2500, 9000, 100]
    got = []
    for n in sizes:
        t = pad.target(n)
        assert t == n or t - n >= 4, f"{policy}: target {t} for {n}"
        got.append(t)
    if policy == "none":
        assert got == sizes
    if policy == "bucket:1024":
        assert all(t % 1024 == 0 or t - n >= 4 for t, n in zip(got, sizes)) and got[0] == 5120
    if policy == "runmax":
        assert got == sorted(got), "runmax must never shrink"
        assert got[1] == got[0] and got[4] == got[3]
    if policy == "window:3":
        assert got[5] == 7168, "the 3-frame window still holds the 7001-byte frame"
        assert got[7] == 9216


def test_unknown_policy():
    with pytest.raises(ValueError):
        wire.SizePadder("constant")
