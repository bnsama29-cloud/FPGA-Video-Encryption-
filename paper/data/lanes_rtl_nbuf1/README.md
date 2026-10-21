# paper/data/lanes_rtl_nbuf1: lane encoder with one line-buffer set per lane

| File | Produced by | Where it ran |
|---|---|---|
| `results.json`, `table.md` | `python experiments/lanes_rtl_throughput.py --lanes 4 2 --sizes 320x240 640x480 --nbuf 1` (RGB input, LOG_MAXW = 10, LOG_FIFO = 10) | Claude Code cloud container, Icarus 12 + cocotb 2.1, 21 Oct 2026 |

`rgb2ycbcr_2px.v` with NBUF = 1: half the converter's line-buffer memory; a lane takes its next MCU row
only after reading the previous one out. Compare with `paper/data/lanes_rtl` (NBUF = 2). Every frame
bit-exact against the model.
