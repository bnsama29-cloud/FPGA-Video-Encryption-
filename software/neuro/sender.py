"""Sender model (Golden model of hardware/rtl/neuro/nv_top.v): EVT 2.0 words in, sealed packets out.

DESIGN §3 (packets, keys), §4 (levels), §5 (padding), §6.7 (commit rules and counters).

    enc = Encryptor(subkeys, sid, Config(level=3, ts_bits=6, T_us=1024, geom=SENSORS["dvsgesture"]))
    packets = enc.push(words) + enc.flush()          # list of bytes, one per packet

Commit (§6.7): enc.commit(at_ctr, cfg=..., subkeys=..., sid=..., ctr0=...) makes a new shadow set active for
the packet that would have counter at_ctr. Accepted only if at_ctr >= open counter + 2 (LATE otherwise); a new
SID with the base of the last emitted SID must have a higher epoch, or the same epoch and ctr0 > last ctr
(REWIND otherwise). With a new SID packet at_ctr-1 carries FINAL and the new epoch's first packet carries
FIRST with link = at_ctr-1 (same base) or 2^64-1.
"""
from dataclasses import dataclass, replace

import numpy as np

from model import ascon

from . import feistel, levels
from .evt2 import is_cd
from .geometry import MIN_PERM_DIM, Geometry
from .keys import SubKeys, nonce
from .packet import (F_FINAL, F_FIRST, F_PAD, LINK_NONE, Packet, PacketHeader, Packetizer, Trailer)
from .pad import PadPolicy, pad_packet

MAXW_DEFAULT, MAXH_DEFAULT = 1280, 720
CFG_NONE, CFG_LATE, CFG_GEOM, CFG_LEVEL, CFG_TUS, CFG_REWIND, CFG_NOKEYS = range(7)
CFG_NAMES = {CFG_NONE: "none", CFG_LATE: "LATE", CFG_GEOM: "GEOM", CFG_LEVEL: "LEVEL/TS/PAD", CFG_TUS: "T_US",
             CFG_REWIND: "REWIND", CFG_NOKEYS: "NO_KEYS"}
COUNTER_KEYS = ("PKTS", "WORDS_IN", "WORDS_OUT", "ERR_RANGE", "ERR_ORDER", "ERR_PRE_TH", "ERR_JUMP",
                "ERR_PADOVF", "ERR_CFG")


class ConfigError(ValueError):
    def __init__(self, code, msg=""):
        super().__init__(f"{CFG_NAMES.get(code, code)}: {msg}")
        self.code = code


@dataclass(frozen=True)
class Config:
    level: int
    ts_bits: int = 0
    T_us: int = 1024
    geom: Geometry = None
    pad: PadPolicy = None
    max_gap_us: int = 1_000_000
    jump_mode: int = 0


def check_config(cfg, maxw=MAXW_DEFAULT, maxh=MAXH_DEFAULT, pad_built=True):
    """§6.7 configuration checks; returns CFG_NONE or the refusal code."""
    g = cfg.geom
    if g is None or g.W > maxw or g.H > maxh:
        return CFG_GEOM
    if cfg.level in levels.PERM_LEVELS and (g.W < MIN_PERM_DIM or g.H < MIN_PERM_DIM):
        return CFG_GEOM
    if cfg.level not in range(5):
        return CFG_LEVEL
    if cfg.level == levels.V3:
        if not 1 <= cfg.ts_bits <= 6:
            return CFG_LEVEL
    elif cfg.ts_bits != 0:
        return CFG_LEVEL
    if cfg.pad is not None:
        if not pad_built or not ((cfg.level == 3 and cfg.ts_bits == 6) or cfg.level == 4):
            return CFG_LEVEL
    T = cfg.T_us
    if not (isinstance(T, int) and 64 <= T <= 65472 and T % 64 == 0):
        return CFG_TUS
    return CFG_NONE


