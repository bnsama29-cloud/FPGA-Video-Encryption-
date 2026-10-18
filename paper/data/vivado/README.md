# paper/data/vivado: post-route results from Vivado

| File | Produced by | Run |
|---|---|---|
| `vivado_results.json`, `vivado_tables.md` | `vivado/run_vivado_day.py parse` on the report folders of two runs (below), one folder per design, the newer run where both have it | |
| (run 7) `secure_jpeg_top`, `secure_jpeg_lanes_top_lanes2_log_l1`, `secure_jpeg_lanes_top_lanes4_log_l2_log_maxw10`, `overlay_lanes` | `vivado_results_20261018_1847.zip` | Vivado 2026.1, tom's PC, 18 Oct 2026, run 7 (`--steps xsim ooc lanes bd_lanes power parse --jobs 2`), 27/27 steps passed. **RTL with E5** (commit b41c733 and later); power also from simulated activity (SAIF) |
| (run 6) the 125 / 150 MHz and line-buffer variants, `overlay` (v2 system) | `vivado_results_20261017_0919.zip` | Vivado 2026.1, Windows laptop, 17 Oct 2026, run 6 (`--steps xsim ooc lanes bd bd_lanes parse --maxw 9 10 --periods 8.0 6.667 --jobs 2`), 20/20 steps passed. **Before E5**: the 2-lane runs at 125 / 150 MHz have no E5 logic (they miss timing either way) |

Run 6 = RTL after the zig-zag/RLE pipelining and the byte-FIFO register (docs/TESTING.md bug #27) and
the block-design clock fix (#28). Designs in the snapshot:

* `secure_jpeg_top` (contract v2 encoder) out of context at 100, 125 (`_8.0ns`) and 150 MHz (`_6.667ns`),
  and with line buffers for 512 / 1024-pixel lines (`_log_maxw9`, `_log_maxw10`);
* `secure_jpeg_lanes_top` (contract v3) with 2 lanes at 100 / 125 / 150 MHz and 4 lanes
  (LOG_MAXW = 10) at 100 MHz, out of context;
* `overlay`: the complete PYNQ-Z2 system (Zynq PS + AXI DMA + v2 encoder), FCLK0 = 100 MHz;
* `overlay_lanes`: the same with the 2-lane encoder and a 64-bit pixel DMA (reports from
  `future_work/board/overlay/lanes/`; parsed with `vivado/run_vivado_day.py parse <...>/overlay/lanes`).

Run 7 rebuilt the 2- and 4-lane encoders and the 2-lane PYNQ-Z2 system with E5 (contract v3 mode 5).
Against run 6, E5 adds 200 LUT to 2 lanes (9,869 -> 10,069), 320 to 4 lanes (16,573 -> 16,893) and 197
to the 2-lane system (11,716 -> 11,913), with no extra BRAM or DSP; all still meet 100 MHz (WNS +0.359,
+0.293, +0.228 ns). The v2 encoder is unchanged (5,037 LUT, +0.554 ns). In run 7 XSim checked E5 bit-exact
for the first time (one 320x240 frame, power step).

Out of context = I/O delays of 20 % of the period. `power` is Vivado's vectorless estimate
(confidence: medium); `power_saif` (run 7 only) is the routed design re-reported with switching activity
from XSim (`power_saif_v2_E0/E2/E4.txt`, `power_saif_v3_E2/E5.txt`): v2 encoder 0.210-0.211 W in every
mode, 2 lanes 0.319 W in E2 and 0.318 W in E5. Still an estimate (confidence medium), not a board
measurement. The overlay power includes the Zynq PS (about 1.5 W) and is not the encoder's.

Nothing here is typed by hand: the JSON is the parser's output on the uploaded reports
(`utilization.txt`, `utilization_hier.txt`, `timing.txt`, `power.txt`). The `folder` field names the
folder inside the uploaded zip.
