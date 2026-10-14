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

## 1. Where the project stands (14 Oct 2026)

| Part | State | Evidence |
|---|---|---|
| Golden model + contract v2 | ✅ done | `model/`, `docs/INTERFACES.md`, 1089 Ascon KATs |
| RTL (E0–E4) | ✅ bit-exact with the model in cocotb + Icarus, 0 extra cycles for encryption | `tb/`, `make test` |
| Vivado testbench | ✅ in Icarus · ⏳ in Vivado XSim | `make xsim-icarus`, then `docs/VIVADO_ONE_DAY.md` |
| Post-route resources / timing / power | ⏳ **next** | `python vivado/run_vivado_day.py` |
| System simulation (feedback, ratchet, defence, attacks, dashboard) | ✅ | `link/`, `experiments/` |
| Simulation results for the paper | ✅ complete (Kaggle run, 14 Oct, 47/47 steps + one clip rerun) | `paper/data/paper_tables.md` |
| PYNQ-Z2 overlay + board tests | ⏳ scripts ready, not yet run | `future_work/board/` |
| Paper | 📝 first full draft | `paper/main.tex` → `paper/main.pdf` |

**Rough position: ~55 % of the project.** The simulation is done; the Vivado day, the board and the
paper are left, in that order.

The headline results, all in `paper/data/paper_tables.md`:

* **Encryption cost.** It adds 0 cycles in RTL; the estimate is 199 fps at 640×480 if 100 MHz closes.
* **Attack suite.** 11/11 attacks are mitigated in 0.91 ± 0.02 s, with 0/375 false alarms (3 runs).
  Benign impairments give 0/447 false alarms.
* **Outline leakage.** E1–E4 leak an outline sketch (edge correlation 0.27–0.58 on four real clips).
  E5 removes it (−0.004…0.017), also against a jigsaw solver and a trained U-Net attacker.
* **Bandit vs threshold over 10 seeds.** The bandit encrypts 14 % fewer bits (10/10 seeds) but
  reacts 0.88 s slower and leaks more under attack (0/10 seeds better). This is a trade-off, not a
  win.
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
  ships 11, so build 12 from source as `kaggle_complete.py` does.
* **Verilator:** `pip install verilator`.
* **Vivado ML Standard** (free, 2022.1 matches the PYNQ v3.0 image) for Role 1 only; see
  `docs/VIVADO_ONE_DAY.md`.

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
| `python vivado/run_vivado_day.py` | XSim + post-route numbers + overlay + tables (Vivado) |
| `python -m future_work.board.first_contact` | bit-exact gate + fps on the PYNQ-Z2 |
| `python -m future_work.figures.paper_tables --root <results>` | every paper table from result files |
| `cd paper && make` | build the paper PDF (`make tables` first after new results) |

**Re-running all the simulation results:** paste `future_work/kaggle/kaggle_complete.py` into one
Kaggle cell (Internet on, GPU T4, clips as a private dataset), then *Save & Run All*. It takes ~4 h
with `PARALLEL = 1` and writes `results.zip`. Unzip it into `paper/data/` and run `cd paper && make`.

---

## 3. Repository map

```
model/          golden model = the referee (Ascon, colour, DCT/quant, entropy, selective, JPEG container)
rtl/            Verilog-2001 encoder + Ascon keystream/tag + AXI (secure_jpeg_top.v); include/ is generated
tb/             cocotb testbenches, every block vs the model under random stalls
vivado/         XSim testbench, run_vivado_day.py, vivado_ooc.tcl, parse_reports.py
hls/            Vitis HLS DCT + quantiser (same arithmetic as the RTL)
link/           system simulation: sender, channel/attacker, receiver, feedback, keys, defence, dashboard
experiments/    every paper number: scenarios, policies, policy_seeds, mode trade-off, crypto benchmark,
                learned attack
future_work/    board/ (PYNQ driver, block design, board sender, first_contact), baselines/, attacks/
                (jigsaw), figures/ (grid, compliance, paper_tables), kaggle/kaggle_complete.py
paper/          IEEE conference draft (main.tex, refs.bib), data/ (the results it is built from),
                make_assets.py (tables + figures from data/)
scripts/        older golden-model tools (encode_image, run_video_eval, mjpeg_server, export_vectors)
tests/          pytest for model, contract, system, future_work, report parsers
docs/           INTERFACES (contract v2), TESTING (+ bug log), TEAM_CONTEXT (for Claude),
                VIVADO_ONE_DAY, DEBUGGING_WITH_CLAUDE
```

---

## 4. The remaining work

Status key: ⏳ ready to run (scripts exist) · 📝 to be written · ✅ done.

### 4.1 Vivado (Role 1 leads, 1 day) ⏳

Follow **`docs/VIVADO_ONE_DAY.md`**. One command does most of it:

```
python vivado/run_vivado_day.py --blocks --fmax
```

This runs:

* XSim;
* post-route LUT/FF/BRAM/DSP, WNS and power at 100 MHz;
* a per-block breakdown and fmax;
* the PYNQ-Z2 overlay;
* the paper table in `sim_out/vivado/vivado_tables.md`.

