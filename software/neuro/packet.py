"""Packets of an EVT 2.0 stream (DESIGN §3.1-§3.3, §2.4 rules 1-3 and 6).

    V0-V3:  header (48 B) || payload (4*n_words B) || trailer || tag (16 B)
            trailer = [bitmap (4*ceil(n_cd/32) B), only if PAD] || n_words (4) || n_cd (4) || rsvd (4)
    V4:     header (48 B) || ascon.encrypt(K_aead, nonce(sid, ctr, 0), AD = header, P = payload || trailer)

Header and trailer integers are big-endian; payload words are little-endian (AXI word j = bytes 4j..4j+3).

`Packetizer` is the stateful time-grid packetizer shared by `packetize()` (batch) and `neuro.sender`
(streaming). It applies the input rules (pre-TIME_HIGH, backwards TIME_HIGH, out-of-range CD word, time jump)
and the closing rule: the open packet closes when a TIME_HIGH with 64*value >= t_start + T arrives; grid
packets in between are emitted empty with needs_tables = False; the arriving TIME_HIGH opens its packet.
"""
from dataclasses import dataclass, field
import struct

import numpy as np

from . import VERSION
from .evt2 import CD_ON, TH_MASK, TIME_HIGH, _check_T

MAGIC = b"NVE1"
HEADER_LEN = 48
TRAILER_FIXED = 12
TAG_LEN = 16
ROUNDS = 8
LINK_NONE = (1 << 64) - 1
F_PAD, F_FIRST, F_FINAL = 1, 2, 4
_HDR = struct.Struct(">4sBBBBQQQHHHBBQ")
assert _HDR.size == HEADER_LEN


@dataclass(frozen=True)
class PacketHeader:
    level: int
    flags: int
    ts_bits: int
    session_id: int
    packet_ctr: int
    t_start: int
    W: int
    H: int
    T_us: int
    pad_policy: int = 0
    link: int = LINK_NONE
    rounds: int = ROUNDS
    version: int = VERSION
    magic: bytes = MAGIC

    @property
    def pad(self):
        return bool(self.flags & F_PAD)

    @property
    def first(self):
        return bool(self.flags & F_FIRST)

    @property
    def final(self):
        return bool(self.flags & F_FINAL)

    def pack(self):
        return _HDR.pack(self.magic, self.version, self.level, self.flags, self.ts_bits, self.session_id,
                         self.packet_ctr, self.t_start, self.W, self.H, self.T_us, self.rounds,
                         self.pad_policy, self.link)

    @classmethod
    def unpack(cls, b):
        if len(b) < HEADER_LEN:
            raise ValueError(f"header needs {HEADER_LEN} bytes, got {len(b)}")
        (magic, version, level, flags, ts_bits, sid, ctr, t_start, W, H, T_us, rounds, pad_policy,
         link) = _HDR.unpack(bytes(b[:HEADER_LEN]))
        return cls(level=level, flags=flags, ts_bits=ts_bits, session_id=sid, packet_ctr=ctr, t_start=t_start,
                   W=W, H=H, T_us=T_us, pad_policy=pad_policy, link=link, rounds=rounds, version=version,
                   magic=magic)


