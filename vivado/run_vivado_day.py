r"""The whole Vivado day in one command: XSim check, post-route numbers, overlay, paper table.

Open a terminal where Vivado is on the PATH, then from the repository root:
    Windows:  "C:\Xilinx\Vivado\<version>\settings64.bat"   (or open "Vivado <version> Tcl Shell")
    Linux:    source /tools/Xilinx/Vivado/<version>/settings64.sh

    python vivado/run_vivado_day.py                  # xsim + ooc + bd + parse  (~1 h of tool time)
    python vivado/run_vivado_day.py --steps xsim ooc parse      # skip the block design
    python vivado/run_vivado_day.py --steps ooc --blocks --fmax # + per-block runs, confirm fmax
    python vivado/run_vivado_day.py --dry-run        # only print what it would run
    python vivado/run_vivado_day.py --steps bd --fclk 50        # overlay at 50 MHz
    python vivado/run_vivado_day.py --steps bd --jobs 1         # less RAM (8 GB laptops: 1-2)
    python vivado/run_vivado_day.py --maxw 9 10                 # + line-buffer memory sweep
    python vivado/run_vivado_day.py --steps ooc parse --periods 8.0 6.667   # clock sweep 125/150 MHz
    python vivado/run_vivado_day.py --maxw 9 10 --periods 8.0 6.667 --jobs 2  # run 4: everything at once
    python vivado/run_vivado_day.py --steps xsim ooc lanes bd_lanes parse --periods 8.0 6.667
                                         # run 5: + the contract-v3 lane encoder (OOC at 100/125/150 MHz,
                                         #   4 lanes at 100 MHz) and its overlay (64-bit pixel DMA)
    python vivado/run_vivado_day.py --steps ooc lanes power parse   # + power from simulated activity
If the overlay misses timing at --fclk, the block design is retried at 90 and then 80 MHz (--no-fallback
turns this off). At the end, everything to send back is packed into vivado_results_<date>.zip in the
repository root (summary, paper tables, timing/utilisation/power reports; no bitstream).
Run it from a normal terminal with YOUR Python (numpy + pillow), not with `exec` from the
Vivado Tcl console: that uses Vivado's bundled Python and hides all output until the end.

Steps (each logs to sim_build/vivado_logs/<step>.log and is checked, not just run):
  xsim   golden-model vectors -> XSim self-checking testbench -> "XSIM RESULT: PASS"
         -> `check` rebuilds the JPEGs and runs the receiver on them
  ooc    out-of-context synthesis + place + route of secure_jpeg_top at 100 MHz
         (--blocks: also the Ascon core, keystream, tag, DCT, quantiser, Huffman on their own;
          --fmax: re-run the top at the period the first run's slack suggests, to confirm fmax)
  lanes  out-of-context runs of secure_jpeg_lanes_top (contract v3): 2 lanes (2048-pixel lines) and 4 lanes
         (1024-pixel lines) at 100 MHz and at every --periods clock, + 4 lanes with 2048-pixel lines (1080p)
  bd     PYNQ-Z2 block design + bitstream -> system/board/overlay/secure_jpeg.bit/.hwh
  bd_lanes  the same for the lane encoder -> overlay/secure_jpeg_lanes.bit/.hwh (reports in overlay/lanes/)
  bd_lanes4 the same with 4 lanes, lines up to 1024 px -> overlay/secure_jpeg_lanes4.bit/.hwh (overlay/lanes4/)
  bd_lanes4hd   4 lanes, 2048-px lines (1080p), one line-buffer set -> overlay/secure_jpeg_lanes4hd.bit
  bd_lanes4yuyv 4 lanes, camera-native YUYV input (4 px per beat) -> overlay/secure_jpeg_lanes4yuyv.bit
  bd_tamper the 2-lane image + hardware tamper injector (board-day attack demo, BTN0/switches/PMOD)
            + BTN1..BTN3 for the protection level (system/board/axil_buttons.v)
            -> overlay/secure_jpeg_lanes_tamper.bit/.hwh (reports in overlay/lanestamper/); run it at --fclk 100
  power  post-route power with SIMULATED switching activity (needs ooc and/or lanes first): XSim
         encodes --power-size scene frames in each mode and records activity.saif, then Vivado
         re-reports the routed design's power with it -> power_saif_<v2|v3>_E<m>.txt next to power.txt
         (v2 encoder: E0, E2, E4; 2-lane encoder: E2, E5)
  parse  every report -> sim_out/vivado/vivado_tables.md (the paper's hardware table)
  collect  (always, last) summary + reports -> vivado_results_<date>.zip
At the end it prints a PASS/FAIL table with the time of every step; a FAIL names its log
(the first "ERROR:" line there is the cause).

One file, four tools (they were separate scripts until 17 Oct 2026):
    python vivado/run_vivado_day.py [--steps ...]   the Vivado day (above)
    python vivado/run_vivado_day.py vectors [...]   XSim test vectors from the golden model
    python vivado/run_vivado_day.py check [...]     rebuild the JPEGs from an XSim/Icarus run, run the receiver
    python vivado/run_vivado_day.py parse [dirs]    Vivado reports -> sim_out/vivado/vivado_tables.md + .json
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

VECTORS_DOC = r"""Generate the XSim testbench inputs (vivado/tb_secure_jpeg_top.v) from the golden model.

    python vivado/run_vivado_day.py vectors                       # default frame set (fast)
    python vivado/run_vivado_day.py vectors --image photo.jpg --size 320x240 --modes 2 4
    python vivado/run_vivado_day.py vectors --video clip.mp4 --frames 3 --size 160x128
    python vivado/run_vivado_day.py vectors --v3                  # contract-v3 lane encoder (2 lanes)
                                                            #   -> vivado/xsim_work_v3/

Writes to vivado/xsim_work/ (or --out):
    commands.txt      register writes / reads, stream and check commands
    pixels.hex        32-bit words {pad, B, G, R}, one per line, all frames
    expect_scan.hex   expected scan bytes (one per line), all frames
    frames.json       what each frame is (for `check`)
The same files run in Icarus (make xsim-icarus) and in Vivado XSim (run_xsim.sh/.bat).
"""
CHECK_DOC = r"""After an XSim (or Icarus) run: rebuild the JPEG files from what the simulated
hardware produced, run the real receiver on them and save images to look at.

    python vivado/run_vivado_day.py check                 # reads vivado/xsim_work/
    python vivado/run_vivado_day.py check --dir vivado/xsim_work_v3     # contract-v3 run
