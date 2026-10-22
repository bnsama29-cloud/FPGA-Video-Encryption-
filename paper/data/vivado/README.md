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

## Run 10 (21 Oct 2026)

`vivado_results_20261021_2101.zip`, Vivado 2026.1, Samarth's PC, **RTL of commit dd13f55** (skid buffers,
keystream ring, packer and zig-zag fixes, YUYV and NBUF options), `SJPEG_IMPL=perf`. Command:
`--steps xsim ooc lanes bd_lanes4 power parse --periods 6.667 6.0 --fclk 142 --parallel 1 --jobs 2`, then
(after the two crashed 4-lane jobs) `--steps bd_lanes4 power parse --fclk 142 --parallel 1`.
Tables of this run alone: `vivado_tables_run10.md`. It replaces the run-9 / run-6 entries of the same design
(`secure_jpeg_top`, `_6.667ns`, 2 lanes at 100 / 150 MHz, 4 lanes, `overlay_lanes4`) and adds
`secure_jpeg_top_6.0ns`, 2 lanes at 166.7 MHz and the 4-lane variants `_nbuf1`, `_pixfmt1` (YUYV) and
`_log_maxw11_nbuf1` (1080p lines). Not taken from the zip: `overlay` and `lanes` (stale copies of runs 8 and 9,
same report dates as before) and `..._6.0ns_lanes4_...` (synthesis only: Vivado crashed, below).

* XSim: v2, 2 lanes and 4 lanes bit-exact (5 frames each, plus one SAIF frame per mode).
* Out of context: single pipeline 100 MHz +1.376, **150 MHz +0.074**, 166.7 MHz -0.284 ns (fmax estimate
  159 MHz); 2 lanes 100 MHz +0.803, 150 MHz -0.060, 166.7 MHz -0.467 ns; 4 lanes 100 MHz +0.833 ns, with
  NBUF = 1 +0.808 ns (32 BRAM instead of 56), 1080p lines +0.789 ns, YUYV input +0.599 ns (15,138 LUT).
* 4 lanes at 150 and 166.7 MHz: no result. Vivado crashed in `phys_opt_design` (EXCEPTION_ACCESS_VIOLATION)
  twice each, with only one Vivado running (docs/TESTING.md bug #38).
* 4-lane PYNQ-Z2 system: 142.9 MHz missed by -0.008 ns (one endpoint); **built at 125 MHz, +0.433 ns**,
  20,097 LUT, 58.5 BRAM, 92 DSP (`secure_jpeg_lanes4.bit`, SHA-256 bd6baa5a…). The `attempts` field of
  `overlay_lanes4` holds each try, parsed from `lanes4/timing_<MHz>MHz.txt` with the same parser
  (`timing_100MHz.txt` is the run-9 build, 0.461 ns).
* SAIF power (one frame of activity): v2 0.231 W, 2 lanes 0.353 W (E2 and E5), 4 lanes 0.503 / 0.504 W.
  Higher than run 9's 0.206 / 0.32 W because the skid buffers and the ring add flip-flops (v2 3,178 -> 3,506 FF).
* The worst path of the 166.7 MHz pipeline and of the 142.9 MHz system is the keystream loop; the 2-lane
  150 MHz path is the segment-count multiply. Both are changed in the RTL after this run (bug #38,
  bit-exact); their post-route effect is not measured yet.

## Run 11 (22 Oct 2026)

`vivado_results_20261022_1602.zip`, **RTL of commit d34604f** (run 10 + the bug-#38 fixes: keystream next state
prepared from registers, two register stages for the segment count). Out of context only (the board images were
not rebuilt in this run: `overlay`, `lanes`, `lanes4` in the zip are the run-8/9/10 copies and are not taken).
Run in two parts: `--steps xsim ooc lanes ... --periods 6.667 6.0`, stopped after the 4-lane 100 MHz job, then
`--steps lanes power --only ooc_lanes4_6 ooc_lanes4_hd ooc_lanes4_nbuf1 ooc_lanes4_yuyv`. Tables of this run alone:
`vivado_tables_run11.md`; it replaces every out-of-context entry of run 10.

* Single pipeline: 100 MHz +1.524, **150 MHz +0.270**, 166.7 MHz **-0.015 ns** (fmax estimate 166.3 MHz).
* 2 lanes: 100 MHz +1.056, **150 MHz +0.003**, 166.7 MHz **-0.019 ns**.
* 4 lanes: 100 MHz +1.020, **150 MHz +0.011 ns** (17,887 LUT, 54 BRAM), 166.7 MHz -0.182 ns. The 166.7 MHz job
  crashed in `phys_opt_design` again with the perf flow and finished with `SJPEG_IMPL=safe` on the retry
  (its `impl` in the RESULT line); the 150 MHz job finished with the perf flow.
* 4-lane variants at 100 MHz: NBUF = 1 +0.414 (32 BRAM), 1080p lines +1.011, YUYV +0.985 ns (15,172 LUT).
* At 166.7 MHz the near-critical paths are spread (BRAM read -> DCT row buffer, Huffman length -> packer skid,
  lane FIFO full flag, converter chroma sum); none dominates.
* The 4-lane PYNQ-Z2 system in the snapshot is still the run-10 build (commit dd13f55, 125 MHz).

