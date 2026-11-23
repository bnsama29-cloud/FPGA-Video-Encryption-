# N9 overhead

Software cost on x86_64 x86_64 CPython 3.13.18 (µs per event, same Python for every scheme):

| scheme | µs/event |
|---|---|
| ours V1 (model) | 57.16 |
| ours V2 (model) | 49.24 |
| ours V3 (model) | 61.29 |
| ours V4 (model) | 45.44 |
| Du 2021 (own 2D-SIMM) | 0.1748 |
| Du 2021 (Ascon-keyed) | 0.8324 |
| Zhang 2024 | 2.598 |

Du 2021's own figure (0.20 µs/event, Raspberry Pi 4B, score 8.4) is quoted separately (BASELINES.md §1.4).

Event rate (events/s) per window:

| window | median | p99 | max |
|---|---|---|---|
| 10 µs | 0 | 2e+05 | 7e+05 |
| 100 µs | 1e+04 | 7e+04 | 1.5e+05 |
| 1000 µs | 9000 | 4.4e+04 | 6e+04 |

Fixed cost per packet: 76 B (header 48 + trailer 12 + tag 16).

| T µs | config | bytes/event | overhead vs 4 B |
|---|---|---|---|
| 256 | V3 | 30.37 | 6.592 |
| 256 | V3 + pad floor 4 | 49.48 | 11.37 |
| 256 | V3 + pad ladder 2..64 | 40.67 | 9.168 |
| 256 | V4 | 30.37 | 6.592 |
| 512 | V3 | 18.33 | 3.583 |
| 512 | V3 + pad floor 4 | 37.27 | 8.317 |
| 512 | V3 + pad ladder 2..64 | 28.39 | 6.098 |
| 512 | V4 | 18.33 | 3.583 |
| 1024 | V3 | 12.32 | 2.079 |
| 1024 | V3 + pad floor 4 | 31.51 | 6.879 |
| 1024 | V3 + pad ladder 2..64 | 22.43 | 4.609 |
| 1024 | V4 | 12.32 | 2.079 |
| 4096 | V3 | 7.802 | 0.9504 |
| 4096 | V3 + pad floor 4 | 27.76 | 5.941 |
| 4096 | V3 + pad ladder 2..64 | 18.36 | 3.591 |
| 4096 | V4 | 7.802 | 0.9504 |

Cycle model (V3, 100 MHz, timed replay; max-rate replay throughput separately):

| T µs | U | finalisation µs median | p99 µs | auth latency worst ms (p99) | FIFO max words | input backlog | max-rate words/clk |
|---|---|---|---|---|---|---|---|
| 256 | 1 | 0.51 | 0.53 | 0.2565 | 7 | 1 | 0.01052 |
| 256 | 2 | 0.37 | 0.39 | 0.2564 | 7 | 1 | 0.01052 |
| 256 | 4 | 0.3 | 0.32 | 0.2563 | 6 | 1 | 0.01052 |
| 512 | 1 | 0.51 | 0.53 | 0.5125 | 7 | 1 | 0.01784 |
| 512 | 2 | 0.37 | 0.39 | 0.5124 | 7 | 1 | 0.01784 |
| 512 | 4 | 0.3 | 0.32 | 0.5123 | 6 | 1 | 0.01784 |
| 1024 | 1 | 0.51 | 0.53 | 1.025 | 7 | 1 | 0.03243 |
| 1024 | 2 | 0.37 | 0.39 | 1.024 | 7 | 1 | 0.03244 |
| 1024 | 4 | 0.3 | 0.32 | 1.024 | 6 | 1 | 0.03245 |
| 4096 | 1 | 0.51 | 0.53 | 4.097 | 7 | 1 | 0.1183 |
| 4096 | 2 | 0.37 | 0.39 | 4.096 | 7 | 1 | 0.1185 |
| 4096 | 4 | 0.3 | 0.32 | 4.096 | 6 | 1 | 0.1185 |
