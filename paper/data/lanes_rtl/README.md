# paper/data/lanes_rtl: measured throughput of the contract-v3 lane encoder

| File | Produced by | Where it ran |
|---|---|---|
| `results.json`, `table.md` | `python experiments/lanes_rtl_throughput.py` (default sizes 128x96, 320x240, 640x480; LANES = 1, 2, 4; LOG_MAXW = 10, LOG_FIFO = 11, the per-lane output FIFO of the Vivado runs and board images) | Claude Code cloud container, Icarus 12 + cocotb 2.1, rerun 21 Oct 2026 on the RTL of PR #41 |

What a row is: `tb/test_lanes_top.py::throughput` on `rtl/secure_jpeg_lanes_top.v`, synthetic `scene`
image, quality 75, mode E2, no DMA stalls. Clocks are counted from the encoder's internal start pulse
to `irq_done` (scan fully written and tag ready); latency is from the first accepted pixel to the first
scan word offered to the DMA. Every measured frame is checked bit-exact (scan and tag) against
`model/hw.py :: encode_frame_v3` before its number is written.

Limits: simulation at an assumed 100 MHz clock (Vivado run 5 decides the real clock and the area);
the DMA never stalls (the board's DDR bandwidth is not modelled). The contract-v2 baseline in the
table is R1 (`paper/data/research/stall_profile/scaling.json`), measured the same way.

Rerun 21 Oct 2026 (skid buffers, keystream ring, registered restart: same clocks per pixel within 0.001) with 2 KB lane FIFOs instead of 1 KB, the configuration Vivado builds: 2 lanes 0.817 -> 0.793 and 4 lanes 0.569 -> 0.551 clocks per pixel at 640x480 (a lane no longer waits while the merger copies another lane's segment); 1 lane unchanged.
