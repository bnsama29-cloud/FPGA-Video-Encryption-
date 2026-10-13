"""COMPLETE simulation in one Kaggle run: every role (except Vivado), 10-seed policy study, real video.

HOW TO RUN (one Kaggle account is enough)
  1. + Create -> New Dataset -> upload your clips (avengers.mp4, jailer.mp4, denzel.mp4, challenge.mp4).
     Keep it PRIVATE (the clips are copyrighted). Without clips the real-video part is skipped.
  2. New Notebook -> + Add Input -> your clip dataset.
     Settings: Internet ON (phone-verified account), Accelerator GPU T4.
  3. Paste this whole file into ONE code cell.
  4. Save Version -> "Save & Run All (Commit)". This runs in the background (you can close the
     browser) for up to 12 h and keeps /kaggle/working. An interactive session stops when you leave.
  5. When it finishes: open the version -> Output -> download results.zip.
     results.zip is also written after every section, so a crash still leaves the finished part.

TIME (Kaggle, 4 CPU cores + T4), default settings:
  setup 4 min | Role 1 3 | Role 2 2 | Role 3 25 | Role 4 3 | Role 5 policies 21 + 10 seeds 155 |
  figures 2 | real video 35-45   ->  about 4 h 10 min with PARALLEL = 1
  PARALLEL = 2 runs two scenarios at a time: about 2 h 45 min (reaction times can shift slightly).
  QUICK = True: smoke test of every step, about 20 min. Do this first if you changed anything.

OUTPUT: results.zip with sim_out/ (all runs), future_work_results/, real_video/ and
paper_tables.md (every table of the paper, built from the files; lists anything missing).
"""
# ============================ SETTINGS =======================================
QUICK = False                 # True = ~20 min smoke test of every step
PARALLEL = 1                  # 1 = numbers for the paper; 2 = faster
SEEDS = list(range(1, 11))    # bandit vs threshold: one learning run (7.7 min) per policy per seed
REPEATS = 3                   # repeated full_suite / benign runs (Role 3)
RUN = dict(role1=True, role2=True, role3=True, role4=True, role5=True, seeds=True, real_video=True)
REPO_URL = "https://github.com/bnsama29-cloud/FPGA-Video-Encryption-.git"
BRANCH = "main"               # everything is merged into main
PAIRS = None                  # learned attack (train, test) clip pairs; None = automatic
# =============================================================================

import glob, json, os, pathlib, shutil, signal, statistics, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor

T_START = time.time()
ON_KAGGLE = os.path.exists("/kaggle")
WORK = pathlib.Path(os.environ.get("WORK", "/kaggle/working" if ON_KAGGLE else "/tmp/kcwork"))
WORK.mkdir(parents=True, exist_ok=True)
REPO_URL = os.environ.get("REPO_URL", REPO_URL)
BRANCH = os.environ.get("BRANCH", BRANCH)
QUICK = os.environ.get("QUICK", str(QUICK)) == "True"
if QUICK:
    SEEDS, REPEATS = [1], 1
REPO = WORK / "repo"
ENV = {**os.environ, "PYTHONUNBUFFERED": "1",
       "PATH": f"{os.environ['PATH']}:{sys.exec_prefix}/bin:/usr/local/bin:{pathlib.Path(sys.executable).parent}"}
LOG = []                      # (section, step, status, seconds)


def sh(cmd, sec, step, cwd=None, tail=20, check_text=None):
    """Run one step; a failure is logged and the run goes on."""
    t0 = time.time()
    print(f"\n=== [{sec}] {step}   (t = {(t0 - T_START) / 60:.0f} min)\n$ {cmd}", flush=True)
    p = subprocess.run(cmd, shell=True, cwd=cwd or REPO, env=ENV, capture_output=True, text=True)
    print("\n".join((p.stdout + p.stderr).strip().splitlines()[-tail:]))
    ok = p.returncode == 0 and (check_text is None or check_text in p.stdout + p.stderr)
    LOG.append((sec, step, "PASS" if ok else "FAIL", round(time.time() - t0, 1)))
    print(f"--> {LOG[-1][2]} in {LOG[-1][3]:.0f} s", flush=True)
    return ok


def start(cmd):
    """Long-running command in its own process group (stop() then ends all of it, see bug #14)."""
    return subprocess.Popen(cmd, shell=True, cwd=REPO, env=ENV, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, start_new_session=True)


def stop(p):
    try:
        os.killpg(p.pid, signal.SIGTERM)
        p.wait(10)
    except Exception:
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except Exception:
            pass


def stray_nodes():
    return subprocess.run("ps aux | grep -E 'link\\.(run_all|channel|receiver|sender|dashboard)|board_sender' "
                          "| grep -v grep", shell=True, capture_output=True, text=True).stdout.strip()


