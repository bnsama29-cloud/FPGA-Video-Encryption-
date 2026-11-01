## Hardware results from Vivado (post-route, xc7z020clg400-1)

| Design | LUT | FF | BRAM | DSP | Clock (MHz) | WNS (ns) | Timing met | Est. fmax (MHz) | Power total / dynamic (W) |
|---|---|---|---|---|---|---|---|---|---|
| secure_jpeg_lanes_top_8.0ns_lanes2_log_l1 | 9650 (18.1%) | 5504 (5.2%) | 52.0 (37.1%) | 46 (20.9%) | 125 | -0.914 | NO | 112.2 | 0.443 / 0.332 |
| secure_jpeg_lanes_top_lanes2_log_l1 | 9528 (17.9%) | 5503 (5.2%) | 52.0 (37.1%) | 46 (20.9%) | 100 | 0.491 | yes | 105.2 | 0.374 / 0.265 |
| secure_jpeg_lanes_top_lanes4_log_l2_log_maxw10 | 16345 (30.7%) | 8523 (8.0%) | 56.0 (40.0%) | 92 (41.8%) | 100 | 0.243 | yes | 102.5 | 0.543 / 0.430 |
| secure_jpeg_top | 4785 (9.0%) | 3051 (2.9%) | 25.5 (18.2%) | 23 (10.4%) | 100 | 0.630 | yes | 106.7 | 0.218 / 0.112 |
| secure_jpeg_top_8.0ns | 4820 (9.1%) | 3052 (2.9%) | 25.5 (18.2%) | 23 (10.4%) | 125 | -0.487 | NO | 117.8 | 0.247 / 0.141 |
| overlay | 7433 (14.0%) | 6731 (6.3%) | 27.5 (19.6%) | 23 (10.4%) | 100 | 0.760 | yes | 108.2 | 1.799 / 1.656 |
| overlay_lanes | 12099 (22.7%) | 9026 (8.5%) | 54.5 (38.9%) | 46 (20.9%) | 100 | 0.311 | yes | 103.2 | 1.940 / 1.791 |

Power is Vivado's vectorless estimate (confidence shown in power.txt); measure the board for real power.
Est. fmax = 1000 / (period - WNS): a single-run estimate, confirm by re-running at that period.

### Power with simulated switching activity (SAIF from the XSim testbench)

| Design | Run | Total (W) | Dynamic (W) | Vectorless dynamic (W) | Confidence | Internal nodes |
|---|---|---|---|---|---|---|
| secure_jpeg_lanes_top_lanes2_log_l1 | v3_E2 | 0.318 | 0.209 | 0.265 | Medium | Medium: User specified less than 25% of internal nodes |
| secure_jpeg_lanes_top_lanes2_log_l1 | v3_E5 | 0.317 | 0.209 | 0.265 | Medium | Medium: User specified less than 25% of internal nodes |
| secure_jpeg_top | v2_E0 | 0.206 | 0.100 | 0.112 | Medium | Medium: User specified less than 25% of internal nodes |
| secure_jpeg_top | v2_E2 | 0.205 | 0.099 | 0.112 | Medium | Medium: User specified less than 25% of internal nodes |
| secure_jpeg_top | v2_E4 | 0.205 | 0.099 | 0.112 | Medium | Medium: User specified less than 25% of internal nodes |

Run = contract (v2: secure_jpeg_top, v3: 2 lanes) and mode; activity of one scene frame (vivado/run_vivado_day.py --steps power). Activity from RTL simulation matches only the nets whose names survive synthesis; the rest keep Vivado's default. Still an estimate: the board measurement (GUIDE A4) is the measured number.

### Worst setup paths (block of source -> destination)

