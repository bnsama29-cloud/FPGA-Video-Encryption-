
### 320x240, quality 75, mean of 10 frames (PC)

| Method | ms / frame | Bytes encrypted | Output bytes | Plays in VLC |
|---|---|---|---|---|
| plain JPEG (no protection) | 38.09 | 0 | 8392 | yes |
| in-encoder E2 (golden model, Python) | 73.58 | 994 | 8435 | yes |
| software selective E2 after encoding | 62.20 | 994 | 8435 | yes |
| in-encoder E4 (golden model, Python) | 77.94 | 2178 | 8441 | yes |
| software selective E4 after encoding | 68.36 | 2178 | 8441 | yes |
| in-encoder E5 (golden model, Python) | 97.95 | 2381 | 9426 | yes |
| software selective E5 after encoding | 84.43 | 2381 | 9426 | yes |
| full-stream Ascon-AEAD128 (Python) | 23.95 | 8392 | 8408 | no |
| full-stream AES-128-GCM (OpenSSL) | 0.00 | 8392 | 8408 | no |
| full-stream ChaCha20-Poly1305 (OpenSSL) | 0.01 | 8392 | 8408 | no |

### 640x480, quality 75, mean of 10 frames (PC)

| Method | ms / frame | Bytes encrypted | Output bytes | Plays in VLC |
|---|---|---|---|---|
| plain JPEG (no protection) | 130.81 | 0 | 19948 | yes |
| in-encoder E2 (golden model, Python) | 214.98 | 2325 | 20005 | yes |
| software selective E2 after encoding | 151.79 | 2325 | 20005 | yes |
| in-encoder E4 (golden model, Python) | 223.20 | 4531 | 20009 | yes |
| software selective E4 after encoding | 159.08 | 4531 | 20009 | yes |
| in-encoder E5 (golden model, Python) | 310.44 | 5564 | 24218 | yes |
| software selective E5 after encoding | 248.17 | 5564 | 24218 | yes |
| full-stream Ascon-AEAD128 (Python) | 54.99 | 19948 | 19964 | no |
| full-stream AES-128-GCM (OpenSSL) | 0.01 | 19948 | 19964 | no |
| full-stream ChaCha20-Poly1305 (OpenSSL) | 0.01 | 19948 | 19964 | no |
