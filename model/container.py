"""JPEG file packaging (what the ARM does on the board) and parsing (receiver side).

Frame layout:
    SOI | APP0 (JFIF) | APP11 secure segment | DQT | SOF0 | DHT | SOS | scan data | EOI

APP11 (marker 0xFFEB) secure segment payload, 38 bytes, ignored by normal viewers:
    'SJV1'      4 bytes  identifier
    version     1 byte   (1)
    mode        1 byte   0..4 = E0..E4
    session_id  8 bytes  big-endian
    frame_ctr   8 bytes  big-endian
    tag        16 bytes  Ascon-AEAD128 tag

Authenticated data for the tag (AD):
    meta (first 22 bytes of the segment) || width (2B BE) || height (2B BE) || scan data
so the mode, counter and picture size cannot be changed without detection.
(The frame counter and session id are also inside the nonce.)
"""
from dataclasses import dataclass, field

import numpy as np

from .entropy import (AC_CHROMA_BITS, AC_CHROMA_VALS, AC_LUMA_BITS, AC_LUMA_VALS,
                      DC_CHROMA_BITS, DC_CHROMA_VALS, DC_LUMA_BITS, DC_LUMA_VALS, ZIGZAG)

SECURE_MARKER = 0xEB
SECURE_IDENT = b"SJV1"
SECURE_VERSION = 1
META_LEN = 22
TAG_LEN = 16


def _segment(marker, payload):
    return bytes([0xFF, marker]) + (len(payload) + 2).to_bytes(2, "big") + payload


def secure_meta(mode_id, session_id, frame_ctr):
    return (SECURE_IDENT + bytes([SECURE_VERSION, mode_id]) +
            session_id.to_bytes(8, "big") + frame_ctr.to_bytes(8, "big"))


def auth_data(meta, width, height, scan):
    return meta + width.to_bytes(2, "big") + height.to_bytes(2, "big") + scan


def build_headers(width, height, qy, qc, secure_segment=None):
    out = bytearray(b"\xff\xd8")
    out += _segment(0xE0, b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00")
    if secure_segment is not None:
        out += _segment(SECURE_MARKER, secure_segment)
    qy_zz = np.asarray(qy).reshape(64)[ZIGZAG]
    qc_zz = np.asarray(qc).reshape(64)[ZIGZAG]
    out += _segment(0xDB, bytes([0x00]) + bytes(qy_zz.astype(np.uint8).tolist()) +
                    bytes([0x01]) + bytes(qc_zz.astype(np.uint8).tolist()))
    out += _segment(0xC0, bytes([8]) + height.to_bytes(2, "big") + width.to_bytes(2, "big") +
                    bytes([3, 1, 0x22, 0, 2, 0x11, 1, 3, 0x11, 1]))
    dht = b""
    for tc_th, bits, vals in ((0x00, DC_LUMA_BITS, DC_LUMA_VALS), (0x10, AC_LUMA_BITS, AC_LUMA_VALS),
                              (0x01, DC_CHROMA_BITS, DC_CHROMA_VALS), (0x11, AC_CHROMA_BITS, AC_CHROMA_VALS)):
        dht += bytes([tc_th]) + bytes(bits) + bytes(vals)
    out += _segment(0xC4, dht)
    out += _segment(0xDA, bytes([3, 1, 0x00, 2, 0x11, 3, 0x11, 0, 63, 0]))
    return bytes(out)


def build_jpeg(width, height, qy, qc, scan, secure_segment=None):
    return build_headers(width, height, qy, qc, secure_segment) + scan + b"\xff\xd9"


class JPEGFormatError(ValueError):
    pass


@dataclass
class ParsedJPEG:
    width: int
    height: int
    segments: list = field(default_factory=list)     # [(marker, payload), ...] before scan
    scan: bytes = b""
    end: int = 0                                     # index just after EOI

    def segment(self, marker):
        for m, p in self.segments:
            if m == marker:
                return p
        return None

    def qtables(self):
        """Returns (qy, qc) in natural order from the DQT segment(s)."""
        tabs = {}
        for m, p in self.segments:
            if m != 0xDB:
                continue
            i = 0
            while i < len(p):
                pq, tq = p[i] >> 4, p[i] & 15
                if pq != 0:
                    raise JPEGFormatError("only 8-bit quantisation tables supported")
                nat = np.zeros(64, dtype=np.int32)
                nat[ZIGZAG] = np.frombuffer(p[i + 1:i + 65], dtype=np.uint8)
                tabs[tq] = nat.reshape(8, 8)
                i += 65
        return tabs[0], tabs[1]

    def secure(self):
        """Returns (meta bytes, mode_id, session_id, frame_ctr, tag) or None."""
        p = self.segment(SECURE_MARKER)
        if p is None or len(p) != META_LEN + TAG_LEN or p[:4] != SECURE_IDENT:
            return None
        meta, tag = p[:META_LEN], p[META_LEN:]
        return (meta, meta[5], int.from_bytes(meta[6:14], "big"),
                int.from_bytes(meta[14:22], "big"), tag)


def parse_jpeg(data, start=0):
    """Parses one baseline JPEG starting at `start` (works on concatenated MJPEG)."""
    if data[start:start + 2] != b"\xff\xd8":
        raise JPEGFormatError("missing SOI")
    pos = start + 2
    segs = []
    width = height = None
    while True:
        if pos + 4 > len(data) or data[pos] != 0xFF:
            raise JPEGFormatError(f"expected marker at {pos}")
        m = data[pos + 1]
        length = int.from_bytes(data[pos + 2:pos + 4], "big")
        payload = data[pos + 4:pos + 2 + length]
        segs.append((m, payload))
        pos += 2 + length
        if m == 0xC0:
            height = int.from_bytes(payload[1:3], "big")
            width = int.from_bytes(payload[3:5], "big")
        if m == 0xDA:
            break
    i = pos
    while True:
        j = data.find(b"\xff", i)
        if j < 0 or j + 1 >= len(data):
            raise JPEGFormatError("no EOI found")
        nxt = data[j + 1]
        if nxt == 0x00 or 0xD0 <= nxt <= 0xD7:
            i = j + 2
            continue
        if nxt != 0xD9:
            raise JPEGFormatError(f"unexpected marker 0xFF{nxt:02X} in scan")
        break
    if width is None:
        raise JPEGFormatError("no SOF0")
    return ParsedJPEG(width, height, segs, bytes(data[pos:j]), j + 2)


def split_mjpeg(data):
    """Splits a concatenated MJPEG byte string into individual JPEG frames."""
    frames, pos = [], 0
    while True:
        k = data.find(b"\xff\xd8", pos)
        if k < 0:
            break
        try:
            p = parse_jpeg(data, k)
        except JPEGFormatError:
            pos = k + 2
            continue
        frames.append(bytes(data[k:p.end]))
        pos = p.end
    return frames
