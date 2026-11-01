### R6: E5 with keyed DCT-domain block transforms (jailer, 6 frames)

| Level | Jigsaw neighbours | Edge, as seen | Edge, after jigsaw | Oracle positions: edge / SSIM | + orientation repair: edge / SSIM | Size vs E5 |
|---|---|---|---|---|---|---|
| E5 | 1.0 % | -0.017 | 0.028 | 0.439 / 0.049 | -- | -- |
| E5+T | 0.6 % | -0.017 | -0.008 | 0.446 / 0.049 | 0.484 / 0.059 | -0.1 % |

Oracle columns are upper bounds for an attacker who knows every tile position; for E5+T the last column also undoes the block orientations greedily.