| Design | Clock (MHz) | Paths (slack ns: from -> to) |
|---|---|---|
| secure_jpeg_lanes_top_8.0ns_lanes2_log_l1 | 125 | -0.914: g_lane[1].u_lane -> g_lane[0].u_lane; -0.904: g_lane[1].u_lane -> g_lane[1].u_lane; -0.864: g_lane[1].u_lane -> g_lane[0].u_lane; -0.854: g_lane[1].u_lane -> g_lane[1].u_lane; -0.848: g_lane[1].u_lane -> g_lane[0].u_lane |
| secure_jpeg_lanes_top_lanes2_log_l1 | 100 | +0.491: g_lane[1].u_lane -> g_lane[0].u_lane; +0.491: g_lane[1].u_lane -> g_lane[1].u_lane; +0.514: g_lane[1].u_lane -> g_lane[0].u_lane; +0.547: g_lane[1].u_lane -> g_lane[1].u_lane; +0.561: g_lane[1].u_lane -> g_lane[1].u_lane |
| secure_jpeg_lanes_top_lanes4_log_l2_log_maxw10 | 100 | +0.243: g_lane[3].u_lane -> g_lane[2].u_lane; +0.327: g_lane[3].u_lane -> g_lane[2].u_lane; +0.347: g_lane[3].u_lane -> g_lane[2].u_lane; +0.422: g_lane[3].u_lane -> g_lane[0].u_lane; +0.450: g_lane[3].u_lane -> g_lane[1].u_lane |
| secure_jpeg_top | 100 | +0.630: u_conv -> u_conv; +0.761: u_rle -> u_ks; +0.761: u_rle -> u_ks; +0.761: u_rle -> u_ks; +0.800: u_rle -> u_ks |
| secure_jpeg_top_8.0ns | 125 | -0.487: u_conv -> u_conv; -0.403: u_conv -> u_conv; -0.385: u_conv -> u_conv; -0.383: u_conv -> u_conv; -0.345: u_conv -> u_conv |
| overlay | 100 | +0.760: system_i -> system_i; +0.783: system_i -> system_i; +0.790: system_i -> system_i; +0.830: system_i -> system_i; +0.862: system_i -> system_i |
| overlay_lanes | 100 | +0.311: system_i -> system_i; +0.406: system_i -> system_i; +0.422: system_i -> system_i; +0.584: system_i -> system_i; +0.613: system_i -> system_i |

### Resource breakdown: secure_jpeg_lanes_top_8.0ns_lanes2_log_l1

| Block | Module | LUT | FF | BRAM | DSP |
|---|---|---|---|---|---|
| secure_jpeg_lanes_top | (top) | 9650 | 5504 | 52 | 46 |
| &nbsp;&nbsp;(secure_jpeg_lanes_top) | (top) | 4 | 40 | 0 | 0 |
| &nbsp;&nbsp;g_lane[0].u_lane | encoder_lane | 2802 | 1523 | 26 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle_10 | 274 | 110 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_conv | rgb2ycbcr_2px_2 | 147 | 235 | 25 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8_3 | 801 | 69 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc_4 | 85 | 24 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc_6 | 226 | 34 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen_7 | 966 | 851 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer_8 | 218 | 84 | 0 | 0 |
| &nbsp;&nbsp;g_lane[1].u_lane | encoder_lane__parameterized0 | 4088 | 1573 | 26 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle | 274 | 110 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_conv | rgb2ycbcr_2px | 1423 | 284 | 25 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8 | 805 | 69 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc | 82 | 24 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc | 226 | 34 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen | 966 | 851 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer | 219 | 84 | 0 | 0 |
| &nbsp;&nbsp;u_kseg | kseg_unit | 790 | 591 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_kseg) | kseg_unit | 4 | 133 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core_0 | 786 | 458 | 0 | 0 |
| &nbsp;&nbsp;u_merge | segment_merger | 56 | 38 | 0 | 0 |
| &nbsp;&nbsp;u_regs | axil_regs | 552 | 453 | 0 | 0 |
| &nbsp;&nbsp;u_tag | tag_unit | 1336 | 1191 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_tag) | tag_unit | 359 | 605 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core | 977 | 586 | 0 | 0 |
| &nbsp;&nbsp;u_words | scan_word_packer | 24 | 95 | 0 | 0 |

### Resource breakdown: secure_jpeg_lanes_top_lanes2_log_l1

