"""The encoder on the processing system (future_work/arm/native/sjpeg_sw.c) must give the same bytes as
the golden model (model/hw.py), and therefore as the programmable logic, in every mode and contract,
for any number of threads. Also: the full-file Ascon baseline matches model/ascon.py, the A3 script runs."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from model import ascon, hw
from model.testimage import make_image

sw = pytest.importorskip("future_work.arm.sw_encoder")
ROOT = Path(__file__).resolve().parents[1]
KEY, SID = bytes(range(16)), 0x5EC0_1234_5678

pytestmark = pytest.mark.skipif(not sw.available(), reason="no C compiler")


def _recips(q):
    luma, chroma = hw.quality_tables(q)
    return [hw.reciprocal(v) for v in luma + chroma]


def _first_diff(a, b):
    return next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))


@pytest.mark.parametrize("w,h,kind,q", [(16, 16, "scene", 75), (64, 48, "noise", 90), (48, 96, "scene", 30),
                                        (160, 128, "noise", 75)])
def test_ps_encoder_bit_exact_with_model(w, h, kind, q):
    rgb, rec = make_image(w, h, kind), _recips(q)
    ctr, sid = (1 << 40) + 5, (1 << 63) + 9                     # high words exercised
    for mode in range(5):
        ref = hw.encode_frame(rgb, q, mode, KEY, ctr, sid)
        scan, tag = sw.encode_scan(rgb, rec, mode, KEY, sid, ctr, contract=2)
        assert scan == ref["scan"], f"v2 E{mode} {w}x{h}: first scan mismatch at byte {_first_diff(scan, ref['scan'])}"
        assert tag == ref["tag"], f"v2 E{mode} {w}x{h}: tag {tag.hex()} expected {ref['tag'].hex()}"
    for mode in range(6):
        ref = hw.encode_frame_v3(rgb, q, mode, KEY, ctr, sid)
        for th in (1, 2, 3):
            scan, tag = sw.encode_scan(rgb, rec, mode, KEY, sid, ctr, contract=3, threads=th)
            assert scan == ref["scan"], (f"v3 E{mode} {w}x{h} {th} threads: first scan mismatch at byte "
                                         f"{_first_diff(scan, ref['scan'])}")
            assert tag == ref["tag"], f"v3 E{mode} {w}x{h} {th} threads: tag differs"


def test_software_backend_through_the_board_driver():
    """SecureJpegIP on the PS-only backend: same JPEG as the model incl. the E5 shuffle."""
    from future_work.board.pynq_driver import SecureJpegIP
    ip = SecureJpegIP(sw.SoftwareBackend(contract=3, lanes=2, e5=True, threads=2))
    ip.setup_session(KEY, SID, 75)
    rgb = make_image(64, 48, "scene")
    for mode in range(6):
        scan, tag = ip.encode(rgb, mode, 77)
        got = ip.build_jpeg(64, 48, mode, 77, scan, tag)
        exp = hw.encode_frame_v3(rgb, 75, mode, KEY, 77, SID)["jpeg"]
        if mode == 5:
            exp = hw.arm_shuffle(exp, KEY, SID, 77)
        assert got == exp, f"E{mode}: first mismatch at byte {_first_diff(got, exp)}"


@pytest.mark.parametrize("n", [0, 1, 15, 16, 17, 33, 1000])
def test_full_file_ascon_matches_model(n):
    data = bytes((7 * i) & 0xFF for i in range(n))
    nonce = ascon.make_nonce(SID, 3, 0)
    assert sw.ascon_encrypt(KEY, nonce, data) == ascon.encrypt(KEY, nonce, b"", data)


def test_arm_baseline_script_runs(tmp_path):
    r = subprocess.run([sys.executable, "-m", "future_work.arm.arm_baseline", "--sizes", "32x32", "--frames", "1",
                        "--out", str(tmp_path)], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    d = json.loads((tmp_path / "arm_baseline.json").read_text())
    assert any(v["kind"] == "ps_ours" for v in d["sizes"]["32x32"].values())
