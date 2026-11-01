### R8: chosen-plaintext permutation transferred to the next frame (jailer, 6 frame pairs, 300 tiles)

| Attacker's picture of frame t+1 | Tiles in place | Edge corr. | SSIM |
|---|---|---|---|
| as seen | 0.4 % | 0.010 | 0.046 |
| key-only shuffle | 100.0 % | 0.439 | 0.049 |
| E5 (per frame) | 0.4 % | 0.003 | 0.047 |

The attacker is given the exact permutation of frame t (a perfect chosen-plaintext step). Key-only shuffle: that permutation is also frame t+1's (oracle).