The block design script has not run in Vivado yet; expect one or two small fixes (the guide's
step 4 lists the likely errors).

**Done when** WNS ≥ 0, `secure_jpeg.bit` + `.hwh` are committed, and the table is copied into
`paper/data/vivado/`. Then **replace the Yosys estimate in the paper** (Table III).

### 4.2 Board (critical path, deadline 12 Nov) ⏳

| # | Task | Owner | Time | How | Done when |
|---|---|---|---|---|---|
| A1 | **Bit-exact gate on silicon** | 1 | ½ day | `sudo -E python3 -m future_work.board.first_contact --sizes 320x240 640x480` | all modes E0–E4 byte-identical with the model |
| A2 | FPGA speed | 1 | same run | part 2 of the same script | fps table in `sim_out/board/first_contact.md` |
| A3 | ARM baseline on the same board | 2 | ½ day | `python3 -m future_work.baselines.bench_software_codecs --sizes 320x240 640x480 --frames 30` | `baselines_<host>.md` |
| A4 | Power and energy per frame | 1 + 5 | 1 day | USB meter: idle / ARM / FPGA per mode, 30 s averages → `future_work/baselines/power_template.csv` → `python -m future_work.baselines.energy_table <csv>` | mJ/frame, FPGA vs ARM |
| A5 | Live link board → laptop | 3 + 4 | 1 day | board: `python3 -m future_work.board.board_sender --bitfile ... --set link.host=<laptop> --set link.bind_host=0.0.0.0`; laptop: `python -m link.run_all --no-sender --set link.bind_host=0.0.0.0 --set link.sender_host=<board>` | the dashboard shows the board's stream |
| A6 | Attacks against the board | 3 | 1 day | `experiments/scenario.py` with `full_suite.json` and `benign.json`, 3 runs each | "on hardware" row in the reaction table |
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

| # | Item | P | Owner | Time | Spec |
|---|---|---|---|---|---|
| B1 | **Selective encryption in C** on the ARM (fair software baseline) | P1 | 2 | 1–2 d | below |
| B2 | **Open, citable test clips** instead of the movie trailers | P1 | 4 | ½ d | below |
| B3 | **Threat model + nonce-uniqueness argument** (1 page) | P1 | 2 | 1 d | below |
| B4 | Learned attack on more data | P2 | 5 | 1 d GPU | below |
| B5 | E5 restart-interval study (N = 1, 2, 4, 8) | P2 | 5 | 1 d | below |
| B6 | E5 in RTL (restart markers + keyed MCU shuffle) | P2 | 1 | 3–5 d | below |
| B7 | Shared vs separate Ascon core (area vs throughput) | P2 | 1 | 2 d | below |
| B8 | Ascon-XOF128 KDF with official vectors | P2 | 2 | 1 d | below |
| B9 | Stronger jigsaw solver (MST / learned compatibility) | P2 | 5 | 2–3 d | below |
| B10 | Simulated-clock scenarios (seconds instead of real time) for 100-seed studies | P3 | 3 | 2 d | below |
| B11 | Multi-receiver prototype (per-receiver tags) | P3 | 4 + 3 | 3 d | below |
| B12 | Masked Ascon, ROI encryption, H.264/HEVC | P3 | – | future | paper §VII only |

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

**B2 – Open clips.** The trailers are copyrighted: they cannot be shown in the paper, and the repo must
never contain them (`*.mp4` is ignored; `future_work/clips_manifest.md` lists hashes only).

1. Pick 4 clips with an open licence: a surveillance-style scene, a talking head, outdoor motion
   and an indoor scene. Good sources are public research datasets with a clear licence, or
   CC-BY footage.
2. Note the licence and source of each in the manifest.
3. Rerun the real-video part of `kaggle_complete.py` (`RUN = dict(... only real_video=True)`).
4. Update `paper/data/`, and then the paper can show a real frame in Fig. 2.

**B3 – Threat model.** One page, in `docs/THREAT_MODEL.md` and in paper §III:

* **The attacker's abilities:** passive eavesdropping, and on-path modify / drop / replay / inject /
  delay / flood. It does not hold the keys, and side channels on the device are out of scope.
* **Assets:** frame content, integrity of content + metadata, and the availability signal.
* **Nonce uniqueness:** per (key, session_id, frame_ctr, purpose). The session id holds 48 random
  bits plus the epoch, and the counter is 63 bits, monotonic, reset only with a new key. So
  (key, nonce) never repeats as long as the random base is fresh. Say what happens on reboot
  without persistent state: there is a new random base, and the collision probability is ~2⁻⁴⁸
  per pair of sessions.
* **What we do not hide:** which coefficients are non-zero (the sketch leak, closed only by E5),
  frame sizes and timing.

**B4 – More data for the learned attack.** Train on 3–4 clips and test on held-out ones (after B2).
Report PSNR, SSIM and edge correlation per mode. Current result: the network recovers brightness and
colour layout (SSIM up to 0.43 in E2/E4) but no outline in E5 (edge correlation ≈ 0). Say exactly
that.

