### R3: bitrate regulation (denzel, 150 frames, budget 100 % -> 60 % -> 120 % of the median size at quality 75; 0 % of frames infeasible even at quality 5)

| Controller | Mean abs. error | Error after settling | Frames >10 % over | Settling after drop (frames) | Overshoot after drop | Mean quality | Mean SSIM |
|---|---|---|---|---|---|---|---|
| fixed | 35.1 % | 33.4 % | 53 % | -- | +79 % | 75 | 0.983 |
| bang-bang | 10.7 % | 7.6 % | 9 % | 6 | +49 % | 65 | 0.977 |
| I | 6.3 % | 4.5 % | 7 % | 4 | +24 % | 63 | 0.976 |
| PI | 8.4 % | 6.5 % | 11 % | 6 | +27 % | 63 | 0.976 |
| FF+PI | 7.3 % | 6.1 % | 7 % | 0 | +7 % | 63 | 0.975 |
