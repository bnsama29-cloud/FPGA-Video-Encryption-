"""Receiver model: verify, then decrypt (DESIGN §3.5).

Steps 1-4 read only the header and the length and change no state; the tag (step 5) is the only MAC per
datagram; state changes only in step 7, after the tag has verified.

Statuses: ok, forged, replay, malformed, stale, policy. Notices: gap (counters that left the window unmarked, or
were missing at an epoch switch or at close), truncated (an epoch or the stream closed without an authenticated
FINAL), stall (no authenticated packet for more than stall_k * T_us of wall time).

NeuroWindow.mark returns missing counters as inclusive (lo, hi) ranges (not single ints), so a genuine outage of
many packets costs one tuple, not one list entry per packet.
"""
from dataclasses import dataclass, field
import hmac
import json
from pathlib import Path
from typing import Literal

import numpy as np

from model import ascon

from . import feistel, levels
from .keys import E_MAX, EventRatchet, nonce, split_session, subkeys_of
from .packet import (F_FINAL, F_FIRST, F_PAD, HEADER_LEN, LINK_NONE, ROUNDS, TAG_LEN, TRAILER_FIXED, MAGIC,
                     PacketHeader, Trailer, bitmap_len)
from .pad import PadPolicy, StripError, strip

STATUSES = ("ok", "forged", "replay", "malformed", "stale", "policy")


