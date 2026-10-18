# SVE-Bench (synthetic, 320x240, 19 scored frames)

| Scheme | Source | Per-frame key | Auth. | Bytes | Decodes | A1 decode | A2 repl. | A3 NZCA | A4 cross-frame | **Max leak** |
|---|---|---|---|---|---|---|---|---|---|---|
| plain | - | - | no | +0.0% | yes | 1.00 | 1.00 | 0.79 | - | **1.00** |
| E1 | ours | yes | yes | +0.4% | yes | 0.44 | 0.37 | 0.79 | - | **0.79** |
| E2 | ours | yes | yes | +0.4% | yes | 0.17 | 0.37 | 0.79 | - | **0.79** |
| E3 | ours | yes | yes | +0.4% | yes | 0.15 | 0.38 | 0.79 | - | **0.79** |
| E4 | ours | yes | yes | +0.5% | yes | 0.16 | 0.38 | 0.79 | - | **0.79** |
| E5 (v2) | ours | yes | yes | +11.5% | yes | -0.00 | 0.00 | 0.00 | 0.00 | **0.00** |
| E5 (v3, hw) | ours | yes | yes | +11.5% | yes | -0.00 | 0.00 | 0.00 | 0.00 | **0.00** |
| VanDroogenbroeck | vandroogenbroeck2002 | no | no | -0.0% | yes | 0.44 | 0.37 | 0.79 | - | **0.79** |
| Kishore | kishore2015 | no | no | -0.0% | yes | -0.01 | -0.01 | 0.00 | 0.79 | **0.79** |
| Auer | auer2013 | yes | no | +0.0% | yes | 0.24 | 0.24 | 0.58 | 0.58 | **0.58** |
| Hirose RI=1 | hirose2024 | no | no | +11.0% | yes | -0.02 | -0.01 | 0.01 | 0.79 | **0.79** |
| Hirose RI=4 | hirose2024 | no | no | +2.7% | yes | 0.01 | 0.01 | 0.11 | 0.79 | **0.79** |
