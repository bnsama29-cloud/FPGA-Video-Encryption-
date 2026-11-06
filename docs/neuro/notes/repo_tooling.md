# Repository tooling: how paper 2 (event-camera encryption) plugs into the existing flows

Working notes for the `neuromorphic` branch. Everything below was read from the code on this branch
(6 Nov 2026), not from memory; file:function names are given so each claim can be checked. "Proposal"
marks what does not exist yet.

## 1. Folder conventions

- Six top-level folders: `hardware/` (rtl, tb, vivado, hls, vectors), `software/` (Python packages `model`,
  `link`, `system`, plus `scripts/`, `configs/`), `experiments/`, `results/` (board, hardware, security,
  simulation), `tests/`, `docs/`. Nothing new goes at the top level.
- `software/` is on the import path in three places: `pytest.ini` (`pythonpath = . software`), `conftest.py`
  (also exports `PYTHONPATH` so subprocesses and cocotb see it), `Makefile` (`export PYTHONPATH`). Elsewhere:
  `pip install -e .`.
- READMEs that list contents and must be kept in sync when files are added: `README.md` (root, section
  "Reproducing the results" at line ~81), `docs/README.md`, `hardware/README.md`, `software/README.md`,
  `software/system/README.md`, `experiments/README.md` (table: script -> result), `tests/README.md`,
  `results/README.md` and each `results/<area>/README.md` (names the run a snapshot came from).
  The new `docs/neuro/` folder must get a row in `docs/README.md`.
- Specs/logs: `docs/INTERFACES.md` (registers, nonce, arithmetic; keep in sync), `docs/TESTING.md`
  (§2 test order, §3 unit-test template, §8 bug log table `| # | Symptom | Root cause | Fix | Lesson |`),
  `docs/LITERATURE.md` (only references checked at their DOI), `docs/JOURNAL_RUNBOOK.md` (X-numbered
  experiments: command + output folder, software phase -> board phase -> paper phase).
- Outputs: every number from a script writing to `sim_out/<exp>/` (git-ignored); finished runs are copied
  unchanged into `results/`. Generated files `hardware/rtl/include/*.vh`, `hardware/hls/dct_coeffs.h` come
  from `make tables` only.
- RTL header line `Golden model: software/model/... :: fn()` is required in every RTL file.

Proposal for paper 2 (keeps paper 1 untouched): `software/model/evt/` (golden model), `hardware/rtl/` files
prefixed `evt_` (see §3 for why not a subfolder), `hardware/tb/test_evt_*.py`, `experiments/evt_*.py`,
`tests/test_evt_*.py`, `docs/neuro/` for design notes, results later under `results/<area>/neuro_*`.

## 2. Tests: model tests and cocotb testbenches

Two pytest trees:
- `tests/` = golden model + system layer (`make test-model`, `pytest.ini` `testpaths = tests`). Experiment
  cores are tested there on tiny inputs, e.g. `tests/test_journal_experiments.py` puts `experiments/`,
  `hardware/vivado/`, `software/scripts/` on `sys.path` and imports the script module directly.
- `hardware/tb/` = cocotb testbenches (`make test-rtl` = `pytest -q hardware/tb/`). Any new
  `hardware/tb/test_*.py` is collected automatically by `make test-rtl` and `make test`.

Runner helper, `hardware/tb/common.py`:
- `SOURCES = {top: [files relative to hardware/rtl, dependencies first]}`. A new top MUST be added here.
  Paths outside `hardware/rtl` work with `../../` (e.g. `"../../software/system/board/axis_tamper.v"`).
  `ASCON = ["ascon_round.v", "ascon_aead128_core.v"]` is reusable for any Ascon-based top.
- `run_sim(toplevel, test_module, parameters=None, testcase=None, build_tag="")`: cocotb_tools runner,
  Icarus by default (`SIM=verilator` optional), timescale 1ns/1ps, include dir `hardware/rtl/include`,
  build dir `sim_build/<top><build_tag>` (use `build_tag` for parameter variants), `seed=$SEED`, asserts
  zero failed cocotb tests. Env: `WAVES=1` (FST), `SEED=n`, `FULL=1` (long tests, `full_run()`).
