## Hardware results from Vivado (post-route, xc7z020clg400-1)

| Design | LUT | FF | BRAM | DSP | Clock (MHz) | WNS (ns) | Timing met | Est. fmax (MHz) | Power total / dynamic (W) |
|---|---|---|---|---|---|---|---|---|---|
| overlay_lanes4 | 20097 (37.8%) | 14269 (13.4%) | 58.5 (41.8%) | 92 (41.8%) | 125 | 0.433 | yes | 132.2 | 2.254 / 2.093 |
| secure_jpeg_lanes_top_6.0ns_lanes2_log_l1 | 10404 (19.6%) | 6824 (6.4%) | 51.0 (36.4%) | 46 (20.9%) | 167 | -0.467 | NO | 154.6 | 0.617 / 0.503 |
| secure_jpeg_lanes_top_6.667ns_lanes2_log_l1 | 10294 (19.4%) | 6650 (6.2%) | 51.0 (36.4%) | 46 (20.9%) | 150 | -0.060 | NO | 148.7 | 0.562 / 0.450 |
| secure_jpeg_lanes_top_lanes2_log_l1 | 10086 (19.0%) | 6633 (6.2%) | 52.0 (37.1%) | 46 (20.9%) | 100 | 0.803 | yes | 108.7 | 0.413 / 0.302 |
| secure_jpeg_lanes_top_lanes4_log_l2_log_maxw10 | 17478 (32.9%) | 10746 (10.1%) | 56.0 (40.0%) | 92 (41.8%) | 100 | 0.833 | yes | 109.1 | 0.606 / 0.492 |
| secure_jpeg_lanes_top_lanes4_log_l2_log_maxw10_nbuf1 | 17455 (32.8%) | 10710 (10.1%) | 32.0 (22.9%) | 92 (41.8%) | 100 | 0.808 | yes | 108.8 | 0.577 / 0.465 |
| secure_jpeg_lanes_top_lanes4_log_l2_log_maxw10_pixfmt1 | 15138 (28.4%) | 9377 (8.8%) | 60.0 (42.9%) | 92 (41.8%) | 100 | 0.599 | yes | 106.4 | 0.569 / 0.455 |
| secure_jpeg_lanes_top_lanes4_log_l2_log_maxw11_nbuf1 | 17481 (32.9%) | 10742 (10.1%) | 56.0 (40.0%) | 92 (41.8%) | 100 | 0.789 | yes | 108.6 | 0.606 / 0.492 |
| secure_jpeg_top | 5028 (9.4%) | 3506 (3.3%) | 25.5 (18.2%) | 23 (10.4%) | 100 | 1.376 | yes | 116.0 | 0.250 / 0.144 |
| secure_jpeg_top_6.0ns | 5217 (9.8%) | 3613 (3.4%) | 25.0 (17.9%) | 23 (10.4%) | 167 | -0.284 | NO | 159.1 | 0.352 / 0.244 |
| secure_jpeg_top_6.667ns | 5124 (9.6%) | 3512 (3.3%) | 25.0 (17.9%) | 23 (10.4%) | 150 | 0.074 | yes | 151.7 | 0.322 / 0.215 |

Power is Vivado's vectorless estimate (confidence shown in power.txt); measure the board for real power.
Est. fmax = 1000 / (period - WNS): a single-run estimate, confirm by re-running at that period.

### Power with simulated switching activity (SAIF from the XSim testbench)

| Design | Run | Total (W) | Dynamic (W) | Vectorless dynamic (W) | Confidence | Internal nodes |
|---|---|---|---|---|---|---|
| secure_jpeg_lanes_top_lanes2_log_l1 | v3_E2 | 0.353 | 0.244 | 0.302 | Medium | Medium: User specified less than 25% of internal nodes |
| secure_jpeg_lanes_top_lanes2_log_l1 | v3_E5 | 0.353 | 0.243 | 0.302 | Medium | Medium: User specified less than 25% of internal nodes |
| secure_jpeg_lanes_top_lanes4_log_l2_log_maxw10 | v3l4_E2 | 0.503 | 0.391 | 0.492 | Medium | Medium: User specified less than 25% of internal nodes |
| secure_jpeg_lanes_top_lanes4_log_l2_log_maxw10 | v3l4_E5 | 0.504 | 0.392 | 0.492 | Medium | Medium: User specified less than 25% of internal nodes |
| secure_jpeg_top | v2_E0 | 0.231 | 0.125 | 0.144 | Medium | Medium: User specified less than 25% of internal nodes |
| secure_jpeg_top | v2_E2 | 0.231 | 0.125 | 0.144 | Medium | Medium: User specified less than 25% of internal nodes |
| secure_jpeg_top | v2_E4 | 0.231 | 0.126 | 0.144 | Medium | Medium: User specified less than 25% of internal nodes |

