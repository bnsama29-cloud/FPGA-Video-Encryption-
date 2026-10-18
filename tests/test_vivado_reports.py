"""vivado/run_vivado_day.py parse on report text in Vivado's format (we have no Vivado here)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "vivado"))
import run_vivado_day as pr  # noqa: E402

UTIL = """
1. Slice Logic
--------------

+----------------------------+------+-------+------------+-----------+-------+
|          Site Type         | Used | Fixed | Prohibited | Available | Util% |
+----------------------------+------+-------+------------+-----------+-------+
| Slice LUTs                 | 5321 |     0 |          0 |     53200 | 10.00 |
|   LUT as Logic             | 5100 |     0 |          0 |     53200 |  9.59 |
| Slice Registers            | 4012 |     0 |          0 |    106400 |  3.77 |
|   Register as Flip Flop    | 4012 |     0 |          0 |    106400 |  3.77 |
+----------------------------+------+-------+------------+-----------+-------+

3. Memory
---------
+-------------------+------+-------+------------+-----------+-------+
|     Site Type     | Used | Fixed | Prohibited | Available | Util% |
+-------------------+------+-------+------------+-----------+-------+
| Block RAM Tile    |  1.5 |     0 |          0 |       140 |  1.07 |
+-------------------+------+-------+------------+-----------+-------+

4. DSP
------
+----------------+------+-------+------------+-----------+-------+
|    Site Type   | Used | Fixed | Prohibited | Available | Util% |
+----------------+------+-------+------------+-----------+-------+
| DSPs           |    4 |     0 |          0 |       220 |  1.82 |
|   DSP48E1 only |    4 |       |            |           |       |
+----------------+------+-------+------------+-----------+-------+
"""

TIMING = """
------------------------------------------------------------------------------------------------
| Design Timing Summary
| ---------------------
------------------------------------------------------------------------------------------------

    WNS(ns)      TNS(ns)  TNS Failing Endpoints  TNS Total Endpoints      WHS(ns)      THS(ns)  THS Failing Endpoints  THS Total Endpoints     WPWS(ns)     TPWS(ns)  TPWS Failing Endpoints  TPWS Total Endpoints
    -------      -------  ---------------------  -------------------      -------      -------  ---------------------  -------------------     --------     --------  ----------------------  --------------------
      1.234        0.000                      0                 9876        0.045        0.000                      0                 9876        4.020        0.000                       0                  4100


All user specified timing constraints are met.

Clock  Waveform(ns)       Period(ns)      Frequency(MHz)
-----  ------------       ----------      --------------
clk    {0.000 5.000}      10.000          100.000
"""

POWER = """
+--------------------------+--------------+
| Total On-Chip Power (W)  | 0.152        |
| Design Power Budget (W)  | Unspecified* |
| Dynamic (W)              | 0.047        |
| Device Static (W)        | 0.105        |
| Confidence Level         | Low          |
+--------------------------+--------------+
"""

HIER = """
+---------------------+-----------------+------------+------------+---------+------+------+--------+--------+--------------+
|       Instance      |      Module     | Total LUTs | Logic LUTs | LUTRAMs | SRLs |  FFs | RAMB36 | RAMB18 | DSP48 Blocks |
+---------------------+-----------------+------------+------------+---------+------+------+--------+--------+--------------+
| secure_jpeg_top     |           (top) |       5321 |       5100 |     200 |   21 | 4012 |      1 |      1 |            4 |
|   u_ks              |   keystream_gen |       1350 |       1350 |       0 |    0 |  700 |      0 |      0 |            0 |
|     u_core          | ascon_aead128_c |       1200 |       1200 |       0 |    0 |  650 |      0 |      0 |            0 |
|       u_round       |     ascon_round |        900 |        900 |       0 |    0 |    0 |      0 |      0 |            0 |
|   u_dct             |          dct8x8 |        800 |        700 |     100 |    0 |  900 |      0 |      1 |            4 |
+---------------------+-----------------+------------+------------+---------+------+------+--------+--------+--------------+
"""


def test_parse_each_report():
    u = pr.parse_utilization(UTIL)
    assert u["lut"] == (5321, 53200, 10.0) and u["ff"][0] == 4012 and u["bram"][0] == 1.5 and u["dsp"][0] == 4
    t = pr.parse_timing(TIMING)
    assert t == dict(wns=1.234, tns=0.0, whs=0.045, met=True)
    assert pr.parse_power(POWER) == dict(total=0.152, dynamic=0.047, static=0.105, confidence="Low")
    h = pr.parse_hier(HIER)
    assert [(lvl, inst) for lvl, inst, *_ in h] == [(0, "secure_jpeg_top"), (1, "u_ks"), (2, "u_core"), (1, "u_dct")]
    assert h[0][3:] == (5321, 4012, 1.5, 4)


def test_folder_to_table(tmp_path):
    d = tmp_path / "vivado_secure_jpeg_top"
    d.mkdir()
    for name, text in (("utilization.txt", UTIL), ("timing.txt", TIMING), ("power.txt", POWER),
                       ("utilization_hier.txt", HIER)):
        (d / name).write_text(text)
    r = pr.read_folder(d)
    assert r["period"] == 10.0 and r["fmax_mhz"] == round(1000 / (10 - 1.234), 1) and not r["missing"]
    md = pr.tables([r])
    assert "| secure_jpeg_top | 5321 (10.0%) | 4012 (3.8%) | 1.5 (1.1%) | 4 (1.8%) | 100 | 1.234 | yes |" in md
    assert "Resource breakdown" in md and "keystream_gen" in md


def test_missing_reports_are_reported_not_guessed(tmp_path):
    d = tmp_path / "vivado_keystream_gen_8.0ns"
    d.mkdir()
    (d / "timing.txt").write_text(TIMING.replace("1.234", "-0.500").replace(
        "All user specified timing constraints are met.", "Timing constraints are not met."))
    r = pr.read_folder(d)
    assert r["period"] == 10.0                      # the clock table in timing.txt wins over the folder name
    assert r["timing"]["met"] is False and set(r["missing"]) == {"utilization.txt", "power.txt"}
    md = pr.tables([r])
    assert "| NO |" in md and "missing utilization.txt, power.txt" in md and "| ? (" not in md


POWER_SAIF = POWER.replace("0.152", "0.139").replace("0.047", "0.034").replace("| Low ", "| Medium ") + """
1.3 Confidence Level
--------------------

