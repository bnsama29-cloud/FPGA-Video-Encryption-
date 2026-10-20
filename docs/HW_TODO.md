# What is left for the hardware (as of 20 Oct 2026)

All software and all RTL are done and tested: the golden model, the receiver, the board driver, the board
sender, the bit-exact gate, the XSim vector and check tools, the dashboard, and **E5 in the lane encoder**
(contract v3 mode 5, VERSION bit 7, bit-exact for 1, 2 and 4 lanes, Vivado run 7 closes 100 MHz). What is
left needs the board, or Vivado time.

| # | Task | Status | Why | Effort | How-to |
|---|---|---|---|---|---|
| H1 | E5 in the lane encoder | ✅ done (17–18 Oct, run 7: +2 % LUT, no BRAM/DSP, 318 mW SAIF) | the strongest level in hardware | — | `docs/INTERFACES.md` §8.6 |
| H2 | **Board bring-up A1–A6** | ⏳ waiting for the board | every board number in the papers (red TODOs) | 1–2 days | **`docs/FPGA_HANDS_ON.md`** (step by step), `docs/BOARD_BRINGUP.md` (task list) |
| H3 | 125 MHz: one more pipeline stage in the colour converter | open | 1 lane 82, 2 lanes ~150 Mpixel/s | 1–2 days + Vivado run | below |
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

Vivado run 6/7: at 125 MHz the colour converter fails by 0.875 ns (v2). Add one register stage in
`rgb2ycbcr_block.v` / `rgb2ycbcr_2px.v` behind the existing valid/ready handshake (the same technique as
bugs #17, #20, #27 in `docs/TESTING.md`). Done when every RTL test is still bit-exact and
`py vivado\run_vivado_day.py --steps ooc lanes --periods 8.0` shows WNS ≥ 0 at 8 ns. Then the block
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
