"""Every Kaggle run of the project in one file (until 17 Oct 2026 these were four scripts).

HOW TO USE: set JOB below, then paste this whole file into ONE Kaggle code cell and
"Save Version -> Save & Run All (Commit)". Each job's own instructions (inputs, GPU, time, output zip)
are in the docstring at the start of its block.

  JOB = "complete"   every role's simulation + 10-seed policy study + real video   (14 Oct, ~4 h)
  JOB = "remaining"  open clips, Kodak, metrics, restart interval, learned attack  (14 Oct, ~1.5 h)
  JOB = "research"   R1-R8: stall profile, lanes, rate control, change-driven, size channel (15 Oct)
  JOB = "final"      60-frame leakage, MST jigsaw, recognition, P5 learned attacker  (16 Oct, ~3-4 h)
  JOB = "references" attacks from the reference papers: Lin et al. sign recovery, Schuster et al.
                     video identification from frame sizes                       (17 Oct, ~2-3 h, CPU only)
  JOB = "benchmark"  SVE-Bench: ours and four published schemes under the same four attacks, every
                     source                                                       (17 Oct, ~30-45 min, CPU only)

The first four have been run; their results are in paper/data/ (simulation, extra, research, final).
Each block below is the original script, byte for byte apart from the indentation.
"""
JOB = "benchmark"

# ==================================================================================================
# JOB = "complete"   (was future_work/kaggle/kaggle_complete.py)
# ==================================================================================================
if JOB == "complete":
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

    import glob, json, os, pathlib, re, shutil, signal, statistics, subprocess, sys, time
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
    # folder-safe names: a file called "challenge .mp4" (space) broke the unquoted --out paths in run 1
    CLIPS = {re.sub(r"[^A-Za-z0-9_-]+", "_", pathlib.Path(f).stem.strip()).strip("_"): f for f in found}
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

# ==================================================================================================
# JOB = "remaining"   (was future_work/kaggle/kaggle_remaining.py)
# ==================================================================================================
elif JOB == "remaining":
    """Every remaining task that a Kaggle GPU T4 can do, in one run (GUIDE.md B2, B4, B5, B13, B15, B16, B17).
After this, the only remaining simulation-side work is the Vivado day.

RERUN = True (the default since 14 Oct 2026): the full run is done (paper/data/extra). Only two things
are repeated, with the scripts fixed after it (GUIDE.md B20, B21; docs/TESTING.md bug #16):
  * restart interval on the open sources (Sintel, Tears of Steel, Kodak) and the real-frame figure: ~5 min
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
                    if not img:                         # the paper figure, now sized for 0.7\textwidth
                        sh(f"python -m future_work.figures.visual_security_grid --video '{p}' --frame 300 --out {base}/grid",
                           name, "visual-security figure, paper size (B2)", tail=1)
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

# ==================================================================================================
# JOB = "research"   (was future_work/kaggle/kaggle_research.py)
# ==================================================================================================
elif JOB == "research":
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

# ==================================================================================================
# JOB = "final"   (was future_work/kaggle/kaggle_final.py)
# ==================================================================================================
elif JOB == "final":
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

# ==================================================================================================
# JOB = "references"   attacks taken from the reference papers (added 17 Oct 2026)
# ==================================================================================================
elif JOB == "references":
    """Two attacks from the papers we cite, run on the same sources as the paper (GUIDE.md B35, B36).

HOW TO RUN (one Kaggle account, NO GPU needed)
  1. Notebook settings: Internet ON, Accelerator None (CPU; 4 cores are used in parallel).
  2. + Add Input -> your private clips dataset (the same one as before). Optional: without it only
     the open films and Kodak are used.
  3. Paste this whole file into ONE code cell -> Save Version -> "Save & Run All (Commit)".
  4. Download references_results.zip from the version's Output tab and send it.
  QUICK = True first for a ~10-minute smoke test (tiny sizes; the numbers mean nothing).

