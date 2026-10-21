# What is left for the hardware (as of 21 Oct 2026, after Vivado run 9)

All software and all RTL are done and tested: the golden model, the receiver, the board driver, the board
sender, the bit-exact gate, the XSim vector and check tools, the dashboard, and **E5 in the lane encoder**
(contract v3 mode 5, VERSION bit 7, bit-exact for 1, 2 and 4 lanes, Vivado run 7 closes 100 MHz). What is
left needs the board, or Vivado time.

| # | Task | Status | Why | Effort | How-to |
|---|---|---|---|---|---|
| H1 | E5 in the lane encoder | ✅ done (17–18 Oct, run 7: +2 % LUT, no BRAM/DSP, 318 mW SAIF) | the strongest level in hardware | — | `docs/INTERFACES.md` §8.6 |
| H2 | **Board bring-up A1–A6** | ⏳ waiting for the board | every board number in the papers (red TODOs) | 1–2 days | **`docs/FPGA_HANDS_ON.md`** (step by step), `docs/BOARD_BRINGUP.md` (task list) |
| H3 | 125 MHz: pipeline the colour converter | ✅ run 9: **125 MHz met** (v2 +0.060 ns, 2 lanes +0.213 ns) with stage P | 1 lane 82, 2 lanes ~150 Mpixel/s | — | below |
| H10 | **150 / 166 MHz** (the commercial cores' clocks) | RTL done 21 Oct, bit-exact (bug #36): skid buffers, keystream ring, packer and zig-zag fixes, timing-driven flow; needs run 10 | 4 lanes ≈ 260 Mpixel/s (RGB) | Vivado run | below, `docs/BENCHMARK_PLAN.md` |
| H11 | YUYV (camera-native) input, 4 pixels per beat | RTL + model + driver done 21 Oct (`PIXFMT = 1`, `rtl/yuyv_4px.v`, bit-exact, 2 and 4 lanes) | 4 lanes 0.434 clk/px (230 Mpx/s at 100 MHz), half the DDR bytes | run 10 (OOC) + `bd_lanes4yuyv` | `docs/INTERFACES.md` §8.7 |
| H12 | 4 lanes with 1080p lines | `NBUF = 1` option done (half the line buffers, under 2 % slower) | 1080p at 4 lanes on the xc7z020 | run 10 (OOC) + `bd_lanes4hd` | §8.7 |
| H6 | Fabric cycle counters CYCLES / IN_WAIT / OUT_STALL (0x54..0x5C) | ✅ in the run-8 bitstreams (100 MHz met, system WNS +0.311 ns); read on the board by first_contact | fabric-only time on silicon (the paper's A2 TODO) | rebuild | `py vivado\run_vivado_day.py --steps bd bd_lanes parse` |
| H7 | ARM (PS) baseline A3: our encoder in C on the Cortex-A9 | code done 21 Oct (`future_work/arm/`, bit-exact gate) | like-for-like PL vs PS speed-up | 1 h on the board | `docs/BOARD_BRINGUP.md` §6 |
| H9 | 4-lane PYNQ-Z2 image | ✅ run 9: system meets 100 MHz (18,683 LUT, 58.5 BRAM, 92 DSP, WNS +0.461 ns); next: first_contact on the board (whether DDR feeds ~700 MB/s; the YUYV image needs half) | 30 min board | `docs/RUNBOOK.md` §3 |
| H8 | Faster driver: pixels straight into the DMA buffer, cache ops on the frame's bytes only, E5 order + split in one C call, time breakdown | done 21 Oct | board fps (92 ms at VGA was the Python copy, not the fabric) | rerun first_contact | — |
| H4 | Power with simulated switching activity (SAIF) | ✅ done (run 7: 211 mW encoder, 318/319 mW 2 lanes E5/E2) | replaces the vectorless estimate | — | `vivado/power_saif.tcl` |
| H5 | Keep the bitstreams safe | open | the E5 pair exists only on tom's PC | 10 min | below |

---

## H2 — Board bring-up (the only thing the papers still wait for)

Follow `docs/FPGA_HANDS_ON.md`. In short:

1. SD card with the PYNQ-Z2 image, jumpers Boot = SD and Power = USB, network to the laptop (§2–§5).
2. Copy the repo and `secure_jpeg_lanes.bit` + `.hwh` (run 7, E5) to `/home/xilinx/fpga` (§6).
3. **A1 + A2:** `first_contact` on the board: every size and level E0–E5 bit-exact, then ms/frame (§8).
4. **A3:** ARM baseline on the same chip; **A4:** USB power meter, idle and per workload (§9).
5. **A5 + A6:** board as camera into the laptop's receiver and dashboard; the 11-attack suite and the
   benign suite, three runs each, with `--board-max-mode E5` (§10).

Done when `sim_out/board/lanes/first_contact.md` says `Bit-exact ... **yes**` for E0–E5 on the board,
the baseline and power tables are filled, and the scenario runs are committed. Then replace the red
`\TODO{A1--A4 ...}` in `paper/sections/access_08_hwresults.tex` and the limitation sentence of
`paper/conference.tex` (the numbers go through `paper/data/board/` and `make_assets.py`, never by hand).

## H3 — 125 MHz (done) and H10 — 150 / 166 MHz

Run 9 (21 Oct, commit 6798a4f): with stage P the single pipeline meets 125 MHz (+0.060 ns) and two lanes
too (+0.213 ns). The new worst paths were handshakes (docs/TESTING.md bug #36): the bit packer's
accumulator update (9 levels), a ready chain packer → Huffman → encryption stage → keystream pointer →
128-bit block copy (fan-out 133), and in the lanes the zig-zag stage's RAM read → DC-predictor reset.
**Done in RTL after run 9 (bit-exact, same clocks per pixel):** `rtl/skid_buf.v` at the encryption stage
and at the bit packer's input and output, keystream slots used as a ring with a registered `ks_avail`,
the packer shifting by its registered fill level, non-zero flags in the zig-zag stage. Vivado now runs a
timing-driven flow (`SJPEG_IMPL=perf`: retiming, Explore / ExtraTimingOpt / AggressiveExplore
directives; `SJPEG_IMPL=default` repeats the old flow).

Run 10 (one command, overnight; RUNBOOK §3):
`py vivado\run_vivado_day.py --steps xsim ooc lanes bd_lanes4 power parse --periods 6.667 6.0 --fclk 142 --parallel 2 --jobs 2`
→ 1, 2 and 4 lanes at 100 / 150 / 166 MHz, 4 lanes with NBUF = 1, with 1080p lines and with YUYV input, the
4-lane system at 142.9 MHz (falls back to 125, then 100), XSim of 1, 2 and 4 lanes, SAIF power incl. 4 lanes.
Send the zip; its `summary.txt` now starts with the git commit and the SHA-256 of every bitstream.

## H5 — Keep the bitstreams safe

Bitstreams are not in git (large, generated). Put the run-7 pair (`secure_jpeg_lanes.bit` + `.hwh`, and
`vivado_results_20261018_1847.zip`) in the team's shared drive **and** attach them to a GitHub release
of the commit they were built from (`gh release create run7 secure_jpeg_lanes.bit secure_jpeg_lanes.hwh`),
so the board day does not depend on one PC.

## Rehearsing without a board (works today)

```
py -m future_work.board.first_contact --mock-lanes 2 --mock-e5 --sizes 64x48 --frames 2 --timing-frames 2
py scripts\demo_key.py                                    # fresh pre-shared key + the exact commands
py -m link.run_all --no-sender --set keys.master=<KEY>    # window 1
py -m future_work.board.board_sender --mock-lanes 2 --mock-e5 --set keys.master=<KEY> --set sender.policy=fixed --set sender.mode=E5   # window 2
```
