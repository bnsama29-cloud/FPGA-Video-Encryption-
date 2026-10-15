### R4: change-driven encoding (challenge, 120 frames, threshold 4.0, refresh every 30)

| Policy | Bytes vs full | Blocks coded | Projected cycles/px | PSNR | SSIM | Mask leak | Count leak | Size leak |
|---|---|---|---|---|---|---|---|---|
| full | 100 % | 100 % | 1.50 | 40.2 | 0.979 | -- | -- | 0.13 |
| full+pad | 169 % | 100 % | 1.50 | 40.2 | 0.979 | -- | -- | 0.00 |
| map-visible | 61 % | 40 % | 1.00 | 37.2 | 0.968 | 0.55 | 0.87 | 0.64 |
| map-hidden | 61 % | 40 % | 1.00 | 37.2 | 0.968 | -- | 0.87 | 0.64 |
| bins | 65 % | 47 % | 1.00 | 38.0 | 0.971 | -- | 0.79 | 0.58 |
| constant-0.25 | 38 % | 25 % | 1.00 | 26.8 | 0.760 | -- | 0.00 | -0.09 |
| constant-0.25+pad | 65 % | 25 % | 1.00 | 26.8 | 0.760 | -- | 0.00 | 0.00 |
| constant-0.5 | 66 % | 50 % | 1.00 | 32.8 | 0.891 | -- | 0.00 | 0.06 |

Leak columns: correlation with the true motion (1 = the attacker sees the motion exactly). Projected cycles/px assumes one input pixel per clock (the input then limits at 1.0).
