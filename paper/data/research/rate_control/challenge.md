### R3: bitrate regulation (challenge, 150 frames, budget 100 % -> 60 % -> 120 % of the median size at quality 75; 0 % of frames infeasible even at quality 5)

| Controller | Mean abs. error | Error after settling | Frames >10 % over | Settling after drop (frames) | Overshoot after drop | Mean quality | Mean SSIM |
|---|---|---|---|---|---|---|---|
| fixed | 40.6 % | 39.2 % | 45 % | 6 | +111 % | 75 | 0.979 |
| bang-bang | 15.2 % | 12.6 % | 21 % | 10 | +70 % | 62 | 0.966 |
| I | 11.1 % | 10.0 % | 19 % | 11 | +80 % | 63 | 0.965 |
| PI | 14.0 % | 12.8 % | 26 % | 11 | +74 % | 63 | 0.966 |
| FF+PI | 13.5 % | 13.5 % | 25 % | 20 | +72 % | 62 | 0.965 |
