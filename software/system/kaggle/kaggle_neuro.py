"""Paper 2 (event-camera encryption) on Kaggle: data, N5 count cache, N3, N6, N4 and the CPU experiments (DESIGN §8.4).

HOW TO RUN (two Kaggle accounts, one PART each, in parallel)
  1. In each account: New Notebook, Internet ON, Accelerator GPU T4. No inputs to attach: DVS Gesture and FireNet
     come from DATA_ZIP (Google Drive), N-MNIST and Event-ReId from their sources. ("C" = N6 only, optional.)
  2. Paste this whole file into ONE code cell, set PART, run QUICK = True first (about 20-30 min; the assertions of
     DESIGN §8.4 fail fast), then QUICK = False with "Save Version -> Save & Run All (Commit)".
  3. Output: neuro_results_<PART>.zip (sim_out/neuro/ of every step, data manifests, meta_budget.json with the
     measured time and disk per step, run_log.md), rewritten after every step (checkpoint()), so a crash or the
     12-hour limit still leaves the finished steps. Copy each unchanged into results/simulation/neuro_kaggle/<PART>/.

Order (GPU steps last, DESIGN §8.4): setup -> data (N-MNIST, DVS Gesture via Tonic 1.7.0; Event-ReId from Zenodo)
-> Event-ReId format print -> N5 count caches -> CPU experiments on real data (N4b, N5, N7, N8, N9, N11)
-> N3 (E2VID / FireNet downloaded at run time into /kaggle/working, GPL code never committed) -> N6 -> N4.
Paper 1's Kaggle quota comes first: start this only when paper 1 has no pending Kaggle step.
"""
# ============================ SETTINGS ===========================================================
QUICK = True                     # True: ~20 min smoke run with the §8.4 assertions; False: the paper run
PART = "A"                       # one part per Kaggle account, run in parallel (both GPU T4):
                                 #   "A"  N-MNIST + DVS Gesture + Event-ReId: N5 caches and analysis, N4b, N7, N8,
                                 #        N9, N11 (CPU), then N6 (GPU, frame CNN, 3 seeds)          (~6-9 h)
                                 #   "B"  Event-ReId only: N3 (E2VID, FireNet), then N4            (~4-6 h)
                                 #   "C"  N6 only (optional third account)                         (~3-4 h)
                                 # env STEPS narrows a part: with three accounts, A runs STEPS=cpu (no GPU step, so a
                                 # CPU session that skips the T4 queue) and C runs N6.
REPO_URL = "https://github.com/bnsama29-cloud/FPGA-Video-Encryption-.git"
BRANCH = "neuromorphic"
KEYS = 5                         # independent master keys (N3, N4)
SEEDS = [0, 1, 2]                # N6 training seeds
E2VID_URL = "http://rpg.ifi.uzh.ch/data/E2VID/models/E2VID_lightweight.pth.tar"
E2VID_REPO = "https://github.com/uzh-rpg/rpg_e2vid.git"
# One zip with the files that cannot be downloaded reliably from their sources: ibmGestureTrain.tar.gz,
# ibmGestureTest.tar.gz (DVS Gesture; figshare refused some hosts) and firenet_1000.pth.tar. Each run takes only the
# members it needs (HTTP range requests: part B reads 0.5 MB, not 3 GB). Files attached as a Kaggle dataset (archives
# or folders Kaggle unpacked) are used first; None = attached inputs and the original sources only.
DATA_ZIP = "https://drive.google.com/file/d/10lsAYQsfsbdzGWrA0LGmoyUqisoYGINq/view?usp=sharing"
FIRENET_CKPT = "auto"            # "auto": firenet_1000.pth.tar from the attached inputs, else from DATA_ZIP; or a path /
                                 # https URL; None = FireNet skipped. Checked against CKPT_SHA256 either way.
FIRENET_REPO = "https://github.com/cedric-scheerlinck/rpg_e2vid.git"   # fork with the FireNet model class
FIRENET_BRANCH = "cedric/firenet"
CKPT_SHA256 = {                  # name -> sha256; a name not listed is recorded in meta_budget.json, not checked
    "firenet": "a64af3191a00e9f01cd47d086d9a88c35ff1e63756566ca44b4ff02301ca696e",   # firenet_1000.pth.tar, 7 Nov 2026
}
# =================================================================================================

