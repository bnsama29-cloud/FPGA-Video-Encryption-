"""Channel node = the network between camera and receiver, plus the attacker.

    python -m link.channel [--config ...]

Forwards video (sender -> receiver) and feedback (receiver -> sender) over UDP
with benign impairments (loss, delay, jitter, reordering), and runs attacks
on command (dashboard buttons or experiments/run_scenario.py):

  video path   eavesdrop (always: the 'wire' and 'attacker' dashboard tiles)
               bitflip     flip one bit in the scan of each frame        -> tag-fail
               downgrade   rewrite the APP11 mode byte (E2 -> E0)         -> tag-fail
               splice      put an older frame's scan under a new header  -> tag-fail
               inject      forge extra frames with a guessed tag          -> tag-fail
               replay      re-send captured old frames                    -> replay
               delay       hold frames and release them late             -> replay / gap
               drop        jam: drop a fraction of frames                 -> gap / stall
               flood       spray junk datagrams at the receiver           -> malformed
  feedback     fb_drop     suppress the feedback channel                  -> dead-man rule
               fb_forge    inject forged "all OK" heartbeats              -> fb_forged
               fb_replay   replay captured heartbeats                     -> fb_replay
  key exchange (channel.kex_relay = true: the channel on its own laptop, between board and receiver)
               channel.kex_tamper_s = N: flip a byte of every kex message for the first N s
                                                                          -> HMAC fails, no key until it stops

Two laptops: run this node on the attacker laptop with
  --set link.host=<RECEIVER IP> --set link.sender_host=<BOARD IP> --set link.bind_host=0.0.0.0
  --set channel.kex_relay=true   (+ the ports printed by experiments/scenario.py --attacker)

Control commands (JSON over UDP to link.control):
  {"cmd":"attack","type":"bitflip","duration":10,"rate":1.0}   rate = fraction of frames
  {"cmd":"stop"}                                              stop every attack
  {"cmd":"impair","loss":0.02,"delay_ms":20,"jitter_ms":5,"reorder":0.0}
The 'attacker' tile shows the best picture an eavesdropper WITHOUT the key gets
from the intercepted bytes (replacement attack, model/selective.py).
"""
import heapq
import json
import os
import random
import threading
import time
from collections import deque

from model.container import parse_jpeg
from model.jpeg import replacement_attack_jpeg

from . import config, wire

ATTACKS = ["bitflip", "downgrade", "splice", "inject", "replay", "delay", "drop", "flood",
           "fb_drop", "fb_forge", "fb_replay"]


