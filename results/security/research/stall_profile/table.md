### R1: stall profile of the encoder pipeline (Icarus, cycle-accurate)

Floor of this architecture: 1.5 cycles/pixel (4:2:0, one DCT sample per clock).

| Image | Mode | Cycles/pixel | Above floor | Most-stalled link | Stall share | Scan bytes |
|---|---|---|---|---|---|---|
| scene | E0 | 1.689 | 12.6 % | pixels in (s_axis) | 19.8 % | 2700 |
| scene | E2 | 1.689 | 12.6 % | pixels in (s_axis) | 19.8 % | 2705 |
| scene | E4 | 1.689 | 12.6 % | pixels in (s_axis) | 19.8 % | 2704 |
| noise | E0 | 1.689 | 12.6 % | pixels in (s_axis) | 19.8 % | 7407 |
| noise | E2 | 1.689 | 12.6 % | pixels in (s_axis) | 19.8 % | 7405 |
| noise | E4 | 1.689 | 12.6 % | pixels in (s_axis) | 19.8 % | 7410 |
| bars | E0 | 1.690 | 12.6 % | pixels in (s_axis) | 19.7 % | 390 |
| bars | E2 | 1.690 | 12.6 % | pixels in (s_axis) | 19.7 % | 390 |
| bars | E4 | 1.690 | 12.6 % | pixels in (s_axis) | 19.7 % | 390 |

Per-link shares for scene E0 (transfer / stall / starve, % of cycles):

| Link | Transfer | Stall | Starve |
|---|---|---|---|
| pixels in (s_axis) | 59.2 | 19.8 | 21.0 |
| colour conv -> DCT | 88.8 | 0.0 | 11.2 |
| DCT -> quantiser | 88.8 | 0.0 | 11.2 |
| quantiser -> zig-zag/RLE | 88.8 | 0.0 | 11.2 |
| RLE -> selective enc | 17.4 | 0.0 | 82.6 |
| selective enc -> Huffman | 17.4 | 0.0 | 82.6 |
| Huffman -> bit packer | 17.4 | 0.0 | 82.6 |
| bit packer -> word packer | 13.0 | 0.3 | 86.7 |
| scan out (m_axis) | 3.3 | 0.0 | 96.7 |
