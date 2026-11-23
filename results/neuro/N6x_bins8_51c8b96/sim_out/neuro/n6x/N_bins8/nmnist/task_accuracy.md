# N6 task accuracy

Clean model ({'nb': 8, 'arch': 'small', 'epochs': 20, 'shift': 0, 'down': 1}): 60000 training / 10000 test samples; ciphertext rows and decryption check: a fixed subset of 4000 / 2000, with a clear reference trained on the same subset. Decryption check: 64 of 64 test samples decrypt event-equal (V3). Gate: clean 0.995 vs 0.98 -> pass. Chance 0.100. SNN rows: run with --config N_snn10.

| view | (i) clear-trained on cipher | (ii) cipher-trained | (ii) - chance |
|---|---|---|---|
| clear (clean) | 0.995 [0.994, 0.997] | - | - |
| clear, trained on the subset | - | 0.985 [0.984, 0.986] | 0.885 [0.884, 0.886] |
| V2 | 0.116 [0.114, 0.119] | 0.407 [0.387, 0.426] | 0.307 [0.287, 0.326] |
| V3 | 0.117 [0.115, 0.119] | 0.398 [0.374, 0.423] | 0.298 [0.274, 0.323] |
| Du 2021 | 0.133 [0.111, 0.154] | 0.541 [0.517, 0.564] | 0.441 [0.417, 0.464] |
| Zhang 2024 | 0.246 [0.188, 0.304] | 0.980 [0.973, 0.986] | 0.880 [0.873, 0.886] |
