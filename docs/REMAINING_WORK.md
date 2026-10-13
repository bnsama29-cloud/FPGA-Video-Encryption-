# What remains after the Vivado day

Status on 13 Oct 2026:

* **Done:** the simulation phase. The full Kaggle run (`future_work/kaggle/kaggle_complete.py`)
  produces every simulation table, and the Vivado day (`docs/VIVADO_ONE_DAY.md`) produces the
  hardware table and the overlay.
* **Left:** the board, the polish items that make the claims stronger, and the paper.

Owners use the role numbers:

| Role | Area |
|---|---|
| 1 | Hardware & Vivado |
| 2 | Crypto & protocol |
| 3 | Network & attacker |
| 4 | Receiver, dashboard & demo |
| 5 | Defence, ML & visual security |

Give this file plus `docs/TEAM_CONTEXT.md` to Claude when you pick an item.

**Rough position after the Vivado day: ~65–70 % of the project.**

| Part | Weight | Done |
|---|---|---|
| Simulation evidence | 35 % | ~100 % |
| Hardware | 25 % | ~90 % once Vivado numbers and overlay exist |
| Board | 20 % | ~15 % |
| Paper | 20 % | ~15 % |

The board (A) is now the critical path; the paper (C) can start in parallel.

---

## A. The board (critical path, deadline 12 Nov)

| # | Task | Owner | Time | Command / file | Done when |
|---|---|---|---|---|---|
| A1 | **Bit-exact gate on hardware**: every mode E0–E4, 320×240 and 640×480 | 1 | ½ day | `future_work.board.first_contact` | `all_bit_exact: true` for ≥ 10 frames per mode and size |
| A2 | **FPGA speed**: encoder alone and full frame | 1 | ½ day | same script, part 2 | fps table in `sim_out/board/first_contact.md` |
| A3 | **ARM baseline** on the same board: libjpeg-turbo, + AES-GCM, + Python selective (and C selective once B1 exists) | 2 | ½ day | `bench_software_codecs --sizes 320x240 640x480 --frames 30` on the board | `baselines_<board>.md` |
| A4 | **Power and energy**: USB meter on the board supply, idle / ARM encoding / FPGA encoding per mode, 30 s averages | 1 + 5 | 1 day | `future_work/baselines/power_template.csv` → `energy_table` | mJ per frame, FPGA vs ARM |
| A5 | **Live link board → laptop**: board as camera node, laptop as channel + receiver + dashboard | 3 + 4 | 1 day | `board_sender --bitfile ...` + `run_all --no-sender` (future_work README §3.3) | dashboard shows the board's stream decrypted |
| A6 | **Attacks against the board**: `full_suite.json` and `benign.json` with the board as sender, 3 runs each | 3 | 1 day | `experiments/scenario.py --set ...` (laptop side) | reaction table "on hardware" |
| A7 | **Webcam on the board** (USB webcam into the PYNQ) | 4 | ½ day | `--set sender.source=webcam:0` | live demo works |
| A8 | **Demo video** (2 min): calm → attack → detection → recovery, on the real board | 4 | ½ day | screen + phone recording | `demo.mp4` (not in git; link it) |

**Rules for the board phase:**

* A1 comes before anything else. A fast wrong encoder is worthless.
* Report what you measure. If the FPGA is not more energy-efficient than the ARM on some metric, say
  so; the playability, integrity and zero-cycle-overhead claims stand anyway.
* Board numbers go to `sim_out/board/` via the scripts and are committed on a `board-results` branch.

---

## B. Polish that makes the claims stronger (pick by priority)

**P1 = the paper is weak without it, P2 = clearly stronger, P3 = future-work section.**
Detailed specs are in `future_work/README.md` §4.