Run = contract (v2: secure_jpeg_top, v3: 2 lanes) and mode; activity of one scene frame (vivado/run_vivado_day.py --steps power). Activity from RTL simulation matches only the nets whose names survive synthesis; the rest keep Vivado's default. Still an estimate: the board measurement (GUIDE A4) is the measured number.

### Worst setup paths (block of source -> destination)

| Design | Clock (MHz) | Paths (slack ns: from -> to) |
|---|---|---|
| overlay_lanes4 | 125 | +0.433: system_i -> system_i; +0.433: system_i -> system_i; +0.433: system_i -> system_i; +0.437: system_i -> system_i; +0.437: system_i -> system_i |
| secure_jpeg_lanes_top_6.0ns_lanes2_log_l1 | 167 | -0.467: g_lane[0].u_lane -> g_lane[0].u_lane; -0.443: g_lane[1].u_lane -> g_lane[1].u_lane; -0.443: g_lane[1].u_lane -> g_lane[1].u_lane; -0.425: g_lane[1].u_lane -> g_lane[1].u_lane; -0.425: g_lane[1].u_lane -> g_lane[1].u_lane |
| secure_jpeg_lanes_top_6.667ns_lanes2_log_l1 | 150 | -0.060: u_regs -> segs_reg[15]_inv; -0.059: u_regs -> segs_reg[13]; +0.016: u_regs -> segs_reg[12]; +0.049: g_lane[1].u_lane -> g_lane[1].u_lane; +0.056: g_lane[0].u_lane -> g_lane[0].u_lane |
| secure_jpeg_lanes_top_lanes2_log_l1 | 100 | +0.803: g_lane[1].u_lane -> g_lane[1].u_lane; +1.155: u_regs -> u_kseg; +1.178: u_regs -> u_kseg; +1.178: u_regs -> u_kseg; +1.199: g_lane[1].u_lane -> g_lane[1].u_lane |
| secure_jpeg_lanes_top_lanes4_log_l2_log_maxw10 | 100 | +0.833: (top) -> g_lane[3].u_lane; +0.833: (top) -> g_lane[3].u_lane; +0.833: (top) -> g_lane[3].u_lane; +0.864: (top) -> g_lane[3].u_lane; +0.864: (top) -> g_lane[3].u_lane |
| secure_jpeg_lanes_top_lanes4_log_l2_log_maxw10_nbuf1 | 100 | +0.808: u_regs -> segs_reg[15]_inv; +0.812: u_regs -> u_kseg; +0.812: u_regs -> u_kseg; +0.953: u_regs -> u_kseg; +0.953: u_regs -> u_kseg |
| secure_jpeg_lanes_top_lanes4_log_l2_log_maxw10_pixfmt1 | 100 | +0.599: g_lane[0].u_lane -> g_lane[0].u_lane; +0.599: g_lane[0].u_lane -> g_lane[0].u_lane; +0.686: g_lane[0].u_lane -> g_lane[0].u_lane; +0.686: g_lane[0].u_lane -> g_lane[0].u_lane; +0.711: g_lane[1].u_lane -> g_lane[1].u_lane |
| secure_jpeg_lanes_top_lanes4_log_l2_log_maxw11_nbuf1 | 100 | +0.789: g_lane[1].u_lane -> g_lane[1].u_lane; +0.789: g_lane[1].u_lane -> g_lane[1].u_lane; +0.794: g_lane[1].u_lane -> g_lane[1].u_lane; +0.921: g_lane[1].u_lane -> g_lane[1].u_lane; +1.037: u_regs -> u_kseg |
| secure_jpeg_top | 100 | +1.376: u_enc -> u_ks; +1.471: u_enc -> u_ks; +1.528: u_enc -> u_ks; +1.553: u_enc -> u_ks; +1.819: u_regs -> u_ks |
| secure_jpeg_top_6.0ns | 167 | -0.284: u_ks -> u_ks; -0.284: u_ks -> u_ks; -0.266: u_ks -> u_ks; -0.266: u_ks -> u_ks; -0.063: u_conv -> u_dct |
| secure_jpeg_top_6.667ns | 150 | +0.074: (top) -> u_regs; +0.074: (top) -> u_regs; +0.074: (top) -> u_regs; +0.074: (top) -> u_regs; +0.074: (top) -> u_regs |

