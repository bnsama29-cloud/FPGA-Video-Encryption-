"""Secure video link: every role's simulation work (no Vivado) in one script.

Kaggle: New Notebook -> File -> Import / or paste into a code cell and run. Turn Internet ON and GPU T4.
Edit the SETTINGS block below. Output: /kaggle/working/results.zip
"""


# # Secure video link: every role's simulation work in one Kaggle notebook
# Runs everything **except Vivado/board**: Role 1 (RTL tests, lint, cycle benchmark), Role 2 (model, Ascon KATs, crypto benchmark),
# Role 3 (attack scenarios, repeated runs), Role 4 (live link + dashboard API, format compliance, mock board), Role 5 (policies, learned attack on the GPU, jigsaw, figures).
# 
# **Before you start:** Settings (right panel) → *Internet: On* (needs phone verification) → *Accelerator: GPU T4* (for Role 5's learned attack; CPU also works, that step just gets skipped).
# Then *Run All*. Expected time: **~1.5 h** (`PARALLEL=1`), **~1 h** (`PARALLEL=2`), **~15 min** (`QUICK=True`).
# 
# Every step is logged; a failed step does not stop the notebook, and the last cell prints a pass/fail/time table and zips all results to `/kaggle/working/results.zip`.

# ---- SETTINGS (edit here) ---------------------------------------------------
QUICK     = False      # True = smoke test of every role in ~15 min (no repeats, no learning run)
PARALLEL  = 1          # 2 = run scenario chains side by side (faster, but CPU contention can shift reaction times;
                       #     for numbers that go into the paper keep 1)
REPO_URL  = "https://github.com/bnsama29-cloud/FPGA-Video-Encryption-.git"
BRANCH    = "future-work"   # change to "main" once pull request #3 is merged
CLIP_TRAIN = None      # e.g. "/kaggle/input/my-clips/train.mp4"  (Role 5 learned attack; None = synthetic, testing only)
CLIP_TEST  = None      # a DIFFERENT clip, e.g. "/kaggle/input/my-clips/test.mp4"
CLIP_DEMO  = None      # clip for Role 4's mode trade-off / jigsaw; None = synthetic scene
REPEATS   = 3          # repeated runs for mean +- std (Role 3)

import os, sys, time, json, subprocess, shutil, glob, statistics, pathlib
from concurrent.futures import ThreadPoolExecutor

ON_KAGGLE = os.path.exists("/kaggle")
WORK = pathlib.Path(os.environ.get("WORK", "/kaggle/working" if ON_KAGGLE else "/tmp/nbwork"))
WORK.mkdir(parents=True, exist_ok=True)
REPO_URL = os.environ.get("REPO_URL", REPO_URL); BRANCH = os.environ.get("BRANCH", BRANCH)
REPO = WORK / "repo"
LOG = []                      # (role, step, status, seconds)
PATHX = f"{os.environ['PATH']}:{sys.exec_prefix}/bin:/usr/local/bin:{pathlib.Path(sys.executable).parent}"
ENV = {**os.environ, "PATH": PATHX, "PYTHONUNBUFFERED": "1"}

def sh(cmd, role, step, cwd=None, tail=25, check_text=None, timeout=None):
    """Run a shell command, keep going on failure, record status + time."""
    t0 = time.time()
    print(f"\n=== [{role}] {step}\n$ {cmd}")
    p = subprocess.run(cmd, shell=True, cwd=cwd or REPO, env=ENV, capture_output=True, text=True, timeout=timeout)
    out = (p.stdout + p.stderr).strip().splitlines()
    print("\n".join(out[-tail:]))
    ok = p.returncode == 0 and (check_text is None or check_text in p.stdout + p.stderr)
    dt = time.time() - t0
    LOG.append((role, step, "PASS" if ok else "FAIL", round(dt, 1)))
    print(f"--> {'PASS' if ok else 'FAIL'} in {dt:.0f} s")
    return ok