def commit_ok(open_ctr, at_ctr, last_sid, last_ctr, new_sid, ctr0, active_sid):
    """§6.7 counter/SID rules: (ok, code). last_sid None = nothing emitted since power-on."""
    if at_ctr < open_ctr + 2:
        return False, CFG_LATE
    if new_sid != active_sid and last_sid is not None and (new_sid >> 16) == (last_sid >> 16):
        e_new, e_last = new_sid & 0xFFFF, last_sid & 0xFFFF
        if not (e_new > e_last or (e_new == e_last and ctr0 > last_ctr)):
            return False, CFG_REWIND
    return True, CFG_NONE


@dataclass
class _Set:
    cfg: Config
    subkeys: SubKeys
    sid: int
    ctr0: int
    link_first: int          # link carried by the first packet of this set (FIRST packets only)
    new_epoch: bool          # this set started a new SID (its first packet carries FIRST)


class Encryptor:
    def __init__(self, subkeys, sid, cfg, ctr0=0, maxw=MAXW_DEFAULT, maxh=MAXH_DEFAULT, pad_built=True):
        self.maxw, self.maxh, self.pad_built = maxw, maxh, pad_built
        code = check_config(cfg, maxw, maxh, pad_built)
        if code:
            raise ConfigError(code, f"initial configuration {cfg}")
        if sid == 0 or not 0 <= ctr0 < (1 << 63):
            raise ConfigError(CFG_REWIND, "sid 0 is reserved; ctr0 must fit 63 bits")
        self.counters = dict.fromkeys(COUNTER_KEYS, 0)
        self.last_sid = None
        self.last_ctr = None
        self.active = _Set(cfg, subkeys, sid, ctr0, LINK_NONE, True)
        self.pz = Packetizer(cfg.geom.W, cfg.geom.H, cfg.T_us, ctr0, cfg.max_gap_us, cfg.jump_mode)
        self.pz.hook = self._account
        self.pending = None            # (at_ctr, _Set)
        self._tables_cache = {}

    # ------------------------------------------------------------ input
    def push(self, words):
        w = np.asarray(words, dtype=np.uint32)
        self.counters["WORDS_IN"] += len(w)
        out = []
        for raw in self._feed(w):
            out.append(self._seal(raw))
        return out

    def _feed(self, w):
        return self.pz.feed(w)

    def _account(self, raw):
        """Attach the set that owns raw and apply a pending commit at its boundary."""
        st = self.active
        raw.set = st
        if self.pending is not None:
            at, new = self.pending
            if raw.ctr == at - 1:
                if new.sid != st.sid:
                    raw.flags |= F_FINAL
                self._apply(new)
        return raw

    def _apply(self, new):
        old = self.active
        if new.sid != old.sid:
            new.link_first = (self.pz.open_ctr - 1 if (new.sid >> 16) == (old.sid >> 16) else LINK_NONE)
            new.new_epoch = True
            self.pz.restart(new.ctr0, new.cfg.T_us)
        else:                                   # same SID: the counter continues, the epoch's ctr0 stays
            new.ctr0, new.new_epoch, new.link_first = old.ctr0, False, old.link_first
            self.pz.restart(self.pz.open_ctr, new.cfg.T_us)
        g = new.cfg.geom
        self.pz.W, self.pz.H = g.W, g.H
        self.pz.max_gap_us, self.pz.jump_mode = new.cfg.max_gap_us, new.cfg.jump_mode
        self.active, self.pending = new, None

    def flush(self):
        """CTRL.FLUSH: close the open packet and emit the FINAL packet."""
        return [self._seal(r) for r in self.pz.flush()]

    @property
    def halted(self):
        return self.pz.halted

    # ------------------------------------------------------------ commit
    def commit(self, at_ctr=None, cfg=None, subkeys=None, sid=None, ctr0=0):
        st = self.active
        new = _Set(cfg or st.cfg, subkeys or st.subkeys, st.sid if sid is None else sid, ctr0, LINK_NONE, False)
        code = check_config(new.cfg, self.maxw, self.maxh, self.pad_built)
        if code == CFG_NONE and new.sid == 0:
            code = CFG_REWIND
        if code == CFG_NONE and self.pz.halted:
            if new.sid == st.sid:
                code = CFG_REWIND
            else:
                ok, code = commit_ok(-2, 0, self.last_sid, self.last_ctr, new.sid, ctr0, st.sid)
        elif code == CFG_NONE:
            open_ctr = self.pz.open_ctr if self.pz.started else st.ctr0
            ok, code = commit_ok(open_ctr, at_ctr, self.last_sid, self.last_ctr, new.sid, ctr0, st.sid)
            if code == CFG_NONE and self.pending is not None:
                code = CFG_LATE
        if code != CFG_NONE:
            self.counters["ERR_CFG"] += 1
            raise ConfigError(code, f"commit at {at_ctr} refused")
        if self.pz.halted:
            new.link_first = LINK_NONE
            new.new_epoch = True
            g = new.cfg.geom
            self.pz.W, self.pz.H = g.W, g.H
            self.pz.max_gap_us, self.pz.jump_mode = new.cfg.max_gap_us, new.cfg.jump_mode
            self.active = new
            return [self._seal(r) for r in self.pz.resume(ctr0, new.cfg.T_us)]
        self.pending = (at_ctr, new)
        return []

    # ------------------------------------------------------------ sealing
    def _seal(self, raw):
        st = raw.set
        cfg, sk, sid = st.cfg, st.subkeys, st.sid
        for k in ("ERR_PRE_TH", "ERR_ORDER", "ERR_RANGE", "ERR_JUMP"):
            self.counters[k] = self.pz.err[k]
        flags = raw.flags
        if st.new_epoch and raw.ctr == st.ctr0:
            flags |= F_FIRST
        link = st.link_first if flags & F_FIRST else st.ctr0
        words = raw.words
        dmask = None
        bitmap = b""
        if cfg.pad is not None:
            flags |= F_PAD
            words, bitmap, ndrop, dmask = pad_packet(words, cfg.pad, sk.dum, sid, raw.ctr, cfg.geom, raw.t_start,
                                                     cfg.T_us)
            self.counters["ERR_PADOVF"] += ndrop
        hdr = PacketHeader(level=cfg.level, flags=flags, ts_bits=cfg.ts_bits, session_id=sid,
                           packet_ctr=raw.ctr, t_start=raw.t_start, W=cfg.geom.W, H=cfg.geom.H, T_us=cfg.T_us,
                           pad_policy=(cfg.pad.kind if cfg.pad else 0), link=link)
        n_cd = int(is_cd(words).sum())
        tr = Trailer(len(words), n_cd, bitmap)
        if cfg.level == levels.V4:
            ct = ascon.encrypt(sk.aead, nonce(sid, raw.ctr, 0), hdr.pack(),
                               np.asarray(words, dtype="<u4").tobytes() + tr.pack())
            pkt = Packet(hdr, words, tr, ct[-16:], ct[:-16])
        else:
            tables = None
            if cfg.level in levels.PERM_LEVELS and levels.real_cd_mask(words, dmask).any():
                tables = feistel.make_tables(sk.perm, sid, raw.ctr, cfg.geom.W, cfg.geom.H)
            pw = levels.protect(words, cfg.level, cfg.ts_bits, tables, sk.pol, sid, raw.ctr, dmask)
            body = hdr.pack() + np.asarray(pw, dtype="<u4").tobytes() + tr.pack()
            pkt = Packet(hdr, pw, tr, ascon.mac(sk.tag, nonce(sid, raw.ctr, 1), body))
        b = pkt.to_bytes()
        self.counters["PKTS"] += 1
        self.counters["WORDS_OUT"] += len(b) // 4
        self.last_sid, self.last_ctr = sid, raw.ctr
        return b


def encrypt_stream(words, subkeys, sid, cfg, ctr0=0, flush=True):
    """Convenience: all packets of a whole stream (with the FINAL packet if flush)."""
    enc = Encryptor(subkeys, sid, cfg, ctr0)
    out = enc.push(words)
    if flush:
        out += enc.flush()
    return out, enc
