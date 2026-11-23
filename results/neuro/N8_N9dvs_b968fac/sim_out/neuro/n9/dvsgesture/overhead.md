# N9 overhead

Software cost on x86_64 x86_64 CPython 3.13.18 (µs per event, same Python for every scheme):

| scheme | µs/event |
|---|---|
| ours V1 (model) | 64.91 |
| ours V2 (model) | 54.59 |
| ours V3 (model) | 68.19 |
| ours V4 (model) | 51.37 |
| Du 2021 (own 2D-SIMM) | 0.08708 |
| Du 2021 (Ascon-keyed) | 0.2638 |
| Zhang 2024 | 2.869 |

Du 2021's own figure (0.20 µs/event, Raspberry Pi 4B, score 8.4) is quoted separately (BASELINES.md §1.4).

Event rate (events/s) per window:

| window | median | p99 | max |
|---|---|---|---|
| 10 µs | 0 | 3e+05 | 1.4e+06 |
| 100 µs | 2e+04 | 1.3e+05 | 2.9e+05 |
| 1000 µs | 2.5e+04 | 9.3e+04 | 1.59e+05 |

Fixed cost per packet: 76 B (header 48 + trailer 12 + tag 16).

| T µs | config | bytes/event | overhead vs 4 B |
|---|---|---|---|
| 256 | V3 | 15.59 | 2.896 |
| 256 | V3 + pad floor 4 | 21.51 | 4.377 |
| 256 | V3 + pad ladder 2..64 | 19.1 | 3.775 |
| 256 | V4 | 15.59 | 2.896 |
| 512 | V3 | 10.54 | 1.636 |
| 512 | V3 + pad floor 4 | 16.39 | 3.099 |
| 512 | V3 + pad ladder 2..64 | 13.91 | 2.477 |
| 512 | V4 | 10.54 | 1.636 |
| 1024 | V3 | 8.023 | 1.006 |
| 1024 | V3 + pad floor 4 | 13.88 | 2.469 |
| 1024 | V3 + pad ladder 2..64 | 11.39 | 1.848 |
| 1024 | V4 | 8.023 | 1.006 |
| 4096 | V3 | 6.132 | 0.533 |
| 4096 | V3 + pad floor 4 | 11.99 | 1.997 |
| 4096 | V3 + pad ladder 2..64 | 9.485 | 1.371 |
| 4096 | V4 | 6.132 | 0.533 |

Cycle model (V3, 100 MHz, timed replay; max-rate replay throughput separately):

| T µs | U | finalisation µs median | p99 µs | auth latency worst ms (p99) | FIFO max words | input backlog | max-rate words/clk |
|---|---|---|---|---|---|---|---|
| 256 | 1 | 0.51 | 0.53 | 0.2565 | 7 | 1 | 0.004061 |
| 256 | 2 | 0.37 | 0.39 | 0.2564 | 7 | 1 | 0.004061 |
| 256 | 4 | 0.3 | 0.32 | 0.2563 | 6 | 1 | 0.004061 |
| 512 | 1 | 0.51 | 0.53 | 0.5125 | 7 | 1 | 0.007838 |
| 512 | 2 | 0.37 | 0.39 | 0.5124 | 7 | 1 | 0.007838 |
| 512 | 4 | 0.3 | 0.32 | 0.5123 | 6 | 1 | 0.007838 |
| 1024 | 1 | 0.51 | 0.53 | 1.025 | 7 | 1 | 0.01552 |
| 1024 | 2 | 0.37 | 0.39 | 1.024 | 7 | 1 | 0.01552 |
| 1024 | 4 | 0.3 | 0.32 | 1.024 | 6 | 1 | 0.01552 |
| 4096 | 1 | 0.51 | 0.53 | 4.097 | 7 | 1 | 0.06178 |
| 4096 | 2 | 0.37 | 0.39 | 4.096 | 7 | 1 | 0.06178 |
| 4096 | 4 | 0.3 | 0.32 | 4.096 | 6 | 1 | 0.06178 |
