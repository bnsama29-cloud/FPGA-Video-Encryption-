"""Seeded policies and the repeated-runs table (experiments/policy_seeds.py)."""
import sys
from pathlib import Path

from link import config
from link.defence import make_policy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))
import policy_seeds  # noqa: E402


def test_policy_seed_setting():
    assert config.policy_seed(config.load(overrides=["defence.seed=-1"])) is None
    assert config.policy_seed(config.load(overrides=["defence.seed=7"])) == 7
    assert config.policy_seed(config.load()) is None                       # default: random


def test_same_seed_same_exploration():
    cfg = config.load(overrides=["defence.memory_file=''"])
    a, b, c = (make_policy("bandit", cfg, "E2", s) for s in (5, 5, 6))
    seq = lambda p: [p.rng.random() for _ in range(20)]
    sa, sb, sc = seq(a), seq(b), seq(c)
    assert sa == sb and sa != sc


def test_summarise_pairs_by_seed(tmp_path):
    def run(policy, seed, ttm, cost):
        return dict(policy=policy, seed=seed, mean_time_to_mitigate_s=ttm, mean_leakage_under_attack=0.05,
                    mean_cost=cost, mean_cost_calm=0.135, latency_ms_median=90, mitigated_episodes="4/4",
                    false_alarm_windows=0, calm_windows=45)
    runs = [run("threshold", 1, 1.2, 0.20), run("bandit", 1, 1.0, 0.18),
            run("threshold", 2, 1.3, 0.20), run("bandit", 2, 1.6, 0.21)]
    rows, paired = policy_seeds.summarise(runs, tmp_path)
    assert [r["policy"] for r in rows] == ["threshold", "bandit"]
    assert abs(rows[1]["mean_cost"][0] - 0.195) < 1e-9
    assert paired["mean_cost"]["wins"] == 1 and paired["mean_cost"]["n"] == 2
    assert abs(paired["mean_time_to_mitigate_s"]["mean_diff"] - 0.05) < 1e-9
    md = (tmp_path / "table.md").read_text()
    assert "Bandit better in" in md and "indication" in md
