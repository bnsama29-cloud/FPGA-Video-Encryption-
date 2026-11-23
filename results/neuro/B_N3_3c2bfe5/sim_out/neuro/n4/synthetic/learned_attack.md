# N4 learned attack (synthetic smoke data)

Target: ground truth. Scored full frame.

Validity: control (f) (count series) must not be clearly worse than control (c) (median frame), else P1 is reported as invalid.

| view | SSIM network | SSIM control (f) | SSIM control (c) | network - control (f) | P1 pass | test clusters |
|---|---|---|---|---|---|---|
| plain | 0.740 [0.735, 0.746] | 0.466 [0.461, 0.469] | 0.470 [0.467, 0.474] | 0.275 [0.267, 0.282] | invalid: control (f) < control (c) | 34 |
| V1 | 0.718 [0.713, 0.723] | 0.466 [0.462, 0.470] | 0.470 [0.467, 0.474] | 0.252 [0.246, 0.259] | invalid: control (f) < control (c) | 34 |
| V2 | 0.473 [0.471, 0.475] | 0.466 [0.462, 0.470] | 0.470 [0.467, 0.474] | 0.007 [0.004, 0.010] | invalid: control (f) < control (c) | 34 |
| V3 | 0.468 [0.465, 0.470] | 0.466 [0.462, 0.470] | 0.470 [0.467, 0.474] | 0.002 [-0.002, 0.005] | invalid: control (f) < control (c) | 34 |
| Du 2021 | 0.471 [0.468, 0.473] | 0.466 [0.462, 0.470] | 0.470 [0.467, 0.474] | 0.004 [0.000, 0.009] | invalid: control (f) < control (c) | 34 |
| Zhang 2024 | 0.725 [0.720, 0.730] | 0.466 [0.462, 0.470] | 0.470 [0.467, 0.474] | 0.259 [0.252, 0.266] | invalid: control (f) < control (c) | 34 |
