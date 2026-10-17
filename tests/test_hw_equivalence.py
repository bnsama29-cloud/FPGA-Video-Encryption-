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


# ------------------------------------------------- contract v3 (parallel lanes)
@pytest.mark.parametrize("kind,w,h", [("scene", 64, 80), ("noise", 48, 32), ("bars", 16, 64)])
def test_v3_hw_view_equals_golden_frame(kind, w, h):
    """encode_frame_v3 (drives tb/test_lanes_top.py) == jpeg.encode_frame(segmented=True).
    E5: the fabric's frame (raster order) + the ARM's permutation (hw.arm_shuffle) == the golden frame."""
    img = make_image(w, h, kind, seed=w * h)
    for mode in range(6):
        ctr = (1 << 40) + mode
        a = hw.encode_frame_v3(img, 75, mode, KEY, ctr, SID)
        b = encode_frame(img, KEY, SID, ctr, MODE_NAME[mode], 75, segmented=True)
        if mode == 5:
            assert a["tag"] == b.tag, f"{kind} E5: the tag must cover the fabric's raster order"
            a = dict(a, jpeg=hw.arm_shuffle(a["jpeg"], KEY, SID, ctr))
            a["scan"] = hw.split_scan(a["jpeg"])[1]
        assert a["scan"] == b.scan, f"{kind} mode{mode}: v3 scan differs"
        assert a["jpeg"] == b.jpeg, f"{kind} mode{mode}: v3 file differs"


def test_v3_bytes_do_not_depend_on_lane_count():
    img = make_image(64, 112, "scene", seed=3)
    for mode in (4, 5):
        ref = hw.encode_frame_v3(img, 75, mode, KEY, 9, SID, lanes=1)
        for lanes in (2, 4, 8):
            assert hw.encode_frame_v3(img, 75, mode, KEY, 9, SID, lanes=lanes)["jpeg"] == ref["jpeg"]


@pytest.mark.parametrize("mode", ["E0", "E2", "E4", "E5"])
def test_v3_receiver_returns_the_v2_plain_frame(mode):
    """Decrypting a v3 frame gives exactly the plain contract-v2 JPEG, and it decodes to the same
    pixels as the restart-marked frame (restart markers change no sample)."""
    img = make_image(80, 48, "scene", seed=5)
    v3 = encode_frame(img, KEY, SID, 77, mode, segmented=True)
    r = receive_frame(v3.jpeg, KEY)
    assert r.ok and r.plain_jpeg == encode_frame(img).jpeg
    p3 = encode_frame(img, segmented=True).jpeg
    a = np.asarray(Image.open(io.BytesIO(p3)).convert("RGB"))
    b = np.asarray(Image.open(io.BytesIO(encode_frame(img).jpeg)).convert("RGB"))
    assert np.array_equal(a, b)


def test_v3_segments_use_independent_keystreams():
    """Segment s is encrypted under (K_seg, nonce(s, ctr)): changing one segment's content must not
    change the ciphertext of any other segment (that is what lets lanes run independently)."""
    img = make_image(32, 64, "noise", seed=1)
    img2 = img.copy()
    img2[16:32] = 255 - img2[16:32]               # only MCU row 1 differs
    a = hw.encode_frame_v3(img, 75, 4, KEY, 5, SID)["segments"]
    b = hw.encode_frame_v3(img2, 75, 4, KEY, 5, SID)["segments"]
    assert a[1] != b[1] and [a[i] for i in (0, 2, 3)] == [b[i] for i in (0, 2, 3)]


def test_v3_version_byte_is_authenticated():
    img = make_image(32, 32, "scene")
    for m in ("E2", "E5"):
        jpg = bytearray(encode_frame(img, KEY, SID, 3, m, segmented=True).jpeg)
        k = jpg.find(b"SJV1")
        assert jpg[k + 4] == 3
        jpg[k + 4] = 2
        assert receive_frame(bytes(jpg), KEY).reason != "ok", f"{m}: version downgrade accepted"
    with pytest.raises(ValueError):
        hw.encode_frame_v3(img, 75, 6, KEY, 3, SID)


