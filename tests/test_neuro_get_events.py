"""software/scripts/get_events.py: DVS Gesture archives from an attached input, MD5-checked (no network)."""
import hashlib
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("get_events", ROOT / "software" / "scripts" / "get_events.py")
ge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ge)


def test_attached_archives_are_staged_where_tonic_looks(tmp_path, monkeypatch):
    inputs = tmp_path / "input" / "dvs-gesture"
    inputs.mkdir(parents=True)
    fake = {}
    for train, name in ((True, "ibmGestureTrain.tar.gz"), (False, "ibmGestureTest.tar.gz")):
        data = name.encode() * 100
        (inputs / name).write_bytes(data)
        fake[train] = (name, "https://example.invalid/never", hashlib.md5(data).hexdigest())
    monkeypatch.setattr(ge, "GESTURE", fake)
    monkeypatch.setattr(ge, "download", lambda url, dst: pytest.fail("must not download"))
    ge.stage_gesture(tmp_path / "out", tmp_path / "input")
    d = tmp_path / "out" / "dvsgesture" / "DVSGesture"
    assert sorted(p.name for p in d.iterdir()) == ["ibmGestureTest.tar.gz", "ibmGestureTrain.tar.gz"]


def test_wrong_archive_is_rejected(tmp_path, monkeypatch):
    inputs = tmp_path / "input"
    inputs.mkdir()
    (inputs / "ibmGestureTrain.tar.gz").write_bytes(b"not the archive")
    monkeypatch.setattr(ge, "GESTURE", {True: ("ibmGestureTrain.tar.gz", "x", "0" * 32)})
    with pytest.raises(RuntimeError, match="MD5"):
        ge.stage_gesture(tmp_path / "out", inputs)
    assert not (tmp_path / "out" / "dvsgesture" / "DVSGesture" / "ibmGestureTrain.tar.gz").exists()


def test_archives_unpacked_by_kaggle_are_linked(tmp_path, monkeypatch):
    # Kaggle can unpack an uploaded .tar.gz (sometimes into a folder named like the archive): the unpacked
    # ibmGestureTrain/ folder is linked where Tonic looks, with an empty file under the archive's name
    inputs = tmp_path / "input" / "dvs-gesture" / "ibmGestureTrain.tar.gz" / "ibmGestureTrain" / "user01_fluorescent"
    inputs.mkdir(parents=True)
    (inputs / "0.npy").write_bytes(b"x")
    monkeypatch.setattr(ge, "GESTURE", {True: ("ibmGestureTrain.tar.gz", "x", "0" * 32)})
    monkeypatch.setattr(ge, "download", lambda url, dst: pytest.fail("must not download"))
    ge.stage_gesture(tmp_path / "out", tmp_path / "input")
    d = tmp_path / "out" / "dvsgesture" / "DVSGesture"
    assert (d / "ibmGestureTrain.tar.gz").is_file()
    assert (d / "ibmGestureTrain").is_dir()          # a symlink (Linux, Kaggle) or a copy (Windows without privilege)
    assert [p.name for p in (d / "ibmGestureTrain").rglob("*.npy")] == ["0.npy"]


def test_nested_unpack_takes_the_folder_with_the_user_dirs(tmp_path, monkeypatch):
    # Kaggle layout seen on 7 Nov 2026: <dataset>/ibmGestureTrain/ibmGestureTrain/userNN_<light>/*.npy
    user = tmp_path / "input" / "neuro-inputs" / "ibmGestureTrain" / "ibmGestureTrain" / "user01_fluorescent"
    user.mkdir(parents=True)
    (user / "0.npy").write_bytes(b"x")
    monkeypatch.setattr(ge, "GESTURE", {True: ("ibmGestureTrain.tar.gz", "x", "0" * 32)})
    monkeypatch.setattr(ge, "download", lambda url, dst: pytest.fail("must not download"))
    ge.stage_gesture(tmp_path / "out", tmp_path / "input")
    d = tmp_path / "out" / "dvsgesture" / "DVSGesture" / "ibmGestureTrain"
    assert [p.name for p in d.iterdir()] == ["user01_fluorescent"]


def test_dataset_mounted_through_a_link_is_searched(tmp_path, monkeypatch):
    real = tmp_path / "mount" / "ibmGestureTrain" / "user02_led"
    real.mkdir(parents=True)
    (real / "1.npy").write_bytes(b"x")
    inputs = tmp_path / "input"
    inputs.mkdir()
    try:
        (inputs / "neuro-inputs").symlink_to(tmp_path / "mount", target_is_directory=True)
    except OSError:
        pytest.skip("no symlink privilege on this machine (Kaggle has it)")
    monkeypatch.setattr(ge, "GESTURE", {True: ("ibmGestureTrain.tar.gz", "x", "0" * 32)})
    monkeypatch.setattr(ge, "download", lambda url, dst: pytest.fail("must not download"))
    ge.stage_gesture(tmp_path / "out", inputs)
    assert (tmp_path / "out" / "dvsgesture" / "DVSGesture" / "ibmGestureTrain" / "user02_led").is_dir()


