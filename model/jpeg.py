"""Top-level golden model: the whole transmitter and receiver.

Transmitter (what the PYNQ-Z2 does):
    analyse_frame()  : RGB -> YCbCr 4:2:0 -> 8x8 blocks -> DCT -> quantise -> symbols
    package_frame()  : selective encryption -> Huffman/pack/stuff -> tag -> JPEG bytes
    encode_frame()   : both of the above

Receiver (the laptop, key holder):
    receive_frame()  : parse -> verify tag -> replay check -> Huffman decode
                       -> XOR keystream back -> re-pack -> clear JPEG (bit-exact)

Software baseline (b) in the methodology:
    selective_encrypt_jpeg() : takes a plain JPEG and encrypts it after the fact.
    Its output must be byte-identical to the in-encoder path (hardware baseline d).
"""
import hmac
import io
from dataclasses import dataclass, field

import numpy as np
from PIL import Image

from . import ascon
from .color import pad_to_mcu, rgb_to_ycbcr, subsample_420, to_mcu_blocks
from .container import (auth_data, build_jpeg, parse_jpeg, secure_meta)
from .dct_quant import DEFAULT_QUALITY, Q_CHROMA, Q_LUMA, fdct, quantise, tables  # noqa: F401
from .entropy import huffman_decode, huffman_encode, run_length_encode
from .selective import MODE_ID, MODE_NAME, MODES, apply_keystream


@dataclass
class FrameAnalysis:
    width: int
    height: int
    quality: int
    qy: np.ndarray
    qc: np.ndarray
    symbols: list
    n_mcu: int
    stages: dict = field(default_factory=dict)


@dataclass
class EncodedFrame:
    jpeg: bytes
    scan: bytes
    symbols: list             # symbols after encryption (what went into Huffman)
    payload_bits: int         # Huffman + amplitude bits before padding/stuffing
    enc_bits: int             # how many of those bits were encrypted
    tag: bytes = None
    keystream_blocks: int = 0


def analyse_frame(rgb, quality=DEFAULT_QUALITY, keep_stages=False):
    rgb = np.ascontiguousarray(rgb, dtype=np.uint8)
    if rgb.ndim != 3 or rgb.shape[2] != 3:
        raise ValueError("expected an HxWx3 RGB uint8 image")
    H, W = rgb.shape[:2]
    padded = pad_to_mcu(rgb)
    Y, Cb, Cr = rgb_to_ycbcr(padded)
    Cb2, Cr2 = subsample_420(Cb), subsample_420(Cr)
    blocks = to_mcu_blocks(Y, Cb2, Cr2)
    coeffs = fdct(blocks)
    qy, qc = tables(quality)
    qtab = np.stack([qy, qy, qy, qy, qc, qc])
    quant = quantise(coeffs, qtab)
    symbols = run_length_encode(quant)
    stages = {}
    if keep_stages:
        stages = dict(rgb_padded=padded, Y=Y, Cb=Cb2, Cr=Cr2, blocks=blocks,
                      coeffs=coeffs, quant=quant)
    return FrameAnalysis(W, H, quality, qy, qc, symbols, blocks.shape[0], stages)


def package_frame(an, key=None, session_id=0, frame_ctr=0, mode="E2"):
    """key=None -> plain, standard JPEG with no secure segment (baseline a)."""
    if mode not in MODES:
        raise ValueError(f"mode must be one of {list(MODES)}")
    symbols, n_enc, ks_blocks = an.symbols, 0, 0
    if key is not None and mode != "E0":
        ks = ascon.Keystream(key, ascon.make_nonce(session_id, frame_ctr, 0))
        symbols, n_enc = apply_keystream(an.symbols, ks, mode)
        ks_blocks = ks.blocks
    scan, nbits = huffman_encode(symbols)
    if key is None:
        return EncodedFrame(build_jpeg(an.width, an.height, an.qy, an.qc, scan),
                            scan, symbols, nbits, 0)
    meta = secure_meta(MODE_ID[mode], session_id, frame_ctr)
    tag = ascon.mac(key, ascon.make_nonce(session_id, frame_ctr, 1),
                    auth_data(meta, an.width, an.height, scan))
    jpeg = build_jpeg(an.width, an.height, an.qy, an.qc, scan, secure_segment=meta + tag)
    return EncodedFrame(jpeg, scan, symbols, nbits, n_enc, tag, ks_blocks)


