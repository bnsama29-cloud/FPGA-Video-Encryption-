# N6 task accuracy

Clean model ({'nb': 1, 'arch': 'small', 'epochs': 20, 'shift': 0, 'down': 1}): 60000 training / 10000 test samples; ciphertext rows and decryption check: a fixed subset of 4000 / 2000, with a clear reference trained on the same subset. Decryption check: 64 of 64 test samples decrypt event-equal (V3). Gate: clean 0.991 vs 0.98 -> pass. Chance 0.100. SNN rows: run with --config N_snn10.

| view | (i) clear-trained on cipher | (ii) cipher-trained | (ii) - chance |
|---|---|---|---|
| clear (clean) | 0.991 [0.991, 0.992] | - | - |
| clear, trained on the subset | - | 0.972 [0.970, 0.974] | 0.872 [0.870, 0.874] |
| V1 | 0.990 [0.988, 0.992] | 0.970 [0.964, 0.976] | 0.870 [0.864, 0.876] |
| V2 | 0.114 [0.108, 0.120] | 0.216 [0.191, 0.242] | 0.116 [0.091, 0.142] |
| V3 | 0.109 [0.084, 0.134] | 0.204 [0.183, 0.226] | 0.104 [0.083, 0.126] |
| V4 | 0.114 [0.114, 0.114] | 0.114 [0.114, 0.114] | 0.013 [0.013, 0.013] |
| Du 2021 | 0.103 [0.084, 0.122] | 0.270 [0.249, 0.290] | 0.170 [0.149, 0.190] |
| Zhang 2024 | 0.824 [0.653, 0.994] | 0.965 [0.959, 0.971] | 0.865 [0.859, 0.871] |
