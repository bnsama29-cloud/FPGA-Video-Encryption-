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