def test_not_found_lists_the_attached_inputs(tmp_path, monkeypatch, capsys):
    (tmp_path / "input" / "other").mkdir(parents=True)
    monkeypatch.setattr(ge, "GESTURE", {True: ("ibmGestureTrain.tar.gz", "x", "0" * 32)})

    def no_network(url, dst):
        raise OSError("offline")
    monkeypatch.setattr(ge, "download", no_network)
    with pytest.raises(RuntimeError, match="not attached and the download failed"):
        ge.stage_gesture(tmp_path / "out", tmp_path / "input")
    assert "other/" in capsys.readouterr().out


# ---------------------------------------------------------------- DVS Gesture / FireNet from one zip (Google Drive)
import http.server
import io
import threading
import zipfile


class _RangeHandler(http.server.BaseHTTPRequestHandler):
    """Serves one in-memory file with byte-range support, like drive.usercontent.google.com."""
    payload = b""
    requests = []

    def do_GET(self):
        a, b = 0, len(self.payload) - 1
        rng = self.headers.get("Range")
        if rng:
            lo, hi = rng.split("=")[1].split("-")
            a, b = int(lo), min(int(hi), len(self.payload) - 1)
        type(self).requests.append((a, b))
        body = self.payload[a:b + 1]
        self.send_response(206 if rng else 200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        if rng:
            self.send_header("Content-Range", f"bytes {a}-{b}/{len(self.payload)}")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


@pytest.fixture
def zip_server():
    members = {"ibmGestureTrain.tar.gz": b"train" * 4000, "ibmGestureTest.tar.gz": b"test" * 3000,
               "firenet_1000.pth.tar": b"weights" * 50, "big_unused.bin": bytes(40_000_000)}         # > 2 x the 8 MB read buffer
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
        for n, d in members.items():
            z.writestr(n, d)
    _RangeHandler.payload, _RangeHandler.requests = buf.getvalue(), []
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _RangeHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}/datasets.zip", members
    srv.shutdown()


def test_drive_share_link_becomes_a_direct_download():
    want = "https://drive.usercontent.google.com/download?id=10lsAYQsfsbdzGWrA0LGmoyUqisoYGINq&export=download&confirm=t"
    assert ge.drive_url("https://drive.google.com/file/d/10lsAYQsfsbdzGWrA0LGmoyUqisoYGINq/view?usp=sharing") == want
    assert ge.drive_url("https://drive.google.com/open?id=10lsAYQsfsbdzGWrA0LGmoyUqisoYGINq") == want
    assert ge.drive_url("10lsAYQsfsbdzGWrA0LGmoyUqisoYGINq") == want
    assert ge.drive_url("https://example.org/a.zip") == "https://example.org/a.zip"


def test_one_member_is_extracted_without_downloading_the_zip(tmp_path, zip_server, monkeypatch):
    url, members = zip_server
    got = ge.extract_from_zip(url, ["firenet_1000.pth.tar"], tmp_path)
    assert got["firenet_1000.pth.tar"].read_bytes() == members["firenet_1000.pth.tar"]
    fetched = sum(b - a + 1 for a, b in _RangeHandler.requests)
    assert fetched < len(_RangeHandler.payload) // 2, f"read {fetched} of {len(_RangeHandler.payload)} bytes"
    n = len(_RangeHandler.requests)
    ge.extract_from_zip(url, ["firenet_1000.pth.tar"], tmp_path)          # present with the right size: no re-read
    assert all(b - a < 1 << 16 for a, b in _RangeHandler.requests[n:]), "re-extracted an existing member"


def test_gesture_comes_from_the_zip_when_nothing_is_attached(tmp_path, zip_server, monkeypatch):
    monkeypatch.setattr(ge.shutil, "disk_usage", lambda p: type("U", (), {"free": 1e12})())   # not this host's disk
    url, members = zip_server
    fake = {True: ("ibmGestureTrain.tar.gz", "https://example.invalid/never",
                   hashlib.md5(members["ibmGestureTrain.tar.gz"]).hexdigest()),
            False: ("ibmGestureTest.tar.gz", "https://example.invalid/never",
                    hashlib.md5(members["ibmGestureTest.tar.gz"]).hexdigest())}
    monkeypatch.setattr(ge, "GESTURE", fake)
    monkeypatch.setattr(ge, "download", lambda u, d: pytest.fail("figshare must not be used"))
    ge.stage_gesture(tmp_path / "out", [tmp_path / "nothing-attached"], url)
    d = tmp_path / "out" / "dvsgesture" / "DVSGesture"
    assert (d / "ibmGestureTrain.tar.gz").read_bytes() == members["ibmGestureTrain.tar.gz"]
    assert (d / "ibmGestureTest.tar.gz").read_bytes() == members["ibmGestureTest.tar.gz"]


