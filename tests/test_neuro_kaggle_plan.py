"""kaggle_neuro.plan(): the step groups of each Kaggle part and the STEPS narrowing (16 Nov 2026: part A runs
STEPS=cpu as a CPU session while part C runs N6, so N6 is not trained twice and A skips the T4 queue).

kaggle_neuro.py is a job script (it clones and installs at import), so the test compiles only plan() from its source."""
import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "software" / "system" / "kaggle" / "kaggle_neuro.py"


def _plan():
    tree = ast.parse(SRC.read_text(encoding="utf-8"))
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "plan")
    ns = {}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(SRC), "exec"), ns)
    return ns["plan"]


plan = _plan()


@pytest.mark.parametrize("part,expected", [("A", {"cpu", "n6"}), ("B", {"n3", "n4"}), ("C", {"n6"})])
def test_default_steps_per_part(part, expected):
    got = plan(part)
    assert got == expected, f"part {part}: got {sorted(got)}, expected {sorted(expected)}"
    assert plan(part, "") == expected, "an empty STEPS must keep the defaults"


def test_steps_narrows_part_a_to_cpu():
    assert plan("A", "cpu") == {"cpu"}
    assert plan("A", " CPU , ") == {"cpu"}, "STEPS is case- and space-insensitive"


def test_steps_outside_the_part_is_refused():
    with pytest.raises(SystemExit, match="n3"):
        plan("A", "cpu,n3")         # a typo or a wrong part must stop the run, not silently skip steps


def _fn(name):
    tree = ast.parse(SRC.read_text(encoding="utf-8"))
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    ns = {}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(SRC), "exec"), ns)
    return ns[name]


def test_n6_quick_passes_quick_so_the_small_ciphertext_subset_is_used():
    """TESTING bug #64: QUICK gave N6 only --limit 300 --epochs 2, so N6 sealed its full-run subset and timed out."""
    n6_args = _fn("n6_args")
    q = n6_args(True, [0, 1, 2]).split()
    assert "--quick" in q, f"QUICK N6 options {q} lack --quick"
    assert q[q.index("--limit") + 1] == "300", f"QUICK N6 options {q}: clean model limit should be 300"
    full = n6_args(False, [0, 1, 2])
    assert full == "--seeds 0 1 2", f"full N6 options: got {full!r}, expected '--seeds 0 1 2'"


def test_n6_datasets_default_and_narrowed():
    """Bug #65: a second account runs N6 on DVS Gesture alone (N6_DATASETS=dvsgesture)."""
    f = _fn("n6_datasets")
    assert f(None) == ["nmnist", "dvsgesture"]
    assert f(" DVSGesture ") == ["dvsgesture"]
    with pytest.raises(SystemExit, match="cifar"):
        f("dvsgesture,cifar")


def test_n6_gets_the_session_budget_in_full_runs():
    src = SRC.read_text(encoding="utf-8")
    assert "N6_S = GPU_S if QUICK else DEADLINE_S" in src
    assert 'limit=N6_S, want="wrote "' in src, "N6 must run under N6_S, not the 4-hour GPU_S"


def test_only_reruns_named_steps_and_setup():
    """Bug #66: ONLY reruns one failed step (as paper 1's --only) without the rest of the part."""
    ns = {}
    tree = ast.parse(SRC.read_text(encoding="utf-8"))
    keep = [n for n in tree.body if (isinstance(n, ast.FunctionDef) and n.name == "selected") or
            (isinstance(n, ast.Assign) and any(getattr(t, "id", "") == "SETUP" for t in n.targets))]
    exec(compile(ast.Module(body=keep, type_ignores=[]), str(SRC), "exec"), ns)
    sel = ns["selected"]
    only = "N5 cache nmnist, n5 NMNIST"
    for step, want in [("N5 nmnist", True), ("N5 cache nmnist", True), ("data", True), ("clone", True),
                       ("N5 dvsgesture", False), ("N9 eventreid", False)]:
        assert sel(step, only) is want, f"step {step!r} with ONLY={only!r}: got {sel(step, only)}, expected {want}"
    assert all(sel(s, "") for s in ("N5 nmnist", "N9 eventreid")), "no ONLY: every step runs"


def test_n9_caps_dvs_gesture_recordings_in_full_runs():
    """Bug #73: N9 on DVS Gesture (default 30 recordings) timed out at the 2-hour step limit on Kaggle."""
    src = SRC.read_text(encoding="utf-8")
    assert 'N9_LIMIT = {"eventreid": "--limit 8", "dvsgesture": "--limit 12"} if not QUICK else {}' in src


def test_n6sel_is_a_part_c_step_on_request_only():
    """Bug #75: the N6 model selection runs as STEPS=n6sel on part C; it is not part of any default plan."""
    assert plan("C", "n6sel") == {"n6sel"}
    assert "n6sel" not in plan("C") and "n6sel" not in plan("A")
    with pytest.raises(SystemExit):
        plan("A", "n6sel")


def test_n6x_configs_are_the_extra_models_of_n6():
    """22 Nov: the n6x step runs the EXTRA models of neuro_task_accuracy.py; names must match exactly."""
    import importlib.util
    import sys as _s
    tree = ast.parse(SRC.read_text(encoding="utf-8"))
    ns = {"os": __import__("os")}
    keep = [n for n in tree.body if (isinstance(n, ast.Assign) and any(getattr(t, "id", "") == "N6X_VIEWS"
            for t in n.targets)) or (isinstance(n, ast.FunctionDef) and n.name == "n6x_configs")]
    exec(compile(ast.Module(body=keep, type_ignores=[]), str(SRC), "exec"), ns)
    root = SRC.parents[3]
    _s.path[:0] = [str(root / "software"), str(root / "experiments")]
    spec = importlib.util.spec_from_file_location("n6mod", root / "experiments" / "neuro_task_accuracy.py")
    n6 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(n6)
    assert set(ns["N6X_VIEWS"]) == set(n6.EXTRA)
    assert ns["n6x_configs"](None) == ["N_bins8", "N_ts3", "N_snn10"]
    assert ns["n6x_configs"](" N_snn10 ") == ["N_snn10"]
    with pytest.raises(SystemExit):
        ns["n6x_configs"]("N_foo")
    assert plan("C", "n6x") == {"n6x"} and "n6x" not in plan("C")
