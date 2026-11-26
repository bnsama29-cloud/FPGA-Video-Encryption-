# N2 hardware tables (Vivado, xc7z020clg400-1, post-route OOC)

| build | LUT | FF | BRAM tiles | DSP | WNS ns | Fmax MHz | auth Mev/s at Fmax | power W | power source | impl |
|---|---|---|---|---|---|---|---|---|---|---|
| nv_ascon_round_dom | 2290 | 2368 | 0 | 0 | 2.094 | 126.5 | - | 0.158 | vectorless | fast |
| nv_ascon_round_reg | 462 | 648 | 0 | 0 | 5.501 | 222.3 | - | 0.121 | vectorless | fast |
| nv_feistel_walk_w1280_h720_k4 | 1046 | 1682 | 60 | 0 | 0.491 | 105.2 | - | 0.287 | vectorless | fast |
| nv_feistel_walk_w1280_h720_k8 | 1945 | 3304 | 108 | 0 | 0.502 | 105.3 | - | 0.443 | vectorless | fast |
No post-route reports (build did not finish): nv_top_u2_maxw34_maxh34.

impl: Vivado implementation strategy (NV_IMPL). fast = default directives, redone with the timing-driven ones only when 100 MHz was missed (fast+perf); its Fmax from the slack can be slightly below a perf build's.
