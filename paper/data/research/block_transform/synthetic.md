### R6: E5 with keyed DCT-domain block transforms (synthetic, 6 frames)

| Level | Jigsaw neighbours | Edge, as seen | Edge, after jigsaw | Oracle positions: edge / SSIM | + orientation repair: edge / SSIM | Size vs E5 |
|---|---|---|---|---|---|---|
| E5 | 2.2 % | -0.001 | 0.034 | 0.386 / 0.546 | -- | -- |
| E5+T | 1.4 % | -0.000 | 0.041 | 0.380 / 0.539 | 0.348 / 0.549 | -0.5 % |

Oracle columns are upper bounds for an attacker who knows every tile position; for E5+T the last column also undoes the block orientations greedily.
