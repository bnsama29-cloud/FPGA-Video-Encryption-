### R3: bitrate regulation (synthetic, 150 frames, budget 100 % -> 60 % -> 120 % of the median size at quality 75; 0 % of frames infeasible even at quality 5)

| Controller | Mean abs. error | Error after settling | Frames >10 % over | Settling after drop (frames) | Overshoot after drop | Mean quality | Mean SSIM |
|---|---|---|---|---|---|---|---|
| fixed | 27.9 % | 27.7 % | 33 % | -- | +71 % | 75 | 0.949 |
| bang-bang | 5.9 % | 3.6 % | 5 % | 6 | +42 % | 63 | 0.941 |
| I | 2.8 % | 1.4 % | 3 % | 5 | +24 % | 63 | 0.941 |
| PI | 3.8 % | 2.2 % | 5 % | 7 | +27 % | 64 | 0.941 |
| FF+PI | 1.9 % | 1.4 % | 0 % | 0 | +8 % | 63 | 0.940 |
