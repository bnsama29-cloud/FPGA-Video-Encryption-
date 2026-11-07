# ASIC area estimate (Yosys + abc, logic synthesis only)

GE = area / area of the library's NAND2. RAMs are mapped to flip-flops (memory bits column).

| Block | library | area (um^2) | kGE | cells | memory bits |
|---|---|---|---|---|---|
| ascon_round | sky130 | 12804 | 3.41 | 1630 | 0 |
| ascon_aead128_core | sky130 | 44227 | 11.78 | 4020 | 0 |
| keystream_gen | sky130 | 50923 | 13.57 | 4534 | 0 |
| tag_unit | sky130 | 64124 | 17.08 | 5103 | 0 |
| selective_enc | sky130 | 4803 | 1.28 | 290 | 0 |
| ascon_round | nangate45 | 2385 | 2.99 | 1737 | 0 |
| ascon_aead128_core | nangate45 | 8725 | 10.93 | 5004 | 0 |
| keystream_gen | nangate45 | 10158 | 12.73 | 5194 | 0 |
| tag_unit | nangate45 | 13311 | 16.68 | 7449 | 0 |
| selective_enc | nangate45 | 986 | 1.24 | 424 | 0 |
