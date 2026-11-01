## Hardware results from Vivado (post-route, xc7z020clg400-1)

| Design | LUT | FF | BRAM | DSP | Clock (MHz) | WNS (ns) | Timing met | Est. fmax (MHz) | Power total / dynamic (W) |
|---|---|---|---|---|---|---|---|---|---|
| secure_jpeg_lanes_top_8.0ns_lanes2_log_l1 | 9458 (17.8%) | 5972 (5.6%) | 52.0 (37.1%) | 46 (20.9%) | 125 | 0.213 | yes | 128.4 | 0.448 / 0.338 |
| secure_jpeg_lanes_top_lanes2_log_l1 | 9394 (17.7%) | 5972 (5.6%) | 52.0 (37.1%) | 46 (20.9%) | 100 | 0.241 | yes | 102.5 | 0.379 / 0.269 |
| secure_jpeg_lanes_top_lanes4_log_l2_log_maxw10 | 16098 (30.3%) | 9424 (8.9%) | 56.0 (40.0%) | 92 (41.8%) | 100 | 0.383 | yes | 104.0 | 0.549 / 0.436 |
| secure_jpeg_top | 4752 (8.9%) | 3178 (3.0%) | 25.5 (18.2%) | 23 (10.4%) | 100 | 0.583 | yes | 106.2 | 0.219 / 0.113 |
| secure_jpeg_top_8.0ns | 4780 (9.0%) | 3178 (3.0%) | 25.5 (18.2%) | 23 (10.4%) | 125 | 0.060 | yes | 125.9 | 0.248 / 0.142 |
| overlay | 7433 (14.0%) | 6731 (6.3%) | 27.5 (19.6%) | 23 (10.4%) | 100 | 0.760 | yes | 108.2 | 1.799 / 1.656 |
| overlay_lanes | 11982 (22.5%) | 9495 (8.9%) | 54.5 (38.9%) | 46 (20.9%) | 100 | 0.481 | yes | 105.1 | 1.943 / 1.794 |
| overlay_lanes4 | 18683 (35.1%) | 12947 (12.2%) | 58.5 (41.8%) | 92 (41.8%) | 100 | 0.461 | yes | 104.8 | 2.107 / 1.951 |

Power is Vivado's vectorless estimate (confidence shown in power.txt); measure the board for real power.
Est. fmax = 1000 / (period - WNS): a single-run estimate, confirm by re-running at that period.

### Power with simulated switching activity (SAIF from the XSim testbench)

| Design | Run | Total (W) | Dynamic (W) | Vectorless dynamic (W) | Confidence | Internal nodes |
|---|---|---|---|---|---|---|
| secure_jpeg_lanes_top_lanes2_log_l1 | v3_E2 | 0.322 | 0.213 | 0.269 | Medium | Medium: User specified less than 25% of internal nodes |
| secure_jpeg_lanes_top_lanes2_log_l1 | v3_E5 | 0.321 | 0.212 | 0.269 | Medium | Medium: User specified less than 25% of internal nodes |
| secure_jpeg_top | v2_E0 | 0.206 | 0.100 | 0.113 | Medium | Medium: User specified less than 25% of internal nodes |
| secure_jpeg_top | v2_E2 | 0.205 | 0.099 | 0.113 | Medium | Medium: User specified less than 25% of internal nodes |
| secure_jpeg_top | v2_E4 | 0.205 | 0.099 | 0.113 | Medium | Medium: User specified less than 25% of internal nodes |

Run = contract (v2: secure_jpeg_top, v3: 2 lanes) and mode; activity of one scene frame (vivado/run_vivado_day.py --steps power). Activity from RTL simulation matches only the nets whose names survive synthesis; the rest keep Vivado's default. Still an estimate: the board measurement (GUIDE A4) is the measured number.

### Worst setup paths (block of source -> destination)

