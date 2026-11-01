### R3: bitrate regulation (sintel_trailer, 150 frames, budget 100 % -> 60 % -> 120 % of the median size at quality 75; 0 % of frames infeasible even at quality 5)

| Controller | Mean abs. error | Error after settling | Frames >10 % over | Settling after drop (frames) | Overshoot after drop | Mean quality | Mean SSIM |
|---|---|---|---|---|---|---|---|
| fixed | 61.6 % | 61.8 % | 45 % | -- | +156 % | 75 | 0.989 |
| bang-bang | 24.7 % | 21.5 % | 14 % | 12 | +64 % | 60 | 0.953 |
| I | 22.7 % | 20.8 % | 14 % | 6 | +33 % | 61 | 0.953 |
| PI | 23.7 % | 21.4 % | 19 % | 8 | +41 % | 61 | 0.961 |
| FF+PI | 22.1 % | 20.9 % | 14 % | 0 | +8 % | 61 | 0.954 |
