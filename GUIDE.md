# Helper guide: what is done, what is left, and how to do each remaining task

This is the **one guide** for the rest of the project (it replaces the old HELP_GUIDE, ROADMAP and
REMAINING_WORK files). Give it to Claude together with `docs/TEAM_CONTEXT.md` when you pick a task.

**Team.** CMOS Crusaders, RVCE: Aravind R, Suhas VJ, Rishab HR, Samarth BN, Vijaysurya BS. Mentor: Dr. Chetana G.

**Deadlines.** Working hardware by **12 Nov 2026**; conference paper by **15 Dec 2026**.

**Roles:**

| Role | Area |
|---|---|
| 1 | Hardware & Vivado |
| 2 | Crypto & protocol |
| 3 | Network & attacker |
| 4 | Receiver, dashboard & demo |
| 5 | Defence, ML & visual security |

---

## 1. Where the project stands (20 Oct 2026: papers split into conference + IEEE Access, board guide ready)

| Part | State | Evidence |
|---|---|---|
| Golden model + contracts v2/v3 | ✅ done | `model/`, `docs/INTERFACES.md`, 1089 Ascon KATs |
| RTL, single pipeline (E0–E4) | ✅ bit-exact with the model in cocotb + Icarus, 0 extra cycles for encryption | `tb/`, `make test` |
| RTL, lane encoder (E0–E5, 1/2/4 lanes) | ✅ bit-exact with the model, E5 included (B6) | `tb/test_lanes_top.py`, `rtl/secure_jpeg_lanes_top.v` |
| Vivado testbench | ✅ Icarus · ✅ Vivado XSim 2026.1, both designs, E5 frames included (run 7) | `make xsim-icarus`, `python vivado/run_vivado_day.py --steps xsim` |
| Post-route resources / timing / power | ✅ run 7 (18 Oct, 27/27 steps): encoder, 2 and 4 lanes with E5 and both PYNQ-Z2 systems meet 100 MHz; power from simulated activity (SAIF) | `paper/data/vivado/`, §4.1 |
| System simulation (feedback, ratchet, defence, attacks, dashboard) | ✅ | `link/`, `experiments/` |
| Simulation results (private clips, open data, learned attackers, jigsaw, sign recovery, recognition, size channel) | ✅ Kaggle runs 14–17 Oct | `paper/data/simulation/`, `paper/data/extra/` |
| SVE-Bench: ours vs four published schemes under the same attacks | ✅ Kaggle 18 Oct (method v2), in the paper | `paper/data/benchmark/`, B39/B41 |
| PYNQ-Z2 board tests | ⏳ E5 bitstream built (tom's PC, not in git: keep a copy, `docs/HW_TODO.md` H5); `first_contact` passes against the emulated board for E0–E5; **not yet run on the board**. Step-by-step manual: `docs/FPGA_HANDS_ON.md` | §4.2 |
| Phase 2 demo | ✅ LAN dashboard + VLC (Aravind, `docs/DASHBOARD_LAN_DEMO.md`); fresh pre-shared key `scripts/demo_key.py`; script and judge Q&A `docs/PHASE2_DEMO.md` | `tests/test_dashboard.py`, `tests/test_demo_key.py` |
| Paper | 📝 two papers: `conference.pdf` (exactly 6 pages, condensed, 7 figures) and `access.pdf` (IEEE Access, 24 pages, maths with lemmas/propositions, gate-level and block-design figures); open TODOs are author details, board/ARM results and the AI disclosure | `paper/conference.tex`, `paper/access.tex`, `cd paper && make` |

**Rough position: ~75 % of the project.** Design, simulation, Vivado and the security evaluation are
finished. Left: the board (§4.2, the critical path to 12 Nov), the ARM baseline (A3 + B1), then the
board numbers in the paper and the final proof-reading.

A full re-run on a fresh Windows 11 PC (WSL Ubuntu 24.04, 18 Oct) reproduced the simulation side:
`make test` (154 + 16 passed), `RUN_SLOW=1 pytest tests/` (155 passed), `make xsim-icarus` (v2 5 frames,
v3 7 frames incl. E5, bit-exact), the dashboard on port 8000; Vivado run 7 ran on the same PC.

The headline results (generated tables in `paper/tables/`, numbers in `paper/tables/numbers.tex`):

* **Encryption cost.** 0 extra cycles in RTL. The encoder meets 100 MHz post-route: 65 Mpixel/s,
  212 fps at 640×480. Two and four lanes reach 122 and 176 Mpixel/s in RTL simulation; E5 costs 2–4 %.
* **Area and power (run 7).** Encoder 5,037 LUT, about 211 mW (SAIF). E5 adds +2 % LUT to the lane
  encoder, no BRAM or DSP, and no power (2 lanes: 318 mW with E5, 319 mW with E2).
* **Attack suite.** 11/11 attacks are mitigated in 0.91 s on average, with 0/375 false alarms
  (3 runs); benign impairments give 0/447.
* **Outline leakage** on 9 sources: E1–E4 leak an outline (edge correlation 0.28–0.56); E5 removes
  it (−0.007…0.014). Jigsaw solvers (greedy, MST) restore at most 2.5 % of E5's neighbours (chance).
* **Published schemes (SVE-Bench, 175 frames).** Van Droogenbroeck, Kishore, Auer and Hirose leak
  0.58–0.94 at their strongest attack; the fixed-key ones fall to one known frame. E5 stays ≤ 0.02.
* **Learned attackers.** The U-Net breaks E1 (edge 0.69, SSIM 0.79). Under E5 it scores SSIM 0.34,
  no more than an oracle of each frame's true colour statistics (0.36); the adversarial P5 gets 0.26.
* **Restart interval.** Keep N = 1: at N = 32 a beam-search solver chains 15–41 % of the segments.
* **Frame sizes.** Every level leaks motion and video identity equally (98 % identification of 7 videos);
  only constant-size frames close it.
* **Bandit vs threshold over 10 seeds.** The bandit encrypts 14 % fewer bits but reacts slower
  (1.34 s vs 0.46 s). A trade-off, not a win.
* **Format compliance.** Every mode decodes in Pillow, OpenCV, scikit-image and ffmpeg.

---

## 2. Setup and commands

```bash
git clone https://github.com/bnsama29-cloud/FPGA-Video-Encryption-.git && cd FPGA-Video-Encryption-
python3 -m venv .venv && source .venv/bin/activate           # Windows: use WSL, work in ~/ not /mnt/c
pip install -r requirements.txt
```

**Tools:**

* **Icarus Verilog 12** for the RTL tests. Ubuntu 24.04: `sudo apt install iverilog`. Ubuntu 22.04
  ships 11, so build 12 from source as `kaggle_runs.py (JOB = "complete")` does.
* **Verilator:** `pip install verilator`.
* **Vivado ML Standard 2026.1** (free; the version of runs 1–7) for Role 1 only; see
  `docs/VIVADO_ONE_DAY.md`.

**Windows PCs: two copies of the repo.** Run tests and simulations in WSL (Ubuntu 24.04 gives
Icarus 12) from a clone in `~/`. Vivado is a Windows program and needs a **separate Windows clone at a
path without spaces** (e.g. `D:\FPGA-Video-Encryption-`), driven from a normal Command Prompt with
`settings64.bat` loaded (or the AutoRun entry of `docs/VIVADO_ONE_DAY.md` §0). Open the WSL copy in
VS Code through the WSL extension (`code .` from the Ubuntu terminal), not as `\\wsl.localhost\...`,
or git and Python run on the Windows side.

**Git: fork and upstream.** The team repository is `bnsama29-cloud/FPGA-Video-Encryption-`. Work is done
on a fork branch (e.g. `vij-ship-it/FPGA-Video-Encryption-`, branch `claude/project-thread-yxa59j`)
and reaches `main` through a pull request (#31, #32). `git fetch upstream && git log upstream/main..HEAD`
shows exactly what a PR will bring.

| Command | What it does |
|---|---|
| `make test` | model + system + RTL tests; must pass before every merge (~1 min) |
| `RUN_SLOW=1 python -m pytest tests/` | adds the end-to-end UDP link test |
| `make xsim-icarus` | the Vivado testbench, run in Icarus |
| `make lint` / `make hls-csim` / `make synth` | Verilator lint / HLS C-sim / Yosys estimate |
| `make one T=tb/test_top.py SEED=n`, `make bundle T=...` | one test reproducibly / failure report for Claude |
| `python -m link.run_all` | the whole link + dashboard on http://localhost:8000 |
| `python experiments/scenario.py --scenario experiments/scenarios/full_suite.json` | one attack scenario |
| `python experiments/policy_seeds.py --seeds 1 2 3` | bandit vs threshold over seeds |
| `python experiments/measure_mode_tradeoff.py --video clip.mp4` | leakage vs cost per mode |
| `python experiments/learned_attack.py --train-source a.mp4 --test-source b.mp4` | neural attacker (GPU) |
| `python -m future_work.attacks.jigsaw_attack --video clip.mp4` | jigsaw attack on E5 |
| `python vivado/run_vivado_day.py` | XSim + post-route numbers + overlay + tables (Vivado; on Windows: `py vivado\run_vivado_day.py --steps xsim ooc lanes bd_lanes power parse --jobs 2`) |
| `python -m future_work.board.first_contact` | bit-exact gate + fps on the PYNQ-Z2 |
| `python -m future_work.figures.paper_tables --root <results>` | every paper table from result files |
| `cd paper && make` | build `conference.pdf` and `access.pdf` (`make tables` first after new results). Needs `texlive-latex-extra texlive-publishers texlive-science texlive-pictures` (or Overleaf) |

**The remaining GPU tasks in one Kaggle run:** `future_work/kaggle/kaggle_runs.py (JOB = "remaining")` (GPU T4, Internet on,
your clips dataset attached). With `RERUN = True` (the default now) it only repeats what the fixes of
14 Oct changed — the restart interval on the open sources and both learned attacks with the new
no-ciphertext control (B20, B21, ~1 h). `RERUN = False` repeats the whole open-data run (~1.5 h). It
uses the first branch in `BRANCHES` that has the fixed experiments. Unzip `remaining_results.zip`, copy
`extra/` over `paper/data/extra/` (keep the README), run `python paper/make_assets.py`, `cd paper && make`.

**Re-running all the simulation results:** paste `future_work/kaggle/kaggle_runs.py (JOB = "complete")` into one
Kaggle cell (Internet on, GPU T4, clips as a private dataset), then *Save & Run All*. It takes ~4 h
with `PARALLEL = 1` and writes `results.zip`. Unzip it into `paper/data/` and run `cd paper && make`.

---

## 3. Repository map

```
model/          golden model = the referee (Ascon, colour, DCT/quant, entropy, selective, JPEG container)
rtl/            Verilog-2001 encoder + Ascon keystream/tag + AXI (secure_jpeg_top.v); include/ is generated
tb/             cocotb testbenches, every block vs the model under random stalls
vivado/         XSim testbench, run_vivado_day.py (the Vivado day + vectors/check/parse tools), vivado_ooc.tcl
hls/            Vitis HLS DCT + quantiser (same arithmetic as the RTL)
link/           system simulation: sender, channel/attacker, receiver, feedback, keys, defence, dashboard
experiments/    every paper number: scenarios, policies, policy_seeds, mode trade-off, crypto benchmark,
                learned attack
future_work/    board/ (PYNQ driver, block design, board sender, first_contact), baselines/, attacks/
                (jigsaw), figures/ (grid, compliance, paper_tables), kaggle/kaggle_runs.py (every Kaggle run)
paper/          conference.tex (6 pages), access.tex + sections/ (IEEE Access), refs.bib, data/ (the results they are built from),
                make_assets.py (tables + figures from data/)
scripts/        tools.py: older golden-model tools (encode-image, video-eval, mjpeg-server, export-vectors, bundle);
                demo_key.py: fresh pre-shared demo key + the laptop/board commands
tests/          pytest for model, contract, system, future_work, report parsers
docs/           INTERFACES (contracts v2, v3), TESTING (+ bug log, debugging with Claude), TEAM_CONTEXT
                (for Claude), VIVADO_ONE_DAY, RESEARCH (R1-R8 + throughput notes), FPGA_HANDS_ON (board
                manual), BOARD_BRINGUP (task list), HW_TODO, PHASE2_DEMO (demo script + judge Q&A),
                DASHBOARD_LAN_DEMO (LAN + VLC)
```

---

## 4. The remaining work

Status key: ⏳ ready to run (scripts exist) · 📝 to be written · ✅ done.

### 4.1 Vivado ✅ (run 6, 17 Oct 2026; run 7 with E5, 18 Oct)

Everything in **`docs/VIVADO_ONE_DAY.md`** (install, the one command, results, board first contact,
troubleshooting, history of runs 1-6). Run 6 passed all 20 steps: encoder WNS +0.554 ns, 2 lanes
+0.400, 4 lanes +0.440 (out of context), v2 overlay +0.788, 2-lane overlay +0.208 ns at 100 MHz.
Run 7 (18 Oct, tom's PC, 27/27 steps) rebuilt the lane encoders and the 2-lane system **with E5**: 2 lanes 10,069 LUT (+200) WNS +0.359, 4 lanes 16,893 (+320) +0.293, 2-lane overlay 11,913 (+197) +0.228 ns, no extra BRAM/DSP; SAIF power 0.318 W (E5) vs 0.319 W (E2) for 2 lanes. Snapshot (runs 6 + 7) in `paper/data/vivado/`, in the paper. At 125 MHz the colour converter is the next
limit (v2 -0.875 ns). Bitstreams (not in git): the run 6 pair on Samarth's laptop, and the **E5
2-lane system from run 7** on tom's PC (`D:\FPGA-Video-Encryption-\future_work\board\overlay\secure_jpeg_lanes.bit` + `.hwh`).

Run 7's E5 bitstream: 18 Oct 18:17, DRC 0 errors, WNS +0.228 ns; results in `vivado_results_20261018_1847.zip`.
Note that the `xsim` step builds its contract-v3 vectors for E0–E4 only; E5 is checked bit-exact in XSim
by the `power` step (one 320×240 frame) and in Icarus by `make xsim-icarus` (`--modes 2 5`).

**Still to do:** share the `.bit` + `.hwh` pairs (commit them or copy them to the board's SD card) so
teammates without Vivado can use the board.

### 4.2 Board (critical path, deadline 12 Nov) ⏳

Step by step, from unboxing to every number below: **`docs/FPGA_HANDS_ON.md`** (wiring, jumpers, LEDs, which machine runs which command, expected output, troubleshooting, demo checklist); short task list: `docs/BOARD_BRINGUP.md`; what is left in hardware: `docs/HW_TODO.md`.

| # | Task | Owner | Time | How | Done when |
|---|---|---|---|---|---|
| A1 | **Bit-exact gate on silicon** | 1 | ½ day | copy the repo and the `.bit` + `.hwh` to `/home/xilinx/fpga`, then `sudo -E python3 -m future_work.board.first_contact --bitfile future_work/board/overlay/secure_jpeg_lanes.bit --sizes 320x240 640x480 --frames 10` (already passes with `--mock --mock-lanes 2 --mock-e5`) | all modes E0–E5 byte-identical with the model |
| A2 | FPGA speed | 1 | same run | part 2 of the same script | fps table in `sim_out/board/first_contact.md` |
| A3 | ARM baseline on the same board | 2 | ½ day | `python3 -m future_work.baselines.bench_software_codecs --sizes 320x240 640x480 --frames 30` | `baselines_<host>.md` |
| A4 | Power and energy per frame | 1 + 5 | 1 day | USB meter: idle / ARM / FPGA per mode, 30 s averages → `future_work/baselines/power_template.csv` → `python -m future_work.baselines.energy_table <csv>` | mJ/frame, FPGA vs ARM |
| A5 | Live link board → laptop | 3 + 4 | 1 day | board: `python3 -m future_work.board.board_sender --bitfile ... --set link.host=<laptop> --set link.bind_host=0.0.0.0`; laptop: `python -m link.run_all --no-sender --set link.bind_host=0.0.0.0 --set link.sender_host=<board>` | the dashboard shows the board's stream |
| A6 | Attacks against the board | 3 | 1 day | `experiments/scenario.py --external-sender <BOARD IP>` with `full_suite.json` and `benign.json`, 3 runs each (docs/BOARD_BRINGUP.md §8) | "on hardware" row in the reaction table |
| A7 | Webcam on the board | 4 | ½ day | `--set sender.source=webcam:0` | live demo |
| A8 | Demo video (2 min) | 4 | ½ day | calm → attack → detection → recovery | linked in the README (not in git) |

**If A1 fails**, the board is wrong, not the model. Check, in this order:

1. the clock (FCLK0 running);
2. reset polarity (active high);
3. DMA lengths;
4. the pixel word order `{pad, B, G, R}`;
5. the HI registers (0x4C, 0x50).

`first_contact.py` reports the first differing byte.

**Rule:** report what you measure. If the FPGA path is not more energy-efficient than the ARM on some
metric, the paper says so; the playability, integrity and zero-cycle claims stand anyway.

### 4.3 Polish that makes the claims stronger

P1 = the paper is weak without it, P2 = clearly stronger, P3 = future-work section of the paper.
Every item has a **Done when** line: that is the test the reviewer of the pull request checks.

**Done on 14 Oct (open-data run, `paper/data/extra/`):**

| # | Item | Result | Where in the paper |
|---|---|---|---|
| B2 | Open, citable data | Sintel trailer + Tears of Steel (CC BY 3.0) and Kodak; Fig. 2 now shows a Sintel frame | §V setup, Fig. 2, Tab. IV |
| B4 | Learned attack on more data | P3 (open clips) and P4 (3 → 3 clips, 2,609 frames, wider U-Net, 35 epochs) | Tab. V |
| B5 | Restart-interval study | N = 1, 2, 4, 5, 8, 10, 32 with `experiments/restart_interval.py` (E5(N) built from the model's own blocks; the model itself stays at N = 1) | Tab. VI |
| B13 | Standard image-encryption metrics | `experiments/standard_metrics.py` on 8 sources | §V text (table in the repo) |
| B15 | Non-zero counting attack | block-level NZCA correlation per N | Tab. VI |
| B16 | Standard image set | Kodak 24 in every leakage/jigsaw/metrics run | Tab. IV |
| B17 (part) | Stronger learned attacker | multi-clip training done; GAN-style attack still open (B17 below) | Tab. V |

**Open items:**

| # | Item | P | Owner | Time | Spec |
|---|---|---|---|---|---|
| B25 | **Global-statistics control for E5** | P2 | 5 | ✅ measured: U-Net E5 SSIM 0.34 [0.33, 0.36] vs oracle of true frame statistics 0.36 [0.34, 0.37]; in the paper | below |
| B1 | **Selective encryption in C** on the ARM (fair software baseline) | P1 | 2 | 1–2 d | below |
| B3 | **Threat model + nonce-uniqueness argument** (1 page) | P1 | 2 | ½ d | ✅ in the paper (§III threat model and nonce subsections) · ⏳ `docs/THREAT_MODEL.md` |
| B22 | **E1's status after the U-Net result** (documentation + defaults) | P1 | 2 + 5 | ½ d | below |
| B14 | ✅ **Comparison table in the paper** (Table II, `paper/data/related/compare.json`) | P1 | 1 + 2 | done | §7 |
| B26 | Research R1: stall profile + frame-size law (RTL) | P2 | 1 | ✅ VM + Kaggle (640x480 measured 1.534 cycles/px, law confirmed) | `docs/RESEARCH.md` |
| B27 | Research R2: parallel lanes over restart segments (+ per-segment keystream, contract v3) | P3 | 1 + 2 | ✅ model, exact on 7 sources; ✅ **RTL built** (`rtl/secure_jpeg_lanes_top.v`, 16 Oct), measured 122 / 176 Mpx/s for 2 / 4 lanes; ✅ Vivado run 6: 100 MHz post-route, 2-lane overlay built; ⏳ board | `docs/INTERFACES.md` §8 |
| B28 | Research R3: bitrate regulation (FF+PI) | P2 | 3 | ✅ synthetic + 6 real clips after bugs #22-#26 (error 3-7x lower than fixed quality; FF+PI settles in <= 2 frames) | `docs/RESEARCH.md` |
| B29 | Research R4: change-driven coding, motion leakage, useful chaff + size padding | P2 | 5 | ✅ synthetic + 6 film clips (fixed-camera technique; static-camera clip wanted) | `docs/RESEARCH.md` |
| B30 | Research R5: clock sweep 125/150 MHz, critical blocks | P2 | 1 | ✅ run 6: 125 / 150 MHz fail (v2 -0.875 / -1.765 ns, colour converter; 2 lanes -1.071 / -2.023 ns, inside a lane); estimated fmax 104–108 MHz | `docs/RESEARCH.md` |
| B31 | Frame-size side channel (R7: every level E0-E5 leaks the same; separability 0.95 fixed camera, 0.50-0.95 films): constant-size padding option in `link/` + static-camera clip | P1 | 2 + 5 | ✅ measured, in the paper (Discussion); padding option and FF+PI rerun open | `docs/RESEARCH.md` |
| B33 | Research R8: chosen-plaintext attack (Li et al.) on the E5 shuffle, transferred across frames | P1 | 5 | ✅ 7 sources (chance-level placement) | `docs/RESEARCH.md` |
| B34 | Deployable size padding (running max / 10 s window) in `link/sender.py`, measured in R7 | P1 | 2 + 5 | ✅ 0.54 for +3 % (fixed camera), 0.54-0.78 on clips; sender option open | `docs/RESEARCH.md` |
| B35 | **Sign-bit recovery attack** (Lin et al. 2024, LP relaxation) against E1-E4, with a check in their own setting | P1 | 5 | ✅ Kaggle 17 Oct: 29 frames, 9 source sets (Kodak, open films, private clips); in the paper | `experiments/sign_recovery.py`, `docs/RESEARCH.md` |
| B36 | **Video identification from frame sizes** (Schuster et al. 2017) for E2, E5 and the padding schemes | P2 | 5 | ✅ Kaggle 17 Oct: 7 videos; in the paper (Table XII extended, one sentence in the conference version) | `experiments/video_fingerprint.py` |
| B37 | Vivado power with simulated switching activity (SAIF from the XSim testbench) instead of the vectorless estimate | P2 | 1 | ✅ run 7 (18 Oct): v2 0.210-0.211 W (E0/E2/E4), 2 lanes 0.319 W (E2) / 0.318 W (E5); `paper/data/vivado/`, in the paper (`\SaifTopMw`, `\SaifLanes*Mw`) · ⏳ board | `docs/HW_TODO.md` H4 |
| B39 | **SVE-Bench**: ours and four published schemes (Van Droogenbroeck, Kishore, Auer, Hirose) under the same four attacks | P1 | 5 | ✅ Kaggle (re-run with method v2, received 18 Oct 10:01): 9 sources, 175 frames; `paper/data/benchmark/`; in the paper (§V paragraph in both versions, `tab_bench.tex` in the extended one; `tab_bench_metrics.tex` not yet `\input`) | `experiments/benchmark_suite.py` |
| B40 | Hardware figures of merit as hardware papers report them: Mpixel/s per kLUT, input Gbit/s, nJ/pixel, per mode (E5 rows) | P2 | 1 | ✅ from RTL throughput + Vivado run 7 (E5 netlist, SAIF power for v2 and 2 lanes; 4 lanes vectorless): 2 lanes E5 2.7 nJ/pixel · ⏳ board | `experiments/hw_efficiency.py` |
| B41 | **SVE-Bench method v2** (comparable with published work): A4 becomes a known-plaintext attacker (permutation and keystream recovered from one clear frame, nothing handed over); per scheme PSNR/SSIM, entropy, adjacent correlation, NPCR/UACI (key, 1 pixel); 95 % bootstrap CIs; Kodak at 768x512 with quality 50/75/90; standard metrics for E5's hardware form | P1 | 5 | ✅ code + Kaggle re-run (18 Oct, every step PASS, 43.9 min): `paper/data/benchmark/` (with `standard_metrics/` and the Kodak q50/q90 files), `tab_bench.tex`, `tab_bench_metrics.tex` | `docs/BENCHMARK_METHOD.md` |
| B38 | Last `refs.bib` fields from the publisher pages: lin2024 volume, hirose2024 pages, puech2005 pages, wampler2015 DOI; a team member reads the PDFs of the two entries added 18 Oct (`sirichotedumrong2020`, `qiu2025`) | P1 | 4 | ⏳ 30 min with IEEE Xplore / ScienceDirect / arXiv | `paper/refs.bib` |
| B32 | Research R6: keyed DCT-domain block transforms for E5 -- negative result (flips = sign changes, already encrypted) | P3 | 5 | ✅ confirmed on 7 sources | `docs/RESEARCH.md` |
| B23 | **Recognition test** (Faster R-CNN persons) | P2 | 5 | ✅ plain 68-100 %, E1 up to 37 %, E2/E4 <= 3 %, E5 0 %; in the paper | below |
| B24 | **More frames + 95 % intervals** for leakage | P2 | 5 | ✅ 60 frames/source, intervals in the extended paper (Table + Fig.) | below |
| B6 | E5 in RTL: contract v3 mode 5 (one segment per MCU; the ARM permutes) | P1 | 1 | ~1 week | ✅ spec + model + driver + tests + **RTL** (17 Oct, bit-exact for 1/2/4 lanes) + **Vivado run 7** (18 Oct, post-route, XSim) · ⏳ board |
| B7 | Shared vs separate Ascon core (area vs throughput) | P2 | 1 | 2 d | below |
| B8 | Ascon-XOF128 KDF with official vectors | P2 | 2 | 1 d | below |
| B9 | Stronger jigsaw solver (MST + MGC) | P2 | 5 | ✅ gate 0.84-1.00 on plain tiles (greedy 0.62-1.00); E5 at chance (<= 2.5 %) on 9 sources | below |
| B17 | Learned attacker P5 (public corpus + PatchGAN) | P2 | 5 | ✅ E5: SSIM 0.26 (below the no-stream control), edge -0.01; E1 broken (edge 0.74) | below |
| B10 | Simulated-clock scenarios for 100-seed studies | P3 | 3 | 2 d | below |
| B11 | Multi-receiver prototype (per-receiver tags) | P3 | 4 + 3 | 3 d | below |
| B12 | Masked Ascon, ROI encryption, H.264/HEVC | P3 | – | future | paper §VII only |
| B18 | Throughput toward 1 pixel/clock and a higher clock | P3 | 1 | 1 week | below |
| B19 | Area: fewer BRAM/DSP, shared Ascon core (B7) | P3 | 1 | 2–4 d | below |

**B20 – Restart interval on the open sources. ✅ done 14 Oct (rerun; Table VI now over 8 sources).** The Kaggle numbers for Sintel, Tears of Steel and Kodak
were made before bug #16 was fixed (overhead measured against a file with the APP11 segment; no
any-N solver). They were kept as `*.prefix16.*.txt` until 17 Oct 2026 (now only in git history, commit 327e237).

1. Run `kaggle_runs.py (JOB = "remaining")` with `RERUN = True` (it also redraws the Fig. 2 grid at paper size).
2. Copy `extra/{sintel_trailer,tearsofsteel,kodak}/restart_interval/` and `.../grid/` into `paper/data/extra/`.
3. `python paper/make_assets.py` — Table VI's caption then says "mean over 8 sources".

**Done when** Table VI is built from 8 sources and `make test` passes.

**B21 – What does the network get without the ciphertext? ✅ done 14 Oct.** Result: E5 edge correlation
0.037 [0.028, 0.046] = control 0.036, so no outline comes from the stream; SSIM beats the control by 0.11 in
P4 (0.34 vs 0.23) and by 0.00 in P3. The paper states both. Original spec, for the record: Under E5 the U-Net raises SSIM from 0.14 to
0.36 without any outline (edge ≤ 0.044). Part of that is just "typical video" (black letterbox bars,
average brightness), which no encryption can hide. `learned_attack.py` now also scores the per-pixel
median of the training frames (the best constant picture under its L1 loss) and gives a 95 %
bootstrap interval for the learned edge correlation.

1. Rerun P3 and P4 (the `RERUN` Kaggle run does both).
2. In the paper, replace the red TODO in "Learned attacker": report the control's SSIM next to the
   network's, and say whether the E5 edge interval contains 0.
3. If the network beats the control clearly under E5 (SSIM gap > 0.05 or edge interval above 0),
   look at `examples_E5.png` (open clips only) and describe what it recovers; do not hide it.

**Done when** Table V or the text carries the control, and the TODO is gone.

**B25 – Global-statistics control.** The U-Net beats the no-ciphertext prior under E5 by 0.11 SSIM in P4.
The likely reason: shuffled blocks still carry the frame's brightness and colour histogram (and DC size
categories), just not their positions. Test it instead of assuming it:

1. In `learned_attack.py`, add a second control: a picture filled with the *true* per-frame mean colour
   of the original (an oracle of frame-level statistics), and a third: the mean colour of the attacker's
   E5 replacement picture (what the stream really reveals at frame level).
2. If the U-Net's E5 SSIM is close to the oracle's, the paper can say "frame-level statistics only".
   If it is clearly above, look at `examples_E5.png` (open clips) for what else it recovers.

**Done when** the two extra rows are in Table V (or the text) and "we attribute" becomes "we measured".

**B22 – E1 after the U-Net result.** The U-Net undoes sign-only encryption (edge 0.69, SSIM 0.79 on
unseen clips). E2 is already the default minimum level, so nothing is insecure by default, but:

1. `docs/INTERFACES.md` and the dashboard legend: describe E1 as "visual degradation only, not
   confidential against a trained attacker".
2. `link/defence.py`: check that no policy can select E1 when `min_mode` ≥ E2 (add a test that the
   bandit never picks a level below the minimum over 10 seeds).
3. Paper §III-C: one sentence in the protection-level paragraph pointing to the result.

**Done when** the three changes are merged with a test.

**B23 – Recognition test.** Correlations need the picture to be in the right place; a person looking
at the screen does not. The Kodak picture at N = 32 shows whole strips of windows although its
correlation is 0.02 (`paper/data/extra/kodak/restart_interval/kodak_frame0/`).

1. New `experiments/recognition.py`: run an off-the-shelf detector (OpenCV DNN face detector, or a
   torchvision Faster R-CNN "person" class) on the original and on the attacker's picture per mode
   (E2, E4, E5 N = 1, E5 N = 32, U-Net output), on the open clips and talking-head clips.
2. Report detection recall relative to the original (fraction of originals' detections that are
   also found in the attacker's picture, IoU ≥ 0.3 for E1–E4; for shuffled modes count any detection).
3. Expectation (not a result): E1 high, E2/E4 low-to-medium on outlines, E5 N = 1 near zero.

**Done when** a table per mode exists in `sim_out/recognition/` and a sentence is in §V.

**B24 – More frames and intervals.** Leakage uses 20 frames per source (standard metrics and restart
interval 5–6). Raise to 60 frames for leakage, 20 for the rest, and give a 95 % bootstrap interval
per cell (reuse `bootstrap_ci` from `learned_attack.py`). The table then shows "0.34 [0.30, 0.38]".

**Done when** `measure_mode_tradeoff.py` writes intervals and `make_assets.py` prints them.

**B1 – Selective encryption in C.** The current software baseline is Python (~140 ms/frame), which a
reviewer will dismiss.

1. Write `future_work/baselines/c_selective/selective.c`. It parses a baseline JPEG with standard
   tables, Huffman-decodes it, XORs the keystream onto sign and amplitude bits (contract v2 rules,
   `docs/INTERFACES.md`), and re-encodes.
2. Take the keystream from the official Ascon C reference (`ascon-c`, `asconaead128/ref` or `opt32`).
3. Expose it as a CLI (`selective in.jpg out.jpg key nonce mode`) or with ctypes.
4. **Gate:** the output is byte-identical to `model.jpeg.selective_encrypt_jpeg` on 100 frames (write
   the test first).
5. Add a row to `bench_software_codecs.py` and run it on the ARM (A3).

**Done when** the C path is byte-identical on 100 frames and has an ARM timing row.

**B3 – Threat model.** One page, in `docs/THREAT_MODEL.md` and in paper §III:

* **The attacker's abilities:** passive eavesdropping, and on-path modify / drop / replay / inject /
  delay / flood. It does not hold the keys, and side channels on the device are out of scope.
* **Assets:** frame content, integrity of content + metadata, and the availability signal.
* **Nonce uniqueness:** per (key, session_id, frame_ctr, purpose). The session id holds 48 random
  bits plus the epoch, and the counter is 63 bits, monotonic, reset only with a new key. So
  (key, nonce) never repeats as long as the random base is fresh. Say what happens on reboot
  without persistent state: there is a new random base, and the collision probability is ~2⁻⁴⁸
  per pair of sessions.
* **What we do not hide:** which coefficients are non-zero (closed only by E5), frame sizes and timing,
  and the brightness/colour statistics a trained network learns (B21).

**Done when** the paper's TODO in §III-A is replaced and `docs/THREAT_MODEL.md` exists.

**B6 – E5 in RTL** (✅ done 17 Oct 2026 as contract v3 mode 5, `docs/HW_TODO.md` H1; the plan below was the
original contract-v2 idea). Keep the model as the referee: add a mode-5 path to `model/hw.py` first, then the
cocotb test, then the RTL.

1. `zigzag_rle.v`: when a new CTRL bit is set, reset the DC predictors at each MCU start.
2. `bit_packer.v`: at each MCU end, pad with 1-bits to a byte, then emit `FF D0+n` (n = MCU mod 8,
   none after the last MCU), with no stuffing.
3. The keyed shuffle reorders whole segments. Either do it on the ARM, with the tag computed on the
   ARM, or use a BRAM reorder buffer before the tag unit.

Keep N = 1: the restart study (Tab. VI) shows that N = 32 is partly solvable.
**Done when** `tb/test_top.py` passes for E5 byte for byte.

**B7 – Shared Ascon core.** Today the keystream and the tag each have a core. Build a variant with one
time-shared core plus an arbiter. Measure LUTs (Vivado, `vivado_ooc.tcl`) and cycles per pixel
(`benchmark_crypto.py --rtl`). Report it as an ablation. **Done when** both variants have a row.

**B8 – XOF KDF.** Replace the AEAD-tag-as-PRF KDF in `link/keys.py` with Ascon-XOF128 (SP 800-232 §5),
checked against the official XOF KATs. This is protocol-only: no RTL change. **Done when** the KATs pass.

**B9 – Stronger jigsaw for N = 1.** Two solvers exist: greedy region growing
(`future_work/attacks/jigsaw_attack.py`) and the beam-search raster solver in
`experiments/restart_interval.py` (good for few, long segments; at chance for N = 1). Implement a
minimum-spanning-tree solver with Mahalanobis gradient compatibility, or a learned pair score
trained on *unencrypted* tiles from other clips. **Gate:** it must beat the current solver on plain
tiles (`tests/test_future_work.py`) before its E5 numbers count.

**B17 – Larger learned attacker.** Train on a public video corpus with a clear licence (check the
licence before downloading) and add an adversarial (GAN-style) loss, as in the ITN/GAN attacks of
Sirichotedumrong & Kiya (§7). Report with the B21 control. **Done when** a P5 column exists.

**B10 – Simulated clock.** Run `link/` nodes on a virtual clock (one process, event queue) so a
462 s scenario takes seconds. Keep the real-time version for latency numbers; use the fast one only
for policy statistics (100+ seeds).

**B11 – Multi-receiver.** Encrypt once, then compute one tag per receiver key (a few µs of Ascon
each). The channel fans out to N receiver processes. Removing a receiver means rekeying the others.

**B14 – Comparison table.** After the Vivado day, add Table "Comparison with related designs" to §II or
§IV: device, LUT, FF, BRAM, DSP, clock, pixels/s, encryption, authentication, format compliance. Use
the rows of §7 and cite each source. Compare like with like, and mark which numbers are post-route
and which are estimates. The paper is at the 6-page limit: shorten §VI text to make room.

**B18 – Throughput.** At 1.64 cycles/pixel and 100 MHz we reach ~61 Mpixel/s. Commercial JPEG cores
reach 1 pixel/clock at 150–166 MHz on 7-series parts, i.e. 1080p60. Find the stage that limits us
(cocotb stall statistics per stage), pipeline it, and push fmax (Vivado `--fmax`). This is future
work for the paper; just state the gap honestly.

**B19 – Area.** Yosys estimates 25 BRAM36 and 24 DSP. Check in Vivado where they go (line buffers,
Huffman tables, the DCT multipliers). Arithmetic says 24 of the BRAM36 are the colour-conversion line
buffers of `rgb2ycbcr_block.v`, sized for 2048-pixel lines (`LOG_MAXW = 11`) and double-buffered:
LOG_MAXW 10 (1024 px) would need 12, 9 (512 px) 6. A `LOG_MAXW` sweep in Vivado (BRAM, LUT, power
per point) is a cheap memory-optimisation experiment. BRAM-light line buffers and a shared Ascon core (B7) would bring
us near the commercial cores plus one ~1 K-LUT Ascon.

### 4.4 The paper (all, drafting now; final by 15 Dec)

**The draft is in `paper/`.** `paper/README.md` explains:

* how to build it;
* what each section needs;
* the reference list, which was checked by hand;
* the rules on originality, citations and disclosure of AI assistance.

Placeholders that wait for results are marked `\TODO{...}` in red. The PDF lists them, so nothing
unfinished slips through. **The conference version is exactly 6 pages with no slack** (commit 6f1bc20,
18 Oct: the last reference ends on page 6). Anything added must be paid for with text cut elsewhere,
usually by moving detail into `access.tex` / `sections/access_*.tex` (the IEEE Access version has no page limit).

| Paper part | Waits for | Owner |
|---|---|---|
| Hardware tables (resources, comparison) | ✅ Vivado run 7, post-route | 1 |
| E5 in hardware, SAIF power | ✅ run 7 (18 Oct) | 1 |
| Comparison with published schemes (SVE-Bench) | ✅ B39 (18 Oct) | 5 |
| Fig. 2 with a real frame, learned-attacker controls, threat model | ✅ B2, B21, B25, B3 | 2 + 4 + 5 |
| §VI board results and "Cost relative to software" (red TODO) | 4.2 A1–A4 + B1 | 1 + 2 + 4 |
| Author order, e-mails, funding line, AI-assistance disclosure (red TODOs) | team decision | all |
| Proof-reading, own wording, plagiarism check | everything | all |

**Dates:**

| Date | Milestone |
|---|---|
| 16–18 Oct | Vivado day done ✅ (runs 6 and 7) |
| 24 Oct | A1–A2 |
| 7 Nov | A3–A6 + B1–B3 |
| 12 Nov | demo, project complete |
| 22 Nov | final numbers |
| 2 Dec | full draft with board results |
| 9 Dec | review with Dr. Chetana G |
| 12 Dec | plagiarism check (Turnitin / iThenticate via the library) |
| 15 Dec | submit |

### 4.5 Housekeeping

* Merge open pull requests, and keep CI green before each merge.
* Rename `challenge .mp4` (trailing space) in the Kaggle dataset; the script is fixed anyway.
* Big Buck Bunny's download URL returns 404 (14 Oct); it was removed from `OPEN_CLIPS`.
* Every bug found on the board gets a row in `docs/TESTING.md` §8.

---

## 5. Claim → evidence checklist (the paper may only say what is ✅)

| Claim | Evidence | Status |
|---|---|---|
| Output stays a valid, playable JPEG/MJPEG in every mode | format compliance (4 decoders, 6 modes) | ✅ |
| Key holder recovers the frame bit-exactly | tests + figure row 3 | ✅ |
| Encryption adds 0 cycles to the encoder | `benchmark_crypto.py --rtl` | ✅ RTL simulation |
| Resources / timing / power on the Zynq-7020 | Vivado | ✅ encoder and both PYNQ-Z2 systems post-route at 100 MHz (runs 6-7; the 2-lane system with E5) · power = SAIF estimate for the encoders (B37), vectorless for the systems · ⏳ board |
| 1.5 + a/MCU rows cycles per pixel; 65 Mpixel/s at 640x480 and 100 MHz | `stall_profile.py --scaling` (RTL, 5 frame sizes) | ✅ RTL simulation |
| Lane encoder (contract v3) bit-exact with the model for 1, 2, 4 lanes, all levels, under stalls; same bytes for every lane count | `tb/test_lanes_top.py`, `make xsim-icarus` | ✅ RTL simulation · ✅ XSim in Vivado (runs 5, 6; run 7 with E5 frames) |
| 2 lanes 122 Mpixel/s, 4 lanes 176 Mpixel/s at 640x480 and 100 MHz | `experiments/lanes_rtl_throughput.py` | ✅ RTL simulation (no DMA stalls) · ⏳ board |
| The lane encoder fits the xc7z020 and meets 100 MHz; its LUT/BRAM/DSP | Vivado run 6 (`lanes`, `bd_lanes` steps) | ✅ post-route with E5 (run 7): 2 lanes 10,069 LUT / 50 BRAM / 46 DSP, 4 lanes 16,893 / 52 / 92 (out of context); 2-lane PYNQ-Z2 system with E5 meets 100 MHz; E5 costs +2 % LUT, no BRAM/DSP · ⏳ 4-lane system not built; whether DDR feeds ~700 MB/s: board |
| Peculiar case 1: a bit flip is caught at the first frame, held-back frames only as jamming (their late return is benign reordering), silenced feedback only by the dead-man rule, with the highest leakage while active | `paper/make_assets.py :: peculiar_cases` on the full-suite runs (`experiments/scenario.py`) | ✅ system simulation, 3 runs (extended paper, Fig. 7) |
| Peculiar case 2: 6 % packet loss loses ~37 % of frames (fragmentation, 1-(1-p)^n), and the defence still never escalates (5-90 % frame loss = degraded network) | same, on the benign runs | ✅ system simulation, 3 runs (extended paper, Fig. 8) |
| Faster than the commercial encoders | only as "more Mpixel/s at 100 MHz than logiJPGE reports at 150 MHz" | ✅ throughput only; ❌ never "better" overall (they use less BRAM and no cipher) |
| E1–E4 leak an outline sketch, E5 does not (8 sources incl. open films + Kodak) | mode trade-off + jigsaw | ✅ |
| A trained network does not recover E5 outlines | learned attack, 4 setups, up to 2,609 training frames | ✅ |
| No outline comes from the E5 stream (U-Net no better than the true-frame-statistics oracle) | learned attack + B25 controls, P4/P5 | ✅ (the old 'edge = plain control' wording no longer holds with the 16 Oct P4) |
| E5 hides everything beyond the video prior | U-Net SSIM above the plain control, but not above the frame-statistics oracle (B25) | ❌ **do not claim**; frame-level brightness/colour leak |
| A trained network breaks E1 | learned attack P1–P4 | ✅ (a result to state, not hide) |
| E5 defeats the non-zero counting attack | restart_interval.py, NZCA ≤ 0.08 for all N | ✅ |
| Longer restart intervals are as safe as N = 1 | beam solver finds 15–41 % successors at N = 32 | ❌ **do not claim** |
| Standard metrics show security | they assume full-image ciphers | ❌ report for comparability only |
| Schemes with fixed key material (Van Droogenbroeck, Kishore, Hirose) fall to one known frame; E5's per-frame keys and permutation do not transfer | SVE-Bench A4 (known plaintext), `docs/BENCHMARK_METHOD.md` | ✅ Kaggle, 9 sources (`tab_bench.tex`, mean max leak: Van Droogenbroeck 0.94, Hirose 0.90-0.91, Kishore 0.78, Auer 0.58 vs E5 0.02, worst source 0.04); E1-E4 stay at 0.79 through NZCA (A3), not A4 |
| E5 costs 2-4 % throughput at 640x480 and 100 MHz (1 lane 63.5 vs 65.8, 2 lanes 118.0 vs 122.3, 4 lanes 171.4 vs 175.7 Mpixel/s, E5 vs E2) | `lanes_rtl_throughput.py --sizes 640x480 --modes 2 5`, `hw_efficiency.py` | ✅ RTL simulation (18 Oct) · ⏳ board |
| 11 active attacks detected and mitigated in < 1 s on average, no false alarms | full_suite × 3, benign × 3 | ✅ simulation · ⏳ board (A6) |
| Bandit: fewer encrypted bits, slower reaction | policy_seeds, 10 seeds, paired | ✅ |
| Faster / lower energy than software on the same board | A2–A4 (+ B1) | ⏳ |
| Every level E0–E5 leaks motion through the frame size equally; constant-size frames close it (cost depends on content) | `size_leak.py`, 7 sources (fixed-camera case: synthetic only) | ✅ (E0–E5 and padding rows) |
| Rate control + padding to a cap hides motion | `size_leak.py` FF+PI row | ❌ **do not claim**: 0.51-0.73 and 13-36 % frames over cap on real clips |
| E5's per-frame permutation defeats a chosen-plaintext (learned-permutation) attack | `chosen_plaintext.py` | ✅ 7 sources |
| The sign-recovery LP of Lin et al. recovers 88-93 % of signs in its own setting but 59 % of E1's and 49 % of E2's; it still sharpens E1's outline (edge 0.41 vs 0.33) | `sign_recovery.py` | ✅ 29 frames, 9 source sets |
| One second of frame sizes identifies which of 7 known videos plays (98 % E1-E4, 99 % E5, chance 14 %); only constant-size frames (+81 % bytes) reach chance | `video_fingerprint.py` | ✅ 7 videos |
| E5 in hardware | B6 | ✅ RTL simulation (lane encoder, 1/2/4 lanes bit-exact) · ✅ Vivado run 7: XSim bit-exact, post-route at 100 MHz, +2 % LUT · ⏳ board. Until the board run the paper says "in RTL" / "post-route", not "on the board" |

**Claims to avoid:**

* "first JPEG selective encryption" (false since 2002);
* "first FPGA JPEG encryption" (false since 2012/2015);
* "post-quantum secure";
* "secure against all attacks";
* any number not produced by a script.

---

## 6. Rules (also for AI assistants)

1. **The model is the referee.** Never change `model/` to make an RTL test pass, unless it contradicts
   T.81 or SP 800-232, and then say so.
2. **Every change comes with a test; `make test` is green before every PR.** CI runs it on GitHub.
3. **Numbers come only from scripts.** Paper tables are generated by `paper/make_assets.py` from
   `paper/data/`; never type a result by hand.
4. **When something fails:**
   1. reproduce it with the printed SEED;
   2. run `make bundle T=...`;
   3. paste the bundle into Claude (`docs/TESTING.md` §9);
   4. add a bug-log row (`docs/TESTING.md` §8).
5. **Git.** Use one branch per task and a pull request with a reviewer. Do not commit `sim_out/`,
   videos, `.pt` or `.npz` files.
6. **Writing.** AI tools may help draft. Every sentence in the paper must be checked, rewritten in your
   own words where needed, and understood by the person presenting it. Disclose AI assistance as the
   conference requires (paper/README.md).

---

## 7. How we compare with published work (checked 14 Oct 2026, ours updated 18 Oct)

Numbers are copied from each source. Ours are post-route (Vivado run 7) with throughput from RTL
simulation. The paper's version of this table is generated (`tab_compare.tex` from
`paper/data/related/compare.json`); copy numbers from there, not from here.

| Work | Platform | Area | Speed | Encryption | Authentication | Format compliant | Security evaluation |
|---|---|---|---|---|---|---|---|
| **Ours** | Zynq-7020 (post-route) | 5,037 LUT, 2,950 FF, 24.5 BRAM36, 23 DSP (one pipeline); 2 lanes with E5 10,069 LUT | 100 MHz: 65 Mpx/s (212 fps VGA), 2/4 lanes 122/176 Mpx/s; 0 extra cycles for encryption; ~211 mW (SAIF) | Ascon-AEAD128 keystream on signs/amplitudes (+ keyed MCU shuffle in E5) | per-frame 128-bit tag over metadata + scan, replay window, ratchet | yes, 4 decoders | edge leakage on 9 sources (incl. open films + Kodak), jigsaw (greedy, MST), U-Net + GAN (5 setups), sign recovery, chosen plaintext, NZCA + restart interval, SVE-Bench vs 4 published schemes, standard metrics; 11 active attacks, 10-seed policy study |
| Kishore et al. 2015 [JRTIP] | Stratix II / IV, 256×256 grey | 2250 ALUT, 47 mult., 1.26 Mbit (Stratix IV, with scrambler; +13-17 % ALUT, 2× memory vs. without) | 100 MHz, 170 frames/s (188 without) = 11.1 Mpx/s | lightweight block/symbol scrambling | no | yes (claimed) | visual |
| Bağbaba & Örs 2015 [ELECO] | Virtex-6 | 2130 LUT, 1456 FF, 9 DSP | 87 MHz (no throughput) | TEA on DC (+5 AC) coefficients | no | – | PSNR |
| Gladis Kurian & Chen 2025 [Electronics] | Artix-7 100T | 3.5–5.3 K LUT, 4.3 K FF, 32 BRAM, 0 DSP | 100 MHz; replay check ~0.8 µs | Ascon-128 (messages, not video) | AEAD + Bloom-filter replay check | n/a | false-positive rate |
| Khairallah & Yadhunathan 2023 [NIST LWC workshop] | Artix-7 100T | Ascon-p MACs: ~0.8–1.7 K LUT, ~390 FF | 200 MHz, 33–166 Mbps (duplex) | – (MAC) | MAC | n/a | – |
| CAST JPEG-E-S (commercial) | Artix-7 | 3.1 K LUT, 2 BRAM, 16 DSP | 1 sample/clk @ 166 MHz | none | none | yes | – |
| logicBRICKS logiJPGE (commercial) | Zynq-7020 | 3.2 K LUT, 2.0 K FF, 16 BRAM, 30 DSP | 1 px/clk @ 150 MHz, 1080p60 | none | none | yes | – |
| Hirose, Imaizumi & Kiya 2024 [APSIPA ASC] | software | – | – | bitstream XOR + restart-marker block permutation (RI 2–32) | no | yes | key space/sensitivity, NZCA, histograms, PSNR/SSIM on 1338 UCID images |
| Sirichotedumrong & Kiya [arXiv 2010.06198] | software | – | – | learnable pixel/block-wise encryption for DNNs (not JPEG) | no | – | on 96×96 STL-10 images, ITN attack SSIM 0.91 and GAN attack 0.72 on Tanaka's scheme; not comparable with our SSIM numbers |
| Qiu et al. 2025 [arXiv 2503.16287] | Raspberry Pi 4B (satellite payload); chaotic maps also in Zynq HLS | – | 720p, 10 s clip encrypted in ~2.7 s on the payload | chaotic keystream XOR on raw frames | no | no (raw video) | entropy, correlation, NPCR/UACI, NIST/DIEHARD |

**Where we are stronger:**

* **Authentication.** We are the only one in this list that authenticates every frame *and* its
  metadata while staying playable.
* **Standard cipher.** We use a standardized lightweight AEAD (SP 800-232) instead of TEA, chaos or
  an ad-hoc scrambler.
* **Zero cycle cost.** Encryption costs no cycles.
* **Attacks.** We evaluate learned and puzzle-solving attackers on real video, plus a closed-loop
  response to 11 active attacks with statistics over runs and seeds. None of the hardware papers
  above does this.

**Where we are weaker (each has a task):**

| Weakness | Task |
|---|---|
| No board numbers yet (frame rate with DMA, measured power) | §4.2 |
| One pipeline is ~2.3× below commercial JPEG cores (1 px/clk at 150 MHz); only 4 lanes pass them, at 5× their LUTs | B18 |
| More BRAM than commercial encoders (24 of our 24.5 BRAM36 are line buffers sized for 2048-pixel lines; 512-pixel lines need 6.5, run 6) | B19 |
| ~~Our Ascon blocks are larger than published cores~~ resolved post-route: 861–969 LUT per core, as small as the round-per-cycle cores of Khairallah & Yadhunathan | – |
| Our baselines of published schemes are our own re-implementations, and the scope is Motion-JPEG, not H.264/HEVC | state in the paper ✅ |
| Adjacent-pixel correlation and entropy are far from full-cipher values (by design; must be explained, not hidden) | §V text ✅ |
| Our learned attacker is still small next to the ITN/GAN attacks in the literature | B17, B21 |
| ~~Leakage cells rest on 5–20 frames per source~~ ✅ 60 frames per source with 95 % intervals | B24 |

**Sources:**

* [Gladis Kurian & Chen 2025](https://www.mdpi.com/2079-9292/14/13/2668)
* [Khairallah & Yadhunathan, NIST LWC 2023](https://csrc.nist.gov/csrc/media/Events/2023/lightweight-cryptography-workshop-2023/documents/accepted-papers/14-fpga-implementations-of-message-authentication-codes.pdf)
* [CAST JPEG-E-S brief](https://www.cast-inc.com/pdfs/cast_jpeg-e-s-brief-amd.pdf)
* [logiJPGE datasheet](https://www.logicbricks.com/Documentation/Datasheets/IP/logiJPGE_hds.pdf)
* [Hirose et al.](https://arxiv.org/abs/2410.06522)
* [Sirichotedumrong & Kiya](https://arxiv.org/abs/2010.06198)
* [Qiu et al.](https://arxiv.org/abs/2503.16287)
* [Malal 2024 (ISCTR, Ascon throughput/area)](https://avesis.metu.edu.tr/yayin/6f2daa79-8ad3-46de-aec5-5fd1bd1b9937/high-performance-fpga-implementations-of-lightweight-ascon-128-and-ascon-128a-with-enhanced-throughput-to-area-efficiency)

Kishore et al., Bağbaba & Örs, Sirichotedumrong & Kiya and Qiu et al. are in `paper/refs.bib`. Read a
source before citing it, and add it to `refs.bib` with a "checked:" comment. Never copy a number into the
paper from a summary table (this one included): take it from the source, or from `paper/data/` through
`make_assets.py`.
