"""software/scripts/save_board_day.py: board-day results go from sim_out/ (git-ignored) to results/board/<name>/,
only result files, with a manifest, and never a file that holds the demo or session key."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "software")]

from scripts import save_board_day as sbd       # noqa: E402


def _tree(root, files):
    for rel, data in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(data)


def test_copies_only_board_results_with_a_manifest(tmp_path):
    _tree(tmp_path, {
        "sim_out/board/lanes4_final/first_contact.json": "{}",
        "sim_out/board/lanes4_final/frame.jpg": "binary",                 # not a result file
        "sim_out/pq_kex/pynq.md": "x",
        "sim_out/runs/board_full_suite_rep1/summary.json": "{}",
        "sim_out/runs/hw_tamper_rep1/events.jsonl": "{}\n",
        "sim_out/runs/quick_threshold/summary.json": "{}",                # laptop simulation: not board day
        "sim_out/board_backups/x.json": "{}",                             # checkpoints stay out
        "software/system/baselines/power_template.md": "| |",
        "software/configs/demo_key.txt": "167ae045648ba4c22af59f4c743abc38"})
    dest = tmp_path / "results/board/day"
    rows, skipped = sbd.save(dest, root=tmp_path)
    got = sorted(r[1].as_posix() for r in rows)
    assert got == ["board/lanes4_final/first_contact.json", "energy/power_template.md", "pq_kex/pynq.md",
                   "runs/board_full_suite_rep1/summary.json", "runs/hw_tamper_rep1/events.jsonl"], got
    assert not skipped
    assert (dest / "runs/hw_tamper_rep1/events.jsonl").exists()
    assert "board/lanes4_final/first_contact.json" in (dest / "MANIFEST.md").read_text()


def test_stops_before_copying_a_file_with_the_key(tmp_path):
    key = "167ae045648ba4c22af59f4c743abc38"
    _tree(tmp_path, {"software/configs/demo_key.txt": key + "\n",
                     "sim_out/board/a/first_contact.json": "{}",
                     "sim_out/runs/board_x/summary.json": '{"cmd": "--set keys.master=%s"}' % key})
    dest = tmp_path / "out"
    with pytest.raises(SystemExit, match="contains your demo or session key"):
        sbd.save(dest, root=tmp_path)
    assert not dest.exists(), "nothing may be copied when a key is found"


def test_dry_run_copies_nothing(tmp_path):
    _tree(tmp_path, {"sim_out/board/a/first_contact.json": "{}"})
    rows, _ = sbd.save(tmp_path / "out", root=tmp_path, dry_run=True)
    assert len(rows) == 1 and not (tmp_path / "out").exists()


def test_pull_lists_repeat_and_rekey_runs_as_done(tmp_path):
    """Bug #51: pull_board_results listed board_repeat_runs and board_rekey_load as 'unfinished' because it
    only knew hw_tamper.md and summary.json; repeat_runs writes table.md and rekey_load writes rekey_load.md."""
    from scripts import pull_board_results as pbr
    _tree(tmp_path, {
        "runs/board_repeat_runs/table.md": "x",
        "runs/board_rekey_load/rekey_load.md": "x",
        "runs/hw_tamper_journal/hw_tamper.md": "x",
        "runs/board_full_suite_rep1/summary.json": "{}",
        "runs/board_half_done/events.jsonl": "{}\n",
    })
    got = {name: state for name, state, _ in pbr.laptop_rows(tmp_path)}
    want = {"runs/board_repeat_runs": "done", "runs/board_rekey_load": "done", "runs/hw_tamper_journal": "done",
            "runs/board_full_suite_rep1": "done", "runs/board_half_done": "unfinished"}
    for k, v in want.items():
        assert got.get(k) == v, f"{k}: got {got.get(k)!r}, expected {v!r}"