**B5 – Restart interval.** Add `restart_interval` N (now fixed at 1) to the following, then plot
overhead and leakage (`measure_mode_tradeoff.py` + `jigsaw_attack.py`) for N = 1, 2, 4, 8, keeping
`make test-model` green:

* `model/entropy.py :: run_length_encode` (reset every N MCUs);
* `mcu_segments` (N MCUs per segment);
* `model/jpeg.py :: package_frame / receive_frame / replacement_attack_jpeg` (DRI = N).

**B6 – E5 in RTL.** Keep the model as the referee: add a mode-5 path to `model/hw.py` first, then the
cocotb test, then the RTL.

1. `zigzag_rle.v`: when a new CTRL bit is set, reset the DC predictors at each MCU start.
2. `bit_packer.v`: at each MCU end, pad with 1-bits to a byte, then emit `FF D0+n` (n = MCU mod 8,
   none after the last MCU), with no stuffing.
3. The keyed shuffle reorders whole segments. Either do it on the ARM, with the tag computed on the
   ARM, or use a BRAM reorder buffer before the tag unit.

**B7 – Shared Ascon core.** Today the keystream and the tag each have a core. Build a variant with one
time-shared core plus an arbiter. Measure LUTs (Vivado, `vivado_ooc.tcl`) and cycles per pixel
(`benchmark_crypto.py --rtl`). Report it as an ablation.

**B8 – XOF KDF.** Replace the AEAD-tag-as-PRF KDF in `link/keys.py` with Ascon-XOF128 (SP 800-232 §5),
checked against the official XOF KATs. This is protocol-only: no RTL change.

**B9 – Stronger jigsaw.** Implement a minimum-spanning-tree solver with Mahalanobis gradient
compatibility, or a learned pair score trained on *unencrypted* tiles from other clips. **Gate:** it
must beat the current solver on plain tiles (`tests/test_future_work.py`) before its E5 numbers count.

**B10 – Simulated clock.** Run `link/` nodes on a virtual clock (one process, event queue) so a
462 s scenario takes seconds. Keep the real-time version for latency numbers; use the fast one only
for policy statistics (100+ seeds).

**B11 – Multi-receiver.** Encrypt once, then compute one tag per receiver key (a few µs of Ascon
each). The channel fans out to N receiver processes. Removing a receiver means rekeying the others.

### 4.4 The paper (all, drafting now; final by 15 Dec)

**The draft is in `paper/`.** `paper/README.md` explains:

* how to build it;
* what each section needs;
* the reference list, which was checked by hand;
* the rules on originality, citations and disclosure of AI assistance.

Placeholders that wait for results are marked `\TODO{...}` in red. The PDF lists them, so nothing
unfinished slips through.

| Paper part | Waits for | Owner |
|---|---|---|
| Table III hardware (now a Yosys estimate) | 4.1 Vivado | 1 |
| §VI board results (now a placeholder) | 4.2 A1–A6 | 1 + 4 |
| Fig. 2 with a real frame | B2 | 4 |
| Software baseline row on the ARM | A3 + B1 | 2 |
| Threat model paragraph | B3 | 2 |
| Proof-reading, own wording, plagiarism check | everything | all |

**Dates:**

| Date | Milestone |
|---|---|
| 16 Oct | Vivado day done |
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
* Every bug found on the board gets a row in `docs/TESTING.md` §8.

---

## 5. Claim → evidence checklist (the paper may only say what is ✅)

| Claim | Evidence | Status |
|---|---|---|
| Output stays a valid, playable JPEG/MJPEG in every mode | format compliance (4 decoders, 6 modes) | ✅ |
| Key holder recovers the frame bit-exactly | tests + figure row 3 | ✅ |
| Encryption adds 0 cycles to the encoder | `benchmark_crypto.py --rtl` | ✅ RTL simulation |
| Resources / timing / power on the Zynq-7020 | Vivado | ⏳ (Yosys estimate only, labelled as such) |
| E1–E4 leak an outline sketch, E5 does not (synthetic + 4 real clips) | mode trade-off + jigsaw | ✅ |
| A trained network does not recover E5 outlines | learned attack, 2 train/test pairs | ✅ (more data: B4) |
| 11 active attacks detected and mitigated in < 1 s on average, no false alarms | full_suite × 3, benign × 3 | ✅ simulation · ⏳ board (A6) |
| Bandit: fewer encrypted bits, slower reaction | policy_seeds, 10 seeds, paired | ✅ |
| Faster / lower energy than software on the same board | A2–A4 (+ B1) | ⏳ |
| E5 in hardware | B6 | 📝 (paper says "model level") |

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
   3. paste the bundle into Claude (`docs/DEBUGGING_WITH_CLAUDE.md`);
   4. add a bug-log row (`docs/TESTING.md` §8).
5. **Git.** Use one branch per task and a pull request with a reviewer. Do not commit `sim_out/`,
   videos, `.pt` or `.npz` files.
6. **Writing.** AI tools may help draft. Every sentence in the paper must be checked, rewritten in your
   own words where needed, and understood by the person presenting it. Disclose AI assistance as the
   conference requires (paper/README.md).
