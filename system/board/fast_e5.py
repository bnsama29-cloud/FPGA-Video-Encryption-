"""The ARM's E5 step (docs/INTERFACES.md §8.6) fast enough for the board's Cortex-A9.

model/hw.py :: arm_shuffle is the reference, but its keyed order runs Ascon in pure Python (about 6 ms per
640x480 frame on a laptop, 10-15x more on the A9). This module computes the same order in C
(native/e5_order.c, compiled once with the system C compiler into ~/.cache/sjpeg) and splits the scan
with bytes.find. Without a compiler it falls back to the model, so it is never wrong, only slower.
tests/test_system.py checks both against model/hw.py.
"""
import ctypes
from pathlib import Path

from link.fastrx import native_lib
from model import ascon, hw

_SRC = Path(__file__).resolve().parent / "native" / "e5_order.c"
_lib = None
_shuffle_keys = {}


def _load():
    global _lib
    if _lib is not None:
        return _lib or None
    try:
        lib = native_lib(_SRC, "e5_order", ["-O2", "-shared", "-fPIC"], timeout=60)
        lib.e5_order.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int32, ctypes.POINTER(ctypes.c_int32)]
        lib.e5_order.restype = None
        i32p = ctypes.POINTER(ctypes.c_int32)
        lib.e5_shuffle.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int32,
                                   ctypes.c_char_p, i32p, i32p, i32p, ctypes.c_int32]
        lib.e5_shuffle.restype = ctypes.c_int32
        _lib = lib
    except Exception:
        _lib = False                                   # no compiler: use the model
    return _lib or None


def native_available():
    return _load() is not None


def e5_order(key, session_id, frame_ctr, n):
    lib = _load()
    if lib is None:
        return hw.e5_order(key, session_id, frame_ctr, n)
    sk = _shuffle_key(key)                             # one Ascon MAC per key, not per frame
    out = (ctypes.c_int32 * n)()
    lib.e5_order(sk, ascon.make_nonce(session_id, frame_ctr, 0), n, out)
    return list(out)


def split_segments(scan):
    """Same as model/hw.py :: split_segments, with bytes.find (no per-byte Python loop)."""
    out, start, i = [], 0, 0
    while True:
        j = scan.find(b"\xff", i)
        if j < 0 or j + 1 >= len(scan):
            break
        if 0xD0 <= scan[j + 1] <= 0xD7:
            out.append(scan[start:j])
            start = i = j + 2
        else:
            i = j + 1
    out.append(scan[start:])
    return out


def _shuffle_key(key):
    sk = _shuffle_keys.get(key)
    if sk is None:
        sk = _shuffle_keys[key] = hw.shuffle_key(key)
    return sk


def arm_shuffle(jpeg, key, session_id, frame_ctr):
    """Byte-identical to model/hw.py :: arm_shuffle. With the C library, split + order + reassembly run
    in one native call (e5_shuffle); otherwise the Python path below."""
    head, scan = hw.split_scan(jpeg)
    lib = _load()
    if lib is not None:
        maxseg = len(scan) // 2 + 1                       # a segment is at least the 2-byte marker apart
        out = ctypes.create_string_buffer(len(scan))
        arr = ctypes.c_int32 * maxseg
        n = lib.e5_shuffle(_shuffle_key(key), ascon.make_nonce(session_id, frame_ctr, 0), scan, len(scan),
                           out, arr(), arr(), arr(), maxseg)
        if n > 0:
            return head + out.raw + b"\xFF\xD9"
    segs = split_segments(scan)
    order = e5_order(key, session_id, frame_ctr, len(segs))
    rst = hw.RST_MARKERS
    return head + b"".join((rst[(p - 1) % 8] if p else b"") + segs[i] for p, i in enumerate(order)) + b"\xFF\xD9"
