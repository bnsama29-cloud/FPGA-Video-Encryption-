# N6 task accuracy

Clean model ({'nb': 8, 'arch': 'small', 'epochs': 20, 'shift': 0, 'down': 1}): 60000 training / 10000 test samples; ciphertext rows and decryption check: a fixed subset of 4000 / 2000, with a clear reference trained on the same subset. Decryption check: 64 of 64 test samples decrypt event-equal (V3). Gate: clean 0.995 vs 0.98 -> pass. Chance 0.100. SNN rows: run with --config N_snn10.

| view | (i) clear-trained on cipher | (ii) cipher-trained | (ii) - chance |
|---|---|---|---|
| clear (clean) | 0.995 [0.995, 0.996] | - | - |
| clear, trained on the subset | - | 0.984 [0.979, 0.988] | 0.884 [0.879, 0.888] |
| V2 | 0.130 [0.072, 0.187] | 0.407 [0.384, 0.429] | 0.307 [0.284, 0.329] |
| ideal | 0.130 [0.071, 0.188] | 0.407 [0.386, 0.427] | 0.306 [0.286, 0.327] |
