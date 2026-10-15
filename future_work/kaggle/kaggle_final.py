"""The last Kaggle run: every remaining simulation task that needs a GPU or long CPU time, in one cell
(GUIDE.md B9, B17, B23, B24, B25). After this, the remaining work is Vivado and the board.

HOW TO RUN (one Kaggle account)
  1. Notebook settings: Internet ON, Accelerator GPU T4 (x1 is enough).
  2. + Add Input -> your private clips dataset (the same one as before).
  3. Paste this whole file into ONE code cell -> Save Version -> "Save & Run All (Commit)".
  4. Download final_results.zip from the version's Output tab and send it.
  QUICK = True first for a ~15-minute smoke test (tiny sizes; the numbers mean nothing).

WHAT IT RUNS (each step writes its numbers under sim_out/final/, zipped after every step)
  B24  leakage per level with 60 frames per video source and 95 % bootstrap intervals
       (experiments/measure_mode_tradeoff.py), every source incl. Kodak
  B9   the stronger MST jigsaw solver on E5 (future_work/attacks/jigsaw_attack.py --solver mst), every source
  B23  person detection in the eavesdropper's pictures (experiments/recognition.py, Faster R-CNN, COCO)
  B25  the learned attacks of the paper (L1_open, L2_all = P3/P4) again, now with the frame-statistics
       controls (true and revealed per-frame colour statistics)
  B17  P5: a learned attacker trained on a public corpus (Big Buck Bunny, Elephants Dream, Tears of Steel;
       all Blender Foundation, Creative Commons Attribution) with an adversarial (PatchGAN) loss, tested
       on the Sintel trailer and the private clips it never saw
TIME (Kaggle, T4): about 3-4 h (downloads ~10 min, B24 ~40 min, B9 ~20 min, B23 ~20 min, three learned
attacks ~40-60 min each). Frames of the private clips are never saved as images; only numbers are kept.
"""
# ============================ SETTINGS =======================================
QUICK = False
REPO_URL = "https://github.com/bnsama29-cloud/FPGA-Video-Encryption-.git"
BRANCHES = ["kaggle-final", "main"]          # the first one that has recognition.py and mst_jigsaw.py
OPEN_CLIPS = {                               # CC BY 3.0, (c) Blender Foundation
    "sintel_trailer": "https://download.blender.org/durian/trailer/sintel_trailer-480p.mp4",
    "tearsofsteel": "https://download.blender.org/demo/movies/ToS/tears_of_steel_720p.mov",
}
CORPUS_DIRS = {                              # directory listings; the smallest movie file is picked at run time
    "bigbuckbunny": "https://download.blender.org/peach/bigbuckbunny_movies/",   # CC BY 3.0 (peach.blender.org/about)
    "elephantsdream": "https://download.blender.org/ED/",                         # CC BY (orange.blender.org)
}
KODAK_URL = "http://r0k.us/graphics/kodak/kodak/kodim{:02d}.png"
RUN = dict(b24_leakage=True, b9_mst=True, b23_recognition=True, b25_learned=True, b17_p5=True)
# =============================================================================

import glob, json, os, pathlib, re, shutil, subprocess, sys, time, urllib.request

T_START = time.time()
ON_KAGGLE = os.path.exists("/kaggle")
WORK = pathlib.Path(os.environ.get("WORK", "/kaggle/working" if ON_KAGGLE else "/tmp/kfwork"))
WORK.mkdir(parents=True, exist_ok=True)
QUICK = os.environ.get("QUICK", str(QUICK)) == "True"
REPO, DATA, OUT = WORK / "repo", WORK / "opendata", "sim_out/final"
ENV = {**os.environ, "PYTHONUNBUFFERED": "1"}
LOG, SOURCES, CORPUS = [], {}, {}


def sh(cmd, sec, step, tail=12, cwd=None):
    t0 = time.time()
    print(f"\n=== [{sec}] {step}   (t = {(t0 - T_START) / 60:.0f} min)\n$ {cmd}", flush=True)
    p = subprocess.run(cmd, shell=True, cwd=cwd or REPO, env=ENV, capture_output=True, text=True)
    print("\n".join((p.stdout + p.stderr).strip().splitlines()[-tail:]))
    LOG.append((sec, step, "PASS" if p.returncode == 0 else "FAIL", round(time.time() - t0, 1)))
    print(f"--> {LOG[-1][2]} in {LOG[-1][3]:.0f} s", flush=True)
    return p.returncode == 0


