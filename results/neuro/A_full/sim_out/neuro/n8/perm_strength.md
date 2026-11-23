# N8 permutation strength

| domain | points | inverse exact | table TV | TV sampling noise | corr(P_k, P_k+1) |
|---|---|---|---|---|---|
| nmnist | 1156 | yes | 0.04118 | 0.0446 | -0.02243 |
| dvsgesture | 16384 | yes | 0.0417 | 0.0446 | -0.0008912 |
| davis346 | 89960 | yes | 0.04905 | 0.05145 | -0.005197 |
| cif | 101376 | yes | 0.0506 | 0.04931 | -0.0007558 |
| vga | 307200 | yes | 0.05047 | 0.0515 | -0.0004457 |
| imx636 | 921600 | yes | 0.06005 | 0.05947 | 0.00188 |
| 16x16 | 256 | yes | 0.03125 | 0.0446 | 0.07504 |
| 1280x16 | 20480 | yes | 0.3727 | 0.3989 | -0.0002503 |

Refusal below 16: 15x16 refused, 16x15 refused, 1x720 refused, 1280x1 refused

| T µs | packets | distinct addr median | p99 | max | DV 4-round need | max/need |
|---|---|---|---|---|---|---|
| 256 | 1300262 | 11 | 43 | 75 | 2896 | 0.0259 |
| 1024 | 328727 | 40 | 140 | 198 | 2896 | 0.06836 |
| 4096 | 82214 | 135 | 398 | 532 | 2896 | 0.1837 |

Round structure (oracle, full codebook): P(same y | inputs differ only in x)

| domain | r1 | r2 | r4 | r6 | r8 | ideal | ideal_expected |
|---|---|---|---|---|---|---|---|
| 34x34 | 1 | 0.0298 | 0.0304 | 0.0271 | 0.02905 | 0.02825 | 0.02857 |
| 64x16 | 1 | 0.0578 | 0.0589 | 0.0641 | 0.05865 | 0.05985 | 0.06158 |

| level | n_cd | read back | in range | non-monotone pairs | max back-step µs | expelliarmus | tonic |
|---|---|---|---|---|---|---|---|
| V1 | 87787 | 87787 | True | 0 | 0 | installed: run on Kaggle (reader call in kaggle_neuro.py) | installed: run on Kaggle (reader call in kaggle_neuro.py) |
| V2 | 87787 | 87787 | True | 0 | 0 | installed: run on Kaggle (reader call in kaggle_neuro.py) | installed: run on Kaggle (reader call in kaggle_neuro.py) |
| V3 | 87787 | 87787 | True | 21353 | 63 | installed: run on Kaggle (reader call in kaggle_neuro.py) | installed: run on Kaggle (reader call in kaggle_neuro.py) |