def lanes(jobs, parallel):
    """jobs = list of chains (lists of zero-arg callables); `parallel` chains at a time."""
    with ThreadPoolExecutor(max_workers=max(1, parallel)) as ex:
        list(ex.map(lambda ch: [f() for f in ch], jobs))


def checkpoint(final=False):
    """Copy every result so far into results/ and zip it (survives a crash later in the run)."""
    out = WORK / "results"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir()
    for src, dst in (("sim_out", "sim_out"), ("future_work/results", "future_work_results")):
        if (REPO / src).exists():
            shutil.copytree(REPO / src, out / dst, ignore=shutil.ignore_patterns("*.npz", "*.pt", "events.jsonl"))
    (out / "run_log.json").write_text(json.dumps(dict(log=LOG, minutes=round((time.time() - T_START) / 60, 1),
                                                      settings=dict(QUICK=QUICK, PARALLEL=PARALLEL, SEEDS=SEEDS,
                                                                    REPEATS=REPEATS)), indent=1))
    subprocess.run(f"{sys.executable} -m future_work.figures.paper_tables --root {out} --out {out}/paper_tables.md",
                   shell=True, cwd=REPO, env=ENV, capture_output=True)
    shutil.make_archive(str(WORK / "results"), "zip", out)
    print(f"[checkpoint] results.zip {round((WORK / 'results.zip').stat().st_size / 1e6, 1)} MB, "
          f"{(time.time() - T_START) / 60:.0f} min so far", flush=True)


print("work dir:", WORK, "| kaggle:", ON_KAGGLE, "| python", sys.version.split()[0], "| QUICK", QUICK)

# ============================ 0. SETUP =======================================
if REPO.exists():
    shutil.rmtree(REPO)
sh(f"git clone --depth 1 -b {BRANCH} {REPO_URL} {REPO}", "setup", "clone repo", cwd=WORK, tail=2)
sh("python -m pip install -q cocotb==2.1.0 cocotbext-axi==0.1.28 verilator cryptography scikit-image "
   "opencv-python-headless pillow matplotlib pytest tomli numpy pandas", "setup", "pip install", tail=3)
sh("git log --oneline -1", "setup", "repo version", tail=2)
have12 = subprocess.run("iverilog -V 2>/dev/null | head -1", shell=True, capture_output=True, text=True, env=ENV).stdout
if RUN["role1"] and "12." not in have12:   # Kaggle ships Icarus 11; the RTL tests were verified on 12
    sh("apt-get update -qq && apt-get install -y -qq build-essential flex bison gperf autoconf",
       "setup", "apt build tools", cwd=WORK, tail=2)
    sh("rm -rf iverilog && git clone --depth 1 -b v12_0 https://github.com/steveicarus/iverilog.git && cd iverilog && "
       "sh autoconf.sh && ./configure -q && make -j4 >/dev/null && make install >/dev/null && iverilog -V | head -1",
       "setup", "build Icarus Verilog 12 (~2.5 min)", cwd=WORK, tail=2, check_text="12.0")
try:
    import torch
    HAVE_GPU = torch.cuda.is_available()
    print("torch", torch.__version__, "| GPU:", torch.cuda.get_device_name(0) if HAVE_GPU else "none")
except Exception as e:
    HAVE_GPU = False
    print("no torch:", e)
sh("nproc; free -g | head -2", "setup", "machine", tail=4)

roots = [os.environ["CLIPS_DIR"]] if os.environ.get("CLIPS_DIR") else ["/kaggle/input"]
found = sorted({f for r in roots for e in ("mp4", "mkv", "avi", "mov", "webm")
                for f in glob.glob(f"{r}/**/*.{e}", recursive=True)})
CLIPS = {pathlib.Path(f).stem: f for f in found}
print("clips found:", list(CLIPS) or "none (real-video part will be skipped)")


def pick(*words):
    return next((f for k, f in CLIPS.items() if any(w in k.lower() for w in words)), None)


# ============================ ROLE 1: hardware without Vivado ================
if RUN["role1"]:
    sh("make test-rtl", "R1", "RTL blocks vs golden model (cocotb + Icarus)", tail=4)
    sh("make xsim-icarus", "R1", "Vivado testbench run in Icarus", tail=3, check_text="CHECK RESULT: PASS")
    vbin = glob.glob(f"{sys.exec_prefix}/lib/python3*/*-packages/verilator/bin") + \
        glob.glob("/usr/local/lib/python3*/dist-packages/verilator/bin")
    if vbin:
        ENV["PATH"] += ":" + vbin[0]
    sh("make lint", "R1", "Verilator lint", tail=2, check_text="lint clean")
    sh("make hls-csim", "R1", "HLS C simulation", tail=2)
    if not QUICK:
        sh("python experiments/benchmark_crypto.py --rtl", "R1", "cycles per pixel per mode (RTL)", tail=14)
        shutil.copytree(REPO / "sim_out" / "benchmark", REPO / "sim_out" / "benchmark_rtl", dirs_exist_ok=True)  # bug #15
    checkpoint()

