"""Journal-version programs (docs/JOURNAL_RUNBOOK.md): the parts that run without a board, Vivado or GPU.

Each test runs the program's core on a tiny input and checks a property the result table relies on.
Failures name the first wrong value (what, got, expected)."""
import random
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))
sys.path.insert(0, str(ROOT / "hardware" / "vivado"))
sys.path.insert(0, str(ROOT / "software" / "scripts"))

from model.testimage import make_image   # noqa: E402


def test_size_overhead_payload_equal_for_e1_to_e4():
    import size_overhead as so
    per = [so.frame_sizes(make_image(64, 48, "scene"), 75, k + 1) for k in range(2)]
    s = so.summarise(per)
    for m in ("v2 E1", "v2 E2", "v2 E3", "v2 E4", "v3 E1", "v3 E2", "v3 E3", "v3 E4"):
        assert s[m]["payload_equal_share"] == 1.0, f"{m}: payload length differs from its unencrypted stream"
    assert s["plain"]["frame_over_pct"] == 0.0
    pad = so.padding_cost([1000, 1500, 1200])
    assert pad["none"]["over_pct"] == 0.0, f"padding 'none' added {pad['none']['over_pct']} %"
    for pol, r in pad.items():
        assert r["mean_bytes"] >= 1233.33 - 1e-6, f"{pol}: padded frames smaller than the originals"


def test_fault_pre_tag_sites():
    import fault_pre_tag as fp
    from model.jpeg import analyse_frame
    an = analyse_frame(make_image(64, 48, "scene"), 75)
    rng = random.Random(3)
    res = {s: [fp.trial(an, "E2", 1 << 32, s, rng) for _ in range(4)] for s in ("coefficient", "after_tag")}
    for k, (ok, why) in enumerate(res["after_tag"]):
        assert not ok and why == "tag-mismatch", f"after_tag fault {k}: got ({ok}, {why}), expected rejection"
    for k, (ok, _) in enumerate(res["coefficient"]):
        assert ok, f"coefficient fault {k} was rejected: the tag is computed over the faulty data, so it verifies"
    s = fp.summarise(res)
    assert s["after_tag"]["rejected_tag"] == 4 and s["coefficient"]["accepted_share"] == 1.0


def test_rekey_analysis():
    import rekey_load as rk
    ev = [dict(src="receiver", kind="frame", t=0.1 * i, verdict="ok", ctr=i, epoch=0) for i in range(1, 50)]
    ev.append(dict(src="sender", kind="rekey", t=4.99, epoch=1))
    for i in range(50, 80):
        if i == 52:
            continue                                         # one frame lost
        ev.append(dict(src="receiver", kind="frame", t=0.1 * i + 0.05, verdict="ok", ctr=i, epoch=1))
    ev.append(dict(src="receiver", kind="frame", t=5.06, verdict="stale-epoch", ctr=49, epoch=0))
    per, s = rk.analyse_rekeys(ev)
    assert len(per) == 1 and per[0]["adopted"], f"rekey not adopted: {per}"
    assert per[0]["first_new_epoch_ms"] == pytest.approx(60.0, abs=0.2), per[0]
    assert per[0]["missing_by_counter"] == 1, f"missing: got {per[0]['missing_by_counter']}, expected 1"
    assert s["rekeys"] == 1 and s["rejected_total"] == 1 and s["stale_epoch_total"] == 1, s   # the old-epoch straggler


def test_repeat_runs_interval():
    import repeat_runs as rr
    m, h = rr.mean_ci([1.0, 2.0, 3.0])
    assert m == 2.0 and h == pytest.approx(4.303 * 1.0 / 3 ** 0.5, rel=1e-3), (m, h)
    assert rr.mean_ci([]) == (None, None) and rr.mean_ci([5]) == (5.0, None)
    runs = [([dict(type="replay", rx_first_rejection_s=0.1, time_to_mitigate_s=1.0)],
             dict(false_alarm_windows=0, calm_windows=10))] * 2
    s = rr.summarise(runs)
    assert s["by_type"]["replay"]["mitigated"] == 2 and s["calm_windows"] == 20