WHAT IT RUNS (numbers under sim_out/references/, zipped after every step; no frames are saved)
  B35  Sign-bit recovery, Lin et al. (JVCIR 2024): their LP relaxation against E1-E4, plus a check in
       their own setting (LinU3 / LinU6). 128x96 luma; Kodak 12 images, 2 frames per video source.
       One E1 LP takes 3-5 min on one core, so four sources run in parallel.
  B36  Video identification from frame sizes, Schuster et al. (USENIX Security 2017): which of the
       videos is playing, from W consecutive encrypted frame sizes, for E2, E5 and the padding schemes.
       All video sources, 600 frames at stride 3 (about 10 frames/s of video).
TIME (Kaggle CPU): downloads ~10 min, B35 ~1.5-2 h, B36 ~40 min.
"""
    # ============================ SETTINGS =======================================
    QUICK = False
    REPO_URL = "https://github.com/bnsama29-cloud/FPGA-Video-Encryption-.git"
    BRANCHES = ["refs-verify", "main"]          # the first one that has experiments/sign_recovery.py
    OPEN_CLIPS = {                               # CC BY 3.0, (c) Blender Foundation
        "sintel_trailer": "https://download.blender.org/durian/trailer/sintel_trailer-480p.mp4",
        "tearsofsteel": "https://download.blender.org/demo/movies/ToS/tears_of_steel_720p.mov",
    }
    KODAK_URL = "http://r0k.us/graphics/kodak/kodak/kodim{:02d}.png"
    PARALLEL = 4
    RUN = dict(b35_sign=True, b36_fingerprint=True)
    # =============================================================================

    import glob, json, os, pathlib, re, shutil, subprocess, sys, time, urllib.request
    from concurrent.futures import ThreadPoolExecutor

    T_START = time.time()
    ON_KAGGLE = os.path.exists("/kaggle")
    WORK = pathlib.Path(os.environ.get("WORK", "/kaggle/working" if ON_KAGGLE else "/tmp/krwork"))
    WORK.mkdir(parents=True, exist_ok=True)
    QUICK = os.environ.get("QUICK", str(QUICK)) == "True"
    REPO, DATA, OUT = WORK / "repo", WORK / "opendata", "sim_out/references"
    ENV = {**os.environ, "PYTHONUNBUFFERED": "1"}
    LOG, SOURCES = [], {}


    def sh(cmd, sec, step, tail=12, cwd=None):
        t0 = time.time()
        print(f"\n=== [{sec}] {step}   (t = {(t0 - T_START) / 60:.0f} min)\n$ {cmd}", flush=True)
        p = subprocess.run(cmd, shell=True, cwd=cwd or REPO, env=ENV, capture_output=True, text=True)
        print("\n".join((p.stdout + p.stderr).strip().splitlines()[-tail:]), flush=True)
        LOG.append((sec, step, "PASS" if p.returncode == 0 else "FAIL", round(time.time() - t0, 1)))
        print(f"--> [{sec}] {LOG[-1][2]} in {LOG[-1][3]:.0f} s", flush=True)
        return p.returncode == 0


    def checkpoint():
        res = WORK / "references_results"
        shutil.rmtree(res, ignore_errors=True)
        res.mkdir()
        if (REPO / OUT).exists():
            shutil.copytree(REPO / OUT, res / "references")
        (res / "run_log.json").write_text(json.dumps(dict(log=LOG, minutes=round((time.time() - T_START) / 60, 1),
                                                          quick=QUICK, sources=SOURCES), indent=1))
        shutil.make_archive(str(WORK / "references_results"), "zip", res)
        print(f"[checkpoint] references_results.zip {round((WORK / 'references_results.zip').stat().st_size / 1e6, 2)} MB", flush=True)


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


    def safe(name):
        return re.sub(r"[^A-Za-z0-9_-]+", "_", name.strip()).strip("_")


    # ============================ 0. SETUP =======================================
    shutil.rmtree(REPO, ignore_errors=True)
    for b in BRANCHES:
        if sh(f"git clone --depth 1 -b {b} {REPO_URL} {REPO}", "setup", f"clone ({b})", cwd=WORK, tail=2) and \
                (REPO / "experiments" / "sign_recovery.py").exists():
            break
        shutil.rmtree(REPO, ignore_errors=True)
    else:
        raise SystemExit("no branch with experiments/sign_recovery.py: push / merge refs-verify first")
    sh("python -m pip install -q cryptography scikit-image opencv-python-headless pillow tomli numpy scipy",
       "setup", "pip install", tail=2)
    DATA.mkdir(exist_ok=True)
    inputs = [os.environ["CLIPS_DIR"]] if os.environ.get("CLIPS_DIR") else ["/kaggle/input"]
    for f in sorted({f for r in inputs for e in ("mp4", "mkv", "avi", "mov", "webm")
                     for f in glob.glob(f"{r}/**/*.{e}", recursive=True)}):
        kind = "open" if any(k in f.lower() for k in ("bunny", "sintel", "tears", "elephant")) else "private"
        SOURCES[safe(pathlib.Path(f).stem)] = dict(path=f, kind=kind)
    if not QUICK:
        for name, url in OPEN_CLIPS.items():
            if any(name[:5] in k.lower() for k in SOURCES):
                continue
            dest = DATA / (name + pathlib.Path(url).suffix)
            if fetch(url, dest):
                SOURCES[name] = dict(path=str(dest), kind="open")
    kodak = DATA / "kodak"
    kodak.mkdir(exist_ok=True)
    for f in (glob.glob("/kaggle/input/**/kodim*.png", recursive=True) if ON_KAGGLE else []):
        shutil.copy(f, kodak / pathlib.Path(f).name)
    if len(list(kodak.glob("*.png"))) < 12 and not QUICK:
        for i in range(1, 13):
            fetch(KODAK_URL.format(i), kodak / f"kodim{i:02d}.png")
    if list(kodak.glob("*.png")):
        SOURCES["kodak"] = dict(path=str(kodak), kind="open", images=True)
    print("sources:", json.dumps(SOURCES, indent=1))
    checkpoint()

    # ============================ B35: sign-bit recovery (Lin et al.) ===============
    if RUN["b35_sign"]:
        jobs = [("skimage", f"python experiments/sign_recovery.py --frames {1 if QUICK else 8} "
                            f"{'--size 64x48 --levels LinU3 E1 E2' if QUICK else ''} --name skimage --out {OUT}/sign_recovery")]
        for name, s in SOURCES.items():
            img = s.get("images")
            n = 1 if QUICK else (12 if img else 2)
            stride = 1 if img else 600
            jobs.append((name, f"python experiments/sign_recovery.py --video '{s['path']}' --frames {n} --stride {stride} "
                               f"{'--size 64x48 --levels LinU3 E1 E2' if QUICK else ''} --name {name} --out {OUT}/sign_recovery"))
        with ThreadPoolExecutor(max_workers=PARALLEL) as ex:
            list(ex.map(lambda j: sh(j[1], j[0], "B35 sign-bit recovery (Lin et al.)", tail=10), jobs))
        checkpoint()

    # ============================ B36: video identification (Schuster et al.) =======
    if RUN["b36_fingerprint"]:
        vids = [s["path"] for k, s in SOURCES.items() if not s.get("images")]
        if len(vids) >= 2:
            fr = 60 if QUICK else 600
            sh(f"python experiments/video_fingerprint.py --sources " + " ".join(f"'{v}'" for v in vids) +
               f" --frames {fr} --stride 3 --size {'160x128' if QUICK else '320x240'} --name all_videos "
               f"--out {OUT}/video_fingerprint", "fingerprint", "B36 video identification (Schuster et al.)", tail=12)
        else:
            print("B36 skipped: fewer than two videos")
        checkpoint()

    # ============================ SUMMARY ========================================
    checkpoint()
    w = max(len(s) for _, s, _, _ in LOG)
    print("\n" + "\n".join(f"{sec:<16}{s:<{w + 2}}{st:<6}{t:>7.0f} s" for sec, s, st, t in LOG))
    fails = [f"{sec}: {s}" for sec, s, st, _ in LOG if st != "PASS"]
    print(f"\n{len(LOG) - len(fails)} passed, {len(fails)} failed, {(time.time() - T_START) / 3600:.2f} h")
    if fails:
        print("FAILED:", *fails, sep="\n  ")
    print("Download references_results.zip from the Output tab.")

# ==================================================================================================
# JOB = "benchmark"   SVE-Bench (experiments/benchmark_suite.py), added 17 Oct 2026
# ==================================================================================================
elif JOB == "benchmark":
    """Ours (E1-E5, both E5 forms) and four published schemes (Van Droogenbroeck 2002, Kishore 2015,
Auer 2013, Hirose 2024 with RI = 1 and 4) under the same four attacks, on every source (GUIDE.md B39).

