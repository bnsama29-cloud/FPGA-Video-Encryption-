# Repeated runs: full_suite

5 repetitions; mean ± half-width of the 95 % interval over episodes (Student t).

| Attack | episodes | mitigated | first rejection at the receiver (s) | time to mitigate (s) |
|---|---|---|---|---|
| bitflip | 5 | 5/5 | 0.044 ± 0.045 | 0.43 ± 0.01 |
| downgrade | 5 | 5/5 | 0.064 ± 0.038 | 0.48 ± 0.02 |
| splice | 5 | 5/5 | 0.068 ± 0.058 | 0.48 ± 0.03 |
| inject | 5 | 5/5 | 0.055 ± 0.044 | 0.46 ± 0.04 |
| replay | 5 | 5/5 | 0.068 ± 0.037 | 0.48 ± 0.03 |
| delay | 5 | 5/5 | 4.046 ± 0.066 | 1.47 ± 0.04 |
| drop | 5 | 5/5 | - | 1.46 ± 0.02 |
| flood | 5 | 5/5 | - | 0.48 ± 0.03 |
| fb_drop | 5 | 5/5 | - | 3.49 ± 0.04 |
| fb_forge | 5 | 5/5 | - | 0.46 ± 0.04 |
| fb_replay | 5 | 5/5 | - | 0.46 ± 0.02 |

All attacks: 55/55 episodes mitigated, mean time to mitigate 0.92 ± 0.24 s.
False alarms: 0 of 625 calm windows (summed over repetitions).
