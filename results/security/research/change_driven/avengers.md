### R4: change-driven encoding (avengers, 120 frames, threshold 4.0, refresh every 30)

| Policy | Bytes vs full | Blocks coded | Projected cycles/px | PSNR | SSIM | Mask leak | Count leak | Size leak |
|---|---|---|---|---|---|---|---|---|
| full | 100 % | 100 % | 1.50 | 46.6 | 0.983 | -- | -- | 0.47 |
| full+pad | 178 % | 100 % | 1.50 | 46.6 | 0.983 | -- | -- | 0.00 |
| map-visible | 67 % | 30 % | 1.00 | 40.2 | 0.932 | 0.64 | 0.66 | 0.62 |
| map-hidden | 67 % | 30 % | 1.00 | 40.2 | 0.932 | -- | 0.66 | 0.62 |
| bins | 74 % | 39 % | 1.00 | 41.6 | 0.955 | -- | 0.53 | 0.57 |
| constant-0.25 | 50 % | 25 % | 1.00 | 38.1 | 0.893 | -- | 0.00 | 0.31 |
| constant-0.25+pad | 89 % | 25 % | 1.00 | 38.1 | 0.893 | -- | 0.00 | 0.00 |
| constant-0.5 | 77 % | 50 % | 1.00 | 42.7 | 0.959 | -- | 0.00 | 0.43 |

Leak columns: correlation with the true motion (1 = the attacker sees the motion exactly). Projected cycles/px assumes one input pixel per clock (the input then limits at 1.0).
