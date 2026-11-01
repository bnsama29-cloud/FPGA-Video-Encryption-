### R6: E5 with keyed DCT-domain block transforms (sintel_trailer, 6 frames)

| Level | Jigsaw neighbours | Edge, as seen | Edge, after jigsaw | Oracle positions: edge / SSIM | + orientation repair: edge / SSIM | Size vs E5 |
|---|---|---|---|---|---|---|
| E5 | 1.3 % | 0.003 | -0.022 | 0.281 / 0.208 | -- | -- |
| E5+T | 0.7 % | 0.005 | -0.013 | 0.297 / 0.207 | 0.307 / 0.214 | -0.3 % |

Oracle columns are upper bounds for an attacker who knows every tile position; for E5+T the last column also undoes the block orientations greedily.
