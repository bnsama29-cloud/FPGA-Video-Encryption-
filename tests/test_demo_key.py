"""scripts/demo_key.py: a fresh demo key that survives `--set keys.master=...` and never enters git."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import demo_key  # noqa: E402
from link import config  # noqa: E402


def test_new_key_is_32_hex_digits_and_stays_a_string():
    for _ in range(200):
        k = demo_key.new_key()
        assert len(k) == 32 and int(k, 16) >= 0
        cfg = config.load(None, [f"keys.master={k}"])
        assert cfg["keys"]["master"] == k, f"--set turned {k} into {cfg['keys']['master']!r}"


def test_number_like_keys_are_never_produced():
    # a hex string such as "1e50..." would be parsed by TOML as a float: new_key must reject it
    assert config._parse_value("1e5" + "0" * 29) != "1e5" + "0" * 29


def test_saved_key_is_ignored_by_git():
    r = subprocess.run(["git", "check-ignore", "configs/demo_key.txt"], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, "configs/demo_key.txt must be in .gitignore"
