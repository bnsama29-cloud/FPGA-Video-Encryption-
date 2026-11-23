# N6 model selection

Training split only: 835 recordings to fit, 242 of held-out users ['train/user06', 'train/user08', 'train/user11', 'train/user13', 'train/user17'] to score. Median 309702 events and 6.36 s per recording (max 1594557 events); class counts [97, 98, 98, 98, 98, 98, 98, 98, 98, 98, 98].

| candidate | round | config | held-out accuracy per seed | mean | train s |
|---|---|---|---|---|---|
| A_bug74 | 1 | {'nb': 8, 'arch': 'small', 'epochs': 20, 'shift': 0, 'down': 1} | 0.686 / 0.731 | 0.709 | 73.3 |
| B_deep16 | 1 | {'nb': 16, 'arch': 'deep', 'epochs': 60, 'shift': 8, 'down': 1} | 0.756 / 0.769 | 0.762 | 360.9 |
| C_deep16_64px | 1 | {'nb': 16, 'arch': 'deep', 'epochs': 100, 'shift': 4, 'down': 2} | 0.711 / 0.756 | 0.733 | 85.9 |
| D_rn18_ts3 | 2 | {'nb': 1, 'feat': 'ts3', 'arch': 'resnet18', 'epochs': 40, 'shift': 8, 'down': 1} | 0.736 / 0.752 | 0.744 | 79 |
| E_rn18_bins16 | 2 | {'nb': 16, 'arch': 'resnet18', 'epochs': 40, 'shift': 8, 'down': 1} | 0.711 / 0.723 | 0.717 | 146.7 |
| F_rn18_bins16_64px | 2 | {'nb': 16, 'arch': 'resnet18', 'epochs': 60, 'shift': 4, 'down': 2} | 0.727 / 0.744 | 0.736 | 73.1 |

Chosen: B_deep16 (mean 0.762) of 6 candidates over 2 selection round(s) on the same held-out users (report the count: choosing the best of several on one split is itself optimistic); gate of the full run on the test split: 0.9.

| view | sealing s per recording (mean) |
|---|---|
| V1 | 8.1 |
| V2 | 49.4 |
| V3 | 9.7 |
| V4 | 6.8 |
| Du 2021 | 0.0 |
| Zhang 2024 | 0.2 |

Estimated sealing of the full N6 run (300 + 264 recordings, 4 processes): 2.9 h.
