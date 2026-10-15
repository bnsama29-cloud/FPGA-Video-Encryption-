### R7: frame-size side channel (tearsofsteel, 150 frames)

| Stream | Size-motion corr. | Event AUC (0.5 = chance) | Bytes vs E2 | Notes |
|---|---|---|---|---|
| E0 | 0.44 | 0.74 | 100 % |  |
| E1 | 0.44 | 0.74 | 100 % |  |
| E2 | 0.44 | 0.74 | 100 % |  |
| E3 | 0.44 | 0.74 | 100 % |  |
| E4 | 0.44 | 0.74 | 100 % |  |
| E5 | 0.45 | 0.75 | 115 % |  |
| E2 pad-1KB | 0.45 | 0.72 | 105 % |  |
| E2 pad-max | 0.00 | 0.50 | 221 % |  |
| E5 pad-1KB | 0.44 | 0.66 | 123 % |  |
| E5 pad-max | 0.00 | 0.50 | 235 % |  |
| E2 FF+PI + pad-105% | 0.28 | 0.53 | 117 % | 9 % frames over cap; quality factor leaks: corr -0.37, AUC 0.62; SSIM 0.969 |