def chains(jobs, parallel):
    """jobs = list of chains; a chain = list of zero-arg callables run in order. Chains run `parallel` at a time."""
    def run_chain(ch):
        for f in ch: f()
    with ThreadPoolExecutor(max_workers=max(1, parallel)) as ex:
        list(ex.map(run_chain, jobs))
print("work dir:", WORK, "| on kaggle:", ON_KAGGLE, "| python", sys.version.split()[0])


# ## 0. Setup: clone, packages, Icarus Verilog 12, GPU check

if REPO.exists(): shutil.rmtree(REPO)
sh(f"git clone --depth 1 -b {BRANCH} {REPO_URL} {REPO}", "setup", "clone repo", cwd=WORK)
sh("python -m pip install -q cocotb==2.1.0 cocotbext-axi==0.1.28 verilator cryptography scikit-image "
   "opencv-python-headless pillow matplotlib pytest tomli numpy", "setup", "pip install", tail=5)
sh("git log --oneline -1 && ls", "setup", "repo contents", tail=30)

# Role 1's RTL tests were verified with Icarus Verilog 12; Kaggle's Ubuntu ships 11, so build 12 (about 6-8 minutes, once).
have12 = subprocess.run("iverilog -V 2>/dev/null | head -1", shell=True, capture_output=True, text=True, env=ENV).stdout
print("found:", have12.strip() or "no iverilog")
if "12." not in have12:
    sh("apt-get update -qq && apt-get install -y -qq build-essential flex bison gperf autoconf", "setup", "apt build tools", cwd=WORK, tail=3)
    sh("rm -rf iverilog && git clone --depth 1 -b v12_0 https://github.com/steveicarus/iverilog.git && cd iverilog && "
       "sh autoconf.sh && ./configure -q && make -j4 >/dev/null && make install >/dev/null && iverilog -V | head -1",
       "setup", "build Icarus Verilog 12", cwd=WORK, tail=3, check_text="12.0")
else:
    LOG.append(("setup", "Icarus Verilog 12 present", "PASS", 0))

try:
    import torch
    print("torch", torch.__version__, "| cuda:", torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else "")
    HAVE_GPU = torch.cuda.is_available()
except Exception as e:
    print("torch not importable:", e); HAVE_GPU = False
sh("nproc; free -g | head -2", "setup", "machine", tail=5)


# ## Role 1: hardware (everything that does not need Vivado)
# RTL blocks vs the golden model (cocotb + Icarus), the Vivado testbench run in Icarus, lint, and the cycles-per-pixel benchmark.

sh("make test-rtl", "R1", "RTL blocks vs model (cocotb)", tail=6)
sh("make xsim-icarus", "R1", "Vivado testbench in Icarus", tail=4, check_text="CHECK RESULT: PASS")
vbin = glob.glob(f"{sys.exec_prefix}/lib/python3*/*-packages/verilator/bin") + glob.glob("/usr/local/lib/python3*/dist-packages/verilator/bin")
if vbin: ENV["PATH"] += ":" + vbin[0]
sh("make lint", "R1", "Verilator lint", tail=3, check_text="lint clean")
sh("make hls-csim", "R1", "HLS C simulation (needs g++)", tail=3)
if not QUICK:
    sh("python experiments/benchmark_crypto.py --rtl", "R1", "cycles/pixel per mode (RTL)", tail=25)


# ## Role 2: cryptography and the golden model

sh("make test-model", "R2", "model + 1089 Ascon KATs + contract equivalence", tail=4)
sh("RUN_SLOW=1 python -m pytest -q tests/", "R2", "all tests incl. end-to-end link", tail=4)
sh("python experiments/benchmark_crypto.py" + (" --frames 3" if QUICK else ""), "R2", "crypto benchmark (AES-GCM / ChaCha20 / Ascon)", tail=30)
sh("python -m future_work.baselines.bench_software_codecs" + (" --frames 3" if QUICK else ""), "R2", "libjpeg-turbo + software selective baselines", tail=25)


# ## Role 3: network and attacker (real time: the scenarios run for as long as their timeline)
# quick 110 s · full_suite 300 s · benign 150 s. Repeats give the mean ± std the paper needs.

