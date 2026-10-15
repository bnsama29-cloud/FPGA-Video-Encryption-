### R7: frame-size side channel (avengers, 150 frames)

| Stream | Size-motion corr. | Event AUC (0.5 = chance) | Bytes vs E2 | Notes |
|---|---|---|---|---|
| E0 | 0.51 | 0.95 | 100 % |  |
| E1 | 0.51 | 0.95 | 100 % |  |
| E2 | 0.51 | 0.95 | 100 % |  |
| E3 | 0.51 | 0.95 | 100 % |  |
| E4 | 0.51 | 0.95 | 100 % |  |
| E5 | 0.51 | 0.95 | 124 % |  |
| E2 pad-1KB | 0.50 | 0.94 | 111 % |  |
| E2 pad-max | 0.00 | 0.50 | 199 % |  |
| E5 pad-1KB | 0.50 | 0.94 | 134 % |  |
| E5 pad-max | 0.00 | 0.50 | 224 % |  |
| E2 pad-runmax | 0.24 | 0.78 | 161 % |  |
| E2 pad-win | 0.24 | 0.78 | 161 % |  |
| E2 FF+PI + pad-105% | 0.02 | 0.73 | 99 % | 26 % frames over cap; quality factor leaks: corr -0.56, AUC 0.85; SSIM 0.970 |
