### R6: E5 with keyed DCT-domain block transforms (challenge, 6 frames)

| Level | Jigsaw neighbours | Edge, as seen | Edge, after jigsaw | Oracle positions: edge / SSIM | + orientation repair: edge / SSIM | Size vs E5 |
|---|---|---|---|---|---|---|
| E5 | 2.3 % | 0.013 | 0.036 | 0.442 / 0.378 | -- | -- |
| E5+T | 1.2 % | 0.013 | 0.007 | 0.441 / 0.375 | 0.461 / 0.389 | +0.0 % |

Oracle columns are upper bounds for an attacker who knows every tile position; for E5+T the last column also undoes the block orientations greedily.
