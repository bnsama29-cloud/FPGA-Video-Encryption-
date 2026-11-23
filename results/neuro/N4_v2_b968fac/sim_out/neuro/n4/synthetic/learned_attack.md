# N4 learned attack (synthetic smoke data)

Target: ground truth. Scored full frame.

Validity: control (f) (count series) must not be clearly worse than control (c) (median frame), else P1 is reported as invalid.

| view | SSIM network | SSIM control (f) | SSIM control (c) | network - control (f) | P1 pass | test clusters |
|---|---|---|---|---|---|---|
| plain | 0.725 [0.719, 0.730] | 0.463 [0.456, 0.470] | 0.470 [0.467, 0.474] | 0.262 [0.252, 0.271] | invalid: control (f) < control (c) | 34 |
| V1 | 0.664 [0.657, 0.670] | 0.462 [0.454, 0.470] | 0.470 [0.467, 0.474] | 0.202 [0.191, 0.212] | invalid: control (f) < control (c) | 34 |
| V2 | 0.472 [0.469, 0.474] | 0.462 [0.454, 0.470] | 0.470 [0.467, 0.474] | 0.010 [0.003, 0.017] | invalid: control (f) < control (c) | 34 |
| V3 | 0.473 [0.470, 0.475] | 0.462 [0.454, 0.470] | 0.470 [0.467, 0.474] | 0.011 [0.004, 0.018] | invalid: control (f) < control (c) | 34 |
| Du 2021 | 0.471 [0.469, 0.474] | 0.462 [0.454, 0.470] | 0.470 [0.467, 0.474] | 0.010 [0.003, 0.016] | invalid: control (f) < control (c) | 34 |
| Zhang 2024 | 0.672 [0.666, 0.677] | 0.462 [0.454, 0.470] | 0.470 [0.467, 0.474] | 0.210 [0.200, 0.220] | invalid: control (f) < control (c) | 34 |
