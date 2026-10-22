## Hardware results from Vivado (post-route, xc7z020clg400-1)

| Design | LUT | FF | BRAM | DSP | Clock (MHz) | WNS (ns) | Timing met | Est. fmax (MHz) | Power total / dynamic (W) |
|---|---|---|---|---|---|---|---|---|---|
| secure_jpeg_top_log_maxw9 | 4782 (9.0%) | 2908 (2.7%) | 6.5 (4.6%) | 23 (10.4%) | 100 | 0.733 | yes | 107.9 | 0.204 / 0.099 |
| secure_jpeg_top_log_maxw10 | 4871 (9.2%) | 2912 (2.7%) | 12.5 (8.9%) | 23 (10.4%) | 100 | 0.609 | yes | 106.5 | 0.211 / 0.106 |
| secure_jpeg_lanes_top_8.0ns_lanes2_log_l1 | 9458 (17.8%) | 5972 (5.6%) | 52.0 (37.1%) | 46 (20.9%) | 125 | 0.213 | yes | 128.4 | 0.448 / 0.338 |
| secure_jpeg_top_8.0ns | 4780 (9.0%) | 3178 (3.0%) | 25.5 (18.2%) | 23 (10.4%) | 125 | 0.060 | yes | 125.9 | 0.248 / 0.142 |
| overlay | 7679 (14.4%) | 7185 (6.8%) | 27.5 (19.6%) | 23 (10.4%) | 100 | 1.309 | yes | 115.1 | 1.821 / 1.679 |
| overlay_lanes | 12679 (23.8%) | 10171 (9.6%) | 54.5 (38.9%) | 46 (20.9%) | 100 | 1.082 | yes | 112.1 | 1.950 / 1.800 |
| overlay_lanes4 | 20123 (37.8%) | 14282 (13.4%) | 58.5 (41.8%) | 92 (41.8%) | 125 | 0.141 | yes | 127.2 | 2.220 / 2.061 |
| secure_jpeg_lanes_top_6.0ns_lanes2_log_l1 | 10440 (19.6%) | 6761 (6.3%) | 51.0 (36.4%) | 46 (20.9%) | 167 | -0.019 | NO | 166.1 | 0.613 / 0.499 |
| secure_jpeg_lanes_top_6.0ns_lanes4_log_l2_log_maxw10 | 18141 (34.1%) | 10917 (10.3%) | 54.0 (38.6%) | 92 (41.8%) | 167 | -0.182 | NO | 161.8 | 0.943 / 0.822 |
| secure_jpeg_lanes_top_6.667ns_lanes2_log_l1 | 10301 (19.4%) | 6670 (6.3%) | 51.0 (36.4%) | 46 (20.9%) | 150 | 0.003 | yes | 150.1 | 0.562 / 0.449 |
| secure_jpeg_lanes_top_6.667ns_lanes4_log_l2_log_maxw10 | 17887 (33.6%) | 10803 (10.2%) | 54.0 (38.6%) | 92 (41.8%) | 150 | 0.011 | yes | 150.2 | 0.855 / 0.736 |
| secure_jpeg_lanes_top_lanes2_log_l1 | 10099 (19.0%) | 6648 (6.2%) | 52.0 (37.1%) | 46 (20.9%) | 100 | 1.056 | yes | 111.8 | 0.410 / 0.300 |
| secure_jpeg_lanes_top_lanes4_log_l2_log_maxw10 | 17515 (32.9%) | 10759 (10.1%) | 56.0 (40.0%) | 92 (41.8%) | 100 | 1.020 | yes | 111.4 | 0.606 / 0.492 |
| secure_jpeg_lanes_top_lanes4_log_l2_log_maxw10_nbuf1 | 17492 (32.9%) | 10723 (10.1%) | 32.0 (22.9%) | 92 (41.8%) | 100 | 0.414 | yes | 104.3 | 0.578 / 0.466 |
| secure_jpeg_lanes_top_lanes4_log_l2_log_maxw10_pixfmt1 | 15172 (28.5%) | 9390 (8.8%) | 60.0 (42.9%) | 92 (41.8%) | 100 | 0.985 | yes | 110.9 | 0.570 / 0.456 |
| secure_jpeg_lanes_top_lanes4_log_l2_log_maxw11_nbuf1 | 17511 (32.9%) | 10755 (10.1%) | 56.0 (40.0%) | 92 (41.8%) | 100 | 1.011 | yes | 111.2 | 0.607 / 0.493 |
| secure_jpeg_top | 5043 (9.5%) | 3506 (3.3%) | 25.5 (18.2%) | 23 (10.4%) | 100 | 1.524 | yes | 118.0 | 0.249 / 0.143 |
| secure_jpeg_top_6.0ns | 5181 (9.7%) | 3548 (3.3%) | 25.0 (17.9%) | 23 (10.4%) | 167 | -0.015 | NO | 166.3 | 0.345 / 0.237 |
| secure_jpeg_top_6.667ns | 5126 (9.6%) | 3512 (3.3%) | 25.0 (17.9%) | 23 (10.4%) | 150 | 0.270 | yes | 156.3 | 0.318 / 0.211 |
| overlay_lanes4hd | 20104 (37.8%) | 14278 (13.4%) | 58.5 (41.8%) | 92 (41.8%) | 125 | 0.032 | yes | 125.5 | 2.226 / 2.067 |
| overlay_lanes4yuyv | 17780 (33.4%) | 12945 (12.2%) | 62.5 (44.6%) | 92 (41.8%) | 125 | 0.197 | yes | 128.2 | 2.282 / 2.120 |

Power is Vivado's vectorless estimate (confidence shown in power.txt); measure the board for real power.
Est. fmax = 1000 / (period - WNS): a single-run estimate, confirm by re-running at that period.

### Power with simulated switching activity (SAIF from the XSim testbench)

| Design | Run | Total (W) | Dynamic (W) | Vectorless dynamic (W) | Confidence | Internal nodes |
|---|---|---|---|---|---|---|
| secure_jpeg_lanes_top_lanes2_log_l1 | v3_E2 | 0.345 | 0.235 | 0.300 | Medium | Medium: User specified less than 25% of internal nodes |
| secure_jpeg_lanes_top_lanes2_log_l1 | v3_E5 | 0.344 | 0.235 | 0.300 | Medium | Medium: User specified less than 25% of internal nodes |
| secure_jpeg_lanes_top_lanes4_log_l2_log_maxw10 | v3l4_E2 | 0.492 | 0.380 | 0.492 | Medium | Medium: User specified less than 25% of internal nodes |
| secure_jpeg_lanes_top_lanes4_log_l2_log_maxw10 | v3l4_E5 | 0.493 | 0.381 | 0.492 | Medium | Medium: User specified less than 25% of internal nodes |
| secure_jpeg_top | v2_E0 | 0.229 | 0.123 | 0.143 | Medium | Medium: User specified less than 25% of internal nodes |
| secure_jpeg_top | v2_E2 | 0.230 | 0.125 | 0.143 | Medium | Medium: User specified less than 25% of internal nodes |
| secure_jpeg_top | v2_E4 | 0.230 | 0.125 | 0.143 | Medium | Medium: User specified less than 25% of internal nodes |

