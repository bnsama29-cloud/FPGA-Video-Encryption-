"""EVT 2.0 words (DESIGN §2.1, §2.4, §2.5): canonical encoder, decoder, input rules, event equality, RAW files.

One little-endian 32-bit word per event; bits 31..28 are the type.
    CD_OFF / CD_ON   [27:22] ts[5:0], [21:11] x, [10:0] y      (polarity = bit 28)
    EVT_TIME_HIGH    [27:0]  ts[33:6]
    EXT_TRIGGER      [27:22] ts[5:0], [12:8] id, [0] edge
    OTHERS           [27:22] ts[5:0], [16] class, [15:0] subtype
    CONTINUED        [27:0]  depends on the previous word
t = (last TIME_HIGH << 6) | ts[5:0]; decoding starts at the first TIME_HIGH.

`encode` is the canonical encoder of §2.4 rule 5: a TIME_HIGH before an event whenever ts[33:6] changes, and a
TIME_HIGH at every packet boundary of the grid t_origin + k*T_us (boundary heartbeat, §3.2), up to and including
the first boundary after the last event, so that every packet holding an event is closed by the stream itself.

`input_filter` applies the §2.4 rules 1-3 that need no packet state (pre-TIME_HIGH, backwards TIME_HIGH,
out-of-range CD word). The time-jump rule (6) depends on the open packet's t_start and is applied by
neuro.packet.packetize.
"""
from pathlib import Path

import numpy as np

from .geometry import Geometry, by_size

CD_OFF, CD_ON, TIME_HIGH, EXT_TRIGGER, OTHERS, CONTINUED = 0x0, 0x1, 0x8, 0xA, 0xE, 0xF

EVENT_DTYPE = [("t", "<u8"), ("x", "<u2"), ("y", "<u2"), ("p", "u1")]
# Every decoded non-CD, non-TIME_HIGH word: i = ordinal among all decoded non-TIME_HIGH words (so the
# interleaving with CD events is part of the comparison), t = timestamp (bucket base for words without a
# ts field), type = bits 31..28, payload = bits 27..0.
EXTRA_DTYPE = [("i", "<u8"), ("t", "<u8"), ("type", "u1"), ("payload", "<u4")]

TS_BITS = 34
TH_MASK = (1 << 28) - 1
_HAS_TS = (CD_OFF, CD_ON, EXT_TRIGGER, OTHERS)     # types whose bits 27..22 are ts[5:0]


# ------------------------------------------------------------------ single words
def word_type(w):
    return (int(w) >> 28) & 0xF


def cd_word(x, y, p, ts6):
    """CD word for pixel (x, y), polarity p, low timestamp bits ts6 = t & 63."""
    if not (0 <= x < 2048 and 0 <= y < 2048 and p in (0, 1) and 0 <= ts6 < 64):
        raise ValueError(f"cd_word: field out of range (x={x}, y={y}, p={p}, ts6={ts6})")
    return ((CD_ON if p else CD_OFF) << 28) | (ts6 << 22) | (x << 11) | y


def time_high(value):
    """EVT_TIME_HIGH word carrying ts[33:6] = value."""
    if not 0 <= value <= TH_MASK:
        raise ValueError(f"time_high: value {value} outside 28 bits")
    return (TIME_HIGH << 28) | value


def is_cd(words):
    """Boolean mask of CD words (type 0000 or 0001)."""
    return (np.asarray(words, dtype=np.uint32) >> np.uint32(29)) == 0


# ------------------------------------------------------------------ encoder
def _check_T(T_us):
    if not (isinstance(T_us, (int, np.integer)) and 64 <= T_us <= 65472 and T_us % 64 == 0):
        raise ValueError(f"T_us = {T_us!r}: must be a multiple of 64 in 64..65472 (DESIGN §3.1)")
    return int(T_us)


def as_events(events):
    """Any array/record with fields t, x, y, p -> structured array of EVENT_DTYPE (copy)."""
    events = np.asarray(events)
    out = np.empty(len(events), dtype=EVENT_DTYPE)
    for f in ("t", "x", "y", "p"):
        out[f] = events[f]
    return out


