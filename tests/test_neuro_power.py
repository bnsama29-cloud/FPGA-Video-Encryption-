"""N2 power with simulated activity: stimulus, testbench (Icarus), runner helpers and the energy table."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "hardware" / "vivado" / "neuro"))
import run_vivado_neuro as R  # noqa: E402

RTL = ["hardware/tb/neuro/tb_nv_power.v", "hardware/rtl/ascon_round.v", "hardware/rtl/ascon_aead128_core.v",
       "hardware/rtl/keystream_gen.v", "hardware/rtl/skid_buf.v"]


def vectors(out, level):
    p = subprocess.run([sys.executable, "experiments/neuro_power_vectors.py", "--level", str(level), "--ms", "2",
                        "--rate", "300", "--out", str(out)], cwd=ROOT, capture_output=True, text=True, timeout=300)
    assert p.returncode == 0, p.stdout + p.stderr
    return json.loads((out / "vectors.json").read_text())


@pytest.fixture(scope="module")
def tb(tmp_path_factory):
    if not shutil.which("iverilog"):
        pytest.skip("iverilog not installed")
    vvp = tmp_path_factory.mktemp("tb") / "tb.vvp"
    srcs = RTL + sorted(str(p.relative_to(ROOT)) for p in (ROOT / "hardware/rtl/neuro").glob("*.v"))
    p = subprocess.run(["iverilog", "-g2005", "-I", "hardware/rtl/include", "-o", str(vvp), *srcs], cwd=ROOT,
                       capture_output=True, text=True, timeout=300)
    assert p.returncode == 0, p.stderr
    return vvp


def sim(vvp, work):
    p = subprocess.run(["vvp", "-n", str(vvp)], cwd=work, capture_output=True, text=True, timeout=600)
    return R.sim_result(p.stdout), p.stdout


@pytest.mark.parametrize("level", [2, 3])
def test_power_testbench_is_bit_exact_and_counts_events(tb, tmp_path, level):
    info = vectors(tmp_path, level)
    r, out = sim(tb, tmp_path)
    assert r is not None, out[-2000:]
    assert r["mismatches"] == 0, out[-2000:]
    assert (r["words"], r["events"]) == (info["words_out"], info["events"]), (r, info)
    assert r["cycles"] > 0


def test_power_testbench_catches_a_wrong_word(tb, tmp_path):
    vectors(tmp_path, 2)
    lines = (tmp_path / "expect.hex").read_text().splitlines()
    k = len(lines) // 2
    lines[k] = f"{int(lines[k], 16) ^ 1:09x}"                  # one bit of one expected word
    (tmp_path / "expect.hex").write_text("\n".join(lines) + "\n")
    r, out = sim(tb, tmp_path)
    assert r["mismatches"] == 1 and f"first mismatch at output word {k}:" in out, out[-1500:]


def test_sim_result_and_power_jobs():
    assert R.sim_result("x\nRESULT nv_power mismatches=0 words=9 events=4 cycles=120\n") == \
        {"mismatches": 0, "words": 9, "events": 4, "cycles": 120}
    assert R.sim_result("ERROR\n") is None
    assert [t for t, _ in R.power_jobs(None)] == ["dense_v2", "dense_v3"]
    jobs = dict(R.power_jobs(Path("r.npy")))
    assert jobs["real_v3"][-2:] == ["--npy", "r.npy"] and "--npy" not in jobs["dense_v2"]


def test_energy_per_event_in_the_table(tmp_path):
    from test_vivado_reports import UTIL, TIMING, POWER            # total 0.152 W, dynamic 0.047 W
    b = tmp_path / "vivado_neuro_nv_top_u2_maxw1280_maxh720"
    b.mkdir()
    for name, text in (("utilization.txt", UTIL), ("timing.txt", TIMING), ("power.txt", POWER),
                       ("power_saif_dense_v2.txt", POWER)):
        (b / name).write_text(text)
    w = tmp_path / "nv_power_dense_v2"
    w.mkdir()
    (w / "sim_result.json").write_text(json.dumps({"mismatches": 0, "words": 10, "events": 1000, "cycles": 2000}))
    (w / "vectors.json").write_text(json.dumps({"level": 2, "source": "synthetic"}))
    p = subprocess.run([sys.executable, "experiments/neuro_hw_tables.py", "--dir", str(tmp_path), "--out",
                        str(tmp_path), "--overlay", str(tmp_path / "none")], cwd=ROOT, capture_output=True,
                       text=True, timeout=120)
    assert p.returncode == 0, p.stdout + p.stderr
    e = json.loads((tmp_path / "hw_tables.json").read_text())["builds"][0]["energy"][0]
    # 0.152 W x 2000 clk x 10 ns / 1000 events = 3.04 nJ; dynamic 0.047 -> 0.94 nJ
    assert (round(e["nj_per_event"], 6), round(e["dyn_nj_per_event"], 6)) == (3.04, 0.94), e
    assert "| dense_v2 | 1000 | 2000 | 0.500 |" in (tmp_path / "hw_tables.md").read_text()
