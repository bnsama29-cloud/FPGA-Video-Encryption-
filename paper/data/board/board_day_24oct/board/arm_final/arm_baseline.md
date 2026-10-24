# A3: ARM baseline on `pynq` (ARMv7 Processor rev 0 (v7l), 2 cores, armv7l)

Compiler flags: `-O3 -shared -fPIC -pthread -mcpu=cortex-a9 -mfpu=neon`. Median of 30 frames, quality 75, wall clock incl. the Python call. Gate: PS encoder bit-exact with the model.

## 320x240

| Method | ms / frame | fps | plays without key | authenticated |
|---|---|---|---|---|
| ours on the PS, E0, 1 core | 29.87 | 33.5 | yes | yes |
| ours on the PS, E2, 1 core | 31.22 | 32.0 | yes | yes |
| ours on the PS, E4, 1 core | 31.37 | 31.9 | yes | yes |
| ours on the PS, E5, 1 core | 36.39 | 27.5 | yes | yes |
| ours on the PS, E0, 2 cores | 18.15 | 55.1 | yes | yes |
| ours on the PS, E2, 2 cores | 18.92 | 52.8 | yes | yes |
| ours on the PS, E4, 2 cores | 18.99 | 52.7 | yes | yes |
| ours on the PS, E5, 2 cores | 21.83 | 45.8 | yes | yes |
| libjpeg-turbo (no security) | 7.45 | 134.2 | yes | no |
| libjpeg-turbo + Ascon-AEAD128 whole file (C) | 8.41 | 119.0 | no | yes |
| libjpeg-turbo + AES-128-GCM whole file (OpenSSL) | 8.81 | 113.5 | no | yes |
| PL (FPGA) round trip, E0 | 15.51 | 64.5 | yes | yes |
| PL fabric only, E0 | 0.98 | 1024.6 | yes | yes |
| PL (FPGA) round trip, E2 | 15.47 | 64.6 | yes | yes |
| PL fabric only, E2 | 0.97 | 1035.2 | yes | yes |
| PL (FPGA) round trip, E4 | 15.51 | 64.5 | yes | yes |
| PL fabric only, E4 | 0.97 | 1032.0 | yes | yes |
| PL (FPGA) round trip, E5 | 16.83 | 59.4 | yes | yes |
| PL fabric only, E5 | 0.97 | 1027.7 | yes | yes |

Speed-up of the PL (round trip) over our encoder on the PS (2 cores), E2: **1.2x**

Speed-up of the PL (fabric only) over our encoder on the PS (2 cores), E2: **19.6x**

## 640x480

| Method | ms / frame | fps | plays without key | authenticated |
|---|---|---|---|---|
| ours on the PS, E0, 1 core | 109.16 | 9.2 | yes | yes |
| ours on the PS, E2, 1 core | 114.18 | 8.8 | yes | yes |
| ours on the PS, E4, 1 core | 114.56 | 8.7 | yes | yes |
| ours on the PS, E5, 1 core | 133.02 | 7.5 | yes | yes |
| ours on the PS, E0, 2 cores | 59.02 | 16.9 | yes | yes |
| ours on the PS, E2, 2 cores | 61.61 | 16.2 | yes | yes |
| ours on the PS, E4, 2 cores | 61.82 | 16.2 | yes | yes |
| ours on the PS, E5, 2 cores | 74.80 | 13.4 | yes | yes |
| libjpeg-turbo (no security) | 28.75 | 34.8 | yes | no |
| libjpeg-turbo + Ascon-AEAD128 whole file (C) | 31.73 | 31.5 | no | yes |
| libjpeg-turbo + AES-128-GCM whole file (OpenSSL) | 31.93 | 31.3 | no | yes |
| PL (FPGA) round trip, E0 | 49.06 | 20.4 | yes | yes |
| PL fabric only, E0 | 1.96 | 509.4 | yes | yes |
| PL (FPGA) round trip, E2 | 49.06 | 20.4 | yes | yes |
| PL fabric only, E2 | 1.96 | 509.7 | yes | yes |
| PL (FPGA) round trip, E4 | 49.06 | 20.4 | yes | yes |
| PL fabric only, E4 | 1.96 | 509.4 | yes | yes |
| PL (FPGA) round trip, E5 | 51.86 | 19.3 | yes | yes |
| PL fabric only, E5 | 1.96 | 509.4 | yes | yes |

Speed-up of the PL (round trip) over our encoder on the PS (2 cores), E2: **1.3x**

Speed-up of the PL (fabric only) over our encoder on the PS (2 cores), E2: **31.4x**
