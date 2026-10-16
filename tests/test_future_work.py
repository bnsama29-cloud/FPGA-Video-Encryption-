"""Tests for future_work/: board driver (mock), board sender, jigsaw attack, figures, baselines."""
import shutil
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

from future_work.attacks.jigsaw_attack import accuracies, assemble, attack_frame, solve, tiles_of
from future_work.board.pynq_driver import (FRAME_CTR_HI, SESSION_ID_HI, MockBackend, SecureJpegIP,
                                           pixels_to_words)
from model import hw
from model.jpeg import receive_frame
from model.testimage import make_image

ROOT = Path(__file__).resolve().parents[1]
KEY = bytes(range(16))


def test_driver_on_mock_is_bit_exact_with_the_model():
    ip = SecureJpegIP(MockBackend())
    sid, img = 0xABCD_1234_5678, make_image(64, 48, "scene")
    ip.setup_session(KEY, sid, 50)
    for mode in range(5):
        ctr = (1 << 35) + mode
        scan, tag = ip.encode(img, mode, ctr)
        jpg = ip.build_jpeg(64, 48, mode, ctr, scan, tag)
        assert jpg == hw.encode_frame(img, 50, mode, KEY, ctr, sid)["jpeg"]
        assert receive_frame(jpg, KEY).ok
    writes = dict(ip.b.writes)
    assert writes[SESSION_ID_HI] == sid >> 32 and writes[FRAME_CTR_HI] == ((1 << 35) + 4) >> 32


def test_driver_rejects_what_the_rtl_cannot_do():
    ip = SecureJpegIP(MockBackend())
    ip.setup_session(KEY, 1)
    with pytest.raises(ValueError):
        ip.encode(make_image(40, 32), 2, 1)          # width not a multiple of 16
    with pytest.raises(ValueError):
        ip.encode(make_image(32, 32), 5, 1)          # E5 needs RTL restart markers


def test_pixel_word_order():
    px = np.array([[[1, 2, 3]]], np.uint8)
    assert pixels_to_words(px)[0] == 0x030201        # {pad, B, G, R}, R in bits [7:0]


def test_board_sender_with_mock_encodes_and_rekeys():
    from future_work.board.board_sender import make_board_sender
    from link import config
    cfg = config.load(overrides=["link.fb_out=47801", "link.sender_control=47802", "link.bus=[47809]",
                                 "sender.width=64", "sender.height=48", "defence.memory_file=''"])
    s = make_board_sender(cfg, mock=True)
    assert s.encoder.name == "board" and cfg["defence"]["max_mode"] == "E4"
    rgb = s.source.read()
    out = s.encoder.encode(rgb, s.ratchet.key, s.session_id, 1, "E2")
    assert receive_frame(out.jpeg, s.ratchet.key).ok
    s.ratchet.forward()
    out = s.encoder.encode(rgb, s.ratchet.key, s.session_id, 2, "E4")    # new key reloads registers
    assert receive_frame(out.jpeg, s.ratchet.key).mode == "E4"
    s.fsock.close()
    s.csock.close()


def test_jigsaw_solver_reassembles_plain_tiles():
    """Sanity check: without encryption the solver must work, or its E5 result means nothing."""
    from skimage import data
    rgb = cv2.resize(data.chelsea(), (320, 240), interpolation=cv2.INTER_AREA)
    tiles, rows, cols = tiles_of(rgb)
    order = np.random.default_rng(1).permutation(len(tiles))
    placement = solve(tiles[order], rows, cols)
    _, neighbours = accuracies(placement, list(order), rows, cols)
    assert neighbours > 0.8
    assert np.array_equal(assemble(tiles[order], placement, rows, cols).shape, rgb.shape)


