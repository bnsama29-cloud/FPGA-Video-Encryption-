Seeds: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]  (mean ± std over seeds; std uses n-1)

| Policy | Runs | Mitigated per run | time to mitigate (s) | leakage under attack | cost | cost when calm | latency median (ms) | False alarms |
|---|---|---|---|---|---|---|---|---|
| threshold | 10 | 10/10 10/10 10/10 10/10 10/10 10/10 10/10 10/10 10/10 10/10 | 0.460 ± 0.015 | 0.000 ± 0.001 | 0.188 ± 0.001 | 0.135 ± 0.000 | 79 ± 2 | 0/3010 |
| bandit | 10 | 10/10 10/10 10/10 10/10 10/10 10/10 10/10 10/10 10/10 10/10 | 1.336 ± 0.031 | 0.054 ± 0.004 | 0.162 ± 0.001 | 0.138 ± 0.001 | 71 ± 1 | 0/3010 |

Paired by seed, bandit minus threshold (negative = bandit better):

| Metric | Mean difference | Bandit better in |
|---|---|---|
| time to mitigate (s) | +0.876 | 0/10 seeds |
| leakage under attack | +0.053 | 0/10 seeds |
| cost | -0.026 | 10/10 seeds |
| cost when calm | +0.003 | 0/10 seeds |
| latency median (ms) | -8.200 | 10/10 seeds |