@dataclass(frozen=True)
class Profile:
    allowed: frozenset                  # tuples (level, ts_bits, pad, pad_policy); None = any value
    geom: object
    T_us: int
    R_max_words_per_us: float = 4.0
    pad: PadPolicy = None
    window: int = 64
    e_max: int = E_MAX
    stall_k: int = 100
    psk: bool = True                    # experiment profile: persist the highest boot_id per cam_id

    def permits(self, level, ts_bits, pad, pad_policy):
        for a in self.allowed:
            if all(v is None or v == got for v, got in zip(a, (level, ts_bits, int(pad), pad_policy))):
                return True
        return False

    def max_len(self, pad):
        T = self.T_us
        w_max = int(self.R_max_words_per_us * T * (2 if pad else 1)) + (T // 64) * (
            1 + (self.pad.pad_min if (pad and self.pad) else 0))
        max_cd = self.pad.max_cd if self.pad else 1 << 30
        bm = 4 * ((min(w_max, max_cd) + 31) // 32) if pad else 0
        return HEADER_LEN + 4 * w_max + bm + TRAILER_FIXED + TAG_LEN


@dataclass
class Notice:
    kind: Literal["gap", "truncated", "stall"]
    sid: int
    ctrs: tuple = None


@dataclass
class Result:
    status: str
    ctr: int = None
    words: np.ndarray = None
    notices: list = field(default_factory=list)
    header: PacketHeader = None


class NeuroWindow:
    """RFC 3711-style sliding window over packet counters (size 64), with explicit missing set."""

    def __init__(self, size=64):
        self.size = size
        self.top = None
        self.missing = set()

    def start(self, ctr0):
        """Counters below ctr0 count as seen (they belong to no packet of this epoch)."""
        self.top = ctr0 - 1
        self.missing = set()

    def would_accept(self, ctr):
        if self.top is None or ctr > self.top:
            return True
        return ctr in self.missing

    def mark(self, ctr):
        """Mark ctr; return the missing counters that left the window, as (lo, hi) ranges."""
        gaps = []
        if self.top is None:
            self.top = ctr - 1
        if ctr > self.top:
            lo_new = ctr - self.size + 1
            if self.top + 1 < lo_new:                       # whole stretch is older than the new window
                gaps.append((self.top + 1, lo_new - 1))
            self.missing.update(range(max(self.top + 1, lo_new), ctr))
            self.top = ctr
        else:
            self.missing.discard(ctr)
        lo = self.top - self.size + 1
        old = sorted(c for c in self.missing if c < lo)
        for c in old:
            self.missing.discard(c)
        gaps.extend(_ranges(old))
        return sorted(gaps)

    def pending_ranges(self):
        return _ranges(sorted(self.missing))


def _ranges(cs):
    out = []
    for c in cs:
        if out and out[-1][1] == c - 1:
            out[-1] = (out[-1][0], c)
        else:
            out.append((c, c))
    return out


@dataclass
class _Session:
    ratchet: EventRatchet
    window: NeuroWindow
    ctr0: int = None
    t_origin: int = None
    final_seen: bool = False
    last_auth: float = None
    stalled: bool = False


class Decryptor:
    def __init__(self, keyring, profile, state_path=None):
        self.keyring = dict(keyring)        # (cam_id, boot_id) -> master key
        self.profile = profile
        self.state_path = Path(state_path) if state_path else None
        self.highest_boot = {}
        if self.state_path and self.state_path.exists():
            self.highest_boot = {int(k): v for k, v in json.loads(self.state_path.read_text()).items()}
        self.sessions = {}                  # (cam_id, boot_id) -> _Session
        self.kdf_calls = 0

    # ------------------------------------------------------------ helpers
    def _persist(self):
        if self.state_path:
            self.state_path.write_text(json.dumps({str(k): v for k, v in self.highest_boot.items()}))

    def _session(self, cam, boot):
        s = self.sessions.get((cam, boot))
        if s is None:
            s = _Session(EventRatchet(self.keyring[(cam, boot)], cam, boot, 0), NeuroWindow(self.profile.window))
        return s

    # ------------------------------------------------------------ accept
    def accept(self, pkt, now=0.0):
        b = bytes(pkt)
        L = len(b)
        prof = self.profile
        # 1. framing
        if L < HEADER_LEN + TRAILER_FIXED + TAG_LEN or L % 4:
            return Result("malformed")
        h = PacketHeader.unpack(b)
        if (h.magic != MAGIC or h.version != 1 or h.rounds != ROUNDS or h.flags & ~0x7 or h.t_start >> 34
                or h.level > 4 or h.packet_ctr >> 63):
            return Result("malformed", h.packet_ctr)
        ctr = h.packet_ctr
        cam, boot, epoch = split_session(h.session_id)
        # 2. session and epoch
        if (cam, boot) not in self.keyring:
            return Result("stale", ctr)
        if prof.psk and boot < self.highest_boot.get(cam, -1):
            return Result("stale", ctr)
        known = (cam, boot) in self.sessions
        sess = self._session(cam, boot)
        cur = sess.ratchet.epoch
        if epoch < cur:
            return Result("stale", ctr)
        if epoch > cur + prof.e_max:
            return Result("policy", ctr)
        k_ev = sess.ratchet.peek(epoch)
        if k_ev is None:
            return Result("policy", ctr)
        self.kdf_calls += epoch - cur
        # 3. profile and plausibility (header only)
        if not prof.permits(h.level, h.ts_bits, h.pad, h.pad_policy):
            return Result("policy", ctr)
        if (h.W, h.H, h.T_us) != (prof.geom.W, prof.geom.H, prof.T_us):
            return Result("policy", ctr)
        if h.pad and (prof.pad is None or h.pad_policy != prof.pad.kind):
            return Result("policy", ctr)
        if L > prof.max_len(h.pad):
            return Result("malformed", ctr)
        same_epoch = known and epoch == cur and sess.ctr0 is not None
        if same_epoch:
            if not h.first and h.link != sess.ctr0:
                return Result("policy", ctr)
            if h.t_start != sess.t_origin + (ctr - sess.ctr0) * h.T_us:
                return Result("policy", ctr)
        # 4. replay (read only)
        if epoch == cur and known and not sess.window.would_accept(ctr):
            return Result("replay", ctr)
        # 5. tag
        sk = subkeys_of(k_ev)
        self.kdf_calls += 5
        hdr_b = b[:HEADER_LEN]
        if h.level == 4:
            pt = ascon.decrypt(sk.aead, nonce(h.session_id, ctr, 0), hdr_b, b[HEADER_LEN:])
            if pt is None:
                return Result("forged", ctr)
            body = pt
        else:
            tag = ascon.mac(sk.tag, nonce(h.session_id, ctr, 1), b[:-TAG_LEN])
            if not hmac.compare_digest(tag, b[-TAG_LEN:]):
                return Result("forged", ctr)
            body = b[HEADER_LEN:-TAG_LEN]
        # 6. structure
        try:
            tr = Trailer.unpack(body, h.pad)
        except ValueError:
            return Result("malformed", ctr)
        if tr.rsvd != 0 or 4 * tr.n_words + (bitmap_len(tr.n_cd) if h.pad else 0) + TRAILER_FIXED != len(body):
            return Result("malformed", ctr)
        words = np.frombuffer(body[:4 * tr.n_words], dtype="<u4").astype(np.uint32)
        # 7. commit
        notices = []
        if prof.psk and boot > self.highest_boot.get(cam, -1):
            for (c2, b2), s2 in list(self.sessions.items()):
                if c2 == cam and b2 < boot:
                    notices += self._close_session(c2, b2, s2)
            self.highest_boot[cam] = boot
            self._persist()
        if not known:
            self.sessions[(cam, boot)] = sess
        if epoch > cur:
            notices += self._end_epoch(h.session_id - (epoch - cur), sess, h.link if h.first else None)
            sess.ratchet.forward(epoch)
            sess.window = NeuroWindow(prof.window)
            sess.ctr0 = sess.t_origin = None
            sess.final_seen = False
        if sess.ctr0 is None:
            sess.ctr0 = ctr if h.first else h.link
            sess.t_origin = h.t_start - (ctr - sess.ctr0) * h.T_us
            sess.window.start(sess.ctr0)
        for g in sess.window.mark(ctr):
            notices.append(Notice("gap", h.session_id, g))
        if h.final:
            sess.final_seen = True
        sess.last_auth, sess.stalled = now, False
        dmask = None
        if h.pad:
            try:
                words, _ = strip(words, tr.bitmap, sk.dum, h.session_id, ctr, prof.geom, prof.pad, h.t_start,
                                 h.T_us)
            except (StripError, ValueError):
                return Result("policy", ctr, notices=notices, header=h)
        if h.level != 4:
            tables = None
            if h.level in levels.PERM_LEVELS and levels.real_cd_mask(words).any():
                tables = feistel.make_tables(sk.perm, h.session_id, ctr, h.W, h.H)
            words = levels.unprotect(words, h.level, h.ts_bits, tables, sk.pol, h.session_id, ctr, dmask)
        return Result("ok", ctr, words, notices, h)

    # ------------------------------------------------------------ notices
    def _end_epoch(self, old_sid, sess, link):
        out = []
        if sess.ctr0 is None:
            return out
        for g in sess.window.pending_ranges():
            out.append(Notice("gap", old_sid, g))
        top = sess.window.top
        if link is not None and link != LINK_NONE and link > top:
            out.append(Notice("gap", old_sid, (top + 1, link)))
        if not sess.final_seen:
            out.append(Notice("truncated", old_sid))
        return out

    def _close_session(self, cam, boot, sess):
        sid = sess.ratchet.sid
        out = self._end_epoch(sid, sess, None)
        del self.sessions[(cam, boot)]
        return out

    def tick(self, now):
        out = []
        limit = self.profile.stall_k * self.profile.T_us * 1e-6
        for sess in self.sessions.values():
            if sess.last_auth is not None and not sess.stalled and now - sess.last_auth > limit:
                sess.stalled = True
                out.append(Notice("stall", sess.ratchet.sid))
        return out

    def close(self):
        out = []
        for (cam, boot), sess in list(self.sessions.items()):
            out += self._close_session(cam, boot, sess)
        return out
