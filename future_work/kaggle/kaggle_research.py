"""Research suite in ONE Kaggle run: where the cycles go, parallel lanes, bitrate regulation and
change-driven coding (GUIDE.md B26-B30, docs/RESEARCH.md).

HOW TO RUN (one Kaggle account)
  1. Notebook settings: Internet ON. Accelerator: None is enough (no GPU needed).
  2. + Add Input -> your private clips dataset (the four test clips), as before.
  3. Paste this whole file into ONE code cell -> Save Version -> "Save & Run All (Commit)".
  4. Download research_results.zip from the version's Output tab and send it.
  QUICK = True first if you want a 10-minute smoke test.
  ONLY = ["r3_rate", "r7_size", "r8_cpa"] reruns those (~25 min; R3 after bug #25, R7 with the
  deployable padding rows, R8 the chosen-plaintext test of the E5 shuffle);
  ONLY = [] runs everything (~30 min on Kaggle in the first run, 15 Oct 2026).
  A clip from a STATIC camera (phone on a stand, a room, people walking in and out, 1-2 min) is the
  most useful extra input: the size side channel (R7) and change-driven coding (R4) are about fixed
  cameras, and film clips with cuts and camera motion are a different case. Put it in the same dataset.

WHAT IT RUNS (every number comes from a script in experiments/, as in the paper)
  R1  stall profile of the RTL (Icarus + cocotb, cycle-accurate): which link stalls, and the
      frame-size law cycles/pixel = 1.5 + a/rows, now including a 640x480 frame to test the prediction
  R2  parallel encoder lanes over restart segments: exactness checks, per-segment keystream,
      restart cost per MCU row, throughput/area projection           (every video source)
  R3  bitrate regulation (fixed, bang-bang, I, PI, FF+PI) with budget steps    (every video source)
  R4  change-driven coding with its motion leakage and the chaff/padding defences (every video source),
      plus a threshold sweep (2, 4, 8) on the open sources
  R6  E5 with keyed DCT-domain block flips/transposes vs the jigsaw and an orientation-repair attacker
  R8  chosen-plaintext attack on the E5 shuffle, transferred from frame t to frame t+1
  R7  the frame-size side channel of every level E0-E5 (event detection from sizes) and the padding /
      rate-control defences, including the quality-factor leak of rate control
TIME (Kaggle, 4 CPU): ~1.5 h (iverilog build ~6 min, R1 ~15 min, R2-R4 ~5 min per source).
Frames from the private clips are never saved; only numbers (and byte-count plots) are kept.
"""
# ============================ SETTINGS =======================================
QUICK = False
ONLY = ["r3_rate", "r7_size"]               # [] = run everything
REPO_URL = "https://github.com/bnsama29-cloud/FPGA-Video-Encryption-.git"
BRANCHES = ["research-real-clips", "main"]  # the first one that has the fixed experiments is used
OPEN_CLIPS = {                               # CC-BY 3.0, (c) Blender Foundation
    "sintel_trailer": "https://download.blender.org/durian/trailer/sintel_trailer-480p.mp4",
    "tearsofsteel": "https://download.blender.org/demo/movies/ToS/tears_of_steel_720p.mov",
}
RUN = dict(r1_stall=True, r2_lanes=True, r3_rate=True, r4_change=True, r6_transform=True, r7_size=True,
           r8_cpa=True)
if ONLY:
    RUN = {k: k in ONLY for k in RUN}
# =============================================================================

import glob, json, os, pathlib, re, shutil, subprocess, sys, time, urllib.request

T_START = time.time()
ON_KAGGLE = os.path.exists("/kaggle")
WORK = pathlib.Path(os.environ.get("WORK", "/kaggle/working" if ON_KAGGLE else "/tmp/krwork"))
WORK.mkdir(parents=True, exist_ok=True)
QUICK = os.environ.get("QUICK", str(QUICK)) == "True"
REPO, DATA = WORK / "repo", WORK / "opendata"
ENV = {**os.environ, "PYTHONUNBUFFERED": "1"}
LOG, SOURCES = [], {}
DIRS = ["stall_profile", "parallel_lanes", "rate_control", "change_driven", "block_transform", "size_leak",
        "chosen_plaintext"]


def sh(cmd, sec, step, tail=12, cwd=None):
    t0 = time.time()
    print(f"\n=== [{sec}] {step}   (t = {(t0 - T_START) / 60:.0f} min)\n$ {cmd}", flush=True)
    p = subprocess.run(cmd, shell=True, cwd=cwd or REPO, env=ENV, capture_output=True, text=True)
    print("\n".join((p.stdout + p.stderr).strip().splitlines()[-tail:]))
    LOG.append((sec, step, "PASS" if p.returncode == 0 else "FAIL", round(time.time() - t0, 1)))
    print(f"--> {LOG[-1][2]} in {LOG[-1][3]:.0f} s", flush=True)
    return p.returncode == 0


def checkpoint():
    res = WORK / "research_results"
    shutil.rmtree(res, ignore_errors=True)
    res.mkdir()
    for d in DIRS:
        if (REPO / "sim_out" / d).exists():
            shutil.copytree(REPO / "sim_out" / d, res / d, ignore=shutil.ignore_patterns("raw.json"))
    (res / "run_log.json").write_text(json.dumps(dict(log=LOG, minutes=round((time.time() - T_START) / 60, 1),
                                                      quick=QUICK, sources=SOURCES), indent=1))
    shutil.make_archive(str(WORK / "research_results"), "zip", res)
    print(f"[checkpoint] research_results.zip {round((WORK / 'research_results.zip').stat().st_size / 1e6, 2)} MB",
          flush=True)


