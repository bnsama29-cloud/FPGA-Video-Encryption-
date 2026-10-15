### R3: bitrate regulation (sintel_trailer, 150 frames, budget 100 % -> 60 % -> 120 % of the median size at quality 75; 0 % of frames infeasible even at quality 5)

| Controller | Mean abs. error | Error after settling | Frames >10 % over | Settling after drop (frames) | Overshoot after drop | Mean quality | Mean SSIM |
|---|---|---|---|---|---|---|---|
| fixed | 61.6 % | 61.8 % | 45 % | -- | +156 % | 75 | 0.989 |
| bang-bang | 24.7 % | 21.5 % | 14 % | 12 | +64 % | 60 | 0.953 |
| I | 19.5 % | 17.2 % | 8 % | 5 | +40 % | 61 | 0.954 |
| PI | 23.5 % | 21.4 % | 11 % | 7 | +44 % | 61 | 0.956 |
| FF+PI | 21.7 % | 20.8 % | 7 % | 2 | +19 % | 61 | 0.952 |
