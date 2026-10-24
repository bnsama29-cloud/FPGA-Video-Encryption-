# RUNBOOK: every program, where it runs, and the order (22 Oct 2026, after Vivado run 12)

Three machines take part. **Laptop** = any PC with the repo and `pip install -r requirements.txt`
(Linux, macOS or Windows; Icarus Verilog for the RTL tests). **Vivado PC** = the Windows PC with Vivado
2026.1 (`E:\FPGA\2026.1\Vivado`). **Board** = the PYNQ-Z2 (PYNQ image 3.1.1), reached by ssh/Jupyter.
Optional fourth: an **attacker laptop** for the two-laptop runs (`docs/INTERFACES.md` §9).
The step-by-step page with expected output for every command is `docs/BOARD_DAY.html`.

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
| `future_work/baselines/energy_table.py` | laptop | A4: energy per frame from the board's fps and the meter readings, or Vivado's power estimate without a meter (`--no-meter`) |
| `future_work/board/board_sender.py` | board | A5/A6: the board as camera into the laptop's receiver (`--pq-kex`, `--set link.pad=runmax`) |
| `python -m link.channel` | attacker laptop | two-laptop runs: network + attacker between board and receiver (command printed by `scenario.py --attacker`) |
| `experiments/hw_tamper.py` | receiver laptop (+ board, Pico) | tamper inside the board: one bit flipped after the tag per shot (`secure_jpeg_lanes_tamper.bit`, `INTERFACES.md` §10) |
| `future_work/board/pico_tamper/main.py` | Raspberry Pi Pico | fires the tamper shots on PMOD A pin 1, time-stamped on the receiver laptop's clock |
| `python -m link.kex` | laptop + board | post-quantum session key (ML-KEM-768 + X25519) before the link starts |
| `experiments/pq_kex_cost.py` | board / laptop | cost of that exchange on this CPU |
| `scripts/demo_key.py` | laptop | fresh pre-shared key + exact commands (never commit `configs/demo_key.txt`) |
| `paper/make_assets.py`, `make -C paper` | laptop | tables, figures, both PDFs (conference must stay 6 pages) |

## 3. End-to-end order (hardware in one or two days)

**Before the board — Vivado PC.** Run 12 (22 Oct, commit `03d5144`, RTL of `d34604f`) built the five board
images; the paper's Vivado tables are from the same run, and the RTL is frozen.

| Image | VERSION | Clock | WNS |
|---|---|---|---|
| `secure_jpeg.bit` (single pipeline, E0–E4) | `0x5EC00200` | 100 MHz | +1.309 ns |
| `secure_jpeg_lanes.bit` (2 lanes + E5) | `0x5EC00382` | 100 MHz | +1.082 ns |
| `secure_jpeg_lanes4.bit` (4 lanes + E5) | `0x5EC00384` | 125 MHz | +0.141 ns (142.9 MHz: −0.228) |
| `secure_jpeg_lanes4hd.bit` (1080p lines) | `0x5EC00384` | 125 MHz | +0.032 ns (142.9 MHz: Vivado IP synthesis error) |
| `secure_jpeg_lanes4yuyv.bit` (YUYV input) | `0x5EC003C4` | 125 MHz | +0.197 ns (142.9 MHz: −0.237) |

1. `git pull` on `hw-polish-arm-baseline` (`d4e4392` or newer). Check the images are run 12:
   `certutil -hashfile future_work\board\overlay\secure_jpeg_lanes4.bit SHA256` starts `7f1260af5daf72b0`
   (all hashes in `summary.txt` of `vivado_results_20261022_2123.zip`).
2. Build the tamper image (~35 min; only step 11 needs it):
   `py vivado\run_vivado_day.py --steps bd_tamper parse --fclk 100 --jobs 2`
   → `overlay\secure_jpeg_lanes_tamper.bit` + `.hwh`. Put the images into git once (`py scripts\publish_bitstreams.py`, then commit and push: it checks the
   hashes and stages only the `.bit`/`.hwh` files and `MANIFEST.md`), and keep a USB-stick copy (H5).
   Board results are only comparable with the Vivado numbers of the same commit.
3. Rehearse on the laptop (no board): section 4 below, plus
   `py -m pytest tests/test_hw_tamper.py tests/test_two_laptop.py` and
   `py experiments\hw_tamper.py --external-sender 127.0.0.1 --trigger udp:127.0.0.1` with the printed
   command in a second window (`--mock-lanes 2 --mock-e5 --mock-tamper` instead of `--bitfile`).

**Day 1 — board.** Every command below runs in `sudo -i; source /etc/profile.d/pynq_venv.sh; cd /home/xilinx/fpga`.

