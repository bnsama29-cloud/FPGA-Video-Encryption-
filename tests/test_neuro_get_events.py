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
