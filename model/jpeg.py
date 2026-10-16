"""Top-level golden model: the whole transmitter and receiver.

Transmitter (what the PYNQ-Z2 does):
    analyse_frame()  : RGB -> YCbCr 4:2:0 -> 8x8 blocks -> DCT -> quantise -> symbols
    package_frame()  : selective encryption -> Huffman/pack/stuff -> tag -> JPEG bytes
    encode_frame()   : both of the above
    segmented=True   : contract v3 (APP11 version 3): one restart segment per MCU row, each
                       segment with its own DC predictors and its own keystream, so the
                       segments can be coded independently by parallel hardware lanes
                       (rtl/secure_jpeg_lanes_top.v). The bytes do not depend on the lane count.

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
from .entropy import encode_segments, join_restart, split_restart, symbols_to_blocks
from .dct_quant import DEFAULT_QUALITY, Q_CHROMA, Q_LUMA, fdct, quantise, tables  # noqa: F401
from .entropy import huffman_decode, huffman_encode, run_length_encode  # noqa: F401
from .selective import MODE_ID, MODE_NAME, MODES, apply_keystream, replacement_attack, shuffle_order


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
    quant: np.ndarray = None          # quantised blocks (n_mcu, 6, 8, 8), needed for E5


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
    return FrameAnalysis(W, H, quality, qy, qc, symbols, blocks.shape[0], stages, quant)


def _shuffle_key(key):
    """Separate key for the E5 MCU permutation (session id 0 is never used by frames)."""
    return ascon.mac(key, ascon.make_nonce(0, 0, 0), b"E5 MCU shuffle")


def _shuffle_order(key, session_id, frame_ctr, n):
    return shuffle_order(n, ascon.Keystream(_shuffle_key(key), ascon.make_nonce(session_id, frame_ctr, 0)))


def segment_key(key, session_id, frame_ctr):
    """Contract v3: per-frame key of the segment keystreams,
    K_seg = Ascon-MAC(K, N_enc(session_id, frame_ctr), AD = "lanes").
    Under K the nonce N_enc is used only for this derivation in v3 (v2 uses it for the frame
    keystream instead; one session never mixes versions for one counter value).
    Segment s then uses the keystream of (K_seg, make_nonce(s, frame_ctr, 0)); K_seg is
    unique per (key, session, frame), so no (key, nonce) pair repeats."""
    return ascon.mac(key, ascon.make_nonce(session_id, frame_ctr, 0), b"lanes")


def _package_segmented(an, key, session_id, frame_ctr, mode):
    """Contract v3: restart interval = one MCU row; segment s = MCU row s."""
    if MODES[mode].shuffle:
        raise ValueError("E5 is contract v2 only (restart interval of one MCU)")
    per_row = (an.width + 15) // 16
    kseg = segment_key(key, session_id, frame_ctr) if key is not None and mode != "E0" else None
    segs, out_syms, nbits, n_enc, ks_blocks = [], [], 0, 0, 0
    for s, m0 in enumerate(range(0, an.n_mcu, per_row)):
        sym = run_length_encode(an.quant[m0:m0 + per_row])      # fresh DC predictors
        if kseg is not None:
            ks = ascon.Keystream(kseg, ascon.make_nonce(s, frame_ctr, 0))
            sym, n = apply_keystream(sym, ks, mode)
            n_enc += n
            ks_blocks += ks.blocks
        b, n = huffman_encode(sym)
        segs.append(b)
        out_syms += sym
        nbits += n
    scan = join_restart(segs)
    if key is None:
        return EncodedFrame(build_jpeg(an.width, an.height, an.qy, an.qc, scan, restart_interval=per_row),
                            scan, out_syms, nbits, 0)
    meta = secure_meta(MODE_ID[mode], session_id, frame_ctr, version=3)
    tag = ascon.mac(key, ascon.make_nonce(session_id, frame_ctr, 1),
                    auth_data(meta, an.width, an.height, scan))
    jpeg = build_jpeg(an.width, an.height, an.qy, an.qc, scan, secure_segment=meta + tag,
                      restart_interval=per_row)
    return EncodedFrame(jpeg, scan, out_syms, nbits, n_enc, tag, ks_blocks)


def package_frame(an, key=None, session_id=0, frame_ctr=0, mode="E2", segmented=False):
    """key=None -> plain, standard JPEG with no secure segment (baseline a).
    segmented=True -> contract v3 (see the module docstring)."""
    if mode not in MODES:
        raise ValueError(f"mode must be one of {list(MODES)}")
    if segmented:
        return _package_segmented(an, key, session_id, frame_ctr, mode)
    shuffle = key is not None and MODES[mode].shuffle
    symbols, n_enc, ks_blocks = an.symbols, 0, 0
    if shuffle:                                   # E5: restart interval of one MCU
        symbols = run_length_encode(an.quant, restart=True)
    if key is not None and mode != "E0":
        ks = ascon.Keystream(key, ascon.make_nonce(session_id, frame_ctr, 0))
        symbols, n_enc = apply_keystream(symbols, ks, mode)
        ks_blocks = ks.blocks
    if shuffle:
        segs, nbits = encode_segments(symbols)
        order = _shuffle_order(key, session_id, frame_ctr, len(segs))
        scan = join_restart([segs[i] for i in order])
    else:
        scan, nbits = huffman_encode(symbols)
    if key is None:
        return EncodedFrame(build_jpeg(an.width, an.height, an.qy, an.qc, scan),
                            scan, symbols, nbits, 0)
    meta = secure_meta(MODE_ID[mode], session_id, frame_ctr)
    tag = ascon.mac(key, ascon.make_nonce(session_id, frame_ctr, 1),
                    auth_data(meta, an.width, an.height, scan))
    jpeg = build_jpeg(an.width, an.height, an.qy, an.qc, scan, secure_segment=meta + tag,
                      restart_interval=1 if shuffle else 0)
    return EncodedFrame(jpeg, scan, symbols, nbits, n_enc, tag, ks_blocks)


def encode_frame(rgb, key=None, session_id=0, frame_ctr=0, mode="E2", quality=DEFAULT_QUALITY,
                 segmented=False):
    return package_frame(analyse_frame(rgb, quality), key, session_id, frame_ctr, mode, segmented)


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
    if meta[4] == 3:
        return _receive_segmented(p, key, mode, session_id, ctr, status, n_mcu)
    shuffle = MODES[mode].shuffle
    try:
        if shuffle:
            segs = split_restart(p.scan)
            if len(segs) != n_mcu:
                raise ValueError(f"{len(segs)} restart segments for {n_mcu} MCUs")
            order = _shuffle_order(key, session_id, ctr, n_mcu)
            natural = [None] * n_mcu
            for pos, i in enumerate(order):
                natural[i] = segs[pos]
            symbols = [s for seg in natural for s in huffman_decode(seg, 1)]
        else:
            symbols = huffman_decode(p.scan, n_mcu)
    except ValueError as e:
        return ReceivedFrame(False, f"malformed: {e}", mode, session_id, ctr)
    if mode != "E0":
        ks = ascon.Keystream(key, ascon.make_nonce(session_id, ctr, 0))
        symbols, _ = apply_keystream(symbols, ks, mode)
    if shuffle:                                   # back to the canonical (no-restart) coding
        symbols = run_length_encode(symbols_to_blocks(symbols, n_mcu, restart=True))
    plain_scan, _ = huffman_encode(symbols)
    qy, qc = p.qtables()
    plain = build_jpeg(p.width, p.height, qy, qc, plain_scan)
    return ReceivedFrame(True, status, mode, session_id, ctr, plain, plain_scan)


def _receive_segmented(p, key, mode, session_id, ctr, status, n_mcu):
    """Contract v3 receiver: decode and decrypt every MCU-row segment on its own, then re-code
    the clear frame canonically (no restart markers), so the output equals the v2 plain JPEG."""
    per_row = (p.width + 15) // 16
    try:
        if MODES[mode].shuffle:
            raise ValueError("E5 is not defined in contract v3")
        segs = split_restart(p.scan)
        rows = n_mcu // per_row
        if len(segs) != rows:
            raise ValueError(f"{len(segs)} restart segments for {rows} MCU rows")
        kseg = segment_key(key, session_id, ctr)
        blocks = []
        for s, seg in enumerate(segs):
            sym = huffman_decode(seg, per_row)
            if mode != "E0":
                sym, _ = apply_keystream(sym, ascon.Keystream(kseg, ascon.make_nonce(s, ctr, 0)), mode)
            blocks.append(symbols_to_blocks(sym, per_row))
    except ValueError as e:
        return ReceivedFrame(False, f"malformed: {e}", mode, session_id, ctr)
    plain_scan, _ = huffman_encode(run_length_encode(np.concatenate(blocks)))
    qy, qc = p.qtables()
    plain = build_jpeg(p.width, p.height, qy, qc, plain_scan)
    return ReceivedFrame(True, status, mode, session_id, ctr, plain, plain_scan)


def verify_frame(jpeg, key):
    """Tag check only (no decoding): True if the frame is authentic under `key`.
    Cheap -- one Ascon pass over the scan -- for frames we will not display."""
    try:
        p = parse_jpeg(jpeg)
    except ValueError:
        return False
    sec = p.secure()
    if sec is None:
        return False
    meta, _, session_id, ctr, tag = sec
    expected = ascon.mac(key, ascon.make_nonce(session_id, ctr, 1), auth_data(meta, p.width, p.height, p.scan))
    return hmac.compare_digest(expected, tag)


def selective_encrypt_jpeg(plain_jpeg, key, session_id, frame_ctr, mode):
    """Software selective encryption of an existing plain JPEG (baseline b).
    Must give exactly the same bytes as the in-encoder path."""
    p = parse_jpeg(plain_jpeg)
    n_mcu = ((p.width + 15) // 16) * ((p.height + 15) // 16)
    symbols = huffman_decode(p.scan, n_mcu)
    qy, qc = p.qtables()
    an = FrameAnalysis(p.width, p.height, 0, qy, qc, symbols, n_mcu,
                       quant=symbols_to_blocks(symbols, n_mcu))
    return package_frame(an, key, session_id, frame_ctr, mode).jpeg


def replacement_attack_jpeg(jpeg):
    """Best picture an eavesdropper WITHOUT the key gets from a protected frame:
    the encrypted values are replaced by fixed guesses (selective.replacement_attack)
    and re-encoded as a normal JPEG. For E5 the MCUs stay in their shuffled order.
    Works on any frame of this format; returns JPEG bytes."""
    p = parse_jpeg(jpeg)
    sec = p.secure()
    mode = MODE_NAME.get(sec[1], "E2") if sec else "E0"
    n_mcu = ((p.width + 15) // 16) * ((p.height + 15) // 16)
    qy, qc = p.qtables()
    if mode == "E0":
        return build_jpeg(p.width, p.height, qy, qc, p.scan)
    if MODES[mode].shuffle:
        syms = [s for seg in split_restart(p.scan) for s in huffman_decode(seg, 1)]
        segs, _ = encode_segments(replacement_attack(syms, mode))
        return build_jpeg(p.width, p.height, qy, qc, join_restart(segs), restart_interval=1)
    scan, _ = huffman_encode(replacement_attack(huffman_decode(p.scan, n_mcu), mode))
    return build_jpeg(p.width, p.height, qy, qc, scan)


def full_stream_encrypt(plain_jpeg, key, session_id, frame_ctr):
    """Baseline c: Ascon-AEAD128 over the entire JPEG (unplayable, cost reference)."""
    return ascon.encrypt(key, ascon.make_nonce(session_id, frame_ctr, 0), b"", plain_jpeg)


def decode_pixels(jpeg):
    """Decode any JPEG (scrambled or clear) like a normal viewer would -> RGB uint8."""
    with Image.open(io.BytesIO(jpeg)) as im:
        return np.asarray(im.convert("RGB"))
