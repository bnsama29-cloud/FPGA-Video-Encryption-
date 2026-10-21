"""Sender node = digital twin of the PYNQ-Z2 camera.

    python -m link.sender [--config configs/default.toml] [--set sender.mode=E3 ...]

Every frame: read the camera -> encode with in-encoder selective encryption + tag
(golden model, or the real Verilog with sender.encoder=rtl) -> UDP to the channel.
In parallel it receives the receiver's authenticated feedback; every defence
window the policy (link/defence.py) chooses the mode and may rekey. Everything
it does is reported to the dashboard bus.

The board version (board/, later) does the same with the FPGA doing the encode.
"""
import json
import threading
import time
from collections import deque

import cv2

from . import config, keys, wire
from .backends import make_encoder
from .defence import MODES, Window, make_policy, threat_score
from .feedback import FeedbackReader
from .sources import open_source


class Sender:
    def __init__(self, cfg):
        self.cfg = cfg
        s, L = cfg["sender"], cfg["link"]
        self.master = bytes.fromhex(cfg["keys"]["master"])
        self.base = cfg["keys"]["session_base"] or keys.random_base()
        self.ratchet = keys.Ratchet(self.master, 0)
        self.fb = FeedbackReader(keys.feedback_key(self.master))
        self.mode = s["mode"]
        self.encoder = make_encoder(s["encoder"], s["quality"])
        if self.encoder.name == "rtl" and cfg["defence"]["max_mode"] == "E5":
            cfg["defence"]["max_mode"] = "E4"          # the RTL has no restart markers yet
        self.policy = make_policy(s["policy"], cfg, self.mode, config.policy_seed(cfg))
        self.source = open_source(s["source"], s["width"], s["height"], s["loop"], live_clock=True)
        self.fps = float(s["fps"])
        self.ctr = 1
        self.bus = wire.Bus(cfg, "sender")
        self.vsock = wire.udp_socket()
        self.vaddr = (L["host"], L["video_in"])
        self.padder = wire.SizePadder(L.get("pad", "none"))     # frame-size padding (link/wire.py)
        self.fsock = wire.udp_socket(L["fb_out"], config.bind_host(cfg), timeout=0.2)
        self.csock = wire.udp_socket(L["sender_control"], config.bind_host(cfg), timeout=0.2)
        self.lock = threading.Lock()
        self.win = Window()
        self.last_hb = time.monotonic()
        self.last_rx_ctr = 0
        self.loss_hist = deque(maxlen=3)        # (ok, lost) of the last 3 windows
        self.running = True
        self.paused = False
        self.manual_mode = None
        self.enc_bits = self.payload_bits = self.frames_sent = 0
        self.t_encode = 0.0

    @property
    def session_id(self):
        return keys.session_id(self.base, self.ratchet.epoch)

    # ------------------------------------------------------------ feedback
    def feedback_loop(self):
        rasm = wire.Reassembler()
        while self.running:
            try:
                data, _ = self.fsock.recvfrom(65535)
            except OSError:
                continue
            m = rasm.add(data)
            if m is None or m[0] != wire.FEEDBACK:
                continue
            status, msg = self.fb.unpack(m[4])
            with self.lock:
                if status == "forged" or status == "malformed":
                    self.win.fb_forged += 1
                elif status == "replay":
                    self.win.fb_replay += 1
                else:
                    self.win.fb_ok += 1
                    self.last_hb = time.monotonic()
                    c = msg.get("counts", {})
                    if msg.get("type") == "hb":
                        for k in ("ok", "lost", "tag_fail", "replay", "malformed", "stale_epoch", "junk"):
                            setattr(self.win, k, getattr(self.win, k) + int(c.get(k, 0)))
                        self.last_rx_ctr = msg.get("last_good", self.last_rx_ctr)
                    elif msg.get("type") == "alert":
                        self.win.alerts.append(msg.get("kind"))
            if status != "ok":
                self.bus.event("feedback_rejected", status=status)

    # ------------------------------------------------------------- control
    def control_loop(self):
        while self.running:
            try:
                data, _ = self.csock.recvfrom(65535)
                cmd = json.loads(data)
            except (OSError, ValueError):
                continue
            c = cmd.get("cmd")
            with self.lock:
                if c == "mode":
                    self.manual_mode = cmd.get("mode") if cmd.get("mode") in MODES else None
                elif c == "policy":
                    self.policy = make_policy(cmd["policy"], self.cfg, self.cfg["sender"]["mode"],
                                              config.policy_seed(self.cfg))
                elif c == "rekey":
                    self._rekey("operator request")
                elif c == "fps":
                    self.fps = max(0.2, float(cmd["fps"]))
                elif c == "pause":
                    self.paused = bool(cmd.get("on", True))
            self.bus.event("control", cmd=cmd)

    def _rekey(self, reason):
        self.ratchet.forward()            # one-way: the old key is overwritten
        self.bus.event("rekey", epoch=self.ratchet.epoch, session=f"{self.session_id:016x}", reason=reason)

    # ------------------------------------------------------------- defence
    def defence_step(self):
        d = self.cfg["defence"]
        with self.lock:
            w, self.win = self.win, Window()
            w.hb_age = time.monotonic() - self.last_hb
            w.sent = self.frames_sent
            self.loss_hist.append((w.ok, w.lost))
            w.recent_ok = sum(o for o, _ in self.loss_hist)
            w.recent_lost = sum(lo for _, lo in self.loss_hist)
            f = w.features(d["deadman_s"])
            dec = self.policy.decide(w, f, time.monotonic())
            if dec.rekey:
                self._rekey(dec.reason)
            old = self.mode
            self.mode = self.manual_mode or dec.mode
        payload = self.payload_bits or 1
        self.bus.event("window", mode=self.mode, prev_mode=old, epoch=self.ratchet.epoch,
                       session=f"{self.session_id:016x}", policy=self.policy.name, reason=dec.reason,
                       manual=self.manual_mode, threat=round(threat_score(f), 3), features=f,
                       counts=dict(ok=w.ok, lost=w.lost, tag_fail=w.tag_fail, replay=w.replay,
                                   malformed=w.malformed, stale_epoch=w.stale_epoch, junk=w.junk,
                                   fb_ok=w.fb_ok, fb_forged=w.fb_forged, fb_replay=w.fb_replay),
                       alerts=w.alerts[:20], hb_age=round(w.hb_age, 2),
                       enc_fraction=round(self.enc_bits / payload, 4),
                       frames=self.frames_sent, fps=round(self.measured_fps, 2),
                       encode_ms=round(1000 * self.t_encode, 1), policy_info=self.policy.info())
        self.enc_bits = self.payload_bits = self.frames_sent = 0

    # ---------------------------------------------------------------- main
    def run(self):
        for fn in (self.feedback_loop, self.control_loop):
            threading.Thread(target=fn, daemon=True).start()
        s = self.cfg["sender"]
        self.bus.event("start", session=f"{self.session_id:016x}", mode=self.mode, policy=self.policy.name,
                       encoder=self.encoder.name, size=[s["width"], s["height"]], fps=self.fps)
        print(f"sender: session {self.session_id:016x}, {s['width']}x{s['height']} @ {self.fps} fps, "
              f"encoder={self.encoder.name}, policy={self.policy.name} -> {self.vaddr}")
        next_t = time.monotonic()
        next_win = next_t + self.cfg["defence"]["window_s"]
        t_fps, n_fps, self.measured_fps = time.monotonic(), 0, 0.0
        try:
            while self.running:
                now = time.monotonic()
                if now >= next_win:
                    self.defence_step()
                    next_win += self.cfg["defence"]["window_s"]
                    if now > next_win:
                        next_win = now + self.cfg["defence"]["window_s"]
                if self.paused or now < next_t:
                    time.sleep(min(0.01, max(0.0, next_t - now)))
                    continue
                next_t = max(next_t + 1.0 / self.fps, now - 0.5)
                rgb = self.source.read()
                if rgb is None:
                    print("sender: end of video")
                    break
                self.send_frame(rgb)
                n_fps += 1
                if now - t_fps >= 1.0:
                    self.measured_fps, t_fps, n_fps = n_fps / (now - t_fps), now, 0
        except KeyboardInterrupt:
            pass
        self.running = False
        if hasattr(self.policy, "save") and getattr(self.policy, "memory_file", None):
            self.policy.save()

    def send_frame(self, rgb):
        with self.lock:
            key, sid, ctr, mode = self.ratchet.key, self.session_id, self.ctr, self.mode
            self.ctr += 1
        t0 = time.perf_counter()
        out = self.encoder.encode(rgb, key, sid, ctr, mode)
        self.t_encode = time.perf_counter() - t0
        jpeg = self.padder.pad(out.jpeg)          # link.pad (size side channel); "none" = unchanged
        wire.send_message(self.vsock, self.vaddr, wire.VIDEO, jpeg, ctr, stream=0,
                          size=self.cfg["link"]["fragment"])
        self.enc_bits += out.enc_bits
        self.payload_bits += out.payload_bits
        self.frames_sent += 1
        if ctr % self.cfg["sender"]["preview_every"] == 0:
            ok, buf = cv2.imencode(".jpg", cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 80])
            if ok:
                self.bus.preview("camera", buf.tobytes())


def main():
    cfg, _ = config.from_args(__doc__)
    Sender(cfg).run()


if __name__ == "__main__":
    main()
