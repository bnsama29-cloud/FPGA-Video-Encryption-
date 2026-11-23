# N6 task accuracy

Clean model: 60000 training / 10000 test samples; ciphertext rows and decryption check: a fixed subset of 4000 / 2000. Decryption check: 64 of 64 test samples decrypt event-equal (V3). Gate: clean 0.991 vs 0.98 -> pass. Chance 0.100. SNN rows not run: the SNN of DESIGN §8.2 is not implemented, CNN only.

| view | (i) clear-trained on cipher | (ii) cipher-trained | (ii) - chance |
|---|---|---|---|
| clear (clean) | 0.991 [0.990, 0.992] | - | - |
| V1 | 0.989 [0.988, 0.991] | 0.970 [0.962, 0.977] | 0.870 [0.862, 0.877] |
| V2 | 0.108 [0.089, 0.127] | 0.220 [0.172, 0.268] | 0.120 [0.072, 0.168] |
| V3 | 0.109 [0.101, 0.117] | 0.212 [0.182, 0.243] | 0.112 [0.082, 0.143] |
| V4 | 0.114 [0.111, 0.118] | 0.114 [0.114, 0.114] | 0.013 [0.013, 0.013] |
| Du 2021 | 0.097 [0.072, 0.123] | 0.279 [0.264, 0.293] | 0.178 [0.164, 0.193] |
| Zhang 2024 | 0.849 [0.785, 0.914] | 0.966 [0.959, 0.973] | 0.866 [0.859, 0.873] |
