# N3 reconstruction attack (synthetic smoke data)

Target: ground truth; 404 test windows, 34 clusters, 5 keys; learned attacks: yes; scored full frame.

Validity gate (plain - control (c) >= 0.05, CI excluding 0): (0.1342330659236059, 0.12278340391263615, 0.1462100588477955) -> passes

| view | SSIM [95 % CI] | PSNR | edge corr | SSIM - control (f) | P1 pass | best attack |
|---|---|---|---|---|---|---|
| plain | 0.262 [0.256, 0.268] | 10.47 | 0.4941 | 0.130 [0.113, 0.146] | no | e2vid |
| V1 | 0.139 [0.137, 0.141] | 9.479 | 0.474 | 0.006 [-0.009, 0.022] | yes | denoise+integration |
| V2 | 0.029 [0.028, 0.030] | 9.244 | -0.001153 | -0.104 [-0.118, -0.088] | yes | denoise+integration |
| V3 | 0.030 [0.029, 0.030] | 9.168 | -0.001155 | -0.103 [-0.118, -0.088] | yes | denoise+integration |
| V4 | 0.005 [0.004, 0.005] | 10.31 | 0 | -0.128 [-0.143, -0.113] | yes | none |
| Du 2021 | 0.042 [0.041, 0.043] | 9.376 | 0.006851 | -0.091 [-0.106, -0.076] | yes | denoise+integration |
| Zhang 2024 | 0.112 [0.110, 0.114] | 10.24 | 0.1581 | -0.021 [-0.035, -0.006] | yes | denoise+integration |
| control_c | 0.128 [0.117, 0.139] | 10.4 | 0.08493 | -0.005 [-0.020, 0.010] | yes | - |
| control_f | 0.133 [0.118, 0.148] | 10.98 | 0.1122 | 0.000 [0.000, 0.000] | yes | - |
