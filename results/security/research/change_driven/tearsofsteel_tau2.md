### R4: change-driven encoding (tearsofsteel_tau2, 120 frames, threshold 2.0, refresh every 30)

| Policy | Bytes vs full | Blocks coded | Projected cycles/px | PSNR | SSIM | Mask leak | Count leak | Size leak |
|---|---|---|---|---|---|---|---|---|
| full | 100 % | 100 % | 1.50 | 42.7 | 0.985 | -- | -- | 0.52 |
| full+pad | 241 % | 100 % | 1.50 | 42.7 | 0.985 | -- | -- | 0.00 |
| map-visible | 85 % | 33 % | 1.00 | 42.6 | 0.984 | 0.24 | 0.58 | 0.53 |
| map-hidden | 85 % | 33 % | 1.00 | 42.6 | 0.984 | -- | 0.58 | 0.53 |
| bins | 86 % | 39 % | 1.00 | 42.7 | 0.985 | -- | 0.56 | 0.53 |
| constant-0.25 | 44 % | 25 % | 1.00 | 38.2 | 0.872 | -- | 0.00 | 0.48 |
| constant-0.25+pad | 95 % | 25 % | 1.00 | 38.2 | 0.872 | -- | 0.00 | 0.00 |
| constant-0.5 | 74 % | 50 % | 1.00 | 40.8 | 0.945 | -- | 0.00 | 0.50 |

Leak columns: correlation with the true motion (1 = the attacker sees the motion exactly). Projected cycles/px assumes one input pixel per clock (the input then limits at 1.0).
