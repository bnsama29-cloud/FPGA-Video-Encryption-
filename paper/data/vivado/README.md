# paper/data/vivado: post-route results from Vivado

| File | Produced by | Run |
|---|---|---|
| `vivado_results.json`, `vivado_tables.md` | `vivado/parse_reports.py` on the reports in `vivado_results_20261017_0919.zip` | Vivado 2026.1, Windows laptop, 17 Oct 2026, run 6 of `run_vivado_day.py` (`--steps xsim ooc lanes bd bd_lanes parse --maxw 9 10 --periods 8.0 6.667 --jobs 2`), 20/20 steps passed |

Run 6 = RTL after the zig-zag/RLE pipelining and the byte-FIFO register (docs/TESTING.md bug #27) and
the block-design clock fix (#28). Designs in the snapshot:

* `secure_jpeg_top` (contract v2 encoder) out of context at 100, 125 (`_8.0ns`) and 150 MHz (`_6.667ns`),
  and with line buffers for 512 / 1024-pixel lines (`_log_maxw9`, `_log_maxw10`);
* `secure_jpeg_lanes_top` (contract v3) with 2 lanes at 100 / 125 / 150 MHz and 4 lanes
  (LOG_MAXW = 10) at 100 MHz, out of context;
* `overlay`: the complete PYNQ-Z2 system (Zynq PS + AXI DMA + v2 encoder), FCLK0 = 100 MHz;
* `overlay_lanes`: the same with the 2-lane encoder and a 64-bit pixel DMA (reports from
  `future_work/board/overlay/lanes/`; parsed with `vivado/parse_reports.py <...>/overlay/lanes`).

Out of context = I/O delays of 20 % of the period. Power is Vivado's vectorless estimate
(confidence: medium); the overlay power includes the Zynq PS (about 1.5 W) and is not the encoder's.

Nothing here is typed by hand: the JSON is the parser's output on the uploaded reports
(`utilization.txt`, `utilization_hier.txt`, `timing.txt`, `power.txt`). The `folder` field names the
folder inside the uploaded zip.