| # | Item | P | Owner | Time | Why |
|---|---|---|---|---|---|
| B1 | **Selective encryption in C** (byte-identical with the Python model), as the fair software baseline on the ARM | P1 | 2 | 1–2 days | reviewers will dismiss a Python-vs-FPGA comparison |
| B2 | **Open, citable test clips**: replace the movie trailers with CC-licensed or public-dataset clips; rerun `run_real_video.py` | P1 | 4 | ½ day | copyrighted trailers cannot appear in the paper |
| B3 | **Threat model + nonce-uniqueness argument** (1 page, with the attacker list from `channel.py`) | P1 | 2 | 1 day | the security section |
| B4 | **Learned attack on more data** (several clips for training, other clips for testing) | P2 | 5 | 1 day GPU | strongest leakage evidence |
| B5 | **E5 restart-interval study** (N = 1, 2, 4, 8: overhead vs leakage) | P2 | 5 | 1 day | justifies the E5 setting |
| B6 | **E5 in RTL** (restart markers + keyed MCU shuffle), or state clearly that E5 is model-level | P2 | 1 | 3–5 days | E5 is currently not in hardware |
| B7 | **Shared vs separate Ascon core** ablation: area vs throughput, with Vivado numbers | P2 | 1 | 2 days | design-choice justification |
| B8 | **Ascon-XOF128 KDF** with the official test vectors | P2 | 2 | 1 day | standards-conformant key derivation |
| B9 | **Stronger jigsaw solver** (MST / learned compatibility) | P2 | 5 | 2–3 days | E5 against a strong attacker |
| B10 | **Simulated-clock version of the scenarios** (seconds instead of real time) for many-seed studies | P3 | 3 | 2 days | 100 seeds instead of 10 |
| B11 | Multi-receiver prototype (per-receiver tags) | P3 | 4 + 3 | 3 days | scalability |
| B12 | Masked Ascon, ROI encryption, H.264 | P3 | – | future | future-work section |

---

## C. The paper (13 Nov – 15 Dec, but start the text now)

**Format:** IEEE conference, ~6 pages, two columns.

**Every number comes from `sim_out/paper_tables.md`.** Rebuild it with
`python -m future_work.figures.paper_tables --root <all results>` and never type a number by hand.

| Section | Content | Source | Owner |
|---|---|---|---|
| I. Introduction | problem (video privacy on edge cameras), why in-encoder selective encryption, contributions (4 bullets) | – | all |
| II. Related work | selective encryption of JPEG/MJPEG, Ascon hardware, authenticated video, adaptive defences | literature list | 2 + 5 |
| III. System and threat model | encoder + Ascon, nonce layout, tag, feedback, ratchet, dead-man rule; attacker capabilities | `docs/INTERFACES.md`, B3 | 2 + 3 |
| IV. Hardware | block diagram, zero-cycle integration, resources / timing / power, fmax | `vivado_tables.md`, cycles table | 1 |
| V. Security evaluation | leakage per mode (synthetic + real video), visual figure, jigsaw, learned attack, format compliance | paper_tables §leakage / jigsaw / learned | 5 |
| VI. Protocol and defence evaluation | 11 attacks, reaction time ± std, false alarms, benign loss, bandit vs threshold (10 seeds) | paper_tables §reaction / policy_seeds | 3 + 5 |
| VII. Board results | bit-exact on hardware, fps, energy vs ARM, live link | A1–A6 | 1 + 4 |
| VIII. Conclusion + future work | B6–B12 | – | all |

**Figures:**

1. System block diagram.
2. `visual_security_grid.png` on an open clip.
3. Leakage vs cost per mode.
4. Reaction-time timeline (`compare/quick/timeline.png`).
5. Bandit vs threshold over seeds.
6. A board photo with the live dashboard.

**Dates:**

| Date | Milestone |
|---|---|
| 24 Oct | A1–A2 (board bit-exact + fps) |
| 7 Nov | A3–A6 done |
| 12 Nov | demo (A7–A8); project complete |
| 22 Nov | all numbers final (P1 polish included) |
| 2 Dec | full draft |
| 9 Dec | internal review with Dr. Chetana G |
| 15 Dec | submission |

---

## D. Housekeeping (any time, 1 hour each)

* Merge open pull requests; keep CI green (`make test`, `RUN_SLOW=1 pytest`) before every merge.
* `results/` holds the original golden-model outputs from before contract v2. Mark it as historical
  in its own README, or move it out of the repo, so nobody quotes old numbers.
* Rename `challenge .mp4` (trailing space) in the Kaggle dataset.
* Once `main` has everything, set `BRANCH = "main"` in the Kaggle scripts.
* Keep `docs/TESTING.md` §8 (bug log) going: every bug found on the board gets a row.