def checkpoint():
    res = WORK / "final_results"
    shutil.rmtree(res, ignore_errors=True)
    res.mkdir()
    if (REPO / OUT).exists():
        shutil.copytree(REPO / OUT, res / "final", ignore=shutil.ignore_patterns("*.npz", "*.pt"))
    (res / "run_log.json").write_text(json.dumps(dict(log=LOG, minutes=round((time.time() - T_START) / 60, 1),
                                                      quick=QUICK, sources=SOURCES, corpus=CORPUS), indent=1))
    shutil.make_archive(str(WORK / "final_results"), "zip", res)
    print(f"[checkpoint] final_results.zip {round((WORK / 'final_results.zip').stat().st_size / 1e6, 2)} MB", flush=True)


def fetch(url, dest):
    if dest.exists() and dest.stat().st_size > 0:
        return True
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=300) as r, open(dest, "wb") as f:
            shutil.copyfileobj(r, f)
        return dest.stat().st_size > 1000
    except Exception as e:
        print(f"  download failed: {url}: {e}")
        if dest.exists():
            dest.unlink()
        return False


def smallest_movie(listing_url):
    """Pick the smallest-resolution movie file from an Apache directory listing (names carry the size)."""
    try:
        req = urllib.request.Request(listing_url, headers={"User-Agent": "Mozilla/5.0"})
        html = urllib.request.urlopen(req, timeout=60).read().decode("utf8", "replace")
    except Exception as e:
        print(f"  listing failed: {listing_url}: {e}")
        return None
    names = sorted(set(re.findall(r'href="([^"?/]+\.(?:mp4|mov|avi|mkv|ogg|webm))"', html, re.I)))
    if not names:
        return None
    pref = ["320x180", "180p", "360p", "480p", "640x360", "854x480", "480", "720p", "1024", "1280"]
    rank = lambda n: next((i for i, k in enumerate(pref) if k in n.lower()), len(pref))
    return listing_url + sorted(names, key=lambda n: (rank(n), len(n)))[0]


def safe(name):
    return re.sub(r"[^A-Za-z0-9_-]+", "_", name.strip()).strip("_")


# ============================ 0. SETUP =======================================
shutil.rmtree(REPO, ignore_errors=True)
for b in BRANCHES:
    if sh(f"git clone --depth 1 -b {b} {REPO_URL} {REPO}", "setup", f"clone ({b})", cwd=WORK, tail=2) and \
            (REPO / "experiments" / "recognition.py").exists() and (REPO / "future_work/attacks/mst_jigsaw.py").exists():
        break
    print(f"  branch {b} does not have the final experiments, trying the next one")
    shutil.rmtree(REPO, ignore_errors=True)
else:
    raise SystemExit("no branch with experiments/recognition.py: push / merge kaggle-final first")
