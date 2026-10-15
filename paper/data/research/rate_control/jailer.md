### R3: bitrate regulation (jailer, 150 frames, budget 100 % -> 60 % -> 120 % of the median size at quality 75; 0 % of frames infeasible even at quality 5)

| Controller | Mean abs. error | Error after settling | Frames >10 % over | Settling after drop (frames) | Overshoot after drop | Mean quality | Mean SSIM |
|---|---|---|---|---|---|---|---|
| fixed | 55.0 % | 54.2 % | 60 % | -- | +191 % | 75 | 0.991 |
| bang-bang | 19.8 % | 16.9 % | 18 % | 8 | +61 % | 53 | 0.929 |
| I | 10.3 % | 7.9 % | 7 % | 3 | +40 % | 54 | 0.942 |
| PI | 13.5 % | 10.0 % | 13 % | 5 | +32 % | 53 | 0.930 |
| FF+PI | 12.1 % | 9.5 % | 10 % | 2 | +28 % | 53 | 0.925 |