Writes xsim_work/frame<N>_scrambled.jpg (what VLC would show) and
xsim_work/frame<N>_decrypted.jpg (what the key holder sees).
"""
PARSE_DOC = r"""Turn Vivado reports into the paper's hardware table (no number typed by hand).

    python vivado/run_vivado_day.py parse                       # every sim_build/vivado_*/ and both overlays
    python vivado/run_vivado_day.py parse sim_build/vivado_secure_jpeg_top system/board/overlay

Reads, in each folder: utilization.txt (LUT / FF / BRAM / DSP), timing.txt (WNS, TNS, WHS),
power.txt (total / dynamic / static W) and utilization_hier.txt (per-block LUT / FF).
Writes sim_out/vivado/vivado_tables.md and vivado_results.json; paper_tables.py includes them.

Formats: Vivado 2019.2-2024.x text reports. If a field is missing the table shows "?" and the
script says which file and field -- it never guesses a number.
"""



# ==================================================================================================
# vectors: XSim testbench inputs from the golden model (was run_vivado_day.py vectors)
# ==================================================================================================
CTRL, STATUS, VERSION = 0x00, 0x04, 0x08
WIDTH, HEIGHT, FRAME_CTR, SESSION_ID = 0x10, 0x14, 0x18, 0x1C
KEY0, OUT_BYTES, TAG0, QT_ADDR, QT_DATA = 0x20, 0x30, 0x34, 0x44, 0x48
SESSION_ID_HI, FRAME_CTR_HI = 0x4C, 0x50
DEFAULT_KEY = "000102030405060708090a0b0c0d0e0f"


def load_frames(a):
    from model.testimage import make_image
    w, h = (int(v) for v in a.size.lower().split("x"))
    if a.image or a.video:
        import cv2
        imgs = []
        if a.image:
            imgs.append(cv2.cvtColor(cv2.imread(a.image), cv2.COLOR_BGR2RGB))
        else:
            cap = cv2.VideoCapture(a.video)
            while len(imgs) < a.frames:
                ok, f = cap.read()
                if not ok:
                    break
                imgs.append(cv2.cvtColor(f, cv2.COLOR_BGR2RGB))
        imgs = [cv2.resize(i, (w, h), interpolation=cv2.INTER_AREA) for i in imgs]
        frames = []
        for k, img in enumerate(imgs):
            for m in a.modes:
                frames.append((img, a.quality, m, f"input{k}_E{m}"))
        return frames
    if a.scene:                         # power flow: one realistic frame per mode
        w, h = (int(v) for v in a.scene.lower().split("x"))
        return [(make_image(w, h, "scene", 11), a.quality, m, f"scene{w}x{h}_E{m}") for m in a.modes]
    # default: small synthetic set covering every mode, two qualities, odd sizes
    return [(make_image(64, 48, "scene", 1), 75, 2, "scene64x48_E2"),
            (make_image(32, 32, "noise", 2), 75, 4, "noise32x32_E4"),
            (make_image(48, 32, "checker", 3), 75, 0, "checker48x32_E0"),
            (make_image(64, 64, "bars", 4), 50, 1, "bars64x64_q50_E1"),
            (make_image(80, 48, "scene", 5), 50, 3, "scene80x48_q50_E3")] + \
        ([(make_image(64, 48, "scene", 6), 75, 5, "scene64x48_E5"),       # E5 RTL (INTERFACES.md §8.6)
          (make_image(48, 32, "noise", 7), 75, 5, "noise48x32_E5")] if 5 in a.modes and a.v3 else [])


def vectors_main(argv=None):
    import numpy as np
    from model import hw
    ap = argparse.ArgumentParser(prog="run_vivado_day.py vectors", description=VECTORS_DOC, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--image")
    ap.add_argument("--video")
    ap.add_argument("--frames", type=int, default=2, help="frames to take from --video")
    ap.add_argument("--size", default="64x48", help="WxH, multiples of 16 (with --image/--video)")
    ap.add_argument("--scene", default=None,
                    help="WxH: one synthetic scene frame of this size per --modes value (power flow)")
    ap.add_argument("--modes", type=int, nargs="+", default=[2])
    ap.add_argument("--quality", type=int, default=75)
    ap.add_argument("--key", default=DEFAULT_KEY)
    ap.add_argument("--session", type=lambda s: int(s, 0), default=0x5EC0_0001_C0FF_EE00)
    ap.add_argument("--ctr", type=lambda s: int(s, 0), default=(1 << 32) + 100)
    ap.add_argument("--v3", action="store_true",
                    help="vectors for secure_jpeg_lanes_top (contract v3, 2 lanes, 2 pixels per beat)")
    ap.add_argument("--lanes", type=int, default=2, choices=[2, 4],
                    help="with --v3: drive the 2-lane (dut3) or the 4-lane (dut4) encoder of the testbench")
    ap.add_argument("--out", default=None,
                    help="default vivado/xsim_work (v2), vivado/xsim_work_v3 (2 lanes) or xsim_work_v3l4")
    a = ap.parse_args(argv)
    if a.out is None:
        a.out = str(ROOT / "vivado" / (("xsim_work_v3l4" if a.lanes == 4 else "xsim_work_v3") if a.v3 else "xsim_work"))
    key = bytes.fromhex(a.key)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    cmds, pix, exp, meta = [], [], [], []
    w32 = lambda addr, val: cmds.append(f"W {addr:02x} {val & 0xFFFFFFFF:08x}")
    r32 = lambda addr, val: cmds.append(f"R {addr:02x} {val & 0xFFFFFFFF:08x}")

    # session setup + register sanity checks
    if a.v3:
        cmds.append("M 4" if a.lanes == 4 else "M 3")
    r32(VERSION, (0x5EC00380 + a.lanes) if a.v3 else 0x5EC00200)   # v3: 0x80 = mode 5 in the RTL, + lanes
    for i in range(4):
        w32(KEY0 + 4 * i, int.from_bytes(key[4 * i:4 * i + 4], "little"))
        r32(KEY0 + 4 * i, 0)                                   # keys are write-only
    w32(SESSION_ID, a.session)
    w32(SESSION_ID_HI, a.session >> 32)
    r32(SESSION_ID_HI, a.session >> 32)
    loaded_q = None
    for n, (img, q, mode, name) in enumerate(load_frames(a)):
        h, w = img.shape[:2]
        assert w % 16 == 0 and h % 16 == 0, "width and height must be multiples of 16"
        if q != loaded_q:
            luma, chroma = hw.quality_tables(q)
            w32(QT_ADDR, 0)
            for v in luma + chroma:
                w32(QT_DATA, hw.reciprocal(v))
            loaded_q = q
        ctr = a.ctr + n
        e = (hw.encode_frame_v3 if a.v3 else hw.encode_frame)(img, q, mode, key, ctr, a.session)
        cmds.append(f"F {n}")
        w32(WIDTH, w)
        w32(HEIGHT, h)
        w32(FRAME_CTR, ctr)
        w32(FRAME_CTR_HI, ctr >> 32)
        w32(CTRL, 1 | (mode << 1))
        cmds.append(f"S {w * h}")
        cmds.append(f"C {len(e['scan'])}")
        t = e["tag"]
        cmds.append("G " + " ".join(f"{int.from_bytes(t[4 * i:4 * i + 4], 'little'):08x}" for i in range(4)))
        p = img.astype(np.uint32)
        pix.extend((p[..., 0] | (p[..., 1] << 8) | (p[..., 2] << 16)).flatten().tolist())
        exp.extend(e["scan"])
        meta.append(dict(index=n, name=name, width=w, height=h, quality=q, mode=mode, version=3 if a.v3 else 2,
                         frame_ctr=ctr, scan_bytes=len(e["scan"]), tag=t.hex()))
    cmds.append("E")
    (out / "commands.txt").write_text("\n".join(cmds) + "\n")
    (out / "pixels.hex").write_text("".join(f"{v:08x}\n" for v in pix))
    (out / "expect_scan.hex").write_text("".join(f"{v:02x}\n" for v in exp))
    (out / "frames.json").write_text(json.dumps(dict(key=a.key, session_id=a.session, frames=meta), indent=2))
    write_abs_prj(out)
    print(f"{len(meta)} frames, {len(pix)} pixels, {len(exp)} scan bytes -> {out}/")
    if len(pix) > 640 * 480 * 4:
        print("NOTE: more pixels than the testbench's MAXPIX; raise it with -generic_top / -P")


def write_abs_prj(out):
    """xsim.prj with absolute paths (bug #18): xvlog on Windows resolves the relative paths
    of a .prj against the .prj file's folder, not the working folder, so the shared
    vivado/xsim.prj (relative to xsim_work/, also read by the Makefile and the tests) broke
    there. run_xsim.bat / run_xsim.sh use this generated copy instead."""
    base = ROOT / "vivado" / "xsim_work"           # what the paths in vivado/xsim.prj are relative to
    out = Path(out)
    lines = []
    for line in (ROOT / "vivado" / "xsim.prj").read_text().splitlines():
        f = line.split()
        if len(f) == 3 and f[0] == "verilog":
            lines.append(f"verilog {f[1]} {(base / f[2]).resolve().as_posix()}")
    (out / "xsim_abs.prj").write_text("\n".join(lines) + "\n")


# ==================================================================================================
# check: rebuild the JPEGs from what the simulated hardware produced (was run_vivado_day.py check)
# ==================================================================================================
def check_main(argv=None):
    from model import hw
    from model.jpeg import ReplayGuard, receive_frame
    ap = argparse.ArgumentParser(prog="run_vivado_day.py check", description=CHECK_DOC,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", default=str(ROOT / "vivado" / "xsim_work"))
    a = ap.parse_args(argv)
    d = Path(a.dir)
    info = json.loads((d / "frames.json").read_text())
    key, sid = bytes.fromhex(info["key"]), info["session_id"]
    scan_all = bytes(int(x, 16) for x in (d / "out_scan.hex").read_text().split())
    tags = {}
    for line in (d / "out_tags.txt").read_text().splitlines():
        f = line.split()
        tags[int(f[0])] = b"".join(int(w, 16).to_bytes(4, "little") for w in f[1:5])
    guard, pos, bad = ReplayGuard(), 0, 0
    for fr in info["frames"]:
        scan = scan_all[pos:pos + fr["scan_bytes"]]
        pos += fr["scan_bytes"]
        jpg = hw.build_frame(fr["width"], fr["height"], fr["quality"], fr["mode"],
                             fr["frame_ctr"], sid, scan, tags[fr["index"]], version=fr.get("version", 2))
        if fr["mode"] == hw.MODE_E5:                  # E5 (INTERFACES.md §8.6): the ARM permutes the segments
            jpg = hw.arm_shuffle(jpg, key, sid, fr["frame_ctr"])
        r = receive_frame(jpg, key, guard)
        (d / f"frame{fr['index']}_scrambled.jpg").write_bytes(jpg)
        if r.plain_jpeg:
            (d / f"frame{fr['index']}_decrypted.jpg").write_bytes(r.plain_jpeg)
        ok = r.ok and r.mode == f"E{fr['mode']}"
        bad += not ok
        print(f"frame {fr['index']} {fr['name']:<22} receiver: {r.reason:<13} mode {r.mode}  "
              f"{'OK' if ok else 'FAIL'}")
    print("CHECK RESULT:", "PASS" if bad == 0 else f"FAIL ({bad} frames)")
    sys.exit(1 if bad else 0)


# ==================================================================================================
# parse: Vivado reports -> the paper's hardware table (was run_vivado_day.py parse)
# ==================================================================================================
OUT = ROOT / "sim_out" / "vivado"
DEVICE = dict(lut=53200, ff=106400, bram=140, dsp=220)        # xc7z020 totals (for the % column)
ROWS = {"lut": ("Slice LUTs",), "ff": ("Slice Registers", "Register as Flip Flop"),
        "bram": ("Block RAM Tile",), "dsp": ("DSPs",)}


def _cells(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def parse_utilization(text):
    """{'lut': (used, available, pct), ...} from report_utilization (flat)."""
    res = {}
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        c = _cells(line)
        name = c[0].rstrip("*").strip()
        for key, names in ROWS.items():
            if key not in res and name in names:
                try:
                    used, avail, pct = float(c[1]), float(c[-2]), c[-1]
                    res[key] = (used, avail, float(pct.replace("<", "")))
                except (ValueError, IndexError):
                    pass
    return res


def parse_timing(text):
    """{'wns': ns, 'tns': ns, 'whs': ns, 'met': bool} from report_timing_summary."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if "WNS(ns)" in line and "TNS(ns)" in line:
            # fixed column order: WNS, TNS, TNS failing, TNS total, WHS, THS, ... (headers contain spaces)
            for nxt in lines[i + 1:i + 6]:
                parts = nxt.split()
                if parts and not set(nxt.strip()) <= set("- "):
                    try:
                        v = [float(p) for p in parts[:5]]
                    except ValueError:
                        break
                    met = "All user specified timing constraints are met" in text
                    return dict(wns=v[0], tns=v[1], whs=v[4], met=met)
    return {}


def parse_critical(text, n=10):
    """Blocks on the worst setup paths: [(slack, source block, destination block)] from the
    report_timing_summary path list (block = first hierarchy level, e.g. u_conv)."""
    out = []
    blk = lambda pin: pin.split("/")[0] if "/" in pin else "(top)"
    slack = src = None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("Slack"):
            m = re.search(r":\s*(-?[\d.]+)ns", line)
            slack = float(m.group(1)) if m else None
        elif line.startswith("Source:"):
            src = blk(line.split()[1])
        elif line.startswith("Destination:") and slack is not None and src is not None:
            out.append((slack, src, blk(line.split()[1])))
            slack = src = None
            if len(out) >= n:
                break
    return out


def parse_period(text, folder):
    m = re.search(r"\{0\.000\s+([\d.]+)\}\s+([\d.]+)\s+([\d.]+)", text)    # clock table: {0.000 5.000} 10.000 100.000
    if m:
        return float(m.group(2))
    m = re.search(r"_([\d.]+)ns$", folder.name)
    return float(m.group(1)) if m else 10.0


def parse_power(text):
    res = {}
    for key, label in (("total", "Total On-Chip Power (W)"), ("dynamic", "Dynamic (W)"),
                       ("static", "Device Static (W)")):
        m = re.search(r"\|\s*" + re.escape(label) + r"\s*\|\s*([\d.]+)", text)
        if m:
            res[key] = float(m.group(1))
    m = re.search(r"\|\s*Confidence Level\s*\|\s*(\w+)", text)
    if m:
        res["confidence"] = m.group(1)
    m = re.search(r"\|\s*Internal nodes activity\s*\|\s*(\w+)\s*\|\s*([^|]*?)\s*\|", text)
    if m:                               # how much of the design had simulated (not default) activity
        res["internal"] = m.group(1)
        res["internal_detail"] = m.group(2)
    return res


def parse_power_saif(folder):
    """{tag: power} from power_saif_<tag>.txt (step_power), e.g. tag v2_E2."""
    out = {}
    for f in sorted(Path(folder).glob("power_saif_*.txt")):
        out[f.stem[len("power_saif_"):]] = parse_power(f.read_text(errors="replace"))
    return out


def parse_hier(text, depth=2):
    """[(indent_level, instance, module, total_luts, ffs, bram36+bram18/2, dsp)] from the hierarchical report."""
    rows, head = [], None
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        raw = line.strip().strip("|").split("|")
        c = [x.strip() for x in raw]
        if c[0] == "Instance":
            head = c
            continue
        if head is None or len(c) != len(head):
            continue
        level = (len(raw[0]) - len(raw[0].lstrip(" ")) - 1) // 2
        if level > depth:
            continue
        row = dict(zip(head, c))
        num = lambda k: float(row.get(k, "0") or 0)
        try:
            bram = num("RAMB36") + num("RAMB18") / 2
            rows.append((level, c[0], row.get("Module", ""), int(num("Total LUTs")), int(num("FFs")), bram,
                         int(num("DSP48 Blocks") or num("DSP Blocks"))))
        except ValueError:
            continue
    return rows


def _name(folder):
    """Design name from the folder: vivado_<design> (OOC runs), overlay, overlay/lanes -> overlay_lanes."""
    if folder.name in ("lanes", "lanes4", "lanes4hd", "lanes4yuyv", "lanestamper") and folder.parent.name == "overlay":
        return f"overlay_{folder.name}"
    return folder.name.replace("vivado_", "")


def read_folder(folder):
    folder = Path(folder)
    rd = lambda n: (folder / n).read_text(errors="replace") if (folder / n).exists() else ""
    t = rd("timing.txt")
    r = dict(folder=str(folder), name=_name(folder), util=parse_utilization(rd("utilization.txt")),
             timing=parse_timing(t), power=parse_power(rd("power.txt")), power_saif=parse_power_saif(folder),
             hier=parse_hier(rd("utilization_hier.txt")),
             critical=parse_critical(t),
             period=parse_period(t, folder), missing=[])
    for f in ("utilization.txt", "timing.txt", "power.txt"):
        if not (folder / f).exists():
            r["missing"].append(f)
    wns = r["timing"].get("wns")
    r["fmax_mhz"] = round(1000 / (r["period"] - wns), 1) if wns is not None and r["period"] - wns > 0 else None
    return r


def fmt(v, nd=0):
    return "?" if v is None else (f"{v:.{nd}f}" if isinstance(v, float) else str(v))


def tables(results):
    md = ["## Hardware results from Vivado (post-route, xc7z020clg400-1)", "",
          "| Design | LUT | FF | BRAM | DSP | Clock (MHz) | WNS (ns) | Timing met | Est. fmax (MHz) | Power total / dynamic (W) |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for r in results:
        u, t, p = r["util"], r["timing"], r["power"]
        cell = lambda k: f"{fmt(u[k][0], 1 if k == 'bram' else 0)} ({u[k][2]:.1f}%)" if k in u else "?"
        md.append(f"| {r['name']} | {cell('lut')} | {cell('ff')} | {cell('bram')} | {cell('dsp')} | "
                  f"{fmt(1000 / r['period'], 0)} | {fmt(t.get('wns'), 3)} | {'yes' if t.get('met') else ('NO' if t else '?')} | "
                  f"{fmt(r['fmax_mhz'], 1)} | {fmt(p.get('total'), 3)} / {fmt(p.get('dynamic'), 3)} |")
    md += ["", "Power is Vivado's vectorless estimate (confidence shown in power.txt); measure the board for real power.",
           "Est. fmax = 1000 / (period - WNS): a single-run estimate, confirm by re-running at that period.", ""]
    saif = [r for r in results if r.get("power_saif")]
    if saif:
        md += ["### Power with simulated switching activity (SAIF from the XSim testbench)", "",
               "| Design | Run | Total (W) | Dynamic (W) | Vectorless dynamic (W) | Confidence | Internal nodes |",
               "|---|---|---|---|---|---|---|"]
        for r in saif:
            for tag, p in r["power_saif"].items():
                md.append(f"| {r['name']} | {tag} | {fmt(p.get('total'), 3)} | {fmt(p.get('dynamic'), 3)} | "
                          f"{fmt(r['power'].get('dynamic'), 3)} | {p.get('confidence', '?')} | "
                          f"{p.get('internal', '?')}: {p.get('internal_detail', '')} |")
        md += ["", "Run = contract (v2: secure_jpeg_top, v3: 2 lanes) and mode; activity of one scene frame "
               "(vivado/run_vivado_day.py --steps power). Activity from RTL simulation matches only the nets "
               "whose names survive synthesis; the rest keep Vivado's default. Still an estimate: the "
               "board measurement is the measured number.", ""]
    crit = [r for r in results if r.get("critical")]
    if crit:
        md += ["### Worst setup paths (block of source -> destination)", "",
               "| Design | Clock (MHz) | Paths (slack ns: from -> to) |", "|---|---|---|"]
        for r in crit:
            paths = "; ".join(f"{sl:+.3f}: {a} -> {b}" for sl, a, b in r["critical"][:5])
            md.append(f"| {r['name']} | {fmt(1000 / r['period'], 0)} | {paths} |")
        md.append("")
    for r in results:
        if r["hier"]:
            md += [f"### Resource breakdown: {r['name']}", "", "| Block | Module | LUT | FF | BRAM | DSP |",
                   "|---|---|---|---|---|---|"]
            md += [f"| {'&nbsp;' * 2 * lvl}{inst} | {mod} | {lut} | {ff} | {bram:g} | {dsp} |"
                   for lvl, inst, mod, lut, ff, bram, dsp in r["hier"]]
            md.append("")
    probs = [f"* {r['name']}: missing {', '.join(r['missing'])}" for r in results if r["missing"]]
    probs += [f"* {r['name']}: no {k} in utilization.txt" for r in results for k in ROWS if k not in r["util"]
              and not r["missing"]]
    if probs:
        md += ["### Not found (check these files)", ""] + probs
    return "\n".join(md) + "\n"


def parse_main(argv=None):
    argv = sys.argv[2:] if argv is None else argv
    if argv and argv[0] in ("-h", "--help"):
        sys.exit(PARSE_DOC)
    folders = [Path(a) for a in argv] or sorted((ROOT / "sim_build").glob("vivado_*")) + \
        [p for p in [ROOT / "system" / "board" / "overlay",
                     ROOT / "system" / "board" / "overlay" / "lanes",
                     ROOT / "system" / "board" / "overlay" / "lanes4",
                     ROOT / "system" / "board" / "overlay" / "lanes4hd",
                     ROOT / "system" / "board" / "overlay" / "lanes4yuyv",
                     ROOT / "system" / "board" / "overlay" / "lanestamper"] if (p / "timing.txt").exists()]
    folders = [f for f in folders if f.is_dir() and f.name != "vivado_logs"]   # logs are not a design
    if not folders:
        sys.exit("no report folders: run vivado/vivado_ooc.tcl (or vivado/run_vivado_day.py) first")
    results = [read_folder(f) for f in folders]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "vivado_results.json").write_text(json.dumps(results, indent=1))
    md = tables(results)
    (OUT / "vivado_tables.md").write_text(md)
    print(md + f"\nwritten {OUT}/vivado_tables.md and vivado_results.json")


# ==================================================================================================
# the Vivado day
# ==================================================================================================
LOGS = ROOT / "sim_build" / "vivado_logs"
BLOCKS = ["ascon_aead128_core", "keystream_gen", "tag_unit", "dct8x8", "quantiser", "huffman_enc", "selective_enc"]
WIN = os.name == "nt"
RESULTS = []


def run(name, cmd, check=None, dry=False):
    """Run one command from the repo root, log it, check for a success marker."""
    LOGS.mkdir(parents=True, exist_ok=True)
    log = LOGS / f"{name}.log"
    print(f"\n=== {name}\n$ {cmd}", flush=True)
    if dry:
        RESULTS.append((name, "DRY", 0.0, str(log)))
        return ""
    t0 = time.time()
    p = subprocess.run(cmd, shell=True, cwd=ROOT, capture_output=True, text=True, errors="replace")
    out = p.stdout + p.stderr
    log.write_text(out)
    ok = p.returncode == 0 and (check is None or re.search(check, out) is not None)
    dt = time.time() - t0
    RESULTS.append((name, "PASS" if ok else "FAIL", dt, str(log)))
    tail = [line for line in out.splitlines() if line.startswith(("RESULT", "XSIM RESULT", "CHECK", "ERROR"))][-6:]
    print("\n".join(tail) or "\n".join(out.splitlines()[-5:]))
    print(f"--> {'PASS' if ok else 'FAIL'} in {dt / 60:.1f} min   (log: {log.relative_to(ROOT)})", flush=True)
    if not ok:
        errs = [line for line in out.splitlines() if "ERROR" in line][:3]
        print("first errors:\n  " + "\n  ".join(errs) if errs else
              "no ERROR line: the tool stopped without a message (crash or out of memory); last lines:\n  "
              + "\n  ".join(out.splitlines()[-8:]))
    return out


def vivado(name, script, args="", check=None, dry=False):
    tcl_args = f" -tclargs {args}" if args else ""
    log = (LOGS / f"{name}_vivado.log").relative_to(ROOT).as_posix()      # relative: no spaces from the user's path
    return run(name, f"vivado -mode batch -nojournal -log {log} -source {script}{tcl_args}",
               check, dry)


def vivado_many(a, jobs):
    """Run several OOC jobs [(name, script, args)], --parallel at a time (each Vivado needs ~3-4 GB RAM).
    --only keeps the jobs whose name contains one of the given words. A job that ends without its RESULT
    line is run once more on its own (run 10: a Vivado process died silently while another one was
    routing). Returns {name: log text}."""
    if a.only:
        jobs = [j for j in jobs if any(w in j[0] for w in a.only)]
    if not jobs:
        return {}
    if a.parallel <= 1 or a.dry_run or len(jobs) < 2:
        outs = {n: vivado(n, sc, ar, r"RESULT top=", a.dry_run) for n, sc, ar in jobs}
    else:
        from concurrent.futures import ThreadPoolExecutor
        print(f"\n=== {len(jobs)} out-of-context runs, {a.parallel} at a time: {', '.join(j[0] for j in jobs)}",
              flush=True)
        with ThreadPoolExecutor(max_workers=a.parallel) as ex:
            futs = {n: ex.submit(vivado, n, sc, ar, r"RESULT top=") for n, sc, ar in jobs}
            outs = {n: f.result() for n, f in futs.items()}
    if not a.dry_run:
        for n, sc, ar in jobs:
            if "RESULT top=" not in (outs.get(n) or ""):
                # run 10 (bug #38): the same settings crashed again in phys_opt_design, so the retry
                # uses the "safe" flow (no AggressiveExplore physical optimisation)
                print(f"\n{n} gave no result: running it again on its own (SJPEG_IMPL=safe)", flush=True)
                for k, r in enumerate(RESULTS):              # the retry decides this job's status
                    if r[0] == n and r[1] == "FAIL":
                        RESULTS[k] = (n, "RETRY", r[2], r[3])
                before = os.environ.get("SJPEG_IMPL")
                os.environ["SJPEG_IMPL"] = "safe"
                try:
                    outs[n] = vivado(n, sc, ar, r"RESULT top=")
                finally:
                    if before is None:
                        os.environ.pop("SJPEG_IMPL", None)
                    else:
                        os.environ["SJPEG_IMPL"] = before
    return outs


def step_xsim(a):
    run("xsim_vectors", f"{sys.executable} vivado/run_vivado_day.py vectors", dry=a.dry_run)
    sim = "vivado\\run_xsim.bat" if WIN else "bash vivado/run_xsim.sh"
    run("xsim_run", sim, check=r"XSIM RESULT: PASS", dry=a.dry_run)
    run("xsim_check", f"{sys.executable} vivado/run_vivado_day.py check", dry=a.dry_run)
    if any(s in a.steps for s in ("lanes", "bd_lanes", "bd_lanes4", "bd_lanes4hd", "bd_lanes4yuyv")):
        # the contract-v3 lane encoder in XSim too
        run("xsim_vectors_v3", f"{sys.executable} vivado/run_vivado_day.py vectors --v3", dry=a.dry_run)
        run("xsim_run_v3", f"{sim} batch xsim_work_v3", check=r"XSIM RESULT: PASS", dry=a.dry_run)
        run("xsim_check_v3", f"{sys.executable} vivado/run_vivado_day.py check --dir vivado/xsim_work_v3",
            dry=a.dry_run)
    if "lanes" in a.steps or "bd_lanes4" in a.steps:    # and the 4-lane encoder (dut4) on the same frames
        run("xsim_vectors_v3l4", f"{sys.executable} vivado/run_vivado_day.py vectors --v3 --lanes 4", dry=a.dry_run)
        run("xsim_run_v3l4", f"{sim} batch xsim_work_v3l4", check=r"XSIM RESULT: PASS", dry=a.dry_run)
        run("xsim_check_v3l4", f"{sys.executable} vivado/run_vivado_day.py check --dir vivado/xsim_work_v3l4",
            dry=a.dry_run)


def step_ooc(a):
    jobs = [("ooc_secure_jpeg_top", "vivado/vivado_ooc.tcl", "secure_jpeg_top 10.0")]
    for per in a.periods:               # clock sweep (research R5): which block limits 125 / 150 / 166 MHz?
        jobs.append((f"ooc_period_{per}ns", "vivado/vivado_ooc.tcl", f"secure_jpeg_top {per}"))
    for w in a.maxw:                    # memory sweep: line buffers for 2^w-pixel lines
        jobs.append((f"ooc_maxw{w}", "vivado/vivado_ooc.tcl", f"secure_jpeg_top 10.0 LOG_MAXW {w}"))
    out = vivado_many(a, jobs).get("ooc_secure_jpeg_top")
    if a.blocks:
        for b in BLOCKS:
            vivado(f"ooc_{b}", "vivado/vivado_ooc.tcl", f"{b} 10.0", r"RESULT top=", a.dry_run)
    if a.fmax and not a.dry_run:
        m = re.search(r"WNS=(-?[\d.]+)ns", out or "")
        if m:
            wns = float(m.group(1))
            period = max(4.0, round((10.0 - wns) * 1.05 * 2) / 2)      # 5 % margin, 0.5 ns steps
            if abs(period - 10.0) >= 0.5:
                vivado(f"ooc_fmax_{period}ns", "vivado/vivado_ooc.tcl", f"secure_jpeg_top {period}", r"RESULT top=")
            else:
                print("fmax run skipped: slack at 100 MHz is too small to suggest a faster clock")


def step_lanes(a):
    """Contract-v3 lane encoder: area and timing (OOC). 2 lanes with 2048-pixel lines (720p) and 4 lanes
    with 1024-pixel lines (640x480, the PYNQ-Z2 image), each at 100 MHz and at every --periods clock."""
    two = "secure_jpeg_lanes_top {} LANES 2 LOG_L 1"
    four = "secure_jpeg_lanes_top {} LANES 4 LOG_L 2 LOG_MAXW 10"
    jobs = [("ooc_lanes2", "vivado/vivado_ooc.tcl", two.format("10.0"))]
    jobs += [(f"ooc_lanes2_{per}ns", "vivado/vivado_ooc.tcl", two.format(per)) for per in a.periods]
    jobs += [("ooc_lanes4", "vivado/vivado_ooc.tcl", four.format("10.0"))]
    # run 10: does the 4-lane encoder close 125 / 150 / 166 MHz too?
    jobs += [(f"ooc_lanes4_{per}ns", "vivado/vivado_ooc.tcl", four.format(per)) for per in a.periods]
    # and 4 lanes with 2048-pixel lines (1080p): one line-buffer set per lane (NBUF = 1) makes it fit;
    # 4 lanes with YUYV input (PIXFMT = 1, four pixels per beat, no colour conversion)
    jobs += [("ooc_lanes4_hd", "vivado/vivado_ooc.tcl", "secure_jpeg_lanes_top 10.0 LANES 4 LOG_L 2 LOG_MAXW 11 NBUF 1"),
             ("ooc_lanes4_nbuf1", "vivado/vivado_ooc.tcl", "secure_jpeg_lanes_top 10.0 LANES 4 LOG_L 2 LOG_MAXW 10 NBUF 1"),
             ("ooc_lanes4_yuyv", "vivado/vivado_ooc.tcl", "secure_jpeg_lanes_top 10.0 LANES 4 LOG_L 2 LOG_MAXW 10 PIXFMT 1")]
    vivado_many(a, jobs)


POWER_RUNS = [   # (tag, contract flag, modes, OOC report folder, testbench instance)
    ("v2", "", (0, 2, 4), "vivado_secure_jpeg_top", "tb_secure_jpeg_top/dut"),
    ("v3", "--v3", (2, 5), "vivado_secure_jpeg_lanes_top_lanes2_log_l1", "tb_secure_jpeg_top/dut3"),
    ("v3l4", "--v3 --lanes 4", (2, 5), "vivado_secure_jpeg_lanes_top_lanes4_log_l2_log_maxw10",
     "tb_secure_jpeg_top/dut4"),
]


def step_power(a):
    """Post-route power with simulated switching activity . For each routed
    OOC design and mode: XSim encodes one --power-size scene frame with SAIF logging on, then Vivado
    reads the SAIF into the routed checkpoint and reports power."""
    sim = "vivado\\run_xsim.bat" if WIN else "bash vivado/run_xsim.sh"
    for tag, flag, modes, folder, inst in POWER_RUNS:
        if a.only and not any(w == tag or w in f"power_{tag}" for w in a.only) and \
                not any(w.startswith("ooc") for w in a.only):
            continue
        dcp = ROOT / "sim_build" / folder / "routed.dcp"
        if not dcp.exists() and not a.dry_run:
            print(f"\n=== power_{tag}: skipped, no {dcp.relative_to(ROOT)} (run --steps "
                  f"{'ooc' if tag == 'v2' else 'lanes'} first)")
            RESULTS.append((f"power_{tag}", "FAIL", 0.0, ""))
            continue
        for m in modes:
            work = f"xsim_power_{tag}_E{m}"
            wdir = ROOT / "vivado" / work
            run(f"power_vectors_{tag}_E{m}", f"{sys.executable} vivado/run_vivado_day.py vectors {flag} "
                f"--scene {a.power_size} --modes {m} --out vivado/{work}", dry=a.dry_run)
            if not a.dry_run:
                wdir.mkdir(parents=True, exist_ok=True)
                (wdir / "saif.tcl").write_text(
                    "# written by run_vivado_day.py --steps power\n"
                    "open_saif activity.saif\n"
                    f"log_saif [get_objects -r /{inst}/*]\n"
                    "run all\n"
                    "close_saif\n"
                    "quit\n")
            run(f"power_xsim_{tag}_E{m}", f"{sim} saif {work}", check=r"XSIM RESULT: PASS", dry=a.dry_run)
            rpt = (ROOT / "sim_build" / folder / f"power_saif_{tag}_E{m}.txt").relative_to(ROOT).as_posix()
            saif = (wdir / "activity.saif").relative_to(ROOT).as_posix()
            vivado(f"power_report_{tag}_E{m}", "vivado/power_saif.tcl",
                   f"{dcp.relative_to(ROOT).as_posix()} {saif} {inst} {rpt}", r"RESULT power_saif", a.dry_run)


# overlay clocks to try when the requested one misses timing (run 3: -0.24 ns). The PS makes FCLK0 by
# dividing its 1 GHz IO PLL, so 166 / 142 / 125 MHz are exact (divide by 6 / 7 / 8).
FALLBACK_MHZ = (166, 142, 125, 100, 90, 80)


def overlay_wns(out):
    m = re.search(r"RESULT overlay (?:design=\w+ )?fclk=(\d+)MHz WNS=(-?[\d.]+)ns", out or "")
    return float(m.group(2)) if m else None


def step_bd(a, design="v2"):
    overlay = ROOT / "system" / "board" / "overlay"
    rpt = overlay if design == "v2" else overlay / design
    base = "block_design" if design == "v2" else f"block_design_{design}"
    clocks = [a.fclk] + ([] if a.no_fallback else [f for f in FALLBACK_MHZ if f < a.fclk])
    if a.fclk > 100 and not a.no_fallback:
        clocks = [f for f in clocks if f >= 100]        # a fast try falls back to 100 MHz, not below
    for i, f in enumerate(clocks):
        name = base if i == 0 else f"{base}_{f}MHz"
        out = vivado(name, "system/board/block_design.tcl", f"{f} {a.jobs} {design}", r"RESULT overlay",
                     a.dry_run)
        if a.dry_run:
            return
        if (rpt / "timing.txt").exists():             # keep every attempt's timing report
            shutil.copy(rpt / "timing.txt", rpt / f"timing_{f}MHz.txt")
        wns = overlay_wns(out)
        if wns is not None and wns >= 0:
            print(f"overlay meets timing at {f} MHz (WNS {wns:+.3f} ns)")
            break
        if f != clocks[-1]:
            print(f"overlay misses timing at {f} MHz (WNS {wns} ns): retrying at {clocks[i + 1]} MHz")
        else:
            print(f"overlay misses timing at {f} MHz (WNS {wns} ns) and no lower clock is left to try")
    have = [f.name for f in overlay.glob("secure_jpeg*.*")] if overlay.exists() else []
    print(f"overlay files: {have or 'none'}")


def step_parse(a):
    run("parse_reports", f"{sys.executable} vivado/run_vivado_day.py parse", dry=a.dry_run)
    if not a.dry_run:
        run("paper_tables", f"{sys.executable} -m system.figures.paper_tables --root sim_out "
                            f"--out sim_out/paper_tables.md")


def step_collect(a):
    """Pack the results into one zip: summary, paper tables, every report (no bitstream)."""
    import zipfile
    if a.dry_run:
        RESULTS.append(("collect", "DRY", 0.0, ""))
        print("\n=== collect (dry run: would write vivado_results_<date>.zip)")
        return
    stamp = time.strftime("%Y%m%d_%H%M")
    zpath = ROOT / f"vivado_results_{stamp}.zip"
    lines = [f"{n:<28}{st:<6}{dt / 60:>6.1f} min   {Path(log).name if log else ''}" for n, st, dt, log in RESULTS]
    for log in sorted(LOGS.glob("*.log")):
        txt = log.read_text(errors="replace")
        keep = [l for l in txt.splitlines() if l.startswith(("RESULT", "XSIM RESULT", "CHECK"))]
        errs = [l for l in txt.splitlines() if "ERROR" in l][:5]
        if keep or errs:
            lines += ["", f"--- {log.name}"] + keep + errs
    info = run_info()
    lines = [f"git commit {info['commit']}{' (with uncommitted changes)' if info['dirty'] else ''}, "
             f"branch {info['branch']}, implementation strategy {info['impl']}"] + \
            [f"bitstream {b['file']}  sha256 {b['sha256']}  {b['bytes']} bytes" for b in info["bitstreams"]] + \
            [""] + lines
    (ROOT / "sim_out" / "vivado").mkdir(parents=True, exist_ok=True)
    (ROOT / "sim_out" / "vivado" / "run_info.json").write_text(json.dumps(info, indent=1))
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("summary.txt", "\n".join(lines) + "\n")
        for f in sorted((ROOT / "sim_out" / "vivado").glob("*")) if (ROOT / "sim_out" / "vivado").exists() else []:
            z.write(f, f"sim_out/vivado/{f.name}")
        reports = ("timing*.txt", "utilization*.txt", "power.txt", "power_saif_*.txt")
        ov = ROOT / "system" / "board" / "overlay"
        for d in sorted((ROOT / "sim_build").glob("vivado_*")) + [ov] + [ov / x for x in
                                                                        ("lanes", "lanes4", "lanes4hd", "lanes4yuyv", "lanestamper")]:
            for pat in reports:
                for f in sorted(d.glob(pat)) if d.is_dir() else []:
                    z.write(f, f"{d.name}/{f.name}")
        for n, st, _, log in RESULTS:                  # failed steps: the last 300 lines of their logs
            if st == "FAIL" and log and Path(log).exists():
                z.writestr(f"failed_logs/{Path(log).name}",
                           "\n".join(Path(log).read_text(errors="replace").splitlines()[-300:]))
    RESULTS.append(("collect", "PASS", 0.0, str(zpath)))
    print(f"\n=== collect\nSend this file: {zpath}")


def run_info():
    """Which RTL a run implemented and which bitstreams it left: the git commit (and whether the
    working tree had uncommitted changes) and the SHA-256 of every overlay .bit/.hwh. Board results
    are only comparable with the Vivado numbers of the same commit and the same bitstream."""
    import hashlib

    def git(*args):
        try:
            return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=30).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return ""
    ov = ROOT / "system" / "board" / "overlay"
    bits = []
    for f in sorted(ov.glob("secure_jpeg*.bit")) + sorted(ov.glob("secure_jpeg*.hwh")) if ov.exists() else []:
        bits.append(dict(file=f.name, bytes=f.stat().st_size, sha256=hashlib.sha256(f.read_bytes()).hexdigest(),
                         modified=time.strftime("%Y-%m-%d %H:%M", time.localtime(f.stat().st_mtime))))
    return dict(commit=git("rev-parse", "HEAD") or "unknown", branch=git("rev-parse", "--abbrev-ref", "HEAD"),
                dirty=bool(git("status", "--porcelain", "--untracked-files=no", "rtl", "vivado", "system/board")),
                impl=os.environ.get("SJPEG_IMPL", "perf"), date=time.strftime("%Y-%m-%d %H:%M"), bitstreams=bits)


