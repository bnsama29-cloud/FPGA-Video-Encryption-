### R3: bitrate regulation (denzel, 150 frames, budget 100 % -> 60 % -> 120 % of the median size at quality 75; 0 % of frames infeasible even at quality 5)

| Controller | Mean abs. error | Error after settling | Frames >10 % over | Settling after drop (frames) | Overshoot after drop | Mean quality | Mean SSIM |
|---|---|---|---|---|---|---|---|
| fixed | 35.1 % | 33.4 % | 53 % | -- | +79 % | 75 | 0.983 |
| bang-bang | 10.7 % | 7.6 % | 9 % | 6 | +49 % | 65 | 0.977 |
| I | 6.1 % | 4.5 % | 5 % | 3 | +18 % | 62 | 0.975 |
| PI | 8.2 % | 6.0 % | 7 % | 5 | +24 % | 62 | 0.974 |
| FF+PI | 8.1 % | 6.0 % | 5 % | 2 | +15 % | 62 | 0.974 |
