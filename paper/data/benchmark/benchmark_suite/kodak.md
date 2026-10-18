# SVE-Bench (kodak, 320x240, 23 scored frames)

| Scheme | Source | Per-frame key | Auth. | Bytes | Decodes | A1 decode | A2 repl. | A3 NZCA | A4 cross-frame | **Max leak** |
|---|---|---|---|---|---|---|---|---|---|---|
| plain | - | - | no | +0.0% | yes | 0.99 | 0.99 | 0.82 | - | **0.99** |
| E1 | ours | yes | yes | +0.3% | yes | 0.45 | 0.38 | 0.82 | - | **0.82** |
| E2 | ours | yes | yes | +0.3% | yes | 0.09 | 0.37 | 0.82 | - | **0.82** |
| E3 | ours | yes | yes | +0.3% | yes | 0.11 | 0.36 | 0.82 | - | **0.82** |
| E4 | ours | yes | yes | +0.3% | yes | 0.08 | 0.36 | 0.82 | - | **0.82** |
| E5 (v2) | ours | yes | yes | +7.8% | yes | -0.00 | 0.01 | 0.01 | 0.01 | **0.01** |
| E5 (v3, hw) | ours | yes | yes | +7.8% | yes | 0.00 | 0.01 | 0.01 | 0.01 | **0.01** |
| VanDroogenbroeck | vandroogenbroeck2002 | no | no | +0.0% | yes | 0.44 | 0.36 | 0.82 | - | **0.82** |
| Kishore | kishore2015 | no | no | +0.1% | yes | -0.00 | -0.00 | -0.00 | 0.82 | **0.82** |
| Auer | auer2013 | yes | no | +0.1% | yes | 0.28 | 0.28 | 0.61 | 0.60 | **0.61** |
| Hirose RI=1 | hirose2024 | no | no | +7.5% | yes | 0.01 | 0.01 | 0.02 | 0.82 | **0.82** |
| Hirose RI=4 | hirose2024 | no | no | +1.9% | yes | -0.00 | 0.00 | -0.01 | 0.82 | **0.82** |