+-----------------------------+------------+--------------------------------------------------------+------------------------------------------------+
| User Input Data             | Confidence | Details                                                | Action                                         |
+-----------------------------+------------+--------------------------------------------------------+------------------------------------------------+
| Design implementation state | High       | Design is routed                                       |                                                |
| Clock nodes activity        | High       | User specified more than 95% of clocks                 |                                                |
| I/O nodes activity          | High       | User specified more than 95% of inputs                 |                                                |
| Internal nodes activity     | Medium     | User specified more than 25% of internal nodes         |                                                |
+-----------------------------+------------+--------------------------------------------------------+------------------------------------------------+
"""


def test_power_with_simulated_activity(tmp_path):
    """--steps power writes power_saif_<run>.txt next to power.txt; parse puts each run in its own
    table, next to the vectorless number, with the confidence Vivado gave the activity data."""
    d = tmp_path / "vivado_secure_jpeg_top"
    d.mkdir()
    for name, text in (("utilization.txt", UTIL), ("timing.txt", TIMING), ("power.txt", POWER),
                       ("power_saif_v2_E2.txt", POWER_SAIF), ("power_saif_v2_E4.txt", POWER_SAIF)):
        (d / name).write_text(text)
    p = pr.parse_power(POWER_SAIF)
    assert p["dynamic"] == 0.034 and p["confidence"] == "Medium" and p["internal"] == "Medium"
    assert "25% of internal nodes" in p["internal_detail"]
    r = pr.read_folder(d)
    assert sorted(r["power_saif"]) == ["v2_E2", "v2_E4"]
    md = pr.tables([r])
    assert "Power with simulated switching activity" in md
    assert "| secure_jpeg_top | v2_E2 | 0.139 | 0.034 | 0.047 | Medium | Medium: User specified more than 25% of internal nodes |" in md


def test_power_step_dry_run():
    import subprocess
    r = subprocess.run([sys.executable, "vivado/run_vivado_day.py", "--steps", "power", "--dry-run"], cwd=ROOT,
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "vectors --v3 --scene 320x240 --modes 5 --out vivado/xsim_power_v3_E5" in r.stdout
    assert "run_xsim.sh saif xsim_power_v2_E4" in r.stdout or "run_xsim.bat saif xsim_power_v2_E4" in r.stdout
    assert ("power_saif.tcl -tclargs sim_build/vivado_secure_jpeg_top/routed.dcp "
            "vivado/xsim_power_v2_E0/activity.saif tb_secure_jpeg_top/dut "
            "sim_build/vivado_secure_jpeg_top/power_saif_v2_E0.txt") in r.stdout