def test_multi_camera_aggregate():
    import multi_camera as mc
    cams = [dict(frames_ok=100, latency_ms_median=10.0, latency_ms_p95=20.0, false_alarms=0, calm_windows=5),
            dict(frames_ok=80, latency_ms_median=12.0, latency_ms_p95=30.0, false_alarms=1, calm_windows=5)]
    a = mc.aggregate(2, cams, 0.5)
    assert a["frames_ok_per_camera"] == 90 and a["latency_ms_p95_worst"] == 30.0 and a["false_alarms"] == 1


def test_privacy_metrics_levels_and_order():
    import privacy_metrics as pm
    frames = [make_image(64, 48, "scene")]
    seen = []

    def fake_detect(rgb):                                  # a "face" everywhere: tests the counting only
        seen.append(rgb.shape)
        return [(0, 0, 32, 32)]
    res = pm.evaluate(frames, fake_detect, None)
    assert list(res) == pm.LEVELS
    assert res["plain"]["ssim"] > res["E2"]["ssim"], f"plain SSIM {res['plain']['ssim']} <= E2 {res['E2']['ssim']}"
    assert res["plain"]["face_recall"] == 1.0 and res["plain"]["faces"] == 1
    assert pm.face_detector("does/not/exist.onnx") is None


def test_privacy_metrics_edge_correlation_identity():
    import privacy_metrics as pm
    img = make_image(64, 48, "scene")
    assert pm.edge_corr(img, img) == pytest.approx(1.0)
    assert pm.edge_corr(img, np.zeros_like(img)) == 0.0


def test_benchmark_suite_new_schemes_registered():
    import benchmark_suite as bs
    for name, cite in (("EtC", "kurihara2015"), ("Tang", "tang1996")):
        assert name in bs.SCHEMES, f"{name} missing from SCHEMES"
        assert bs.SCHEMES[name]["cite"] == cite


def test_stream_protection_overheads():
    from system.baselines import stream_protection as sp
    assert sp.overhead_bytes("ascon_frame", 50_000) == 16
    assert sp.overhead_bytes("srtp_aesgcm", 1) == 16
    n = 3 * sp.RTP_PAYLOAD + 1
    assert sp.overhead_bytes("srtp_aesgcm", n) == 4 * 16
    assert sp.overhead_bytes("dtls_aesgcm", 1) == 13 + 8 + 16


def test_asic_estimate_parsing(tmp_path):
    import asic_estimate as ae
    lib = tmp_path / "x.lib"
    lib.write_text('library (x) {\n cell ("NAND2_X1") {\n  area : 0.798000;\n }\n}\n')
    assert ae.cell_area(lib, "NAND2_X1") == pytest.approx(0.798)
    old = "   Number of cells:   42\n   Chip area for module '\\top': 123.5\n"
    new = "     1623 1.28E+04 cells\n   Chip area for module '\\top': 12795.4\n"
    assert ae.parse("Number of memory bits: 64", old) == dict(area_um2=123.5, cells=42, memory_bits=64)
    assert ae.parse("", new) == dict(area_um2=12795.4, cells=1623, memory_bits=0)


def test_vivado_parts_dry_run():
    import run_vivado_day as rv
    jobs = rv.part_jobs(["artix7_100t"], [8.0])
    names = [j[0] for j in jobs]
    assert names == ["ooc_part_artix7_100t", "ooc_part_artix7_100t_lanes4",
                     "ooc_part_artix7_100t_8.0ns", "ooc_part_artix7_100t_lanes4_8.0ns"], names
    assert all("PART xc7a100tcsg324-1" in j[2] for j in jobs)
    tcl = (ROOT / "hardware" / "vivado" / "vivado_ooc.tcl").read_text()
    assert '-part $part' in tcl and 'eq "PART"' in tcl


def test_xiph_list_is_consistent():
    import get_xiph as gx
    assert set(gx.DEFAULT) <= set(gx.SEQUENCES)
    for n, (res, _) in gx.SEQUENCES.items():
        w, h = (int(v) for v in res.split("x"))
        assert w > 0 and h > 0, n
        if n in gx.DEFAULT:                                  # used as they are: whole MCUs
            assert w % 16 == 0 and h % 16 == 0, f"{n}: {res} is not a multiple of 16 (the encoder's MCU)"


def test_scenarios_parse():
    import json
    for f in ("calm.json", "rekey_load.json"):
        sc = json.loads((ROOT / "experiments" / "scenarios" / f).read_text())
        assert sc["end_s"] > 0 and all(s["at"] < sc["end_s"] for s in sc["steps"]), f