Run = contract (v2: secure_jpeg_top, v3: 2 lanes) and mode; activity of one scene frame (vivado/run_vivado_day.py --steps power). Activity from RTL simulation matches only the nets whose names survive synthesis; the rest keep Vivado's default. Still an estimate: the board measurement (GUIDE A4) is the measured number.

### Worst setup paths (block of source -> destination)

| Design | Clock (MHz) | Paths (slack ns: from -> to) |
|---|---|---|
| secure_jpeg_top_log_maxw9 | 100 | +0.733: u_conv -> u_conv; +0.742: u_rle -> u_ks; +0.742: u_rle -> u_ks; +0.742: u_rle -> u_ks; +0.742: u_rle -> u_ks |
| secure_jpeg_top_log_maxw10 | 100 | +0.609: u_rle -> u_ks; +0.609: u_rle -> u_ks; +0.609: u_rle -> u_ks; +0.609: u_rle -> u_ks; +0.609: u_rle -> u_ks |
| secure_jpeg_lanes_top_8.0ns_lanes2_log_l1 | 125 | +0.213: g_lane[0].u_lane -> g_lane[0].u_lane; +0.213: g_lane[0].u_lane -> g_lane[0].u_lane; +0.213: g_lane[0].u_lane -> g_lane[0].u_lane; +0.213: g_lane[0].u_lane -> g_lane[0].u_lane; +0.277: mode_l_reg[0] -> g_lane[1].u_lane |
| secure_jpeg_top_8.0ns | 125 | +0.060: u_pack -> u_pack; +0.147: u_rle -> u_ks; +0.147: u_rle -> u_ks; +0.147: u_rle -> u_ks; +0.147: u_rle -> u_ks |
| overlay | 100 | +1.309: system_i -> system_i; +1.541: system_i -> system_i; +1.646: system_i -> system_i; +1.646: system_i -> system_i; +1.646: system_i -> system_i |
| overlay_lanes | 100 | +1.082: system_i -> system_i; +1.186: system_i -> system_i; +1.224: system_i -> system_i; +1.276: system_i -> system_i; +1.276: system_i -> system_i |
| overlay_lanes4 | 125 | +0.141: system_i -> system_i; +0.141: system_i -> system_i; +0.141: system_i -> system_i; +0.141: system_i -> system_i; +0.151: system_i -> system_i |
| secure_jpeg_lanes_top_6.0ns_lanes2_log_l1 | 167 | -0.019: g_lane[1].u_lane -> g_lane[1].u_lane; -0.002: g_lane[1].u_lane -> g_lane[1].u_lane; +0.006: g_lane[0].u_lane -> g_lane[0].u_lane; +0.006: g_lane[1].u_lane -> g_lane[1].u_lane; +0.006: g_lane[1].u_lane -> g_lane[1].u_lane |
| secure_jpeg_lanes_top_6.0ns_lanes4_log_l2_log_maxw10 | 167 | -0.182: g_lane[3].u_lane -> g_lane[3].u_lane; -0.101: g_lane[0].u_lane -> g_lane[0].u_lane; -0.086: g_lane[1].u_lane -> g_lane[1].u_lane; -0.063: g_lane[2].u_lane -> g_lane[2].u_lane; -0.043: u_regs -> g_lane[2].u_lane |
| secure_jpeg_lanes_top_6.667ns_lanes2_log_l1 | 150 | +0.003: g_lane[1].u_lane -> g_lane[1].u_lane; +0.006: g_lane[0].u_lane -> g_lane[0].u_lane; +0.055: g_lane[1].u_lane -> g_lane[1].u_lane; +0.096: g_lane[0].u_lane -> g_lane[0].u_lane; +0.099: g_lane[1].u_lane -> g_lane[1].u_lane |
| secure_jpeg_lanes_top_6.667ns_lanes4_log_l2_log_maxw10 | 150 | +0.011: g_lane[2].u_lane -> g_lane[2].u_lane; +0.019: g_lane[3].u_lane -> g_lane[3].u_lane; +0.019: g_lane[3].u_lane -> g_lane[3].u_lane; +0.019: g_lane[3].u_lane -> g_lane[3].u_lane; +0.019: g_lane[3].u_lane -> g_lane[3].u_lane |
| secure_jpeg_lanes_top_lanes2_log_l1 | 100 | +1.056: g_lane[1].u_lane -> g_lane[1].u_lane; +1.059: g_lane[1].u_lane -> g_lane[1].u_lane; +1.135: g_lane[1].u_lane -> g_lane[1].u_lane; +1.231: g_lane[1].u_lane -> g_lane[1].u_lane; +1.238: g_lane[1].u_lane -> g_lane[1].u_lane |
| secure_jpeg_lanes_top_lanes4_log_l2_log_maxw10 | 100 | +1.020: u_regs -> u_kseg; +1.020: u_regs -> u_kseg; +1.020: u_regs -> u_kseg; +1.043: u_regs -> u_kseg; +1.050: u_regs -> u_kseg |
| secure_jpeg_lanes_top_lanes4_log_l2_log_maxw10_nbuf1 | 100 | +0.414: u_tag -> u_tag; +0.434: u_tag -> u_tag; +0.739: u_tag -> u_tag; +0.759: u_tag -> u_tag; +0.813: u_tag -> u_tag |
| secure_jpeg_lanes_top_lanes4_log_l2_log_maxw10_pixfmt1 | 100 | +0.985: (top) -> g_lane[0].u_lane; +0.985: (top) -> g_lane[0].u_lane; +1.067: g_lane[1].u_lane -> g_lane[1].u_lane; +1.074: g_lane[1].u_lane -> g_lane[1].u_lane; +1.086: g_lane[1].u_lane -> g_lane[1].u_lane |
| secure_jpeg_lanes_top_lanes4_log_l2_log_maxw11_nbuf1 | 100 | +1.011: u_regs -> u_tag; +1.156: u_regs -> u_tag; +1.156: u_regs -> u_tag; +1.156: u_regs -> u_tag; +1.156: u_regs -> u_tag |
| secure_jpeg_top | 100 | +1.524: u_regs -> u_ks; +1.524: u_regs -> u_ks; +1.606: u_regs -> u_ks; +1.606: u_regs -> u_ks; +1.606: u_regs -> u_ks |
| secure_jpeg_top_6.0ns | 167 | -0.015: u_conv -> u_dct; +0.041: u_conv -> u_dct; +0.053: u_conv -> u_dct; +0.053: u_conv -> u_dct; +0.056: u_conv -> u_dct |
| secure_jpeg_top_6.667ns | 150 | +0.270: u_enc -> u_huff; +0.277: u_enc -> u_huff; +0.283: u_enc -> u_huff; +0.300: u_pack -> u_pack; +0.309: u_conv -> u_dct |
| overlay_lanes4hd | 125 | +0.032: system_i -> system_i; +0.160: system_i -> system_i; +0.161: system_i -> system_i; +0.173: system_i -> system_i; +0.173: system_i -> system_i |
| overlay_lanes4yuyv | 125 | +0.197: system_i -> system_i; +0.197: system_i -> system_i; +0.197: system_i -> system_i; +0.303: system_i -> system_i; +0.405: system_i -> system_i |

