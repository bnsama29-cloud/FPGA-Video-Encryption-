# paper/data/lanes_rtl_yuyv: lane encoder with camera-native YUYV input

| File | Produced by | Where it ran |
|---|---|---|
| `results.json`, `table.md` | `python experiments/lanes_rtl_throughput.py --lanes 4 2 --sizes 320x240 640x480 --pixfmt yuyv` (LOG_MAXW = 10, LOG_FIFO = 10, NBUF = 2) | Claude Code cloud container, Icarus 12 + cocotb 2.1, 21 Oct 2026 |

`rtl/secure_jpeg_lanes_top.v` built with PIXFMT = 1 (`rtl/yuyv_4px.v`, four pixels per 64-bit beat). The
input frame is `model/hw.py :: rgb_to_yuyv` of the same synthetic scene as `paper/data/lanes_rtl`; every
measured frame is bit-exact against `model/hw.py :: encode_frame_v3(..., pixfmt="yuyv")`. No DMA stalls.
