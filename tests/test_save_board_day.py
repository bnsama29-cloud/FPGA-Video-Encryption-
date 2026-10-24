"""scripts/save_board_day.py: board-day results go from sim_out/ (git-ignored) to paper/data/board/<name>/,
only result files, with a manifest, and never a file that holds the demo or session key."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

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
        "future_work/baselines/power_template.md": "| |",
        "configs/demo_key.txt": "167ae045648ba4c22af59f4c743abc38"})
    dest = tmp_path / "paper/data/board/day"
    rows, skipped = sbd.save(dest, root=tmp_path)
    got = sorted(r[1].as_posix() for r in rows)
    assert got == ["board/lanes4_final/first_contact.json", "energy/power_template.md", "pq_kex/pynq.md",
                   "runs/board_full_suite_rep1/summary.json", "runs/hw_tamper_rep1/events.jsonl"], got
    assert not skipped
    assert (dest / "runs/hw_tamper_rep1/events.jsonl").exists()
    assert "board/lanes4_final/first_contact.json" in (dest / "MANIFEST.md").read_text()


def test_stops_before_copying_a_file_with_the_key(tmp_path):
    key = "167ae045648ba4c22af59f4c743abc38"
    _tree(tmp_path, {"configs/demo_key.txt": key + "\n",
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
