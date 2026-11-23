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

## Power with simulated switching activity (SAIF from tb_nv_power, bit-exact replay)

| build | workload | events | clocks | events/clk | total W | dynamic W | confidence | nJ/event (total) | nJ/event (dynamic) |
|---|---|---|---|---|---|---|---|---|---|
| nv_top_u2_maxw1280_maxh720 | dense_v2 | 80000 | 102779 | 0.778 | 0.274 | 0.168 | Medium | 3.52 | 2.16 |
| nv_top_u2_maxw1280_maxh720 | dense_v3 | 80000 | 102779 | 0.778 | 0.277 | 0.171 | Medium | 3.56 | 2.20 |
| nv_top_u2_maxw1280_maxh720 | real_v2 | 1524 | 130409 | 0.012 | 0.259 | 0.154 | Medium | 221.63 | 131.78 |
| nv_top_u2_maxw1280_maxh720 | real_v3 | 1524 | 130409 | 0.012 | 0.259 | 0.154 | Medium | 221.63 | 131.78 |

real_*: a DVS Gesture test recording at sensor rate (the per-packet table fill dominates the clocks); dense_*: uniform synthetic events, 10 000 per ms (the datapath busy every clock). Energy per event = power x clocks x 10 ns / events.

impl: Vivado implementation strategy (NV_IMPL). fast = default directives, redone with the timing-driven ones only when 100 MHz was missed (fast+perf); its Fmax from the slack can be slightly below a perf build's.
