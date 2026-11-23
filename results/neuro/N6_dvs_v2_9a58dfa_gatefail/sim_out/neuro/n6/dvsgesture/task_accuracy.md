# N6 task accuracy

Clean model: 1077 training / 264 test samples; ciphertext rows and decryption check: a fixed subset of 300 / 264. Decryption check: 64 of 64 test samples decrypt event-equal (V3). Gate: clean 0.732 vs 0.9 -> FAIL: no ciphertext rows. Chance 0.091. SNN rows not run: the SNN of DESIGN §8.2 is not implemented, CNN only.

| view | (i) clear-trained on cipher | (ii) cipher-trained | (ii) - chance |
|---|---|---|---|
| clear (clean) | 0.732 [0.617, 0.847] | - | - |
