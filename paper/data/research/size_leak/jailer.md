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
| E2 pad-runmax | 0.10 | 0.54 | 149 % |  |
| E2 pad-win | 0.10 | 0.54 | 149 % |  |
| E2 FF+PI + pad-105% | 0.43 | 0.59 | 106 % | 32 % frames over cap; quality factor leaks: corr -0.09, AUC 0.62; SSIM 0.981 |
