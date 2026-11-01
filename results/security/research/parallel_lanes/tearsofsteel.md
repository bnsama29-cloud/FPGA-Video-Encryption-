### R2: parallel lanes over restart segments (tearsofsteel, 4 frames)

Exactness (all frames): plain_N1_L2 OK, plain_N1_L3 OK, plain_N1_L4 OK, plain_N20_L2 OK, plain_N20_L3 OK, plain_N20_L4 OK, plain_N80_L2 OK, plain_N80_L3 OK, plain_N80_L4 OK, restart_rows_decode_same_pixels OK, encrypted_lanes_merge_exact OK, segment_keystream_decrypts OK

Bitrate cost of one restart segment per MCU row: 1.95 % mean, 4.66 % max.

Model check against the RTL law (L=1, B=2, P=1): 160x128 -> 1.631, 320x240 -> 1.570 cycles/pixel (measured: 1.639, 1.570).

| Frame | Lanes | Input px/clk | Frame overlap | Cycles/px | Mpx/s @100 | @125 | @150 | LUT | DSP | BRAM36 |
|---|---|---|---|---|---|---|---|---|---|---|
| 640x480 | 1 | 1 | no | 1.535 | 65 | 81 | 98 | 5039 | 23 | 24.5 |
| 640x480 | 1 | 1 | yes | 1.502 | 67 | 83 | 100 | 5039 | 23 | 24.5 |
| 640x480 | 2 | 1 | no | 1.050 | 95 | 119 | 143 | 7584 | 45 | 36.5 |
| 640x480 | 2 | 1 | yes | 1.000 | 100 | 125 | 150 | 7584 | 45 | 36.5 |
| 640x480 | 2 | 2 | yes | 0.751 | 133 | 166 | 200 | 7584 | 45 | 36.5 |
| 640x480 | 4 | 2 | yes | 0.500 | 200 | 250 | 300 | 12674 | 89 | 60.5 |
| 1280x720 | 1 | 1 | no | 1.523 | 66 | 82 | 98 | 5039 | 23 | 24.5 |
| 1280x720 | 1 | 1 | yes | 1.501 | 67 | 83 | 100 | 5039 | 23 | 24.5 |
| 1280x720 | 2 | 1 | no | 1.033 | 97 | 121 | 145 | 7584 | 45 | 36.5 |
| 1280x720 | 2 | 1 | yes | 1.000 | 100 | 125 | 150 | 7584 | 45 | 36.5 |
| 1280x720 | 2 | 2 | yes | 0.750 | 133 | 167 | 200 | 7584 | 45 | 36.5 |
| 1280x720 | 4 | 2 | yes | 0.500 | 200 | 250 | 300 | 12674 | 89 | 60.5 |

Lanes > 1, 2 px/clk input and overlap are projections from the event model, not RTL measurements.
