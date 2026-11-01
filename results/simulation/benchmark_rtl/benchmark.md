
### 320x240, quality 75, mean of 10 frames (PC)

| Method | ms / frame | Bytes encrypted | Output bytes | Plays in VLC |
|---|---|---|---|---|
| plain JPEG (no protection) | 36.31 | 0 | 8395 | yes |
| in-encoder E2 (golden model, Python) | 70.34 | 995 | 8437 | yes |
| software selective E2 after encoding | 62.33 | 995 | 8437 | yes |
| in-encoder E4 (golden model, Python) | 75.60 | 2178 | 8442 | yes |
| software selective E4 after encoding | 67.08 | 2178 | 8442 | yes |
| in-encoder E5 (golden model, Python) | 97.25 | 2382 | 9427 | yes |
| software selective E5 after encoding | 84.79 | 2382 | 9427 | yes |
| full-stream Ascon-AEAD128 (Python) | 22.96 | 8395 | 8411 | no |
| full-stream AES-128-GCM (OpenSSL) | 0.01 | 8395 | 8411 | no |
| full-stream ChaCha20-Poly1305 (OpenSSL) | 0.01 | 8395 | 8411 | no |

### 640x480, quality 75, mean of 10 frames (PC)

| Method | ms / frame | Bytes encrypted | Output bytes | Plays in VLC |
|---|---|---|---|---|
| plain JPEG (no protection) | 134.02 | 0 | 19932 | yes |
| in-encoder E2 (golden model, Python) | 219.04 | 2323 | 19982 | yes |
| software selective E2 after encoding | 150.60 | 2323 | 19982 | yes |
| in-encoder E4 (golden model, Python) | 229.19 | 4524 | 19987 | yes |
| software selective E4 after encoding | 162.33 | 4524 | 19987 | yes |
| in-encoder E5 (golden model, Python) | 316.11 | 5557 | 24198 | yes |
| software selective E5 after encoding | 248.28 | 5557 | 24198 | yes |
| full-stream Ascon-AEAD128 (Python) | 55.38 | 19932 | 19948 | no |
| full-stream AES-128-GCM (OpenSSL) | 0.01 | 19932 | 19948 | no |
| full-stream ChaCha20-Poly1305 (OpenSSL) | 0.01 | 19932 | 19948 | no |

### RTL (Icarus), 160x128, 100 MHz

| Mode | Cycles / frame | Cycles / pixel | Extra cycles vs E0 | 640x480 fps |
|---|---|---|---|---|
| E0 | 33519 | 1.637 | 0 | 199 |
| E1 | 33518 | 1.637 | -1 | 199 |
| E2 | 33521 | 1.637 | 2 | 199 |
| E3 | 33518 | 1.637 | -1 | 199 |
| E4 | 33519 | 1.637 | 0 | 199 |