# ============================ ROLE 2: crypto and model =======================
if RUN["role2"]:
    sh("make test-model", "R2", "model + 1089 Ascon KATs + contract equivalence", tail=3)
    sh("RUN_SLOW=1 python -m pytest -q tests/", "R2", "all tests incl. end-to-end link", tail=3)
    sh("python experiments/benchmark_crypto.py" + (" --frames 3" if QUICK else ""), "R2", "crypto benchmark", tail=14)
    sh("python -m future_work.baselines.bench_software_codecs" + (" --frames 3" if QUICK else ""),
       "R2", "libjpeg-turbo + AES-GCM / ChaCha20 baselines", tail=12)
    checkpoint()


# ============================ ROLE 3: attacks, repeated ======================
def scen(name, k, port, extra="", tag=None):
    tag = tag or f"{name}_threshold_rep{k}"
    return lambda: sh(f"python experiments/scenario.py --scenario experiments/scenarios/{name}.json --policy threshold "
                      f"--out sim_out/runs/{tag} --base-port {port} {extra}", "R3", f"scenario {tag}", tail=6)


if RUN["role3"]:
    jobs = [[scen("quick", 1, 48000)]]
    if not QUICK:
        jobs += [[scen("full_suite", k, 48100 + 100 * k) for k in range(1, REPEATS + 1)],
                 [scen("benign", k, 48600 + 100 * k) for k in range(1, REPEATS + 1)]]
    lanes(jobs, PARALLEL)
    checkpoint()

# ============================ ROLE 4: live link, board mock, compliance ======
if RUN["role4"]:
    import urllib.request
    for name, cmd, port, need in (("full link: sender -> channel -> receiver -> dashboard API", "link.run_all", 49, 100),
                                  ("mock FPGA board as the sender over the live link", "board", 50, 10)):
        p = {k: f"{port}{v}" for k, v in dict(vi="000", vo="001", fi="002", fo="003", c="004", sc="005", b="010",
                                                h="123").items()}
        sets = (f"--set link.video_in={p['vi']} --set link.video_out={p['vo']} --set link.fb_in={p['fi']} "
                f"--set link.fb_out={p['fo']} --set link.control={p['c']} --set link.sender_control={p['sc']} "
                f"--set link.bus=[{p['b']}] --set dashboard.http_port={p['h']} --set defence.memory_file=''")
        t0 = time.time()
        procs = [start(f"python -m link.run_all {sets}")] if cmd == "link.run_all" else \
            [start(f"python -m link.run_all --no-sender {sets}")]
        if cmd == "board":
            time.sleep(3)
            procs.append(start(f"python -m future_work.board.board_sender --mock {sets}"))
        time.sleep(25)
        try:
            st = json.load(urllib.request.urlopen(f"http://127.0.0.1:{p['h']}/api/state", timeout=10))["latest"]
            tot = st["receiver.heartbeat"]["total"]
            ok = tot["ok"] >= need and tot["tag_fail"] == 0
            print(name, "->", tot, "| encoder:", st["sender.start"]["encoder"])
        except Exception as e:
            ok = False
            print(name, "failed:", e)
        LOG.append(("R4", name, "PASS" if ok else "FAIL", round(time.time() - t0, 1)))
        for q in procs[::-1]:
            stop(q)
    time.sleep(2)
    left = stray_nodes()
    LOG.append(("R4", "no link process left running", "FAIL" if left else "PASS", 0))
    sh("python -m future_work.figures.format_compliance", "R4", "format compliance (5 decoders)", tail=9)
    sh(f"python experiments/measure_mode_tradeoff.py --frames {3 if QUICK else 20} --size 320x240",
       "R4", "mode trade-off, synthetic scene", tail=9)
    sh("python -m pytest -q tests/test_future_work.py tests/test_policy_seeds.py", "R4", "future_work tests", tail=3)
    checkpoint()

# ============================ ROLE 5: policies, figures ======================
if RUN["role5"]:
    sh("python experiments/compare_policies.py --scenario experiments/scenarios/quick.json",
       "R5", "fixed / threshold / bandit on quick.json (figures)", tail=8)
    if not QUICK:
        sh("python experiments/compare_policies.py --scenario experiments/scenarios/learning.json "
           "--policies threshold bandit", "R5", "learning curve figure (one run each)", tail=6)
    sh(f"python -m future_work.attacks.jigsaw_attack --frames {2 if QUICK else 8} --save-images",
       "R5", "jigsaw attack on E5, synthetic", tail=8)
    sh("python -m future_work.figures.visual_security_grid", "R5", "visual-security figure, synthetic", tail=2)
    checkpoint()