def test_mst_solver_beats_greedy_on_plain_tiles():
    """GUIDE B9 gate: the stronger solver must beat the greedy one on unencrypted tiles before its E5
    numbers count (here on two photos where greedy struggles)."""
    from skimage import data
    from future_work.attacks.mst_jigsaw import solve as mst
    for img in (data.coffee(), data.rocket()):
        rgb = cv2.resize(img, (320, 240), interpolation=cv2.INTER_AREA)
        tiles, rows, cols = tiles_of(rgb)
        order = np.random.default_rng(1).permutation(len(tiles))
        _, nb_greedy = accuracies(solve(tiles[order], rows, cols), list(order), rows, cols)
        _, nb_mst = accuracies(mst(tiles[order], rows, cols), list(order), rows, cols)
        assert nb_mst > nb_greedy + 0.1 and nb_mst > 0.9, (nb_mst, nb_greedy)


def test_jigsaw_fails_on_e5():
    from skimage import data
    rgb = cv2.resize(data.chelsea(), (320, 240), interpolation=cv2.INTER_AREA)
    r = attack_frame(rgb, mode="E5")
    assert r["neighbour_accuracy"] < 0.1 and r["edge_corr_solved"] < 0.15
    assert r["edge_corr_perfect_placement"] > 0.25    # the sketch is there if positions were known


def test_format_compliance_all_modes():
    from future_work.figures import format_compliance as fc
    table = fc.main()
    for mode, row in table.items():
        for dec in ("Pillow", "OpenCV"):
            assert row[dec] is True, f"{dec} failed on {mode}"


def test_energy_table(tmp_path):
    csv = tmp_path / "p.csv"
    csv.write_text("method,mode,width,height,fps,power_w,idle_power_w,notes\n"
                   "ARM,E2,640,480,10,3.0,2.0,x\nFPGA,E2,640,480,100,2.5,2.0,y\n")
    subprocess.run([sys.executable, "-m", "future_work.baselines.energy_table", str(csv)], cwd=ROOT, check=True,
                   capture_output=True)
    md = csv.with_suffix(".md").read_text()
    assert "300.0" in md and "25.0" in md and "0.08x" in md