### Resource breakdown: overlay_lanes4

| Block | Module | LUT | FF | BRAM | DSP |
|---|---|---|---|---|---|
| system_wrapper | (top) | 20097 | 14269 | 58.5 | 92 |
| &nbsp;&nbsp;system_i | system | 20097 | 14269 | 58.5 | 92 |
| &nbsp;&nbsp;&nbsp;&nbsp;sjpeg | system_sjpeg_0 | 17508 | 10746 | 56 | 92 |
| &nbsp;&nbsp;&nbsp;&nbsp;axi_mem_intercon | system_axi_mem_intercon_0 | 661 | 781 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;dma | system_dma_0 | 1397 | 2033 | 2.5 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;ps7_axi_periph | system_ps7_axi_periph_0 | 515 | 675 | 0 | 0 |

### Resource breakdown: secure_jpeg_lanes_top_6.0ns_lanes2_log_l1

| Block | Module | LUT | FF | BRAM | DSP |
|---|---|---|---|---|---|
| secure_jpeg_lanes_top | (top) | 10404 | 6824 | 51 | 46 |
| &nbsp;&nbsp;(secure_jpeg_lanes_top) | (top) | 4 | 41 | 0 | 0 |
| &nbsp;&nbsp;g_lane[0].u_lane | encoder_lane | 3419 | 2142 | 25.5 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle_10 | 425 | 238 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;g_rgb.u_conv | rgb2ycbcr_2px_2 | 308 | 451 | 25 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8_3 | 805 | 113 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc_4 | 163 | 140 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc_6 | 331 | 36 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen_7 | 927 | 859 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer_8 | 305 | 184 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_quant | quantiser_9 | 90 | 36 | 0 | 1 |
| &nbsp;&nbsp;g_lane[1].u_lane | encoder_lane__parameterized0 | 4196 | 2257 | 25.5 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;(g_lane[1].u_lane) | encoder_lane__parameterized0 | 50 | 47 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;g_rgb.u_conv | rgb2ycbcr_2px | 1095 | 535 | 25 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8 | 808 | 144 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc | 163 | 126 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc | 327 | 36 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen | 919 | 857 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer | 297 | 182 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_quant | quantiser | 90 | 53 | 0 | 1 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle | 426 | 240 | 0 | 0 |
| &nbsp;&nbsp;u_kseg | kseg_unit | 790 | 591 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_kseg) | kseg_unit | 4 | 133 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core_0 | 786 | 458 | 0 | 0 |
| &nbsp;&nbsp;u_merge | segment_merger | 56 | 38 | 0 | 0 |
| &nbsp;&nbsp;u_regs | axil_regs | 576 | 462 | 0 | 0 |
| &nbsp;&nbsp;u_tag | tag_unit | 1339 | 1198 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_tag) | tag_unit | 360 | 612 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core | 979 | 586 | 0 | 0 |
| &nbsp;&nbsp;u_words | scan_word_packer | 24 | 95 | 0 | 0 |

### Resource breakdown: secure_jpeg_lanes_top_6.667ns_lanes2_log_l1

