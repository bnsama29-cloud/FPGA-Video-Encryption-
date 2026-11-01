### R3: bitrate regulation (jailer, 150 frames, budget 100 % -> 60 % -> 120 % of the median size at quality 75; 0 % of frames infeasible even at quality 5)

| Controller | Mean abs. error | Error after settling | Frames >10 % over | Settling after drop (frames) | Overshoot after drop | Mean quality | Mean SSIM |
|---|---|---|---|---|---|---|---|
| fixed | 55.0 % | 54.2 % | 60 % | -- | +191 % | 75 | 0.991 |
| bang-bang | 19.8 % | 16.9 % | 18 % | 8 | +61 % | 53 | 0.929 |
| I | 13.2 % | 10.6 % | 16 % | 6 | +37 % | 55 | 0.940 |
| PI | 15.8 % | 13.1 % | 22 % | 9 | +37 % | 56 | 0.943 |
| FF+PI | 14.2 % | 12.4 % | 16 % | 0 | +31 % | 55 | 0.940 |
