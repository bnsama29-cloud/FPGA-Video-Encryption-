"""UDP transport: fragmentation, reassembly and the small datagram header.

Every datagram = 24-byte header + payload:
    magic 'SV' | version 1 | type | stream id (u32) | message id (u32)
    | fragment index (u16) | fragment count (u16) | send time in ms (u64)
Types: VIDEO (a JPEG frame), FEEDBACK (one authenticated feedback message),
TELEMETRY (JSON event for the dashboard), PREVIEW (a JPEG for a dashboard tile),
CONTROL (JSON command).

The header is NOT authenticated and does not need to be: the frame's own Ascon
tag (inside the JPEG) and the feedback AEAD protect what matters. A lost
fragment means a lost frame, exactly as with a real RTP/UDP video link.
"""
import json
import socket
import struct
import time

MAGIC = b"SV"
VERSION = 1
HDR = struct.Struct("!2sBBIIHHQ")
VIDEO, FEEDBACK, TELEMETRY, PREVIEW, CONTROL = 1, 2, 3, 4, 5
VIEWS = {"camera": 0, "wire": 1, "receiver": 2, "attacker": 3}
VIEW_NAMES = {v: k for k, v in VIEWS.items()}


def now_ms():
    return int(time.time() * 1000)


def fragment(mtype, payload, msg_id, stream=0, size=1200, t_ms=None):
    """Split payload into datagrams."""
    t_ms = now_ms() if t_ms is None else t_ms
    n = max(1, (len(payload) + size - 1) // size)
    if n > 0xFFFF:
        raise ValueError("message too large")
    return [HDR.pack(MAGIC, VERSION, mtype, stream & 0xFFFFFFFF, msg_id & 0xFFFFFFFF, i, n, t_ms)
            + payload[i * size:(i + 1) * size] for i in range(n)]


def parse(datagram):
    """Returns (type, stream, msg_id, idx, count, t_ms, payload) or None."""
    if len(datagram) < HDR.size:
        return None
    magic, ver, mtype, stream, msg_id, idx, cnt, t_ms = HDR.unpack_from(datagram)
    if magic != MAGIC or ver != VERSION or idx >= cnt:
        return None
    return mtype, stream, msg_id, idx, cnt, t_ms, datagram[HDR.size:]


class Reassembler:
    """Collects fragments; a message is complete when all its fragments arrived.

    Incomplete messages older than `timeout` seconds are dropped and counted."""

    def __init__(self, timeout=1.0):
        self.timeout = timeout
        self.parts = {}
        self.dropped = 0          # incomplete messages that timed out
        self.junk = 0             # datagrams that are not ours at all (bad header)

    def add(self, datagram):
        p = parse(datagram)
        if p is None:
            self.junk += 1
            return None
        mtype, stream, msg_id, idx, cnt, t_ms, payload = p
        if cnt == 1:
            return mtype, stream, msg_id, t_ms, payload
        key = (mtype, stream, msg_id)
        entry = self.parts.get(key)
        if entry is None or entry[1] != cnt:
            entry = self.parts[key] = [time.monotonic(), cnt, {}, t_ms]
        entry[2][idx] = payload
        if len(entry[2]) == cnt:
            del self.parts[key]
            return mtype, stream, msg_id, entry[3], b"".join(entry[2][i] for i in range(cnt))
        self._expire()
        return None

    def _expire(self):
        t = time.monotonic()
        for key in [k for k, e in self.parts.items() if t - e[0] > self.timeout]:
            del self.parts[key]
            self.dropped += 1


def udp_socket(bind_port=None, host="127.0.0.1", timeout=None):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 << 20)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4 << 20)
    if bind_port is not None:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((host, bind_port))
    if timeout is not None:
        s.settimeout(timeout)
    return s


def send_message(sock, addr, mtype, payload, msg_id, stream=0, size=1200, t_ms=None):
    for d in fragment(mtype, payload, msg_id, stream, size, t_ms):
        sock.sendto(d, addr)


class Bus:
    """Telemetry publisher: JSON events and preview JPEGs to the dashboard / logger(s)."""

    def __init__(self, cfg, source):
        self.sock = udp_socket()
        self.addrs = [(cfg["link"]["host"], p) for p in cfg["link"]["bus"]]
        self.source = source
        self.size = cfg["link"]["fragment"]
        self.msg = 0

    def event(self, kind, **data):
        data.update(src=self.source, kind=kind, t=time.time())
        payload = json.dumps(data, separators=(",", ":")).encode()
        self._send(TELEMETRY, payload, 0)

    def preview(self, view, jpeg):
        self._send(PREVIEW, jpeg, VIEWS[view])

    def _send(self, mtype, payload, stream):
        self.msg += 1
        for addr in self.addrs:
            try:
                send_message(self.sock, addr, mtype, payload, self.msg, stream, self.size)
            except OSError:
                pass                     # nobody listening: telemetry is best effort


def send_control(cfg, port_key, **cmd):
    """Send one JSON control command to the channel ('control') or sender ('sender_control')."""
    s = udp_socket()
    s.sendto(json.dumps(cmd).encode(), (cfg["link"]["host"], cfg["link"][port_key]))
    s.close()
