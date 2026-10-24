"""Running the project from a fresh clone: the native-library compiler default on Windows,
the energy table without a USB meter, publishing / checking the board images, and the setup check."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from system.baselines import energy_table as et   # noqa: E402
from link import fastrx                                # noqa: E402
from scripts import check_setup, publish_bitstreams as pb   # noqa: E402


def test_native_compiler_default():
    """MinGW has no `cc`: on Windows the fast receiver and the E5 shuffle must ask for gcc (bug #42)."""
    for name, env, want in (("nt", {}, "gcc"), ("posix", {}, "cc"), ("nt", {"CC": "clang"}, "clang"),
                            ("posix", {"CC": "gcc-12"}, "gcc-12"), ("nt", {"CC": ""}, "gcc")):
        got = fastrx._cc(name, env)
        assert got == want, f"os.name={name!r}, env={env}: got {got!r}, expected {want!r}"
    from system.arm import sw_encoder
    from system.board import fast_e5
    assert fast_e5.native_lib is fastrx.native_lib is sw_encoder.native_lib


@pytest.mark.skipif(not shutil.which(fastrx._cc()), reason="no C compiler")
def test_native_cache_rebuilds_a_library_that_does_not_load(tmp_path, monkeypatch):
    """Bug #43: a DLL built by a 32-bit MinGW stayed in ~/.cache/sjpeg and was loaded (and failed) on every
    run, even after a 64-bit gcc was installed. Now the compiler's target is part of the cache name, and a
    library that does not load is deleted, with the reason in the error."""
    src = tmp_path / "t.c"
    src.write_text("int seven(void) { return 7; }\n")
    flags = ["-O2", "-shared", "-fPIC"]
    first, cache = tmp_path / "first", tmp_path / "cache"
    monkeypatch.setenv("SJPEG_CACHE", str(first))
    assert fastrx.native_lib(src, "t", flags).seven() == 7
    name = next(first.glob("t_*.so")).name
    monkeypatch.setenv("SJPEG_CACHE", str(cache))         # a fresh path: the OS has not loaded it yet
    cache.mkdir()
    (cache / name).write_bytes(b"not a library")         # what a wrong-architecture build looks like
    with pytest.raises(RuntimeError, match="cannot load t.c"):
        fastrx.native_lib(src, "t", flags)
    assert not (cache / name).exists(), "the unloadable library must be deleted"
    assert fastrx.native_lib(src, "t", flags).seven() == 7     # rebuilt
    monkeypatch.setattr(fastrx, "_machine", lambda cc: "another-target")
    fastrx.native_lib(src, "t", flags)
    assert len(list(cache.glob("t_*.so"))) == 2, "another compiler target gets its own cache file"


def _vivado_json(tmp_path):
    p = tmp_path / "vivado.json"
    p.write_text(json.dumps([{"name": "overlay_lanes4", "power": {"total": 2.0, "confidence": "Medium"}},
                             {"name": "secure_jpeg_top", "power": {"total": 0.25}}]))
    return p


def test_energy_table_without_meter(tmp_path):
    rows = [dict(method="FPGA 4 lanes", mode="E2", width="640", height="480", fps="", power_w="3.0",
                 idle_power_w="1.0", image="overlay_lanes4"),
            dict(method="FPGA 4 lanes", mode="E5", width="640", height="480", fps="", power_w="",
                 idle_power_w="", image="overlay_lanes4"),
            dict(method="ours on the PS, E2, 2 cores", mode="E2", width="640", height="480", fps="", power_w="",
                 idle_power_w="", image="")]
    fpga = {"speed": [{"size": "640x480", "mode": 2, "full_fps": 100.0}, {"size": "640x480", "mode": 5, "full_fps": 80.0}]}
    arm = {"sizes": {"640x480": {"ours on the PS, E2, 2 cores": {"fps": 5.0}}}}
    viv = _vivado_json(tmp_path)

    t = et.build(rows, fpga, arm, no_meter=True, vivado_json=viv)
    exp = [(100.0, 2.0, "Vivado estimate", 20.0), (80.0, 2.0, "Vivado estimate", 25.0), (5.0, None, "not measured", None)]
    for i, (o, (fps, p, src, mj)) in enumerate(zip(t, exp)):
        got = (o["fps"], o["power_w"], o["source"].split(" (")[0], o["energy_mj"] and round(o["energy_mj"], 6))
        assert got == (fps, p, src, mj), f"row {i} without meter: got {got}, expected {(fps, p, src, mj)}"
    assert t[0]["dyn_mj"] is None, "Vivado's static power is not the board's idle power: no 'above idle'"
    assert round(t[1]["ratio"], 6) == 1.25

    t = et.build(rows, fpga, arm, no_meter=False, vivado_json=viv)        # row 0 has a meter reading
    assert (t[0]["source"], round(t[0]["energy_mj"], 6), round(t[0]["dyn_mj"], 6)) == ("USB meter", 30.0, 20.0)
    assert t[1]["source"].startswith("Vivado estimate") and t[1]["ratio"] == 1.0, \
        "ratios only between rows whose power comes from the same source"

    csv = tmp_path / "p.csv"
    csv.write_text("method,mode,width,height,fps,power_w,idle_power_w,image,notes\n"
                   "FPGA 4 lanes,E2,640,480,,,,overlay_lanes4,x\n")
    fj = tmp_path / "fc.json"
    fj.write_text(json.dumps(fpga))
    et.main([str(csv), "--no-meter", "--fpga-json", str(fj), "--vivado-json", str(viv)])
    md = csv.with_suffix(".md").read_text(encoding="utf-8")
    assert "Vivado estimate (overlay_lanes4" in md and "| 20.0 |" in md, md


def test_energy_table_template_columns():
    """The shipped template has the columns the script reads, and its FPGA rows name a Vivado design."""
    import csv
    rows = list(csv.DictReader((ROOT / "system" / "baselines" / "power_template.csv").open(encoding="utf-8")))
    assert rows and {"fps", "power_w", "idle_power_w", "image"} <= set(rows[0])
    names = {e["name"] for e in json.loads(et.VIVADO_JSON.read_text(encoding="utf-8"))}
    for r in rows:
        assert not r["image"] or r["image"] in names, f"{r['method']}: image {r['image']!r} not in vivado_results.json"


def _overlay(tmp_path, files):
    ov = tmp_path / "overlay"
    ov.mkdir()
    for name, data in files.items():
        (ov / name).write_bytes(data)
    lst = tmp_path / "list.json"
    import hashlib
    pre = hashlib.sha256(b"bit A").hexdigest()[:16]
    lst.write_text(json.dumps({"images": [
        dict(file="a.bit", design="d", step="s", version="v", clock_mhz=100, run="run 1", sha256_prefix=pre,
             required=True, purpose="p"),
        dict(file="b.bit", design="d", step="s", version="v", clock_mhz=100, run="run 1", sha256_prefix=None,
             required=False, purpose="p"),
        dict(file="c.bit", design="d", step="s", version="v", clock_mhz=100, run="run 1", sha256_prefix=None,
             required=False, purpose="p")]}))
    return ov, lst


def test_publish_bitstreams_checks(tmp_path):
    ov, lst = _overlay(tmp_path, {"a.bit": b"bit A", "a.hwh": b"hwh A", "b.bit": b"bit B"})
    st = {r["file"]: (r["status"], r["problem"]) for r in pb.check(ov, lst)}
    assert st["a.bit"][0] == "ok", st
    assert st["b.bit"][0] == "error" and ".hwh" in st["b.bit"][1], st
    assert st["c.bit"][0] == "missing", st

    (ov / "a.bit").write_bytes(b"another build")
    st = {r["file"]: r for r in pb.check(ov, lst)}
    assert st["a.bit"]["status"] == "error" and "run 1" in st["a.bit"]["problem"]
    assert pb.check(ov, lst, force=True)[0]["status"] == "ok"


def test_publish_bitstreams_manifest(tmp_path):
    ov, lst = _overlay(tmp_path, {"a.bit": b"bit A", "a.hwh": b"hwh A"})
    assert pb.main(["--overlay", str(ov), "--list", str(lst), "--no-git"]) == 0
    m = json.loads((ov / "MANIFEST.json").read_text())
    assert [i["file"] for i in m["images"]] == ["a.bit"]
    assert "`a.bit`" in (ov / "MANIFEST.md").read_text(encoding="utf-8")
    assert pb.main(["--overlay", str(ov), "--list", str(lst), "--check"]) == 0
    (ov / "a.hwh").write_bytes(b"truncated")                        # a broken copy on the board
    rows = pb.check(ov, lst, use_manifest=True)
    assert rows[0]["status"] == "error" and "MANIFEST" in rows[0]["problem"], rows[0]


def test_bitstream_list_matches_vivado_flow():
    """Every listed image is one run_vivado_day.py builds, and its design name is in the Vivado results."""
    src = (ROOT / "vivado" / "run_vivado_day.py").read_text(encoding="utf-8")
    names = {e["name"] for e in json.loads(et.VIVADO_JSON.read_text(encoding="utf-8"))}
    ims = pb.images()
    assert len(ims) == len({i["file"] for i in ims}) == 6
    for im in ims:
        assert im["file"] in src, f"{im['file']} is not an output of run_vivado_day.py"
        assert im["design"] in names, f"{im['file']}: design {im['design']} not in vivado_results.json"
    req = {i["file"] for i in ims if i["required"]}
    assert req == {"secure_jpeg_lanes.bit", "secure_jpeg_lanes4.bit", "secure_jpeg_lanes_tamper.bit"}


def test_bitstreams_stay_byte_exact_in_git():
    attrs = (ROOT / ".gitattributes").read_text()
    assert "*.bit binary" in attrs and "*.hwh binary" in attrs


def test_check_setup_runs(capsys):
    rc = check_setup.main([])
    out = capsys.readouterr().out
    assert "Setup check (laptop)" in out and "Python packages" in out, out
    assert rc == 0, out


def test_check_setup_cli():
    r = subprocess.run([sys.executable, "scripts/check_setup.py", "--vivado"], cwd=ROOT, capture_output=True, text=True)
    assert "Setup check (vivado)" in r.stdout and "Vivado" in r.stdout, r.stdout + r.stderr


def test_energy_table_zero_copy_fps(tmp_path):
    """--zero-copy takes the FPGA fps from first_contact's zero-copy rows (on the board 169 fps at 640x480 instead
    of 20 fps, which is mostly numpy copying the pixels into the DMA buffer)."""
    rows = [dict(method="FPGA 4 lanes", mode="E2", width="640", height="480", fps="", power_w="", idle_power_w="",
                 image="overlay_lanes4")]
    fpga = {"speed": [{"size": "640x480", "mode": 2, "zero_copy": False, "full_fps": 20.4},
                      {"size": "640x480", "mode": 2, "zero_copy": True, "full_fps": 169.4}]}
    viv = _vivado_json(tmp_path)
    for zc, want in ((False, 20.4), (True, 169.4)):
        got = et.build(rows, fpga, None, no_meter=True, vivado_json=viv, zero_copy=zc)[0]["fps"]
        assert got == want, f"zero_copy={zc}: fps {got}, expected {want}"
    assert "zero-copy" in et.markdown(et.build(rows, fpga, None, True, viv, True), zero_copy=True)