| Design | Clock (MHz) | Paths (slack ns: from -> to) |
|---|---|---|
| secure_jpeg_lanes_top_8.0ns_lanes2_log_l1 | 125 | +0.213: g_lane[0].u_lane -> g_lane[0].u_lane; +0.213: g_lane[0].u_lane -> g_lane[0].u_lane; +0.213: g_lane[0].u_lane -> g_lane[0].u_lane; +0.213: g_lane[0].u_lane -> g_lane[0].u_lane; +0.277: mode_l_reg[0] -> g_lane[1].u_lane |
| secure_jpeg_lanes_top_lanes2_log_l1 | 100 | +0.241: g_lane[1].u_lane -> g_lane[1].u_lane; +0.241: g_lane[1].u_lane -> g_lane[1].u_lane; +0.241: g_lane[1].u_lane -> g_lane[1].u_lane; +0.241: g_lane[1].u_lane -> g_lane[1].u_lane; +0.241: g_lane[1].u_lane -> g_lane[1].u_lane |
| secure_jpeg_lanes_top_lanes4_log_l2_log_maxw10 | 100 | +0.383: g_lane[3].u_lane -> g_lane[3].u_lane; +0.384: g_lane[3].u_lane -> g_lane[3].u_lane; +0.437: g_lane[1].u_lane -> g_lane[1].u_lane; +0.437: g_lane[1].u_lane -> g_lane[1].u_lane; +0.437: g_lane[1].u_lane -> g_lane[1].u_lane |
| secure_jpeg_top | 100 | +0.583: u_tag -> u_pack; +0.636: u_rle -> u_ks; +0.636: u_rle -> u_ks; +0.636: u_rle -> u_ks; +0.636: u_rle -> u_ks |
| secure_jpeg_top_8.0ns | 125 | +0.060: u_pack -> u_pack; +0.147: u_rle -> u_ks; +0.147: u_rle -> u_ks; +0.147: u_rle -> u_ks; +0.147: u_rle -> u_ks |
| overlay | 100 | +0.760: system_i -> system_i; +0.783: system_i -> system_i; +0.790: system_i -> system_i; +0.830: system_i -> system_i; +0.862: system_i -> system_i |
| overlay_lanes | 100 | +0.481: system_i -> system_i; +0.481: system_i -> system_i; +0.481: system_i -> system_i; +0.522: system_i -> system_i; +0.571: system_i -> system_i |
| overlay_lanes4 | 100 | +0.461: system_i -> system_i; +0.461: system_i -> system_i; +0.565: system_i -> system_i; +0.565: system_i -> system_i; +0.577: system_i -> system_i |

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

### Resource breakdown: secure_jpeg_lanes_top_lanes2_log_l1

| Block | Module | LUT | FF | BRAM | DSP |
|---|---|---|---|---|---|
| secure_jpeg_lanes_top | (top) | 9394 | 5972 | 52 | 46 |
| &nbsp;&nbsp;(secure_jpeg_lanes_top) | (top) | 4 | 41 | 0 | 0 |
| &nbsp;&nbsp;g_lane[0].u_lane | encoder_lane | 2918 | 1739 | 26 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle_10 | 262 | 110 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_conv | rgb2ycbcr_2px_2 | 306 | 451 | 25 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8_3 | 800 | 69 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc_4 | 82 | 24 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc_6 | 217 | 34 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen_7 | 963 | 851 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer_8 | 207 | 84 | 0 | 0 |
| &nbsp;&nbsp;g_lane[1].u_lane | encoder_lane__parameterized0 | 3718 | 1824 | 26 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle | 264 | 110 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_conv | rgb2ycbcr_2px | 1091 | 535 | 25 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8 | 804 | 69 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc | 82 | 24 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc | 217 | 34 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen | 963 | 851 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer | 208 | 84 | 0 | 0 |
| &nbsp;&nbsp;u_kseg | kseg_unit | 790 | 591 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_kseg) | kseg_unit | 4 | 133 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core_0 | 786 | 458 | 0 | 0 |
| &nbsp;&nbsp;u_merge | segment_merger | 56 | 38 | 0 | 0 |
| &nbsp;&nbsp;u_regs | axil_regs | 552 | 453 | 0 | 0 |
| &nbsp;&nbsp;u_tag | tag_unit | 1336 | 1191 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_tag) | tag_unit | 359 | 605 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core | 977 | 586 | 0 | 0 |
| &nbsp;&nbsp;u_words | scan_word_packer | 24 | 95 | 0 | 0 |

### Resource breakdown: secure_jpeg_lanes_top_lanes4_log_l2_log_maxw10

| Block | Module | LUT | FF | BRAM | DSP |
|---|---|---|---|---|---|
| secure_jpeg_lanes_top | (top) | 16098 | 9424 | 56 | 92 |
| &nbsp;&nbsp;(secure_jpeg_lanes_top) | (top) | 4 | 42 | 0 | 0 |
| &nbsp;&nbsp;g_lane[0].u_lane | encoder_lane | 2913 | 1731 | 14 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle_34 | 264 | 110 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_conv | rgb2ycbcr_2px_26 | 299 | 445 | 13 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8_27 | 802 | 69 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc_28 | 82 | 24 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc_30 | 217 | 34 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen_31 | 962 | 851 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer_32 | 208 | 84 | 0 | 0 |
| &nbsp;&nbsp;g_lane[1].u_lane | encoder_lane__parameterized0 | 2919 | 1732 | 14 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;(g_lane[1].u_lane) | encoder_lane__parameterized0 | 105 | 43 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_conv | rgb2ycbcr_2px_14 | 306 | 445 | 13 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8_15 | 723 | 68 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc_16 | 82 | 24 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc_18 | 217 | 34 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen_19 | 971 | 851 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer_20 | 211 | 84 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle_22 | 258 | 110 | 0 | 0 |
| &nbsp;&nbsp;g_lane[2].u_lane | encoder_lane__parameterized1 | 2922 | 1732 | 14 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle_10 | 265 | 110 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_conv | rgb2ycbcr_2px_2 | 300 | 445 | 13 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8_3 | 802 | 69 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc_4 | 82 | 24 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc_6 | 217 | 34 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen_7 | 962 | 851 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer_8 | 207 | 84 | 0 | 0 |
| &nbsp;&nbsp;g_lane[3].u_lane | encoder_lane__parameterized2 | 4485 | 1817 | 14 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;(g_lane[3].u_lane) | encoder_lane__parameterized2 | 107 | 43 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_conv | rgb2ycbcr_2px | 1871 | 529 | 13 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8 | 721 | 69 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc | 82 | 24 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc | 217 | 34 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen | 970 | 851 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer | 212 | 84 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle | 259 | 110 | 0 | 0 |
| &nbsp;&nbsp;u_kseg | kseg_unit | 790 | 591 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_kseg) | kseg_unit | 4 | 133 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core_0 | 786 | 458 | 0 | 0 |
| &nbsp;&nbsp;u_merge | segment_merger | 68 | 39 | 0 | 0 |
| &nbsp;&nbsp;u_regs | axil_regs | 639 | 454 | 0 | 0 |
| &nbsp;&nbsp;u_tag | tag_unit | 1339 | 1191 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_tag) | tag_unit | 362 | 605 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core | 978 | 586 | 0 | 0 |
| &nbsp;&nbsp;u_words | scan_word_packer | 24 | 95 | 0 | 0 |

