### R4: change-driven encoding (synthetic_tau8, 120 frames, threshold 8.0, refresh every 30)

| Policy | Bytes vs full | Blocks coded | Projected cycles/px | PSNR | SSIM | Mask leak | Count leak | Size leak |
|---|---|---|---|---|---|---|---|---|
| full | 100 % | 100 % | 1.50 | 35.7 | 0.950 | -- | -- | 0.93 |
| full+pad | 103 % | 100 % | 1.50 | 35.7 | 0.950 | -- | -- | 0.00 |
| map-visible | 21 % | 6 % | 1.00 | 32.1 | 0.925 | 0.90 | 0.95 | 0.96 |
| map-hidden | 21 % | 6 % | 1.00 | 32.1 | 0.925 | -- | 0.95 | 0.96 |
| bins | 23 % | 9 % | 1.00 | 31.9 | 0.926 | -- | 0.88 | 0.88 |
| constant-0.25 | 37 % | 25 % | 1.00 | 33.7 | 0.941 | -- | 0.00 | 0.47 |
| constant-0.25+pad | 46 % | 25 % | 1.00 | 33.7 | 0.941 | -- | 0.00 | 0.00 |
| constant-0.5 | 62 % | 50 % | 1.00 | 34.8 | 0.946 | -- | 0.00 | 0.44 |

Leak columns: correlation with the true motion (1 = the attacker sees the motion exactly). Projected cycles/px assumes one input pixel per clock (the input then limits at 1.0).