def encode_frame(rgb, key=None, session_id=0, frame_ctr=0, mode="E2", quality=DEFAULT_QUALITY):
    return package_frame(analyse_frame(rgb, quality), key, session_id, frame_ctr, mode)


# ---------------------------------------------------------------- receiver ----
class ReplayGuard:
    """Accepts a frame only if its counter is larger than the last one seen in the session."""

    def __init__(self):
        self.last = {}

    def check(self, session_id, frame_ctr):
        last = self.last.get(session_id)
        if last is not None and frame_ctr <= last:
            return "replay"
        status = "gap" if (last is not None and frame_ctr > last + 1) else "ok"
        self.last[session_id] = frame_ctr
        return status


@dataclass
class ReceivedFrame:
    ok: bool
    reason: str               # ok | gap | tag-mismatch | replay | no-secure-segment | malformed
    mode: str = None
    session_id: int = None
    frame_ctr: int = None
    plain_jpeg: bytes = None
    plain_scan: bytes = None


def receive_frame(jpeg, key, guard=None):
    try:
        p = parse_jpeg(jpeg)
    except ValueError as e:
        return ReceivedFrame(False, f"malformed: {e}")
    sec = p.secure()
    if sec is None:
        return ReceivedFrame(False, "no-secure-segment")
    meta, mode_id, session_id, ctr, tag = sec
    mode = MODE_NAME.get(mode_id)
    expected = ascon.mac(key, ascon.make_nonce(session_id, ctr, 1),
                         auth_data(meta, p.width, p.height, p.scan))
    if not hmac.compare_digest(expected, tag) or mode is None:
        return ReceivedFrame(False, "tag-mismatch", mode, session_id, ctr)
    status = guard.check(session_id, ctr) if guard is not None else "ok"
    if status == "replay":
        return ReceivedFrame(False, "replay", mode, session_id, ctr)
    n_mcu = ((p.width + 15) // 16) * ((p.height + 15) // 16)
    try:
        symbols = huffman_decode(p.scan, n_mcu)
    except ValueError as e:
        return ReceivedFrame(False, f"malformed: {e}", mode, session_id, ctr)
    if mode != "E0":
        ks = ascon.Keystream(key, ascon.make_nonce(session_id, ctr, 0))
        symbols, _ = apply_keystream(symbols, ks, mode)
    plain_scan, _ = huffman_encode(symbols)
    qy, qc = p.qtables()
    plain = build_jpeg(p.width, p.height, qy, qc, plain_scan)
    return ReceivedFrame(True, status, mode, session_id, ctr, plain, plain_scan)


def selective_encrypt_jpeg(plain_jpeg, key, session_id, frame_ctr, mode):
    """Software selective encryption of an existing plain JPEG (baseline b)."""
    p = parse_jpeg(plain_jpeg)
    n_mcu = ((p.width + 15) // 16) * ((p.height + 15) // 16)
    symbols = huffman_decode(p.scan, n_mcu)
    if mode != "E0":
        ks = ascon.Keystream(key, ascon.make_nonce(session_id, frame_ctr, 0))
        symbols, _ = apply_keystream(symbols, ks, mode)
    scan, _ = huffman_encode(symbols)
    meta = secure_meta(MODE_ID[mode], session_id, frame_ctr)
    tag = ascon.mac(key, ascon.make_nonce(session_id, frame_ctr, 1),
                    auth_data(meta, p.width, p.height, scan))
    qy, qc = p.qtables()
    return build_jpeg(p.width, p.height, qy, qc, scan, secure_segment=meta + tag)


def full_stream_encrypt(plain_jpeg, key, session_id, frame_ctr):
    """Baseline c: Ascon-AEAD128 over the entire JPEG (unplayable, cost reference)."""
    return ascon.encrypt(key, ascon.make_nonce(session_id, frame_ctr, 0), b"", plain_jpeg)


def decode_pixels(jpeg):
    """Decode any JPEG (scrambled or clear) like a normal viewer would -> RGB uint8."""
    with Image.open(io.BytesIO(jpeg)) as im:
        return np.asarray(im.convert("RGB"))
