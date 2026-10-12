"""One contract, two views: model/hw.py (stage-level, drives the RTL testbenches)
must produce exactly the same bytes as model/jpeg.py (frame-level golden model).

If this file fails, the RTL tests and the system simulation would be checking
against different "truths" -- which is exactly the bug that contract v2 fixed.
"""
import io

import numpy as np
import pytest
from PIL import Image

from model import ascon, hw, tables as T
from model.container import parse_jpeg
from model.dct_quant import fdct, quantise, reciprocal, tables
from model.jpeg import encode_frame, receive_frame
from model.selective import MODE_NAME
from model.testimage import make_image, psnr

KEY = bytes(range(16))
SID = 0xFEEDFACE_C0FFEE01          # full 64-bit session id (contract v2)


@pytest.mark.parametrize("quality", [30, 50, 75, 90])
@pytest.mark.parametrize("kind,w,h", [("scene", 64, 48), ("noise", 32, 32),
                                      ("checker", 48, 16), ("bars", 16, 64)])
def test_hw_view_equals_golden_frame(kind, w, h, quality):
    img = make_image(w, h, kind, seed=w + h)
    for mode in range(5):
        ctr = (1 << 40) + mode                     # exercise the high counter bits
        a = hw.encode_frame(img, quality, mode, KEY, ctr, SID)
        b = encode_frame(img, KEY, SID, ctr, MODE_NAME[mode], quality)
        assert a["scan"] == b.scan, f"{kind} q{quality} mode{mode}: scan differs"
        assert a["tag"] == b.tag, f"{kind} q{quality} mode{mode}: tag differs"
        assert a["jpeg"] == b.jpeg, f"{kind} q{quality} mode{mode}: file differs"


def test_dct_and_quantiser_stage_equal():
    rng = np.random.default_rng(7)
    qy, _ = tables(50)
    recips = [int(r) for r in reciprocal(qy.flatten())]
    for i in range(400):
        blk = rng.integers(0, 256, (8, 8)) if i % 2 else \
            np.clip(np.cumsum(rng.integers(-30, 31, (8, 8)), 1) + 128, 0, 255)
        g = fdct(blk).flatten().tolist()
        h = hw.dct2d([int(v) for v in blk.flatten()])
        assert g == h, f"block {i}: DCT differs at {next(k for k in range(64) if g[k] != h[k])}"
        assert quantise(np.array(h), qy).tolist() == hw.quantise(h, recips)


def test_quantiser_clamps_like_rtl():
    big = np.zeros(64, np.int64)
    big[0], big[1], big[2] = -40000, 40000, -40000
    q = quantise(big, np.ones(64, np.int64))
    assert q[0] == -1024 and q[1] == 1023 and q[2] == -1023


def test_tag_prefix_is_26_bytes_and_authenticated():
    p = hw.tag_prefix(2, 7, SID, 64, 48)
    assert len(p) == 26 and p[:4] == b"SJV1" and p[4] == 2 and p[5] == 2
    assert int.from_bytes(p[6:14], "big") == SID and int.from_bytes(p[14:22], "big") == 7
    assert p[22:] == (64).to_bytes(2, "big") + (48).to_bytes(2, "big")


def test_keystream_bit_order_matches_selective_stage():
    """hw.selective_encrypt (bit lists, RTL view) == model.selective (Keystream.take)."""
    img = make_image(32, 32, "scene")
    for mode in range(1, 5):
        a = hw.encode_frame(img, 75, mode, KEY, 3, SID)
        b = encode_frame(img, KEY, SID, 3, MODE_NAME[mode])
        assert a["keystream_bits_used"] == b.enc_bits


def test_mode_downgrade_is_detected():
    """Contract v1 hole: the RTL tag covered only the scan, so changing the APP11
    mode byte (E2 -> E1) was not detected and the receiver decrypted garbage."""
    jpg = bytearray(hw.encode_frame(make_image(32, 32), 75, 2, KEY, 5, SID)["jpeg"])
    k = jpg.find(b"SJV1")
    jpg[k + 5] = 1
    assert receive_frame(bytes(jpg), KEY).reason == "tag-mismatch"


def _pillow_jpeg(img, quality):
    b = io.BytesIO()
    Image.fromarray(img).save(b, "JPEG", quality=quality, subsampling=2)
    return b.getvalue()


def test_huffman_tables_match_libjpeg():
    data = _pillow_jpeg(make_image(32, 32, "noise"), 75)
    found = {}
    for marker, _, p in hw.segments(data):
        if marker == 0xC4:
            i = 0
            while i < len(p):
                n = sum(p[i + 1:i + 17])
                found[p[i]] = (list(p[i + 1:i + 17]), list(p[i + 17:i + 17 + n]))
                i += 17 + n
    assert found[0x00] == (T.DC_LUMA_BITS, T.DC_LUMA_VALS)
    assert found[0x10] == (T.AC_LUMA_BITS, T.AC_LUMA_VALS)
    assert found[0x01] == (T.DC_CHROMA_BITS, T.DC_CHROMA_VALS)
    assert found[0x11] == (T.AC_CHROMA_BITS, T.AC_CHROMA_VALS)


@pytest.mark.parametrize("kind", ["scene", "bars", "checker"])
def test_quality_close_to_libjpeg(kind):
    img = make_image(128, 96, kind)
    ours = np.array(Image.open(io.BytesIO(hw.encode_frame(img, 75, 0)["jpeg"])).convert("RGB"))
    ref = np.array(Image.open(io.BytesIO(_pillow_jpeg(img, 75))).convert("RGB"))
    assert psnr(ours, img) > psnr(ref, img) - 0.5


def test_receiver_wrapper_verdicts():
    img = make_image(32, 32, "scene")
    f1 = hw.encode_frame(img, 75, 2, KEY, 1, SID)["jpeg"]
    f2 = hw.encode_frame(img, 75, 2, KEY, 2, SID)["jpeg"]
    rx = hw.Receiver(KEY, SID)
    assert rx.process(f1)[0] == "ok" and rx.process(f2)[0] == "ok"
    assert rx.process(f1)[0] == "replay"
    bad = bytearray(f2)
    bad[-6] ^= 0x80
    assert hw.Receiver(KEY, SID).process(bytes(bad))[0] == "tag-mismatch"
    assert hw.Receiver(bytes(16), SID).process(f1)[0] == "tag-mismatch"
    assert hw.Receiver(KEY, SID + 1).process(f1)[0] == "wrong-session"
    plain = hw.encode_frame(img, 75, 0, KEY, 1, SID)["scan"]
    assert hw.split_scan(hw.Receiver(KEY, SID).process(f1)[1])[1] == plain


def test_marker_parsing_regression():
    """0xFF 0xC0 can appear inside APP11 (session id / tag); parse by walking segments."""
    sid = 0x00C0FFEE_00FFC000
    e = hw.encode_frame(make_image(64, 48, "scene"), 75, 2, KEY, 10, sid)
    assert hw.frame_size(e["jpeg"]) == (64, 48)
    assert parse_jpeg(e["jpeg"]).width == 64
    assert hw.Receiver(KEY, sid).process(e["jpeg"])[0] == "ok"


def test_nonce_purposes_differ():
    a = ascon.keystream(KEY, ascon.make_nonce(SID, 1, 0), 32)
    b = ascon.keystream(KEY, ascon.make_nonce(SID, 2, 0), 32)
    c = ascon.keystream(KEY, ascon.make_nonce(SID, 1, 1), 32)
    assert len({a, b, c}) == 3