| Block | Module | LUT | FF | BRAM | DSP |
|---|---|---|---|---|---|
| secure_jpeg_lanes_top | (top) | 9528 | 5503 | 52 | 46 |
| &nbsp;&nbsp;(secure_jpeg_lanes_top) | (top) | 4 | 40 | 0 | 0 |
| &nbsp;&nbsp;g_lane[0].u_lane | encoder_lane | 2763 | 1523 | 26 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle_10 | 261 | 110 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_conv | rgb2ycbcr_2px_2 | 147 | 235 | 25 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8_3 | 801 | 69 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc_4 | 82 | 24 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc_6 | 218 | 34 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen_7 | 964 | 851 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer_8 | 208 | 84 | 0 | 0 |
| &nbsp;&nbsp;g_lane[1].u_lane | encoder_lane__parameterized0 | 4003 | 1572 | 26 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle | 263 | 110 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_conv | rgb2ycbcr_2px | 1380 | 283 | 25 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8 | 802 | 69 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc | 82 | 24 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc | 217 | 34 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen | 963 | 851 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer | 208 | 84 | 0 | 0 |
| &nbsp;&nbsp;u_kseg | kseg_unit | 790 | 591 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_kseg) | kseg_unit | 4 | 133 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core_0 | 786 | 458 | 0 | 0 |
| &nbsp;&nbsp;u_merge | segment_merger | 56 | 38 | 0 | 0 |
| &nbsp;&nbsp;u_regs | axil_regs | 554 | 453 | 0 | 0 |
| &nbsp;&nbsp;u_tag | tag_unit | 1337 | 1191 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_tag) | tag_unit | 360 | 605 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core | 978 | 586 | 0 | 0 |
| &nbsp;&nbsp;u_words | scan_word_packer | 24 | 95 | 0 | 0 |

### Resource breakdown: secure_jpeg_lanes_top_lanes4_log_l2_log_maxw10

| Block | Module | LUT | FF | BRAM | DSP |
|---|---|---|---|---|---|
| secure_jpeg_lanes_top | (top) | 16345 | 8523 | 56 | 92 |
| &nbsp;&nbsp;(secure_jpeg_lanes_top) | (top) | 4 | 41 | 0 | 0 |
| &nbsp;&nbsp;g_lane[0].u_lane | encoder_lane | 2757 | 1515 | 14 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle_34 | 264 | 110 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_conv | rgb2ycbcr_2px_26 | 140 | 229 | 13 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8_27 | 804 | 69 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc_28 | 82 | 24 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc_30 | 217 | 34 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen_31 | 963 | 851 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer_32 | 208 | 84 | 0 | 0 |
| &nbsp;&nbsp;g_lane[1].u_lane | encoder_lane__parameterized0 | 2756 | 1516 | 14 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;(g_lane[1].u_lane) | encoder_lane__parameterized0 | 106 | 43 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_conv | rgb2ycbcr_2px_14 | 144 | 229 | 13 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8_15 | 720 | 68 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc_16 | 82 | 24 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc_18 | 217 | 34 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen_19 | 971 | 851 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer_20 | 212 | 84 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle_22 | 258 | 110 | 0 | 0 |
| &nbsp;&nbsp;g_lane[2].u_lane | encoder_lane__parameterized1 | 2763 | 1516 | 14 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle_10 | 264 | 110 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_conv | rgb2ycbcr_2px_2 | 141 | 229 | 13 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8_3 | 803 | 69 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc_4 | 82 | 24 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc_6 | 217 | 34 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen_7 | 962 | 851 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer_8 | 208 | 84 | 0 | 0 |
| &nbsp;&nbsp;g_lane[3].u_lane | encoder_lane__parameterized2 | 5212 | 1565 | 14 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;(g_lane[3].u_lane) | encoder_lane__parameterized2 | 106 | 43 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_conv | rgb2ycbcr_2px | 2598 | 277 | 13 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8 | 724 | 69 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc | 82 | 24 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc | 217 | 34 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen | 970 | 851 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer | 211 | 84 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle | 258 | 110 | 0 | 0 |
| &nbsp;&nbsp;u_kseg | kseg_unit | 790 | 591 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_kseg) | kseg_unit | 4 | 133 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core_0 | 786 | 458 | 0 | 0 |
| &nbsp;&nbsp;u_merge | segment_merger | 68 | 39 | 0 | 0 |
| &nbsp;&nbsp;u_regs | axil_regs | 639 | 454 | 0 | 0 |
| &nbsp;&nbsp;u_tag | tag_unit | 1338 | 1191 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_tag) | tag_unit | 361 | 605 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core | 977 | 586 | 0 | 0 |
| &nbsp;&nbsp;u_words | scan_word_packer | 24 | 95 | 0 | 0 |