| Block | Module | LUT | FF | BRAM | DSP |
|---|---|---|---|---|---|
| secure_jpeg_lanes_top | (top) | 10294 | 6650 | 51 | 46 |
| &nbsp;&nbsp;(secure_jpeg_lanes_top) | (top) | 4 | 41 | 0 | 0 |
| &nbsp;&nbsp;g_lane[0].u_lane | encoder_lane | 3359 | 2078 | 25.5 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle_10 | 423 | 239 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;g_rgb.u_conv | rgb2ycbcr_2px_2 | 304 | 451 | 25 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8_3 | 801 | 68 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc_4 | 155 | 127 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc_6 | 321 | 35 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen_7 | 922 | 857 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer_8 | 279 | 182 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_quant | quantiser_9 | 90 | 36 | 0 | 1 |
| &nbsp;&nbsp;g_lane[1].u_lane | encoder_lane__parameterized0 | 4154 | 2161 | 25.5 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;(g_lane[1].u_lane) | encoder_lane__parameterized0 | 50 | 47 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;g_rgb.u_conv | rgb2ycbcr_2px | 1090 | 535 | 25 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8 | 803 | 69 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc | 155 | 122 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc | 320 | 35 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen | 922 | 860 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer | 281 | 182 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_quant | quantiser | 90 | 36 | 0 | 1 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle | 423 | 238 | 0 | 0 |
| &nbsp;&nbsp;u_kseg | kseg_unit | 790 | 591 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_kseg) | kseg_unit | 4 | 133 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core_0 | 786 | 458 | 0 | 0 |
| &nbsp;&nbsp;u_merge | segment_merger | 56 | 38 | 0 | 0 |
| &nbsp;&nbsp;u_regs | axil_regs | 570 | 455 | 0 | 0 |
| &nbsp;&nbsp;u_tag | tag_unit | 1338 | 1191 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_tag) | tag_unit | 361 | 605 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core | 977 | 586 | 0 | 0 |
| &nbsp;&nbsp;u_words | scan_word_packer | 24 | 95 | 0 | 0 |

### Resource breakdown: secure_jpeg_lanes_top_lanes2_log_l1

| Block | Module | LUT | FF | BRAM | DSP |
|---|---|---|---|---|---|
| secure_jpeg_lanes_top | (top) | 10086 | 6633 | 52 | 46 |
| &nbsp;&nbsp;(secure_jpeg_lanes_top) | (top) | 4 | 41 | 0 | 0 |
| &nbsp;&nbsp;g_lane[0].u_lane | encoder_lane | 3265 | 2069 | 26 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle_10 | 421 | 238 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;g_rgb.u_conv | rgb2ycbcr_2px_2 | 301 | 451 | 25 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8_3 | 802 | 68 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc_4 | 147 | 120 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc_6 | 315 | 34 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen_7 | 915 | 857 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer_8 | 276 | 182 | 0 | 0 |
| &nbsp;&nbsp;g_lane[1].u_lane | encoder_lane__parameterized0 | 4059 | 2155 | 26 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;(g_lane[1].u_lane) | encoder_lane__parameterized0 | 51 | 47 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;g_rgb.u_conv | rgb2ycbcr_2px | 1084 | 535 | 25 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8 | 804 | 69 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc | 149 | 120 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc | 314 | 34 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen | 914 | 857 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer | 276 | 182 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle | 421 | 238 | 0 | 0 |
| &nbsp;&nbsp;u_kseg | kseg_unit | 790 | 591 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_kseg) | kseg_unit | 4 | 133 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core_0 | 786 | 458 | 0 | 0 |
| &nbsp;&nbsp;u_merge | segment_merger | 56 | 38 | 0 | 0 |
| &nbsp;&nbsp;u_regs | axil_regs | 553 | 453 | 0 | 0 |
| &nbsp;&nbsp;u_tag | tag_unit | 1337 | 1191 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_tag) | tag_unit | 360 | 605 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core | 977 | 586 | 0 | 0 |
| &nbsp;&nbsp;u_words | scan_word_packer | 24 | 95 | 0 | 0 |

### Resource breakdown: secure_jpeg_lanes_top_lanes4_log_l2_log_maxw10

