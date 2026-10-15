### R7: frame-size side channel (synthetic, 150 frames)

| Stream | Size-motion corr. | Event AUC (0.5 = chance) | Bytes vs E2 | Notes |
|---|---|---|---|---|
| E0 | 0.93 | 0.96 | 100 % |  |
| E1 | 0.93 | 0.95 | 100 % |  |
| E2 | 0.93 | 0.96 | 100 % |  |
| E3 | 0.93 | 0.95 | 100 % |  |
| E4 | 0.93 | 0.95 | 100 % |  |
| E5 | 0.93 | 0.94 | 111 % |  |
| E2 pad-1KB | 0.00 | 0.50 | 104 % |  |
| E2 pad-max | 0.00 | 0.50 | 103 % |  |
| E5 pad-1KB | 0.00 | 0.50 | 115 % |  |
| E5 pad-max | 0.00 | 0.50 | 114 % |  |
| E2 FF+PI + pad-105% | -0.10 | 0.52 | 106 % | 3 % frames over cap; quality factor leaks: corr -0.76, AUC 0.87; SSIM 0.949 |