### Resource breakdown: secure_jpeg_top_log_maxw9

| Block | Module | LUT | FF | BRAM | DSP |
|---|---|---|---|---|---|
| secure_jpeg_top | (top) | 4782 | 2908 | 6.5 | 23 |
| &nbsp;&nbsp;(secure_jpeg_top) | (top) | 0 | 5 | 0 | 0 |
| &nbsp;&nbsp;u_conv | rgb2ycbcr_block | 508 | 172 | 6 | 0 |
| &nbsp;&nbsp;u_dct | dct8x8 | 809 | 70 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_cols | dct_stage__parameterized0 | 508 | 37 | 0 | 11 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rows | dct_stage | 301 | 33 | 0 | 11 |
| &nbsp;&nbsp;u_enc | selective_enc | 82 | 24 | 0 | 0 |
| &nbsp;&nbsp;u_huff | huffman_enc | 268 | 34 | 0 | 0 |
| &nbsp;&nbsp;u_ks | keystream_gen | 949 | 851 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_ks) | keystream_gen | 89 | 266 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core_0 | 860 | 585 | 0 | 0 |
| &nbsp;&nbsp;u_pack | bit_packer | 211 | 84 | 0 | 0 |
| &nbsp;&nbsp;u_regs | axil_regs | 348 | 355 | 0 | 0 |
| &nbsp;&nbsp;u_rle | zigzag_rle | 219 | 110 | 0 | 0 |
| &nbsp;&nbsp;u_tag | tag_unit | 1344 | 1072 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_tag) | tag_unit | 375 | 614 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core | 969 | 458 | 0 | 0 |
| &nbsp;&nbsp;u_words | scan_word_packer | 22 | 95 | 0 | 0 |

### Resource breakdown: secure_jpeg_top_log_maxw10

| Block | Module | LUT | FF | BRAM | DSP |
|---|---|---|---|---|---|
| secure_jpeg_top | (top) | 4871 | 2912 | 12.5 | 23 |
| &nbsp;&nbsp;(secure_jpeg_top) | (top) | 0 | 5 | 0 | 0 |
| &nbsp;&nbsp;u_conv | rgb2ycbcr_block | 600 | 177 | 12 | 0 |
| &nbsp;&nbsp;u_dct | dct8x8 | 807 | 69 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_cols | dct_stage__parameterized0 | 506 | 36 | 0 | 11 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rows | dct_stage | 301 | 33 | 0 | 11 |
| &nbsp;&nbsp;u_enc | selective_enc | 82 | 24 | 0 | 0 |
| &nbsp;&nbsp;u_huff | huffman_enc | 268 | 34 | 0 | 0 |
| &nbsp;&nbsp;u_ks | keystream_gen | 949 | 851 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_ks) | keystream_gen | 89 | 266 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core_0 | 860 | 585 | 0 | 0 |
| &nbsp;&nbsp;u_pack | bit_packer | 211 | 84 | 0 | 0 |
| &nbsp;&nbsp;u_regs | axil_regs | 348 | 355 | 0 | 0 |
| &nbsp;&nbsp;u_rle | zigzag_rle | 219 | 110 | 0 | 0 |
| &nbsp;&nbsp;u_tag | tag_unit | 1344 | 1072 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_tag) | tag_unit | 375 | 614 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core | 969 | 458 | 0 | 0 |
| &nbsp;&nbsp;u_words | scan_word_packer | 22 | 95 | 0 | 0 |

### Resource breakdown: secure_jpeg_lanes_top_8.0ns_lanes2_log_l1

| Block | Module | LUT | FF | BRAM | DSP |
|---|---|---|---|---|---|
| secure_jpeg_lanes_top | (top) | 9458 | 5972 | 52 | 46 |
| &nbsp;&nbsp;(secure_jpeg_lanes_top) | (top) | 4 | 41 | 0 | 0 |
| &nbsp;&nbsp;g_lane[0].u_lane | encoder_lane | 2957 | 1739 | 26 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle_10 | 274 | 110 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_conv | rgb2ycbcr_2px_2 | 308 | 451 | 25 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8_3 | 800 | 69 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc_4 | 82 | 24 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc_6 | 226 | 34 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen_7 | 966 | 851 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer_8 | 218 | 84 | 0 | 0 |
| &nbsp;&nbsp;g_lane[1].u_lane | encoder_lane__parameterized0 | 3740 | 1824 | 26 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle | 274 | 110 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_conv | rgb2ycbcr_2px | 1090 | 535 | 25 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8 | 803 | 69 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc | 82 | 24 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc | 222 | 34 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen | 965 | 851 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer | 214 | 84 | 0 | 0 |
| &nbsp;&nbsp;u_kseg | kseg_unit | 790 | 591 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_kseg) | kseg_unit | 4 | 133 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core_0 | 786 | 458 | 0 | 0 |
| &nbsp;&nbsp;u_merge | segment_merger | 56 | 38 | 0 | 0 |
| &nbsp;&nbsp;u_regs | axil_regs | 552 | 453 | 0 | 0 |
| &nbsp;&nbsp;u_tag | tag_unit | 1337 | 1191 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_tag) | tag_unit | 359 | 605 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core | 978 | 586 | 0 | 0 |
| &nbsp;&nbsp;u_words | scan_word_packer | 24 | 95 | 0 | 0 |

### Resource breakdown: secure_jpeg_top_8.0ns

| Block | Module | LUT | FF | BRAM | DSP |
|---|---|---|---|---|---|
| secure_jpeg_top | (top) | 4780 | 3178 | 25.5 | 23 |
| &nbsp;&nbsp;(secure_jpeg_top) | (top) | 0 | 5 | 0 | 0 |
| &nbsp;&nbsp;u_conv | rgb2ycbcr_block | 428 | 347 | 25 | 0 |
| &nbsp;&nbsp;u_dct | dct8x8 | 806 | 69 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_cols | dct_stage__parameterized0 | 505 | 36 | 0 | 11 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rows | dct_stage | 301 | 33 | 0 | 11 |
| &nbsp;&nbsp;u_enc | selective_enc | 82 | 24 | 0 | 0 |
| &nbsp;&nbsp;u_huff | huffman_enc | 278 | 34 | 0 | 0 |
| &nbsp;&nbsp;u_ks | keystream_gen | 949 | 851 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_ks) | keystream_gen | 89 | 266 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core_0 | 860 | 585 | 0 | 0 |
| &nbsp;&nbsp;u_pack | bit_packer | 221 | 84 | 0 | 0 |
| &nbsp;&nbsp;u_regs | axil_regs | 392 | 451 | 0 | 0 |
| &nbsp;&nbsp;u_rle | zigzag_rle | 221 | 110 | 0 | 0 |
| &nbsp;&nbsp;u_tag | tag_unit | 1359 | 1072 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_tag) | tag_unit | 389 | 614 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core | 970 | 458 | 0 | 0 |
| &nbsp;&nbsp;u_words | scan_word_packer | 20 | 95 | 0 | 0 |

