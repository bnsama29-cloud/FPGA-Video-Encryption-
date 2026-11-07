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
