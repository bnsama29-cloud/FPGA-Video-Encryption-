"""Second Kaggle run: everything that needs REAL video (run this after run_all_roles.py).

Kaggle setup: upload your clips as a private Dataset (+ Create -> New Dataset), add it to the notebook
(+ Add Input), turn Internet ON and Accelerator GPU T4, paste this file into one cell and run it.
It finds the clips itself under /kaggle/input. Output: /kaggle/working/real_video_results.zip

What it runs (about 45 min with the default settings):
  1. mode trade-off (SSIM / edge leakage per mode) on every clip
  2. jigsaw attack on E5 on every clip
  3. visual-security figure on two clips
  4. attack scenario full_suite with the sender fed by a trailer and by a talking-head clip
  5. learned (neural) attack on the GPU: train on one clip, test on a DIFFERENT clip, two pairs
Never commit the clips: they are copyrighted (the repo ignores *.mp4).
"""
# ---- SETTINGS ---------------------------------------------------------------
QUICK = False            # True = tiny smoke test (~10 min)
REPO_URL = "https://github.com/bnsama29-cloud/FPGA-Video-Encryption-.git"
BRANCH = "main"          # everything is merged into main
PAIRS = None             # None = automatic; or [("/kaggle/input/x/a.mp4", "/kaggle/input/x/b.mp4"), ...] (train, test)
# -----------------------------------------------------------------------------
import glob, json, os, pathlib, shutil, subprocess, sys, time

ON_KAGGLE = os.path.exists("/kaggle")
WORK = pathlib.Path(os.environ.get("WORK", "/kaggle/working" if ON_KAGGLE else "/tmp/rvwork"))
WORK.mkdir(parents=True, exist_ok=True)
REPO_URL = os.environ.get("REPO_URL", REPO_URL); BRANCH = os.environ.get("BRANCH", BRANCH)
QUICK = os.environ.get("QUICK", str(QUICK)) == "True"
REPO = WORK / "repo"
ENV = {**os.environ, "PYTHONUNBUFFERED": "1"}
LOG = []

def sh(cmd, step, tail=15, cwd=None):
    t0 = time.time(); print(f"\n=== {step}\n$ {cmd}")
    p = subprocess.run(cmd, shell=True, cwd=cwd or REPO, env=ENV, capture_output=True, text=True)
    print("\n".join((p.stdout + p.stderr).strip().splitlines()[-tail:]))
    LOG.append((step, "PASS" if p.returncode == 0 else "FAIL", round(time.time() - t0, 1)))
    print(f"--> {LOG[-1][1]} in {LOG[-1][2]:.0f} s")
    return p.returncode == 0

# ---- find the clips ---------------------------------------------------------
roots = [os.environ["CLIPS_DIR"]] if os.environ.get("CLIPS_DIR") else ["/kaggle/input"]
found = sorted({f for r in roots for ext in ("mp4", "mkv", "avi", "mov", "webm") for f in glob.glob(f"{r}/**/*.{ext}", recursive=True)})
print("clips found:", *found, sep="\n  ")
assert len(found) >= 2, "need at least 2 videos: add your clip Dataset to the notebook (+ Add Input)"
CLIPS = {pathlib.Path(f).stem: f for f in found}
def pick(*words):
    for k, f in CLIPS.items():
        if any(w in k.lower() for w in words): return f
trailer = pick("avengers", "jailer", "trailer") or found[0]
talking = pick("denzel", "motivat", "challenge", "topper") or found[-1]
if PAIRS is None:
    a, b = pick("avengers"), pick("jailer")
    c, d = pick("denzel", "motivat"), pick("challenge", "topper")
    PAIRS = [p for p in ((a, b), (c, d)) if p[0] and p[1]] or [(found[0], found[1])]
print("learned-attack pairs (train -> test):", PAIRS)

# ---- setup ------------------------------------------------------------------
if REPO.exists(): shutil.rmtree(REPO)
sh(f"git clone --depth 1 -b {BRANCH} {REPO_URL} {REPO}", "clone", cwd=WORK, tail=2)
sh("python -m pip install -q scikit-image opencv-python-headless pillow matplotlib cryptography tomli numpy", "pip install", tail=3)
try:
    import torch; HAVE_GPU = torch.cuda.is_available(); print("torch", torch.__version__, "cuda", HAVE_GPU)
except Exception as e:
    HAVE_GPU = False; print("no torch:", e)

n = 3 if QUICK else 20
# 1-3: per-clip measurements
for name, f in CLIPS.items():
    stride = max(1, 3000 // n)
    sh(f"python experiments/measure_mode_tradeoff.py --video '{f}' --frames {n} --stride {stride} --size 320x240 "
       f"--out sim_out/real/{name}/mode_tradeoff.json", f"mode trade-off: {name}", tail=10)
    sh(f"python -m future_work.attacks.jigsaw_attack --video '{f}' --frames {2 if QUICK else 8} --stride {max(1, 3000 // 8)} "
       f"--size 320x240 --out sim_out/real/{name}/jigsaw", f"jigsaw on E5: {name}", tail=8)
for name, f in {"trailer": trailer, "talking": talking}.items():
    sh(f"python -m future_work.figures.visual_security_grid --video '{f}' --frame 300 --out sim_out/real/grid_{name}",
       f"visual-security figure: {name}", tail=2)

# 4: protocol on real video
if not QUICK:
    for i, (name, f) in enumerate({"trailer": trailer, "talking": talking}.items()):
        sh(f"python experiments/scenario.py --scenario experiments/scenarios/full_suite.json --policy threshold "
           f"--out sim_out/real/scenario_{name} --base-port {48200 + 200 * i} --set sender.source='{f}'",
           f"full_suite with {name} as the video source", tail=6)
else:
    sh(f"python experiments/scenario.py --scenario experiments/scenarios/quick.json --policy threshold "
       f"--out sim_out/real/scenario_trailer --base-port 48200 --set sender.source='{trailer}'", "quick scenario on trailer", tail=6)

# 5: learned attack
if HAVE_GPU or QUICK:
    for k, (tr, te) in enumerate(PAIRS):
        args = ("--modes E2 E5 --size 96x64 --frames 60 --test-frames 50 --stride 6 --epochs 1" if QUICK else
                "--modes E1 E2 E4 E5 --size 160x128 --frames 1000 --test-frames 400 --stride 3 --epochs 25")
        sh(f"python experiments/learned_attack.py --train-source '{tr}' --test-source '{te}' {args} "
           f"--out sim_out/real/learned_pair{k + 1}",
           f"learned attack pair {k + 1}: train {pathlib.Path(tr).stem} -> test {pathlib.Path(te).stem}", tail=14)
else:
    print("No GPU: learned attack skipped (Accelerator: GPU T4).")

# ---- summary + zip ----------------------------------------------------------
print("\n" + "\n".join(f"{s:<70}{st:<6}{t:>8.0f} s" for s, st, t in LOG))
print(f"\n{sum(x[1] == 'PASS' for x in LOG)} passed, {sum(x[1] == 'FAIL' for x in LOG)} failed")
out = WORK / "real_video_results"
if out.exists(): shutil.rmtree(out)
shutil.copytree(REPO / "sim_out" / "real", out)
(out / "run_summary.json").write_text(json.dumps(LOG, indent=1))
for p in out.rglob("*.npz"): p.unlink()             # big cached datasets, not needed
for p in out.rglob("*.pt"): p.unlink()
shutil.make_archive(str(WORK / "real_video_results"), "zip", out)
print("real_video_results.zip ->", round((WORK / "real_video_results.zip").stat().st_size / 1e6, 1), "MB  (download from the Output tab)")
