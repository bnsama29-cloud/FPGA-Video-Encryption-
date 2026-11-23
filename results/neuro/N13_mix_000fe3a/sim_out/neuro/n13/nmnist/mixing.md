# N13 mixing and shaped padding

Chance 0.100; 10000 test clusters. Mixing k cameras costs no dummies;
largest k per sensor (k W <= 2048): imx636 1, davis346 5, cif 5, dvsgesture 16, nmnist 60, vga 3

| view | k | dummies per real | bal. acc. nearest-centroid | bal. acc. 5-NN |
|---|---|---|---|---|
| V3 | 1 | 0 | 0.267 [0.258, 0.274] | 0.229 [0.221, 0.237] |
| V3 mixed k=2 | 2 | 0 | 0.179 [0.171, 0.187] | 0.151 [0.144, 0.158] |
| V3 mixed k=4 | 4 | 0 | 0.159 [0.152, 0.165] | 0.130 [0.124, 0.136] |
| V3 mixed k=8 | 8 | 0 | 0.133 [0.126, 0.140] | 0.111 [0.105, 0.116] |
| V3 + pad floor 4 | 1 | 3.619 | 0.215 [0.207, 0.222] | 0.199 [0.192, 0.206] |
| V3 + pad floor 16 | 1 | 17.35 | 0.112 [0.107, 0.118] | 0.107 [0.101, 0.113] |
| V3 + pad ladder 2..64 | 1 | 1.618 | 0.239 [0.231, 0.246] | 0.218 [0.210, 0.225] |
| V3 + shaped lam=0.9 | 1 | 1.45 | 0.252 [0.244, 0.260] | 0.240 [0.231, 0.247] |
| V3 + shaped lam=0.98 | 1 | 2.339 | 0.252 [0.243, 0.260] | 0.227 [0.219, 0.234] |
