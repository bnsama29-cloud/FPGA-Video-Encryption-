# N4 learned attack

Target: plaintext E2VID reconstruction. Scored inside the person box (Event-ReId labels/label.json; union over the frames of the window, +4 px).

Validity: control (f) (count series) must not be clearly worse than control (c) (median frame), else P1 is reported as invalid.

| view | SSIM network | SSIM control (f) | SSIM control (c) | network - control (f) | P1 pass | test clusters |
|---|---|---|---|---|---|---|
| plain | 0.819 [0.802, 0.835] | 0.573 [0.546, 0.599] | 0.687 [0.654, 0.718] | 0.246 [0.230, 0.263] | invalid: control (f) < control (c) | 17 |
| V1 | 0.689 [0.660, 0.715] | 0.572 [0.545, 0.598] | 0.687 [0.654, 0.718] | 0.117 [0.105, 0.130] | invalid: control (f) < control (c) | 17 |
| V2 | 0.650 [0.624, 0.675] | 0.572 [0.545, 0.598] | 0.687 [0.654, 0.718] | 0.078 [0.063, 0.094] | invalid: control (f) < control (c) | 17 |
| V3 | 0.652 [0.624, 0.677] | 0.572 [0.545, 0.598] | 0.687 [0.654, 0.718] | 0.080 [0.065, 0.097] | invalid: control (f) < control (c) | 17 |
| Du 2021 | 0.666 [0.638, 0.694] | 0.572 [0.545, 0.598] | 0.687 [0.654, 0.718] | 0.094 [0.078, 0.112] | invalid: control (f) < control (c) | 17 |
| Zhang 2024 | 0.726 [0.703, 0.747] | 0.572 [0.545, 0.598] | 0.687 [0.654, 0.718] | 0.154 [0.141, 0.167] | invalid: control (f) < control (c) | 17 |
