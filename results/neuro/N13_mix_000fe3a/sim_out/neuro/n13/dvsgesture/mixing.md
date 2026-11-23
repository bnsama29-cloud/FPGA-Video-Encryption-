# N13 mixing and shaped padding

Chance 0.091; 6 test clusters. Mixing k cameras costs no dummies;
largest k per sensor (k W <= 2048): imx636 1, davis346 5, cif 5, dvsgesture 16, nmnist 60, vga 3

| view | k | dummies per real | bal. acc. nearest-centroid | bal. acc. 5-NN |
|---|---|---|---|---|
| V3 | 1 | 0 | 0.348 [0.277, 0.409] | 0.277 [0.229, 0.340] |
| V3 mixed k=2 | 2 | 0 | 0.261 [0.207, 0.319] | 0.227 [0.205, 0.253] |
| V3 mixed k=4 | 4 | 0 | 0.178 [0.165, 0.189] | 0.129 [0.086, 0.169] |
| V3 mixed k=8 | 8 | 0 | 0.197 [0.175, 0.225] | 0.197 [0.154, 0.234] |
| V3 + pad floor 4 | 1 | 0.412 | 0.303 [0.219, 0.397] | 0.227 [0.182, 0.277] |
| V3 + pad floor 16 | 1 | 3.383 | 0.318 [0.273, 0.357] | 0.250 [0.209, 0.293] |
| V3 + pad ladder 2..64 | 1 | 0.407 | 0.303 [0.230, 0.379] | 0.246 [0.219, 0.293] |
| V3 + shaped lam=0.9 | 1 | 0.659 | 0.326 [0.258, 0.393] | 0.280 [0.232, 0.351] |
| V3 + shaped lam=0.98 | 1 | 1.271 | 0.333 [0.268, 0.390] | 0.288 [0.239, 0.344] |
