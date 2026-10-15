### R3: bitrate regulation (tearsofsteel, 150 frames, budget 100 % -> 60 % -> 120 % of the median size at quality 75; 33 % of frames infeasible even at quality 5)

| Controller | Mean abs. error | Error after settling | Frames >10 % over | Settling after drop (frames) | Overshoot after drop | Mean quality | Mean SSIM |
|---|---|---|---|---|---|---|---|
| fixed | 104.4 % | 144.3 % | 50 % | 0 | +67 % | 75 | 0.989 |
| bang-bang | 21.7 % | 19.1 % | 31 % | 0 | +74 % | 46 | 0.921 |
| I | 23.4 % | 25.8 % | 27 % | 0 | +47 % | 42 | 0.911 |
| PI | 31.4 % | 38.6 % | 38 % | 0 | +50 % | 43 | 0.916 |
| FF+PI | 30.7 % | 38.6 % | 38 % | 0 | +34 % | 41 | 0.911 |
