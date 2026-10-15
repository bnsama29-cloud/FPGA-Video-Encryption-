### R7: frame-size side channel (jailer, 150 frames)

| Stream | Size-motion corr. | Event AUC (0.5 = chance) | Bytes vs E2 | Notes |
|---|---|---|---|---|
| E0 | 0.16 | 0.62 | 100 % |  |
| E1 | 0.16 | 0.62 | 100 % |  |
| E2 | 0.16 | 0.61 | 100 % |  |
| E3 | 0.16 | 0.62 | 100 % |  |
| E4 | 0.16 | 0.62 | 100 % |  |
| E5 | 0.16 | 0.62 | 117 % |  |
| E2 pad-1KB | 0.15 | 0.58 | 108 % |  |
| E2 pad-max | 0.00 | 0.50 | 279 % |  |
| E5 pad-1KB | 0.16 | 0.60 | 124 % |  |
| E5 pad-max | 0.00 | 0.50 | 292 % |  |
| E2 FF+PI + pad-105% | 0.53 | 0.57 | 101 % | 18 % frames over cap; quality factor leaks: corr -0.05, AUC 0.53; SSIM 0.976 |