### Resource breakdown: secure_jpeg_top

| Block | Module | LUT | FF | BRAM | DSP |
|---|---|---|---|---|---|
| secure_jpeg_top | (top) | 4785 | 3051 | 25.5 | 23 |
| &nbsp;&nbsp;(secure_jpeg_top) | (top) | 0 | 5 | 0 | 0 |
| &nbsp;&nbsp;u_conv | rgb2ycbcr_block | 459 | 220 | 25 | 0 |
| &nbsp;&nbsp;u_dct | dct8x8 | 806 | 69 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_cols | dct_stage__parameterized0 | 506 | 36 | 0 | 11 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rows | dct_stage | 300 | 33 | 0 | 11 |
| &nbsp;&nbsp;u_enc | selective_enc | 82 | 24 | 0 | 0 |
| &nbsp;&nbsp;u_huff | huffman_enc | 268 | 34 | 0 | 0 |
| &nbsp;&nbsp;u_ks | keystream_gen | 949 | 851 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_ks) | keystream_gen | 89 | 266 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core_0 | 860 | 585 | 0 | 0 |
| &nbsp;&nbsp;u_pack | bit_packer | 210 | 84 | 0 | 0 |
| &nbsp;&nbsp;u_regs | axil_regs | 392 | 451 | 0 | 0 |
| &nbsp;&nbsp;u_rle | zigzag_rle | 219 | 110 | 0 | 0 |
| &nbsp;&nbsp;u_tag | tag_unit | 1358 | 1072 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_tag) | tag_unit | 388 | 614 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core | 970 | 458 | 0 | 0 |
| &nbsp;&nbsp;u_words | scan_word_packer | 20 | 95 | 0 | 0 |

### Resource breakdown: secure_jpeg_top_8.0ns

| Block | Module | LUT | FF | BRAM | DSP |
|---|---|---|---|---|---|
| secure_jpeg_top | (top) | 4820 | 3052 | 25.5 | 23 |
| &nbsp;&nbsp;(secure_jpeg_top) | (top) | 0 | 5 | 0 | 0 |
| &nbsp;&nbsp;u_conv | rgb2ycbcr_block | 467 | 221 | 25 | 0 |
| &nbsp;&nbsp;u_dct | dct8x8 | 807 | 69 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_cols | dct_stage__parameterized0 | 506 | 36 | 0 | 11 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rows | dct_stage | 301 | 33 | 0 | 11 |
| &nbsp;&nbsp;u_enc | selective_enc | 82 | 24 | 0 | 0 |
| &nbsp;&nbsp;u_huff | huffman_enc | 278 | 34 | 0 | 0 |
| &nbsp;&nbsp;u_ks | keystream_gen | 950 | 851 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_ks) | keystream_gen | 89 | 266 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core_0 | 861 | 585 | 0 | 0 |
| &nbsp;&nbsp;u_pack | bit_packer | 220 | 84 | 0 | 0 |
| &nbsp;&nbsp;u_regs | axil_regs | 391 | 451 | 0 | 0 |
| &nbsp;&nbsp;u_rle | zigzag_rle | 223 | 110 | 0 | 0 |
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
| system_wrapper | (top) | 12099 | 9026 | 54.5 | 46 |
| &nbsp;&nbsp;system_i | system | 12099 | 9026 | 54.5 | 46 |
| &nbsp;&nbsp;&nbsp;&nbsp;sjpeg | system_sjpeg_0 | 9516 | 5503 | 52 | 46 |
| &nbsp;&nbsp;&nbsp;&nbsp;axi_mem_intercon | system_axi_mem_intercon_0 | 655 | 781 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;dma | system_dma_0 | 1397 | 2033 | 2.5 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;ps7_axi_periph | system_ps7_axi_periph_0 | 514 | 675 | 0 | 0 |

