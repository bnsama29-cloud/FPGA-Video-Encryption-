Backend: pynq. Bit-exact with the golden model in every size and mode: **yes** (2 frames each).

| Size | Mode | Zero copy | Encode only (ms) | fps | Incl. headers on ARM (ms) | fps | load (ms) | DMA (ms) | ARM after (ms) | fabric (ms) | fabric fps |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 64x48 | E0 | no | 3.46 | 288.6 | 4.83 | 206.9 | 1.25 | 1.71 | 1.37 | 0.655 | 1526.7 |
| 64x48 | E1 | no | 3.46 | 288.8 | 4.82 | 207.3 | 1.25 | 1.7 | 1.36 | 0.647 | 1545.6 |
| 64x48 | E2 | no | 3.46 | 289.0 | 4.83 | 207.1 | 1.25 | 1.7 | 1.37 | 0.65 | 1538.5 |
| 64x48 | E3 | no | 3.44 | 290.7 | 4.79 | 208.7 | 1.24 | 1.69 | 1.36 | 0.65 | 1538.5 |
| 64x48 | E4 | no | 3.46 | 289.4 | 4.82 | 207.3 | 1.25 | 1.7 | 1.37 | 0.65 | 1538.5 |
| 64x48 | E5 | no | 3.45 | 289.8 | 5.61 | 178.3 | 1.21 | 1.71 | 2.17 | 0.657 | 1522.1 |

fabric = CYCLES register (START to DONE, 100 MHz clocks): the encoder alone, without the ARM; '-' = bitstream built before the counters (21 Oct 2026).
