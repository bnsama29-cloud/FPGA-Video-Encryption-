# SVE-Bench (jailer, 320x240, 19 scored frames)

| Scheme | Source | Per-frame key | Auth. | Bytes | Decodes | A1 decode | A2 repl. | A3 NZCA | A4 cross-frame | **Max leak** |
|---|---|---|---|---|---|---|---|---|---|---|
| plain | - | - | no | +0.0% | yes | 0.99 | 0.99 | 0.83 | - | **0.99** |
| E1 | ours | yes | yes | +0.8% | yes | 0.58 | 0.54 | 0.83 | - | **0.83** |
| E2 | ours | yes | yes | +0.8% | yes | 0.19 | 0.46 | 0.83 | - | **0.83** |
| E3 | ours | yes | yes | +0.8% | yes | 0.17 | 0.45 | 0.83 | - | **0.83** |
| E4 | ours | yes | yes | +0.8% | yes | 0.16 | 0.45 | 0.83 | - | **0.83** |
| E5 (v2) | ours | yes | yes | +22.7% | yes | 0.02 | 0.03 | 0.01 | 0.01 | **0.03** |
| E5 (v3, hw) | ours | yes | yes | +22.7% | yes | 0.02 | 0.03 | 0.01 | 0.01 | **0.03** |
| VanDroogenbroeck | vandroogenbroeck2002 | no | no | +0.0% | yes | 0.58 | 0.54 | 0.83 | - | **0.83** |
| Kishore | kishore2015 | no | no | +0.0% | yes | -0.01 | -0.01 | 0.00 | 0.83 | **0.83** |
| Auer | auer2013 | yes | no | +0.1% | yes | 0.34 | 0.34 | 0.61 | 0.60 | **0.61** |
| Hirose RI=1 | hirose2024 | no | no | +21.9% | yes | 0.02 | 0.03 | 0.02 | 0.83 | **0.83** |
| Hirose RI=4 | hirose2024 | no | no | +5.5% | yes | 0.01 | 0.03 | 0.02 | 0.83 | **0.83** |
