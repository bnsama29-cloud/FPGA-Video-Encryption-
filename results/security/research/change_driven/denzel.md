### R4: change-driven encoding (denzel, 120 frames, threshold 4.0, refresh every 30)

| Policy | Bytes vs full | Blocks coded | Projected cycles/px | PSNR | SSIM | Mask leak | Count leak | Size leak |
|---|---|---|---|---|---|---|---|---|
| full | 100 % | 100 % | 1.50 | 35.6 | 0.983 | -- | -- | -0.39 |
| full+pad | 140 % | 100 % | 1.50 | 35.6 | 0.983 | -- | -- | 0.00 |
| map-visible | 41 % | 21 % | 1.00 | 34.8 | 0.964 | 0.59 | 0.85 | 0.52 |
| map-hidden | 41 % | 21 % | 1.00 | 34.8 | 0.964 | -- | 0.85 | 0.52 |
| bins | 46 % | 29 % | 1.00 | 35.1 | 0.969 | -- | 0.75 | 0.42 |
| constant-0.25 | 46 % | 25 % | 1.00 | 33.4 | 0.933 | -- | 0.00 | -0.50 |
| constant-0.25+pad | 57 % | 25 % | 1.00 | 33.4 | 0.933 | -- | 0.00 | 0.00 |
| constant-0.5 | 68 % | 50 % | 1.00 | 34.4 | 0.961 | -- | 0.00 | -0.36 |

Leak columns: correlation with the true motion (1 = the attacker sees the motion exactly). Projected cycles/px assumes one input pixel per clock (the input then limits at 1.0).
