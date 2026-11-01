### R3: bitrate regulation (tearsofsteel, 150 frames, budget 100 % -> 60 % -> 120 % of the median size at quality 75; 33 % of frames infeasible even at quality 5)

| Controller | Mean abs. error | Error after settling | Frames >10 % over | Settling after drop (frames) | Overshoot after drop | Mean quality | Mean SSIM |
|---|---|---|---|---|---|---|---|
| fixed | 104.4 % | 144.3 % | 50 % | 0 | +67 % | 75 | 0.989 |
| bang-bang | 21.7 % | 19.1 % | 31 % | 0 | +74 % | 46 | 0.921 |
| I | 20.4 % | 20.3 % | 32 % | 0 | +47 % | 41 | 0.917 |
| PI | 20.1 % | 19.0 % | 36 % | 0 | +53 % | 42 | 0.923 |
| FF+PI | 25.7 % | 29.7 % | 37 % | 0 | +34 % | 41 | 0.921 |
