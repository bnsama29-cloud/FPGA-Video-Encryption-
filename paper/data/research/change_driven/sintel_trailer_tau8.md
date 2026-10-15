### R4: change-driven encoding (sintel_trailer_tau8, 120 frames, threshold 8.0, refresh every 30)

| Policy | Bytes vs full | Blocks coded | Projected cycles/px | PSNR | SSIM | Mask leak | Count leak | Size leak |
|---|---|---|---|---|---|---|---|---|
| full | 100 % | 100 % | 1.50 | 48.9 | 0.986 | -- | -- | 0.26 |
| full+pad | 165 % | 100 % | 1.50 | 48.9 | 0.986 | -- | -- | 0.00 |
| map-visible | 53 % | 26 % | 1.00 | 37.0 | 0.867 | 0.60 | 0.84 | 0.68 |
| map-hidden | 53 % | 26 % | 1.00 | 37.0 | 0.867 | -- | 0.84 | 0.68 |
| bins | 60 % | 33 % | 1.00 | 39.8 | 0.926 | -- | 0.80 | 0.66 |
| constant-0.25 | 47 % | 25 % | 1.00 | 35.8 | 0.864 | -- | 0.00 | 0.16 |
| constant-0.25+pad | 85 % | 25 % | 1.00 | 35.8 | 0.864 | -- | 0.00 | 0.00 |
| constant-0.5 | 73 % | 50 % | 1.00 | 41.2 | 0.940 | -- | 0.00 | 0.18 |

Leak columns: correlation with the true motion (1 = the attacker sees the motion exactly). Projected cycles/px assumes one input pixel per clock (the input then limits at 1.0).
