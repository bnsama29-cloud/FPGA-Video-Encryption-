# N2 hardware tables (Vivado, xc7z020clg400-1, post-route OOC)

| build | LUT | FF | BRAM tiles | DSP | WNS ns | Fmax MHz | auth Mev/s at Fmax | power W | power source | impl |
|---|---|---|---|---|---|---|---|---|---|---|
| nv_ascon_core_u_u1 | 994 | 715 | 0 | 0 | 3.039 | 143.7 | - | 0.125 | vectorless | fast |
| nv_ascon_core_u_u2 | 1495 | 714 | 0 | 0 | 1.664 | 120 | - | 0.18 | vectorless | fast |
| nv_feistel | 389 | 272 | 12 | 0 | 1.89 | 123.3 | - | 0.144 | vectorless | fast |
| nv_table_gen | 893 | 916 | 0 | 1 | 1.217 | 113.9 | - | 0.128 | vectorless | fast |
| nv_tag32_u2 | 1824 | 1934 | 0 | 0 | 1.787 | 121.8 | - | 0.22 | vectorless | fast |
| nv_top_u1 | 7499 | 10961 | 16.5 | 3 | 0.026 | 100.3 | 44.58 | 0.251 | vectorless | fast |
| nv_top_u2_maxw1280_maxh720 | 7997 | 10958 | 16.5 | 3 | 0.298 | 103.1 | 82.48 | 0.336 | vectorless | fast |
| nv_top_u2_maxw128_maxh128 | 7995 | 10954 | 12.5 | 3 | 0.148 | 101.5 | 81.2 | 0.329 | vectorless | fast |
| nv_top_u2_maxw346_maxh260 | 7992 | 10956 | 12.5 | 3 | 0.182 | 101.9 | 81.52 | 0.329 | vectorless | fast |
| nv_top_u2_maxw34_maxh34 | 8261 | 10894 | 4.5 | 3 | 0.116 | 101.2 | 80.96 | 0.312 | vectorless | fast |
| nv_top_u4 | 9826 | 11033 | 16.5 | 3 | -2.133 | 82.4 | 82.4 | 0.73 | vectorless | fast+perf |
| board overlay (PS + AXI DMA + nv_top U=2) | 10706 | 14442 | 18.5 | 3 | 0.382 | 104 | - | 1.9 | vectorless | bd |
No post-route reports (build did not finish): nv_ascon_core_u_u4.

impl: Vivado implementation strategy (NV_IMPL). fast = default directives, redone with the timing-driven ones only when 100 MHz was missed (fast+perf); its Fmax from the slack can be slightly below a perf build's.
