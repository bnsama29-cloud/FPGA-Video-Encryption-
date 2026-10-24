Backend: pynq. Bit-exact with the golden model in every size and mode: **yes** (2 frames each).

| Size | Mode | Zero copy | Encode only (ms) | fps | Incl. headers on ARM (ms) | fps | load (ms) | DMA (ms) | ARM after (ms) | fabric (ms) | fabric fps |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 64x48 | E0 | no | 3.47 | 288.1 | 4.83 | 206.8 | 1.19 | 1.72 | 1.36 | 0.652 | 1533.7 |
| 64x48 | E1 | no | 3.44 | 290.9 | 4.79 | 208.7 | 1.22 | 1.72 | 1.35 | 0.651 | 1536.1 |
| 64x48 | E2 | no | 3.48 | 287.0 | 4.84 | 206.5 | 1.19 | 1.72 | 1.36 | 0.654 | 1529.1 |
| 64x48 | E3 | no | 3.46 | 288.8 | 4.81 | 207.8 | 1.24 | 1.71 | 1.35 | 0.642 | 1557.6 |
| 64x48 | E4 | no | 3.46 | 288.8 | 4.82 | 207.7 | 1.19 | 1.71 | 1.36 | 0.639 | 1564.9 |
| 64x48 | E5 | no | 3.46 | 288.8 | 5.7 | 175.4 | 1.2 | 1.71 | 2.2 | 0.648 | 1543.2 |

fabric = CYCLES register (START to DONE, 125 MHz clocks): the encoder alone, without the ARM; '-' = bitstream built before the counters (21 Oct 2026).
