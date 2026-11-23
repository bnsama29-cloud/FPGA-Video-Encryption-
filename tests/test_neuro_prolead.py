"""experiments/neuro_prolead.py: log parsing and the PROLEAD configuration (PROLEAD itself is not run in CI)."""
import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("neuro_prolead", Path(__file__).resolve().parents[1]
                                              / "experiments" / "neuro_prolead.py")
P = importlib.util.module_from_spec(spec)
spec.loader.exec_module(P)

OK = ("[t] |   0-00:00:45 |   0TB    0GB 035MB |       1920000 / 79304 |   y_s0[3](4) |   1.153811 |    OKAY |\n"
      "[t] |   0-00:00:49 |   0TB    0GB 035MB |       2048000 / 79304 |  _002_[1](4) |   1.252004 |    OKAY |\n")
LEAK = ("[t] |   0-00:00:03 |   0TB    0GB 035MB |        128000 / 51200 |  _002_[0](3) |        inf | LEAKAGE |\n"
        "[t] |   0-00:00:06 |   0TB    0GB 035MB |        256000 / 51200 |  _002_[0](3) |   2.000000 |    OKAY |\n")


def test_parse_okay_reports_the_last_step():
    r = P.parse(OK)
    assert (r["verdict"], r["simulations"], r["probe"]) == ("OKAY", 2048000, "_002_[1](4)"), r
    assert r["max_neg_log10_p_all_steps"] == pytest.approx(1.252004), r


def test_parse_any_leaky_step_is_leakage():
    r = P.parse(LEAK)
    assert (r["verdict"], r["simulations"], r["probe"]) == ("LEAKAGE", 128000, "_002_[0](3)"), r


def test_parse_rejects_a_log_without_results():
    with pytest.raises(RuntimeError):
        P.parse("PROLEAD: error\n")


def test_config_matches_the_designs():
    assert P.config(7, 2048000)["simulation"]["always_random_inputs"] == ["r[6:0]"]
    assert P.config(5, 1000)["simulation"]["number_of_simulations_per_step"] == 1000
    rtl = P.VARIANTS["independent"][0].read_text()
    assert "input  wire [6:0] r" in rtl and "input  wire [4:0] r" in P.TEXTBOOK