if RUN["seeds"]:
    sc = "quick" if QUICK else "learning"
    sh(f"python experiments/policy_seeds.py --scenario experiments/scenarios/{sc}.json "
       f"--seeds {' '.join(map(str, SEEDS))} --parallel {PARALLEL}",
       "R5", f"bandit vs threshold over {len(SEEDS)} seeds", tail=22)
    checkpoint()

# ============================ REAL VIDEO =====================================
if RUN["real_video"] and len(CLIPS) >= 1:
    n = 3 if QUICK else 20
    for name, f in CLIPS.items():
        base = f"sim_out/real/{name}"
        sh(f"python experiments/measure_mode_tradeoff.py --video '{f}' --frames {n} --stride {max(1, 3000 // n)} "
           f"--size 320x240 --out {base}/mode_tradeoff.json", "video", f"mode trade-off: {name}", tail=9)
        sh(f"python -m future_work.attacks.jigsaw_attack --video '{f}' --frames {2 if QUICK else 8} "
           f"--stride 375 --size 320x240 --out {base}/jigsaw", "video", f"jigsaw on E5: {name}", tail=7)
    trailer = pick("avengers", "jailer", "trailer") or found[0]
    talking = pick("denzel", "motivat", "challenge", "topper") or found[-1]
    for tag, f in {"trailer": trailer, "talking": talking}.items():
        sh(f"python -m future_work.figures.visual_security_grid --video '{f}' --frame 300 --out sim_out/real/grid_{tag}",
           "video", f"visual-security figure: {tag}", tail=1)
    checkpoint()
    jobs = [[(lambda tag=tag, f=f, i=i: sh(
        f"python experiments/scenario.py --scenario experiments/scenarios/{'quick' if QUICK else 'full_suite'}.json "
        f"--policy threshold --out sim_out/real/scenario_{tag} --base-port {49200 + 200 * i} --set sender.source='{f}'",
        "video", f"attack suite with {tag} video as the source", tail=6))]
        for i, (tag, f) in enumerate({"trailer": trailer, "talking": talking}.items())]
    lanes(jobs, PARALLEL)
    checkpoint()
    if PAIRS is None:
        PAIRS = [p for p in ((pick("avengers"), pick("jailer")), (pick("denzel", "motivat"), pick("challenge", "topper")))
                 if p[0] and p[1]] or ([(found[0], found[1])] if len(found) >= 2 else [])
    if HAVE_GPU or QUICK:
        for k, (tr, te) in enumerate(PAIRS):
            args = ("--modes E2 E5 --size 96x64 --frames 60 --test-frames 50 --stride 6 --epochs 1" if QUICK else
                    "--modes E1 E2 E4 E5 --size 160x128 --frames 1000 --test-frames 400 --stride 3 --epochs 25")
            sh(f"python experiments/learned_attack.py --train-source '{tr}' --test-source '{te}' {args} "
               f"--out sim_out/real/learned_pair{k + 1}", "video",
               f"learned attack: train {pathlib.Path(tr).stem} -> test {pathlib.Path(te).stem}", tail=10)
    else:
        print("No GPU: learned attack skipped (Accelerator: GPU T4).")
    checkpoint()
elif RUN["real_video"]:
    print("No clips under /kaggle/input: real-video part skipped (+ Add Input -> your clip dataset).")
    if HAVE_GPU:
        sh("python experiments/learned_attack.py --train-source synthetic --test-source synthetic --modes E2 E5 "
           "--size 96x64 --frames 60 --test-frames 50 --stride 1 --epochs 1", "R5", "learned attack pipeline test", tail=6)

# ============================ SUMMARY ========================================
time.sleep(1)
left = stray_nodes()
if left:
    print("stray processes left:\n" + left)
checkpoint(final=True)
w = max(len(s) for _, s, _, _ in LOG)
print("\n" + "\n".join(f"{sec:<6}{s:<{w + 2}}{st:<6}{t:>7.0f} s" for sec, s, st, t in LOG))
fails = [s for _, s, st, _ in LOG if st != "PASS"]
print(f"\n{len(LOG) - len(fails)} passed, {len(fails)} failed, total {(time.time() - T_START) / 3600:.2f} h")
if fails:
    print("FAILED:", *fails, sep="\n  ")
print("\nDownload results.zip from the Output tab. Open paper_tables.md inside it first.")