sh("python -m pip install -q cryptography scikit-image opencv-python-headless pillow matplotlib tomli numpy torchvision",
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
for f in found:
    kind = "open" if any(k in f.lower() for k in ("bunny", "sintel", "tears", "elephant")) else "private"
    SOURCES[safe(pathlib.Path(f).stem)] = dict(path=f, kind=kind)
if not QUICK:
    for name, url in OPEN_CLIPS.items():
        if any(name[:5] in k.lower() for k in SOURCES):
            continue
        dest = DATA / (name + pathlib.Path(url).suffix)
        if fetch(url, dest):
            SOURCES[name] = dict(path=str(dest), kind="open")
    for name, listing in CORPUS_DIRS.items():          # public training corpus for P5 (not test sources)
        url = smallest_movie(listing)
        dest = DATA / (name + (pathlib.Path(url).suffix if url else ".mp4"))
        if url and fetch(url, dest):
            CORPUS[name] = dict(path=str(dest), url=url, licence="CC BY (Blender Foundation)")
kodak = DATA / "kodak"
kodak.mkdir(exist_ok=True)
for f in (glob.glob("/kaggle/input/**/kodim*.png", recursive=True) if ON_KAGGLE else []):
    shutil.copy(f, kodak / pathlib.Path(f).name)
if len(list(kodak.glob("*.png"))) < 24 and not QUICK:
    for i in range(1, 25):
        fetch(KODAK_URL.format(i), kodak / f"kodim{i:02d}.png")
if list(kodak.glob("*.png")):
    SOURCES["kodak"] = dict(path=str(kodak), kind="open", images=True)
SOURCES = {"synthetic": dict(path="synthetic", kind="open"), **SOURCES}
print("sources:", json.dumps(SOURCES, indent=1), "\ncorpus:", json.dumps(CORPUS, indent=1))
checkpoint()

# ============================ 1. PER-SOURCE: B24, B9, B23 =====================
for name, s in SOURCES.items():
    p, img = s["path"], s.get("images")
    base = f"{OUT}/{name}"
    if RUN["b24_leakage"]:
        nf = 3 if QUICK else (24 if img else 60)
        stride = 1 if img else (10 if p == "synthetic" else 50)
        sh(f"python experiments/measure_mode_tradeoff.py --video '{p}' --frames {nf} --stride {stride} "
           f"--size 320x240 --out {base}/mode_tradeoff.json", name, "B24 leakage, 60 frames + 95 % intervals", tail=8)
    if RUN["b9_mst"]:
        sh(f"python -m future_work.attacks.jigsaw_attack --video '{p}' --frames {1 if QUICK else 8} "
           f"--stride {1 if img else 375} --size 320x240 --solver mst --out {base}/jigsaw_mst",
           name, "B9 MST jigsaw solver on E5", tail=6)
    if RUN["b23_recognition"] and (HAVE_GPU or QUICK):
        sh(f"python experiments/recognition.py --video '{p}' --frames {2 if QUICK else (24 if img else 40)} "
           f"--stride {1 if img else 30} --name {name}", name, "B23 person detection", tail=10)
        r = REPO / "sim_out" / "recognition"
        for f in r.glob(f"{name}.*"):
            pathlib.Path(REPO / base / "recognition").mkdir(parents=True, exist_ok=True)
            shutil.move(str(f), REPO / base / "recognition" / f.name)
    checkpoint()

# ============================ 2. LEARNED ATTACKS: B25 (P3/P4 again) and B17 (P5) ===
vids = {k: s for k, s in SOURCES.items() if not s.get("images") and k != "synthetic"}
opn = [k for k, s in vids.items() if s["kind"] == "open"]
prv = [k for k, s in vids.items() if s["kind"] == "private"]
args = ("--modes E2 E5 --size 96x64 --frames 60 --test-frames 50 --stride 6 --epochs 1" if QUICK else
        "--modes E1 E2 E4 E5 --size 160x128 --frames 4000 --test-frames 800 --stride 3 --epochs 35 --width 48")
pairs = []
if RUN["b25_learned"]:
    if len(opn) >= 2:
        pairs.append(("L1_open", [SOURCES[k]["path"] for k in opn[:-1]], [SOURCES[k]["path"] for k in opn[-1:]], ""))
    if len(vids) >= 3:
        test = (prv[1::2] or prv[-1:]) + opn[-1:]
        pairs.append(("L2_all", [SOURCES[k]["path"] for k in vids if k not in test],
                      [SOURCES[k]["path"] for k in test], ""))
if RUN["b17_p5"]:
    train = [c["path"] for c in CORPUS.values()] + [SOURCES[k]["path"] for k in opn if "tears" in k]
    test = [SOURCES[k]["path"] for k in opn if "sintel" in k] + [SOURCES[k]["path"] for k in prv]
    if QUICK and not train:
        train, test = ["synthetic"], ["synthetic"]
    if train and test:
        pairs.append(("P5_corpus_gan", train, test, "--adv 0.01"))
    else:
        print("P5 skipped: no public corpus downloaded", CORPUS)
if HAVE_GPU or QUICK:
    for tag, tr, te, extra in pairs:
        trs, tes = ",".join(tr), ",".join(te)
        sh(f"python experiments/learned_attack.py --train-source '{trs}' --test-source '{tes}' {args} {extra} "
           f"--out {OUT}/learned_{tag}", "learned", f"{tag}: {len(tr)} train -> {len(te)} test sources", tail=10)
        if tag != "L1_open":                            # examples show private-clip frames: drop them
            for f in glob.glob(f"{REPO}/{OUT}/learned_{tag}/examples_*.png"):
                os.remove(f)
        checkpoint()
else:
    print("No GPU: learned attacks and recognition skipped (Accelerator: GPU T4).")

# ============================ SUMMARY ========================================
checkpoint()
w = max(len(s) for _, s, _, _ in LOG)
print("\n" + "\n".join(f"{sec:<16}{s:<{w + 2}}{st:<6}{t:>7.0f} s" for sec, s, st, t in LOG))
fails = [f"{sec}: {s}" for sec, s, st, _ in LOG if st != "PASS"]
print(f"\n{len(LOG) - len(fails)} passed, {len(fails)} failed, {(time.time() - T_START) / 3600:.2f} h")
if fails:
    print("FAILED:", *fails, sep="\n  ")
print("Download final_results.zip from the Output tab.")