### Resource breakdown: overlay

| Block | Module | LUT | FF | BRAM | DSP |
|---|---|---|---|---|---|
| system_wrapper | (top) | 7679 | 7185 | 27.5 | 23 |
| &nbsp;&nbsp;system_i | system | 7679 | 7185 | 27.5 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;sjpeg | system_sjpeg_0 | 4996 | 3506 | 25.5 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;axi_mem_intercon | system_axi_mem_intercon_0 | 812 | 1007 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;dma | system_dma_0 | 1339 | 1963 | 2 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;ps7_axi_periph | system_ps7_axi_periph_0 | 516 | 675 | 0 | 0 |

### Resource breakdown: overlay_lanes

| Block | Module | LUT | FF | BRAM | DSP |
|---|---|---|---|---|---|
| system_wrapper | (top) | 12679 | 10171 | 54.5 | 46 |
| &nbsp;&nbsp;system_i | system | 12679 | 10171 | 54.5 | 46 |
| &nbsp;&nbsp;&nbsp;&nbsp;sjpeg | system_sjpeg_0 | 10097 | 6648 | 52 | 46 |
| &nbsp;&nbsp;&nbsp;&nbsp;axi_mem_intercon | system_axi_mem_intercon_0 | 656 | 781 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;dma | system_dma_0 | 1394 | 2033 | 2.5 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;ps7_axi_periph | system_ps7_axi_periph_0 | 515 | 675 | 0 | 0 |

### Resource breakdown: overlay_lanes4

| Block | Module | LUT | FF | BRAM | DSP |
|---|---|---|---|---|---|
| system_wrapper | (top) | 20123 | 14282 | 58.5 | 92 |
| &nbsp;&nbsp;system_i | system | 20123 | 14282 | 58.5 | 92 |
| &nbsp;&nbsp;&nbsp;&nbsp;sjpeg | system_sjpeg_0 | 17533 | 10759 | 56 | 92 |
| &nbsp;&nbsp;&nbsp;&nbsp;axi_mem_intercon | system_axi_mem_intercon_0 | 661 | 781 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;dma | system_dma_0 | 1398 | 2033 | 2.5 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;ps7_axi_periph | system_ps7_axi_periph_0 | 515 | 675 | 0 | 0 |

### Resource breakdown: secure_jpeg_lanes_top_6.0ns_lanes2_log_l1

| Block | Module | LUT | FF | BRAM | DSP |
|---|---|---|---|---|---|
| secure_jpeg_lanes_top | (top) | 10440 | 6761 | 51 | 46 |
| &nbsp;&nbsp;(secure_jpeg_lanes_top) | (top) | 89 | 58 | 0 | 0 |
| &nbsp;&nbsp;g_lane[0].u_lane | encoder_lane | 3427 | 2129 | 25.5 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle_10 | 424 | 240 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;g_rgb.u_conv | rgb2ycbcr_2px_2 | 309 | 451 | 25 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8_3 | 803 | 86 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc_4 | 161 | 135 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc_6 | 330 | 38 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen_7 | 935 | 862 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer_8 | 311 | 182 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_quant | quantiser_9 | 90 | 53 | 0 | 1 |
| &nbsp;&nbsp;g_lane[1].u_lane | encoder_lane__parameterized0 | 4225 | 2205 | 25.5 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;(g_lane[1].u_lane) | encoder_lane__parameterized0 | 50 | 46 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;g_rgb.u_conv | rgb2ycbcr_2px | 1101 | 536 | 25 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8 | 808 | 78 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc | 161 | 132 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc | 329 | 37 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen | 932 | 863 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer | 308 | 182 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_quant | quantiser | 90 | 53 | 0 | 1 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle | 424 | 241 | 0 | 0 |
| &nbsp;&nbsp;u_kseg | kseg_unit | 790 | 591 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_kseg) | kseg_unit | 4 | 133 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core_0 | 786 | 458 | 0 | 0 |
| &nbsp;&nbsp;u_merge | segment_merger | 58 | 38 | 0 | 0 |
| &nbsp;&nbsp;u_regs | axil_regs | 481 | 453 | 0 | 0 |
| &nbsp;&nbsp;u_tag | tag_unit | 1347 | 1192 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_tag) | tag_unit | 361 | 606 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core | 986 | 586 | 0 | 0 |
| &nbsp;&nbsp;u_words | scan_word_packer | 24 | 95 | 0 | 0 |

### Resource breakdown: secure_jpeg_lanes_top_6.0ns_lanes4_log_l2_log_maxw10

| Block | Module | LUT | FF | BRAM | DSP |
|---|---|---|---|---|---|
| secure_jpeg_lanes_top | (top) | 18141 | 10917 | 54 | 92 |
| &nbsp;&nbsp;(secure_jpeg_lanes_top) | (top) | 87 | 59 | 0 | 0 |
| &nbsp;&nbsp;g_lane[0].u_lane | encoder_lane | 3423 | 2094 | 13.5 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle_40 | 425 | 241 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;g_rgb.u_conv | rgb2ycbcr_2px_32 | 310 | 446 | 13 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8_33 | 805 | 69 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc_34 | 161 | 129 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc_36 | 330 | 35 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen_37 | 932 | 859 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer_38 | 306 | 182 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_quant | quantiser_39 | 90 | 53 | 0 | 1 |
| &nbsp;&nbsp;g_lane[1].u_lane | encoder_lane__parameterized0 | 3423 | 2127 | 13.5 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;(g_lane[1].u_lane) | encoder_lane__parameterized0 | 106 | 45 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;g_rgb.u_conv | rgb2ycbcr_2px_17 | 316 | 445 | 13 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8_18 | 725 | 109 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc_19 | 162 | 136 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc_21 | 330 | 36 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen_22 | 943 | 860 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer_23 | 300 | 182 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_quant | quantiser_24 | 91 | 36 | 0 | 1 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle_25 | 425 | 241 | 0 | 0 |
| &nbsp;&nbsp;g_lane[2].u_lane | encoder_lane__parameterized1 | 3413 | 2074 | 13.5 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle_10 | 427 | 239 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;g_rgb.u_conv | rgb2ycbcr_2px_2 | 304 | 445 | 13 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8_3 | 804 | 68 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc_4 | 161 | 129 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc_6 | 326 | 34 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen_7 | 933 | 859 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer_8 | 298 | 183 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_quant | quantiser_9 | 90 | 36 | 0 | 1 |
| &nbsp;&nbsp;g_lane[3].u_lane | encoder_lane__parameterized2 | 4994 | 2192 | 13.5 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;(g_lane[3].u_lane) | encoder_lane__parameterized2 | 107 | 45 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;g_rgb.u_conv | rgb2ycbcr_2px | 1897 | 552 | 13 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8 | 723 | 69 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc | 160 | 133 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc | 327 | 39 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen | 943 | 859 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer | 299 | 182 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_quant | quantiser | 91 | 36 | 0 | 1 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle | 422 | 240 | 0 | 0 |
| &nbsp;&nbsp;u_kseg | kseg_unit | 790 | 591 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_kseg) | kseg_unit | 4 | 133 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core_0 | 786 | 458 | 0 | 0 |
| &nbsp;&nbsp;u_merge | segment_merger | 74 | 39 | 0 | 0 |
| &nbsp;&nbsp;u_regs | axil_regs | 569 | 453 | 0 | 0 |
| &nbsp;&nbsp;u_tag | tag_unit | 1347 | 1193 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_tag) | tag_unit | 363 | 607 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core | 984 | 586 | 0 | 0 |
| &nbsp;&nbsp;u_words | scan_word_packer | 24 | 95 | 0 | 0 |

