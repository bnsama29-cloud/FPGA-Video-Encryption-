"""Authenticated feedback channel (receiver -> sender), modelled on SRTCP (RFC 3711).

Datagram payload (inside a wire.FEEDBACK message):
    header (clear, 20 bytes): 'FB' | version | flags | fb_session (u64) | fb_ctr (u64)
    body:  Ascon-AEAD128(K_fb, nonce(fb_session, fb_ctr, 0), AD = header, PT = JSON) = ct || tag

Every message is encrypted and authenticated, so an attacker can neither read the
receiver's statistics nor forge an "all is well" heartbeat or a fake alert.
The sender rejects anything that fails the tag (counted as a forgery attempt)
or that the replay window has already seen.

Message types (JSON field "type"):
    hb      heartbeat every receiver.heartbeat_s: counters since the last heartbeat
    alert   immediate, rate-limited: kind = tag-fail | replay | gap | malformed | stale-epoch
    rekey   receiver asks the sender to move to the next key epoch
"""
import json
import struct

from model import ascon

HDR = struct.Struct("!2sBBQQ")
MAGIC, VERSION = b"FB", 1


class ReplayWindow:
    """Sliding-window replay check (RFC 3711 section 3.3.2), 64 entries.

    Accepts each counter once; late messages inside the window are fine
    (UDP may reorder), anything older than the window is rejected."""

    def __init__(self, size=64):
        self.size, self.top, self.bitmap = size, -1, 0

    def check(self, ctr):
        """True if ctr is new; marks it as seen."""
        if ctr > self.top:
            shift = ctr - self.top
            self.bitmap = ((self.bitmap << shift) | 1) & ((1 << self.size) - 1)
            self.top = ctr
            return True
        off = self.top - ctr
        if off >= self.size or (self.bitmap >> off) & 1:
            return False
        self.bitmap |= 1 << off
        return True


class FeedbackWriter:
    def __init__(self, key, fb_session):
        self.key, self.session, self.ctr = key, fb_session, 0

    def pack(self, msg):
        self.ctr += 1
        hdr = HDR.pack(MAGIC, VERSION, 0, self.session, self.ctr)
        body = json.dumps(msg, separators=(",", ":")).encode()
        return hdr + ascon.encrypt(self.key, ascon.make_nonce(self.session, self.ctr, 0), hdr, body)


class FeedbackReader:
    """Returns (status, msg): status 'ok' | 'forged' | 'replay' | 'malformed'."""

    def __init__(self, key, max_sessions=8):
        self.key, self.windows, self.max = key, {}, max_sessions

    def unpack(self, data):
        if len(data) < HDR.size + 16:
            return "malformed", None
        magic, ver, _, session, ctr = HDR.unpack_from(data)
        if magic != MAGIC or ver != VERSION or session == 0 or ctr >= (1 << 63):
            return "malformed", None
        hdr = data[:HDR.size]
        pt = ascon.decrypt(self.key, ascon.make_nonce(session, ctr, 0), hdr, data[HDR.size:])
        if pt is None:
            return "forged", None
        win = self.windows.get(session)
        if win is None:
            if len(self.windows) >= self.max:
                self.windows.pop(next(iter(self.windows)))
            win = self.windows[session] = ReplayWindow()
        if not win.check(ctr):
            return "replay", None
        try:
            return "ok", json.loads(pt)
        except ValueError:
            return "malformed", None
