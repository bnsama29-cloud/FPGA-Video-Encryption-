"""experiments/neuro_recon_attack.py :: Learned loads networks from an rpg_e2vid checkout although this repository's
golden model is already imported as `model` (TESTING bug #49). A stand-in checkout with rpg_e2vid's package layout
(model/model.py, utils/loading_utils.py, base/) is written to tmp_path, so no network or GPL code is needed."""
import importlib.util
import sys
import textwrap
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(importlib.util.find_spec("torch") is None, reason="needs PyTorch (Kaggle)")

FILES = {
    "base/__init__.py": "import torch.nn as nn\nclass BaseModel(nn.Module):\n    def __init__(self, config):\n"
                        "        super().__init__()\n        self.config = config\n",
    "model/__init__.py": "",
    "model/model.py": """
        import torch
        from base import BaseModel
        class Tiny(BaseModel):
            def __init__(self, config):
                super().__init__(config)
                self.conv = torch.nn.Conv2d(config['num_bins'], 1, 1)
            def forward(self, x, prev_states):
                return torch.sigmoid(self.conv(x)), prev_states
        """,
    "utils/__init__.py": "",
    "utils/loading_utils.py": """
        import torch
        from model.model import *
        def load_model(path_to_model):
            raw = torch.load(path_to_model, weights_only=False)
            model = eval(raw['arch'])(raw['model'])
            model.load_state_dict(raw['state_dict'])
            return model
        """,
}


def test_rpg_checkout_loads_after_golden_model(tmp_path):
    import torch
    import model.ascon  # noqa: F401  the golden model, imported first as the experiments do
    golden = sys.modules["model"]
    repo = tmp_path / "rpg_e2vid"
    for name, body in FILES.items():
        (repo / name).parent.mkdir(parents=True, exist_ok=True)
        (repo / name).write_text(textwrap.dedent(body))
    # write a checkpoint with the stand-in class
    sys.path.insert(0, str(repo))
    saved = {k: sys.modules.pop(k) for k in list(sys.modules) if k.split(".")[0] in ("model", "utils", "base")}
    try:
        from model.model import Tiny
        torch.save({"arch": "Tiny", "model": {"num_bins": 5}, "state_dict": Tiny({"num_bins": 5}).state_dict()},
                   tmp_path / "tiny.pth.tar")
    finally:
        sys.path.remove(str(repo))
        for k in [k for k in sys.modules if k.split(".")[0] in ("model", "utils", "base")]:
            del sys.modules[k]
        sys.modules.update(saved)

    sys.path.insert(0, str(ROOT / "experiments"))
    import neuro_recon_attack as nra
    L = nra.Learned(repo, [f"tiny={tmp_path / 'tiny.pth.tar'}"])
    assert sys.modules["model"] is golden, "golden model package not restored"
    assert "tiny" in L.models

    class G:
        W, H = 20, 18
    L.reset()
    ev = np.array([(0, 1, 2, 1), (10, 3, 4, 0), (20, 5, 6, 1)],
                  dtype=[("t", "i8"), ("x", "i4"), ("y", "i4"), ("p", "i1")])
    out = L(ev, G)
    assert out["tiny"].shape == (18, 20)


def test_input_normalisation_matches_rpg_e2vid():
    sys.path.insert(0, str(ROOT / "experiments"))
    import neuro_recon_attack as nra
    vg = np.zeros((5, 4, 4), np.float32)
    vg[0, 0, 0], vg[1, 1, 1], vg[2, 2, 2] = 1.0, -2.0, 4.0
    got = nra.normalize_nonzero(vg)
    nz = vg != 0
    want = np.where(nz, (vg - vg[nz].mean()) / vg[nz].std(), 0)
    i = np.flatnonzero(~np.isclose(got, want, atol=1e-6))
    assert i.size == 0, f"first mismatch at {i[0]}: got {got.ravel()[i[0]]}, expected {want.ravel()[i[0]]}"
    assert np.all(got[~nz] == 0)