import hashlib, json, os, pathlib, re, shutil, signal, subprocess, sys, time, urllib.request, zipfile

T0 = time.time()
ON_KAGGLE = os.path.exists("/kaggle")
ON_COLAB = not ON_KAGGLE and os.path.isdir("/content") and "COLAB_RELEASE_TAG" in os.environ
COLAB_DRIVE = pathlib.Path("/content/drive/MyDrive/kneuro_results")   # results copied here when Drive is mounted
REPO_URL = os.environ.get("REPO_URL", REPO_URL)      # overridable for a local dry run (as in paper 1's kaggle_runs.py)
BRANCH = os.environ.get("BRANCH", BRANCH)
WORK = pathlib.Path(os.environ.get("WORK", "/kaggle/working" if ON_KAGGLE else
                                   "/content/kneuro" if ON_COLAB else "/tmp/kneuro"))
WORK.mkdir(parents=True, exist_ok=True)
QUICK = os.environ.get("QUICK", str(QUICK)) == "True"
PART = os.environ.get("PART", PART).upper()          # the notebook cell sets PART / QUICK and runs this file
if PART not in ("A", "B", "C"):
    raise SystemExit(f"PART must be A, B or C, not {PART!r}")
REPO = WORK / "repo"
def _data_dir():
    """data/ goes to the disk with the most free space among /kaggle/working, /kaggle/temp and /tmp (env DATA
    overrides): unpacked DVS Gesture alone is 16 GB, and /kaggle/working showed 20.9 GB free in the 7 Nov runs.
    Nothing in data/ is part of the results (the manifests are copied into the zip)."""
    if os.environ.get("DATA"):
        d = pathlib.Path(os.environ["DATA"])
        d.mkdir(parents=True, exist_ok=True)
        return d
    cands = [WORK / "data"] + ([pathlib.Path("/kaggle/temp/kneuro_data"), pathlib.Path("/tmp/kneuro_data")]
                               if ON_KAGGLE else [])
    usable = []
    for d in cands:
        try:                                          # the folder must exist before its free space is read (the
            d.mkdir(parents=True, exist_ok=True)      # 15 Nov run stopped on a /kaggle/temp/kneuro_data never created)
            if os.access(d, os.W_OK):
                usable.append(d)
        except OSError:
            pass
    return max(usable, key=lambda d: shutil.disk_usage(d).free)


