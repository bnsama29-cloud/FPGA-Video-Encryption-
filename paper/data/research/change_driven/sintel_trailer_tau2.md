### R4: change-driven encoding (sintel_trailer_tau2, 120 frames, threshold 2.0, refresh every 30)

| Policy | Bytes vs full | Blocks coded | Projected cycles/px | PSNR | SSIM | Mask leak | Count leak | Size leak |
|---|---|---|---|---|---|---|---|---|
| full | 100 % | 100 % | 1.50 | 48.9 | 0.986 | -- | -- | 0.26 |
| full+pad | 165 % | 100 % | 1.50 | 48.9 | 0.986 | -- | -- | 0.00 |
| map-visible | 86 % | 53 % | 1.00 | 45.9 | 0.975 | 0.69 | 0.63 | 0.49 |
| map-hidden | 86 % | 53 % | 1.00 | 45.9 | 0.975 | -- | 0.63 | 0.49 |
| bins | 95 % | 64 % | 1.00 | 46.6 | 0.979 | -- | 0.58 | 0.41 |
| constant-0.25 | 49 % | 25 % | 1.00 | 37.0 | 0.866 | -- | 0.00 | 0.09 |
| constant-0.25+pad | 86 % | 25 % | 1.00 | 37.0 | 0.866 | -- | 0.00 | 0.00 |
| constant-0.5 | 77 % | 50 % | 1.00 | 42.8 | 0.949 | -- | 0.00 | 0.13 |

Leak columns: correlation with the true motion (1 = the attacker sees the motion exactly). Projected cycles/px assumes one input pixel per clock (the input then limits at 1.0).