def scen(name, k, port, policy="threshold", role="R3"):
    out = f"sim_out/runs/{name}_{policy}_rep{k}"
    return lambda: sh(f"python experiments/scenario.py --scenario experiments/scenarios/{name}.json --policy {policy} "
                      f"--out {out} --base-port {port}", role, f"scenario {name} / {policy} / run {k}", tail=14)

reps = 1 if QUICK else REPEATS
jobs = [[scen("quick", 1, 48000)]]
if not QUICK:
    jobs += [[scen("full_suite", k, 48100 + 100 * k) for k in range(1, reps + 1)],
             [scen("benign", k, 48500 + 100 * k) for k in range(1, reps + 1)]]
t0 = time.time(); chains(jobs, PARALLEL); print(f"\nRole 3 scenarios: {time.time()-t0:.0f} s wall")

def aggregate(name, policy="threshold"):
    rows = [json.load(open(p)) for p in sorted(glob.glob(f"{REPO}/sim_out/runs/{name}_{policy}_rep*/summary.json"))]
    if not rows: return
    def ms(key):
        v = [r[key] for r in rows if isinstance(r.get(key), (int, float))]
        return f"{statistics.mean(v):.3f} +- {statistics.pstdev(v):.3f}" if v else "n/a"
    print(f"\n{name} ({policy}), {len(rows)} runs: mitigated {[r['mitigated_episodes'] for r in rows]}, "
          f"time to mitigate {ms('mean_time_to_mitigate_s')} s, leakage {ms('mean_leakage_under_attack')}, "
          f"false-alarm windows {[str(r['false_alarm_windows'])+'/'+str(r['calm_windows']) for r in rows]}, "
          f"latency median {ms('latency_ms_median')} ms")
for n in ("quick", "full_suite", "benign"): aggregate(n)


# ## Role 4: live link, dashboard API, real-video compliance, mock board
# The dashboard is a web page, so on Kaggle we check its API instead of looking at it. Run `python -m link.run_all` on a laptop for the demo.

import urllib.request
ports = "--set link.video_in=49000 --set link.video_out=49001 --set link.fb_in=49002 --set link.fb_out=49003 " \
        "--set link.control=49004 --set link.sender_control=49005 --set link.bus=[49010] --set dashboard.http_port=49123 " \
        "--set defence.memory_file=''"
