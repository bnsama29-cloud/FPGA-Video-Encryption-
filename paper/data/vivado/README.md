# paper/data/vivado: post-route results from Vivado

| File | Produced by | Run |
|---|---|---|
| `vivado_results.json`, `vivado_tables.md` | `vivado/run_vivado_day.py parse` on the report folders of two runs (below), one folder per design, the newer run where both have it | |
| (run 8) `secure_jpeg_top`, `secure_jpeg_top_8.0ns`, `secure_jpeg_lanes_top_lanes2_log_l1`, `secure_jpeg_lanes_top_8.0ns_lanes2_log_l1`, `secure_jpeg_lanes_top_lanes4_log_l2_log_maxw10`, `overlay`, `overlay_lanes` | `vivado_results_20261021_0055.zip` (tables: `vivado_tables_run8.md`) | Vivado 2026.1, Samarth's PC, 21 Oct 2026, run 8 (`--steps xsim ooc lanes bd bd_lanes power parse --periods 8.0 --jobs 2`), 30/30 steps passed. **RTL of commit 9815fd9**: cycle counters (0x54..0x5C) and the D3 write stage of the colour converters |
| (run 7, superseded by run 8 where both exist) `secure_jpeg_top`, `secure_jpeg_lanes_top_lanes2_log_l1`, `secure_jpeg_lanes_top_lanes4_log_l2_log_maxw10`, `overlay_lanes` | `vivado_results_20261018_1847.zip` | Vivado 2026.1, tom's PC, 18 Oct 2026, run 7 (`--steps xsim ooc lanes bd_lanes power parse --jobs 2`), 27/27 steps passed. **RTL with E5** (commit b41c733 and later); power also from simulated activity (SAIF) |
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

Run 8 against run 7: the v2 encoder 5,037 -> 4,785 LUT, WNS +0.554 -> +0.630 ns; 2 lanes 10,069 -> 9,528 LUT,
+0.359 -> +0.491 ns; 4 lanes 16,893 -> 16,345 LUT, +0.293 -> +0.243 ns; 2-lane system 11,913 -> 12,099 LUT
(+ counters), +0.228 -> +0.311 ns. BRAM +1 per converter (the D3 stage registers the row-sum read, so
those small memories now map to block RAM): v2 24.5 -> 25.5, 2 lanes 50 -> 52, 4 lanes 52 -> 56.
At 125 MHz: v2 -0.875 -> -0.487 ns, 2 lanes -0.914 ns; the worst path is now the constant multiply-add
(d1_rgb -> c_yt / c_cbt, 12 logic levels). In the lane encoder it runs from g_lane[1] to g_lane[0]
because synthesis shares the conversion of the pixel stream both lanes receive (lane 1's converter
reports 1,423 LUT, lane 0's 147). The product stage P (RTL after run 8) splits that path; run 9 checks it.