### Resource breakdown: secure_jpeg_lanes_top_6.667ns_lanes2_log_l1

| Block | Module | LUT | FF | BRAM | DSP |
|---|---|---|---|---|---|
| secure_jpeg_lanes_top | (top) | 10301 | 6670 | 51 | 46 |
| &nbsp;&nbsp;(secure_jpeg_lanes_top) | (top) | 78 | 58 | 0 | 0 |
| &nbsp;&nbsp;g_lane[0].u_lane | encoder_lane | 3367 | 2081 | 25.5 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle_10 | 421 | 239 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;g_rgb.u_conv | rgb2ycbcr_2px_2 | 307 | 451 | 25 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8_3 | 804 | 68 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc_4 | 148 | 129 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc_6 | 320 | 36 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen_7 | 931 | 858 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer_8 | 282 | 182 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_quant | quantiser_9 | 90 | 36 | 0 | 1 |
| &nbsp;&nbsp;g_lane[1].u_lane | encoder_lane__parameterized0 | 4171 | 2163 | 25.5 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;(g_lane[1].u_lane) | encoder_lane__parameterized0 | 52 | 46 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;g_rgb.u_conv | rgb2ycbcr_2px | 1091 | 535 | 25 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8 | 805 | 69 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc | 154 | 127 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc | 324 | 34 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen | 931 | 857 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer | 281 | 182 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_quant | quantiser | 90 | 36 | 0 | 1 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle | 423 | 240 | 0 | 0 |
| &nbsp;&nbsp;u_kseg | kseg_unit | 790 | 591 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_kseg) | kseg_unit | 4 | 133 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core_0 | 786 | 458 | 0 | 0 |
| &nbsp;&nbsp;u_merge | segment_merger | 57 | 38 | 0 | 0 |
| &nbsp;&nbsp;u_regs | axil_regs | 477 | 453 | 0 | 0 |
| &nbsp;&nbsp;u_tag | tag_unit | 1337 | 1191 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_tag) | tag_unit | 360 | 605 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core | 977 | 586 | 0 | 0 |
| &nbsp;&nbsp;u_words | scan_word_packer | 24 | 95 | 0 | 0 |

### Resource breakdown: secure_jpeg_lanes_top_6.667ns_lanes4_log_l2_log_maxw10

| Block | Module | LUT | FF | BRAM | DSP |
|---|---|---|---|---|---|
| secure_jpeg_lanes_top | (top) | 17887 | 10803 | 54 | 92 |
| &nbsp;&nbsp;(secure_jpeg_lanes_top) | (top) | 77 | 59 | 0 | 0 |
| &nbsp;&nbsp;g_lane[0].u_lane | encoder_lane | 3357 | 2067 | 13.5 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle_40 | 420 | 239 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;g_rgb.u_conv | rgb2ycbcr_2px_32 | 299 | 446 | 13 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8_33 | 804 | 69 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc_34 | 148 | 120 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc_36 | 320 | 36 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen_37 | 931 | 859 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer_38 | 282 | 182 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_quant | quantiser_39 | 90 | 36 | 0 | 1 |
| &nbsp;&nbsp;g_lane[1].u_lane | encoder_lane__parameterized0 | 3367 | 2062 | 13.5 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;(g_lane[1].u_lane) | encoder_lane__parameterized0 | 106 | 45 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;g_rgb.u_conv | rgb2ycbcr_2px_17 | 305 | 445 | 13 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8_18 | 724 | 68 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc_19 | 152 | 120 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc_21 | 322 | 34 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen_22 | 939 | 857 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer_23 | 282 | 182 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_quant | quantiser_24 | 91 | 36 | 0 | 1 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle_25 | 421 | 238 | 0 | 0 |
| &nbsp;&nbsp;g_lane[2].u_lane | encoder_lane__parameterized1 | 3367 | 2090 | 13.5 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle_10 | 424 | 240 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;g_rgb.u_conv | rgb2ycbcr_2px_2 | 297 | 445 | 13 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8_3 | 803 | 86 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc_4 | 150 | 128 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc_6 | 324 | 35 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen_7 | 932 | 857 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer_8 | 280 | 182 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_quant | quantiser_9 | 90 | 36 | 0 | 1 |
| &nbsp;&nbsp;g_lane[3].u_lane | encoder_lane__parameterized2 | 4934 | 2156 | 13.5 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;(g_lane[3].u_lane) | encoder_lane__parameterized2 | 106 | 45 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;g_rgb.u_conv | rgb2ycbcr_2px | 1875 | 529 | 13 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8 | 720 | 69 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc | 151 | 125 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc | 319 | 34 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen | 940 | 860 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer | 287 | 182 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_quant | quantiser | 91 | 36 | 0 | 1 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle | 420 | 239 | 0 | 0 |
| &nbsp;&nbsp;u_kseg | kseg_unit | 790 | 591 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_kseg) | kseg_unit | 4 | 133 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core_0 | 786 | 458 | 0 | 0 |
| &nbsp;&nbsp;u_merge | segment_merger | 70 | 39 | 0 | 0 |
| &nbsp;&nbsp;u_regs | axil_regs | 565 | 453 | 0 | 0 |
| &nbsp;&nbsp;u_tag | tag_unit | 1343 | 1191 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_tag) | tag_unit | 363 | 605 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core | 980 | 586 | 0 | 0 |
| &nbsp;&nbsp;u_words | scan_word_packer | 24 | 95 | 0 | 0 |

### Resource breakdown: secure_jpeg_lanes_top_lanes2_log_l1

