"""Every remaining task that a Kaggle GPU T4 can do, in one run (GUIDE.md B2, B4, B5, B13, B15, B16, B17).
After this, the only remaining simulation-side work is the Vivado day.

RERUN = True (the default since 14 Oct 2026): the full run is done (paper/data/extra). Only two things
are repeated, with the scripts fixed after it (GUIDE.md B20, B21; docs/TESTING.md bug #16):
  * restart interval on the open sources (Sintel, Tears of Steel, Kodak): ~5 min
  * both learned attacks (L1_open, L2_all) with the new no-ciphertext control and bootstrap CI: ~60 min
Set RERUN = False to run everything again from scratch (~1.5 h).

HOW TO RUN (one Kaggle account)
  1. Notebook settings: Internet ON, Accelerator GPU T4.
  2. + Add Input -> your private clips dataset (the four test clips). Optional, if downloads are blocked:
     a dataset with the open clips / Kodak images (see OPEN_CLIPS and KODAK_URL below).
  3. Paste this whole file into ONE code cell -> Save Version -> "Save & Run All (Commit)".
  4. Download remaining_results.zip from the version's Output tab and send it.
  QUICK = True first if you want a 15-minute smoke test.

WHAT IT RUNS
  B2   open, citable clips (Blender Foundation films, CC-BY 3.0) downloaded here: leakage, jigsaw, a
       real-frame visual-security figure, and the full attack suite with an open clip as the source
  B16  the Kodak image set (24 images, free to use): leakage, jigsaw, standard metrics, restart interval
  B13  standard image-encryption metrics (key sensitivity, NPCR/UACI, entropy, correlation) on every source
  B5+B15  E5 restart interval N = 1, 2, 4, 5, 8, 10, 32 with the non-zero counting attack and a segment-level
       jigsaw solver, on every source
  B4+B17  stronger learned attacker: wider U-Net, more epochs, trained on several clips, tested on others:
       L1 = open clips only (citable), L2 = all clips
TIME (Kaggle, 4 CPU + T4): ~1.5 h (downloads ~5 min, per-source experiments ~35 min, attack suite 5 min,
learned attacks ~40 min). remaining_results.zip is rewritten after every section.
Frames from the copyrighted test clips are never saved as images; only numbers are kept for them.
"""
# ============================ SETTINGS =======================================
QUICK = False
RERUN = True                               # only the steps listed above (see the docstring)
REPO_URL = "https://github.com/bnsama29-cloud/FPGA-Video-Encryption-.git"
BRANCHES = ["main", "results-open-data"]   # the first one that has the fixed experiments is used
OPEN_CLIPS = {                              # CC-BY 3.0, (c) Blender Foundation -- cite them in the paper
    # Big Buck Bunny's 320x180 file returned HTTP 404 on 14 Oct 2026, so it is no longer listed
    "sintel_trailer": "https://download.blender.org/durian/trailer/sintel_trailer-480p.mp4",
    "tearsofsteel": "https://download.blender.org/demo/movies/ToS/tears_of_steel_720p.mov",
}
KODAK_URL = "http://r0k.us/graphics/kodak/kodak/kodim{:02d}.png"   # 24 images, released for unrestricted use
RUN = dict(open_clips=True, kodak=True, per_source=True, attack_suite=True, learned=True)
if RERUN:
    RUN.update(attack_suite=False)
# =============================================================================

import glob, json, os, pathlib, re, shutil, subprocess, sys, time, urllib.request

T_START = time.time()
ON_KAGGLE = os.path.exists("/kaggle")
WORK = pathlib.Path(os.environ.get("WORK", "/kaggle/working" if ON_KAGGLE else "/tmp/krwork"))
WORK.mkdir(parents=True, exist_ok=True)
REPO_URL = os.environ.get("REPO_URL", REPO_URL)
QUICK = os.environ.get("QUICK", str(QUICK)) == "True"
RERUN = os.environ.get("RERUN", str(RERUN)) == "True"
if not RERUN:
    RUN.update(attack_suite=True)
REPO, DATA, OUT = WORK / "repo", WORK / "opendata", "sim_out/extra"
ENV = {**os.environ, "PYTHONUNBUFFERED": "1"}
LOG = []


def sh(cmd, sec, step, tail=12, cwd=None):
    t0 = time.time()
    print(f"\n=== [{sec}] {step}   (t = {(t0 - T_START) / 60:.0f} min)\n$ {cmd}", flush=True)
    p = subprocess.run(cmd, shell=True, cwd=cwd or REPO, env=ENV, capture_output=True, text=True)
    print("\n".join((p.stdout + p.stderr).strip().splitlines()[-tail:]))
    LOG.append((sec, step, "PASS" if p.returncode == 0 else "FAIL", round(time.time() - t0, 1)))
    print(f"--> {LOG[-1][2]} in {LOG[-1][3]:.0f} s", flush=True)
    return p.returncode == 0