t0 = time.time()
ra = subprocess.Popen(f"python -m link.run_all {ports}", shell=True, cwd=REPO, env=ENV, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(25)
try:
    st = json.load(urllib.request.urlopen("http://127.0.0.1:49123/api/state", timeout=10))
    total = st["latest"]["receiver.heartbeat"]["total"]
    ok = total["ok"] > 100 and total["tag_fail"] == 0
    print("receiver totals after 25 s:", total)
except Exception as e:
    ok = False; print("dashboard API check failed:", e)
LOG.append(("R4", "full link: sender -> channel -> receiver -> dashboard API", "PASS" if ok else "FAIL", round(time.time()-t0, 1)))
ra.terminate()
try: ra.wait(10)
except Exception: ra.kill()

# same link, but the sender is the "board" driver on the model emulation of the FPGA IP
ports2 = ports.replace("49", "50")
t0 = time.time()
ra = subprocess.Popen(f"python -m link.run_all --no-sender {ports2}", shell=True, cwd=REPO, env=ENV, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(3)
bs = subprocess.Popen(f"python -m future_work.board.board_sender --mock {ports2}", shell=True, cwd=REPO, env=ENV, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(25)
try:
    st = json.load(urllib.request.urlopen("http://127.0.0.1:50123/api/state", timeout=10))
    total = st["latest"]["receiver.heartbeat"]["total"]
    enc = st["latest"]["sender.start"]["encoder"]
    ok = total["ok"] >= 10 and total["tag_fail"] == 0 and enc == "board"   # the Python emulation of the IP is slow (~1-2 fps)
    print("mock-board receiver totals:", total, "| encoder:", enc)
except Exception as e:
    ok = False; print("failed:", e)
LOG.append(("R4", "mock board sender over the live link", "PASS" if ok else "FAIL", round(time.time()-t0, 1)))
for p in (bs, ra):
    p.terminate()
    try: p.wait(10)
    except Exception: p.kill()

demo = f"--video {CLIP_DEMO}" if CLIP_DEMO else ""
sh("python -m future_work.figures.format_compliance", "R4", "format compliance (Pillow, OpenCV, scikit-image, ffmpeg)", tail=12)
sh(f"python experiments/measure_mode_tradeoff.py {demo} --frames {3 if QUICK else 20} --size 320x240", "R4", "mode trade-off / leakage per mode", tail=14)
sh("python -m pytest -q tests/test_future_work.py", "R4", "future_work tests (mock driver, board sender, jigsaw)", tail=4)


# ## Role 5: defence, ML and visual security (GPU used for the learned attack)

chain = [lambda: sh("python experiments/compare_policies.py --scenario experiments/scenarios/quick.json", "R5",
                    "policies on quick.json (fixed / threshold / bandit)", tail=12)]
if not QUICK:
    chain.append(lambda: sh("python experiments/compare_policies.py --scenario experiments/scenarios/learning.json --policies threshold bandit",
                            "R5", "learning run: threshold vs bandit (7.7 min each)", tail=12))
t0 = time.time(); chains([chain], 1); print(f"policies: {time.time()-t0:.0f} s wall")

demo = f"--video {CLIP_DEMO}" if CLIP_DEMO else ""
sh(f"python -m future_work.attacks.jigsaw_attack {demo} --frames {2 if QUICK else 8} --save-images", "R5", "jigsaw attack on E5", tail=14)
sh("python -m future_work.figures.visual_security_grid", "R5", "visual-security figure", tail=3)
if HAVE_GPU or QUICK:
    tr, te = (CLIP_TRAIN or "synthetic"), (CLIP_TEST or "synthetic")
    if tr == "synthetic": print("NOTE: synthetic clips = pipeline test only. For paper numbers set CLIP_TRAIN / CLIP_TEST to two different real videos.")
    args = "--modes E2 E5 --size 96x64 --frames 60 --test-frames 50 --stride 1 --epochs 1" if QUICK else \
           "--modes E1 E2 E4 E5 --size 160x128 --frames 3000 --epochs 25"
    sh(f"python experiments/learned_attack.py --train-source {tr} --test-source {te} {args}", "R5", f"learned attack ({'GPU' if HAVE_GPU else 'CPU, tiny'})", tail=25)
else:
    print("No GPU: learned attack skipped (turn on Accelerator: GPU T4 in the notebook settings).")


# ## Collect: summary table and download

import pandas as pd
df = pd.DataFrame(LOG, columns=["role", "step", "status", "seconds"])
pd.set_option("display.width", 200, "display.max_colwidth", 70, "display.max_rows", 200)
print(df.to_string(index=False))
print(f"\n{(df.status=='PASS').sum()} passed, {(df.status=='FAIL').sum()} failed, total {df.seconds.sum()/60:.1f} min of step time")
df.to_csv(REPO / "sim_out" / "kaggle_run_summary.csv", index=False)
out = WORK / "results"
if out.exists(): shutil.rmtree(out)
out.mkdir()
for src in ("sim_out", "future_work/results"):
    if (REPO / src).exists(): shutil.copytree(REPO / src, out / src.replace("/", "_"))
shutil.make_archive(str(WORK / "results"), "zip", out)
print("results.zip:", round((WORK / "results.zip").stat().st_size / 1e6, 1), "MB  -> download from the Output tab")


# **Next:** download `results.zip` (Output tab on the right, or *Save Version → Save & Run All* so Kaggle keeps it), unzip it into the repo on a laptop, and commit the numbers on a branch such as `kaggle-results`. Anything that fails above: paste that step's printed log into Claude together with `docs/TEAM_CONTEXT.md`.
