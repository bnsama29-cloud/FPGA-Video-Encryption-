### R4: change-driven encoding (synthetic, 120 frames, threshold 4.0, refresh every 30)

| Policy | Bytes vs full | Blocks coded | Projected cycles/px | PSNR | SSIM | Mask leak | Count leak | Size leak |
|---|---|---|---|---|---|---|---|---|
| full | 100 % | 100 % | 1.50 | 35.7 | 0.950 | -- | -- | 0.93 |
| full+pad | 103 % | 100 % | 1.50 | 35.7 | 0.950 | -- | -- | 0.00 |
| map-visible | 22 % | 7 % | 1.00 | 33.6 | 0.936 | 0.87 | 0.95 | 0.96 |
| map-hidden | 22 % | 7 % | 1.00 | 33.6 | 0.936 | -- | 0.95 | 0.96 |
| bins | 24 % | 9 % | 1.00 | 33.4 | 0.936 | -- | 0.88 | 0.88 |
| constant-0.25 | 38 % | 25 % | 1.00 | 34.6 | 0.945 | -- | 0.00 | 0.50 |
| constant-0.25+pad | 46 % | 25 % | 1.00 | 34.6 | 0.945 | -- | 0.00 | 0.00 |
| constant-0.5 | 62 % | 50 % | 1.00 | 35.3 | 0.948 | -- | 0.00 | 0.37 |

Leak columns: correlation with the true motion (1 = the attacker sees the motion exactly). Projected cycles/px assumes one input pixel per clock (the input then limits at 1.0).