def check_python():
    """The XSim step runs the golden model, which needs numpy and Pillow. Fail in seconds, not
    after an hour of Vivado runs (bug #18: `exec python ...` typed in the Vivado Tcl console
    starts Vivado's bundled Python, which has numpy but not Pillow)."""
    missing = []
    for mod, pkg in (("numpy", "numpy"), ("PIL", "pillow")):
        try:
            __import__(mod)
        except ImportError:
            missing.append(pkg)
    if missing:
        vivado_py = "vivado" in sys.executable.lower() or "xilinx" in sys.executable.lower()
        sys.exit(f"This Python ({sys.executable}) lacks {', '.join(missing)}.\n"
                 + ("It is Vivado's own Python: do not start this script from the Vivado Tcl console.\n"
                    if vivado_py else "")
                 + "Use your normal Python: open a Command Prompt, run settings64.bat (puts vivado on the\n"
                   "PATH), cd to the repository, then once:  python -m pip install numpy pillow\n"
                   "or skip the simulation:  --steps ooc bd parse")


def day_main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--steps", nargs="+", default=["xsim", "ooc", "bd", "parse"],
                    choices=["xsim", "ooc", "lanes", "bd", "bd_lanes", "bd_lanes4", "bd_lanes4hd", "bd_lanes4yuyv",
                             "bd_tamper", "power", "parse"])
    ap.add_argument("--power-size", default="320x240",
                    help="WxH of the scene frame whose switching activity the power step records")
    ap.add_argument("--blocks", action="store_true", help="also implement each main block on its own")
    ap.add_argument("--fmax", action="store_true", help="re-run the top at the clock the slack suggests")
    ap.add_argument("--fclk", type=int, default=100, help="PL clock of the overlay in MHz (block design)")
    ap.add_argument("--periods", type=float, nargs="*", default=[],
                    help="also run the encoder at these clock periods in ns (clock sweep, e.g. 8.0 6.667)")
    ap.add_argument("--maxw", type=int, nargs="*", default=[],
                    help="also run the encoder with LOG_MAXW = these values (memory sweep, e.g. 9 10)")
    ap.add_argument("--jobs", type=int, default=2, help="parallel runs in the block design (each ~2 GB RAM)")
    ap.add_argument("--only", nargs="+", default=[],
                    help="only the out-of-context runs / power runs whose name contains one of these words, "
                         "e.g. --only ooc_secure_jpeg_top (repeat one failed job) or --only v2 (power)")
    ap.add_argument("--parallel", type=int, default=1,
                    help="out-of-context runs at the same time (each ~3-4 GB RAM; 2 on a 16 GB PC)")
    ap.add_argument("--no-fallback", action="store_true",
                    help="do not retry the overlay at 90/80 MHz when it misses timing at --fclk")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    if not a.dry_run and shutil.which("vivado") is None and shutil.which("vivado.bat") is None:
        sys.exit("vivado is not on the PATH: run settings64.bat / settings64.sh first (see the top of this file)")
    if "xsim" in a.steps and not a.dry_run:
        check_python()
    t0 = time.time()
    for s in a.steps:
        if s == "bd_lanes":
            step_bd(a, "lanes")
        elif s in ("bd_lanes4", "bd_lanes4hd", "bd_lanes4yuyv"):
            step_bd(a, s[3:])
        elif s == "bd_tamper":
            step_bd(a, "lanestamper")
        else:
            globals()[f"step_{s}"](a)
    step_collect(a)
    print("\n" + "\n".join(f"{n:<28}{st:<6}{dt / 60:>6.1f} min   {log}" for n, st, dt, log in RESULTS))
    fails = [n for n, st, *_ in RESULTS if st == "FAIL"]
    print(f"\n{len(RESULTS) - len(fails)} ok, {len(fails)} failed, {(time.time() - t0) / 60:.0f} min in total")
    if not a.dry_run and "parse" in a.steps:
        print(f"Paper table: {ROOT / 'sim_out' / 'vivado' / 'vivado_tables.md'}")
    sys.exit(1 if fails else 0)


TOOLS = {"vectors": vectors_main, "check": check_main, "parse": parse_main}


def main():
    if len(sys.argv) > 1 and sys.argv[1] in TOOLS:
        TOOLS[sys.argv[1]](sys.argv[2:])
    else:
        day_main()


if __name__ == "__main__":
    main()