### Resource breakdown: secure_jpeg_top

| Block | Module | LUT | FF | BRAM | DSP |
|---|---|---|---|---|---|
| secure_jpeg_top | (top) | 4752 | 3178 | 25.5 | 23 |
| &nbsp;&nbsp;(secure_jpeg_top) | (top) | 0 | 5 | 0 | 0 |
| &nbsp;&nbsp;u_conv | rgb2ycbcr_block | 426 | 347 | 25 | 0 |
| &nbsp;&nbsp;u_dct | dct8x8 | 806 | 69 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_cols | dct_stage__parameterized0 | 506 | 36 | 0 | 11 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rows | dct_stage | 300 | 33 | 0 | 11 |
| &nbsp;&nbsp;u_enc | selective_enc | 82 | 24 | 0 | 0 |
| &nbsp;&nbsp;u_huff | huffman_enc | 268 | 34 | 0 | 0 |
| &nbsp;&nbsp;u_ks | keystream_gen | 949 | 851 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_ks) | keystream_gen | 89 | 266 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core_0 | 860 | 585 | 0 | 0 |
| &nbsp;&nbsp;u_pack | bit_packer | 210 | 84 | 0 | 0 |
| &nbsp;&nbsp;u_regs | axil_regs | 393 | 451 | 0 | 0 |
| &nbsp;&nbsp;u_rle | zigzag_rle | 218 | 110 | 0 | 0 |
| &nbsp;&nbsp;u_tag | tag_unit | 1358 | 1072 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_tag) | tag_unit | 388 | 614 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core | 970 | 458 | 0 | 0 |
| &nbsp;&nbsp;u_words | scan_word_packer | 20 | 95 | 0 | 0 |

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
| system_wrapper | (top) | 7433 | 6731 | 27.5 | 23 |
| &nbsp;&nbsp;system_i | system | 7433 | 6731 | 27.5 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;sjpeg | system_sjpeg_0 | 4747 | 3052 | 25.5 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;axi_mem_intercon | system_axi_mem_intercon_0 | 814 | 1007 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;dma | system_dma_0 | 1341 | 1963 | 2 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;ps7_axi_periph | system_ps7_axi_periph_0 | 515 | 675 | 0 | 0 |

### Resource breakdown: overlay_lanes

| Block | Module | LUT | FF | BRAM | DSP |
|---|---|---|---|---|---|
| system_wrapper | (top) | 11982 | 9495 | 54.5 | 46 |
| &nbsp;&nbsp;system_i | system | 11982 | 9495 | 54.5 | 46 |
| &nbsp;&nbsp;&nbsp;&nbsp;sjpeg | system_sjpeg_0 | 9397 | 5972 | 52 | 46 |
| &nbsp;&nbsp;&nbsp;&nbsp;axi_mem_intercon | system_axi_mem_intercon_0 | 653 | 781 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;dma | system_dma_0 | 1398 | 2033 | 2.5 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;ps7_axi_periph | system_ps7_axi_periph_0 | 517 | 675 | 0 | 0 |

### Resource breakdown: overlay_lanes4

| Block | Module | LUT | FF | BRAM | DSP |
|---|---|---|---|---|---|
| system_wrapper | (top) | 18683 | 12947 | 58.5 | 92 |
| &nbsp;&nbsp;system_i | system | 18683 | 12947 | 58.5 | 92 |
| &nbsp;&nbsp;&nbsp;&nbsp;sjpeg | system_sjpeg_0 | 16103 | 9424 | 56 | 92 |
| &nbsp;&nbsp;&nbsp;&nbsp;axi_mem_intercon | system_axi_mem_intercon_0 | 653 | 781 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;dma | system_dma_0 | 1396 | 2033 | 2.5 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;ps7_axi_periph | system_ps7_axi_periph_0 | 515 | 675 | 0 | 0 |

