### R3: bitrate regulation (tearsofsteel, 150 frames, budget 100 % -> 60 % -> 120 % of the median size at quality 75; 33 % of frames infeasible even at quality 5)

| Controller | Mean abs. error | Error after settling | Frames >10 % over | Settling after drop (frames) | Overshoot after drop | Mean quality | Mean SSIM |
|---|---|---|---|---|---|---|---|
| fixed | 104.4 % | 144.3 % | 50 % | 0 | +67 % | 75 | 0.989 |
| bang-bang | 21.7 % | 19.1 % | 31 % | 0 | +74 % | 46 | 0.921 |
| I | 18.6 % | 18.0 % | 24 % | 0 | +45 % | 40 | 0.904 |
| PI | 32.8 % | 41.4 % | 37 % | 0 | +48 % | 42 | 0.911 |
| FF+PI | 138.1 % | 217.7 % | 37 % | 0 | +29 % | 49 | 0.917 |