| Block | Module | LUT | FF | BRAM | DSP |
|---|---|---|---|---|---|
| secure_jpeg_lanes_top | (top) | 17478 | 10746 | 56 | 92 |
| &nbsp;&nbsp;(secure_jpeg_lanes_top) | (top) | 4 | 42 | 0 | 0 |
| &nbsp;&nbsp;g_lane[0].u_lane | encoder_lane | 3261 | 2062 | 14 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle_40 | 421 | 238 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;g_rgb.u_conv | rgb2ycbcr_2px_32 | 297 | 445 | 13 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8_33 | 804 | 69 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc_34 | 148 | 120 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc_36 | 315 | 34 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen_37 | 914 | 857 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer_38 | 276 | 182 | 0 | 0 |
| &nbsp;&nbsp;g_lane[1].u_lane | encoder_lane__parameterized0 | 3261 | 2063 | 14 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;(g_lane[1].u_lane) | encoder_lane__parameterized0 | 105 | 46 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;g_rgb.u_conv | rgb2ycbcr_2px_17 | 300 | 445 | 13 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8_18 | 722 | 68 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc_19 | 147 | 120 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc_21 | 314 | 34 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen_22 | 924 | 857 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer_23 | 280 | 182 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle_25 | 420 | 238 | 0 | 0 |
| &nbsp;&nbsp;g_lane[2].u_lane | encoder_lane__parameterized1 | 3266 | 2062 | 14 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle_10 | 421 | 238 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;g_rgb.u_conv | rgb2ycbcr_2px_2 | 295 | 445 | 13 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8_3 | 800 | 68 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc_4 | 149 | 120 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc_6 | 315 | 34 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen_7 | 914 | 857 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer_8 | 278 | 182 | 0 | 0 |
| &nbsp;&nbsp;g_lane[3].u_lane | encoder_lane__parameterized2 | 4828 | 2148 | 14 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;(g_lane[3].u_lane) | encoder_lane__parameterized2 | 107 | 46 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;g_rgb.u_conv | rgb2ycbcr_2px | 1863 | 529 | 13 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8 | 722 | 69 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc | 148 | 120 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc | 314 | 34 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen | 923 | 857 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer | 280 | 182 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle | 421 | 238 | 0 | 0 |
| &nbsp;&nbsp;u_kseg | kseg_unit | 790 | 591 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_kseg) | kseg_unit | 4 | 133 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core_0 | 786 | 458 | 0 | 0 |
| &nbsp;&nbsp;u_merge | segment_merger | 68 | 39 | 0 | 0 |
| &nbsp;&nbsp;u_regs | axil_regs | 639 | 453 | 0 | 0 |
| &nbsp;&nbsp;u_tag | tag_unit | 1338 | 1191 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_tag) | tag_unit | 361 | 605 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core | 977 | 586 | 0 | 0 |
| &nbsp;&nbsp;u_words | scan_word_packer | 24 | 95 | 0 | 0 |

### Resource breakdown: secure_jpeg_lanes_top_lanes4_log_l2_log_maxw10_nbuf1

| Block | Module | LUT | FF | BRAM | DSP |
|---|---|---|---|---|---|
| secure_jpeg_lanes_top | (top) | 17455 | 10710 | 32 | 92 |
| &nbsp;&nbsp;(secure_jpeg_lanes_top) | (top) | 4 | 42 | 0 | 0 |
| &nbsp;&nbsp;g_lane[0].u_lane | encoder_lane | 3254 | 2053 | 8 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle_40 | 421 | 238 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;g_rgb.u_conv | rgb2ycbcr_2px_32 | 287 | 436 | 7 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8_33 | 806 | 69 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc_34 | 148 | 120 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc_36 | 315 | 34 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen_37 | 914 | 857 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer_38 | 277 | 182 | 0 | 0 |
| &nbsp;&nbsp;g_lane[1].u_lane | encoder_lane__parameterized0 | 3258 | 2054 | 8 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;(g_lane[1].u_lane) | encoder_lane__parameterized0 | 106 | 46 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;g_rgb.u_conv | rgb2ycbcr_2px_17 | 290 | 436 | 7 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8_18 | 725 | 68 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc_19 | 148 | 120 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc_21 | 314 | 34 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen_22 | 924 | 857 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer_23 | 281 | 182 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle_25 | 420 | 238 | 0 | 0 |
| &nbsp;&nbsp;g_lane[2].u_lane | encoder_lane__parameterized1 | 3266 | 2054 | 8 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle_10 | 420 | 238 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;g_rgb.u_conv | rgb2ycbcr_2px_2 | 293 | 436 | 7 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8_3 | 807 | 69 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc_4 | 149 | 120 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc_6 | 314 | 34 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen_7 | 915 | 857 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer_8 | 276 | 182 | 0 | 0 |
| &nbsp;&nbsp;g_lane[3].u_lane | encoder_lane__parameterized2 | 4816 | 2138 | 8 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;(g_lane[3].u_lane) | encoder_lane__parameterized2 | 106 | 46 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;g_rgb.u_conv | rgb2ycbcr_2px | 1851 | 520 | 7 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8 | 724 | 68 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc | 148 | 120 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc | 314 | 34 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen | 923 | 857 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer | 279 | 182 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle | 420 | 238 | 0 | 0 |
| &nbsp;&nbsp;u_kseg | kseg_unit | 790 | 591 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_kseg) | kseg_unit | 4 | 133 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core_0 | 786 | 458 | 0 | 0 |
| &nbsp;&nbsp;u_merge | segment_merger | 68 | 39 | 0 | 0 |
| &nbsp;&nbsp;u_regs | axil_regs | 642 | 453 | 0 | 0 |
| &nbsp;&nbsp;u_tag | tag_unit | 1338 | 1191 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_tag) | tag_unit | 361 | 605 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core | 977 | 586 | 0 | 0 |
| &nbsp;&nbsp;u_words | scan_word_packer | 24 | 95 | 0 | 0 |

