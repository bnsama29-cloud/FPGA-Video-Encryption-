# SVE-Bench (denzel, 320x240, 19 scored frames)

| Scheme | Source | Per-frame key | Auth. | Bytes | Decodes | A1 decode | A2 repl. | A3 NZCA | A4 cross-frame | **Max leak** |
|---|---|---|---|---|---|---|---|---|---|---|
| plain | - | - | no | +0.0% | yes | 0.99 | 0.99 | 0.88 | - | **0.99** |
| E1 | ours | yes | yes | +0.6% | yes | 0.56 | 0.47 | 0.88 | - | **0.88** |
| E2 | ours | yes | yes | +0.6% | yes | 0.14 | 0.47 | 0.88 | - | **0.88** |
| E3 | ours | yes | yes | +0.6% | yes | 0.15 | 0.46 | 0.88 | - | **0.88** |
| E4 | ours | yes | yes | +0.6% | yes | 0.16 | 0.46 | 0.88 | - | **0.88** |
| E5 (v2) | ours | yes | yes | +15.3% | yes | 0.01 | 0.00 | 0.00 | 0.02 | **0.02** |
| E5 (v3, hw) | ours | yes | yes | +15.3% | yes | 0.01 | 0.00 | 0.00 | 0.02 | **0.02** |
| VanDroogenbroeck | vandroogenbroeck2002 | no | no | +0.0% | yes | 0.55 | 0.46 | 0.88 | - | **0.88** |
| Kishore | kishore2015 | no | no | +0.0% | yes | -0.02 | -0.02 | 0.00 | 0.88 | **0.88** |
| Auer | auer2013 | yes | no | +0.1% | yes | 0.33 | 0.32 | 0.57 | 0.58 | **0.58** |
| Hirose RI=1 | hirose2024 | no | no | +14.7% | yes | 0.02 | 0.02 | 0.03 | 0.88 | **0.88** |
| Hirose RI=4 | hirose2024 | no | no | +3.7% | yes | 0.02 | 0.01 | 0.01 | 0.88 | **0.88** |
