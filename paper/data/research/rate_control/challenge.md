### R3: bitrate regulation (challenge, 150 frames, budget 100 % -> 60 % -> 120 % of the median size at quality 75; 0 % of frames infeasible even at quality 5)

| Controller | Mean abs. error | Error after settling | Frames >10 % over | Settling after drop (frames) | Overshoot after drop | Mean quality | Mean SSIM |
|---|---|---|---|---|---|---|---|
| fixed | 40.6 % | 39.2 % | 45 % | 6 | +111 % | 75 | 0.979 |
| bang-bang | 15.2 % | 12.6 % | 21 % | 10 | +70 % | 62 | 0.966 |
| I | 10.7 % | 9.8 % | 15 % | 17 | +77 % | 62 | 0.965 |
| PI | 12.3 % | 11.0 % | 17 % | 18 | +72 % | 62 | 0.964 |
| FF+PI | 11.4 % | 11.3 % | 15 % | 2 | +65 % | 62 | 0.963 |
