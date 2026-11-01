### R4: change-driven encoding (tearsofsteel_tau8, 120 frames, threshold 8.0, refresh every 30)

| Policy | Bytes vs full | Blocks coded | Projected cycles/px | PSNR | SSIM | Mask leak | Count leak | Size leak |
|---|---|---|---|---|---|---|---|---|
| full | 100 % | 100 % | 1.50 | 42.7 | 0.985 | -- | -- | 0.52 |
| full+pad | 241 % | 100 % | 1.50 | 42.7 | 0.985 | -- | -- | 0.00 |
| map-visible | 66 % | 22 % | 1.00 | 41.4 | 0.958 | 0.37 | 0.71 | 0.63 |
| map-hidden | 66 % | 22 % | 1.00 | 41.4 | 0.958 | -- | 0.71 | 0.63 |
| bins | 73 % | 31 % | 1.00 | 42.1 | 0.975 | -- | 0.64 | 0.59 |
| constant-0.25 | 44 % | 25 % | 1.00 | 38.2 | 0.872 | -- | 0.00 | 0.48 |
| constant-0.25+pad | 95 % | 25 % | 1.00 | 38.2 | 0.872 | -- | 0.00 | 0.00 |
| constant-0.5 | 73 % | 50 % | 1.00 | 40.7 | 0.945 | -- | 0.00 | 0.51 |

Leak columns: correlation with the true motion (1 = the attacker sees the motion exactly). Projected cycles/px assumes one input pixel per clock (the input then limits at 1.0).
