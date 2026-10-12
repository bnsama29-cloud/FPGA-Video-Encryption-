"""HTTP MJPEG server on the PC -- the same thing the PYNQ-Z2 will run (section 4.1).

Encodes a video (or webcam) with the golden model and serves the encrypted frames as
multipart/x-mixed-replace. VLC plays it (scrambled); receiver.py decrypts it.

    python scripts/mjpeg_server.py --video test_video.mp4 --mode E2
    VLC:      Media > Open Network Stream > http://localhost:8080/stream.mjpg
    receiver: python scripts/receiver.py --url http://localhost:8080/stream.mjpg

Pure-Python encoding is slow (a few fps at 320x240). On the board the fabric does
this in hardware; here we only need it to behave identically.
--tamper N corrupts every Nth frame so you can watch the receiver catch it.
"""
import argparse
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import _common
import numpy as np

from model.jpeg import encode_frame

BOUNDARY = b"frameboundary"


class Broadcaster:
    def __init__(self):
        self.cond = threading.Condition()
        self.frame = None
        self.seq = 0

    def publish(self, jpeg):
        with self.cond:
            self.frame = jpeg
            self.seq += 1
            self.cond.notify_all()

    def wait(self, last_seq, timeout=5.0):
        with self.cond:
            self.cond.wait_for(lambda: self.seq != last_seq, timeout)
            return self.seq, self.frame


def producer(a, key, bc, stop):
    size = _common.parse_size(a.size)
    session = a.session if a.session is not None else int.from_bytes(np.random.bytes(8), "big")
    ctr = 0
    rng = np.random.default_rng()
    print(f"session id 0x{session:016x}, mode {a.mode}, key {key.hex()}")
    while not stop.is_set():
        for _, rgb in _common.read_frames(a.video, size):
            if stop.is_set():
                return
            t0 = time.perf_counter()
            jpeg = encode_frame(rgb, key, session, ctr, a.mode, a.quality).jpeg
            if a.tamper and ctr % a.tamper == a.tamper - 1:
                b = bytearray(jpeg)
                b[int(rng.integers(len(b) // 2, len(b) - 2))] ^= 0x10   # attacker flips a bit
                jpeg = bytes(b)
                print(f"  frame {ctr}: TAMPERED on purpose")
            bc.publish(jpeg)
            dt = time.perf_counter() - t0
            if ctr % 10 == 0:
                print(f"frame {ctr}: {len(jpeg)} bytes, encode {dt * 1000:.0f} ms "
                      f"({1 / max(dt, 1e-6):.1f} fps)")
            ctr += 1
            if a.fps:
                time.sleep(max(0.0, 1.0 / a.fps - dt))
        # the file ended: loop it. Counters keep increasing, so nothing looks like a replay.


def make_handler(bc):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            if not self.path.startswith("/stream"):
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(b'<html><body><img src="/stream.mjpg"></body></html>')
                return
            self.send_response(200)
            self.send_header("Content-Type", f"multipart/x-mixed-replace; boundary={BOUNDARY.decode()}")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            print(f"client connected: {self.client_address[0]}")
            seq = -1
            try:
                while True:
                    seq, frame = bc.wait(seq)
                    if frame is None:
                        continue
                    self.wfile.write(b"--" + BOUNDARY + b"\r\nContent-Type: image/jpeg\r\n"
                                     b"Content-Length: " + str(len(frame)).encode() + b"\r\n\r\n")
                    self.wfile.write(frame + b"\r\n")
            except (BrokenPipeError, ConnectionResetError):
                print(f"client left: {self.client_address[0]}")
    return Handler


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True, help="video file or webcam index")
    ap.add_argument("--mode", default="E2", choices=["E0", "E1", "E2", "E3", "E4"])
    ap.add_argument("--quality", type=int, default=75)
    ap.add_argument("--size", default="320x240")
    ap.add_argument("--fps", type=float, default=0, help="cap frame rate (0 = as fast as possible)")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--key", default=_common.DEMO_KEY_HEX)
    ap.add_argument("--session", type=lambda s: int(s, 0), default=None,
                    help="session id (default: random, like the board after each boot)")
    ap.add_argument("--tamper", type=int, default=0, help="corrupt every Nth frame")
    a = ap.parse_args()
    key = _common.parse_key(a.key)
    bc = Broadcaster()
    stop = threading.Event()
    threading.Thread(target=producer, args=(a, key, bc, stop), daemon=True).start()
    srv = ThreadingHTTPServer(("0.0.0.0", a.port), make_handler(bc))
    print(f"serving http://localhost:{a.port}/stream.mjpg  (Ctrl+C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        srv.server_close()


if __name__ == "__main__":
    main()
