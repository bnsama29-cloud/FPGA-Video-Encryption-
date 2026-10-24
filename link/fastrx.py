"""Fast receiver: model/jpeg.py :: receive_frame / verify_frame with the heavy work in C.

The golden model stays the referee. This module returns the same ReceivedFrame (same reason, mode,
session, counter, plain JPEG and plain scan bytes) for every frame, and simply calls the model for
anything it does not handle itself: a contract-v2 E5 frame, a frame without the secure segment, any
malformed frame (so reject reasons are exactly the model's), or when no C compiler is available.
tests/test_fastrx.py checks it against the model on valid, tampered, truncated and replayed frames.

Why: the pure-Python receiver needs ~160 ms per 320x240 contract-v3 E5 frame (one Ascon keystream per
MCU), more than the 100 ms between frames at 10 fps, so frames from the board queued for seconds and the
defence loop reacted late. native/sjpeg_rx.c does the tag, the E5 un-permutation, Huffman decoding,
decryption and the canonical re-coding.
"""
import ctypes
import dataclasses
import hashlib
import hmac
import os
import shutil
import subprocess
from pathlib import Path

from model import jpeg as mj
from model.container import build_jpeg, parse_jpeg
from model.selective import MODE_NAME, MODES
from model.tables import (AC_CHROMA_BITS, AC_CHROMA_VALS, AC_LUMA_BITS, AC_LUMA_VALS, DC_CHROMA_BITS,
                          DC_CHROMA_VALS, DC_LUMA_BITS, DC_LUMA_VALS, ZIGZAG)

_SRC = Path(__file__).resolve().parent / "native" / "sjpeg_rx.c"
_lib = None
_skeys = {}


def _cc(name=None, env=None):
    """C compiler: $CC, else gcc on Windows (MinGW has no `cc`), else cc."""
    name = os.name if name is None else name
    env = os.environ if env is None else env
    return env.get("CC") or ("gcc" if name == "nt" else "cc")


def _dll_dir(cc):
    """On Windows let ctypes find MinGW's runtime DLLs next to gcc.exe (bug #41). Linux needs nothing."""
    path = shutil.which(cc)
    if os.name == "nt" and path:
        # winget puts an alias (a link) in ...\WinGet\Links; the DLLs are next to the real gcc.exe
        for d in {os.path.dirname(path), os.path.dirname(os.path.realpath(path))}:
            os.add_dll_directory(d)


def _machine(cc):
    """The compiler's target (x86_64-w64-mingw32, mingw32, aarch64-linux-gnu, ...), or "" if unknown."""
    try:
        return subprocess.run([cc, "-dumpmachine"], capture_output=True, text=True, timeout=30).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def native_lib(src, stem, flags, timeout=120):
    """Compile `src` once into ~/.cache/sjpeg and load it with ctypes. Used by every native helper
    (this module, system/board/fast_e5.py, system/arm/sw_encoder.py).

    The cache name covers the source, the flags and the compiler's target, so a library built by another
    compiler is never reused; a library that does not load is deleted so the next run rebuilds it (bug #43:
    a 32-bit MinGW gcc builds a DLL that 64-bit Python cannot load). Raises RuntimeError with the reason."""
    cc = _cc()
    machine = _machine(cc)
    tag = hashlib.sha1(src.read_bytes() + " ".join(flags).encode() + machine.encode()).hexdigest()[:10]
    cache = Path(os.environ.get("SJPEG_CACHE", Path.home() / ".cache" / "sjpeg"))
    cache.mkdir(parents=True, exist_ok=True)
    so = cache / f"{stem}_{tag}.so"
    if not so.exists():
        try:
            r = subprocess.run([cc, *flags, "-o", str(so), str(src)], capture_output=True, text=True, timeout=timeout)
        except (OSError, subprocess.SubprocessError) as e:
            raise RuntimeError(f"no C compiler '{cc}' ({e})") from e
        if r.returncode:
            raise RuntimeError(f"cannot compile {src.name} with {cc}: {r.stderr.strip()[-600:]}")
    _dll_dir(cc)
    try:
        return ctypes.CDLL(str(so))
    except OSError as e:
        so.unlink(missing_ok=True)
        hint = (" A 32-bit gcc cannot build for 64-bit Python: install a 64-bit gcc (x86_64-w64-mingw32)."
                if os.name == "nt" and not machine.startswith("x86_64") else "")
        raise RuntimeError(f"cannot load {src.name} built by {cc} (target {machine or 'unknown'}): {e}.{hint}") from e


_error = None


def load_error():
    """Why the C path is not used (None when it is, or before the first use)."""
    _load()
    return _error


