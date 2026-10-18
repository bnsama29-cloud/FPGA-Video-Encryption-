# SVE-Bench (sintel_trailer, 320x240, 19 scored frames)

| Scheme | Source | Per-frame key | Auth. | Bytes | Decodes | A1 decode | A2 repl. | A3 NZCA | A4 cross-frame | **Max leak** |
|---|---|---|---|---|---|---|---|---|---|---|
| plain | - | - | no | +0.0% | yes | 0.94 | 0.94 | 0.76 | - | **0.94** |
| E1 | ours | yes | yes | +1.0% | yes | 0.41 | 0.32 | 0.76 | - | **0.76** |
| E2 | ours | yes | yes | +1.0% | yes | 0.12 | 0.38 | 0.76 | - | **0.76** |
| E3 | ours | yes | yes | +1.0% | yes | 0.12 | 0.37 | 0.76 | - | **0.76** |
| E4 | ours | yes | yes | +1.0% | yes | 0.14 | 0.37 | 0.76 | - | **0.76** |
| E5 (v2) | ours | yes | yes | +27.3% | yes | -0.01 | -0.01 | 0.02 | 0.01 | **0.02** |
| E5 (v3, hw) | ours | yes | yes | +27.3% | yes | -0.01 | -0.01 | 0.02 | 0.01 | **0.02** |
| VanDroogenbroeck | vandroogenbroeck2002 | no | no | +0.0% | yes | 0.40 | 0.32 | 0.76 | - | **0.76** |
| Kishore | kishore2015 | no | no | +0.1% | yes | -0.02 | -0.02 | -0.00 | 0.76 | **0.76** |
| Auer | auer2013 | yes | no | +0.1% | yes | 0.25 | 0.24 | 0.50 | 0.49 | **0.50** |
| Hirose RI=1 | hirose2024 | no | no | +26.4% | yes | -0.01 | -0.00 | 0.02 | 0.76 | **0.76** |
| Hirose RI=4 | hirose2024 | no | no | +6.6% | yes | -0.00 | 0.01 | 0.06 | 0.76 | **0.76** |
