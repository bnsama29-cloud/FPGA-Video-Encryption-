### R8: chosen-plaintext permutation transferred to the next frame (synthetic, 6 frame pairs, 300 tiles)

| Attacker's picture of frame t+1 | Tiles in place | Edge corr. | SSIM |
|---|---|---|---|
| as seen | 0.4 % | 0.005 | 0.425 |
| key-only shuffle | 100.0 % | 0.383 | 0.546 |
| E5 (per frame) | 0.4 % | -0.006 | 0.428 |

The attacker is given the exact permutation of frame t (a perfect chosen-plaintext step). Key-only shuffle: that permutation is also frame t+1's (oracle).
