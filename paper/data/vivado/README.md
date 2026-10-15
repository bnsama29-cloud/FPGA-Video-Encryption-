# paper/data/vivado: post-route results from Vivado

| File | Produced by | Run |
|---|---|---|
| `vivado_results.json`, `vivado_tables.md` | `vivado/parse_reports.py` on the reports of `vivado/vivado_ooc.tcl` | Vivado 2026.1, Windows laptop (i5-1135G7, 8 GB), 14 Oct 2026, run 3 of `run_vivado_day.py` |

Run 3 = RTL with the pipelined DCT and quantiser (bug #17) and the 2-stage colour-converter write
pipeline (bug #20); out-of-context, 100 MHz clock, input/output delays 20 % of the period. Timing met
(WNS +0.045 ns). Power is Vivado's vectorless estimate (confidence: medium).

**Provisional.** The next run (run 4) adds one more converter stage (the full overlay missed 100 MHz by
0.24 ns in run 3) and replaces these files. The overlay (Zynq PS + DMA + encoder) is not in this
snapshot because it did not meet timing yet.

Nothing here is typed by hand: the JSON is the parser's output on the uploaded reports
(`utilization.txt`, `utilization_hier.txt`, `timing.txt`, `power.txt`, `clock.xdc`).