def test_attached_archive_wins_over_the_zip(tmp_path, zip_server, monkeypatch):
    url, members = zip_server
    att = tmp_path / "input" / "x"
    att.mkdir(parents=True)
    (att / "ibmGestureTrain.tar.gz").write_bytes(b"attached copy")
    monkeypatch.setattr(ge, "GESTURE", {True: ("ibmGestureTrain.tar.gz", "x", hashlib.md5(b"attached copy").hexdigest())})
    monkeypatch.setattr(ge, "extract_from_zip", lambda *a: pytest.fail("the zip must not be read"))
    ge.stage_gesture(tmp_path / "out", [tmp_path / "input"], url)


def test_server_without_ranges_is_reported(tmp_path):
    class NoRange(_RangeHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<html>sign in</html>")
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), NoRange)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        with pytest.raises(OSError, match="HTML page|byte-range"):
            ge.RangeReader(f"http://127.0.0.1:{srv.server_port}/x", tries=1)
    finally:
        srv.shutdown()


def _fake_gesture(monkeypatch):
    fake = {True: ("ibmGestureTrain.tar.gz", "https://example.invalid/never", hashlib.md5(b"train").hexdigest()),
            False: ("ibmGestureTest.tar.gz", "https://example.invalid/never", hashlib.md5(b"test").hexdigest())}
    monkeypatch.setattr(ge, "GESTURE", fake)
    return fake


def test_unpacked_archives_are_emptied_and_still_accepted(tmp_path, monkeypatch):
    """shrink_gesture frees the 3.1 GB of archives once Tonic unpacked them; a re-run must not fetch them again."""
    _fake_gesture(monkeypatch)
    d = tmp_path / "out" / "dvsgesture" / "DVSGesture"
    for name, data in (("ibmGestureTrain", b"train"), ("ibmGestureTest", b"test")):
        (d / name / "user01_led").mkdir(parents=True)
        (d / name / "user01_led" / "0.npy").write_bytes(b"x")
        (d / f"{name}.tar.gz").write_bytes(data)
    ge.shrink_gesture(tmp_path / "out")
    assert (d / "ibmGestureTrain.tar.gz").stat().st_size == 0 and (d / "ibmGestureTrain.tar.gz.md5ok").exists()
    monkeypatch.setattr(ge, "download", lambda u, dst: pytest.fail("must not download again"))
    monkeypatch.setattr(ge, "extract_from_zip", lambda *a: pytest.fail("must not read the zip again"))
    ge.stage_gesture(tmp_path / "out", [tmp_path / "nothing"], "http://127.0.0.1:9/never.zip")


def test_emptied_archive_without_its_folder_is_fetched_again(tmp_path, monkeypatch, zip_server):
    monkeypatch.setattr(ge.shutil, "disk_usage", lambda p: type("U", (), {"free": 1e12})())   # not this host's disk
    url, members = zip_server
    monkeypatch.setattr(ge, "GESTURE", {True: ("ibmGestureTrain.tar.gz", "x",
                                               hashlib.md5(members["ibmGestureTrain.tar.gz"]).hexdigest())})
    d = tmp_path / "out" / "dvsgesture" / "DVSGesture"
    d.mkdir(parents=True)
    (d / "ibmGestureTrain.tar.gz").write_bytes(b"")
    (d / "ibmGestureTrain.tar.gz.md5ok").write_text(ge.GESTURE[True][2])        # marker, but the folder is gone
    ge.stage_gesture(tmp_path / "out", [tmp_path / "nothing"], url)
    assert (d / "ibmGestureTrain.tar.gz").read_bytes() == members["ibmGestureTrain.tar.gz"]


def test_too_little_disk_stops_before_the_zip_is_read(tmp_path, monkeypatch, zip_server):
    url, _ = zip_server
    _fake_gesture(monkeypatch)
    monkeypatch.setattr(ge.shutil, "disk_usage", lambda p: type("U", (), {"free": 5e9})())
    monkeypatch.setattr(ge, "extract_from_zip", lambda *a: pytest.fail("zip read despite too little disk"))
    with pytest.raises(RuntimeError, match="needs .* GB free"):
        ge.stage_gesture(tmp_path / "out", [tmp_path / "nothing"], url)


def test_event_reid_is_not_downloaded_again_once_unpacked(tmp_path, monkeypatch):
    import zipfile as zf
    z = tmp_path / "src.zip"
    with zf.ZipFile(z, "w") as f:
        f.writestr("Event_ReId/001/cam01/events.txt", "640 480\n1.0 1 1 1\n")
    files = [{"key": "Event_ReId.zip", "size": z.stat().st_size, "url": "u", "checksum": "md5:abc"}]
    monkeypatch.setattr(ge, "zenodo_files", lambda: files)
    calls = []
    monkeypatch.setattr(ge, "download", lambda url, dst: (calls.append(url), dst.parent.mkdir(parents=True,
                        exist_ok=True), dst.write_bytes(z.read_bytes())))
    ge.get_eventreid(tmp_path / "out", 40.0, False)
    ge.get_eventreid(tmp_path / "out", 40.0, False)
    assert calls == ["u"], f"downloaded {len(calls)} times"
    assert (tmp_path / "out" / "eventreid" / "Event_ReId" / "Event_ReId" / "001" / "cam01" / "events.txt").exists()
