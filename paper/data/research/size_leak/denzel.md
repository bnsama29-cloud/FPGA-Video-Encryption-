### R7: frame-size side channel (denzel, 150 frames)

| Stream | Size-motion corr. | Event AUC (0.5 = chance) | Bytes vs E2 | Notes |
|---|---|---|---|---|
| E0 | -0.44 | 0.64 | 100 % |  |
| E1 | -0.44 | 0.64 | 100 % |  |
| E2 | -0.44 | 0.65 | 100 % |  |
| E3 | -0.44 | 0.65 | 100 % |  |
| E4 | -0.44 | 0.64 | 100 % |  |
| E5 | -0.44 | 0.64 | 112 % |  |
| E2 pad-1KB | -0.43 | 0.60 | 107 % |  |
| E2 pad-max | 0.00 | 0.50 | 131 % |  |
| E5 pad-1KB | -0.45 | 0.61 | 119 % |  |
| E5 pad-max | 0.00 | 0.50 | 142 % |  |
| E2 pad-runmax | -0.37 | 0.78 | 104 % |  |
| E2 pad-win | -0.37 | 0.78 | 104 % |  |
| E2 FF+PI + pad-105% | 0.48 | 0.55 | 98 % | 14 % frames over cap; quality factor leaks: corr 0.44, AUC 0.78; SSIM 0.978 |
