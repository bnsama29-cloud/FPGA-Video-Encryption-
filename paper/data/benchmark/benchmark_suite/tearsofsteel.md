# SVE-Bench (tearsofsteel, 320x240, 19 scored frames)

| Scheme | Source | Per-frame key | Auth. | Bytes | Decodes | A1 decode | A2 repl. | A3 NZCA | A4 cross-frame | **Max leak** |
|---|---|---|---|---|---|---|---|---|---|---|
| plain | - | - | no | +0.0% | yes | 0.94 | 0.94 | 0.77 | - | **0.94** |
| E1 | ours | yes | yes | +0.6% | yes | 0.45 | 0.38 | 0.77 | - | **0.77** |
| E2 | ours | yes | yes | +0.6% | yes | 0.12 | 0.39 | 0.77 | - | **0.77** |
| E3 | ours | yes | yes | +0.6% | yes | 0.11 | 0.38 | 0.77 | - | **0.77** |
| E4 | ours | yes | yes | +0.7% | yes | 0.18 | 0.38 | 0.77 | - | **0.77** |
| E5 (v2) | ours | yes | yes | +17.3% | yes | 0.00 | 0.01 | 0.02 | 0.01 | **0.02** |
| E5 (v3, hw) | ours | yes | yes | +17.3% | yes | -0.00 | 0.01 | 0.02 | 0.01 | **0.02** |
| VanDroogenbroeck | vandroogenbroeck2002 | no | no | +0.0% | yes | 0.45 | 0.36 | 0.77 | - | **0.77** |
| Kishore | kishore2015 | no | no | +0.1% | yes | -0.03 | -0.03 | -0.01 | 0.77 | **0.77** |
| Auer | auer2013 | yes | no | +0.1% | yes | 0.31 | 0.31 | 0.60 | 0.61 | **0.61** |
| Hirose RI=1 | hirose2024 | no | no | +16.6% | yes | -0.00 | -0.01 | -0.02 | 0.77 | **0.77** |
| Hirose RI=4 | hirose2024 | no | no | +4.2% | yes | -0.00 | 0.01 | -0.01 | 0.77 | **0.77** |
