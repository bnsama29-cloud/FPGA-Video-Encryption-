### R6: E5 with keyed DCT-domain block transforms (avengers, 6 frames)

| Level | Jigsaw neighbours | Edge, as seen | Edge, after jigsaw | Oracle positions: edge / SSIM | + orientation repair: edge / SSIM | Size vs E5 |
|---|---|---|---|---|---|---|
| E5 | 1.2 % | 0.031 | -0.018 | 0.472 / 0.164 | -- | -- |
| E5+T | 0.9 % | 0.031 | -0.026 | 0.457 / 0.160 | 0.475 / 0.170 | -0.1 % |

Oracle columns are upper bounds for an attacker who knows every tile position; for E5+T the last column also undoes the block orientations greedily.