- Helpers: `start(dut)` (100 MHz clock on `dut.clk`, synchronous active-high `dut.rst` pulse),
  `rng_for(dut)` (logs "random seed = N (re-run with SEED=N)"), `drive_stream(clk, valid, ready, items,
  apply, rng, p_idle)`, `collect_stream(clk, valid, ready, sample, done, rng, p_stall, timeout)`,
  `sval/uval/to_bits`.
- Test file shape (`test_crypto_units.py`): `@cocotb.test()` coroutines at the top, golden values from
  `model.*` (e.g. `ascon.keystream_bits(key, nonce, n)`), and at the bottom one plain pytest function per
  top: `def test_<top>(): run_sim("<top>", "<module>")`.
- Conventions (`docs/TESTING.md` §3 and CLAUDE.md): random idle on the input (`p_idle=0.2`) and random
  backpressure on the output (`p_stall=0.3`); react to DUT state at `FallingEdge` (values after
  `RisingEdge` are pre-edge, bug #2); hold data while `valid && !ready`.
- First-mismatch reporting: the assertion names the first differing index and the values, e.g.
  `assert got == exp, f"frame {frame}: first mismatch at bit {next(i for i in range(n) if got[i] != exp[i])}"`.
  Standard: index, input, got, expected (bug #4 in §8 shows why).
- Running one test: `make one T=hardware/tb/test_evt_x.py::test_evt_x SEED=<n>`; waves: `make waves T=...`;
  failure bundle: `make bundle T=...`. On this Windows PC call pytest with
  `E:/FPGA-Video-Encryption-/.venv/Scripts/python.exe -m pytest` (the Makefile defaults to `python3`;
  `make PY=...` overrides it).
- Contract checks between model views: `tests/test_hw_equivalence.py` (frame view == stage view) is the
  pattern for an event model with a packet-level and a stage-level (per-word) view.

## 3. Vivado: adding a new RTL top

Out-of-context flow, `hardware/vivado/vivado_ooc.tcl`:
- Arguments: `top period [PARAM value]... [PART device]`. Parameter pairs are two arguments, not
  `P=v` (Windows cmd splits at `=`, bug #19). `PART` selects another device.
- Reads `read_verilog [glob hardware/rtl/*.v]` (only that folder, no subfolders) with include dir
  `hardware/rtl/include`, then `synth_design -top $top -mode out_of_context` (retiming in "perf"),
  opt/place/phys_opt/route, and writes `utilization.txt`, `utilization_hier.txt`, `timing.txt`, `power.txt`,
  `routed.dcp` into `sim_build/vivado_<top>[_<period>ns][_<param><value>...][_part_<device>]/`.
- Clock XDC is read before synthesis; I/O delays are 20 % of the period on every port (bug #20), so a
  top whose ports are registered gets realistic numbers.
- Success marker in the log: `RESULT top=<top> period=<p>ns ... WNS=<x>ns`.
- Consequence for paper 2: a new top is picked up with no TCL change **only if its files sit directly in
  `hardware/rtl/`** (hence the `evt_` prefix). A subfolder `hardware/rtl/neuro/` would need an extra glob in
  `vivado_ooc.tcl` and `block_design.tcl`, and both files are shared with paper 1 (the running Vivado job
  reads them from the main checkout, not from this worktree). Module names must not collide with paper 1's.

`hardware/vivado/run_vivado_day.py` (one file, four tools: day / `vectors` / `check` / `parse`):
- Steps are chosen by `--steps` (argparse `choices=[...]` list in `day_main`) and dispatched by name:
  `globals()[f"step_{s}"](a)`. Adding a step = add `def step_neuro(a)` + its name to `choices`.
- An OOC step builds a list of jobs `(name, "hardware/vivado/vivado_ooc.tcl", "<top> <period> [P v]...")`
  and calls `vivado_many(a, jobs)` (honours `--parallel`, `--only`, `--dry-run`; retries a job with no
  `RESULT top=` line once with `SJPEG_IMPL=safe`). Pattern: `step_lanes`, `part_jobs`. `a.periods` gives
  the clock sweep.
- `parse` reads every `sim_build/vivado_*` folder automatically (`parse_main`, `_name` strips `vivado_`),
  so new OOC folders appear in `sim_out/vivado/vivado_tables.md` with no change. `collect` zips every
  `sim_build/vivado_*` report the same way (`vivado_results_<date>.zip`).
- Overlay folders are hard-coded in three places: `_name`, `parse_main` folder list, `step_collect` folder
  list (`lanes`, `lanes4`, ..., `lanestamper`). A new overlay subfolder must be added to all three.
- XSim: `hardware/vivado/xsim.prj` is an explicit list of sources + `tb_secure_jpeg_top.v`, and
  `make xsim-icarus` derives its file list from it. A new event testbench should get its own `.prj` and
  run script rather than extend paper 1's.
- Lint: `Makefile` `RTL_ALL` is an explicit file list with `--top-module secure_jpeg_top`; an event top
  needs its own `lint` line (proposal: `lint-evt`).
- `run_info()` records git commit, branch and dirty state of `hardware/rtl`, `hardware/vivado`,
  `software/system/board` plus SHA-256 of `overlay/secure_jpeg*.bit/.hwh` (pattern would need to include
  the event bitstream name).

Block design (`software/system/board/block_design.tcl`, `step_bd` in run_vivado_day.py):
- `-tclargs <fclk MHz> <jobs> <design>`; `design` selects `projdir`, `outname`, the wrapper module
  `bdtop` (a `.v` in `software/system/board/`, e.g. `sjpeg_lanes_bd_top.v`) and the pixel width `pxbits`,
  then builds PS7 + AXI DMA (simple mode, HP0 64-bit) + AXI-Lite on GP0 + interrupt concat.
- Adds `glob hardware/rtl/*.v`, the wrapper, and the `.vh` headers as "Verilog Header" (bug #18).
- Output: `software/system/board/overlay/<outname>.bit/.hwh`, reports in `overlay/` (v2) or
  `overlay/<design>/`; success marker `RESULT overlay ... fclk=<f>MHz WNS=<x>ns`; `step_bd` retries at lower
  clocks (`FALLBACK_MHZ`) when WNS < 0.
- Registry: `software/system/board/bitstreams.json` (file, design, step, VERSION, clock, run, sha256 prefix,
  purpose) checked by `software/scripts/publish_bitstreams.py` (writes `overlay/MANIFEST.md`).

## 4. Kaggle jobs

`software/system/kaggle/kaggle_runs.py`: one file pasted into one Kaggle cell.
- `JOB = "<name>"` at the top selects an `if/elif JOB == "<name>":` block; the final `else` raises
  `unknown JOB` and lists the names (update that message and the module docstring list when adding one).
  Existing: complete, remaining, research, final, references, benchmark, journal.
- Each block starts with a docstring (HOW TO RUN, WHAT IT RUNS with estimated minutes per step, NOT HERE),
  then a `SETTINGS` section: `QUICK`, `REPO_URL`, `BRANCH` (or a `BRANCHES` list tried in order), data
  lists, `RUN = dict(step=True, ...)` switches.
- `QUICK = os.environ.get("QUICK", str(QUICK)) == "True"`: a ~20 min smoke test with tiny sizes; its numbers
  mean nothing. Every command takes a QUICK-dependent argument (`--frames {2 if QUICK else 24}`).
- Setup: `git clone --depth 1 -b {BRANCH} {REPO_URL} {REPO}` into `/kaggle/working/repo` (WORK falls back to
  `/tmp/...` off Kaggle), `pip install -q -e . <extras>`, GPU check via `torch.cuda.is_available()`; GPU
  steps run last and only `if HAVE_GPU or QUICK`.
- `sh(cmd, section, step, tail)` runs a step from the repo root with `PYTHONPATH=repo/software:repo`, logs
  PASS/FAIL and seconds, and never stops the run on a failure.
- `checkpoint()` after every step: copies `sim_out/<job>/` (ignoring `*.npz`, `*.pt`, large files) into
  `WORK/<job>_results/`, writes `run_log.json` (log, minutes, quick, branch), zips to
  `/kaggle/working/<job>_results.zip` (downloaded from the Output tab). A crash keeps finished steps.
- Inputs: public data fetched with `fetch(url, dest)` (User-Agent header, size check); private Kaggle
  datasets found under `/kaggle/input/**`; private frames are never saved, only numbers.
- Proposal for paper 2: `JOB = "neuro"` with `BRANCH = "neuromorphic"`, output `neuro_results.zip`,
  `sim_out/neuro/<exp>/`; datasets (DVS Gesture, N-MNIST, an E2VID/FireNet checkpoint) need download URLs
  and licences checked before they go into the script.

## 5. Board and UDP

- Board scripts run on the PYNQ-Z2 as `sudo -E python3 -m system.board.<script> --bitfile ...`; every one
  has a `--mock` path that emulates the IP with the golden model, so the script is tested on the laptop
  (`first_contact.py --mock`, `board_sender.py --mock`).
- `software/system/board/pynq_driver.py`: `PynqBackend(bitfile, ip_name, dma_name, ...)` loads
  `pynq.Overlay(bitfile)`, sets FCLK0 to the clock the image was built for (`built_fclk_mhz`,
  `choose_fclk`: PYNQ otherwise applies 62.5 MHz), finds the IP by a name containing `sjpeg`/`secure_jpeg`
  and the DMA by `dma`, allocates `uint32` DMA buffers. `SecureJpegIP(backend)` checks the `VERSION`
  register (0x5EC00200 v2, 0x5EC003LL v3) before anything else. `MockBackend` implements the same
  `read/write/load/run/transfer` interface in Python. An event IP needs its own VERSION value, IP-name
  match, driver class and mock backend (proposal: `evt_driver.py`).
- `first_contact.py` is the gate: Part 1 bit-exactness against the golden model with first-mismatch
  report (size, mode, frame, byte offset), resumable (`--resume`), Part 2 speed (CYCLES register); writes
  `sim_out/board/first_contact.json/.md`.
- UDP: the board does not open its own sockets for video; `board_sender.py` wraps the FPGA as a
  `BoardEncoder` and runs the unchanged `link.sender.Sender`. Transport is `software/link/wire.py`:
  - `fragment(mtype, payload, msg_id, stream, size=1200, t_ms)`: 24-byte header
    `!2sBBIIHHQ` = `'SV'`, version 1, type, stream id u32, message id u32, fragment index u16, count u16,
    send time ms u64; then `send_message(sock, addr, ...)`, `udp_socket(bind_port, host, timeout)`
    (4 MB buffers), `Reassembler(timeout).add(datagram)` (drops incomplete messages, counts junk).
  - Types: `VIDEO=1, FEEDBACK=2, TELEMETRY=3, PREVIEW=4, CONTROL=5`; `Bus` sends JSON telemetry and preview
    JPEGs to the dashboard; `send_control(cfg, port_key, **cmd)` sends JSON commands.
  - The header is not authenticated by design; the payload's own tag protects it. Fragment size comes from
    `cfg["link"]["fragment"]`; ports and hosts from `link.config` / `software/configs/default.toml`
    (`--set link.host=... link.bind_host=0.0.0.0 link.sender_host=<board IP>` for two machines).
  - Proposal: event packets as a new message type (e.g. `EVENTS = 6`) in `wire.py`, one EVT packet (~1 ms,
    words + 16-byte tag) per message; nodes still never import each other.
- Keys (`software/link/keys.py`): `kdf(key, label, ctx)` = `ascon.mac` under nonce
  `make_nonce(0, ctx, 1)` (session 0 reserved for the KDF); `feedback_key`, `video_key(master, epoch)` with
  the one-way ratchet `kdf(k, "ratchet", e)`; `session_id(base48, epoch16)`; `Ratchet`; hybrid ML-KEM +
  X25519 key exchange (`kex_init/respond/finish`). Nonce: `model/ascon.make_nonce(session_id64, ctr63,
  purpose1)`, purpose 0 = keystream, 1 = tag. Only one purpose bit exists, so separate keystreams for the
  V2 permutation and the V1/V3 polarity/timestamp XOR need either KDF subkeys (`kdf(k, "evt-perm")`, ...)
  or a split of the counter; this must be fixed in `docs/INTERFACES.md` before RTL.
- Feedback (`software/link/feedback.py`): `FeedbackWriter(key, fb_session).pack(dict)`,
  `FeedbackReader(key).unpack(bytes) -> (status, msg)` with status ok/forged/replay/malformed;
  `ReplayWindow(64)` per RFC 3711 §3.3.2, reusable as-is for packet counters.

## 6. Attack library (what exists and its API)

- Network attacks, `software/link/channel.py`: `ATTACKS = ["bitflip", "downgrade", "splice", "inject",
  "replay", "delay", "drop", "flood", "fb_drop", "fb_forge", "fb_replay"]`, started by JSON over UDP to
  `link.control`: `{"cmd":"attack","type":"replay","duration":10,"rate":1.0}`, `{"cmd":"stop"}`,
  `{"cmd":"impair","loss":..,"delay_ms":..,"jitter_ms":..,"reorder":..}`. Implementation is in
  `Channel.on_video` and is JPEG-specific: `_scan_span` parses the JPEG, `downgrade` rewrites the byte at
  `SJV1`+5, `_inject` bumps the counter at `SJV1`+14..22 and writes a random tag at +22..38, `splice` takes
  the scan of a frame 5 back, `replay` re-sends a random old frame from `history`. Scripted runs:
  `experiments/scenario.py --scenario experiments/scenarios/*.json`, repeated with
  `experiments/repeat_runs.py`. For events: the same control vocabulary (inject/replay/delete=drop/splice)
  can be kept, but the payload editing needs an EVT-packet equivalent of `_scan_span`/`SJV1` offsets.
- Eavesdropper view: `Channel._attacker_view` -> `model.jpeg.replacement_attack_jpeg` (tile "attacker").
- Offline attacks:
  - `experiments/benchmark_suite.py` (SVE-Bench): `SCHEMES` dict of `s_<name>(an, ctr, key)` functions
    (ours E1-E5, VanDroogenbroeck, Kishore, Auer, Hirose, EtC, Tang) and attacks A1 decode, A2 replacement,
    A3 NZCA, A4 known-plaintext (recover permutation + keystream from one known frame); method in
    `docs/BENCHMARK_METHOD.md`. The scheme-dict + uniform-attack pattern is the template for comparing V0-V4
    with Du 2021 / Zhang 2024 (references to be checked in `docs/LITERATURE.md` first).
  - `experiments/learned_attack.py`: U-Net, `--train-source/--test-source` (different scenes), `--modes`,
    controls (median-of-training prior, frame-statistics oracles), bootstrap 95 % interval, writes
    `results.json/.md`, `examples_<mode>.png`; GPU on Kaggle.
  - `software/system/attacks/jigsaw_attack.py`, `mst_jigsaw.py`: position-recovery attacks on the E5
    shuffle (closest analogue to an attack on the V2 position permutation); `experiments/chosen_plaintext.py`
    on the shuffle; `experiments/sign_recovery.py`, `video_fingerprint.py` (size side channel), `size_leak.py`.

## 7. Checklist when adding a paper-2 component

1. Model function in `software/model/evt/...` + `tests/test_evt_*.py` (first-mismatch messages).
2. RTL `hardware/rtl/evt_*.v` (Verilog-2001, `default_nettype none`, sync active-high `rst`, valid/ready,
   `Golden model:` header line) + `SOURCES` entry in `hardware/tb/common.py` + `hardware/tb/test_evt_*.py`
   ending in `def test_<top>(): run_sim(...)`.
3. `docs/INTERFACES.md` section for the event format, nonce/key split, registers.
4. Vivado: `step_neuro` in `run_vivado_day.py` (+ `choices`), wrapper + `design` branch in
   `block_design.tcl`, overlay folder in `_name`/`parse_main`/`step_collect`, `bitstreams.json` row.
5. Experiment `experiments/evt_*.py` writing `sim_out/neuro/<exp>/`, row in `experiments/README.md`,
   runbook row (N1-N10) in a paper-2 runbook, Kaggle `JOB = "neuro"` block.
6. READMEs of every touched folder; `docs/TESTING.md` §8 row for every bug found.