| Block | Module | LUT | FF | BRAM | DSP |
|---|---|---|---|---|---|
| secure_jpeg_lanes_top | (top) | 10099 | 6648 | 52 | 46 |
| &nbsp;&nbsp;(secure_jpeg_lanes_top) | (top) | 75 | 58 | 0 | 0 |
| &nbsp;&nbsp;g_lane[0].u_lane | encoder_lane | 3272 | 2068 | 26 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle_10 | 421 | 238 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;g_rgb.u_conv | rgb2ycbcr_2px_2 | 301 | 451 | 25 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8_3 | 799 | 68 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc_4 | 143 | 120 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc_6 | 314 | 34 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen_7 | 928 | 857 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer_8 | 278 | 182 | 0 | 0 |
| &nbsp;&nbsp;g_lane[1].u_lane | encoder_lane__parameterized0 | 4074 | 2154 | 26 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;(g_lane[1].u_lane) | encoder_lane__parameterized0 | 51 | 46 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;g_rgb.u_conv | rgb2ycbcr_2px | 1087 | 535 | 25 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8 | 803 | 69 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc | 144 | 120 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc | 314 | 34 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen | 929 | 857 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer | 277 | 182 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle | 422 | 238 | 0 | 0 |
| &nbsp;&nbsp;u_kseg | kseg_unit | 790 | 591 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_kseg) | kseg_unit | 4 | 133 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core_0 | 786 | 458 | 0 | 0 |
| &nbsp;&nbsp;u_merge | segment_merger | 57 | 38 | 0 | 0 |
| &nbsp;&nbsp;u_regs | axil_regs | 475 | 453 | 0 | 0 |
| &nbsp;&nbsp;u_tag | tag_unit | 1336 | 1191 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_tag) | tag_unit | 359 | 605 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core | 977 | 586 | 0 | 0 |
| &nbsp;&nbsp;u_words | scan_word_packer | 24 | 95 | 0 | 0 |

### Resource breakdown: secure_jpeg_lanes_top_lanes4_log_l2_log_maxw10

| Block | Module | LUT | FF | BRAM | DSP |
|---|---|---|---|---|---|
| secure_jpeg_lanes_top | (top) | 17515 | 10759 | 56 | 92 |
| &nbsp;&nbsp;(secure_jpeg_lanes_top) | (top) | 75 | 59 | 0 | 0 |
| &nbsp;&nbsp;g_lane[0].u_lane | encoder_lane | 3272 | 2061 | 14 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle_40 | 421 | 238 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;g_rgb.u_conv | rgb2ycbcr_2px_32 | 297 | 445 | 13 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8_33 | 804 | 69 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc_34 | 143 | 120 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc_36 | 315 | 34 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen_37 | 928 | 857 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer_38 | 278 | 182 | 0 | 0 |
| &nbsp;&nbsp;g_lane[1].u_lane | encoder_lane__parameterized0 | 3272 | 2062 | 14 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;(g_lane[1].u_lane) | encoder_lane__parameterized0 | 106 | 45 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;g_rgb.u_conv | rgb2ycbcr_2px_17 | 301 | 445 | 13 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8_18 | 721 | 68 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc_19 | 143 | 120 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc_21 | 314 | 34 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen_22 | 939 | 857 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer_23 | 280 | 182 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle_25 | 420 | 238 | 0 | 0 |
| &nbsp;&nbsp;g_lane[2].u_lane | encoder_lane__parameterized1 | 3277 | 2061 | 14 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle_10 | 421 | 238 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;g_rgb.u_conv | rgb2ycbcr_2px_2 | 296 | 445 | 13 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8_3 | 803 | 68 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc_4 | 144 | 120 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc_6 | 314 | 34 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen_7 | 929 | 857 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer_8 | 276 | 182 | 0 | 0 |
| &nbsp;&nbsp;g_lane[3].u_lane | encoder_lane__parameterized2 | 4842 | 2147 | 14 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;(g_lane[3].u_lane) | encoder_lane__parameterized2 | 106 | 45 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;g_rgb.u_conv | rgb2ycbcr_2px | 1867 | 529 | 13 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8 | 721 | 69 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc | 143 | 120 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc | 315 | 34 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen | 939 | 857 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer | 280 | 182 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle | 421 | 238 | 0 | 0 |
| &nbsp;&nbsp;u_kseg | kseg_unit | 790 | 591 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_kseg) | kseg_unit | 4 | 133 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core_0 | 786 | 458 | 0 | 0 |
| &nbsp;&nbsp;u_merge | segment_merger | 69 | 39 | 0 | 0 |
| &nbsp;&nbsp;u_regs | axil_regs | 560 | 453 | 0 | 0 |
| &nbsp;&nbsp;u_tag | tag_unit | 1339 | 1191 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_tag) | tag_unit | 362 | 605 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core | 977 | 586 | 0 | 0 |
| &nbsp;&nbsp;u_words | scan_word_packer | 24 | 95 | 0 | 0 |

### Resource breakdown: secure_jpeg_lanes_top_lanes4_log_l2_log_maxw10_nbuf1

| Block | Module | LUT | FF | BRAM | DSP |
|---|---|---|---|---|---|
| secure_jpeg_lanes_top | (top) | 17492 | 10723 | 32 | 92 |
| &nbsp;&nbsp;(secure_jpeg_lanes_top) | (top) | 75 | 59 | 0 | 0 |
| &nbsp;&nbsp;g_lane[0].u_lane | encoder_lane | 3259 | 2052 | 8 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle_40 | 421 | 238 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;g_rgb.u_conv | rgb2ycbcr_2px_32 | 286 | 436 | 7 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8_33 | 804 | 69 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc_34 | 143 | 120 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc_36 | 314 | 34 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen_37 | 928 | 857 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer_38 | 278 | 182 | 0 | 0 |
| &nbsp;&nbsp;g_lane[1].u_lane | encoder_lane__parameterized0 | 3268 | 2053 | 8 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;(g_lane[1].u_lane) | encoder_lane__parameterized0 | 106 | 45 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;g_rgb.u_conv | rgb2ycbcr_2px_17 | 290 | 436 | 7 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8_18 | 726 | 68 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc_19 | 142 | 120 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc_21 | 315 | 34 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen_22 | 938 | 857 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer_23 | 281 | 182 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle_25 | 420 | 238 | 0 | 0 |
| &nbsp;&nbsp;g_lane[2].u_lane | encoder_lane__parameterized1 | 3278 | 2053 | 8 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle_10 | 421 | 238 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;g_rgb.u_conv | rgb2ycbcr_2px_2 | 292 | 436 | 7 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8_3 | 809 | 69 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc_4 | 144 | 120 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc_6 | 315 | 34 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen_7 | 928 | 857 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer_8 | 277 | 182 | 0 | 0 |
| &nbsp;&nbsp;g_lane[3].u_lane | encoder_lane__parameterized2 | 4828 | 2137 | 8 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;(g_lane[3].u_lane) | encoder_lane__parameterized2 | 107 | 45 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;g_rgb.u_conv | rgb2ycbcr_2px | 1857 | 520 | 7 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8 | 721 | 68 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc | 142 | 120 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc | 315 | 34 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen | 938 | 857 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer | 279 | 182 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle | 419 | 238 | 0 | 0 |
| &nbsp;&nbsp;u_kseg | kseg_unit | 790 | 591 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_kseg) | kseg_unit | 4 | 133 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core_0 | 786 | 458 | 0 | 0 |
| &nbsp;&nbsp;u_merge | segment_merger | 69 | 39 | 0 | 0 |
| &nbsp;&nbsp;u_regs | axil_regs | 565 | 453 | 0 | 0 |
| &nbsp;&nbsp;u_tag | tag_unit | 1339 | 1191 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_tag) | tag_unit | 361 | 605 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core | 978 | 586 | 0 | 0 |
| &nbsp;&nbsp;u_words | scan_word_packer | 24 | 95 | 0 | 0 |

