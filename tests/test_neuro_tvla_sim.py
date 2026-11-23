"""N16: experiments/neuro_tvla_sim.py (simulated first-order TVLA of the masked Ascon round)."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments"))
import neuro_tvla_sim as T  # noqa: E402

FIXED = [1, 2, 3, 4, 5]


def test_register_model_matches_the_ascon_model():
    T.check_against_model(np.random.default_rng(3), n=32)          # raises on any mismatch


def test_unmasked_leaks_and_dom_does_not_at_first_order():
    rng = np.random.default_rng(4)
    X, lab = T.traces(T.plain_registers, FIXED, 6000, rng, 2.0, masked=False)
    assert np.abs(T.welch_t(X, lab)).max() > 4.5
    X, lab = T.traces(T.dom_registers, FIXED, 6000, rng, 2.0, masked=True)
    t = np.abs(T.welch_t(X, lab)).max()
    assert t < 4.5, f"DOM round leaks at first order in the simulation: max |t| = {t:.2f}"


def test_dom_with_a_zero_mask_leaks():
    """Sabotage: with share 1 forced to zero, share 0 is the plain state and the same test must see it."""
    rng = np.random.default_rng(5)
    unmasked = lambda S0, S1, R: T.dom_registers(S0 ^ S1, np.zeros_like(S1), R)
    X, lab = T.traces(unmasked, FIXED, 6000, rng, 2.0, masked=True)
    t = np.abs(T.welch_t(X, lab)).max()
    assert t > 4.5, f"the test cannot see an unmasked state in the DOM registers: max |t| = {t:.2f}"
