# results/hardware/lanes_rtl_yuyv: lane encoder with camera-native YUYV input

| File | Produced by | Where it ran |
|---|---|---|
| `results.json`, `table.md` | `python experiments/lanes_rtl_throughput.py --lanes 4 2 --sizes 320x240 640x480 --pixfmt yuyv` (LOG_MAXW = 10, LOG_FIFO = 11, the per-lane output FIFO of the Vivado runs and board images, NBUF = 2) | Claude Code cloud container, Icarus 12 + cocotb 2.1, 21 Oct 2026 (RTL of PR #41) |

`hardware/rtl/secure_jpeg_lanes_top.v` built with PIXFMT = 1 (`hardware/rtl/yuyv_4px.v`, four pixels per 64-bit beat). The
input frame is `software/model/hw.py :: rgb_to_yuyv` of the same synthetic scene as `results/hardware/lanes_rtl`; every
measured frame is bit-exact against `software/model/hw.py :: encode_frame_v3(..., pixfmt="yuyv")`. No DMA stalls.