### Resource breakdown: secure_jpeg_lanes_top_lanes4_log_l2_log_maxw10_pixfmt1

| Block | Module | LUT | FF | BRAM | DSP |
|---|---|---|---|---|---|
| secure_jpeg_lanes_top | (top) | 15138 | 9377 | 60 | 92 |
| &nbsp;&nbsp;(secure_jpeg_lanes_top) | (top) | 4 | 37 | 0 | 0 |
| &nbsp;&nbsp;g_lane[0].u_lane | encoder_lane | 3062 | 1709 | 15 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle_40 | 420 | 238 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;g_yuyv.u_conv | yuyv_4px_32 | 99 | 93 | 14 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8_33 | 804 | 68 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc_34 | 147 | 120 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc_36 | 314 | 34 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen_37 | 914 | 857 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer_38 | 278 | 182 | 0 | 0 |
| &nbsp;&nbsp;g_lane[1].u_lane | encoder_lane__parameterized0 | 3067 | 1711 | 15 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;(g_lane[1].u_lane) | encoder_lane__parameterized0 | 107 | 46 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;g_yuyv.u_conv | yuyv_4px_17 | 104 | 93 | 14 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8_18 | 722 | 68 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc_19 | 147 | 120 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc_21 | 314 | 34 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen_22 | 924 | 857 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer_23 | 279 | 182 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle_25 | 420 | 238 | 0 | 0 |
| &nbsp;&nbsp;g_lane[2].u_lane | encoder_lane__parameterized1 | 3073 | 1712 | 15 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle_10 | 421 | 238 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;g_yuyv.u_conv | yuyv_4px_2 | 99 | 93 | 14 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8_3 | 806 | 70 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc_4 | 148 | 120 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc_6 | 314 | 34 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen_7 | 915 | 857 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer_8 | 276 | 182 | 0 | 0 |
| &nbsp;&nbsp;g_lane[3].u_lane | encoder_lane__parameterized2 | 3079 | 1839 | 15 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;(g_lane[3].u_lane) | encoder_lane__parameterized2 | 105 | 46 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;g_yuyv.u_conv | yuyv_4px | 111 | 221 | 14 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8 | 724 | 68 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc | 148 | 120 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc | 314 | 34 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen | 925 | 857 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer | 280 | 182 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle | 421 | 238 | 0 | 0 |
| &nbsp;&nbsp;u_kseg | kseg_unit | 790 | 591 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_kseg) | kseg_unit | 4 | 133 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core_0 | 786 | 458 | 0 | 0 |
| &nbsp;&nbsp;u_merge | segment_merger | 68 | 39 | 0 | 0 |
| &nbsp;&nbsp;u_regs | axil_regs | 634 | 453 | 0 | 0 |
| &nbsp;&nbsp;u_tag | tag_unit | 1342 | 1191 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_tag) | tag_unit | 364 | 605 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core | 978 | 586 | 0 | 0 |
| &nbsp;&nbsp;u_words | scan_word_packer | 24 | 95 | 0 | 0 |

### Resource breakdown: secure_jpeg_lanes_top_lanes4_log_l2_log_maxw11_nbuf1

