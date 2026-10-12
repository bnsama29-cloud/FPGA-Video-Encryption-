"""Golden-model self-tests. Run before trusting the model as the hardware oracle."""
import io

import cv2
import numpy as np
import pytest
from PIL import Image

from model import ascon
from model.color import rgb_to_ycbcr
from model.container import parse_jpeg, split_mjpeg
from model.dct_quant import Q_LUMA, fdct, quantise
from model.entropy import (Symbol, amp_to_bits, bits_to_amp, huffman_decode, huffman_encode,
                           run_length_encode, symbols_to_blocks)
from model.jpeg import (ReplayGuard, analyse_frame, decode_pixels, encode_frame, package_frame,
                        receive_frame, selective_encrypt_jpeg)
from model.metrics import psnr
from model.selective import MODES

KEY = bytes(range(16))


def make_image(h=96, w=136, seed=1):
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:h, 0:w]
    img = np.stack([(x * 255 // w), (y * 255 // h), ((x + y) * 2) % 256], axis=2).astype(np.int32)
    img[h // 5:h // 2, w // 4:w // 2] = [250, 30, 30]                       # flat area
    noise = rng.integers(0, 256, (h // 4, w // 3, 1))
    img[h - h // 4:, :w // 3] = noise                                        # noise patch
    img[::7, :] = 0                                              # sharp lines
    return np.clip(img, 0, 255).astype(np.uint8)


# ---- stage-level edge cases ----------------------------------------------
def test_colour_extremes():
    px = np.array([[[0, 0, 0], [255, 255, 255], [255, 0, 0], [0, 255, 0], [0, 0, 255]]], np.uint8)
    Y, Cb, Cr = rgb_to_ycbcr(px)
    assert Y[0, 0] == 0 and Y[0, 1] == 255 and Cb[0, 0] == 128 and Cr[0, 1] == 128
    for c in (Y, Cb, Cr):
        assert c.min() >= 0 and c.max() <= 255


def test_dct_flat_block_has_only_dc():
    F = fdct(np.full((8, 8), 200))
    assert F[0, 0] == round((200 - 128) * 8) and np.count_nonzero(F) == 1


def test_dct_close_to_float_dct():
    """Fixed-point DCT stays within 1 unit of the exact (float) JPEG DCT."""
    rng = np.random.default_rng(0)
    u = np.arange(8)[:, None]
    x = np.arange(8)[None, :]
    C = np.where(u == 0, np.sqrt(1 / 8), np.sqrt(2 / 8)) * np.cos((2 * x + 1) * u * np.pi / 16)
    for blk in [np.zeros((8, 8)), np.full((8, 8), 255), (np.indices((8, 8)).sum(0) % 2) * 255,
                *rng.integers(0, 256, (200, 8, 8))]:
        exact = C @ (blk - 128.0) @ C.T
        assert np.abs(fdct(blk) - exact).max() <= 1.0


def test_quantise_rounds_half_away_from_zero():
    q = np.full(64, 10)
    c = np.array([5, -5, 4, -4, 15, -15, 0] + [0] * 57)
    assert list(quantise(c, q)[:7]) == [1, -1, 0, 0, 2, -2, 0]
    assert quantise(np.arange(64), Q_LUMA).shape == (64,)        # cocotb example signature


@pytest.mark.parametrize("size", range(1, 12))
def test_amplitude_bits_roundtrip(size):
    for v in list(range(-(1 << size) + 1, -(1 << (size - 1)) + 1)) + \
             list(range(1 << (size - 1), 1 << size)):
        b = amp_to_bits(v, size)
        assert 0 <= b < (1 << size) and bits_to_amp(b, size) == v
        assert bits_to_amp(b ^ ((1 << size) - 1), size) == -v      # inverting all bits = sign flip


def test_run_length_edge_cases():
    q = np.zeros((1, 6, 8, 8), np.int32)
    q[0, 0, 0, 0] = 5                       # Y0: DC only -> DC + EOB
    q[0, 1].flat[[0, 63]] = [3, -1]         # Y1: last coefficient non-zero -> no EOB, ZRLs
    q[0, 2, 7, 7] = 2                       # Y2: 62 zeros then a value
    syms = run_length_encode(q)
    assert syms[0] == Symbol(1, 0, 3, 5, 0, 0) and syms[1].eob == 1
    assert syms[2] == Symbol(1, 0, 2, -2, 0, 0)                 # DC diff 3-5 = -2
    assert any(s.run == 15 and s.size == 0 for s in syms)       # ZRL present
    assert (symbols_to_blocks(syms, 1) == q).all()


def test_byte_stuffing_and_padding():
    """Saturated blocks produce many 0xFF bytes; each must be followed by 0x00."""
    q = np.zeros((4, 6, 8, 8), np.int32)
    q[:, :, 0, :] = 1023
    q[:, :, 0, 0] = [[1023, -1023, 1023, -1023, 1023, -1023]] * 4
    syms = run_length_encode(q)
    scan, nbits = huffman_encode(syms)
    raw = scan.replace(b"\xff\x00", b"\xff")
    assert b"\xff" in raw
    i = scan.find(b"\xff")
    while i >= 0:
        assert scan[i + 1] == 0x00
        i = scan.find(b"\xff", i + 2)
    pad = len(raw) * 8 - nbits
    assert 0 <= pad < 8 and (raw[-1] & ((1 << pad) - 1)) == (1 << pad) - 1   # padded with 1s
    assert huffman_decode(scan, 4) == syms


# ---- whole-frame properties ----------------------------------------------
@pytest.fixture(scope="module")
def frame():
    img = make_image()
    an = analyse_frame(img, keep_stages=True)
    plain = package_frame(an)
    return img, an, plain


def test_plain_jpeg_opens_everywhere(frame):
    img, an, plain = frame
    d = decode_pixels(plain.jpeg)
    assert d.shape == img.shape
    assert psnr(img, d) > 20
    assert cv2.imdecode(np.frombuffer(plain.jpeg, np.uint8), cv2.IMREAD_COLOR) is not None


def test_huffman_roundtrip(frame):
    _, an, plain = frame
    syms = huffman_decode(plain.scan, an.n_mcu)
    assert syms == an.symbols
    assert (symbols_to_blocks(syms, an.n_mcu) == an.stages["quant"]).all()


def test_close_to_libjpeg(frame):
    img, _, plain = frame
    buf = io.BytesIO()
    Image.fromarray(img).save(buf, "JPEG", quality=75, subsampling=2)
    ref = decode_pixels(buf.getvalue())
    assert abs(psnr(img, decode_pixels(plain.jpeg)) - psnr(img, ref)) < 1.5


@pytest.mark.parametrize("mode", list(MODES))
def test_encrypt_decrypt_bit_exact(frame, mode):
    img, an, plain = frame
    enc = package_frame(an, KEY, 9, 41, mode)
    assert len(enc.symbols) == len(an.symbols)
    assert all(a.size == b.size and a.run == b.run for a, b in zip(enc.symbols, an.symbols))
    assert enc.payload_bits == plain.payload_bits             # zero overhead before stuffing
    assert decode_pixels(enc.jpeg).shape == img.shape          # still a valid JPEG
    r = receive_frame(enc.jpeg, KEY)
    assert r.ok and r.mode == mode and r.plain_jpeg == plain.jpeg
    assert selective_encrypt_jpeg(plain.jpeg, KEY, 9, 41, mode) == enc.jpeg
    if mode in ("E2", "E3", "E4"):
        assert psnr(img, decode_pixels(enc.jpeg)) < 15        # scrambled without the key


def test_wrong_key_rejected(frame):
    _, an, _ = frame
    enc = package_frame(an, KEY, 1, 1, "E2")
    bad = bytearray(KEY)
    bad[0] ^= 1
    assert receive_frame(enc.jpeg, bytes(bad)).reason == "tag-mismatch"


def test_tamper_detection(frame):
    _, an, _ = frame
    enc = package_frame(an, KEY, 1, 1, "E2")
    p = parse_jpeg(enc.jpeg)
    scan_start = len(enc.jpeg) - 2 - len(p.scan)
    rng = np.random.default_rng(3)
    for _ in range(50):
        b = bytearray(enc.jpeg)
        i = int(rng.integers(scan_start, len(b) - 2))
        b[i] ^= 1 << int(rng.integers(0, 8))
        assert not receive_frame(bytes(b), KEY).ok
    # change the mode byte inside the APP11 segment
    k = enc.jpeg.find(b"SJV1")
    b = bytearray(enc.jpeg)
    b[k + 5] = 4
    assert receive_frame(bytes(b), KEY).reason == "tag-mismatch"


def test_replay_reorder_drop():
    img = make_image(32, 32)
    an = analyse_frame(img)
    frames = [package_frame(an, KEY, 5, c, "E2").jpeg for c in range(5)]
    g = ReplayGuard()
    assert receive_frame(frames[0], KEY, g).reason == "ok"
    assert receive_frame(frames[0], KEY, g).reason == "replay"
    assert receive_frame(frames[2], KEY, g).reason == "gap"       # frame 1 dropped
    assert receive_frame(frames[1], KEY, g).reason == "replay"    # reordered (late)
    assert receive_frame(frames[3], KEY, g).reason == "ok"


def test_nonce_never_shared_between_frames():
    img = make_image(32, 32)
    a = encode_frame(img, KEY, 1, 0, "E4")
    b = encode_frame(img, KEY, 1, 1, "E4")
    assert a.scan != b.scan and a.tag != b.tag


def test_split_mjpeg_handles_ff_in_tag():
    img = make_image(32, 32)
    stream = b"".join(encode_frame(img, KEY, 2, c, "E2").jpeg for c in range(20))
    assert len(split_mjpeg(stream)) == 20


def test_keystream_bit_accounting(frame):
    _, an, _ = frame
    for mode in MODES:
        ks = ascon.Keystream(KEY, ascon.make_nonce(1, 1, 0))
        from model.selective import apply_keystream
        _, n = apply_keystream(an.symbols, ks, mode)
        assert ks.consumed == n