HOW TO RUN: Internet ON, Accelerator None (CPU), + Add Input -> your clips dataset, paste this whole
file into ONE cell, Save Version -> Save & Run All (Commit), then send benchmark_results.zip.
QUICK = True: 3-minute smoke test.
"""
    QUICK = False
    REPO_URL = "https://github.com/bnsama29-cloud/FPGA-Video-Encryption-.git"
    BRANCHES = ["e5-hardware", "main"]          # the first one that has experiments/benchmark_suite.py
    OPEN_CLIPS = {
        "sintel_trailer": "https://download.blender.org/durian/trailer/sintel_trailer-480p.mp4",
        "tearsofsteel": "https://download.blender.org/demo/movies/ToS/tears_of_steel_720p.mov",
    }
    KODAK_URL = "http://r0k.us/graphics/kodak/kodak/kodim{:02d}.png"
    PARALLEL = 4

    import glob, json, os, pathlib, re, shutil, subprocess, sys, time, urllib.request
    from concurrent.futures import ThreadPoolExecutor

    T_START = time.time()
    ON_KAGGLE = os.path.exists("/kaggle")
    WORK = pathlib.Path(os.environ.get("WORK", "/kaggle/working" if ON_KAGGLE else "/tmp/kbwork"))
    WORK.mkdir(parents=True, exist_ok=True)
    QUICK = os.environ.get("QUICK", str(QUICK)) == "True"
    REPO, DATA, OUT = WORK / "repo", WORK / "opendata", "sim_out/benchmark_suite"
    ENV = {**os.environ, "PYTHONUNBUFFERED": "1"}
    LOG, SOURCES = [], {}


    def sh(cmd, sec, step, tail=16, cwd=None):
        t0 = time.time()
        print(f"\n=== [{sec}] {step}   (t = {(t0 - T_START) / 60:.0f} min)\n$ {cmd}", flush=True)
        p = subprocess.run(cmd, shell=True, cwd=cwd or REPO, env=ENV, capture_output=True, text=True)
        print("\n".join((p.stdout + p.stderr).strip().splitlines()[-tail:]), flush=True)
        LOG.append((sec, step, "PASS" if p.returncode == 0 else "FAIL", round(time.time() - t0, 1)))
        print(f"--> [{sec}] {LOG[-1][2]} in {LOG[-1][3]:.0f} s", flush=True)
        return p.returncode == 0


    def checkpoint():
        res = WORK / "benchmark_results"
        shutil.rmtree(res, ignore_errors=True)
        res.mkdir()
        if (REPO / OUT).exists():
            shutil.copytree(REPO / OUT, res / "benchmark_suite")
        (res / "run_log.json").write_text(json.dumps(dict(log=LOG, minutes=round((time.time() - T_START) / 60, 1),
                                                          quick=QUICK, sources=SOURCES), indent=1))
        shutil.make_archive(str(WORK / "benchmark_results"), "zip", res)
        print(f"[checkpoint] benchmark_results.zip {round((WORK / 'benchmark_results.zip').stat().st_size / 1e6, 2)} MB", flush=True)


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


    def safe(name):
        return re.sub(r"[^A-Za-z0-9_-]+", "_", name.strip()).strip("_")


    shutil.rmtree(REPO, ignore_errors=True)
    for b in BRANCHES:
        if sh(f"git clone --depth 1 -b {b} {REPO_URL} {REPO}", "setup", f"clone ({b})", cwd=WORK, tail=2) and \
                (REPO / "experiments" / "benchmark_suite.py").exists():
            break
        shutil.rmtree(REPO, ignore_errors=True)
    else:
        raise SystemExit("no branch with experiments/benchmark_suite.py: push / merge e5-hardware first")
    sh("python -m pip install -q cryptography scikit-image opencv-python-headless pillow tomli numpy scipy",
       "setup", "pip install", tail=2)
    DATA.mkdir(exist_ok=True)
    inputs = [os.environ["CLIPS_DIR"]] if os.environ.get("CLIPS_DIR") else ["/kaggle/input"]
    for f in sorted({f for r in inputs for e in ("mp4", "mkv", "avi", "mov", "webm")
                     for f in glob.glob(f"{r}/**/*.{e}", recursive=True)}):
        SOURCES[safe(pathlib.Path(f).stem)] = dict(path=f)
    if not QUICK:
        for name, url in OPEN_CLIPS.items():
            if any(name[:5] in k.lower() for k in SOURCES):
                continue
            dest = DATA / (name + pathlib.Path(url).suffix)
            if fetch(url, dest):
                SOURCES[name] = dict(path=str(dest))
        kodak = DATA / "kodak"
        kodak.mkdir(exist_ok=True)
        for f in (glob.glob("/kaggle/input/**/kodim*.png", recursive=True) if ON_KAGGLE else []):
            shutil.copy(f, kodak / pathlib.Path(f).name)
        if len(list(kodak.glob("*.png"))) < 24:
            for i in range(1, 25):
                fetch(KODAK_URL.format(i), kodak / f"kodim{i:02d}.png")
        if list(kodak.glob("*.png")):
            SOURCES["kodak"] = dict(path=str(kodak), images=True)
    SOURCES = {"synthetic": dict(path="synthetic"), **SOURCES}
    print("sources:", json.dumps(SOURCES, indent=1))
    checkpoint()

    jobs = []
    for name, s in SOURCES.items():
        img = s.get("images")
        n, stride = (3, 5) if QUICK else ((24, 1) if img else (20, 10 if s["path"] == "synthetic" else 60))
        size = "160x128" if QUICK else "320x240"
        jobs.append((name, f"python experiments/benchmark_suite.py --video '{s['path']}' --frames {n} --stride {stride} "
                           f"--size {size} --name {name} --out {OUT}"))
    with ThreadPoolExecutor(max_workers=PARALLEL) as ex:
        list(ex.map(lambda j: sh(j[1], j[0], "SVE-Bench"), jobs))
    checkpoint()
    w = max(len(s) for _, s, _, _ in LOG)
    print("\n" + "\n".join(f"{sec:<16}{s:<{w + 2}}{st:<6}{t:>7.0f} s" for sec, s, st, t in LOG))
    fails = [f"{sec}: {s}" for sec, s, st, _ in LOG if st != "PASS"]
    print(f"\n{len(LOG) - len(fails)} passed, {len(fails)} failed, {(time.time() - T_START) / 3600:.2f} h")
    print("Download benchmark_results.zip from the Output tab.")

else:
    raise SystemExit(f"unknown JOB {JOB!r}: complete | remaining | research | final | references | benchmark")