def _load():
    global _lib, _error
    if _lib is not None:
        return _lib or None
    try:
        lib = native_lib(_SRC, "sjpeg_rx", ["-O2", "-shared", "-fPIC"])
        u64, i32, p = ctypes.c_uint64, ctypes.c_int32, ctypes.c_char_p
        lib.rx_mac2.argtypes = [p, u64, u64, p, i32, p, i32, ctypes.c_void_p]
        lib.rx_mac2.restype = None
        lib.rx_unpermute.argtypes = [p, i32, p, u64, u64, i32, ctypes.c_void_p]
        lib.rx_unpermute.restype = i32
        lib.rx_decode.argtypes = [p, i32, i32, i32, i32, i32, p, u64, u64, ctypes.c_void_p, i32]
        lib.rx_decode.restype = i32
        lib.rx_set_tables.argtypes = [p, p, ctypes.POINTER(ctypes.c_int32)]
        lib.rx_set_tables.restype = None
        bits = bytearray(64)
        vals = bytearray(1024)
        for t, (b, v) in enumerate([(DC_LUMA_BITS, DC_LUMA_VALS), (DC_CHROMA_BITS, DC_CHROMA_VALS),
                                    (AC_LUMA_BITS, AC_LUMA_VALS), (AC_CHROMA_BITS, AC_CHROMA_VALS)]):
            bits[16 * t:16 * t + 16] = bytes(b)
            vals[256 * t:256 * t + len(v)] = bytes(v)
        lib.rx_set_tables(bytes(bits), bytes(vals), (ctypes.c_int32 * 64)(*ZIGZAG))
        _lib = lib
    except Exception as e:                          # noqa: BLE001 -- fall back to the model, say why
        _lib, _error = False, str(e)
    return _lib or None


def available():
    return _load() is not None


def _shuffle_key(key):
    k = _skeys.get(key)
    if k is None:
        k = _skeys[key] = mj._shuffle_key(key)
    return k


def _auth(lib, p, sec, key):
    """(mode, auth scan, tag ok) or None when the model must decide (unsupported or malformed)."""
    meta, mode_id, sid, ctr, tag = sec
    mode = MODE_NAME.get(mode_id)
    if mode is None:
        return None
    version = meta[4]
    if version not in (2, 3) or (version == 2 and MODES[mode].shuffle):
        return None
    n_mcu = ((p.width + 15) // 16) * ((p.height + 15) // 16)
    scan = p.scan
    if version == 3 and MODES[mode].shuffle:
        buf = ctypes.create_string_buffer(len(scan))
        n = lib.rx_unpermute(scan, len(scan), _shuffle_key(key), sid, ctr, n_mcu, buf)
        if n < 0:
            return None
        scan = buf.raw[:n]
    prefix = meta + p.width.to_bytes(2, "big") + p.height.to_bytes(2, "big")
    out = ctypes.create_string_buffer(16)
    lib.rx_mac2(key, sid, (ctr << 1) | 1, prefix, len(prefix), scan, len(scan), out)
    return mode, scan, hmac.compare_digest(out.raw, tag), n_mcu


def receive_frame(jpeg, key, guard=None):
    """Same result as model/jpeg.py :: receive_frame."""
    lib = _load()
    if lib is None:
        return mj.receive_frame(jpeg, key, guard)
    try:
        p = parse_jpeg(jpeg)
        sec = p.secure()
    except ValueError:
        return mj.receive_frame(jpeg, key, guard)
    if sec is None:
        return mj.receive_frame(jpeg, key, guard)
    key = bytes(key)
    a = _auth(lib, p, sec, key)
    if a is None:
        return mj.receive_frame(jpeg, key, guard)
    mode, scan, ok, n_mcu = a
    meta, _, sid, ctr, _ = sec
    if not ok:
        return mj.ReceivedFrame(False, "tag-mismatch", mode, sid, ctr)
    status = guard.check(sid, ctr) if guard is not None else "ok"
    if status == "replay":
        return mj.ReceivedFrame(False, "replay", mode, sid, ctr)
    version = meta[4]
    per = mj.segment_mcus(p.width, mode) if version == 3 else n_mcu
    cap = 2 * len(scan) + 64 * 6 * n_mcu + 1024
    out = ctypes.create_string_buffer(cap)
    n = lib.rx_decode(scan, len(scan), n_mcu, per, sorted(MODES).index(mode), version, key, sid, ctr, out, cap)
    if n < 0:                                     # authentic but undecodable: the model gives the reason
        r = mj.receive_frame(jpeg, key, None)
        return dataclasses.replace(r, reason=status) if r.ok else r
    plain_scan = out.raw[:n]
    qy, qc = p.qtables()
    return mj.ReceivedFrame(True, status, mode, sid, ctr, build_jpeg(p.width, p.height, qy, qc, plain_scan),
                            plain_scan)


def verify_frame(jpeg, key):
    """Same result as model/jpeg.py :: verify_frame (tag only)."""
    lib = _load()
    if lib is None:
        return mj.verify_frame(jpeg, key)
    try:
        p = parse_jpeg(jpeg)
        sec = p.secure()
    except ValueError:
        return False
    if sec is None:
        return False
    a = _auth(lib, p, sec, bytes(key))
    if a is None:
        return mj.verify_frame(jpeg, key)
    return a[2]
