# N4 learned attack

Target: plaintext E2VID reconstruction. Scored inside the person box (Event-ReId labels/label.json; union over the frames of the window, +4 px).

Validity: control (f) (count series) must not be clearly worse than control (c) (median frame), else P1 is reported as invalid.

| view | SSIM network | SSIM control (f) | SSIM control (c) | network - control (f) | P1 pass | test clusters |
|---|---|---|---|---|---|---|
| plain | 0.832 [0.814, 0.849] | 0.687 [0.654, 0.718] | 0.687 [0.654, 0.718] | 0.145 [0.126, 0.165] | no | 17 |
| V1 | 0.711 [0.681, 0.739] | 0.687 [0.654, 0.718] | 0.687 [0.654, 0.718] | 0.024 [0.017, 0.030] | yes | 17 |
| V2 | 0.686 [0.655, 0.716] | 0.687 [0.654, 0.718] | 0.687 [0.654, 0.718] | -0.001 [-0.004, 0.002] | yes | 17 |
| V3 | 0.686 [0.655, 0.716] | 0.687 [0.654, 0.718] | 0.687 [0.654, 0.718] | -0.001 [-0.004, 0.002] | yes | 17 |
| Du 2021 | 0.686 [0.656, 0.715] | 0.687 [0.654, 0.718] | 0.687 [0.654, 0.718] | -0.002 [-0.005, 0.002] | yes | 17 |
| Zhang 2024 | 0.736 [0.709, 0.761] | 0.687 [0.654, 0.718] | 0.687 [0.654, 0.718] | 0.049 [0.037, 0.059] | no | 17 |