| Block | Module | LUT | FF | BRAM | DSP |
|---|---|---|---|---|---|
| secure_jpeg_lanes_top | (top) | 17481 | 10742 | 56 | 92 |
| &nbsp;&nbsp;(secure_jpeg_lanes_top) | (top) | 4 | 42 | 0 | 0 |
| &nbsp;&nbsp;g_lane[0].u_lane | encoder_lane | 3260 | 2061 | 14 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle_40 | 421 | 238 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;g_rgb.u_conv | rgb2ycbcr_2px_32 | 293 | 444 | 13 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8_33 | 807 | 69 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc_34 | 148 | 120 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc_36 | 314 | 34 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen_37 | 914 | 857 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer_38 | 277 | 182 | 0 | 0 |
| &nbsp;&nbsp;g_lane[1].u_lane | encoder_lane__parameterized0 | 3264 | 2062 | 14 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;(g_lane[1].u_lane) | encoder_lane__parameterized0 | 105 | 46 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;g_rgb.u_conv | rgb2ycbcr_2px_17 | 297 | 444 | 13 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8_18 | 725 | 68 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc_19 | 148 | 120 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc_21 | 314 | 34 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen_22 | 924 | 857 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer_23 | 281 | 182 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle_25 | 420 | 238 | 0 | 0 |
| &nbsp;&nbsp;g_lane[2].u_lane | encoder_lane__parameterized1 | 3272 | 2061 | 14 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle_10 | 421 | 238 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;g_rgb.u_conv | rgb2ycbcr_2px_2 | 299 | 444 | 13 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8_3 | 805 | 68 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc_4 | 149 | 120 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc_6 | 315 | 34 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen_7 | 915 | 857 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer_8 | 277 | 182 | 0 | 0 |
| &nbsp;&nbsp;g_lane[3].u_lane | encoder_lane__parameterized2 | 4819 | 2147 | 14 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;(g_lane[3].u_lane) | encoder_lane__parameterized2 | 106 | 46 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;g_rgb.u_conv | rgb2ycbcr_2px | 1854 | 528 | 13 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8 | 723 | 69 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc | 148 | 120 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc | 314 | 34 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen | 924 | 857 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer | 280 | 182 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle | 420 | 238 | 0 | 0 |
| &nbsp;&nbsp;u_kseg | kseg_unit | 790 | 591 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_kseg) | kseg_unit | 4 | 133 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core_0 | 786 | 458 | 0 | 0 |
| &nbsp;&nbsp;u_merge | segment_merger | 68 | 39 | 0 | 0 |
| &nbsp;&nbsp;u_regs | axil_regs | 644 | 453 | 0 | 0 |
| &nbsp;&nbsp;u_tag | tag_unit | 1338 | 1191 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_tag) | tag_unit | 361 | 605 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core | 977 | 586 | 0 | 0 |
| &nbsp;&nbsp;u_words | scan_word_packer | 24 | 95 | 0 | 0 |

### Resource breakdown: secure_jpeg_top

| Block | Module | LUT | FF | BRAM | DSP |
|---|---|---|---|---|---|
| secure_jpeg_top | (top) | 5028 | 3506 | 25.5 | 23 |
| &nbsp;&nbsp;(secure_jpeg_top) | (top) | 0 | 5 | 0 | 0 |
| &nbsp;&nbsp;u_conv | rgb2ycbcr_block | 408 | 346 | 25 | 0 |
| &nbsp;&nbsp;u_dct | dct8x8 | 806 | 69 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_cols | dct_stage__parameterized0 | 506 | 36 | 0 | 11 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rows | dct_stage | 300 | 33 | 0 | 11 |
| &nbsp;&nbsp;u_enc | selective_enc | 151 | 120 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_enc) | selective_enc | 83 | 24 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_in | skid_buf | 68 | 96 | 0 | 0 |
| &nbsp;&nbsp;u_huff | huffman_enc | 315 | 34 | 0 | 0 |
| &nbsp;&nbsp;u_ks | keystream_gen | 861 | 857 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_ks) | keystream_gen | 128 | 272 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core_0 | 733 | 585 | 0 | 0 |
| &nbsp;&nbsp;u_pack | bit_packer | 284 | 182 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_pack) | bit_packer | 17 | 84 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_in | skid_buf__parameterized0 | 228 | 78 | 0 | 0 |
| &nbsp;&nbsp;u_regs | axil_regs | 392 | 452 | 0 | 0 |
| &nbsp;&nbsp;u_rle | zigzag_rle | 411 | 238 | 0 | 0 |
| &nbsp;&nbsp;u_tag | tag_unit | 1357 | 1072 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_tag) | tag_unit | 387 | 614 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core | 970 | 458 | 0 | 0 |
| &nbsp;&nbsp;u_words | scan_word_packer | 20 | 95 | 0 | 0 |

