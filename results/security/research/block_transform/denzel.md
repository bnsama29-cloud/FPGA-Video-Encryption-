### R6: E5 with keyed DCT-domain block transforms (denzel, 6 frames)

| Level | Jigsaw neighbours | Edge, as seen | Edge, after jigsaw | Oracle positions: edge / SSIM | + orientation repair: edge / SSIM | Size vs E5 |
|---|---|---|---|---|---|---|
| E5 | 1.4 % | 0.015 | -0.020 | 0.358 / 0.335 | -- | -- |
| E5+T | 0.5 % | 0.013 | -0.014 | 0.372 / 0.334 | 0.401 / 0.354 | -0.0 % |

Oracle columns are upper bounds for an attacker who knows every tile position; for E5+T the last column also undoes the block orientations greedily.
