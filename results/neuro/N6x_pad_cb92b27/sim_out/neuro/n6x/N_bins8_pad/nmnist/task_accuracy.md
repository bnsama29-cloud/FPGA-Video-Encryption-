# N6 task accuracy

Clean model ({'nb': 8, 'arch': 'small', 'epochs': 20, 'shift': 0, 'down': 1}): 60000 training / 10000 test samples; ciphertext rows and decryption check: a fixed subset of 4000 / 2000, with a clear reference trained on the same subset. Decryption check: 64 of 64 test samples decrypt event-equal (V3). Gate: clean 0.996 vs 0.98 -> pass. Chance 0.100. SNN rows: run with --config N_snn10.

| view | (i) clear-trained on cipher | (ii) cipher-trained | (ii) - chance |
|---|---|---|---|
| clear (clean) | 0.996 [0.994, 0.997] | - | - |
| clear, trained on the subset | - | 0.984 [0.980, 0.988] | 0.884 [0.880, 0.888] |
| V3 | 0.117 [0.112, 0.122] | 0.391 [0.370, 0.413] | 0.291 [0.270, 0.313] |
| V3 + pad floor 4 | 0.116 [0.116, 0.116] | 0.114 [0.114, 0.114] | 0.013 [0.013, 0.013] |
| V3 + pad floor 16 | 0.116 [0.115, 0.118] | 0.114 [0.114, 0.114] | 0.013 [0.013, 0.013] |
| V3 + pad ladder 2..64 | 0.116 [0.116, 0.116] | 0.339 [0.301, 0.378] | 0.239 [0.201, 0.278] |
