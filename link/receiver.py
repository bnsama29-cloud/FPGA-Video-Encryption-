"""Receiver node = the key holder's laptop.

    python -m link.receiver [--config ...]

For every frame that arrives: find the key for its epoch (ratchet), verify the
Ascon tag over header + size + scan, check the counter (replay / gap), decrypt
bit-exactly and show it. Every heartbeat period it sends authenticated counters
back to the sender, plus immediate (rate-limited) alerts when something is wrong.

Session rules (see link/keys.py):
  * the first frame whose tag verifies fixes the sender's session base;
  * a frame with a NEW base that verifies means the sender restarted -> accept it,
    but a base that was seen before can never come back (cross-session replay);
  * a frame from an older epoch cannot be verified any more (its key was erased)
    and is counted as 'stale_epoch'.
"""
import os
import time

from model.container import parse_jpeg
from model.jpeg import receive_frame

from . import config, keys, wire
from .feedback import FeedbackWriter


class Receiver:
    def __init__(self, cfg):
        self.cfg = cfg
        L, r = cfg["link"], cfg["receiver"]
        self.r = r
        self.master = bytes.fromhex(cfg["keys"]["master"])
        self.fbw = FeedbackWriter(keys.feedback_key(self.master), int.from_bytes(os.urandom(8), "big") | 1)
        self.vsock = wire.udp_socket(L["video_out"], L["host"], timeout=0.05)
        self.fsock = wire.udp_socket()
        self.faddr = (L["host"], L["fb_in"])
        self.bus = wire.Bus(cfg, "receiver")
        self.rasm = wire.Reassembler(timeout=1.0)
        self.base = None
        self.seen_bases = set()
        self.ratchet = keys.Ratchet(self.master, 0)
        self.last_ctr = 0
        self.rejected_since_good = 0     # frames that arrived but failed (not 'lost')
        self.counts = self._zero()
        self.total = self._zero()
        self.last_alert = {}
        self.latency = []

    @staticmethod
    def _zero():
        return dict(ok=0, lost=0, tag_fail=0, replay=0, malformed=0, stale_epoch=0)

    def _send_fb(self, msg):
        wire.send_message(self.fsock, self.faddr, wire.FEEDBACK, self.fbw.pack(msg), self.fbw.ctr)

    def _alert(self, kind, **info):
        now = time.monotonic()
        if now - self.last_alert.get(kind, 0) >= self.r["alert_min_gap_s"]:
            self.last_alert[kind] = now
            self._send_fb(dict(type="alert", kind=kind, **info))

    def _count(self, kind, n=1):
        self.counts[kind] += n
        self.total[kind] += n
        if kind in ("tag_fail", "malformed", "stale_epoch"):
            self.rejected_since_good += n

    def handle_frame(self, jpeg, t_ms):
        try:
            sec = parse_jpeg(jpeg).secure()
        except ValueError:
            sec = None
        if sec is None:
            self._count("malformed")
            self._alert("malformed")
            self.bus.event("frame", verdict="malformed")
            return
        _, mode_id, sid, ctr, _ = sec
        base, epoch = keys.split_session(sid)
        if base == 0:
            self._count("malformed")
            self.bus.event("frame", verdict="malformed", ctr=ctr)
            return
        if base == self.base:
            if epoch < self.ratchet.epoch:
                self._count("stale_epoch")
                self._alert("stale-epoch", epoch=epoch)
                self.bus.event("frame", verdict="stale-epoch", ctr=ctr, epoch=epoch)
                return
            if epoch > self.ratchet.epoch + self.r["max_epoch_jump"]:
                self._count("tag_fail")
                self._alert("tag-fail", why="epoch jump")
                self.bus.event("frame", verdict="tag-mismatch", ctr=ctr, epoch=epoch)
                return
            key = self.ratchet.peek(epoch)
        elif base in self.seen_bases:
            self._count("replay")
            self._alert("replay", why="old session")
            self.bus.event("frame", verdict="replay", ctr=ctr, why="old session")
            return
        else:
            key = keys.video_key(self.master, epoch) if epoch <= self.r["max_epoch_jump"] else None
            if key is None:
                self._count("tag_fail")
                self.bus.event("frame", verdict="tag-mismatch", ctr=ctr)
                return
        r = receive_frame(jpeg, key)                     # tag check + decrypt
        if not r.ok:
            kind = "tag_fail" if r.reason == "tag-mismatch" else "malformed"
            self._count(kind)
            self._alert(kind.replace("_", "-"))
            self.bus.event("frame", verdict=r.reason, ctr=ctr, epoch=epoch)
            return
        # authentic frame: adopt a new sender session / epoch if needed
        if base != self.base:
            if self.base is not None:
                self.seen_bases.add(self.base)
            self.base = base
            self.ratchet = keys.Ratchet(self.master, epoch)
            self.last_ctr = 0
            self.bus.event("session", session=f"{sid:016x}", epoch=epoch)
        elif epoch > self.ratchet.epoch:
            self.ratchet.forward(epoch)                  # old key erased
            self.bus.event("epoch", epoch=epoch)
        if ctr <= self.last_ctr:
            self._count("replay")
            self._alert("replay", ctr=ctr)
            self.bus.event("frame", verdict="replay", ctr=ctr, epoch=epoch)
            return
        if self.last_ctr and ctr > self.last_ctr + 1:
            lost = ctr - self.last_ctr - 1 - self.rejected_since_good
            if lost > 0:
                self._count("lost", lost)
        self.last_ctr = ctr
        self.rejected_since_good = 0
        self._count("ok")
        lat = max(0, wire.now_ms() - t_ms)
        self.latency.append(lat)
        if ctr % self.r["preview_every"] == 0:
            self.bus.preview("receiver", r.plain_jpeg)
        self.bus.event("frame", verdict="ok", ctr=ctr, epoch=epoch, mode=r.mode, latency_ms=lat,
                       bytes=len(jpeg))

    def heartbeat(self):
        lat = sorted(self.latency)
        msg = dict(type="hb", counts=self.counts, last_good=self.last_ctr, epoch=self.ratchet.epoch,
                   latency_ms=lat[len(lat) // 2] if lat else None)
        self._send_fb(msg)
        self.bus.event("heartbeat", counts=self.counts, total=self.total, last_good=self.last_ctr,
                       epoch=self.ratchet.epoch, latency_ms=msg["latency_ms"],
                       reassembly_dropped=self.rasm.dropped)
        self.counts = self._zero()
        self.latency = []

    def run(self):
        print(f"receiver: listening on {self.cfg['link']['video_out']}, feedback -> {self.faddr}")
        self.bus.event("start")
        next_hb = time.monotonic() + self.r["heartbeat_s"]
        try:
            while True:
                try:
                    data, _ = self.vsock.recvfrom(65535)
                    m = self.rasm.add(data)
                    if m is not None and m[0] == wire.VIDEO:
                        self.handle_frame(m[4], m[3])
                except OSError:
                    pass
                if time.monotonic() >= next_hb:
                    self.heartbeat()
                    next_hb += self.r["heartbeat_s"]
        except KeyboardInterrupt:
            pass


def main():
    cfg, _ = config.from_args(__doc__)
    Receiver(cfg).run()


if __name__ == "__main__":
    main()