### Resource breakdown: secure_jpeg_lanes_top_lanes4_log_l2_log_maxw10_pixfmt1

| Block | Module | LUT | FF | BRAM | DSP |
|---|---|---|---|---|---|
| secure_jpeg_lanes_top | (top) | 15172 | 9390 | 60 | 92 |
| &nbsp;&nbsp;(secure_jpeg_lanes_top) | (top) | 75 | 54 | 0 | 0 |
| &nbsp;&nbsp;g_lane[0].u_lane | encoder_lane | 3071 | 1708 | 15 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle_40 | 422 | 238 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;g_yuyv.u_conv | yuyv_4px_32 | 100 | 93 | 14 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8_33 | 801 | 68 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc_34 | 143 | 120 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc_36 | 314 | 34 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen_37 | 928 | 857 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer_38 | 277 | 182 | 0 | 0 |
| &nbsp;&nbsp;g_lane[1].u_lane | encoder_lane__parameterized0 | 3083 | 1710 | 15 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;(g_lane[1].u_lane) | encoder_lane__parameterized0 | 107 | 45 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;g_yuyv.u_conv | yuyv_4px_17 | 104 | 93 | 14 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8_18 | 724 | 68 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc_19 | 143 | 120 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc_21 | 315 | 34 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen_22 | 939 | 857 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer_23 | 280 | 182 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle_25 | 420 | 238 | 0 | 0 |
| &nbsp;&nbsp;g_lane[2].u_lane | encoder_lane__parameterized1 | 3081 | 1711 | 15 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle_10 | 421 | 238 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;g_yuyv.u_conv | yuyv_4px_2 | 100 | 93 | 14 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8_3 | 804 | 70 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc_4 | 144 | 120 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc_6 | 314 | 34 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen_7 | 928 | 857 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer_8 | 277 | 182 | 0 | 0 |
| &nbsp;&nbsp;g_lane[3].u_lane | encoder_lane__parameterized2 | 3084 | 1838 | 15 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;(g_lane[3].u_lane) | encoder_lane__parameterized2 | 105 | 45 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;g_yuyv.u_conv | yuyv_4px | 111 | 221 | 14 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8 | 723 | 68 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc | 143 | 120 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc | 314 | 34 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen | 938 | 857 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer | 280 | 182 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle | 421 | 238 | 0 | 0 |
| &nbsp;&nbsp;u_kseg | kseg_unit | 790 | 591 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_kseg) | kseg_unit | 4 | 133 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core_0 | 786 | 458 | 0 | 0 |
| &nbsp;&nbsp;u_merge | segment_merger | 69 | 39 | 0 | 0 |
| &nbsp;&nbsp;u_regs | axil_regs | 556 | 453 | 0 | 0 |
| &nbsp;&nbsp;u_tag | tag_unit | 1341 | 1191 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_tag) | tag_unit | 363 | 605 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core | 978 | 586 | 0 | 0 |
| &nbsp;&nbsp;u_words | scan_word_packer | 24 | 95 | 0 | 0 |

### Resource breakdown: secure_jpeg_lanes_top_lanes4_log_l2_log_maxw11_nbuf1

| Block | Module | LUT | FF | BRAM | DSP |
|---|---|---|---|---|---|
| secure_jpeg_lanes_top | (top) | 17511 | 10755 | 56 | 92 |
| &nbsp;&nbsp;(secure_jpeg_lanes_top) | (top) | 75 | 59 | 0 | 0 |
| &nbsp;&nbsp;g_lane[0].u_lane | encoder_lane | 3267 | 2060 | 14 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle_40 | 421 | 238 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;g_rgb.u_conv | rgb2ycbcr_2px_32 | 293 | 444 | 13 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8_33 | 806 | 69 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc_34 | 143 | 120 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc_36 | 315 | 34 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen_37 | 929 | 857 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer_38 | 276 | 182 | 0 | 0 |
| &nbsp;&nbsp;g_lane[1].u_lane | encoder_lane__parameterized0 | 3270 | 2061 | 14 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;(g_lane[1].u_lane) | encoder_lane__parameterized0 | 106 | 45 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;g_rgb.u_conv | rgb2ycbcr_2px_17 | 297 | 444 | 13 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8_18 | 724 | 68 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc_19 | 143 | 120 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc_21 | 314 | 34 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen_22 | 937 | 857 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer_23 | 280 | 182 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle_25 | 420 | 238 | 0 | 0 |
| &nbsp;&nbsp;g_lane[2].u_lane | encoder_lane__parameterized1 | 3281 | 2060 | 14 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle_10 | 420 | 238 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;g_rgb.u_conv | rgb2ycbcr_2px_2 | 300 | 444 | 13 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8_3 | 806 | 68 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc_4 | 143 | 120 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc_6 | 314 | 34 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen_7 | 929 | 857 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer_8 | 276 | 182 | 0 | 0 |
| &nbsp;&nbsp;g_lane[3].u_lane | encoder_lane__parameterized2 | 4837 | 2146 | 14 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;(g_lane[3].u_lane) | encoder_lane__parameterized2 | 105 | 45 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;g_rgb.u_conv | rgb2ycbcr_2px | 1861 | 528 | 13 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8 | 723 | 69 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc | 143 | 120 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc | 315 | 34 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen | 938 | 857 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer | 280 | 182 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle | 420 | 238 | 0 | 0 |
| &nbsp;&nbsp;u_kseg | kseg_unit | 790 | 591 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_kseg) | kseg_unit | 4 | 133 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core_0 | 786 | 458 | 0 | 0 |
| &nbsp;&nbsp;u_merge | segment_merger | 69 | 39 | 0 | 0 |
| &nbsp;&nbsp;u_regs | axil_regs | 566 | 453 | 0 | 0 |
| &nbsp;&nbsp;u_tag | tag_unit | 1338 | 1191 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_tag) | tag_unit | 361 | 605 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core | 977 | 586 | 0 | 0 |
| &nbsp;&nbsp;u_words | scan_word_packer | 24 | 95 | 0 | 0 |

### Resource breakdown: secure_jpeg_top

