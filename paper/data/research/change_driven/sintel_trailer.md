### R4: change-driven encoding (sintel_trailer, 120 frames, threshold 4.0, refresh every 30)

| Policy | Bytes vs full | Blocks coded | Projected cycles/px | PSNR | SSIM | Mask leak | Count leak | Size leak |
|---|---|---|---|---|---|---|---|---|
| full | 100 % | 100 % | 1.50 | 48.9 | 0.986 | -- | -- | 0.26 |
| full+pad | 165 % | 100 % | 1.50 | 48.9 | 0.986 | -- | -- | 0.00 |
| map-visible | 71 % | 40 % | 1.00 | 42.2 | 0.945 | 0.69 | 0.75 | 0.56 |
| map-hidden | 71 % | 40 % | 1.00 | 42.2 | 0.945 | -- | 0.75 | 0.56 |
| bins | 83 % | 53 % | 1.00 | 44.5 | 0.968 | -- | 0.60 | 0.47 |
| constant-0.25 | 48 % | 25 % | 1.00 | 36.4 | 0.864 | -- | 0.00 | 0.11 |
| constant-0.25+pad | 86 % | 25 % | 1.00 | 36.4 | 0.864 | -- | 0.00 | 0.00 |
| constant-0.5 | 75 % | 50 % | 1.00 | 42.3 | 0.947 | -- | 0.00 | 0.15 |

Leak columns: correlation with the true motion (1 = the attacker sees the motion exactly). Projected cycles/px assumes one input pixel per clock (the input then limits at 1.0).