def test_v3_e5_segments_are_mcus_permuted_per_frame_and_authenticated():
    """E5 in contract v3: one restart segment per MCU (DRI = 1), each with its own keystream; the order is
    keyed and changes with the frame counter; swapping two segments, or sending the fabric's raster
    order unshuffled, fails the tag; and the eavesdropper's replacement picture still decodes."""
    from model.container import parse_jpeg
    from model.entropy import split_restart
    from model.jpeg import decode_pixels, replacement_attack_jpeg
    img = make_image(64, 48, "scene", seed=4)
    n_mcu = (64 // 16) * (48 // 16)
    f1 = encode_frame(img, KEY, SID, 10, "E5", segmented=True)
    f2 = encode_frame(img, KEY, SID, 11, "E5", segmented=True)
    assert len(split_restart(f1.scan)) == n_mcu
    o1, o2 = hw.e5_order(KEY, SID, 10, n_mcu), hw.e5_order(KEY, SID, 11, n_mcu)
    assert sorted(o1) == list(range(n_mcu)) and o1 != o2 and o1 != list(range(n_mcu))
    assert receive_frame(f1.jpeg, KEY).ok
    raster = hw.encode_frame_v3(img, 75, 5, KEY, 10, SID)["jpeg"]
    assert receive_frame(raster, KEY).reason == "tag-mismatch", "unshuffled fabric output accepted"
    head, scan = hw.split_scan(f1.jpeg)
    segs = hw.split_segments(scan)
    segs[0], segs[1] = segs[1], segs[0]
    swapped = head + b"".join((hw.RST_MARKERS[(p - 1) % 8] if p else b"") + x for p, x in enumerate(segs)) + b"\xFF\xD9"
    assert receive_frame(swapped, KEY).reason == "tag-mismatch", "segment swap accepted"
    assert parse_jpeg(f1.jpeg).width == 64
    assert decode_pixels(replacement_attack_jpeg(f1.jpeg)).shape == (48, 64, 3)


def test_v3_eavesdropper_sees_exactly_what_it_sees_in_v2():
    """The replacement attack (the dashboard's eavesdropper view, link/channel.py) on a contract-v3 frame
    must decode, and give the same pixels as on the v2 frame: encrypted fields are replaced by fixed
    guesses and clear fields are equal, so the restart segments must not change the picture. Before
    17 Oct the attack decoded a v3 scan as one block and the eavesdropper view stayed empty."""
    from model.jpeg import decode_pixels, encode_frame, replacement_attack_jpeg
    key = bytes(range(16))
    for kind in ("scene", "noise"):
        img = make_image(96, 64, kind, 3)
        for m in ("E0", "E1", "E2", "E3", "E4"):
            a = decode_pixels(replacement_attack_jpeg(encode_frame(img, key, 7, 9, m).jpeg))
            b = decode_pixels(replacement_attack_jpeg(encode_frame(img, key, 7, 9, m, segmented=True).jpeg))
            assert np.array_equal(a, b), f"{kind} {m}: eavesdropper picture differs between v2 and v3"


def test_hardware_e5_gives_the_eavesdropper_the_same_replacement_picture_as_model_e5():
    """E5 in contract v3 (one keystream per MCU segment, tag over raster order) and the model's E5 of
    contract v2 send the MCUs in the same keyed order and encrypt the same fields, so the replacement
    attack -- the picture the jigsaw, chosen-plaintext and recognition experiments start from -- is
    pixel-identical. That is why the paper's E5 security results carry over to the hardware form."""
    from model.jpeg import decode_pixels, replacement_attack_jpeg
    for kind in ("scene", "noise", "bars"):
        img = make_image(96, 64, kind, seed=3)
        a = decode_pixels(replacement_attack_jpeg(encode_frame(img, KEY, SID, 9, "E5").jpeg))
        b = decode_pixels(replacement_attack_jpeg(encode_frame(img, KEY, SID, 9, "E5", segmented=True).jpeg))
        assert np.array_equal(a, b), f"{kind}: hardware E5 gives a different eavesdropper picture"
