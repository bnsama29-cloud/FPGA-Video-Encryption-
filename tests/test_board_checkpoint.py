"""Board-day checkpoints: first_contact saves every finished bit-exact level and --resume continues after it
(a 640x480 level takes ~10 min on the board's ARM), and scripts/pull_board_results.py copies the board's
results to the laptop and lists what is done."""
import io
import json
import sys
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from system.board import first_contact as fc          # noqa: E402
from scripts import pull_board_results as pbr              # noqa: E402

ARGS = ["--mock-lanes", "2", "--mock-e5", "--sizes", "32x16", "--frames", "1", "--timing-frames", "1"]


def _run(out, *extra):
    with pytest.raises(SystemExit) as e:
        fc.main(ARGS + ["--out", str(out), *extra])
    return e.value.code


def test_interrupted_run_resumes_after_the_saved_levels(tmp_path, monkeypatch):
    real = fc.expected_jpeg
    calls = []

    def stop_at_third(ip, rgb, quality, mode, ctr):
        calls.append(mode)
        if len(calls) == 3:
            raise KeyboardInterrupt
        return real(ip, rgb, quality, mode, ctr)
    monkeypatch.setattr(fc, "expected_jpeg", stop_at_third)
    assert _run(tmp_path) == 130, "Ctrl+C must stop with exit code 130"
    saved = json.loads((tmp_path / fc.PROGRESS).read_text())
    assert [(r["size"], r["mode"], r["bit_exact"]) for r in saved["rows"]] == [("32x16", 0, True), ("32x16", 1, True)]
    assert not (tmp_path / "first_contact.json").exists()

    calls.clear()
    monkeypatch.setattr(fc, "expected_jpeg", lambda *a: calls.append(a[3]) or real(*a))
    assert _run(tmp_path, "--resume") == 0
    assert calls == [2, 3, 4, 5], f"--resume must check only E2..E5, checked {calls}"
    res = json.loads((tmp_path / "first_contact.json").read_text())
    assert res["all_bit_exact"] and [r["mode"] for r in res["exactness"]] == [0, 1, 2, 3, 4, 5]
    assert len(json.loads((tmp_path / fc.PROGRESS).read_text())["rows"]) == 6


def test_progress_of_another_check_is_not_reused(tmp_path, monkeypatch):
    assert _run(tmp_path) == 0                                   # frames 1, all six levels saved
    real, calls = fc.expected_jpeg, []
    monkeypatch.setattr(fc, "expected_jpeg", lambda *a: calls.append(a[3]) or real(*a))
    with pytest.raises(SystemExit):
        fc.main([*ARGS[:-4], "--frames", "2", "--timing-frames", "1", "--out", str(tmp_path), "--resume"])
    assert calls == [m for m in range(6) for _ in range(2)], "another --frames must start over"
    calls.clear()
    assert _run(tmp_path) == 0                                   # no --resume: start over
    assert calls == [0, 1, 2, 3, 4, 5]


def test_a_failed_level_is_checked_again_on_resume(tmp_path):
    meta = dict(bitfile="mock", ip=[3, 2, True, "rgb"], frames=1, source="synthetic", quality=75, fclk_mhz=None)
    rows = [dict(size="32x16", mode=0, frames=1, bit_exact=True, first_mismatch=None),
            dict(size="32x16", mode=1, frames=1, bit_exact=False, first_mismatch=dict(frame=0))]
    fc.save_progress(tmp_path, meta, rows)
    done = fc.load_progress(tmp_path, meta, resume=True)
    assert list(done) == [("32x16", 0)], f"only bit-exact levels are skipped, got {list(done)}"


def _tgz(files):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def test_pull_unpacks_only_the_result_folders_and_lists_them(tmp_path):
    done = dict(all_bit_exact=True, exactness=[dict(frames=3)], speed=[{}] * 12)
    timing = dict(all_bit_exact=True, exactness=[dict(frames=0)], speed=[{}] * 6)
    prog = dict(meta={}, rows=[dict(size="640x480", mode=0, bit_exact=True), dict(size="640x480", mode=1, bit_exact=True)])
    data = _tgz({"sim_out/board/lanes4_final/first_contact.json": json.dumps(done).encode(),
                 "sim_out/board/lanes2_final_640/first_contact.json": json.dumps(timing).encode(),
                 "sim_out/board/v2_final/bitexact_progress.json": json.dumps(prog).encode(),
                 "sim_out/pq_kex/pynq.md": b"x",
                 "../evil.txt": b"no", "model/hw.py": b"no", "/etc/passwd": b"no"})
    assert pbr.unpack(data, tmp_path) == 4
    assert not (tmp_path / "model").exists() and not (tmp_path.parent / "evil.txt").exists()
    rows = {r[0]: r for r in pbr.board_rows(tmp_path / "sim_out")}
    assert rows["lanes4_final"][1:] == ("done", "bit-exact yes (3 frames each), 12 timing rows")
    assert rows["lanes2_final_640"][2].startswith("timing only")
    assert rows["v2_final"][1] == "stopped" and "--resume" in rows["v2_final"][2]
    assert rows["pq_kex/pynq.md"][1] == "done"
