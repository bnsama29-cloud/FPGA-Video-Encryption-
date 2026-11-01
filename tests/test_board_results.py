"""board_results/ holds every result measured on the PYNQ-Z2. Each file listed in a board day's MANIFEST.md
(written by scripts/save_board_day.py) must be in the repository, so the board results cannot go missing again."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "board_results"


def test_every_manifest_entry_is_present():
    manifests = sorted(RESULTS.glob("*/MANIFEST.md"))
    assert manifests, "board_results/<day>/MANIFEST.md is missing"
    for m in manifests:
        listed = re.findall(r"^\| `([^`]+)` \|", m.read_text(encoding="utf-8"), flags=re.M)
        assert listed, f"{m}: no files listed"
        missing = [f for f in listed if not (m.parent / f).is_file()]
        assert not missing, f"{m.parent.name}: first missing file {missing[0]} ({len(missing)} of {len(listed)})"


def test_every_folder_in_the_readme_is_present():
    readme = (RESULTS / "README.md").read_text(encoding="utf-8")
    folders = re.findall(r"^\| `([^`]+)/`", readme, flags=re.M)
    assert folders, "board_results/README.md lists no folders"
    for f in folders:
        assert (RESULTS / f).is_dir(), f"board_results/{f}/ is listed in the README but missing"
