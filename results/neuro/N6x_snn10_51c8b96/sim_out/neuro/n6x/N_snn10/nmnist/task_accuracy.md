# N6 task accuracy

Clean model ({'nb': 10, 'arch': 'snn', 'epochs': 20, 'shift': 0, 'down': 1}): 60000 training / 10000 test samples; ciphertext rows and decryption check: a fixed subset of 4000 / 2000, with a clear reference trained on the same subset. Decryption check: 64 of 64 test samples decrypt event-equal (V3). Gate: clean 0.990 vs 0.98 -> pass. Chance 0.100. this table is the SNN of DESIGN §8.2.

| view | (i) clear-trained on cipher | (ii) cipher-trained | (ii) - chance |
|---|---|---|---|
| clear (clean) | 0.990 [0.989, 0.992] | - | - |
| clear, trained on the subset | - | 0.971 [0.965, 0.976] | 0.871 [0.865, 0.876] |
| V1 | 0.369 [0.297, 0.441] | 0.954 [0.945, 0.963] | 0.854 [0.845, 0.863] |
| V2 | 0.116 [0.116, 0.116] | 0.152 [0.094, 0.210] | 0.052 [-0.006, 0.110] |
| V3 | 0.116 [0.116, 0.116] | 0.147 [0.122, 0.171] | 0.047 [0.022, 0.071] |
| V4 | 0.114 [0.114, 0.114] | 0.114 [0.114, 0.114] | 0.013 [0.013, 0.013] |
| Du 2021 | 0.120 [0.114, 0.126] | 0.218 [0.193, 0.244] | 0.118 [0.093, 0.144] |
| Zhang 2024 | 0.224 [0.189, 0.259] | 0.941 [0.917, 0.964] | 0.841 [0.817, 0.864] |