@pytest.mark.skipif(not shutil.which("iverilog"), reason="needs Icarus Verilog")
def test_block_design_wrapper_compiles(tmp_path):
    srcs = [ROOT / l.split()[2].replace("../../", "") for l in (ROOT / "vivado" / "xsim.prj").read_text().splitlines()
            if l.startswith("verilog") and "tb_secure" not in l]
    r = subprocess.run(["iverilog", "-g2005", "-o", str(tmp_path / "a.vvp"), "-I", str(ROOT / "rtl" / "include"),
                        "-s", "sjpeg_bd_top", *map(str, srcs), str(ROOT / "future_work" / "board" / "sjpeg_bd_top.v")],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_learned_attack_cache_depends_on_the_source():
    """Bug #13: the cache name ignored the video, so a second run reused the first run's frames."""
    pytest.importorskip("torch")
    from experiments import learned_attack as la
    args = ("E2", 100, (160, 128), 2, 75, "train")
    assert la.cache_path("clips/a.mp4", *args) != la.cache_path("clips/b.mp4", *args)
    assert la.cache_path("clips/a.mp4", *args) == la.cache_path("clips/a.mp4", *args)


def test_paper_tables_from_result_files(tmp_path):
    """Every table number must come from result files: build a tiny result tree and check the tables."""
    import json
    ep = lambda t, ttm: dict(type=t, rx_first_rejection_s=0.1, time_to_mitigate_s=ttm)
    for k, ttm in ((1, 0.4), (2, 0.6)):
        d = tmp_path / "sim_out" / "runs" / f"full_suite_threshold_rep{k}"
        d.mkdir(parents=True)
        (d / "summary.json").write_text(json.dumps(dict(
            episodes=[ep("bitflip", ttm)], mean_time_to_mitigate_s=ttm, false_alarm_windows=0, calm_windows=10,
            latency_ms_median=100, latency_ms_p95=150)))
    modes = {m: dict(edge_corr=0.3, ssim=0.5, cost=0.1, psnr=12.0) for m in ("E0", "E1", "E2", "E3", "E4", "E5")}
    (tmp_path / "sim_out" / "real" / "clipA").mkdir(parents=True)
    (tmp_path / "sim_out" / "real" / "clipA" / "mode_tradeoff.json").write_text(
        json.dumps(dict(source="/x/clipA.mp4", modes=modes)))
    subprocess.run([sys.executable, "-m", "future_work.figures.paper_tables", "--root", str(tmp_path)],
                   cwd=ROOT, check=True, capture_output=True)
    md = (tmp_path / "paper_tables.md").read_text()
    assert "| bitflip | 2 | 2/2 | 0.10 ± 0.00 | 0.50 ± 0.14 |" in md
    assert "| E5 | 0.300 | 0.100 |" in md and "clipA" in md
    assert "Not found" in md and "jigsaw.json" in md          # missing parts are listed, never invented


def test_first_contact_on_mock(tmp_path):
    """The board bring-up script: bit-exact gate + timing, run against the golden-model mock."""
    import json
    r = subprocess.run([sys.executable, "-m", "future_work.board.first_contact", "--mock", "--sizes", "32x16",
                        "--frames", "1", "--timing-frames", "1", "--out", str(tmp_path)],
                       cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    res = json.loads((tmp_path / "first_contact.json").read_text())
    assert res["all_bit_exact"] and len(res["exactness"]) == 5 and len(res["speed"]) == 5
    assert "NOT the FPGA" in (tmp_path / "first_contact.md").read_text()


def test_vivado_driver_dry_run():
    r = subprocess.run([sys.executable, "vivado/run_vivado_day.py", "--dry-run", "--blocks"], cwd=ROOT,
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    for step in ("xsim_run", "ooc_secure_jpeg_top", "ooc_keystream_gen", "block_design", "parse_reports"):
        assert step in r.stdout
    assert "vivado/vivado_ooc.tcl -tclargs secure_jpeg_top 10.0" in r.stdout
    assert "collect" in r.stdout


def test_vivado_overlay_fallback_and_collect(tmp_path, monkeypatch):
    """Run 3's overlay missed 100 MHz by 0.24 ns: the driver now retries at 90 and 80 MHz and stops at
    the first clock that meets timing; collect packs reports and summary but never the bitstream."""
    sys.path.insert(0, str(ROOT / "vivado"))
    import importlib
    import run_vivado_day as RV
    importlib.reload(RV)
    overlay = tmp_path / "future_work" / "board" / "overlay"
    overlay.mkdir(parents=True)
    monkeypatch.setattr(RV, "ROOT", tmp_path)
    monkeypatch.setattr(RV, "LOGS", tmp_path / "sim_build" / "vivado_logs")
    monkeypatch.setattr(RV, "RESULTS", [])
    wns = {100: "-0.240", 90: "0.512", 80: "1.900"}
    calls = []

    def fake_vivado(name, script, args="", check=None, dry=False):
        f = int(args.split()[0])
        calls.append(f)
        (overlay / "timing.txt").write_text(f"timing at {f}")
        (overlay / "secure_jpeg.bit").write_text("bitstream")
        RV.RESULTS.append((name, "PASS", 1.0, ""))
        return f"RESULT overlay fclk={f}MHz WNS={wns[f]}ns"
    monkeypatch.setattr(RV, "vivado", fake_vivado)
    a = type("A", (), dict(fclk=100, jobs=1, dry_run=False, no_fallback=False))()
    RV.step_bd(a)
    assert calls == [100, 90], calls
    assert (overlay / "timing_100MHz.txt").exists() and (overlay / "timing_90MHz.txt").exists()
    RV.step_collect(a)
    import zipfile
    zips = list(tmp_path.glob("vivado_results_*.zip"))
    assert len(zips) == 1
    names = zipfile.ZipFile(zips[0]).namelist()
    assert "summary.txt" in names and "overlay/timing_90MHz.txt" in names
    assert not any(n.endswith(".bit") for n in names), names
