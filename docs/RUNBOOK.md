# RUNBOOK: every program, where it runs, and the order (21 Oct 2026)

Three machines take part. **Laptop** = any PC with the repo and `pip install -r requirements.txt`
(Linux, macOS or Windows; Icarus Verilog for the RTL tests). **Vivado PC** = the Windows PC with Vivado
2026.1 (`E:\FPGA\2026.1\Vivado`). **Board** = the PYNQ-Z2 (PYNQ image 3.1.1), reached by ssh/Jupyter.

## 1. What runs where on the Zynq (PL vs PS)

The xc7z020 has two halves. The **programmable logic (PL)** is our RTL; the **processing system (PS)** is
two ARM Cortex-A9 cores running Linux and Python. The split is deliberate: the PL does the work that
happens for every pixel, the PS the work that happens once per frame or per session.

| Work | PL (fabric) | PS (ARM, Python + C) | File |
|---|---|---|---|
| colour conversion, DCT, quantiser, run length, Huffman, packing | ✅ | also in C for A3 / PS-only | `rtl/`, `future_work/arm/native/sjpeg_sw.c` |
| selective encryption (Ascon keystream), K_seg, frame tag | ✅ | also in C | `rtl/keystream_gen.v`, `tag_unit.v`, `kseg_unit.v` |
| restart segments, lanes | ✅ | threads in C | `rtl/secure_jpeg_lanes_top.v` |
| JPEG headers, APP11, DRI | – | ✅ | `model/hw.py :: build_frame` |
| E5 keyed segment order | – | ✅ (C, one call) | `future_work/board/fast_e5.py`, `native/e5_order.c` |
| keys, ratchet, session id, frame counter | – | ✅ | `link/keys.py` |
| UDP sender, feedback, defence policy, replay window | – | ✅ | `link/sender.py`, `feedback.py`, `defence.py` |
| DMA buffers, registers, cycle counters | registers | ✅ driver | `future_work/board/pynq_driver.py` |

Three configurations of the camera node, all producing the **same bytes**:

| Configuration | Command on the board | Use |
|---|---|---|
| PL encodes, PS does the rest (the design) | `board_sender --bitfile …lanes.bit` | the paper's system |
| PS only (no bitstream) | `board_sender --software 2` | A3 baseline, fallback |
| emulated (laptop) | `board_sender --mock-lanes 2 --mock-e5` | rehearsal, tests |

## 2. Inventory

| Program | Machine | What it gives |
|---|---|---|
| `make test` (`tests/`, `tb/`) | laptop | full regression, RTL bit-exact vs model (~5 min) |
| `make one T=tb/…::test SEED=n`, `make waves`, `make bundle` | laptop | one test, waveforms, failure bundle |
| `python -m link.run_all` | laptop | live system simulation + dashboard on :8000 |
| `experiments/scenario.py` | laptop (+ board for A6) | scripted attacks → `sim_out/runs/` |
| `experiments/*.py` (lanes, rate control, size leak, CPA, …) | laptop | every number of the papers → `sim_out/` |
| `future_work/kaggle/kaggle_runs.py` | Kaggle GPU | learned attacks, SVE-Bench |
| `vivado/run_vivado_day.py` | Vivado PC | XSim, post-route OOC, block designs, bitstreams, reports |
| `future_work/board/first_contact.py` | board | A1 bit-exact gate + A2 timing with breakdown and fabric-only time |
| `future_work/arm/arm_baseline.py` | board | A3: same encoder on the PS (1/2 cores) vs libjpeg-turbo ± Ascon / AES-GCM vs PL |
| `future_work/baselines/energy_table.py` | laptop | A4: energy per frame from the meter readings |
| `future_work/board/board_sender.py` | board | A5/A6: the board as camera into the laptop's receiver |
| `scripts/demo_key.py` | laptop | fresh pre-shared key + exact commands (never commit `configs/demo_key.txt`) |
| `paper/make_assets.py`, `make -C paper` | laptop | tables, figures, both PDFs (conference must stay 6 pages) |