class Channel:
    def __init__(self, cfg):
        self.cfg = cfg
        L, c = cfg["link"], cfg["channel"]
        self.c = dict(c)
        self.size = L["fragment"]
        self.vin = wire.udp_socket(L["video_in"], config.bind_host(cfg), timeout=0.05)
        self.fin = wire.udp_socket(L["fb_in"], config.bind_host(cfg), timeout=0.05)
        self.ctl = wire.udp_socket(L["control"], config.bind_host(cfg), timeout=0.2)
        self.out = wire.udp_socket()
        self.to_rx = (L["host"], L["video_out"])
        self.to_tx = (config.sender_host(cfg), L["fb_out"])
        self.bus = wire.Bus(cfg, "channel")
        self.rng = random.Random()
        self.lock = threading.Lock()
        self.active = {}                       # attack type -> dict(until, rate, ...)
        self.history = deque(maxlen=200)       # captured frames (for replay / splice)
        self.fb_history = deque(maxlen=100)
        self.held = []                         # frames held by the delay attack
        self.queue = []                        # (due time, seq, addr, datagram)
        self.seq = 0
        self.frames = 0
        self.stats = dict(frames=0, attacked=0, dropped=0, injected=0, fb_dropped=0, fb_forged=0)
        self.msg_id = 1 << 30                  # ids for frames the attacker creates
        self.t_start = time.monotonic()
        self.kex_in = self.kex_up = None
        if c.get("kex_relay"):
            # sender side listens on link.kex; one upstream socket to the receiver, so the receiver sees
            # one consistent peer (link/kex.py keeps the peer address of the first SVK0)
            self.kex_in = wire.udp_socket(L["kex"], config.bind_host(cfg), timeout=0.2)
            self.kex_up = wire.udp_socket(timeout=0.2)
            self.kex_to = (L["host"], L.get("kex_rx") or L["kex"])
            self.kex_peer = None

    # ------------------------------------------------------------- helpers
    def _schedule(self, addr, datagram, extra_s=0.0):
        d = self.c["delay_ms"] / 1000 + max(0.0, self.rng.gauss(0, self.c["jitter_ms"] / 1000)) + extra_s
        with self.lock:
            self.seq += 1
            heapq.heappush(self.queue, (time.monotonic() + d, self.seq, addr, datagram))

    def _send_frame(self, jpeg, msg_id, t_ms, extra_s=0.0):
        if self.c["reorder"] and self.rng.random() < self.c["reorder"]:
            extra_s += 0.15                   # arrives after the next frame
        for d in wire.fragment(wire.VIDEO, jpeg, msg_id, 0, self.size, t_ms):
            if self.rng.random() < self.c["loss"]:
                continue                      # benign loss, per fragment
            self._schedule(self.to_rx, d, extra_s)
        self.bus.preview("wire", jpeg)

    def _on(self, kind):
        a = self.active.get(kind)
        if a is None:
            return None
        if time.monotonic() > a["until"]:
            if self.active.pop(kind, None) is not None:
                self.bus.event("attack_end", type=kind)
            return None
        return a if self.rng.random() < a.get("rate", 1.0) else None

    @staticmethod
    def _scan_span(jpeg):
        p = parse_jpeg(jpeg)
        return len(jpeg) - 2 - len(p.scan), len(jpeg) - 2

    # ---------------------------------------------------------- video path
    def on_video(self, jpeg, msg_id, t_ms):
        self.stats["frames"] += 1
        self.frames += 1
        original = jpeg
        if self.frames % max(1, self.c["attacker_view_every"]) == 0:
            self._attacker_view(original)
        if self._on("drop"):
            self.stats["dropped"] += 1
            self.history.append((original, msg_id, t_ms))
            return
        attacked = None
        try:
            if self._on("bitflip"):
                a, b = self._scan_span(jpeg)
                buf = bytearray(jpeg)
                i = self.rng.randrange(a, b)
                buf[i] ^= 1 << self.rng.randrange(8)
                jpeg, attacked = bytes(buf), "bitflip"
            elif self._on("downgrade"):
                buf = bytearray(jpeg)
                k = buf.find(b"SJV1")
                if k >= 0:
                    buf[k + 5] = 0                     # claim "E0: nothing encrypted"
                    jpeg, attacked = bytes(buf), "downgrade"
            elif self._on("splice") and len(self.history) > 5:
                old = self.history[-5][0]
                a, b = self._scan_span(jpeg)
                oa, ob = self._scan_span(old)
                jpeg, attacked = jpeg[:a] + old[oa:ob] + b"\xff\xd9", "splice"
        except ValueError:
            pass
        if attacked:
            self.stats["attacked"] += 1
        delay = self._on("delay")
        if delay:
            self.held.append((jpeg, msg_id, t_ms))
        else:
            self._send_frame(jpeg, msg_id, t_ms)
        self.history.append((original, msg_id, t_ms))
        if self._on("inject"):
            self._inject(original)
        if self._on("replay") and len(self.history) > 20:
            old, mid, tm = self.history[self.rng.randrange(0, len(self.history) - 10)]
            self._send_frame(old, mid, tm)
            self.stats["injected"] += 1

    def _inject(self, template):
        """Forge a 'next' frame: bump the counter in APP11, keep a guessed (stale) tag."""
        buf = bytearray(template)
        k = buf.find(b"SJV1")
        if k < 0:
            return
        ctr = int.from_bytes(buf[k + 14:k + 22], "big") + 1
        buf[k + 14:k + 22] = ctr.to_bytes(8, "big")
        buf[k + 22:k + 38] = os.urandom(16)           # the attacker cannot compute the tag
        self.msg_id += 1
        self._send_frame(bytes(buf), self.msg_id, wire.now_ms())
        self.stats["injected"] += 1

    def _release_held(self):
        if self.held and "delay" not in self.active:
            for jpeg, mid, tm in self.held:
                self._send_frame(jpeg, mid, tm)
            self.held = []

    def _attacker_view(self, jpeg):
        """What an eavesdropper without the key can reconstruct (replacement attack,
        model/jpeg.py :: replacement_attack_jpeg: contracts v2 and v3, every level)."""
        try:
            self.bus.preview("attacker", replacement_attack_jpeg(jpeg))
        except (ValueError, IndexError, KeyError):
            pass

    # ------------------------------------------------------- feedback path
    def on_feedback(self, datagram):
        if self._on("fb_drop"):
            self.stats["fb_dropped"] += 1
            return
        self.fb_history.append(datagram)
        self._schedule(self.to_tx, datagram)
        if self._on("fb_replay") and len(self.fb_history) > 10:
            self._schedule(self.to_tx, self.fb_history[self.rng.randrange(0, len(self.fb_history) - 5)])

    def _forge_feedback(self):
        """An 'all OK' heartbeat with a made-up tag (the attacker has no K_fb)."""
        body = json.dumps(dict(type="hb", counts=dict(ok=10), last_good=0)).encode()
        hdr = b"FB" + bytes([1, 0]) + os.urandom(8) + (1).to_bytes(8, "big")
        payload = hdr + os.urandom(len(body)) + os.urandom(16)
        self.msg_id += 1
        for d in wire.fragment(wire.FEEDBACK, payload, self.msg_id, 0, self.size):
            self._schedule(self.to_tx, d)
        self.stats["fb_forged"] += 1

    # ------------------------------------------------------- key exchange
    def _kex_tamper(self, d, direction):
        """During the first channel.kex_tamper_s seconds: flip one byte after the 4-byte magic."""
        if time.monotonic() - self.t_start >= float(self.c.get("kex_tamper_s", 0.0)) or len(d) <= 4:
            return d
        buf = bytearray(d)
        buf[self.rng.randrange(4, len(buf))] ^= 1 << self.rng.randrange(8)
        self.stats["kex_tampered"] = self.stats.get("kex_tampered", 0) + 1
        self.bus.event("kex_tamper", direction=direction, size=len(d))
        return bytes(buf)

    def _kex_down_loop(self):                  # sender -> receiver
        while True:
            try:
                d, addr = self.kex_in.recvfrom(4096)
            except OSError:
                continue
            self.kex_peer = addr
            self.stats["kex_relayed"] = self.stats.get("kex_relayed", 0) + 1
            try:
                self.kex_up.sendto(self._kex_tamper(d, "to_receiver"), self.kex_to)
            except OSError:
                pass

    def _kex_up_loop(self):                    # receiver -> sender
        while True:
            try:
                d, _ = self.kex_up.recvfrom(4096)
            except OSError:
                continue
            if self.kex_peer is not None:
                try:
                    self.kex_in.sendto(self._kex_tamper(d, "to_sender"), self.kex_peer)
                except OSError:
                    pass

    # ------------------------------------------------------------- control
    def control(self, cmd):
        c = cmd.get("cmd")
        if c == "attack" and cmd.get("type") in ATTACKS:
            kind = cmd["type"]
            self.active[kind] = dict(until=time.monotonic() + float(cmd.get("duration", 10)),
                                     rate=float(cmd.get("rate", 1.0)))
            self.bus.event("attack_start", type=kind, duration=float(cmd.get("duration", 10)),
                           rate=float(cmd.get("rate", 1.0)))
        elif c == "stop":
            for kind in list(self.active):
                if self.active.pop(kind, None) is not None:
                    self.bus.event("attack_end", type=kind)
        elif c == "impair":
            for k in ("loss", "delay_ms", "jitter_ms", "reorder"):
                if k in cmd:
                    self.c[k] = float(cmd[k])
            self.bus.event("impair", **{k: self.c[k] for k in ("loss", "delay_ms", "jitter_ms", "reorder")})

    # ---------------------------------------------------------------- loops
    def _video_loop(self):
        rasm = wire.Reassembler()
        while True:
            try:
                data, _ = self.vin.recvfrom(65535)
            except OSError:
                continue
            m = rasm.add(data)
            if m is not None and m[0] == wire.VIDEO:
                self.on_video(m[4], m[2], m[3])

    def _fb_loop(self):
        while True:
            try:
                data, _ = self.fin.recvfrom(65535)
            except OSError:
                continue
            self.on_feedback(data)

    def _ctl_loop(self):
        while True:
            try:
                data, _ = self.ctl.recvfrom(65535)
                self.control(json.loads(data))
            except (OSError, ValueError):
                continue

    def run(self):
        loops = [self._video_loop, self._fb_loop, self._ctl_loop]
        if self.kex_in is not None:
            loops += [self._kex_down_loop, self._kex_up_loop]
            print(f"channel: relaying the key exchange {self.cfg['link']['kex']} -> {self.kex_to[0]}:{self.kex_to[1]}"
                  + (f", tampering for the first {self.c['kex_tamper_s']} s" if self.c.get("kex_tamper_s") else ""))
        for fn in loops:
            threading.Thread(target=fn, daemon=True).start()
        print(f"channel: video {self.cfg['link']['video_in']} -> {self.to_rx[1]}, "
              f"feedback {self.cfg['link']['fb_in']} -> {self.to_tx[1]}, control {self.cfg['link']['control']}")
        self.bus.event("start", **{k: self.c[k] for k in ("loss", "delay_ms", "jitter_ms", "reorder")})
        next_stat = time.monotonic() + 1.0
        next_flood = 0.0
        try:
            while True:
                now = time.monotonic()
                while True:
                    with self.lock:
                        if not self.queue or self.queue[0][0] > now:
                            break
                        _, _, addr, d = heapq.heappop(self.queue)
                    try:
                        self.out.sendto(d, addr)
                    except OSError:
                        pass
                if now >= next_flood and self._on("flood"):
                    next_flood = now + 0.02          # ~1000 junk datagrams per second
                    for _ in range(20):
                        self.out.sendto(os.urandom(self.rng.randrange(30, 1200)), self.to_rx)
                if self._on("fb_forge") and self.rng.random() < 0.05:
                    self._forge_feedback()
                for kind in list(self.active):        # expire attacks that are not frame-driven
                    a = self.active.get(kind)
                    if a and now > a["until"] and self.active.pop(kind, None) is not None:
                        self.bus.event("attack_end", type=kind)
                self._release_held()
                if now >= next_stat:
                    self.bus.event("stats", active=sorted(self.active), **self.stats,
                                   loss=self.c["loss"], delay_ms=self.c["delay_ms"])
                    next_stat = now + 1.0
                time.sleep(0.002)
        except KeyboardInterrupt:
            pass


def main():
    cfg, _ = config.from_args(__doc__)
    Channel(cfg).run()


if __name__ == "__main__":
    main()
