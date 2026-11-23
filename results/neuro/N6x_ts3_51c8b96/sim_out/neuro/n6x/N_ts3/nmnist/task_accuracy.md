# N6 task accuracy

Clean model ({'nb': 1, 'feat': 'ts3', 'arch': 'small', 'epochs': 20, 'shift': 0, 'down': 1}): 60000 training / 10000 test samples; ciphertext rows and decryption check: a fixed subset of 4000 / 2000, with a clear reference trained on the same subset. Decryption check: 64 of 64 test samples decrypt event-equal (V3). Gate: clean 0.993 vs 0.98 -> pass. Chance 0.100. SNN rows: run with --config N_snn10.

| view | (i) clear-trained on cipher | (ii) cipher-trained | (ii) - chance |
|---|---|---|---|
| clear (clean) | 0.993 [0.992, 0.993] | - | - |
| clear, trained on the subset | - | 0.972 [0.967, 0.977] | 0.872 [0.867, 0.877] |
| V2 | 0.118 [0.110, 0.125] | 0.362 [0.359, 0.364] | 0.262 [0.259, 0.264] |
| V3 | 0.118 [0.100, 0.137] | 0.359 [0.358, 0.359] | 0.259 [0.258, 0.259] |
| Du 2021 | 0.125 [0.094, 0.156] | 0.388 [0.375, 0.400] | 0.288 [0.275, 0.300] |
| Zhang 2024 | 0.604 [0.535, 0.672] | 0.969 [0.968, 0.971] | 0.869 [0.868, 0.871] |
