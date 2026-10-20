"""The secure JPEG encoder on the PYNQ-Z2's processing system (PS, the dual Cortex-A9), in C.

The Zynq has two halves: the programmable logic (PL, our RTL) and the processing system (PS, two ARM
cores running Linux and Python). The PL does the per-pixel work; the PS already does the per-frame work
(headers, APP11, the E5 segment order, keys, the UDP sender, the defence policy). This module puts the
per-pixel work on the PS too, as optimised C (native/sjpeg_sw.c), bit-exact with the golden model and
therefore with the PL. It serves three purposes:

  * the ARM baseline (A3): the same function on the same chip, so the PL speed-up is a like-for-like
    number (future_work/arm/arm_baseline.py);
  * a PS-only fallback for the board sender when no bitstream is loaded (SoftwareBackend below plugs into
    future_work/board/pynq_driver.py :: SecureJpegIP like the real board and the mock do);
  * PS + PL together: contract-v3 segments are independent, so the A9's two cores can code segments the
    PL lanes do not (sjpeg_encode takes the number of threads).

    from future_work.arm.sw_encoder import SoftwareBackend
    from future_work.board.pynq_driver import SecureJpegIP
    ip = SecureJpegIP(SoftwareBackend(contract=3, threads=2, e5=True))
    ip.setup_session(key, session_id, quality=75)
    scan, tag = ip.encode(rgb, mode=5, frame_ctr=1)          # same bytes as the FPGA
    jpeg = ip.build_jpeg(w, h, 5, 1, scan, tag)

The C file is compiled once with the system compiler (cc -O3 -pthread; on the board add
CFLAGS="-mcpu=cortex-a9 -mfpu=neon"), cached in ~/.cache/sjpeg. tests/test_arm_software.py checks every
byte against model/hw.py.
"""
import ctypes
import hashlib
import os
import shlex
import subprocess
from pathlib import Path

import numpy as np

from model import hw
from model.dct_quant import STAGE1_SHIFT, STAGE2_SHIFT
from model.tables import AC_CODES, DC_CODES, ZIGZAG

_SRC = Path(__file__).resolve().parent / "native" / "sjpeg_sw.c"
_lib = None


def _compile_flags():
    return ["-O3", "-shared", "-fPIC", "-pthread"] + shlex.split(os.environ.get("CFLAGS", ""))


def load_library():
    """Compile (once) and load native/sjpeg_sw.c. Raises RuntimeError without a C compiler."""
    global _lib
    if _lib is not None:
        return _lib
    flags = _compile_flags()
    tag = hashlib.sha1(_SRC.read_bytes() + " ".join(flags).encode()).hexdigest()[:10]
    cache = Path(os.environ.get("SJPEG_CACHE", Path.home() / ".cache" / "sjpeg"))
    cache.mkdir(parents=True, exist_ok=True)
    so = cache / f"sjpeg_sw_{tag}.so"
    if not so.exists():
        cc = os.environ.get("CC", "cc")
        r = subprocess.run([cc, *flags, "-o", str(so), str(_SRC)], capture_output=True, text=True, timeout=120)
        if r.returncode:
            raise RuntimeError(f"cannot compile {_SRC.name}: {r.stderr.strip()}")
    lib = ctypes.CDLL(str(so))
    u8p, u32p, i32 = ctypes.c_char_p, ctypes.POINTER(ctypes.c_uint32), ctypes.c_int32
    lib.sjpeg_set_tables.argtypes = [ctypes.POINTER(ctypes.c_int32), ctypes.POINTER(ctypes.c_int32),
                                     ctypes.POINTER(ctypes.c_uint16), ctypes.POINTER(ctypes.c_uint8),
                                     ctypes.POINTER(ctypes.c_uint16), ctypes.POINTER(ctypes.c_uint8), i32, i32]
    lib.sjpeg_set_tables.restype = None
    lib.sjpeg_encode.argtypes = [ctypes.c_void_p, i32, i32, u32p, i32, i32, u8p, ctypes.c_uint64,
                                 ctypes.c_uint64, u8p, ctypes.c_void_p, i32, ctypes.c_void_p, i32]
    lib.sjpeg_encode.restype = i32
    lib.sjpeg_ascon_encrypt.argtypes = [u8p, u8p, ctypes.c_void_p, i32, ctypes.c_void_p]
    lib.sjpeg_ascon_encrypt.restype = None
    # tables from the model itself
    dct = (ctypes.c_int32 * 64)(*[int(v) for row in hw.DCT_C for v in row])
    zz = (ctypes.c_int32 * 64)(*ZIGZAG)
    dcc, dcl = (ctypes.c_uint16 * 24)(), (ctypes.c_uint8 * 24)()
    acc, acl = (ctypes.c_uint16 * 512)(), (ctypes.c_uint8 * 512)()
    for t in range(2):
        for s, (c, ln) in DC_CODES[t].items():
            dcc[12 * t + s], dcl[12 * t + s] = c, ln
        for rs, (c, ln) in AC_CODES[t].items():
            acc[256 * t + rs], acl[256 * t + rs] = c, ln
    lib.sjpeg_set_tables(dct, zz, dcc, dcl, acc, acl, STAGE1_SHIFT, STAGE2_SHIFT)
    _lib = lib
    return lib


