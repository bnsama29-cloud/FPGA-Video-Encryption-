### R3: bitrate regulation (sintel_trailer, 150 frames, budget 100 % -> 60 % -> 120 % of the median size at quality 75; 0 % of frames infeasible even at quality 5)

| Controller | Mean abs. error | Error after settling | Frames >10 % over | Settling after drop (frames) | Overshoot after drop | Mean quality | Mean SSIM |
|---|---|---|---|---|---|---|---|
| fixed | 61.6 % | 61.8 % | 45 % | -- | +156 % | 75 | 0.989 |
| bang-bang | 24.7 % | 21.5 % | 14 % | 12 | +64 % | 60 | 0.953 |
| I | 19.5 % | 17.3 % | 7 % | 3 | +31 % | 61 | 0.952 |
| PI | 21.6 % | 19.5 % | 9 % | 6 | +37 % | 60 | 0.953 |
| FF+PI | 20.0 % | 19.0 % | 5 % | 2 | +19 % | 61 | 0.951 |
