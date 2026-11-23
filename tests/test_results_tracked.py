"""Bug #83: result snapshots must carry their data. `.gitignore` had `sim_out/`, which also ignored every
results/<area>/<run>/sim_out/ copy, so the JSON behind the paper never reached the repository and CI failed on a
fresh clone. Every run listed in results/neuro/README.md must have its sim_out data, and git must not ignore it."""
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NEURO = ROOT / "results" / "neuro"


def listed_runs():
    text = (NEURO / "README.md").read_text(encoding="utf-8")
    return sorted(set(re.findall(r"^\| `([^`/]+)/` \|", text, flags=re.M)))


def test_every_listed_neuro_run_has_sim_out_json():
    runs = listed_runs()
    assert len(runs) >= 10, f"README lists only {runs}"
    missing = [r for r in runs if not list((NEURO / r).glob("sim_out/**/*.json"))]
    assert not missing, f"runs listed in results/neuro/README.md without sim_out JSON: {missing}"


def test_git_does_not_ignore_result_snapshots():
    probe = "results/neuro/ANY_RUN/sim_out/neuro/x/y.json"
    r = subprocess.run(["git", "check-ignore", "-q", probe], cwd=ROOT)
    assert r.returncode == 1, f"{probe} is ignored by .gitignore (bug #83)"
