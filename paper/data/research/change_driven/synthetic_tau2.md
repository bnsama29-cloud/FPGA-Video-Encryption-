### R4: change-driven encoding (synthetic_tau2, 120 frames, threshold 2.0, refresh every 30)

| Policy | Bytes vs full | Blocks coded | Projected cycles/px | PSNR | SSIM | Mask leak | Count leak | Size leak |
|---|---|---|---|---|---|---|---|---|
| full | 100 % | 100 % | 1.50 | 35.7 | 0.950 | -- | -- | 0.93 |
| full+pad | 103 % | 100 % | 1.50 | 35.7 | 0.950 | -- | -- | 0.00 |
| map-visible | 23 % | 8 % | 1.00 | 35.2 | 0.946 | 0.84 | 0.93 | 0.95 |
| map-hidden | 23 % | 8 % | 1.00 | 35.2 | 0.946 | -- | 0.93 | 0.95 |
| bins | 24 % | 9 % | 1.00 | 35.2 | 0.946 | -- | 0.84 | 0.90 |
| constant-0.25 | 38 % | 25 % | 1.00 | 35.4 | 0.948 | -- | 0.00 | 0.50 |
| constant-0.25+pad | 45 % | 25 % | 1.00 | 35.4 | 0.948 | -- | 0.00 | 0.00 |
| constant-0.5 | 62 % | 50 % | 1.00 | 35.5 | 0.949 | -- | 0.00 | 0.35 |

Leak columns: correlation with the true motion (1 = the attacker sees the motion exactly). Projected cycles/px assumes one input pixel per clock (the input then limits at 1.0).
