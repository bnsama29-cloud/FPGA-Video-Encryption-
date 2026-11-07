"""Every paper-2 experiment script runs on tiny input and writes its json + md (DESIGN §7.3).

Fast scripts run in `make test`; N3, N7 and N11 (20-35 s each) with RUN_SLOW=1; N4 and N6 need PyTorch and are
skipped without it (they run on Kaggle); N1 runs the RTL and is covered by hardware/tb/neuro/ itself.
The board scripts run their --mock paths (golden model behind the register interface).
"""
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ENV = {**os.environ, "PYTHONPATH": os.pathsep.join([str(ROOT / "software"), str(ROOT)])}
SLOW = pytest.mark.skipif(os.getenv("RUN_SLOW") != "1", reason="RUN_SLOW=1")
TORCH = pytest.mark.skipif(importlib.util.find_spec("torch") is None, reason="needs PyTorch (Kaggle)")


def run(args, cwd=ROOT):
    p = subprocess.run([sys.executable, *args], cwd=cwd, env=ENV, capture_output=True, text=True, timeout=900)
    assert p.returncode == 0, f"{args[0]} failed:\n{p.stdout[-2000:]}\n{p.stderr[-2000:]}"
    return p.stdout


def outputs(d, name):
    j = json.loads((d / f"{name}.json").read_text(encoding="utf-8"))
    assert (d / f"{name}.md").read_text(encoding="utf-8").startswith("#")
    assert "meta" in j and j["meta"]["commit"] is not None
    return j


@pytest.mark.parametrize("script,name", [("neuro_adjacency_attack", "adjacency"), ("neuro_leakage", "leakage"),
                                         ("neuro_perm_strength", "perm_strength"), ("neuro_overhead", "overhead")])
def test_fast_experiments(tmp_path, script, name):
    run([f"experiments/{script}.py", "--quick", "--out", str(tmp_path)])
    j = outputs(tmp_path, name)
    if name == "perm_strength":
        assert all(v["exact"] for v in j["inverse"].values())
        assert set(j["refusal_below_16"].values()) == {"refused"}
        assert j["readers"]["V2"]["ours_read"] == j["readers"]["V2"]["n_cd"]


@SLOW
@pytest.mark.parametrize("script,name", [("neuro_recon_attack", "recon_attack"),
                                         ("neuro_active_attacks", "active_attacks"),
                                         ("neuro_fpe_utility", "fpe_utility")])
def test_slow_experiments(tmp_path, script, name):
    run([f"experiments/{script}.py", "--quick", "--out", str(tmp_path)])
    j = outputs(tmp_path, name)
    if name == "active_attacks":
        assert all(v["success"] == v["trials"] for v in j["attacks"].values() if v["trials"])


@TORCH
@pytest.mark.parametrize("script,name", [("neuro_learned_attack", "learned_attack"),
                                         ("neuro_task_accuracy", "task_accuracy")])
def test_torch_experiments(tmp_path, script, name):
    run([f"experiments/{script}.py", "--quick", "--out", str(tmp_path)])
    outputs(tmp_path, name)


def test_tables_without_runs(tmp_path):
    run(["experiments/neuro_hw_tables.py", "--dir", str(tmp_path), "--out", str(tmp_path)])
    assert "No build found" in (tmp_path / "hw_tables.md").read_text(encoding="utf-8")
    run(["experiments/neuro_board_tables.py", "--dir", str(tmp_path)])
    assert "No replay found" in (tmp_path / "board_tables.md").read_text(encoding="utf-8")


def test_board_mock_first_contact_and_replay(tmp_path):
    out = run(["-m", "system.board.neuro.nv_first_contact", "--mock", "--out", str(tmp_path)], cwd=ROOT / "software")
    assert "FAIL" not in out
    fc = json.loads((tmp_path / "first_contact.json").read_text(encoding="utf-8"))
    assert fc["build"] == {"pad": True, "U": 2, "L": 1} and all(v["pass"] for v in fc["cases"].values())
    run(["-m", "system.board.neuro.nv_replay", "--synthetic", "--mock", "--max-rate", "--out", str(tmp_path)],
        cwd=ROOT / "software")
    r = json.loads((tmp_path / "replay_synthetic_max.json").read_text(encoding="utf-8"))
    assert r["bit_exact"] and r["packets"] > 100
    run(["experiments/neuro_board_tables.py", "--dir", str(tmp_path)])


def test_vivado_runner_dry():
    out = run(["hardware/vivado/neuro/run_vivado_neuro.py", "--steps", "ooc", "usweep", "blocks", "--dry"])
    assert out.count("DRY") == 4 + 2 + 6 and "MAXW 1280 MAXH 720" in out
