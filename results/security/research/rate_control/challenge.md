### R3: bitrate regulation (challenge, 150 frames, budget 100 % -> 60 % -> 120 % of the median size at quality 75; 0 % of frames infeasible even at quality 5)

| Controller | Mean abs. error | Error after settling | Frames >10 % over | Settling after drop (frames) | Overshoot after drop | Mean quality | Mean SSIM |
|---|---|---|---|---|---|---|---|
| fixed | 40.6 % | 39.2 % | 45 % | 6 | +111 % | 75 | 0.979 |
| bang-bang | 15.2 % | 12.6 % | 21 % | 10 | +70 % | 62 | 0.966 |
| I | 11.8 % | 10.5 % | 19 % | 10 | +80 % | 63 | 0.965 |
| PI | 13.0 % | 11.3 % | 23 % | 10 | +77 % | 63 | 0.965 |
| FF+PI | 11.9 % | 11.4 % | 19 % | 0 | +74 % | 62 | 0.964 |
