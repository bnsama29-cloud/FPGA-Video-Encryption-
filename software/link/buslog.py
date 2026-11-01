"""Listen on a telemetry bus port and collect events (used by experiments and tests).

    python -m link.buslog --port 47010 --out sim_out/events.jsonl     (stand-alone)
"""
import argparse
import json
import threading
import time

from . import wire


class BusLogger:
    def __init__(self, port, host="127.0.0.1", keep_previews=False):
        self.sock = wire.udp_socket(port, host, timeout=0.2)
        self.rasm = wire.Reassembler()
        self.events = []
        self.previews = {}
        self.keep_previews = keep_previews
        self.running = True
        self.lock = threading.Lock()
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def _loop(self):
        while self.running:
            try:
                data, _ = self.sock.recvfrom(65535)
            except OSError:
                continue
            m = self.rasm.add(data)
            if m is None:
                continue
            if m[0] == wire.TELEMETRY:
                try:
                    ev = json.loads(m[4])
                except ValueError:
                    continue
                with self.lock:
                    self.events.append(ev)
            elif m[0] == wire.PREVIEW and self.keep_previews:
                with self.lock:
                    self.previews[wire.VIEW_NAMES.get(m[1], "?")] = m[4]

    def take(self, kind=None, src=None):
        with self.lock:
            return [e for e in self.events if (kind is None or e["kind"] == kind)
                    and (src is None or e["src"] == src)]

    def close(self):
        self.running = False
        self.thread.join(timeout=1)
        self.sock.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=47010)
    ap.add_argument("--out", default="sim_out/events.jsonl")
    a = ap.parse_args()
    log = BusLogger(a.port)
    n = 0
    try:
        with open(a.out, "w") as f:
            while True:
                time.sleep(1)
                ev = log.take()
                for e in ev[n:]:
                    f.write(json.dumps(e) + "\n")
                f.flush()
                n = len(ev)
    except KeyboardInterrupt:
        log.close()


if __name__ == "__main__":
    main()
