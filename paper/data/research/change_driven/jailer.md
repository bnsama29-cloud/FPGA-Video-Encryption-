### R4: change-driven encoding (jailer, 120 frames, threshold 4.0, refresh every 30)

| Policy | Bytes vs full | Blocks coded | Projected cycles/px | PSNR | SSIM | Mask leak | Count leak | Size leak |
|---|---|---|---|---|---|---|---|---|
| full | 100 % | 100 % | 1.50 | 42.8 | 0.989 | -- | -- | 0.33 |
| full+pad | 329 % | 100 % | 1.50 | 42.8 | 0.989 | -- | -- | 0.00 |
| map-visible | 50 % | 19 % | 1.00 | 40.1 | 0.945 | 0.69 | 0.86 | 0.83 |
| map-hidden | 50 % | 19 % | 1.00 | 40.1 | 0.945 | -- | 0.86 | 0.83 |
| bins | 54 % | 25 % | 1.00 | 40.8 | 0.972 | -- | 0.76 | 0.73 |
| constant-0.25 | 49 % | 25 % | 1.00 | 36.2 | 0.860 | -- | 0.00 | 0.16 |
| constant-0.25+pad | 95 % | 25 % | 1.00 | 36.2 | 0.860 | -- | 0.00 | 0.00 |
| constant-0.5 | 73 % | 50 % | 1.00 | 40.0 | 0.944 | -- | 0.00 | 0.30 |

Leak columns: correlation with the true motion (1 = the attacker sees the motion exactly). Projected cycles/px assumes one input pixel per clock (the input then limits at 1.0).