def encode(events, T_us=1024, heartbeat=True):
    """Canonical EVT 2.0 encoding of time-sorted events (§2.4 rule 5).

    heartbeat=False omits the boundary TIME_HIGH words (non-canonical; for building test inputs only).
    """
    T_us = _check_T(T_us)
    ev = np.asarray(events)
    n = len(ev)
    if n == 0:
        return np.zeros(0, dtype=np.uint32)
    t = ev["t"].astype(np.uint64)
    x = ev["x"].astype(np.int64)
    y = ev["y"].astype(np.int64)
    p = ev["p"].astype(np.int64)
    if np.any(np.diff(t.astype(np.int64)) < 0):
        i = int(np.argmax(np.diff(t.astype(np.int64)) < 0)) + 1
        raise ValueError(f"encode: events not sorted by t (index {i}: t={int(t[i])} < {int(t[i - 1])})")
    bad = (t >= (1 << TS_BITS)) | (x < 0) | (x >= 2048) | (y < 0) | (y >= 2048) | ((p != 0) & (p != 1))
    if bad.any():
        i = int(np.argmax(bad))
        raise ValueError(f"encode: event {i} out of range: {ev[i]}")

    th = (t >> np.uint64(6)).astype(np.int64)
    ths = np.unique(th)
    if heartbeat:
        step = T_us // 64
        k_last = (int(th[-1]) - int(th[0])) // step + 1        # first boundary after the last event
        bounds = int(th[0]) + step * np.arange(1, k_last + 1, dtype=np.int64)
        ths = np.union1d(ths, bounds)
    if int(ths[-1]) > TH_MASK:
        raise ValueError("encode: a boundary TIME_HIGH would exceed 34-bit time (rollover is not supported in n1)")

    out = np.empty(n + len(ths), dtype=np.uint32)
    # TIME_HIGH v_j goes before every event with th >= v_j: position j + #events with th < v_j.
    th_pos = np.arange(len(ths)) + np.searchsorted(th, ths, side="left")
    ev_pos = np.arange(n) + np.searchsorted(ths, th, side="right")
    out[th_pos] = (np.uint32(TIME_HIGH << 28) | ths.astype(np.uint32))
    out[ev_pos] = ((p.astype(np.uint32) << np.uint32(28))
                   | ((t & np.uint64(63)).astype(np.uint32) << np.uint32(22))
                   | (x.astype(np.uint32) << np.uint32(11)) | y.astype(np.uint32))
    return out


# ------------------------------------------------------------------ decoder
def decode(words):
    """(events, extras) of an EVT 2.0 word stream; words before the first TIME_HIGH are skipped.

    events: EVENT_DTYPE array of the CD words; extras: EXTRA_DTYPE array of the other non-TIME_HIGH words.
    """
    w = np.asarray(words, dtype=np.uint32)
    typ = (w >> np.uint32(28)).astype(np.uint8)
    is_th = typ == TIME_HIGH
    if not is_th.any():
        return np.zeros(0, dtype=EVENT_DTYPE), np.zeros(0, dtype=EXTRA_DTYPE)
    first = int(np.argmax(is_th))
    w, typ, is_th = w[first:], typ[first:], is_th[first:]
    last_th = np.maximum.accumulate(np.where(is_th, np.arange(len(w)), 0))
    base = (w[last_th] & np.uint32(TH_MASK)).astype(np.uint64) << np.uint64(6)
    ts6 = ((w >> np.uint32(22)) & np.uint32(63)).astype(np.uint64)
    has_ts = np.isin(typ, _HAS_TS)
    t = np.where(has_ts, base | ts6, base)

    keep = ~is_th
    w, typ, t = w[keep], typ[keep], t[keep]
    cd = typ <= CD_ON
    events = np.empty(int(cd.sum()), dtype=EVENT_DTYPE)
    events["t"] = t[cd]
    events["x"] = (w[cd] >> np.uint32(11)) & np.uint32(0x7FF)
    events["y"] = w[cd] & np.uint32(0x7FF)
    events["p"] = typ[cd]
    extras = np.empty(int((~cd).sum()), dtype=EXTRA_DTYPE)
    extras["i"] = np.nonzero(~cd)[0]
    extras["t"] = t[~cd]
    extras["type"] = typ[~cd]
    extras["payload"] = w[~cd] & np.uint32(TH_MASK)
    return events, extras


def event_equal(a, b):
    """§2.5: same (t, type, payload) for every non-TIME_HIGH word, in order; extra TIME_HIGH words are framing."""
    ea, xa = decode(a)
    eb, xb = decode(b)
    return (len(ea) == len(eb) and len(xa) == len(xb)
            and bool(np.array_equal(ea, eb)) and bool(np.array_equal(xa, xb)))


def first_difference(a, b):
    """None if event_equal(a, b), else (index, got, expected) of the first differing decoded record."""
    ea, xa = decode(a)
    eb, xb = decode(b)
    for kind, u, v in (("event", ea, eb), ("extra", xa, xb)):
        n = min(len(u), len(v))
        diff = np.nonzero(u[:n] != v[:n])[0]
        if len(diff):
            i = int(diff[0])
            return (f"{kind}[{i}]", u[i], v[i])
        if len(u) != len(v):
            return (f"{kind} count", len(u), len(v))
    return None