def bitmap_len(n_cd):
    return 4 * ((n_cd + 31) // 32)


@dataclass
class Trailer:
    n_words: int
    n_cd: int
    bitmap: bytes = b""
    rsvd: int = 0

    def pack(self):
        return bytes(self.bitmap) + struct.pack(">III", self.n_words, self.n_cd, self.rsvd)

    @classmethod
    def unpack(cls, b, pad):
        """Parse a trailer that ends at the end of b (fixed fields last)."""
        if len(b) < TRAILER_FIXED:
            raise ValueError("trailer too short")
        n_words, n_cd, rsvd = struct.unpack(">III", bytes(b[-TRAILER_FIXED:]))
        bm = b""
        if pad:
            L = bitmap_len(n_cd)
            if len(b) < TRAILER_FIXED + L:
                raise ValueError("trailer too short for its bitmap")
            bm = bytes(b[-TRAILER_FIXED - L:-TRAILER_FIXED])
        return cls(n_words, n_cd, bm, rsvd)

    def __len__(self):
        return len(self.bitmap) + TRAILER_FIXED


@dataclass
class Packet:
    header: PacketHeader
    payload: np.ndarray            # uint32 words (V0-V3); for V4 the decrypted plaintext words, if known
    trailer: Trailer
    tag: bytes = b""
    body: bytes = b""              # V4: ciphertext of payload || trailer (without the tag)

    def to_bytes(self):
        if self.header.level == 4:
            return self.header.pack() + self.body + self.tag
        return (self.header.pack() + np.asarray(self.payload, dtype="<u4").tobytes() + self.trailer.pack()
                + self.tag)

    def to_words(self):
        b = self.to_bytes()
        assert len(b) % 4 == 0
        return np.frombuffer(b, dtype="<u4").astype(np.uint32)


def from_bytes(b):
    """Keyless parse of the public framing of a V0-V3 packet (header, payload, trailer, tag). Used by N8-R.

    Trusts the fixed trailer fields at the end, so it gives the right split for genuine packets only; the
    receiver re-checks lengths after the tag (§3.5 step 6).
    """
    b = bytes(b)
    h = PacketHeader.unpack(b)
    if h.level == 4:
        return Packet(h, np.zeros(0, np.uint32), Trailer(0, 0), b[-TAG_LEN:], b[HEADER_LEN:-TAG_LEN])
    tr = Trailer.unpack(b[:-TAG_LEN], h.pad)
    start, end = HEADER_LEN, HEADER_LEN + 4 * tr.n_words
    payload = np.frombuffer(b[start:end], dtype="<u4").astype(np.uint32)
    return Packet(h, payload, tr, b[-TAG_LEN:])


# ------------------------------------------------------------------ packetizer
@dataclass
class RawPacket:
    ctr: int
    t_start: int
    words: np.ndarray
    flags: int = 0
    needs_tables: bool = True       # False for empty packets created by a time skip (§3.2)
    errors: dict = field(default_factory=dict)


ERR_KEYS = ("ERR_PRE_TH", "ERR_ORDER", "ERR_RANGE", "ERR_JUMP")


class Packetizer:
    """Streaming §2.4/§3.2 packetizer. feed() returns the packets closed by the new words."""

    def __init__(self, W, H, T_us=1024, ctr0=0, max_gap_us=1_000_000, jump_mode=0):
        self.W, self.H, self.T = W, H, _check_T(T_us)
        self.ctr0 = ctr0
        self.max_gap_us = max_gap_us
        self.jump_mode = jump_mode
        self.err = dict.fromkeys(ERR_KEYS, 0)
        self.started = False
        self.t_origin = None
        self.k = 0                  # index of the open packet
        self.cur_th = None
        self.open = []
        self.dropping = False       # jump mode 0: dropping until a non-jump TIME_HIGH
        self.halted = False         # jump mode 1
        self.held = []              # words held while halted (the jumping TIME_HIGH first)
        self.words_in = 0
        self.hook = None            # called with each RawPacket as it closes

    @property
    def open_ctr(self):
        return self.ctr0 + self.k

    @property
    def t_start(self):
        return self.t_origin + self.k * self.T

    def _close(self, needs_tables=True, flags=0):
        p = RawPacket(self.ctr0 + self.k, self.t_start, np.array(self.open, dtype=np.uint32), flags,
                      needs_tables)
        self.open = []
        self.k += 1
        if self.hook is not None:      # the sender applies a commit here, before the next packet opens
            self.hook(p)
        return p

    def restart(self, ctr0, T_us=None):
        """New epoch / config at the current grid point: the open packet becomes packet 0 of the new counter."""
        t0 = self.t_start if self.started else None
        if T_us is not None:
            self.T = _check_T(T_us)
        self.ctr0 = ctr0
        if t0 is not None:
            self.t_origin, self.k = t0, 0

    def feed(self, words):
        out = []
        for w in np.asarray(words, dtype=np.uint32).tolist():
            self.words_in += 1
            if self.halted:
                self.held.append(w)
                continue
            out.extend(self._word(w))
        return out

    def _word(self, w):
        typ = w >> 28
        if not self.started:
            if typ != TIME_HIGH:
                self.err["ERR_PRE_TH"] += 1
                return []
            v = w & TH_MASK
            self.started, self.cur_th, self.t_origin, self.k = True, v, 64 * v, 0
            self.open = [w]
            return []
        if typ == TIME_HIGH:
            v = w & TH_MASK
            if v < self.cur_th:
                self.err["ERR_ORDER"] += 1
                return []
            if 64 * v - self.t_start > self.max_gap_us:
                if self.jump_mode == 0:
                    self.err["ERR_JUMP"] += 1
                    self.dropping = True
                    return []
                # halt: close the open packet, emit one empty FINAL packet, hold this word
                out = [self._close()]
                out.append(self._close(needs_tables=False, flags=F_FINAL))
                self.halted = True
                self.held = [w]
                return out
            self.dropping = False
            self.cur_th = v
            out = []
            if 64 * v >= self.t_start + self.T:
                out.append(self._close())
                while 64 * v >= self.t_start + self.T:      # grid may change at a commit inside the run
                    out.append(self._close(needs_tables=False))
            self.open.append(w)
            return out
        if self.dropping:
            self.err["ERR_JUMP"] += 1
            return []
        if typ <= CD_ON:
            x, y = (w >> 11) & 0x7FF, w & 0x7FF
            if x >= self.W or y >= self.H:
                self.err["ERR_RANGE"] += 1
                return []
        self.open.append(w)
        return []

    def flush(self):
        """CTRL.FLUSH: close the open packet, then one empty FINAL packet at the next grid point (§3.2)."""
        if not self.started:
            return []
        return [self._close(), self._close(needs_tables=False, flags=F_FINAL)]

    def resume(self, ctr0, T_us=None):
        """Clear a jump halt for a new epoch: the held TIME_HIGH starts the new grid. Returns closed packets."""
        held, self.held, self.halted = self.held, [], False
        self.started = False
        self.ctr0, self.k = ctr0, 0
        if T_us is not None:
            self.T = _check_T(T_us)
        self.words_in -= len(held)
        return self.feed(held)


def packetize(words, geom, T_us=1024, ctr0=0, max_gap_us=1_000_000, jump_mode=0):
    """Closed packets of a whole word stream (§2.4, §3.2). The open packet at the end is not returned."""
    pz = Packetizer(geom.W, geom.H, T_us, ctr0, max_gap_us, jump_mode)
    out = pz.feed(words)
    for p in out:
        p.errors = dict(pz.err)
    return out
