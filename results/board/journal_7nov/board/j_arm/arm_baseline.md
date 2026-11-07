# A3: ARM baseline on `pynq` (ARMv7 Processor rev 0 (v7l), 2 cores, armv7l)

Compiler flags: `-O3 -shared -fPIC -pthread`. Median of 20 frames, quality 75, wall clock incl. the Python call. Gate: PS encoder bit-exact with the model.

## 320x240

| Method | ms / frame | fps | plays without key | authenticated |
|---|---|---|---|---|
| ours on the PS, E0, 1 core | 31.53 | 31.7 | yes | yes |
| ours on the PS, E2, 1 core | 33.04 | 30.3 | yes | yes |
| ours on the PS, E4, 1 core | 33.19 | 30.1 | yes | yes |
| ours on the PS, E5, 1 core | 38.35 | 26.1 | yes | yes |
| ours on the PS, E0, 2 cores | 19.19 | 52.1 | yes | yes |
| ours on the PS, E2, 2 cores | 19.98 | 50.1 | yes | yes |
| ours on the PS, E4, 2 cores | 20.10 | 49.7 | yes | yes |
| ours on the PS, E5, 2 cores | 22.95 | 43.6 | yes | yes |
| libjpeg-turbo (no security) | 7.46 | 134.1 | yes | no |
| libjpeg-turbo + Ascon-AEAD128 whole file (C) | 8.54 | 117.1 | no | yes |
| libjpeg-turbo + AES-128-GCM whole file (OpenSSL) | 8.81 | 113.5 | no | yes |
| PL (FPGA) round trip, E0 | 15.82 | 63.2 | yes | yes |
| PL fabric only, E0 | 0.83 | 1204.8 | yes | yes |
| PL (FPGA) round trip, E2 | 15.77 | 63.4 | yes | yes |
| PL fabric only, E2 | 0.82 | 1212.1 | yes | yes |
| PL (FPGA) round trip, E4 | 15.75 | 63.5 | yes | yes |
| PL fabric only, E4 | 0.82 | 1213.6 | yes | yes |
| PL (FPGA) round trip, E5 | 17.14 | 58.3 | yes | yes |
| PL fabric only, E5 | 0.83 | 1209.2 | yes | yes |
| PL (FPGA) round trip, zero-copy, E0 | 4.85 | 206.2 | yes | yes |
| PL (FPGA) round trip, zero-copy, E2 | 4.79 | 208.8 | yes | yes |
| PL (FPGA) round trip, zero-copy, E4 | 4.79 | 208.8 | yes | yes |
| PL (FPGA) round trip, zero-copy, E5 | 6.18 | 161.8 | yes | yes |

Speed-up of the PL (round trip) over our encoder on the PS (2 cores), E2: **1.3x**

Speed-up of the PL (zero-copy round trip) over our encoder on the PS (2 cores), E2: **4.2x**

Speed-up of the PL (fabric only) over our encoder on the PS (2 cores), E2: **24.2x**

## 640x480

| Method | ms / frame | fps | plays without key | authenticated |
|---|---|---|---|---|
| ours on the PS, E0, 1 core | 114.38 | 8.7 | yes | yes |
| ours on the PS, E2, 1 core | 119.77 | 8.3 | yes | yes |
| ours on the PS, E4, 1 core | 120.38 | 8.3 | yes | yes |
| ours on the PS, E5, 1 core | 140.44 | 7.1 | yes | yes |
| ours on the PS, E0, 2 cores | 61.91 | 16.2 | yes | yes |
| ours on the PS, E2, 2 cores | 64.75 | 15.4 | yes | yes |
| ours on the PS, E4, 2 cores | 65.12 | 15.4 | yes | yes |
| ours on the PS, E5, 2 cores | 78.37 | 12.8 | yes | yes |
| libjpeg-turbo (no security) | 28.76 | 34.8 | yes | no |
| libjpeg-turbo + Ascon-AEAD128 whole file (C) | 32.20 | 31.1 | no | yes |
| libjpeg-turbo + AES-128-GCM whole file (OpenSSL) | 31.90 | 31.3 | no | yes |
| PL (FPGA) round trip, E0 | 49.47 | 20.2 | yes | yes |
| PL fabric only, E0 | 1.81 | 551.9 | yes | yes |
| PL (FPGA) round trip, E2 | 49.45 | 20.2 | yes | yes |
| PL fabric only, E2 | 1.81 | 551.3 | yes | yes |
| PL (FPGA) round trip, E4 | 49.45 | 20.2 | yes | yes |
| PL fabric only, E4 | 1.81 | 551.6 | yes | yes |
| PL (FPGA) round trip, E5 | 52.41 | 19.1 | yes | yes |
| PL fabric only, E5 | 1.82 | 550.7 | yes | yes |
| PL (FPGA) round trip, zero-copy, E0 | 5.90 | 169.5 | yes | yes |
| PL (FPGA) round trip, zero-copy, E2 | 5.90 | 169.5 | yes | yes |
| PL (FPGA) round trip, zero-copy, E4 | 5.95 | 168.1 | yes | yes |
| PL (FPGA) round trip, zero-copy, E5 | 8.78 | 113.9 | yes | yes |

Speed-up of the PL (round trip) over our encoder on the PS (2 cores), E2: **1.3x**

Speed-up of the PL (zero-copy round trip) over our encoder on the PS (2 cores), E2: **11.0x**

Speed-up of the PL (fabric only) over our encoder on the PS (2 cores), E2: **35.7x**