| Block | Module | LUT | FF | BRAM | DSP |
|---|---|---|---|---|---|
| secure_jpeg_top | (top) | 5043 | 3506 | 25.5 | 23 |
| &nbsp;&nbsp;(secure_jpeg_top) | (top) | 0 | 5 | 0 | 0 |
| &nbsp;&nbsp;u_conv | rgb2ycbcr_block | 409 | 346 | 25 | 0 |
| &nbsp;&nbsp;u_dct | dct8x8 | 808 | 69 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_cols | dct_stage__parameterized0 | 507 | 36 | 0 | 11 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rows | dct_stage | 301 | 33 | 0 | 11 |
| &nbsp;&nbsp;u_enc | selective_enc | 147 | 120 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_enc) | selective_enc | 83 | 24 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_in | skid_buf | 64 | 96 | 0 | 0 |
| &nbsp;&nbsp;u_huff | huffman_enc | 315 | 34 | 0 | 0 |
| &nbsp;&nbsp;u_ks | keystream_gen | 874 | 857 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_ks) | keystream_gen | 131 | 272 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core_0 | 743 | 585 | 0 | 0 |
| &nbsp;&nbsp;u_pack | bit_packer | 284 | 182 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_pack) | bit_packer | 17 | 84 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_in | skid_buf__parameterized0 | 228 | 78 | 0 | 0 |
| &nbsp;&nbsp;u_regs | axil_regs | 393 | 452 | 0 | 0 |
| &nbsp;&nbsp;u_rle | zigzag_rle | 411 | 238 | 0 | 0 |
| &nbsp;&nbsp;u_tag | tag_unit | 1357 | 1072 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_tag) | tag_unit | 387 | 614 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core | 970 | 458 | 0 | 0 |
| &nbsp;&nbsp;u_words | scan_word_packer | 20 | 95 | 0 | 0 |

### Resource breakdown: secure_jpeg_top_6.0ns

| Block | Module | LUT | FF | BRAM | DSP |
|---|---|---|---|---|---|
| secure_jpeg_top | (top) | 5181 | 3548 | 25 | 23 |
| &nbsp;&nbsp;(secure_jpeg_top) | (top) | 0 | 5 | 0 | 0 |
| &nbsp;&nbsp;u_conv | rgb2ycbcr_block | 413 | 352 | 25 | 0 |
| &nbsp;&nbsp;u_dct | dct8x8 | 808 | 69 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_cols | dct_stage__parameterized0 | 506 | 36 | 0 | 11 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rows | dct_stage | 302 | 33 | 0 | 11 |
| &nbsp;&nbsp;u_enc | selective_enc | 162 | 134 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_enc) | selective_enc | 98 | 38 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_in | skid_buf | 64 | 96 | 0 | 0 |
| &nbsp;&nbsp;u_huff | huffman_enc | 327 | 36 | 0 | 0 |
| &nbsp;&nbsp;u_ks | keystream_gen | 880 | 859 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_ks) | keystream_gen | 136 | 274 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core_0 | 744 | 585 | 0 | 0 |
| &nbsp;&nbsp;u_pack | bit_packer | 303 | 182 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_pack) | bit_packer | 17 | 84 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_in | skid_buf__parameterized0 | 247 | 78 | 0 | 0 |
| &nbsp;&nbsp;u_quant | quantiser | 91 | 53 | 0 | 1 |
| &nbsp;&nbsp;u_regs | axil_regs | 405 | 452 | 0 | 0 |
| &nbsp;&nbsp;u_rle | zigzag_rle | 413 | 239 | 0 | 0 |
| &nbsp;&nbsp;u_tag | tag_unit | 1360 | 1072 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_tag) | tag_unit | 387 | 614 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core | 973 | 458 | 0 | 0 |
| &nbsp;&nbsp;u_words | scan_word_packer | 20 | 95 | 0 | 0 |

### Resource breakdown: secure_jpeg_top_6.667ns

| Block | Module | LUT | FF | BRAM | DSP |
|---|---|---|---|---|---|
| secure_jpeg_top | (top) | 5126 | 3512 | 25 | 23 |
| &nbsp;&nbsp;(secure_jpeg_top) | (top) | 0 | 5 | 0 | 0 |
| &nbsp;&nbsp;u_conv | rgb2ycbcr_block | 411 | 352 | 25 | 0 |
| &nbsp;&nbsp;u_dct | dct8x8 | 805 | 69 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_cols | dct_stage__parameterized0 | 505 | 36 | 0 | 11 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rows | dct_stage | 300 | 33 | 0 | 11 |
| &nbsp;&nbsp;u_enc | selective_enc | 150 | 120 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_enc) | selective_enc | 86 | 24 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_in | skid_buf | 64 | 96 | 0 | 0 |
| &nbsp;&nbsp;u_huff | huffman_enc | 325 | 34 | 0 | 0 |
| &nbsp;&nbsp;u_ks | keystream_gen | 877 | 857 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_ks) | keystream_gen | 134 | 272 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core_0 | 743 | 585 | 0 | 0 |
| &nbsp;&nbsp;u_pack | bit_packer | 286 | 182 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_pack) | bit_packer | 17 | 84 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_in | skid_buf__parameterized0 | 231 | 78 | 0 | 0 |
| &nbsp;&nbsp;u_quant | quantiser | 91 | 36 | 0 | 1 |
| &nbsp;&nbsp;u_regs | axil_regs | 393 | 452 | 0 | 0 |
| &nbsp;&nbsp;u_rle | zigzag_rle | 411 | 238 | 0 | 0 |
| &nbsp;&nbsp;u_tag | tag_unit | 1359 | 1072 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_tag) | tag_unit | 389 | 614 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core | 970 | 458 | 0 | 0 |
| &nbsp;&nbsp;u_words | scan_word_packer | 20 | 95 | 0 | 0 |

### Resource breakdown: overlay_lanes4hd

| Block | Module | LUT | FF | BRAM | DSP |
|---|---|---|---|---|---|
| system_wrapper | (top) | 20104 | 14278 | 58.5 | 92 |
| &nbsp;&nbsp;system_i | system | 20104 | 14278 | 58.5 | 92 |
| &nbsp;&nbsp;&nbsp;&nbsp;sjpeg | system_sjpeg_0 | 17511 | 10755 | 56 | 92 |
| &nbsp;&nbsp;&nbsp;&nbsp;axi_mem_intercon | system_axi_mem_intercon_0 | 664 | 781 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;dma | system_dma_0 | 1397 | 2033 | 2.5 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;ps7_axi_periph | system_ps7_axi_periph_0 | 516 | 675 | 0 | 0 |

### Resource breakdown: overlay_lanes4yuyv

| Block | Module | LUT | FF | BRAM | DSP |
|---|---|---|---|---|---|
| system_wrapper | (top) | 17780 | 12945 | 62.5 | 92 |
| &nbsp;&nbsp;system_i | system | 17780 | 12945 | 62.5 | 92 |
| &nbsp;&nbsp;&nbsp;&nbsp;sjpeg | system_sjpeg_0 | 15174 | 9390 | 60 | 92 |
| &nbsp;&nbsp;&nbsp;&nbsp;axi_mem_intercon | system_axi_mem_intercon_0 | 663 | 781 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;dma | system_dma_0 | 1411 | 2065 | 2.5 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;ps7_axi_periph | system_ps7_axi_periph_0 | 515 | 675 | 0 | 0 |

