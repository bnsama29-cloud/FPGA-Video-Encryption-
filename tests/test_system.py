"""Tests for system/: board driver (mock), board sender, jigsaw attack, figures, baselines."""
import shutil
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

from system.attacks.jigsaw_attack import accuracies, assemble, attack_frame, solve, tiles_of
from system.board.pynq_driver import (FRAME_CTR_HI, SESSION_ID_HI, MockBackend, SecureJpegIP,
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


def test_driver_on_mock_v3_lane_overlay_is_bit_exact_with_the_model():
    """secure_jpeg_lanes.bit (contract v3): the driver detects it from VERSION and frames match
    model/hw.py :: encode_frame_v3 and pass the receiver."""
    ip = SecureJpegIP(MockBackend(contract=3, lanes=2))
    assert (ip.contract, ip.lanes) == (3, 2)
    sid, img = 0xABCD_1234_5678, make_image(64, 80, "scene")
    ip.setup_session(KEY, sid, 75)
    for mode in range(5):
        scan, tag = ip.encode(img, mode, 40 + mode)
        jpg = ip.build_jpeg(64, 80, mode, 40 + mode, scan, tag)
        assert jpg == hw.encode_frame_v3(img, 75, mode, KEY, 40 + mode, sid)["jpeg"]
        assert receive_frame(jpg, KEY).ok


def test_driver_rejects_an_unknown_bitstream():
    class Wrong(MockBackend):
        def read(self, addr):
            return 0x12345678 if addr == 0x08 else super().read(addr)
    with pytest.raises(RuntimeError):
        SecureJpegIP(Wrong())


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
    from system.board.board_sender import make_board_sender
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
    """Jigsaw gate: the stronger solver must beat the greedy one on unencrypted tiles before its E5
    numbers count (here on two photos where greedy struggles)."""
    from skimage import data
    from system.attacks.mst_jigsaw import solve as mst
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
    from system.figures import format_compliance as fc
    table = fc.main()
    for mode, row in table.items():
        for dec in ("Pillow", "OpenCV"):
            assert row[dec] is True, f"{dec} failed on {mode}"


def test_energy_table(tmp_path):
    csv = tmp_path / "p.csv"
    csv.write_text("method,mode,width,height,fps,power_w,idle_power_w,notes\n"
                   "ARM,E2,640,480,10,3.0,2.0,x\nFPGA,E2,640,480,100,2.5,2.0,y\n")
    subprocess.run([sys.executable, "-m", "system.baselines.energy_table", str(csv)], cwd=ROOT, check=True,
                   capture_output=True)
    md = csv.with_suffix(".md").read_text()
    assert "300.0" in md and "25.0" in md and "0.08x" in md


@pytest.mark.skipif(not shutil.which("iverilog"), reason="needs Icarus Verilog")
def test_block_design_wrapper_compiles(tmp_path):
    srcs = [ROOT / l.split()[2].replace("../../", "") for l in (ROOT / "vivado" / "xsim.prj").read_text().splitlines()
            if l.startswith("verilog") and "tb_secure" not in l]
    r = subprocess.run(["iverilog", "-g2005", "-o", str(tmp_path / "a.vvp"), "-I", str(ROOT / "rtl" / "include"),
                        "-s", "sjpeg_bd_top", *map(str, srcs), str(ROOT / "system" / "board" / "sjpeg_bd_top.v")],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_block_design_connects_both_dma_masters_to_ddr():
    """Bug #32: the second AXI automation call targeted ps7/S_AXI_HP0, which the first call had already
    connected, so M_AXI_S2MM stayed unconnected; on the board the receive DMA never wrote and hung."""
    tcl = (ROOT / "system" / "board" / "block_design.tcl").read_text()
    calls = [l.split() for l in tcl.splitlines() if l.startswith("axi_auto ")]
    targets = [c[3] for c in calls]
    assert len(targets) == len(set(targets)), f"two automation calls share a target: {targets}"
    assert "dma/M_AXI_S2MM" in targets or "dma/M_AXI_MM2S" in targets
    assert all(f"dma/Data_{ch}" in tcl for ch in ("MM2S", "S2MM")), "the address-segment guard is missing"


def test_pynq_backend_dma_wait_times_out_instead_of_hanging():
    """Bug #32: pynq's channel.wait() blocks forever when a DMA never finishes."""
    from system.board import pynq_driver as pd

    class Channel:
        def __init__(self, idle):
            self.idle = idle

        def wait(self):
            pass

    class Regs:
        def read(self, addr):
            return 0

    b = object.__new__(pd.PynqBackend)
    b.ip, b.dma = Regs(), Regs()
    b._wait(Channel(True), "send", 0.05)                       # finished: returns
    with pytest.raises(TimeoutError, match="receive"):
        b._wait(Channel(False), "receive", 0.05)


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
    subprocess.run([sys.executable, "-m", "system.figures.paper_tables", "--root", str(tmp_path)],
                   cwd=ROOT, check=True, capture_output=True)
    md = (tmp_path / "paper_tables.md").read_text()
    assert "| bitflip | 2 | 2/2 | 0.10 ± 0.00 | 0.50 ± 0.14 |" in md
    assert "| E5 | 0.300 | 0.100 |" in md and "clipA" in md
    assert "Not found" in md and "jigsaw.json" in md          # missing parts are listed, never invented


def test_first_contact_on_mock(tmp_path):
    """The board bring-up script: bit-exact gate + timing, run against the golden-model mock."""
    import json
    r = subprocess.run([sys.executable, "-m", "system.board.first_contact", "--mock", "--sizes", "32x16",
                        "--frames", "1", "--timing-frames", "1", "--out", str(tmp_path)],
                       cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    res = json.loads((tmp_path / "first_contact.json").read_text())
    assert res["all_bit_exact"] and len(res["exactness"]) == 5 and len(res["speed"]) == 5
    assert "NOT the FPGA" in (tmp_path / "first_contact.md").read_text()


def test_first_contact_checks_the_lane_bitstream_against_contract_v3(tmp_path):
    """The lane overlay (secure_jpeg_lanes.bit) must be compared with encode_frame_v3, not the v2 bytes:
    before 17 Oct the gate used encode_frame for every bitstream and would have failed a correct board."""
    import json
    from system.board.first_contact import expected_jpeg
    r = subprocess.run([sys.executable, "-m", "system.board.first_contact", "--mock-lanes", "2", "--sizes",
                        "32x32", "--frames", "1", "--timing-frames", "1", "--out", str(tmp_path)],
                       cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "contract v3, 2 lanes" in r.stdout
    assert json.loads((tmp_path / "first_contact.json").read_text())["all_bit_exact"]
    ip = SecureJpegIP(MockBackend(contract=3, lanes=2))
    rgb = make_image(32, 32, "scene")
    assert expected_jpeg(ip, rgb, 75, 2, 1) != hw.encode_frame(rgb, 75, 2, bytes(range(16)), 1, 0x5EC0_1234_5678)["jpeg"]


def test_board_e5_path_on_an_emulated_e5_bitstream(tmp_path):
    """E5 on the board (INTERFACES.md §8.6): a lane bitstream that reports VERSION bit 7 runs mode 5; the
    gate compares the fabric output + the ARM's shuffle with the model; without bit 7 the driver refuses
    mode 5 and the board sender caps the policy at E4. The fast ARM shuffle (C order, bytes.find) must give
    the same bytes as model/hw.py."""
    import json
    from system.board import fast_e5
    from system.board.board_sender import make_board_sender
    from link import config
    r = subprocess.run([sys.executable, "-m", "system.board.first_contact", "--mock-lanes", "2", "--mock-e5",
                        "--sizes", "32x32", "--frames", "1", "--timing-frames", "1", "--out", str(tmp_path)],
                       cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    res = json.loads((tmp_path / "first_contact.json").read_text())
    assert res["all_bit_exact"] and {x["mode"] for x in res["exactness"]} == set(range(6)), res["exactness"]
    no_e5 = SecureJpegIP(MockBackend(contract=3, lanes=2))
    no_e5.setup_session(bytes(16), 1)
    with pytest.raises(ValueError):
        no_e5.encode(make_image(32, 32, "scene"), 5, 1)
    cfg1 = config.load(None, []); cfg1["defence"]["max_mode"] = "E5"
    make_board_sender(cfg1, mock_lanes=2)
    assert cfg1["defence"]["max_mode"] == "E4"
    cfg2 = config.load(None, []); cfg2["defence"]["max_mode"] = "E5"
    make_board_sender(cfg2, mock_lanes=2, mock_e5=True)
    assert cfg2["defence"]["max_mode"] == "E5"
    key = bytes(range(16))
    for n, (w, h) in enumerate([(16, 16), (64, 48), (48, 96)]):
        raw = hw.encode_frame_v3(make_image(w, h, "noise", seed=n), 75, 5, key, 1000 + n, 42)["jpeg"]
        assert fast_e5.arm_shuffle(raw, key, 42, 1000 + n) == hw.arm_shuffle(raw, key, 42, 1000 + n)


def test_load_pixels_into_gives_the_same_words():
    """The zero-copy pixel path of the driver writes the same uint32 words as pixels_to_words, into a
    larger buffer, for odd strides too (a cropped, non-contiguous frame)."""
    from system.board.pynq_driver import load_pixels_into
    rgb = np.random.default_rng(3).integers(0, 256, (40, 70, 3), dtype=np.uint8)[4:36, 3:67]
    buf = np.zeros(4000, np.uint32)
    n = load_pixels_into(buf, rgb)
    assert n == 32 * 64
    exp = pixels_to_words(rgb)
    bad = np.flatnonzero(buf[:n] != exp)
    assert bad.size == 0, f"word {bad[0]}: got {buf[bad[0]]:#x} expected {exp[bad[0]]:#x}"
    assert not buf[n:].any()


def test_zero_copy_pixel_buffer_gives_the_same_frame():
    """A frame written into ip.pixel_buffer() (the DMA buffer view a camera could fill) encodes to the
    same scan and tag as the same frame passed as an array."""
    ip = SecureJpegIP(MockBackend(contract=3, lanes=2, e5=True))
    ip.setup_session(bytes(16), 1)
    rgb = make_image(64, 48, "scene")
    view = ip.pixel_buffer(64, 48)
    np.copyto(view, rgb)
    for mode in (0, 2, 5):
        assert ip.encode(view, mode, 9) == ip.encode(rgb, mode, 9), f"E{mode}"


def test_driver_reports_time_breakdown_and_no_counter_on_mock():
    ip = SecureJpegIP(MockBackend(contract=3, lanes=2))
    ip.setup_session(bytes(16), 1)
    ip.encode(make_image(32, 32, "scene"), 2, 1)
    t = ip.last_timing
    assert t["load_ms"] >= 0 and t["dma_ms"] >= 0 and t["fabric_ms"] is None and t["cycles"] is None


def test_native_e5_shuffle_matches_model_on_adversarial_scans():
    """The one-call C shuffle (native/e5_order.c :: e5_shuffle) splits exactly like model/hw.py ::
    split_segments, also for scans full of 0xFF, stuffed 0xFF00, 0xFF 0xFF 0xD0 and a trailing 0xFF."""
    import random
    from system.board import fast_e5
    if not fast_e5.native_available():
        pytest.skip("no C compiler")
    key, rnd, checked = bytes(range(16)), random.Random(5), 0
    head, _ = hw.split_scan(hw.encode_frame_v3(make_image(16, 16, "scene"), 75, 5, key, 1, 42)["jpeg"])
    for t in range(400):
        body = bytes(rnd.choice([0xFF, 0xD0, 0xD7, 0xD8, 0x00, 0x12]) for _ in range(rnd.randint(0, 300)))
        jpeg = head + body + b"\xFF\xD9"
        exp, got = hw.arm_shuffle(jpeg, key, 7, t), fast_e5.arm_shuffle(jpeg, key, 7, t)
        assert got == exp, f"case {t}: scan {body.hex()}: got {got[len(head):].hex()} expected {exp[len(head):].hex()}"
        checked += 1
    assert checked == 400


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
    overlay = tmp_path / "system" / "board" / "overlay"
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


def test_scenario_board_command_matches_the_run_ports():
    """experiments/scenario.py --external-sender prints the board_sender command; its ports
    must be the ones the scenario's channel and logger use, or the board streams into nothing."""
    sys.path.insert(0, str(ROOT / "experiments"))
    import scenario
    cmd = scenario.board_command(47300, "threshold", "10.0.0.5")
    for part in ("link.host=10.0.0.5", "link.video_in=47300", "link.fb_out=47303", "link.sender_control=47305",
                 "link.bus=[47310]", "sender.policy=threshold", "system.board.board_sender"):
        assert part in cmd, part


def test_scenario_board_command_carries_the_demo_key():
    """A run with a fresh key (scripts/demo_key.py, --set keys.master=...) must print a board command with
    the same key, or every frame from the board fails its tag; other overrides stay on the laptop."""
    sys.path.insert(0, str(ROOT / "experiments"))
    import scenario
    cmd = scenario.board_command(47300, "threshold", "10.0.0.5",
                                 extra_sets=["keys.master=0f" * 1 + "e" * 30, "channel.loss=0.05"])
    assert "--set keys.master=0f" + "e" * 30 in cmd
    assert "channel.loss" not in cmd


def test_driver_yuyv_bitstream():
    """A bitstream built for camera-native YUYV input (PIXFMT = 1, VERSION bit 6): the driver sends the
    camera's bytes as they are (2 per pixel), converts an RGB frame itself, and both give the model's bytes."""
    from system.board.pynq_driver import MockBackend, SecureJpegIP, contract_of, has_yuyv
    from model import hw
    from model.testimage import make_image
    assert contract_of(0x5EC003C4) == (3, 4) and has_yuyv(0x5EC003C4) and not has_yuyv(0x5EC00384)
    ip = SecureJpegIP(MockBackend(contract=3, lanes=4, e5=True, yuyv=True))
    assert ip.pixfmt == "yuyv" and ip.lanes == 4 and ip.e5
    key, sid = bytes(range(16)), 0x1234_5678_9ABC
    ip.setup_session(key, sid, 75)
    img = make_image(48, 32, "scene")
    yuyv = hw.rgb_to_yuyv(img)
    for mode in (2, 5):
        ref = hw.encode_frame_v3(yuyv, 75, mode, key, 7, sid, pixfmt="yuyv")
        assert ip.encode(yuyv, mode, 7) == (ref["scan"], ref["tag"]), f"E{mode}: YUYV frame"
        assert ip.encode(img, mode, 7) == (ref["scan"], ref["tag"]), f"E{mode}: RGB frame converted on the ARM"
    buf = ip.pixel_buffer(48, 32)
    assert buf.shape == (32, 96)
    buf[...] = yuyv                                    # zero-copy: the camera writes into the DMA buffer
    assert ip.encode(buf, 2, 8)[0] == hw.encode_frame_v3(yuyv, 75, 2, key, 8, sid, pixfmt="yuyv")["scan"]
    rgb_ip = SecureJpegIP(MockBackend(contract=3, lanes=2, e5=True))
    rgb_ip.setup_session(key, sid, 75)
    import pytest
    with pytest.raises(ValueError):
        rgb_ip.encode(yuyv, 2, 1)                      # a YUYV frame needs a YUYV bitstream
