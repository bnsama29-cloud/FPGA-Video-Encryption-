# Repeated runs: full_suite_board

5 repetitions; mean ± half-width of the 95 % interval over episodes (Student t).

| Attack | episodes | mitigated | first rejection at the receiver (s) | time to mitigate (s) |
|---|---|---|---|---|
| bitflip | 5 | 5/5 | 0.064 ± 0.029 | 0.90 ± 0.03 |
| downgrade | 5 | 5/5 | 0.081 ± 0.025 | 0.90 ± 0.05 |
| splice | 5 | 5/5 | 0.066 ± 0.037 | 0.91 ± 0.05 |
| inject | 5 | 5/5 | 0.071 ± 0.034 | 0.91 ± 0.06 |
| replay | 5 | 5/5 | 0.064 ± 0.024 | 0.90 ± 0.04 |
| delay | 5 | 5/5 | 4.032 ± 0.042 | 1.92 ± 0.05 |
| drop | 5 | 5/5 | - | 1.90 ± 0.03 |
| flood | 5 | 5/5 | - | 0.90 ± 0.03 |
| fb_drop | 5 | 5/5 | - | 3.12 ± 0.53 |
| fb_forge | 5 | 5/5 | - | 0.90 ± 0.04 |
| fb_replay | 5 | 5/5 | - | 0.89 ± 0.03 |

All attacks: 55/55 episodes mitigated, mean time to mitigate 1.29 ± 0.19 s.
False alarms: 0 of 635 calm windows (summed over repetitions).
