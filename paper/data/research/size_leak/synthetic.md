### R7: frame-size side channel (synthetic, 150 frames)

| Stream | Size-motion corr. | Event AUC (0.5 = chance) | Bytes vs E2 | Notes |
|---|---|---|---|---|
| E0 | 0.93 | 0.94 | 100 % |  |
| E1 | 0.93 | 0.95 | 100 % |  |
| E2 | 0.93 | 0.94 | 100 % |  |
| E3 | 0.93 | 0.94 | 100 % |  |
| E4 | 0.93 | 0.95 | 100 % |  |
| E5 | 0.93 | 0.94 | 111 % |  |
| E2 pad-1KB | 0.00 | 0.50 | 104 % |  |
| E2 pad-max | 0.00 | 0.50 | 103 % |  |
| E5 pad-1KB | 0.00 | 0.50 | 115 % |  |
| E5 pad-max | 0.00 | 0.50 | 114 % |  |
| E2 pad-runmax | 0.25 | 0.54 | 103 % |  |
| E2 pad-win | 0.26 | 0.54 | 103 % |  |
| E2 FF+PI + pad-105% | -0.12 | 0.51 | 106 % | 2 % frames over cap; quality factor leaks: corr -0.75, AUC 0.88; SSIM 0.949 |
