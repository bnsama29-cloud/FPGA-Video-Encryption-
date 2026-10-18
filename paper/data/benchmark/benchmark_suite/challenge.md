# SVE-Bench (challenge, 320x240, 19 scored frames)

| Scheme | Source | Per-frame key | Auth. | Bytes | Decodes | A1 decode | A2 repl. | A3 NZCA | A4 cross-frame | **Max leak** |
|---|---|---|---|---|---|---|---|---|---|---|
| plain | - | - | no | +0.0% | yes | 0.99 | 0.99 | 0.83 | - | **0.99** |
| E1 | ours | yes | yes | +0.4% | yes | 0.50 | 0.46 | 0.83 | - | **0.83** |
| E2 | ours | yes | yes | +0.4% | yes | 0.13 | 0.44 | 0.83 | - | **0.83** |
| E3 | ours | yes | yes | +0.5% | yes | 0.16 | 0.43 | 0.83 | - | **0.83** |
| E4 | ours | yes | yes | +0.5% | yes | 0.13 | 0.43 | 0.83 | - | **0.83** |
| E5 (v2) | ours | yes | yes | +10.4% | yes | 0.01 | 0.00 | -0.00 | 0.03 | **0.03** |
| E5 (v3, hw) | ours | yes | yes | +10.4% | yes | 0.01 | 0.00 | -0.00 | 0.03 | **0.03** |
| VanDroogenbroeck | vandroogenbroeck2002 | no | no | +0.0% | yes | 0.50 | 0.45 | 0.83 | - | **0.83** |
| Kishore | kishore2015 | no | no | +0.0% | yes | 0.02 | 0.02 | -0.00 | 0.83 | **0.83** |
| Auer | auer2013 | yes | no | +0.1% | yes | 0.31 | 0.31 | 0.55 | 0.56 | **0.56** |
| Hirose RI=1 | hirose2024 | no | no | +10.0% | yes | 0.01 | 0.00 | -0.01 | 0.83 | **0.83** |
| Hirose RI=4 | hirose2024 | no | no | +2.4% | yes | 0.01 | 0.01 | 0.03 | 0.83 | **0.83** |
