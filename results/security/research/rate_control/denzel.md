### R3: bitrate regulation (denzel, 150 frames, budget 100 % -> 60 % -> 120 % of the median size at quality 75; 0 % of frames infeasible even at quality 5)

| Controller | Mean abs. error | Error after settling | Frames >10 % over | Settling after drop (frames) | Overshoot after drop | Mean quality | Mean SSIM |
|---|---|---|---|---|---|---|---|
| fixed | 35.1 % | 33.4 % | 53 % | -- | +79 % | 75 | 0.983 |
| bang-bang | 10.7 % | 7.6 % | 9 % | 6 | +49 % | 65 | 0.977 |
| I | 6.6 % | 4.8 % | 9 % | 3 | +21 % | 63 | 0.976 |
| PI | 7.9 % | 5.8 % | 11 % | 5 | +30 % | 64 | 0.976 |
| FF+PI | 6.7 % | 5.5 % | 8 % | 1 | +3 % | 63 | 0.975 |
