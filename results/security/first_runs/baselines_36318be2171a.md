# Software baselines on `36318be2171a` (x86_64)


## 320x240, quality 75, mean of 10 frames

| Method | ms / frame | fps | bytes | plays in VLC |
|---|---|---|---|---|
| jpeg (libjpeg-turbo) | 0.28 | 3616.5 | 8338 | yes |
| jpeg + full AES-128-GCM | 0.28 | 3571.9 | 8354 | no |
| jpeg + full ChaCha20-Poly1305 | 0.28 | 3517.3 | 8354 | no |
| jpeg + selective E2 (Python, after encoding) | 55.13 | 18.1 | 8363 | yes |
| jpeg + selective E4 (Python, after encoding) | 61.21 | 16.3 | 8371 | yes |
| FPGA encoder + in-pipeline encryption (from cycles/pixel) | 1.26 | 794.0 | - | yes |

## 640x480, quality 75, mean of 10 frames

| Method | ms / frame | fps | bytes | plays in VLC |
|---|---|---|---|---|
| jpeg (libjpeg-turbo) | 0.95 | 1047.2 | 19512 | yes |
| jpeg + full AES-128-GCM | 0.96 | 1040.2 | 19528 | no |
| jpeg + full ChaCha20-Poly1305 | 0.97 | 1032.3 | 19528 | no |
| jpeg + selective E2 (Python, after encoding) | 142.69 | 7.0 | 19550 | yes |
| jpeg + selective E4 (Python, after encoding) | 150.90 | 6.6 | 19548 | yes |
| FPGA encoder + in-pipeline encryption (from cycles/pixel) | 5.04 | 198.5 | - | yes |
