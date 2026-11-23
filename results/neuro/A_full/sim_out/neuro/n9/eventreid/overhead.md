# N9 overhead

Software cost on x86_64 x86_64 CPython 3.13.18 (µs per event, same Python for every scheme):

| scheme | µs/event |
|---|---|
| ours V1 (model) | 19.01 |
| ours V2 (model) | 16.99 |
| ours V3 (model) | 22.34 |
| ours V4 (model) | 16.93 |
| Du 2021 (own 2D-SIMM) | 0.1505 |
| Du 2021 (Ascon-keyed) | 0.2112 |
| Zhang 2024 | 5.486 |

Du 2021's own figure (0.20 µs/event, Raspberry Pi 4B, score 8.4) is quoted separately (BASELINES.md §1.4).

Event rate (events/s) per window:

| window | median | p99 | max |
|---|---|---|---|
| 10 µs | 2e+05 | 9e+05 | 1.52e+07 |
| 100 µs | 1.6e+05 | 8e+05 | 3.73e+06 |
| 1000 µs | 1.92e+05 | 7.09e+05 | 1.138e+06 |

Fixed cost per packet: 76 B (header 48 + trailer 12 + tag 16).

| T µs | config | bytes/event | overhead vs 4 B |
|---|---|---|---|
| 256 | V3 | 5.478 | 0.3694 |
| 256 | V3 + pad floor 4 | 5.892 | 0.4731 |
| 256 | V3 + pad ladder 2..64 | 7.411 | 0.8529 |
| 256 | V4 | 5.478 | 0.3694 |
| 512 | V3 | 4.854 | 0.2134 |
| 512 | V3 + pad floor 4 | 5.258 | 0.3144 |
| 512 | V3 + pad ladder 2..64 | 6.78 | 0.6949 |
| 512 | V4 | 4.854 | 0.2134 |
| 1024 | V3 | 4.541 | 0.1354 |
| 1024 | V3 + pad floor 4 | 4.94 | 0.2351 |
| 1024 | V3 + pad ladder 2..64 | 6.466 | 0.6165 |
| 1024 | V4 | 4.541 | 0.1354 |
| 4096 | V3 | 4.307 | 0.07686 |
| 4096 | V3 + pad floor 4 | 4.705 | 0.1762 |
| 4096 | V3 + pad ladder 2..64 | 6.228 | 0.5569 |
| 4096 | V4 | 4.307 | 0.07686 |

Cycle model (V3, 100 MHz, timed replay; max-rate replay throughput separately):

| T µs | U | finalisation µs median | p99 µs | auth latency worst ms (p99) | FIFO max words | input backlog | max-rate words/clk |
|---|---|---|---|---|---|---|---|
| 256 | 1 | 0.51 | 0.53 | 0.2565 | 7 | 1 | 0.006607 |
| 256 | 2 | 0.37 | 0.39 | 0.2564 | 7 | 1 | 0.006607 |
| 256 | 4 | 0.3 | 0.32 | 0.2563 | 6 | 1 | 0.006607 |
| 512 | 1 | 0.52 | 0.53 | 0.5125 | 7 | 1 | 0.01321 |
| 512 | 2 | 0.38 | 0.39 | 0.5124 | 7 | 1 | 0.01321 |
| 512 | 4 | 0.31 | 0.32 | 0.5123 | 6 | 1 | 0.01321 |
| 1024 | 1 | 0.52 | 0.53 | 1.025 | 7 | 1 | 0.02642 |
| 1024 | 2 | 0.38 | 0.39 | 1.024 | 7 | 1 | 0.02642 |
| 1024 | 4 | 0.31 | 0.32 | 1.024 | 6 | 1 | 0.02642 |
| 4096 | 1 | 0.51 | 0.53 | 4.097 | 7 | 1 | 0.1057 |
| 4096 | 2 | 0.37 | 0.39 | 4.096 | 7 | 1 | 0.1057 |
| 4096 | 4 | 0.3 | 0.32 | 4.096 | 6 | 1 | 0.1058 |
