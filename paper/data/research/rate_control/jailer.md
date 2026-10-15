### R3: bitrate regulation (jailer, 150 frames, budget 100 % -> 60 % -> 120 % of the median size at quality 75; 0 % of frames infeasible even at quality 5)

| Controller | Mean abs. error | Error after settling | Frames >10 % over | Settling after drop (frames) | Overshoot after drop | Mean quality | Mean SSIM |
|---|---|---|---|---|---|---|---|
| fixed | 55.0 % | 54.2 % | 60 % | -- | +191 % | 75 | 0.991 |
| bang-bang | 19.8 % | 16.9 % | 18 % | 8 | +61 % | 53 | 0.929 |
| I | 10.9 % | 8.0 % | 13 % | 4 | +40 % | 55 | 0.945 |
| PI | 17.0 % | 14.2 % | 23 % | 6 | +39 % | 56 | 0.932 |
| FF+PI | 13.9 % | 11.8 % | 22 % | 4 | +31 % | 56 | 0.930 |