def available():
    try:
        load_library()
        return True
    except Exception:
        return False


def encode_scan(rgb, recips, mode, key, session_id, frame_ctr, contract=3, threads=1):
    """(scan, tag) exactly as the PL returns them (E5: segments in raster order)."""
    lib = load_library()
    rgb = np.ascontiguousarray(rgb[..., :3], dtype=np.uint8)
    h, w = rgb.shape[:2]
    if w % 16 or h % 16:
        raise ValueError("width and height must be multiples of 16")
    if not 0 <= mode <= (5 if contract == 3 else 4):
        raise ValueError(f"contract v{contract} has no mode {mode}")
    r = (ctypes.c_uint32 * 128)(*recips)
    prefix = hw.tag_prefix(mode, frame_ctr, session_id, w, h, version=contract)
    cap = (w // 16) * (h // 16) * 2600 + 2 * (w // 16) * (h // 16)
    out = np.empty(cap, np.uint8)
    tag = ctypes.create_string_buffer(16)
    n = lib.sjpeg_encode(rgb.ctypes.data, w, h, r, mode, contract, bytes(key), session_id, frame_ctr, prefix,
                         out.ctypes.data, cap, tag, threads)
    if n < 0:
        raise RuntimeError(f"sjpeg_encode failed ({n})")
    return out[:n].tobytes(), tag.raw


def ascon_encrypt(key, nonce, data):
    """Full-buffer Ascon-AEAD128 in C (ciphertext || tag), for the 'encrypt the whole JPEG' baseline."""
    lib = load_library()
    out = ctypes.create_string_buffer(len(data) + 16)
    lib.sjpeg_ascon_encrypt(bytes(key), bytes(nonce), data, len(data), out)
    return out.raw


class SoftwareBackend:
    """Answers the register map of the IP (pynq_driver.py) with the C encoder on the PS, so SecureJpegIP,
    first_contact.py and board_sender.py run unchanged with no bitstream: the PS-only encoder."""

    def __init__(self, contract=3, lanes=2, e5=True, threads=2):
        from future_work.board.pynq_driver import MockBackend
        self._regs = MockBackend(contract, lanes, e5)            # reuse its register file and VERSION
        self.contract, self.threads = contract, threads
        self.e5 = self._regs.e5
        load_library()

    def write(self, addr, value):
        self._regs.write(addr, value)

    def read(self, addr):
        return self._regs.read(addr)

    def load(self, rgb):
        self._rgb = rgb
        return rgb.shape[0] * rgb.shape[1]

    def run(self, n, timeout_s=2.0):
        from future_work.board.pynq_driver import (CTRL, FRAME_CTR, FRAME_CTR_HI, KEY0, SESSION_ID,
                                                   SESSION_ID_HI)
        m, r = self._regs, self._regs.regs
        mode = (r.get(CTRL, 0) >> 1) & 7
        if mode > 4 and not self.e5:
            raise ValueError(f"mode {mode}: this configuration has no E5")
        key = b"".join(r.get(KEY0 + 4 * i, 0).to_bytes(4, "little") for i in range(4))
        sid = r.get(SESSION_ID, 0) | (r.get(SESSION_ID_HI, 0) << 32)
        ctr = r.get(FRAME_CTR, 0) | (r.get(FRAME_CTR_HI, 0) << 32)
        m.out, m.tag = encode_scan(self._rgb, m.qt, mode, key, sid, ctr, self.contract, self.threads)
        m.done = True
        return m.out

    def transfer(self, words):
        raise NotImplementedError("SoftwareBackend takes frames through load()/run()")