4. Smoke test the 4-lane image (small frame, stops at the first difference), at 100 MHz, then at its own 125 MHz:
   `python3 -m future_work.board.first_contact --bitfile future_work/board/overlay/secure_jpeg_lanes4.bit --fclk 100 --sizes 64x48 --frames 2 --timing-frames 5 --out sim_out/board/lanes4_smoke100`
   `python3 -m future_work.board.first_contact --bitfile future_work/board/overlay/secure_jpeg_lanes4.bit --sizes 64x48 --frames 2 --timing-frames 5 --out sim_out/board/lanes4_smoke`
   (the first prints `fabric clock: 100.0 MHz`, the second `125.0 MHz`; `--fclk` can only lower the clock).
   Fails at 125 but passes at 100: keep `--fclk 100` for the 4-lane images today and report it.
5. A1 + A2 for every image, 320x240 and 640x480, `--frames 10 --timing-frames 50 --zero-copy`, output folders
   `sim_out/board/{lanes4,lanes2,v2,lanes4yuyv}_final` (+ `lanes4_final_100` with `--fclk 100`);
   1080p: `secure_jpeg_lanes4hd.bit --sizes 1920x1088 --frames 3 --timing-frames 20 --out sim_out/board/lanes4hd_final`.
   Its slack is +0.032 ns: a mismatch deep in the scan means rerun with `--fclk 100` (`…_final_100`) and report both.
   → `first_contact.md` has load / DMA / ARM / **fabric ms** columns and IN_WAIT (DDR starvation).
   If it fails only with the new driver, rerun with `--full-cache-ops` and report it.
6. A3: `CFLAGS="-mcpu=cortex-a9 -mfpu=neon" python3 -m future_work.arm.arm_baseline --sizes 320x240 640x480 --frames 30 --pl-json sim_out/board/lanes4_final/first_contact.json --out sim_out/board/arm_final`
   and `python3 experiments/pq_kex_cost.py --runs 20` (the post-quantum session key on the A9).
7. Copy the results back (`BOARD_DAY.html` phase 13); Claude puts them in `paper/data/board/`.

**Day 2 — board + laptop(s).** Windows laptops: allow UDP once (admin cmd), the scenario runs use 47200–47215:
`netsh advfirewall firewall add rule name="secure-link" dir=in action=allow protocol=UDP localport=47000-47010,47200-47215`

8. A4 power (meter optional). Without a meter, on the laptop after step 7:
   `py -m future_work.baselines.energy_table future_work\baselines\power_template.csv --no-meter --fpga-json sim_out\board\lanes4_final\first_contact.json --arm-json sim_out\board\arm_final\arm_baseline.json`
   (Vivado power estimate, labelled as such). With a meter: idle, `first_contact … --timing-frames 2000`,
   `arm_baseline … --frames 2000`; fill `power_w` / `idle_power_w` in `power_template.csv`; the same command
   without `--no-meter` (BOARD_DAY.html phase 9).
9. A5 live link: `py scripts\demo_key.py`, then `link.run_all --no-sender --pq-kex …` on the laptop and
   `board_sender --pq-kex --set link.pad=runmax …` on the board (exact lines in `BOARD_DAY.html` phase 10).
10. A6: `py experiments\scenario.py --scenario experiments\scenarios\full_suite.json --external-sender <BOARD IP> --board-max-mode E5 --pq-kex --set keys.master=<KEY> --out sim_out\runs\board_full_suite_rep1`
    and the printed board command on the board (add `--set link.pad=runmax`); three runs each of `full_suite`
    and `benign`. Two laptops (optional): add `--attacker <ATTACKER IP>`; start the printed `py -m link.channel …`
    on the attacker laptop first, then the board. `--kex-tamper 20` additionally corrupts the key exchange for 20 s
    (every message must fail its HMAC; the key is agreed only afterwards).
11. Tamper inside the board (SW1 up, SW0 down; Pico on JA1/GND, or `--trigger manual` and BTN0):
    `py experiments\hw_tamper.py --external-sender <BOARD IP> --trigger serial:COM5 --set keys.master=<KEY> --out sim_out\runs\hw_tamper_rep1`
    and the printed board command (`secure_jpeg_lanes_tamper.bit`); three reps. Pass: every shot = exactly one
    rejected frame, 0 missed, 0 unexplained rejections (`hw_tamper.md`). With this image BTN1 / BTN2 / BTN3
    set the protection level one down / one up / automatic (`INTERFACES.md` §10); press BTN3 before measuring.
12. Laptop: `python paper/make_assets.py && make -C paper`, check `pdfinfo paper/conference.pdf` = 6 pages,
    replace the red `\TODO{A2…A6}`, commit the data.

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
