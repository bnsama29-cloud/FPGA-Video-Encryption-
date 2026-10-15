### R1b: cycles/pixel against frame size (scene, E2)

Fit: cycles/pixel = 1.5 + 1.224 / MCU rows (the first MCU row fills before the DCT starts).

| Frame | MCU rows | Measured | Fit |
|---|---|---|---|
| 64x48 | 3 | 1.924 | 1.908 |
| 128x96 | 6 | 1.689 | 1.704 |
| 160x128 | 8 | 1.639 | 1.653 |
| 320x240 | 15 | 1.570 | 1.582 |
| 640x480 | 30 | 1.534 | 1.541 |

| Predicted | cycles/pixel | Mpx/s at 100 MHz |
|---|---|---|
| 640x480 | 1.541 | 64.9 |
| 1280x720 | 1.527 | 65.5 |
| 1920x1080 | 1.518 | 65.9 |
