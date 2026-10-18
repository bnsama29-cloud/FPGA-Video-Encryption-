# SVE-Bench (avengers, 320x240, 19 scored frames)

| Scheme | Source | Per-frame key | Auth. | Bytes | Decodes | A1 decode | A2 repl. | A3 NZCA | A4 cross-frame | **Max leak** |
|---|---|---|---|---|---|---|---|---|---|---|
| plain | - | - | no | +0.0% | yes | 0.88 | 0.88 | 0.74 | - | **0.88** |
| E1 | ours | yes | yes | +0.8% | yes | 0.47 | 0.41 | 0.74 | - | **0.74** |
| E2 | ours | yes | yes | +0.8% | yes | 0.13 | 0.41 | 0.74 | - | **0.74** |
| E3 | ours | yes | yes | +0.8% | yes | 0.17 | 0.41 | 0.74 | - | **0.74** |
| E4 | ours | yes | yes | +0.8% | yes | 0.13 | 0.41 | 0.74 | - | **0.74** |
| E5 (v2) | ours | yes | yes | +22.7% | yes | 0.02 | 0.00 | 0.00 | 0.01 | **0.02** |
| E5 (v3, hw) | ours | yes | yes | +22.7% | yes | 0.02 | 0.00 | 0.00 | 0.01 | **0.02** |
| VanDroogenbroeck | vandroogenbroeck2002 | no | no | +0.0% | yes | 0.47 | 0.41 | 0.74 | - | **0.74** |
| Kishore | kishore2015 | no | no | +0.0% | yes | 0.03 | 0.03 | 0.01 | 0.74 | **0.74** |
| Auer | auer2013 | yes | no | +0.1% | yes | 0.33 | 0.32 | 0.55 | 0.56 | **0.56** |
| Hirose RI=1 | hirose2024 | no | no | +21.9% | yes | 0.02 | 0.02 | 0.03 | 0.74 | **0.74** |
| Hirose RI=4 | hirose2024 | no | no | +5.4% | yes | 0.03 | 0.03 | 0.04 | 0.74 | **0.74** |
