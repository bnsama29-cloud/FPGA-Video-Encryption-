"""Web dashboard: live view of the link, attack console and defence state.

    python -m link.dashboard          (normally started by python -m link.run_all)
    open http://localhost:8000

Listens on the telemetry bus (UDP) and serves:
  /                         the dashboard page (link/static/dashboard.html)
  /events                   Server-Sent Events: every telemetry event as JSON
  /stream/<view>.mjpg       live MJPEG of camera | wire | receiver | attacker
                            (VLC: Media > Open Network Stream > http://localhost:8000/stream/wire.mjpg
                             plays the real scrambled stream)
  /frame/<view>.jpg         latest still
  /api/state                snapshot of the latest events
  POST /api/channel         JSON command forwarded to the channel (attacks, impairments)
  POST /api/sender          JSON command forwarded to the sender (policy, mode, rekey, fps)
Only standard-library modules, so nothing extra to install.
"""
import json
import queue
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import config, wire

STATIC = Path(__file__).resolve().parent / "static"


class Hub:
    """Receives the bus and fans events / frames out to HTTP clients."""

    def __init__(self, cfg):
        self.cfg = cfg
        self.sock = wire.udp_socket(cfg["link"]["bus"][0], config.bind_host(cfg), timeout=0.2)
        self.rasm = wire.Reassembler()
        self.frames = {}
        self.frame_seq = {}
        self.cond = threading.Condition()
        self.clients = set()
        self.latest = {}
        self.lock = threading.Lock()

    def loop(self):
        while True:
            try:
                data, _ = self.sock.recvfrom(65535)
            except OSError:
                continue
            m = self.rasm.add(data)
            if m is None:
                continue
            if m[0] == wire.PREVIEW:
                view = wire.VIEW_NAMES.get(m[1])
                with self.cond:
                    self.frames[view] = m[4]
                    self.frame_seq[view] = self.frame_seq.get(view, 0) + 1
                    self.cond.notify_all()
            elif m[0] == wire.TELEMETRY:
                text = m[4].decode("utf-8", "replace")
                try:
                    ev = json.loads(text)
                    with self.lock:
                        self.latest[f"{ev['src']}.{ev['kind']}"] = ev
                except (ValueError, KeyError):
                    continue
                with self.lock:
                    dead = []
                    for q in self.clients:
                        try:
                            q.put_nowait(text)
                        except queue.Full:
                            dead.append(q)
                    for q in dead:
                        self.clients.discard(q)


def make_handler(hub):
    cfg = hub.cfg

    class H(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *a):
            pass

        def _send(self, code, body, ctype="application/json"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = self.path.split("?")[0]
            if path in ("/", "/index.html"):
                return self._send(200, (STATIC / "dashboard.html").read_bytes(), "text/html; charset=utf-8")
            if path == "/events":
                return self._events()
            if path.startswith("/stream/") and path.endswith(".mjpg"):
                return self._mjpeg(path[8:-5])
            if path.startswith("/frame/") and path.endswith(".jpg"):
                f = hub.frames.get(path[7:-4])
                return self._send(200, f, "image/jpeg") if f else self._send(404, b"no frame yet")
            if path == "/api/state":
                with hub.lock:
                    body = json.dumps(dict(latest=hub.latest, config=dict(
                        sender=cfg["sender"], channel=cfg["channel"], defence=cfg["defence"]))).encode()
                return self._send(200, body)
            self._send(404, b"not found", "text/plain")

        def do_POST(self):
            n = int(self.headers.get("Content-Length", 0))
            try:
                cmd = json.loads(self.rfile.read(n) or b"{}")
            except ValueError:
                return self._send(400, b'{"error":"body must be JSON"}')
            target = {"/api/channel": "control", "/api/sender": "sender_control"}.get(self.path)
            if target is None:
                return self._send(404, b'{"error":"unknown endpoint"}')
            wire.send_control(cfg, target, **cmd)
            self._send(200, b'{"ok":true}')

        def _events(self):
            q = queue.Queue(maxsize=2000)
            with hub.lock:
                hub.clients.add(q)
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            try:
                while True:
                    try:
                        msg = q.get(timeout=5)
                        self.wfile.write(f"data: {msg}\n\n".encode())
                    except queue.Empty:
                        self.wfile.write(b": keep-alive\n\n")
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass
            finally:
                with hub.lock:
                    hub.clients.discard(q)

        def _mjpeg(self, view):
            if view not in wire.VIEWS:
                return self._send(404, b"unknown view", "text/plain")
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            seen = -1
            try:
                while True:
                    with hub.cond:
                        hub.cond.wait_for(lambda: hub.frame_seq.get(view, 0) != seen, timeout=5)
                        seen = hub.frame_seq.get(view, 0)
                        f = hub.frames.get(view)
                    if f is None:
                        continue
                    self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                                     + str(len(f)).encode() + b"\r\n\r\n" + f + b"\r\n")
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass

    return H


class QuietServer(ThreadingHTTPServer):
    """A browser tab that closes or reloads drops its open video/event streams. Windows reports that
    as WinError 10053/10054; it is normal, so it is not printed as an error."""

    def handle_error(self, request, client_address):
        import sys
        if isinstance(sys.exc_info()[1], (ConnectionAbortedError, ConnectionResetError, BrokenPipeError)):
            return
        super().handle_error(request, client_address)


def main():
    cfg, _ = config.from_args(__doc__)
    hub = Hub(cfg)
    threading.Thread(target=hub.loop, daemon=True).start()
    port = cfg["dashboard"]["http_port"]
    srv = QuietServer(("0.0.0.0", port), make_handler(hub))
    srv.daemon_threads = True
    print(f"dashboard: http://localhost:{port}   (bus port {cfg['link']['bus'][0]})")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
