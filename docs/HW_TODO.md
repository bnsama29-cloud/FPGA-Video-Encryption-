# What is left for the hardware (as of 21 Oct 2026, after Vivado run 8)

All software and all RTL are done and tested: the golden model, the receiver, the board driver, the board
sender, the bit-exact gate, the XSim vector and check tools, the dashboard, and **E5 in the lane encoder**
(contract v3 mode 5, VERSION bit 7, bit-exact for 1, 2 and 4 lanes, Vivado run 7 closes 100 MHz). What is
left needs the board, or Vivado time.

| # | Task | Status | Why | Effort | How-to |
|---|---|---|---|---|---|
| H1 | E5 in the lane encoder | ✅ done (17–18 Oct, run 7: +2 % LUT, no BRAM/DSP, 318 mW SAIF) | the strongest level in hardware | — | `docs/INTERFACES.md` §8.6 |
| H2 | **Board bring-up A1–A6** | ⏳ waiting for the board | every board number in the papers (red TODOs) | 1–2 days | **`docs/FPGA_HANDS_ON.md`** (step by step), `docs/BOARD_BRINGUP.md` (task list) |
| H3 | 125 MHz: pipeline the colour converter | run 8: D3 stage improved v2 to −0.487 ns (2 lanes −0.914); worst path now the multiply-add. Product stage P added (RTL, bit-exact); needs run 9 | 1 lane 82, 2 lanes ~150 Mpixel/s | Vivado run | below |
| H6 | Fabric cycle counters CYCLES / IN_WAIT / OUT_STALL (0x54..0x5C) | ✅ in the run-8 bitstreams (100 MHz met, system WNS +0.311 ns); read on the board by first_contact | fabric-only time on silicon (the paper's A2 TODO) | rebuild | `py vivado\run_vivado_day.py --steps bd bd_lanes parse` |
| H7 | ARM (PS) baseline A3: our encoder in C on the Cortex-A9 | code done 21 Oct (`future_work/arm/`, bit-exact gate) | like-for-like PL vs PS speed-up | 1 h on the board | `docs/BOARD_BRINGUP.md` §6 |
| H9 | 4-lane PYNQ-Z2 image | script ready (`--steps bd_lanes4`: LANES=4, lines ≤ 1024 px, `secure_jpeg_lanes4.bit`); needs a Vivado run, then first_contact on the board; DDR must feed ~700 MB/s | ~20 min Vivado + 30 min board | — |
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

## H3 — 125 MHz

Vivado run 6/7: at 125 MHz the colour converter fails by 0.875 ns (v2). **Done in RTL (21 Oct):** a D3
stage in `rgb2ycbcr_block.v` / `rgb2ycbcr_2px.v` registers the chroma pair sums and the row-sum read, and
all buffer writes happen one clock later (same order, same contents; every RTL test still bit-exact).
Run 8 (21 Oct): v2 −0.875 → −0.487 ns, 2 lanes −0.914 ns; the worst path is now D1 → C, the nine
constant multiplies and their sums in one clock (12 levels of carry chains). **Done in RTL after run 8:**
stage P registers the products, C only adds (bit-exact). Left: run 9,
`py vivado\run_vivado_day.py --steps xsim ooc lanes bd_lanes bd_lanes4 power parse --periods 8.0`.
If 125 MHz still fails, the zip's `timing.txt` has the paths; send it. Then the block
design at 125 MHz: `block_design.tcl` takes the FCLK0 frequency as its first argument.

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
