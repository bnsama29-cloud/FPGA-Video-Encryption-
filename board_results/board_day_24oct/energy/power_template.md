| Method | Mode | Size | fps | Power (W) | Power source | Energy / frame (mJ) | Above idle (mJ) | vs first row |
|---|---|---|---|---|---|---|---|---|
| FPGA 4 lanes | E2 | 640x480 | 169.4 | 2.22 | Vivado estimate (overlay_lanes4, confidence Medium) | 13.1 | – | 1.00x |
| FPGA 4 lanes | E5 | 640x480 | 118.6 | 2.22 | Vivado estimate (overlay_lanes4, confidence Medium) | 18.7 | – | 1.43x |
| ours on the PS, E2, 2 cores | E2 | 640x480 | 16.2 | – | not measured | – | – | – |
| ours on the PS, E5, 2 cores | E5 | 640x480 | 13.4 | – | not measured | – | – | – |
| libjpeg-turbo (no security) | - | 640x480 | 34.8 | – | not measured | – | – | – |
| libjpeg-turbo + Ascon-AEAD128 whole file (C) | full | 640x480 | 31.5 | – | not measured | – | – | – |
| libjpeg-turbo + AES-128-GCM whole file (OpenSSL) | full | 640x480 | 31.3 | – | not measured | – | – | – |

* Vivado estimate = post-route power of the whole Zynq design (PS at default activity), not a measurement: report it as an estimate, next to the measured fps.
* FPGA fps: first_contact's zero-copy run (the frame is already in the DMA buffer, as a camera writing there would leave it); the ARM rows read the frame from memory the same way.
* not measured = no meter reading and no Vivado model (ARM rows): fps only.