DATA = _data_dir()
OUT = REPO / "sim_out" / "neuro"
INPUTS = WORK / "inputs"             # members extracted from DATA_ZIP
LOGS = WORK / "logs"                 # the full output of every step (run_log.md keeps only the tails)
ENV = {**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONPATH": f"{REPO}/software:{REPO}"}
LOG, BUDGET = [], {}


def free_gb(p=WORK):
    p = pathlib.Path(p)
    while not p.exists() and p != p.parent:          # a folder not created yet: its disk is its parent's
        p = p.parent
    return shutil.disk_usage(p).free / 1e9


STEP_S = 900 if QUICK else 7200     # per-step limit (paper 1's kaggle_runs.py gives every step one too)
GPU_S = None if QUICK else 4 * 3600  # N3, N4 and N6 per dataset (DESIGN §8.4 guesses: 2, 2-4 and 3 GPU-h)
DEADLINE_S = 11.3 * 3600             # stop starting steps before Kaggle's 12-hour limit; checkpoint() keeps the rest


def sh(cmd, step, cwd=None, check=False, limit=None, want=None):
    """Run one step with a time limit; ok only if rc 0 and, when given, `want` appears in the output
    (experiments print "wrote <file>"). The first QUICK run had no limit: part A's N9 took 58 min (TESTING bug #53).
    The step runs in its own process group and the whole group is killed at the limit, so a timed-out step cannot
    keep a GPU or CPU busy under the next ones (paper 1's kaggle_runs.py, bug #14). Its full output goes to
    logs/<step>.log, which is in the zip."""
    t0 = time.time()
    left = DEADLINE_S - (t0 - T0)
    lim = min(limit or STEP_S, left - 600)
    print(f"\n=== {step} (limit {lim / 60:.0f} min): {cmd}", flush=True)
    full = ""
    if lim <= 0:
        st = "SKIPPED: Kaggle 12-hour budget used up"
    else:
        p = subprocess.Popen(cmd, shell=True, cwd=cwd or REPO, env=ENV, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, text=True, errors="replace", start_new_session=True)
        try:
            full, _ = p.communicate(timeout=lim)
            st = ("ok" if (want is None or want in full) else f"FAILED: no '{want}' in the output") \
                if p.returncode == 0 else f"FAILED rc={p.returncode}"
        except subprocess.TimeoutExpired:
            try:
                os.killpg(p.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            full, _ = p.communicate()
            st = f"TIMEOUT after {lim / 60:.0f} min"
    LOGS.mkdir(parents=True, exist_ok=True)
    (LOGS / (re.sub(r"[^A-Za-z0-9._-]+", "_", step) + ".log")).write_text(f"$ {cmd}\n\n{full}\n{st}\n", encoding="utf-8")
    out = full[-4000:]
    print(out, st, flush=True)
    LOG.append((step, st, round(time.time() - t0, 1), out[-600:]))
    BUDGET[step] = {"seconds": round(time.time() - t0, 1), "free_gb_after": round(free_gb(), 2), "status": st}
    if check and st != "ok":
        checkpoint()
        raise SystemExit(f"{step} failed: stop (QUICK assertion)")
    return st == "ok"


def checkpoint():
    z = WORK / f"neuro_results_{PART}.zip"
    (WORK / "run_log.md").write_text("# kaggle_neuro run\n\n| step | status | s |\n|---|---|---|\n" + "\n".join(
        f"| {s} | {st} | {t} |" for s, st, t, _ in LOG) + "\n\n" + "\n\n".join(
        f"## {s}\n```\n{o}\n```" for s, st, _, o in LOG if st != "ok"), encoding="utf-8")
    (WORK / "meta_budget.json").write_text(json.dumps({"quick": QUICK, "branch": BRANCH, "commit": COMMIT,
                                                       "part": PART, "run": sorted(globals().get("RUN", ())),
                                                       "steps": BUDGET,
                                                       "total_s": round(time.time() - T0)}, indent=1))
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as f:
        for p in [WORK / "run_log.md", WORK / "meta_budget.json"]:
            f.write(p, p.name)
        if OUT.exists():
            for p in OUT.rglob("*"):
                if p.is_file() and p.suffix in (".json", ".md", ".jsonl", ".npz"):
                    f.write(p, "sim_out/neuro/" + p.relative_to(OUT).as_posix())
        for p in DATA.glob("*/MANIFEST.json"):
            f.write(p, "data_manifests/" + p.parent.name + ".json")
        for p in sorted(LOGS.glob("*.log")):
            f.write(p, "logs/" + p.name)
    print(f"checkpoint: {z} ({z.stat().st_size / 1e6:.1f} MB), {time.time() - T0:.0f} s so far", flush=True)
    if ON_COLAB and COLAB_DRIVE.parent.is_dir():      # Colab deletes the VM on a disconnect; Drive keeps the zip
        COLAB_DRIVE.mkdir(exist_ok=True)
        shutil.copy(z, COLAB_DRIVE / z.name)


def fetch(url, dst, name):
    if not dst.exists():
        if os.path.exists(url):                      # a file of an attached Kaggle dataset
            shutil.copy(url, dst)
        elif url.startswith(("http://", "https://")):
            urllib.request.urlretrieve(url, dst)
        else:
            raise FileNotFoundError(f"{name}: {url} does not exist; attached inputs are under /kaggle/input "
                                    f"(add the dataset with the checkpoint as input)")
    h = hashlib.sha256(dst.read_bytes()).hexdigest()
    want = CKPT_SHA256.get(name)
    if want and h != want:
        raise SystemExit(f"{name}: SHA-256 {h} != pinned {want}")
    BUDGET[f"ckpt_{name}"] = {"sha256": h, "url": url}
    return dst


# ---------------------------------------------------------------- setup
# Always a fresh clone (paper 1 does the same): in an interactive Kaggle session /kaggle/working survives a re-run of
# the cell, and the old `if not REPO.exists()` kept running the code of the first run after every push.
COMMIT = None
if REPO.exists():
    shutil.rmtree(REPO)
if LOGS.exists():
    shutil.rmtree(LOGS)
sh(f"git clone --depth 1 -b {BRANCH} {REPO_URL} {REPO}", "clone", cwd=WORK, check=True)
COMMIT = subprocess.run(["git", "-C", str(REPO), "log", "-1", "--format=%h %cI %s"], capture_output=True,
                        text=True).stdout.strip()
print("code:", COMMIT, flush=True)
# scipy, pandas and scikit-image are on Kaggle's image; listed so that the run does not depend on it
sh(f"{sys.executable} -m pip install -q -e . tonic==1.7.0 expelliarmus zstandard snntorch h5py scipy pandas "
   f"scikit-image", "pip", check=QUICK)
sh(f"{sys.executable} -c \"import tonic, torch; print('tonic', tonic.__version__, 'torch', torch.__version__, "
   f"'cuda', torch.cuda.is_available())\"", "assert imports", check=QUICK)
print(f"free disk after setup: {free_gb():.1f} GB at {WORK}; data in {DATA} ({free_gb(DATA):.1f} GB free)", flush=True)

# ---------------------------------------------------------------- data
def plan(part, steps=None):
    """Step groups of a part; env STEPS (comma list of cpu, n3, n4, n6) narrows it. With three accounts part C runs
    N6, so part A runs STEPS=cpu: no GPU step left, a CPU session that does not wait in the T4 queue (16 Nov)."""
    run = {"A": {"cpu", "n6"}, "B": {"n3", "n4"}, "C": {"n6"}}[part]
    if steps:
        want = {s.strip().lower() for s in steps.split(",") if s.strip()}
        if not want <= run:
            raise SystemExit(f"STEPS {sorted(want - run)} are not part of part {part} ({sorted(run)})")
        run = want
    return run


RUN = plan(PART, os.environ.get("STEPS"))
NEED = {"A": "nmnist dvsgesture eventreid", "B": "eventreid", "C": "nmnist dvsgesture"}[PART]
print("steps:", sorted(RUN), flush=True)
ZIP_ARG = f"--zip-url '{DATA_ZIP}'" if DATA_ZIP else ""
sh(f"{sys.executable} software/scripts/get_events.py --out {DATA} {NEED} --inputs /kaggle/input --inputs {INPUTS} "
   f"{ZIP_ARG}", "data", check=True)   # never run hours on missing data
if "eventreid" in NEED:
  sh(f"{sys.executable} -c \"import json; from neuro import datasets; "
   f"print(json.dumps(datasets.describe_eventreid('{DATA}/eventreid'), indent=1))\"", "eventreid format",
   check=QUICK)
print(f"free disk after data: {free_gb():.1f} GB at {WORK}, {free_gb(DATA):.1f} GB at {DATA}")
BUDGET["data_dir"] = {"path": str(DATA), "free_gb_after": round(free_gb(DATA), 2)}
checkpoint()

# ---------------------------------------------------------------- N5 count caches (Tonic needed only here)
if "cpu" in RUN:
    lim = 200 if QUICK else 0
    for ds in ("nmnist", "dvsgesture", "eventreid"):
        # QUICK: samples spread over every class / person (neuro_common.load_samples strides), not the first ones
        splits = "['train', 'test']" if ds != "eventreid" else "['all']"
        sh(f"{sys.executable} -c \"import sys; sys.path.insert(0, 'experiments'); import neuro_common as C; "
           f"from neuro import datasets as D; "
           f"S = [s for sp in {splits} for s in C.load_samples('{ds}', '{DATA}/{ds}', sp, {lim} or None)]; "
           f"print(D.cache_counts(((e, l, g, m) for e, l, g, m, _ in S), '{OUT}/n5/{ds}_counts.npz'), 'samples')\"",
           f"N5 cache {ds}")
    checkpoint()

# QUICK is the smoke run of DESIGN §8.4: every experiment with its own --quick sample count (3-12 samples). The old
# `--limit 20` overrode those counts, so QUICK sealed 20 full recordings per step and took hours (part A, 7 Nov).
q = "--quick" if QUICK else ""
# N9 seals every recording at 4 T x 4 pad policies; one Event-ReId recording (~1 M events) takes ~35 s per setting
# (profiled 15 Nov), so the default 30 recordings would need ~4.5 h. 8 recordings fit the 2-hour step limit.
N9_LIMIT = {"eventreid": "--limit 8"} if not QUICK else {}
# N11 seals each Event-ReId recording at ~9 settings (bandwidth V1-V3, activity V1-V4 and padding): its QUICK default of
# 4 recordings timed out at 15 min (local dry run, 15 Nov) and the full default of 40 would take ~3.5 h.
N11_LIMIT = "--limit 2" if QUICK else "--limit 10"

# ---------------------------------------------------------------- CPU experiments on real data
if "cpu" in RUN:
    for ds in ("nmnist", "dvsgesture", "eventreid"):
        sh(f"{sys.executable} experiments/neuro_leakage.py --counts {OUT}/n5/{ds}_counts.npz --dataset {ds} "
           f"--data {DATA}/{ds} {q} --out {OUT}/n5/{ds}", f"N5 {ds}", want="wrote ")
    for ds in ("eventreid", "dvsgesture", "nmnist"):
        sh(f"{sys.executable} experiments/neuro_adjacency_attack.py --dataset {ds} --data {DATA}/{ds} {q} "
           f"--out {OUT}/n4b/{ds}", f"N4b {ds}", want="wrote ")
        sh(f"{sys.executable} experiments/neuro_overhead.py --dataset {ds} --data {DATA}/{ds} {N9_LIMIT.get(ds, '')} "
           f"{q} --out {OUT}/n9/{ds}", f"N9 {ds}", want="wrote ")
    sh(f"{sys.executable} experiments/neuro_perm_strength.py --dataset dvsgesture --data {DATA}/dvsgesture {q} "
       f"--out {OUT}/n8", "N8", want="wrote ")
    sh(f"{sys.executable} experiments/neuro_active_attacks.py --dataset nmnist --data {DATA}/nmnist {q} "
       f"--out {OUT}/n7", "N7", want="wrote ")
    sh(f"{sys.executable} experiments/neuro_fpe_utility.py --dataset eventreid --data {DATA}/eventreid {N11_LIMIT} {q} "
       f"--out {OUT}/n11", "N11", want="wrote ")
    checkpoint()

# ---------------------------------------------------------------- N3 reconstruction (GPU)
if "n3" in RUN:
    ext = WORK / "ext"
    if ext.exists():                 # a folder left by an earlier run made the clone fail: N3 then ran without E2VID
        shutil.rmtree(ext)
    ext.mkdir()
    recon = ""
    want_firenet = bool(FIRENET_CKPT)
    if want_firenet and (FIRENET_CKPT == "auto" or not (FIRENET_CKPT.startswith("http") or os.path.exists(FIRENET_CKPT))):
        # Attached inputs first: Kaggle mounts them under /kaggle/input/<name>/ (or .../datasets/<owner>/<name>/)
        # through symbolic links, which Path.rglob does not enter, hence os.walk(followlinks=True) (TESTING bug #52)
        want = "firenet_1000.pth.tar" if FIRENET_CKPT == "auto" else pathlib.Path(FIRENET_CKPT).name
        hits = sorted(pathlib.Path(d) / want for root in ("/kaggle/input", INPUTS)
                      for d, _, fs in os.walk(root, followlinks=True) if want in fs)
        print(f"FireNet: {want} in the inputs: {[str(h) for h in hits]}", flush=True)
        if not hits and DATA_ZIP and sh(f"{sys.executable} software/scripts/get_events.py --zip-url '{DATA_ZIP}' "
                                        f"--extract {want} --extract-to {INPUTS}", "FireNet from DATA_ZIP"):
            hits = [INPUTS / want]
        FIRENET_CKPT = str(hits[0]) if hits else None
    # with FireNet: the fork (it keeps E2VID's code and adds the FireNet class), else upstream E2VID
    clone = (f"git clone --depth 1 -b {FIRENET_BRANCH} {FIRENET_REPO} {ext / 'rpg_e2vid'}" if want_firenet
             else f"git clone --depth 1 {E2VID_REPO} {ext / 'rpg_e2vid'}")
    if sh(clone, "E2VID / FireNet code", cwd=WORK, check=QUICK):
        # old-numpy names used by the upstream code (patched in this downloaded copy only)
        for f in (ext / "rpg_e2vid").rglob("*.py"):
            s = f.read_text(errors="replace")
            s2 = s.replace("np.int(", "int(").replace("np.float(", "float(").replace("np.bool(", "bool(")
            if s2 != s:
                f.write_text(s2)
        ck = []
        for name, src, dst in [("e2vid", E2VID_URL, ext / "E2VID_lightweight.pth.tar")] + (
                [("firenet", FIRENET_CKPT, ext / "firenet.pth.tar")] if FIRENET_CKPT else []):
            try:                         # a missing / wrong checkpoint drops that network only, not N3 and N4
                ck.append(f"{name}={fetch(src, dst, name)}")
                LOG.append((f"ckpt {name}", "ok", 0, ""))
            except (OSError, SystemExit, ValueError) as e:
                print(f"checkpoint {name} not used: {e}", flush=True)
                LOG.append((f"ckpt {name}", "FAILED", 0, f"{type(e).__name__}: {e}"))
        missing = ["e2vid"] * (not any(c.startswith("e2vid=") for c in ck)) + \
                  ["firenet"] * (want_firenet and not any(c.startswith("firenet=") for c in ck))
        if missing and QUICK:        # DESIGN §8.4: QUICK asserts that the checkpoints load, before any paid GPU step
            checkpoint()
            raise SystemExit(f"checkpoint(s) {missing} not usable (see ckpt lines above): stop (QUICK assertion)")
        if ck:
            recon = f"--recon-repo {ext / 'rpg_e2vid'} --recon-ckpt " + " ".join(ck)
        # The E2VID / FireNet checkpoints are old full pickles (saved with torch 0.4/1.x): torch >= 2.6 refuses them
        # under weights_only=True. They are loaded only after the SHA-256 check above, from the pinned files.
        ENV["TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD"] = "1"
    sh(f"{sys.executable} experiments/neuro_recon_attack.py --dataset eventreid --data {DATA}/eventreid --keys {KEYS} "
       f"{q} {recon} --out {OUT}/n3/eventreid", "N3 eventreid", limit=GPU_S, want="wrote ")
    sh(f"{sys.executable} experiments/neuro_recon_attack.py --dataset synthetic --keys {KEYS} {q} {recon} "
       f"--out {OUT}/n3/synthetic", "N3 synthetic (v2e-lite, exact ground truth)", limit=GPU_S, want="wrote ")
    checkpoint()

# ---------------------------------------------------------------- N6 task accuracy (GPU)
def n6_args(quick, seeds):
    """N6 options. QUICK passes --quick (seed 0, 2 epochs and the small ciphertext subset CT_QUICK) plus --limit 300 for
    the clean model. Without --quick, N6 sealed its full-run subset (300 + 264 DVS Gesture recordings, ~1 h): part C's
    QUICK timed out on DVS Gesture (16 Nov, TESTING bug #64)."""
    return "--quick --limit 300" if quick else "--seeds " + " ".join(map(str, seeds))


if "n6" in RUN:
    for ds in ("nmnist", "dvsgesture"):
        sh(f"{sys.executable} experiments/neuro_task_accuracy.py --dataset {ds} --data {DATA}/{ds} "
           f"{n6_args(QUICK, SEEDS)} --out {OUT}/n6/{ds}", f"N6 {ds}", limit=GPU_S, want="wrote ")
    checkpoint()

# ---------------------------------------------------------------- N4 learned attacker (GPU, last)
if "n4" in RUN:
    sh(f"{sys.executable} experiments/neuro_learned_attack.py --dataset eventreid --data {DATA}/eventreid "
       f"--keys {KEYS} {q} --out {OUT}/n4/eventreid", "N4 eventreid", limit=GPU_S, want="wrote ")
    sh(f"{sys.executable} experiments/neuro_learned_attack.py --dataset synthetic --keys {KEYS} {q} "
       f"--out {OUT}/n4/synthetic", "N4 synthetic", limit=GPU_S, want="wrote ")
    checkpoint()
print(f"done in {(time.time() - T0) / 60:.0f} min; download {WORK / f'neuro_results_{PART}.zip'}")
