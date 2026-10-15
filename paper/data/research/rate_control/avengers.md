### R3: bitrate regulation (avengers, 150 frames, budget 100 % -> 60 % -> 120 % of the median size at quality 75; 0 % of frames infeasible even at quality 5)

| Controller | Mean abs. error | Error after settling | Frames >10 % over | Settling after drop (frames) | Overshoot after drop | Mean quality | Mean SSIM |
|---|---|---|---|---|---|---|---|
| fixed | 38.9 % | 36.1 % | 50 % | 23 | +169 % | 75 | 0.982 |
| bang-bang | 12.2 % | 10.9 % | 19 % | 6 | +64 % | 60 | 0.962 |
| I | 11.6 % | 11.4 % | 19 % | 4 | +96 % | 60 | 0.959 |
| PI | 12.7 % | 12.0 % | 23 % | 6 | +76 % | 60 | 0.960 |
| FF+PI | 13.0 % | 12.3 % | 20 % | 2 | +76 % | 59 | 0.956 |