def fetch(url, dest):
    if dest.exists() and dest.stat().st_size > 0:
        return True
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as f:
            shutil.copyfileobj(r, f)
        return dest.stat().st_size > 1000
    except Exception as e:
        print(f"  download failed: {url}: {e}")
        if dest.exists():
            dest.unlink()
        return False


def safe(name):
    return re.sub(r"[^A-Za-z0-9_-]+", "_", name.strip()).strip("_")


# ============================ 0. SETUP =======================================
shutil.rmtree(REPO, ignore_errors=True)
for b in BRANCHES:
    if sh(f"git clone --depth 1 -b {b} {REPO_URL} {REPO}", "setup", f"clone ({b})", cwd=WORK, tail=2) and \
            "DU_MAX" in (REPO / "experiments" / "rate_control.py").read_text():
        break
    print(f"  branch {b} does not have the fixed experiments (bugs #22-#26), trying the next one")
    shutil.rmtree(REPO, ignore_errors=True)
else:
    raise SystemExit("no branch with the fixed experiments: push / merge research-real-clips first")
sh("python -m pip install -q cocotb==2.1.0 cocotbext-axi==0.1.28 scikit-image opencv-python-headless "
   "pillow matplotlib tomli numpy", "setup", "pip install", tail=2)
if RUN["r1_stall"]:
    have12 = subprocess.run("iverilog -V 2>/dev/null | head -1", shell=True, capture_output=True, text=True).stdout
    if "12." not in have12:                     # the testbenches are verified with Icarus 12
        sh("apt-get update -qq && apt-get install -y -qq build-essential flex bison gperf autoconf",
           "setup", "build tools", tail=1, cwd=WORK)
        sh("rm -rf iverilog && git clone --depth 1 -b v12_0 https://github.com/steveicarus/iverilog.git && cd iverilog && "
           "sh autoconf.sh && ./configure -q && make -j4 >/dev/null && make install >/dev/null && iverilog -V | head -1",
           "setup", "Icarus Verilog 12 (~6 min)", tail=1, cwd=WORK)

DATA.mkdir(exist_ok=True)
inputs = [os.environ["CLIPS_DIR"]] if os.environ.get("CLIPS_DIR") else ["/kaggle/input"]
found = sorted({f for r in inputs for e in ("mp4", "mkv", "avi", "mov", "webm")
                for f in glob.glob(f"{r}/**/*.{e}", recursive=True)})
for f in found:
    kind = "open" if any(k in f.lower() for k in ("sintel", "tears", "bunny")) else "private"
    SOURCES[safe(pathlib.Path(f).stem)] = dict(path=f, kind=kind)
if not QUICK:
    for name, url in OPEN_CLIPS.items():
        if any(name[:5] in k.lower() for k in SOURCES):
            continue
        dest = DATA / (name + pathlib.Path(url).suffix)
        if fetch(url, dest):
            SOURCES[name] = dict(path=str(dest), kind="open")
SOURCES = {"synthetic": dict(path="synthetic", kind="open"), **SOURCES}
print("sources:", json.dumps(SOURCES, indent=1))
checkpoint()

# ============================ R1. STALL PROFILE (RTL) =========================
if RUN["r1_stall"]:
    sh("python experiments/stall_profile.py --size 128x96", "R1", "stall profile, 3 images x E0/E2/E4", tail=30)
    sizes = "64x48 128x96 160x128" if QUICK else "64x48 128x96 160x128 320x240 640x480"
    sh(f"python experiments/stall_profile.py --scaling {sizes}", "R1", "frame-size law incl. 640x480", tail=16)
    checkpoint()

# ============================ R2-R4 PER VIDEO SOURCE ==========================
nf = dict(lanes=1 if QUICK else 4, rate=30 if QUICK else 150, change=30 if QUICK else 120,
          transform=1 if QUICK else 6, size=30 if QUICK else 150)
for name, s in SOURCES.items():
    p, opn = s["path"], s["kind"] == "open"
    if RUN["r2_lanes"]:
        sh(f"python experiments/parallel_lanes.py --video '{p}' --frames {nf['lanes']} --stride 150 --name {name}",
           name, "R2 parallel lanes", tail=6)
    if RUN["r3_rate"]:
        plot = "--plot" if opn else ""
        sh(f"python experiments/rate_control.py --video '{p}' --frames {nf['rate']} --stride 2 --name {name} {plot}",
           name, "R3 bitrate regulation", tail=8)
    if RUN["r4_change"]:
        sh(f"python experiments/change_driven.py --video '{p}' --frames {nf['change']} --stride 3 --name {name}",
           name, "R4 change-driven coding", tail=12)
        if opn and not QUICK:
            for tau in (2, 8):
                sh(f"python experiments/change_driven.py --video '{p}' --frames {nf['change']} --stride 3 "
                   f"--tau {tau} --name {name}_tau{tau}", name, f"R4 threshold {tau}", tail=3)
    if RUN["r6_transform"]:
        sh(f"python experiments/block_transform.py --video '{p}' --frames {nf['transform']} --stride 150 --name {name}",
           name, "R6 E5 + block transforms", tail=6)
    if RUN["r7_size"]:
        sh(f"python experiments/size_leak.py --video '{p}' --frames {nf['size']} --stride 3 --name {name}",
           name, "R7 frame-size side channel", tail=14)
    if RUN["r8_cpa"]:
        sh(f"python experiments/chosen_plaintext.py --video '{p}' --frames {2 if QUICK else 6} --stride 150 "
           f"--name {name}", name, "R8 chosen-plaintext shuffle", tail=6)
    checkpoint()

print("\n".join(f"{s:<16}{st:<44}{r:<5}{t:>7.0f} s" for s, st, r, t in LOG))
print(f"\nDONE in {(time.time() - T_START) / 60:.0f} min -> research_results.zip")
