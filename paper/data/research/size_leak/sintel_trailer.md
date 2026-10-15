### R7: frame-size side channel (sintel_trailer, 150 frames)

| Stream | Size-motion corr. | Event AUC (0.5 = chance) | Bytes vs E2 | Notes |
|---|---|---|---|---|
| E0 | 0.27 | 0.65 | 100 % |  |
| E1 | 0.27 | 0.65 | 100 % |  |
| E2 | 0.27 | 0.65 | 100 % |  |
| E3 | 0.27 | 0.65 | 100 % |  |
| E4 | 0.27 | 0.65 | 100 % |  |
| E5 | 0.26 | 0.66 | 123 % |  |
| E2 pad-1KB | 0.26 | 0.62 | 111 % |  |
| E2 pad-max | 0.00 | 0.50 | 183 % |  |
| E5 pad-1KB | 0.26 | 0.62 | 133 % |  |
| E5 pad-max | 0.00 | 0.50 | 204 % |  |
| E2 pad-runmax | 0.18 | 0.57 | 141 % |  |
| E2 pad-win | 0.18 | 0.57 | 141 % |  |
| E2 FF+PI + pad-105% | 0.62 | 0.52 | 126 % | 42 % frames over cap; quality factor leaks: corr -0.05, AUC 0.60; SSIM 0.978 |
