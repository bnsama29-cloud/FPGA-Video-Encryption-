# PYNQ-Z2 board images

Written by `scripts/publish_bitstreams.py` at commit `a7ff45d581`. Copy each `.bit` with its `.hwh` to the board (same folder). Check a copy with `python3 scripts/publish_bitstreams.py --check` (on the board: `cd /home/xilinx/fpga` first).

| File | Purpose | Clock | VERSION | Built by | Bytes | SHA-256 |
|---|---|---|---|---|---|---|
| `secure_jpeg_lanes.bit` | 2 lanes + E5, the main demo image (A1, A2, A5, A6) | 100 MHz | `0x5EC00382` | run 12 (`--steps bd_lanes`) | 4,045,769 | `dacf0fd1954b5945bad4d686787b0d1bac6a1753852589730e694bcbf1c324c0` |
| `secure_jpeg_lanes4.bit` | 4 lanes + E5, lines up to 1024 px (A1, A2, A4); --fclk 100 if 125 MHz fails | 125 MHz | `0x5EC00384` | run 12 (`--steps bd_lanes4`) | 4,045,769 | `7f1260af5daf72b0fcd923d8739414285a8e3bf9e705ad4d4d5f5dd0dee99344` |
| `secure_jpeg_lanes_tamper.bit` | 2 lanes + E5 + tamper injector (SW0/SW1/BTN0) and level buttons (BTN1-BTN3) | 100 MHz | `0x5EC00382` | run 13 (`--steps bd_tamper`) | 4,045,769 | `c6a92ab60e8e176d0a582dcd316ebf913c46a81a4e8fe78aa73440573c3be43b` |
| `secure_jpeg.bit` | single pipeline, E0-E4 (contract v2) | 100 MHz | `0x5EC00200` | run 12 (`--steps bd`) | 4,045,769 | `25cb8e7207096e944f5f5697f8c5265a55350124e6e0208a94a80d2c4c9b4f02` |
| `secure_jpeg_lanes4hd.bit` | 4 lanes, lines up to 2048 px (1920x1088) | 125 MHz | `0x5EC00384` | run 12 (`--steps bd_lanes4hd`) | 4,045,769 | `52ecb7f66f1aac74887d473238167a0f2c0748bf69e77f38967df4dbbf1f3815` |
| `secure_jpeg_lanes4yuyv.bit` | 4 lanes, camera-native YUYV input | 125 MHz | `0x5EC003C4` | run 12 (`--steps bd_lanes4yuyv`) | 4,045,769 | `d38adc96f662357211100cb6604ecec68c167938ab036d1f9d5c635790de7cac` |