## 3. End-to-end order (hardware in one or two days)

**Day 1 — Vivado PC (morning)**
1. `git pull`, then rebuild both overlays with the new counters and the D3 converter stage:
   `py vivado\run_vivado_day.py --steps bd bd_lanes parse`
2. In parallel, the 125 MHz check: `py vivado\run_vivado_day.py --steps ooc lanes --periods 8.0`.
   If WNS < 0, keep the `timing_*.rpt` (worst 10 paths) and send it, not only the WNS.
3. Copy `secure_jpeg_lanes.bit` + `.hwh` to the board and to the shared drive (H5).

**Day 1 — board (afternoon)**
4. A1 + A2: `sudo -E python3 -m future_work.board.first_contact --bitfile …/secure_jpeg_lanes.bit`
   → `sim_out/board/first_contact.md` now has load / DMA / ARM / **fabric ms** columns.
   If it fails only with the new driver, rerun with `--full-cache-ops` and report it.
5. A3: `CFLAGS="-mcpu=cortex-a9 -mfpu=neon" sudo -E python3 -m future_work.arm.arm_baseline --sizes 320x240 640x480 --frames 30`
6. Copy both `.json/.md` into `paper/data/board/<date>_lanes/`.

**Day 2 — board + laptop**
7. A4 power: meter inline; idle, `first_contact … --timing-frames 2000`, `arm_baseline … --frames 2000`;
   fill `future_work/baselines/power_template.csv`; `py -m future_work.baselines.energy_table …`.
8. A5/A6: `py scripts\demo_key.py`, then `py experiments\scenario.py --scenario experiments\scenarios\full_suite.json --external-sender <BOARD IP> --board-max-mode E5`
   and the printed board command on the board; three runs each of `full_suite` and `benign`.
9. Laptop: `python paper/make_assets.py && make -C paper`, check `pdfinfo paper/conference.pdf` = 6 pages,
   replace the red `\TODO{A2…A4}`, commit the data.

## 4. Rehearsal without a board (works today, tested)

```
python -m future_work.board.first_contact --mock-lanes 2 --mock-e5 --sizes 64x48 --frames 2 --timing-frames 2
python -m future_work.arm.arm_baseline --sizes 64x48 --frames 2          # laptop numbers, labelled as such
python experiments/scenario.py --scenario experiments/scenarios/quick.json --policy threshold \
       --external-sender 127.0.0.1 --board-max-mode E5
# and in a second window the command it prints, with --software 2 instead of --bitfile (PS-only sender)
```

## 5. Is `docs/RESEARCH.md` used?

Yes. R1–R8 each became an experiment script and a paper section: R1 where the cycles go
(`stall_profile.py`), R2 parallel lanes (`parallel_lanes.py`, then `lanes_rtl_throughput.py` → the lane
encoder in RTL), R3 rate control (`rate_control.py`), R4 retina-style change-driven coding
(`change_driven.py`), R5 the clock limit (Vivado `--periods 8.0` → the D3 converter stage), R6 keyed block
transforms (`block_transform.py`, a negative result), R7 the size channel (`size_leak.py`,
`video_fingerprint.py`), R8 chosen plaintext on E5 (`chosen_plaintext.py`); their numbers reach both papers through
`paper/make_assets.py`. Its "places we underperform" list is the to-do list of `docs/HW_TODO.md`:
item 1 (clock) → H3, 12 (board measurements) → H2/H6/H7, 13 (Ascon Gbps) → `\AsconGbps` from
`tb/test_ascon_core.py :: ascon_block_rate`, 14 (ARM baseline) → `future_work/arm/`. Still open: 6 (BRAM),
8 (one Ascon core shared by the lanes), 9–10, 15 (side channels), 17 (padding in `link/sender`).
