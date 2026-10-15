### R3: bitrate regulation (avengers, 150 frames, budget 100 % -> 60 % -> 120 % of the median size at quality 75; 0 % of frames infeasible even at quality 5)

| Controller | Mean abs. error | Error after settling | Frames >10 % over | Settling after drop (frames) | Overshoot after drop | Mean quality | Mean SSIM |
|---|---|---|---|---|---|---|---|
| fixed | 38.9 % | 36.1 % | 50 % | 23 | +169 % | 75 | 0.982 |
| bang-bang | 12.2 % | 10.9 % | 19 % | 6 | +64 % | 60 | 0.962 |
| I | 9.9 % | 9.7 % | 17 % | 3 | +42 % | 60 | 0.959 |
| PI | 10.8 % | 10.2 % | 19 % | 5 | +50 % | 60 | 0.961 |
| FF+PI | 11.8 % | 10.3 % | 19 % | 5 | +42 % | 60 | 0.960 |