### Resource breakdown: secure_jpeg_top_6.0ns

| Block | Module | LUT | FF | BRAM | DSP |
|---|---|---|---|---|---|
| secure_jpeg_top | (top) | 5217 | 3613 | 25 | 23 |
| &nbsp;&nbsp;(secure_jpeg_top) | (top) | 0 | 5 | 0 | 0 |
| &nbsp;&nbsp;u_conv | rgb2ycbcr_block | 416 | 352 | 25 | 0 |
| &nbsp;&nbsp;u_dct | dct8x8 | 809 | 130 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_cols | dct_stage__parameterized0 | 508 | 68 | 0 | 11 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rows | dct_stage | 301 | 62 | 0 | 11 |
| &nbsp;&nbsp;u_enc | selective_enc | 169 | 136 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_enc) | selective_enc | 99 | 40 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_in | skid_buf | 70 | 96 | 0 | 0 |
| &nbsp;&nbsp;u_huff | huffman_enc | 328 | 36 | 0 | 0 |
| &nbsp;&nbsp;u_ks | keystream_gen | 869 | 859 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_ks) | keystream_gen | 135 | 274 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core_0 | 734 | 585 | 0 | 0 |
| &nbsp;&nbsp;u_pack | bit_packer | 313 | 184 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_pack) | bit_packer | 17 | 86 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_in | skid_buf__parameterized0 | 257 | 78 | 0 | 0 |
| &nbsp;&nbsp;u_quant | quantiser | 91 | 53 | 0 | 1 |
| &nbsp;&nbsp;u_regs | axil_regs | 408 | 452 | 0 | 0 |
| &nbsp;&nbsp;u_rle | zigzag_rle | 413 | 239 | 0 | 0 |
| &nbsp;&nbsp;u_tag | tag_unit | 1381 | 1072 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_tag) | tag_unit | 391 | 614 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core | 990 | 458 | 0 | 0 |
| &nbsp;&nbsp;u_words | scan_word_packer | 20 | 95 | 0 | 0 |

### Resource breakdown: secure_jpeg_top_6.667ns

| Block | Module | LUT | FF | BRAM | DSP |
|---|---|---|---|---|---|
| secure_jpeg_top | (top) | 5124 | 3512 | 25 | 23 |
| &nbsp;&nbsp;(secure_jpeg_top) | (top) | 0 | 5 | 0 | 0 |
| &nbsp;&nbsp;u_conv | rgb2ycbcr_block | 412 | 352 | 25 | 0 |
| &nbsp;&nbsp;u_dct | dct8x8 | 807 | 69 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_cols | dct_stage__parameterized0 | 506 | 36 | 0 | 11 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rows | dct_stage | 301 | 33 | 0 | 11 |
| &nbsp;&nbsp;u_enc | selective_enc | 156 | 120 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_enc) | selective_enc | 88 | 24 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_in | skid_buf | 68 | 96 | 0 | 0 |
| &nbsp;&nbsp;u_huff | huffman_enc | 324 | 34 | 0 | 0 |
| &nbsp;&nbsp;u_ks | keystream_gen | 867 | 857 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_ks) | keystream_gen | 132 | 272 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core_0 | 735 | 585 | 0 | 0 |
| &nbsp;&nbsp;u_pack | bit_packer | 287 | 182 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_pack) | bit_packer | 17 | 84 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_in | skid_buf__parameterized0 | 231 | 78 | 0 | 0 |
| &nbsp;&nbsp;u_quant | quantiser | 91 | 36 | 0 | 1 |
| &nbsp;&nbsp;u_regs | axil_regs | 394 | 452 | 0 | 0 |
| &nbsp;&nbsp;u_rle | zigzag_rle | 411 | 238 | 0 | 0 |
| &nbsp;&nbsp;u_tag | tag_unit | 1358 | 1072 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_tag) | tag_unit | 388 | 614 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core | 970 | 458 | 0 | 0 |
| &nbsp;&nbsp;u_words | scan_word_packer | 20 | 95 | 0 | 0 |