# ------------------------------------------------------------------ input rules 1-4
def input_filter(words, geom):
    """Apply §2.4 rules 1-4 (no packet state): returns (kept words, counts).

    1. words before the first TIME_HIGH are dropped (ERR_PRE_TH);
    2. a TIME_HIGH smaller than the current one is dropped (ERR_ORDER); an equal one passes;
    3. a CD word with x >= W or y >= H is dropped (ERR_RANGE);
    4. all other words pass unchanged.
    The words after a dropped backwards TIME_HIGH keep the current (larger) TIME_HIGH; rule 2 drops only the
    TIME_HIGH word itself.
    """
    w = np.asarray(words, dtype=np.uint32)
    typ = w >> np.uint32(28)
    is_th = typ == TIME_HIGH
    keep = np.ones(len(w), dtype=bool)
    counts = {"ERR_PRE_TH": 0, "ERR_ORDER": 0, "ERR_RANGE": 0}
    if not is_th.any():
        counts["ERR_PRE_TH"] = len(w)
        return w[:0].copy(), counts
    first = int(np.argmax(is_th))
    keep[:first] = False
    counts["ERR_PRE_TH"] = first
    thv = (w & np.uint32(TH_MASK)).astype(np.int64)
    idx = np.nonzero(is_th)[0]
    running = np.maximum.accumulate(thv[idx])
    back = np.zeros(len(idx), dtype=bool)
    back[1:] = thv[idx[1:]] < running[:-1]
    keep[idx[back]] = False
    counts["ERR_ORDER"] = int(back.sum())
    cd = (typ <= CD_ON) & keep
    x = (w >> np.uint32(11)) & np.uint32(0x7FF)
    y = w & np.uint32(0x7FF)
    out_range = cd & ((x >= geom.W) | (y >= geom.H))
    keep &= ~out_range
    counts["ERR_RANGE"] = int(out_range.sum())
    return w[keep], counts


# ------------------------------------------------------------------ Prophesee RAW files
def _parse_header(lines):
    W = H = None
    fmt = None
    for line in lines:
        body = line[1:].strip()
        if body.startswith("format"):
            spec = body[len("format"):].strip()
            parts = spec.split(";")
            fmt = parts[0].strip().upper()
            for kv in parts[1:]:
                if "=" in kv:
                    k, v = kv.split("=", 1)
                    if k.strip() == "width":
                        W = int(v)
                    elif k.strip() == "height":
                        H = int(v)
        elif body.startswith("evt"):
            v = body[3:].strip()
            fmt = fmt or ("EVT2" if v in ("2.0", "2") else f"EVT{v}")
        elif body.startswith("geometry") and W is None:
            ws, hs = body[len("geometry"):].strip().lower().split("x")
            W, H = int(ws), int(hs)
    return fmt, W, H


def read_raw(path):
    """(words, Geometry) of a Prophesee RAW file with an EVT 2.0 payload.

    The header is the leading lines that start with '%' and ends at '% end' (or at the first other byte).
    Geometry comes from '% format EVT2;height=H;width=W', or from '% geometry WxH' in older files.
    """
    data = Path(path).read_bytes()
    pos, lines = 0, []
    while pos < len(data) and data[pos:pos + 1] == b"%":
        nl = data.find(b"\n", pos)
        if nl < 0:
            raise ValueError(f"{path}: header line without newline")
        line = data[pos:nl].decode("ascii", errors="replace").rstrip("\r")
        pos = nl + 1
        lines.append(line)
        if line.strip() == "% end":
            break
    fmt, W, H = _parse_header(lines)
    if fmt is not None and fmt != "EVT2":
        raise ValueError(f"{path}: format {fmt}, only EVT2 is supported")
    if W is None or H is None:
        raise ValueError(f"{path}: no geometry in the RAW header")
    body = data[pos:]
    if len(body) % 4:
        raise ValueError(f"{path}: payload of {len(body)} bytes is not a whole number of 32-bit words")
    return np.frombuffer(body, dtype="<u4").astype(np.uint32), by_size(W, H)


def write_raw(path, words, geom: Geometry):
    """Write words as a Prophesee RAW file: '% format EVT2;height=H;width=W', '% end', little-endian words."""
    header = f"% format EVT2;height={geom.H};width={geom.W}\n% end\n".encode("ascii")
    Path(path).write_bytes(header + np.asarray(words, dtype="<u4").tobytes())
