"""HTTP dashboard routes and listener configuration."""
import http.client
import json
import threading
import time
from types import SimpleNamespace

import pytest

from link import config, dashboard


@pytest.fixture
def dashboard_server():
    cfg = config.load(overrides=["dashboard.http_port=0"])
    hub = SimpleNamespace(
        cfg=cfg,
        frames={},
        frame_seq={},
        cond=threading.Condition(),
        clients=set(),
        latest={},
        lock=threading.Lock(),
    )
    server = dashboard.QuietServer(("127.0.0.1", 0), dashboard.make_handler(hub))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield hub, server.server_address[1]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def request(port, method, path, body=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
    headers = {"Content-Type": "application/json"} if body is not None else {}
    conn.request(method, path, body=body, headers=headers)
    return conn, conn.getresponse()


def test_dashboard_page_and_state_are_served(dashboard_server):
    hub, port = dashboard_server
    hub.latest["receiver.frame"] = {"src": "receiver", "kind": "frame", "verdict": "ok"}

    conn, response = request(port, "GET", "/")
    assert response.status == 200
    assert b"Secure Link Console" in response.read()
    conn.close()

    conn, response = request(port, "GET", "/api/state")
    assert response.status == 200
    state = json.loads(response.read())
    assert state["latest"]["receiver.frame"]["verdict"] == "ok"
    conn.close()


def test_frame_still_and_all_mjpeg_views_are_available(dashboard_server):
    hub, port = dashboard_server
    jpeg = b"\xff\xd8test-jpeg\xff\xd9"
    views = ("camera", "wire", "receiver", "attacker")

    for view in views:
        hub.frames[view] = jpeg
        hub.frame_seq[view] = 1

        conn, response = request(port, "GET", f"/frame/{view}.jpg")
        assert response.status == 200
        assert response.read() == jpeg
        conn.close()

        conn, response = request(port, "GET", f"/stream/{view}.mjpg")
        assert response.status == 200
        assert response.getheader("Content-Type").startswith("multipart/x-mixed-replace")
        assert response.readline() == b"--frame\r\n"
        content_length = None
        while True:
            line = response.readline()
            if line == b"\r\n":
                break
            if line.lower().startswith(b"content-length:"):
                content_length = int(line.split(b":", 1)[1])
        assert content_length == len(jpeg)
        assert response.read(content_length) == jpeg
        conn.close()


def test_event_stream_and_dashboard_controls_work(dashboard_server, monkeypatch):
    hub, port = dashboard_server
    conn, response = request(port, "GET", "/events")
    assert response.status == 200
    assert response.getheader("Content-Type") == "text/event-stream"

    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        with hub.lock:
            clients = list(hub.clients)
        if clients:
            break
        time.sleep(0.01)
    assert clients
    event = json.dumps({"src": "receiver", "kind": "frame", "verdict": "ok"})
    clients[0].put_nowait(event)
    assert response.readline() == f"data: {event}\n".encode()
    assert response.readline() == b"\n"
    conn.close()

    sent = []
    monkeypatch.setattr(dashboard.wire, "send_control",
                        lambda cfg, target, **cmd: sent.append((cfg, target, cmd)))
    conn, response = request(port, "POST", "/api/channel",
                             json.dumps({"cmd": "attack", "type": "bitflip"}))
    assert response.status == 200
    assert json.loads(response.read()) == {"ok": True}
    conn.close()
    assert sent == [(hub.cfg, "control", {"cmd": "attack", "type": "bitflip"})]

    conn, response = request(port, "POST", "/api/sender",
                             json.dumps({"cmd": "policy", "policy": "fixed"}))
    assert response.status == 200
    assert json.loads(response.read()) == {"ok": True}
    conn.close()
    assert sent[-1] == (hub.cfg, "sender_control", {"cmd": "policy", "policy": "fixed"})


def test_dashboard_listener_uses_configured_bind_host(monkeypatch):
    cfg = config.load(overrides=["dashboard.bind_host=0.0.0.0", "dashboard.http_port=8123"])
    captured = {}

    class Server:
        daemon_threads = False

        def __init__(self, address, handler):
            captured["address"] = address

        def serve_forever(self):
            raise KeyboardInterrupt

    monkeypatch.setattr(dashboard.config, "from_args", lambda _doc: (cfg, None))
    monkeypatch.setattr(dashboard, "Hub", lambda _cfg: SimpleNamespace(cfg=cfg, loop=lambda: None))
    monkeypatch.setattr(dashboard.threading, "Thread",
                        lambda **_kwargs: SimpleNamespace(start=lambda: None))
    monkeypatch.setattr(dashboard, "QuietServer", Server)

    dashboard.main()
    assert captured["address"] == ("0.0.0.0", 8123)


def test_dashboard_defaults_to_localhost_and_rejects_unknown_view(dashboard_server):
    assert config.load()["dashboard"]["bind_host"] == "127.0.0.1"
    hub, port = dashboard_server

    conn, response = request(port, "GET", "/stream/not-a-view.mjpg")
    assert response.status == 404
    conn.close()