def checkpoint():
    res = WORK / "remaining_results"
    if res.exists():
        shutil.rmtree(res)
    res.mkdir()
    if (REPO / OUT).exists():
        shutil.copytree(REPO / OUT, res / "extra", ignore=shutil.ignore_patterns("*.npz", "*.pt", "events.jsonl"))
    (res / "run_log.json").write_text(json.dumps(dict(log=LOG, minutes=round((time.time() - T_START) / 60, 1),
                                                      quick=QUICK, sources=SOURCES), indent=1))
    subprocess.run(f"{sys.executable} -m future_work.figures.paper_tables --root {res} --out {res}/paper_tables.md",
                   shell=True, cwd=REPO, env=ENV, capture_output=True)
    shutil.make_archive(str(WORK / "remaining_results"), "zip", res)
    print(f"[checkpoint] remaining_results.zip {round((WORK / 'remaining_results.zip').stat().st_size / 1e6, 1)} MB",
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
SOURCES = {}
if REPO.exists():
    shutil.rmtree(REPO)
def has_fixes(repo):
    text = lambda f: (repo / "experiments" / f).read_text() if (repo / "experiments" / f).exists() else ""
    return "raster_solve" in text("restart_interval.py") and "no_ciphertext_prior" in text("learned_attack.py")


for b in BRANCHES:
    if sh(f"git clone --depth 1 -b {b} {REPO_URL} {REPO}", "setup", f"clone ({b})", cwd=WORK, tail=2) and has_fixes(REPO):
        break
    print(f"  branch {b} does not have the fixed experiments yet, trying the next one")
    shutil.rmtree(REPO, ignore_errors=True)
else:
    raise SystemExit("no branch with the fixed experiments (bug #16, learned control): push / merge first")
sh("python -m pip install -q cryptography scikit-image opencv-python-headless pillow matplotlib tomli numpy",
   "setup", "pip install", tail=2)
try:
    import torch
    HAVE_GPU = torch.cuda.is_available()
    print("GPU:", torch.cuda.get_device_name(0) if HAVE_GPU else "none")
except Exception:
    HAVE_GPU = False

DATA.mkdir(exist_ok=True)
inputs = [os.environ["CLIPS_DIR"]] if os.environ.get("CLIPS_DIR") else ["/kaggle/input"]
found = sorted({f for r in inputs for e in ("mp4", "mkv", "avi", "mov", "webm")
                for f in glob.glob(f"{r}/**/*.{e}", recursive=True)})
open_kw = ("bunny", "sintel", "tears", "elephant")
for f in found:
    kind = "open" if any(k in f.lower() for k in open_kw) else "private"
    SOURCES[safe(pathlib.Path(f).stem)] = dict(path=f, kind=kind)
if RUN["open_clips"] and not QUICK:
    for name, url in OPEN_CLIPS.items():
        if any(name[:5] in k.lower() for k in SOURCES):
            continue
        dest = DATA / (name + pathlib.Path(url).suffix)
        if fetch(url, dest):
            SOURCES[name] = dict(path=str(dest), kind="open")
kodak = DATA / "kodak"
if RUN["kodak"]:
    kodak.mkdir(exist_ok=True)
    have = glob.glob("/kaggle/input/**/kodim*.png", recursive=True) if ON_KAGGLE else []
    for f in have:
        shutil.copy(f, kodak / pathlib.Path(f).name)
    if len(list(kodak.glob("*.png"))) < 24 and not QUICK:
        for i in range(1, 25):
            fetch(KODAK_URL.format(i), kodak / f"kodim{i:02d}.png")
    if list(kodak.glob("*.png")):
        SOURCES["kodak"] = dict(path=str(kodak), kind="open", images=True)
SOURCES = {"synthetic": dict(path="synthetic", kind="open"), **SOURCES}
print("sources:", json.dumps(SOURCES, indent=1))
checkpoint()

# ============================ 1. PER-SOURCE EXPERIMENTS =======================
n_frames, n_jig = (2, 1) if QUICK else (20, 8)
if RUN["per_source"]:
    for name, s in SOURCES.items():
        p, img = s["path"], s.get("images")
        base = f"{OUT}/{name}"
        if RERUN:                                   # only the restart interval, only where it is missing
            if s["kind"] == "open" and name != "synthetic":
                sh(f"python experiments/restart_interval.py --video '{p}' --frames {max(2, (min(n_frames, 24) if img else n_frames) // 3)} "
                   f"--stride {1 if img else 150} --intervals 1 2 4 5 8 10 32 --name {name} "
                   f"--out {base}/restart_interval --save-images", name, "restart interval, fixed (B20)", tail=11)
                checkpoint()
            continue
        stride = 1 if img else (10 if p == "synthetic" else 150)
        nf = min(n_frames, 24) if img else n_frames
        sh(f"python experiments/measure_mode_tradeoff.py --video '{p}' --frames {nf} --stride {stride} "
           f"--size 320x240 --out {base}/mode_tradeoff.json", name, "leakage per mode (B2/B16)", tail=8)
        sh(f"python -m future_work.attacks.jigsaw_attack --video '{p}' --frames {n_jig} --stride {stride if img else 375} "
           f"--size 320x240 --out {base}/jigsaw", name, "jigsaw on E5", tail=7)
        sh(f"python experiments/standard_metrics.py --video '{p}' --frames {max(2, nf // 3)} --stride {stride} "
           f"--name {name} --out {base}/standard_metrics", name, "standard metrics (B13)", tail=9)
        save = "--save-images" if s["kind"] == "open" else ""          # never save frames of private clips
        sh(f"python experiments/restart_interval.py --video '{p}' --frames {max(2, nf // 3)} --stride {stride} "
           f"--intervals 1 2 4 5 8 10 32 --name {name} --out {base}/restart_interval {save}",
           name, "restart interval + NZCA (B5/B15)", tail=11)
        if s["kind"] == "open" and not img and p != "synthetic":
            sh(f"python -m future_work.figures.visual_security_grid --video '{p}' --frame 300 --out {base}/grid",
               name, "visual-security figure with a real frame (B2)", tail=1)
        checkpoint()

# ============================ 2. ATTACK SUITE ON AN OPEN CLIP ===================
open_videos = [k for k, s in SOURCES.items() if s["kind"] == "open" and k != "synthetic" and not s.get("images")]
if RUN["attack_suite"] and open_videos:
    v = SOURCES[open_videos[-1]]["path"]
    sh(f"python experiments/scenario.py --scenario experiments/scenarios/{'quick' if QUICK else 'full_suite'}.json "
       f"--policy threshold --out {OUT}/scenario_open --base-port 47600 --set sender.source='{v}'",
       "suite", f"11 attacks with {open_videos[-1]} as the video source (B2)", tail=8)
    checkpoint()

# ============================ 3. STRONGER LEARNED ATTACKER =====================
if RUN["learned"] and (HAVE_GPU or QUICK):
    vids = {k: s for k, s in SOURCES.items() if not s.get("images") and k != "synthetic"}
    opn = [k for k, s in vids.items() if s["kind"] == "open"]
    prv = [k for k, s in vids.items() if s["kind"] == "private"]
    pairs = []
    if len(opn) >= 2:                                  # L1: citable -- train on all open clips but one
        pairs.append(("L1_open", opn[:-1], opn[-1:]))
    if len(vids) >= 3:                                 # L2: everything, held-out test clips
        test = (prv[1::2] or prv[-1:]) + opn[-1:]
        train = [k for k in vids if k not in test]
        pairs.append(("L2_all", train, test))
    args = ("--modes E2 E5 --size 96x64 --frames 60 --test-frames 50 --stride 6 --epochs 1" if QUICK else
            "--modes E1 E2 E4 E5 --size 160x128 --frames 4000 --test-frames 800 --stride 3 --epochs 35 --width 48")
    for tag, tr, te in pairs:
        trs = ",".join(SOURCES[k]["path"] for k in tr)
        tes = ",".join(SOURCES[k]["path"] for k in te)
        sh(f"python experiments/learned_attack.py --train-source '{trs}' --test-source '{tes}' {args} "
           f"--out {OUT}/learned_{tag}", "learned", f"{tag}: train {tr} -> test {te} (B4/B17)", tail=10)
        if tag != "L1_open":                            # examples show private-clip frames: drop them
            for f in glob.glob(f"{REPO}/{OUT}/learned_{tag}/examples_*.png"):
                os.remove(f)
        checkpoint()
elif RUN["learned"]:
    print("No GPU: learned attacks skipped (Accelerator: GPU T4).")

# ============================ SUMMARY ========================================
checkpoint()
w = max(len(s) for _, s, _, _ in LOG)
print("\n" + "\n".join(f"{sec:<16}{s:<{w + 2}}{st:<6}{t:>7.0f} s" for sec, s, st, t in LOG))
fails = [f"{sec}: {s}" for sec, s, st, _ in LOG if st != "PASS"]
print(f"\n{len(LOG) - len(fails)} passed, {len(fails)} failed, {(time.time() - T_START) / 3600:.2f} h")
if fails:
    print("FAILED:", *fails, sep="\n  ")
print("Download remaining_results.zip from the Output tab.")
