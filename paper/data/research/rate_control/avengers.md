### R3: bitrate regulation (avengers, 150 frames, budget 100 % -> 60 % -> 120 % of the median size at quality 75; 0 % of frames infeasible even at quality 5)

| Controller | Mean abs. error | Error after settling | Frames >10 % over | Settling after drop (frames) | Overshoot after drop | Mean quality | Mean SSIM |
|---|---|---|---|---|---|---|---|
| fixed | 38.9 % | 36.1 % | 50 % | 23 | +169 % | 75 | 0.982 |
| bang-bang | 12.2 % | 10.9 % | 19 % | 6 | +64 % | 60 | 0.962 |
| I | 9.6 % | 9.7 % | 15 % | 2 | +42 % | 59 | 0.959 |
| PI | 10.3 % | 10.2 % | 17 % | 4 | +42 % | 59 | 0.958 |
| FF+PI | 10.6 % | 10.1 % | 15 % | 4 | +42 % | 59 | 0.957 |
