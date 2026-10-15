### R7: frame-size side channel (challenge, 150 frames)

| Stream | Size-motion corr. | Event AUC (0.5 = chance) | Bytes vs E2 | Notes |
|---|---|---|---|---|
| E0 | 0.11 | 0.50 | 100 % |  |
| E1 | 0.11 | 0.50 | 100 % |  |
| E2 | 0.11 | 0.50 | 100 % |  |
| E3 | 0.11 | 0.50 | 100 % |  |
| E4 | 0.11 | 0.50 | 100 % |  |
| E5 | 0.11 | 0.50 | 111 % |  |
| E2 pad-1KB | 0.12 | 0.52 | 106 % |  |
| E2 pad-max | 0.00 | 0.50 | 174 % |  |
| E5 pad-1KB | 0.10 | 0.51 | 117 % |  |
| E5 pad-max | 0.00 | 0.50 | 184 % |  |
| E2 FF+PI + pad-105% | 0.45 | 0.72 | 109 % | 30 % frames over cap; quality factor leaks: corr -0.24, AUC 0.57; SSIM 0.975 |
