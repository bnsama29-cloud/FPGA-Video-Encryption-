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
