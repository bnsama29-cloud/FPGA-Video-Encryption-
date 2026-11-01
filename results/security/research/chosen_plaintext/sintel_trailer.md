### R8: chosen-plaintext permutation transferred to the next frame (sintel_trailer, 6 frame pairs, 300 tiles)

| Attacker's picture of frame t+1 | Tiles in place | Edge corr. | SSIM |
|---|---|---|---|
| as seen | 0.4 % | -0.001 | 0.174 |
| key-only shuffle | 100.0 % | 0.281 | 0.208 |
| E5 (per frame) | 0.4 % | -0.009 | 0.177 |

The attacker is given the exact permutation of frame t (a perfect chosen-plaintext step). Key-only shuffle: that permutation is also frame t+1's (oracle).
