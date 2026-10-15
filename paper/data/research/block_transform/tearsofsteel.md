### R6: E5 with keyed DCT-domain block transforms (tearsofsteel, 6 frames)

| Level | Jigsaw neighbours | Edge, as seen | Edge, after jigsaw | Oracle positions: edge / SSIM | + orientation repair: edge / SSIM | Size vs E5 |
|---|---|---|---|---|---|---|
| E5 | 1.1 % | 0.005 | -0.036 | 0.358 / 0.272 | -- | -- |
| E5+T | 0.5 % | 0.003 | -0.018 | 0.361 / 0.269 | 0.380 / 0.265 | +0.0 % |

Oracle columns are upper bounds for an attacker who knows every tile position; for E5+T the last column also undoes the block orientations greedily.
