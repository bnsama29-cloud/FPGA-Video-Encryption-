"""Paper 2 (event-camera encryption) on Kaggle: data, N5 count cache, N3, N6, N4 and the CPU experiments (DESIGN §8.4).

HOW TO RUN (three Kaggle accounts, one PART each, in parallel)
  1. In each account: New Notebook, Internet ON. Accelerator: None for PART "A" (CPU only, saves GPU quota),
     GPU T4 for "B" and "C". For "B" add the private dataset with firenet_1000.pth.tar as input (FIRENET_CKPT).
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
PART = "A"                       # one part per Kaggle account, run in parallel:
                                 #   "A"  CPU only (no GPU quota): N-MNIST + DVS Gesture + Event-ReId, N5 caches and
                                 #        analysis, N4b, N7, N8, N9, N11                         (~3-5 h)
                                 #   "B"  GPU: Event-ReId only: N3 (E2VID, FireNet), then N4     (~4-6 h)
                                 #   "C"  GPU: N-MNIST + DVS Gesture only: N6 (frame CNN, 3 seeds) (~3-4 h)
REPO_URL = "https://github.com/bnsama29-cloud/FPGA-Video-Encryption-.git"
BRANCH = "neuromorphic"
KEYS = 5                         # independent master keys (N3, N4)
SEEDS = [0, 1, 2]                # N6 training seeds
E2VID_URL = "http://rpg.ifi.uzh.ch/data/E2VID/models/E2VID_lightweight.pth.tar"
E2VID_REPO = "https://github.com/uzh-rpg/rpg_e2vid.git"
FIRENET_CKPT = None              # FireNet checkpoint: a path under /kaggle/input/... (upload it as a private Kaggle
                                 # dataset) or a direct https URL; None = FireNet skipped. Procedure: download
                                 # firenet_1000.pth.tar from the Google Drive link in the README of
                                 # cedric-scheerlinck/rpg_e2vid (branch cedric/firenet), upload it as a private
                                 # Kaggle dataset, add it as input, e.g.
                                 # FIRENET_CKPT = "/kaggle/input/firenet-ckpt/firenet_1000.pth.tar"
FIRENET_REPO = "https://github.com/cedric-scheerlinck/rpg_e2vid.git"   # fork with the FireNet model class
FIRENET_BRANCH = "cedric/firenet"
CKPT_SHA256 = {                  # name -> sha256; a name not listed is recorded in meta_budget.json, not checked
    "firenet": "a64af3191a00e9f01cd47d086d9a88c35ff1e63756566ca44b4ff02301ca696e",   # firenet_1000.pth.tar, 7 Nov 2026
}
# =================================================================================================

import hashlib, json, os, pathlib, shutil, subprocess, sys, time, urllib.request, zipfile

T0 = time.time()
ON_KAGGLE = os.path.exists("/kaggle")
WORK = pathlib.Path(os.environ.get("WORK", "/kaggle/working" if ON_KAGGLE else "/tmp/kneuro"))
WORK.mkdir(parents=True, exist_ok=True)
QUICK = os.environ.get("QUICK", str(QUICK)) == "True"
REPO = WORK / "repo"
DATA = WORK / "data"
OUT = REPO / "sim_out" / "neuro"
ENV = {**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONPATH": f"{REPO}/software:{REPO}"}
LOG, BUDGET = [], {}


def free_gb(p=WORK):
    return shutil.disk_usage(p).free / 1e9


def sh(cmd, step, cwd=None, check=False):
    t0 = time.time()
    print(f"\n=== {step}: {cmd}", flush=True)
    p = subprocess.run(cmd, shell=True, cwd=cwd or REPO, env=ENV, capture_output=True, text=True)
    out = (p.stdout + p.stderr)[-4000:]
    print(out, flush=True)
    st = "ok" if p.returncode == 0 else f"FAILED rc={p.returncode}"
    LOG.append((step, st, round(time.time() - t0, 1), out[-600:]))
    BUDGET[step] = {"seconds": round(time.time() - t0, 1), "free_gb_after": round(free_gb(), 2)}
    if check and p.returncode:
        checkpoint()
        raise SystemExit(f"{step} failed: stop (QUICK assertion)")
    return p.returncode == 0


def checkpoint():
    z = WORK / f"neuro_results_{PART}.zip"
    (WORK / "run_log.md").write_text("# kaggle_neuro run\n\n| step | status | s |\n|---|---|---|\n" + "\n".join(
        f"| {s} | {st} | {t} |" for s, st, t, _ in LOG) + "\n\n" + "\n\n".join(
        f"## {s}\n```\n{o}\n```" for s, st, _, o in LOG if st != "ok"), encoding="utf-8")
    (WORK / "meta_budget.json").write_text(json.dumps({"quick": QUICK, "branch": BRANCH, "steps": BUDGET,
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
    print(f"checkpoint: {z} ({z.stat().st_size / 1e6:.1f} MB), {time.time() - T0:.0f} s so far", flush=True)


def fetch(url, dst, name):
    if not dst.exists():
        if os.path.exists(url):                      # a file of an attached Kaggle dataset
            shutil.copy(url, dst)
        else:
            urllib.request.urlretrieve(url, dst)
    h = hashlib.sha256(dst.read_bytes()).hexdigest()
    want = CKPT_SHA256.get(name)
    if want and h != want:
        raise SystemExit(f"{name}: SHA-256 {h} != pinned {want}")
    BUDGET[f"ckpt_{name}"] = {"sha256": h, "url": url}
    return dst


# ---------------------------------------------------------------- setup
if not REPO.exists():
    sh(f"git clone --depth 1 -b {BRANCH} {REPO_URL} {REPO}", "clone", cwd=WORK, check=True)
sh(f"{sys.executable} -m pip install -q -e . tonic==1.7.0 expelliarmus zstandard snntorch h5py", "pip",
   check=QUICK)
sh(f"{sys.executable} -c \"import tonic, torch; print('tonic', tonic.__version__, 'torch', torch.__version__, "
   f"'cuda', torch.cuda.is_available())\"", "assert imports", check=QUICK)
print(f"free disk after setup: {free_gb():.1f} GB")

# ---------------------------------------------------------------- data
NEED = {"A": "nmnist dvsgesture eventreid", "B": "eventreid", "C": "nmnist dvsgesture"}[PART]
sh(f"{sys.executable} software/scripts/get_events.py --out {DATA} {NEED}", "data", check=QUICK)
if "eventreid" in NEED:
  sh(f"{sys.executable} -c \"import json; from neuro import datasets; "
   f"print(json.dumps(datasets.describe_eventreid('{DATA}/eventreid'), indent=1))\"", "eventreid format",
   check=QUICK)
print(f"free disk after data: {free_gb():.1f} GB")
checkpoint()

# ---------------------------------------------------------------- N5 count caches (Tonic needed only here)
if PART == "A":
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

# ---------------------------------------------------------------- CPU experiments on real data
if PART == "A":
    q = "--quick" if QUICK else ""
    lim_s = "--limit 20" if QUICK else ""
    for ds in ("nmnist", "dvsgesture", "eventreid"):
        sh(f"{sys.executable} experiments/neuro_leakage.py --counts {OUT}/n5/{ds}_counts.npz --dataset {ds} "
           f"--data {DATA}/{ds} {lim_s} --out {OUT}/n5/{ds}", f"N5 {ds}")
    for ds in ("eventreid", "dvsgesture", "nmnist"):
        sh(f"{sys.executable} experiments/neuro_adjacency_attack.py --dataset {ds} --data {DATA}/{ds} {lim_s} {q} "
           f"--out {OUT}/n4b/{ds}", f"N4b {ds}")
        sh(f"{sys.executable} experiments/neuro_overhead.py --dataset {ds} --data {DATA}/{ds} {lim_s} {q} "
           f"--out {OUT}/n9/{ds}", f"N9 {ds}")
    sh(f"{sys.executable} experiments/neuro_perm_strength.py --dataset dvsgesture --data {DATA}/dvsgesture {lim_s} {q} "
       f"--out {OUT}/n8", "N8")
    sh(f"{sys.executable} experiments/neuro_active_attacks.py --dataset nmnist --data {DATA}/nmnist {q} "
       f"--out {OUT}/n7", "N7")
    sh(f"{sys.executable} experiments/neuro_fpe_utility.py --dataset eventreid --data {DATA}/eventreid {lim_s} {q} "
       f"--out {OUT}/n11", "N11")
    checkpoint()

q = "--quick" if QUICK else ""
lim_s = "--limit 20" if QUICK else ""

# ---------------------------------------------------------------- N3 reconstruction (GPU)
if PART == "B":
    ext = WORK / "ext"
    ext.mkdir(exist_ok=True)
    recon = ""
    # with FireNet: the fork (it keeps E2VID's code and adds the FireNet class), else upstream E2VID
    clone = (f"git clone --depth 1 -b {FIRENET_BRANCH} {FIRENET_REPO} {ext / 'rpg_e2vid'}" if FIRENET_CKPT
             else f"git clone --depth 1 {E2VID_REPO} {ext / 'rpg_e2vid'}")
    if sh(clone, "E2VID / FireNet code", cwd=WORK):
        # old-numpy names used by the upstream code (patched in this downloaded copy only)
        for f in (ext / "rpg_e2vid").rglob("*.py"):
            s = f.read_text(errors="replace")
            s2 = s.replace("np.int(", "int(").replace("np.float(", "float(").replace("np.bool(", "bool(")
            if s2 != s:
                f.write_text(s2)
        ck = [f"e2vid={fetch(E2VID_URL, ext / 'E2VID_lightweight.pth.tar', 'e2vid')}"]
        if FIRENET_CKPT:
            ck.append(f"firenet={fetch(FIRENET_CKPT, ext / 'firenet.pth.tar', 'firenet')}")
        recon = f"--recon-repo {ext / 'rpg_e2vid'} --recon-ckpt " + " ".join(ck)
        # The E2VID / FireNet checkpoints are old full pickles (saved with torch 0.4/1.x): torch >= 2.6 refuses them
        # under weights_only=True. They are loaded only after the SHA-256 check above, from the pinned files.
        ENV["TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD"] = "1"
    sh(f"{sys.executable} experiments/neuro_recon_attack.py --dataset eventreid --data {DATA}/eventreid --keys {KEYS} "
       f"{lim_s} {q} {recon} --out {OUT}/n3/eventreid", "N3 eventreid", check=False)
    sh(f"{sys.executable} experiments/neuro_recon_attack.py --dataset synthetic --keys {KEYS} {q} {recon} "
       f"--out {OUT}/n3/synthetic", "N3 synthetic (v2e-lite, exact ground truth)")
    checkpoint()

# ---------------------------------------------------------------- N6 task accuracy (GPU)
if PART == "C":
    seeds = "0" if QUICK else " ".join(map(str, SEEDS))
    for ds in ("nmnist", "dvsgesture"):
        sh(f"{sys.executable} experiments/neuro_task_accuracy.py --dataset {ds} --data {DATA}/{ds} --seeds {seeds} "
           f"{'--limit 300 --epochs 2' if QUICK else ''} --out {OUT}/n6/{ds}", f"N6 {ds}")
    checkpoint()

# ---------------------------------------------------------------- N4 learned attacker (GPU, last)
if PART == "B":
    sh(f"{sys.executable} experiments/neuro_learned_attack.py --dataset eventreid --data {DATA}/eventreid "
       f"--keys {KEYS} {lim_s} {q} --out {OUT}/n4/eventreid", "N4 eventreid")
    sh(f"{sys.executable} experiments/neuro_learned_attack.py --dataset synthetic --keys {KEYS} {q} "
       f"--out {OUT}/n4/synthetic", "N4 synthetic")
    checkpoint()
print(f"done in {(time.time() - T0) / 60:.0f} min; download {WORK / f'neuro_results_{PART}.zip'}")
