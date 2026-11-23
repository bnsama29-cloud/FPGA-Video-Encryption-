# N3 reconstruction attack

Target: plaintext E2VID reconstruction; 386 test windows, 17 clusters, 5 keys; learned attacks: yes; scored inside the person box (Event-ReId labels/label.json; union over the frames of the window, +4 px).

Validity gate (plain - control (c) >= 0.05, CI excluding 0): (0.6918429775367801, 0.6746757475772228, 0.7095224069235961) -> passes

| view | SSIM [95 % CI] | PSNR | edge corr | SSIM - control (f) | P1 pass | best attack |
|---|---|---|---|---|---|---|
| plain | 1.000 [1.000, 1.000] | 99 | 1 | 0.672 [0.643, 0.701] | no | e2vid |
| V1 | 0.503 [0.470, 0.537] | 12.94 | 0.6217 | 0.175 [0.143, 0.210] | no | e2vid |
| V2 | 0.113 [0.099, 0.128] | 10.14 | 0.004528 | -0.215 [-0.245, -0.184] | yes | e2vid |
| V3 | 0.121 [0.108, 0.134] | 10.18 | 0.004607 | -0.207 [-0.233, -0.180] | yes | integration |
| V4 | 0.003 [0.002, 0.003] | 3.529 | 0 | -0.325 [-0.355, -0.297] | yes | none |
| Du 2021 | 0.096 [0.089, 0.105] | 10.18 | 0.01023 | -0.232 [-0.263, -0.201] | yes | e2vid |
| control_c | 0.308 [0.290, 0.325] | 10.34 | 0.1192 | -0.020 [-0.048, 0.010] | yes | - |
| control_f | 0.328 [0.299, 0.357] | 9.712 | 0.08356 | 0.000 [0.000, 0.000] | yes | - |

Zhang 2024: not run at 640 x 480: it adds noise events to every empty pixel (> 128 x 128).
