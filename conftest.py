"""Repository-wide pytest setup: the Python packages (model, link, system) live in software/.
pytest.ini puts software/ on sys.path for the test process; this also puts it on PYTHONPATH so that the
subprocesses the tests start (`python -m link.sender`, cocotb's simulator) import the same packages."""
import os
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_paths = [str(_ROOT / "software"), str(_ROOT)]
_old = os.environ.get("PYTHONPATH", "")
os.environ["PYTHONPATH"] = os.pathsep.join(_paths + ([_old] if _old else []))
