"""save_kaggle_neuro.py copies only result files, unchanged, and records the commit and hashes."""
import hashlib
import importlib.util
import json
import zipfile
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "save_kaggle_neuro", Path(__file__).resolve().parents[1] / "software" / "scripts" / "save_kaggle_neuro.py")
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)

RESULT = json.dumps({"acc": 0.98, "meta": {"commit": "abc1234def"}}).encode()


def make_zip(path, extra=()):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("repo/sim_out/neuro/n6/nmnist/task_accuracy.json", RESULT)
        z.writestr("repo/sim_out/neuro/n6/nmnist/task_accuracy.md", "| a |\n")
        z.writestr("repo/sim_out/neuro/n5/counts.npz", b"\0" * 10)
        z.writestr("repo/sim_out/other/x.json", "{}")
        z.writestr("data_manifests/nmnist.json", "{}")
        z.writestr("logs/N6_nmnist.log", "ok")
        z.writestr("run_log.md", "# log")
        for name, data in extra:
            z.writestr(name, data)
    return path


def test_copies_only_result_files_unchanged(tmp_path):
    out = S.save(make_zip(tmp_path / "r.zip"), "N6_test", "u/k", dest=tmp_path / "neuro")
    got = sorted(p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file())
    want = ["MANIFEST.md", "README.md", "logs/N6_nmnist.log", "run_log.md",
            "sim_out/neuro/n6/nmnist/task_accuracy.json", "sim_out/neuro/n6/nmnist/task_accuracy.md"]
    assert got == want, f"first difference: got {got}, expected {want}"
    assert (out / "sim_out/neuro/n6/nmnist/task_accuracy.json").read_bytes() == RESULT
    assert hashlib.sha256(RESULT).hexdigest() in (out / "MANIFEST.md").read_text()
    assert "`abc1234def`" in (out / "README.md").read_text()
    assert "| `N6_test/` | `u/k` | abc1234 |" in (tmp_path / "neuro" / "README.md").read_text()


def test_refuses_overwrite_bad_name_and_traversal(tmp_path):
    z = make_zip(tmp_path / "r.zip", extra=[("repo/sim_out/neuro/../../../evil.json", "{}")])
    out = S.save(z, "A", "u/k", dest=tmp_path / "neuro")
    assert not any("evil" in p.name for p in tmp_path.rglob("*"))
    with pytest.raises(SystemExit, match="exists"):
        S.save(z, "A", "u/k", dest=tmp_path / "neuro")
    with pytest.raises(SystemExit, match="--name"):
        S.save(z, "../x", "u/k", dest=tmp_path / "neuro")


def test_refuses_zip_without_results(tmp_path):
    with zipfile.ZipFile(tmp_path / "e.zip", "w") as z:
        z.writestr("logs/a.log", "x")
    with pytest.raises(SystemExit, match="no sim_out/neuro"):
        S.save(tmp_path / "e.zip", "E", "u/k", dest=tmp_path / "neuro")
