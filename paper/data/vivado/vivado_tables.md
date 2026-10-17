## Hardware results from Vivado (post-route, xc7z020clg400-1)

| Design | LUT | FF | BRAM | DSP | Clock (MHz) | WNS (ns) | Timing met | Est. fmax (MHz) | Power total / dynamic (W) |
|---|---|---|---|---|---|---|---|---|---|
| secure_jpeg_lanes_top_6.667ns_lanes2_log_l1 | 10198 (19.2%) | 5476 (5.2%) | 49.0 (35.0%) | 46 (20.9%) | 150 | -2.023 | NO | 115.1 | 0.516 / 0.404 |
| secure_jpeg_lanes_top_8.0ns_lanes2_log_l1 | 9989 (18.8%) | 5382 (5.1%) | 50.0 (35.7%) | 46 (20.9%) | 125 | -1.071 | NO | 110.2 | 0.448 / 0.337 |
| secure_jpeg_lanes_top_lanes2_log_l1 | 9869 (18.6%) | 5375 (5.0%) | 50.0 (35.7%) | 46 (20.9%) | 100 | 0.400 | yes | 104.2 | 0.380 / 0.270 |
| secure_jpeg_lanes_top_lanes4_log_l2_log_maxw10 | 16573 (31.1%) | 8303 (7.8%) | 52.0 (37.1%) | 92 (41.8%) | 100 | 0.440 | yes | 104.6 | 0.553 / 0.440 |
| secure_jpeg_top | 5037 (9.5%) | 2950 (2.8%) | 24.5 (17.5%) | 23 (10.4%) | 100 | 0.554 | yes | 105.9 | 0.223 / 0.117 |
| secure_jpeg_top_6.667ns | 5176 (9.7%) | 2958 (2.8%) | 24.0 (17.1%) | 23 (10.4%) | 150 | -1.765 | NO | 118.6 | 0.279 / 0.173 |
| secure_jpeg_top_8.0ns | 5057 (9.5%) | 2954 (2.8%) | 24.5 (17.5%) | 23 (10.4%) | 125 | -0.875 | NO | 112.7 | 0.251 / 0.145 |
| secure_jpeg_top_log_maxw10 | 4871 (9.2%) | 2912 (2.7%) | 12.5 (8.9%) | 23 (10.4%) | 100 | 0.609 | yes | 106.5 | 0.211 / 0.106 |
| secure_jpeg_top_log_maxw9 | 4782 (9.0%) | 2908 (2.7%) | 6.5 (4.6%) | 23 (10.4%) | 100 | 0.733 | yes | 107.9 | 0.204 / 0.099 |
| overlay | 6933 (13.0%) | 5575 (5.2%) | 26.5 (18.9%) | 23 (10.4%) | 100 | 0.788 | yes | 108.6 | 1.799 / 1.657 |
| overlay_lanes | 11716 (22.0%) | 7844 (7.4%) | 52.5 (37.5%) | 46 (20.9%) | 100 | 0.208 | yes | 102.1 | 1.950 / 1.801 |

Power is Vivado's vectorless estimate (confidence shown in power.txt); measure the board for real power.
Est. fmax = 1000 / (period - WNS): a single-run estimate, confirm by re-running at that period.

### Worst setup paths (block of source -> destination)

| Design | Clock (MHz) | Paths (slack ns: from -> to) |
|---|---|---|
| secure_jpeg_lanes_top_6.667ns_lanes2_log_l1 | 150 | -2.023: g_lane[1].u_lane -> g_lane[1].u_lane; -2.018: g_lane[1].u_lane -> g_lane[0].u_lane; -1.902: g_lane[1].u_lane -> g_lane[1].u_lane; -1.845: g_lane[1].u_lane -> g_lane[1].u_lane; -1.799: g_lane[1].u_lane -> g_lane[0].u_lane |
| secure_jpeg_lanes_top_8.0ns_lanes2_log_l1 | 125 | -1.071: g_lane[1].u_lane -> g_lane[0].u_lane; -1.043: g_lane[1].u_lane -> g_lane[1].u_lane; -0.956: g_lane[1].u_lane -> g_lane[1].u_lane; -0.857: g_lane[1].u_lane -> g_lane[1].u_lane; -0.843: g_lane[1].u_lane -> g_lane[0].u_lane |
| secure_jpeg_lanes_top_lanes2_log_l1 | 100 | +0.400: g_lane[1].u_lane -> g_lane[1].u_lane; +0.450: g_lane[1].u_lane -> g_lane[1].u_lane; +0.540: g_lane[1].u_lane -> g_lane[1].u_lane; +0.540: g_lane[1].u_lane -> g_lane[1].u_lane; +0.540: g_lane[1].u_lane -> g_lane[1].u_lane |
| secure_jpeg_lanes_top_lanes4_log_l2_log_maxw10 | 100 | +0.440: g_lane[3].u_lane -> g_lane[0].u_lane; +0.464: g_lane[3].u_lane -> g_lane[3].u_lane; +0.492: g_lane[3].u_lane -> g_lane[0].u_lane; +0.529: g_lane[3].u_lane -> g_lane[0].u_lane; +0.532: g_lane[3].u_lane -> g_lane[2].u_lane |
| secure_jpeg_top | 100 | +0.554: u_conv -> u_conv; +0.799: u_conv -> u_conv; +0.801: u_conv -> u_conv; +0.912: u_conv -> u_conv; +1.008: (top) -> u_pack |
| secure_jpeg_top_6.667ns | 150 | -1.765: u_conv -> u_conv; -1.673: u_conv -> u_conv; -1.661: u_conv -> u_conv; -1.578: u_conv -> u_conv; -1.562: u_conv -> u_conv |
| secure_jpeg_top_8.0ns | 125 | -0.875: u_conv -> u_conv; -0.760: u_conv -> u_conv; -0.666: u_conv -> u_conv; -0.649: u_conv -> u_conv; -0.630: u_conv -> u_conv |
| secure_jpeg_top_log_maxw10 | 100 | +0.609: u_rle -> u_ks; +0.609: u_rle -> u_ks; +0.609: u_rle -> u_ks; +0.609: u_rle -> u_ks; +0.609: u_rle -> u_ks |
| secure_jpeg_top_log_maxw9 | 100 | +0.733: u_conv -> u_conv; +0.742: u_rle -> u_ks; +0.742: u_rle -> u_ks; +0.742: u_rle -> u_ks; +0.742: u_rle -> u_ks |
| overlay | 100 | +0.788: system_i -> system_i; +0.830: system_i -> system_i; +0.848: system_i -> system_i; +0.883: system_i -> system_i; +0.888: system_i -> system_i |
| overlay_lanes | 100 | +0.208: system_i -> system_i; +0.281: system_i -> system_i; +0.286: system_i -> system_i; +0.286: system_i -> system_i; +0.305: system_i -> system_i |

### Resource breakdown: secure_jpeg_lanes_top_6.667ns_lanes2_log_l1

| Block | Module | LUT | FF | BRAM | DSP |
|---|---|---|---|---|---|
| secure_jpeg_lanes_top | (top) | 10198 | 5476 | 49 | 46 |
| &nbsp;&nbsp;(secure_jpeg_lanes_top) | (top) | 3 | 21 | 0 | 0 |
| &nbsp;&nbsp;g_lane[0].u_lane | encoder_lane | 3155 | 1574 | 24.5 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;(g_lane[0].u_lane) | encoder_lane | 22 | 65 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_conv | rgb2ycbcr_2px_2 | 442 | 263 | 24 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8_3 | 804 | 70 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc_4 | 98 | 24 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc_6 | 230 | 34 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen_7 | 952 | 851 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer_8 | 221 | 84 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_quant | quantiser_9 | 90 | 36 | 0 | 1 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle_10 | 274 | 110 | 0 | 0 |
| &nbsp;&nbsp;g_lane[1].u_lane | encoder_lane__parameterized0 | 4443 | 1627 | 24.5 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;(g_lane[1].u_lane) | encoder_lane__parameterized0 | 22 | 65 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_conv | rgb2ycbcr_2px | 1727 | 316 | 24 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8 | 804 | 70 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc | 98 | 24 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc | 230 | 34 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen | 952 | 851 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer | 222 | 84 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_quant | quantiser | 90 | 36 | 0 | 1 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle | 275 | 110 | 0 | 0 |
| &nbsp;&nbsp;u_kseg | kseg_unit | 790 | 591 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_kseg) | kseg_unit | 4 | 133 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core_0 | 786 | 458 | 0 | 0 |
| &nbsp;&nbsp;u_regs | axil_regs | 431 | 356 | 0 | 0 |
| &nbsp;&nbsp;u_tag | tag_unit | 1312 | 1191 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_tag) | tag_unit | 337 | 605 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core | 975 | 586 | 0 | 0 |
| &nbsp;&nbsp;u_words | scan_word_packer | 36 | 95 | 0 | 0 |

### Resource breakdown: secure_jpeg_lanes_top_8.0ns_lanes2_log_l1

| Block | Module | LUT | FF | BRAM | DSP |
|---|---|---|---|---|---|
| secure_jpeg_lanes_top | (top) | 9989 | 5382 | 50 | 46 |
| &nbsp;&nbsp;(secure_jpeg_lanes_top) | (top) | 3 | 21 | 0 | 0 |
| &nbsp;&nbsp;g_lane[0].u_lane | encoder_lane | 3053 | 1526 | 25 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;(g_lane[0].u_lane) | encoder_lane | 23 | 65 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_conv | rgb2ycbcr_2px_2 | 439 | 215 | 24 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8_3 | 805 | 70 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc_4 | 82 | 24 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc_6 | 226 | 34 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen_7 | 950 | 851 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer_8 | 220 | 84 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle_10 | 262 | 110 | 0 | 0 |
| &nbsp;&nbsp;g_lane[1].u_lane | encoder_lane__parameterized0 | 4339 | 1581 | 25 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;(g_lane[1].u_lane) | encoder_lane__parameterized0 | 23 | 65 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_conv | rgb2ycbcr_2px | 1718 | 270 | 24 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8 | 802 | 70 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc | 87 | 24 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc | 225 | 34 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen | 951 | 851 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer | 217 | 84 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle | 269 | 110 | 0 | 0 |
| &nbsp;&nbsp;u_kseg | kseg_unit | 790 | 591 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_kseg) | kseg_unit | 4 | 133 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core_0 | 786 | 458 | 0 | 0 |
| &nbsp;&nbsp;u_regs | axil_regs | 429 | 356 | 0 | 0 |
| &nbsp;&nbsp;u_tag | tag_unit | 1311 | 1191 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_tag) | tag_unit | 336 | 605 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core | 975 | 586 | 0 | 0 |
| &nbsp;&nbsp;u_words | scan_word_packer | 36 | 95 | 0 | 0 |

### Resource breakdown: secure_jpeg_lanes_top_lanes2_log_l1

| Block | Module | LUT | FF | BRAM | DSP |
|---|---|---|---|---|---|
| secure_jpeg_lanes_top | (top) | 9869 | 5375 | 50 | 46 |
| &nbsp;&nbsp;(secure_jpeg_lanes_top) | (top) | 3 | 21 | 0 | 0 |
| &nbsp;&nbsp;g_lane[0].u_lane | encoder_lane | 3019 | 1526 | 25 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;(g_lane[0].u_lane) | encoder_lane | 23 | 65 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_conv | rgb2ycbcr_2px_2 | 436 | 215 | 24 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8_3 | 805 | 70 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc_4 | 82 | 24 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc_6 | 217 | 34 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen_7 | 948 | 851 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer_8 | 208 | 84 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle_10 | 258 | 110 | 0 | 0 |
| &nbsp;&nbsp;g_lane[1].u_lane | encoder_lane__parameterized0 | 4253 | 1574 | 25 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;(g_lane[1].u_lane) | encoder_lane__parameterized0 | 23 | 65 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_conv | rgb2ycbcr_2px | 1669 | 263 | 24 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8 | 805 | 70 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc | 82 | 24 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc | 217 | 34 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen | 948 | 851 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer | 208 | 84 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle | 258 | 110 | 0 | 0 |
| &nbsp;&nbsp;u_kseg | kseg_unit | 790 | 591 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_kseg) | kseg_unit | 4 | 133 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core_0 | 786 | 458 | 0 | 0 |
| &nbsp;&nbsp;u_regs | axil_regs | 429 | 356 | 0 | 0 |
| &nbsp;&nbsp;u_tag | tag_unit | 1311 | 1191 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_tag) | tag_unit | 336 | 605 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core | 975 | 586 | 0 | 0 |
| &nbsp;&nbsp;u_words | scan_word_packer | 36 | 95 | 0 | 0 |

### Resource breakdown: secure_jpeg_lanes_top_lanes4_log_l2_log_maxw10

| Block | Module | LUT | FF | BRAM | DSP |
|---|---|---|---|---|---|
| secure_jpeg_lanes_top | (top) | 16573 | 8303 | 52 | 92 |
| &nbsp;&nbsp;(secure_jpeg_lanes_top) | (top) | 3 | 22 | 0 | 0 |
| &nbsp;&nbsp;g_lane[0].u_lane | encoder_lane | 2868 | 1495 | 13 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;(g_lane[0].u_lane) | encoder_lane | 22 | 64 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_conv | rgb2ycbcr_2px_26 | 291 | 186 | 12 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8_27 | 801 | 69 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc_28 | 82 | 24 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc_30 | 217 | 34 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen_31 | 948 | 851 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer_32 | 208 | 84 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle_34 | 258 | 110 | 0 | 0 |
| &nbsp;&nbsp;g_lane[1].u_lane | encoder_lane__parameterized0 | 2863 | 1494 | 13 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;(g_lane[1].u_lane) | encoder_lane__parameterized0 | 92 | 64 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_conv | rgb2ycbcr_2px_14 | 294 | 186 | 12 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8_15 | 720 | 68 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc_16 | 82 | 24 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc_18 | 217 | 34 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen_19 | 948 | 851 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer_20 | 211 | 84 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle_22 | 253 | 110 | 0 | 0 |
| &nbsp;&nbsp;g_lane[2].u_lane | encoder_lane__parameterized1 | 2873 | 1496 | 13 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;(g_lane[2].u_lane) | encoder_lane__parameterized1 | 22 | 64 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_conv | rgb2ycbcr_2px_2 | 292 | 186 | 12 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8_3 | 806 | 70 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc_4 | 82 | 24 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc_6 | 217 | 34 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen_7 | 948 | 851 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer_8 | 208 | 84 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle_10 | 258 | 110 | 0 | 0 |
| &nbsp;&nbsp;g_lane[3].u_lane | encoder_lane__parameterized2 | 5319 | 1542 | 13 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;(g_lane[3].u_lane) | encoder_lane__parameterized2 | 93 | 64 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_conv | rgb2ycbcr_2px | 2745 | 234 | 12 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_dct | dct8x8 | 722 | 68 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_enc | selective_enc | 82 | 24 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_huff | huffman_enc | 217 | 34 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_ks | keystream_gen | 948 | 851 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_pack | bit_packer | 212 | 84 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rle | zigzag_rle | 253 | 110 | 0 | 0 |
| &nbsp;&nbsp;u_kseg | kseg_unit | 790 | 591 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_kseg) | kseg_unit | 4 | 133 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core_0 | 786 | 458 | 0 | 0 |
| &nbsp;&nbsp;u_regs | axil_regs | 447 | 356 | 0 | 0 |
| &nbsp;&nbsp;u_tag | tag_unit | 1319 | 1191 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_tag) | tag_unit | 344 | 605 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core | 975 | 586 | 0 | 0 |
| &nbsp;&nbsp;u_words | scan_word_packer | 52 | 95 | 0 | 0 |

### Resource breakdown: secure_jpeg_top

| Block | Module | LUT | FF | BRAM | DSP |
|---|---|---|---|---|---|
| secure_jpeg_top | (top) | 5037 | 2950 | 24.5 | 23 |
| &nbsp;&nbsp;(secure_jpeg_top) | (top) | 0 | 5 | 0 | 0 |
| &nbsp;&nbsp;u_conv | rgb2ycbcr_block | 762 | 215 | 24 | 0 |
| &nbsp;&nbsp;u_dct | dct8x8 | 806 | 69 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_cols | dct_stage__parameterized0 | 505 | 36 | 0 | 11 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rows | dct_stage | 301 | 33 | 0 | 11 |
| &nbsp;&nbsp;u_enc | selective_enc | 82 | 24 | 0 | 0 |
| &nbsp;&nbsp;u_huff | huffman_enc | 268 | 34 | 0 | 0 |
| &nbsp;&nbsp;u_ks | keystream_gen | 950 | 851 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_ks) | keystream_gen | 89 | 266 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core_0 | 861 | 585 | 0 | 0 |
| &nbsp;&nbsp;u_pack | bit_packer | 211 | 84 | 0 | 0 |
| &nbsp;&nbsp;u_regs | axil_regs | 351 | 355 | 0 | 0 |
| &nbsp;&nbsp;u_rle | zigzag_rle | 219 | 110 | 0 | 0 |
| &nbsp;&nbsp;u_tag | tag_unit | 1345 | 1072 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_tag) | tag_unit | 376 | 614 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core | 969 | 458 | 0 | 0 |
| &nbsp;&nbsp;u_words | scan_word_packer | 22 | 95 | 0 | 0 |

### Resource breakdown: secure_jpeg_top_6.667ns

| Block | Module | LUT | FF | BRAM | DSP |
|---|---|---|---|---|---|
| secure_jpeg_top | (top) | 5176 | 2958 | 24 | 23 |
| &nbsp;&nbsp;(secure_jpeg_top) | (top) | 0 | 5 | 0 | 0 |
| &nbsp;&nbsp;u_conv | rgb2ycbcr_block | 777 | 223 | 24 | 0 |
| &nbsp;&nbsp;u_dct | dct8x8 | 806 | 69 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_cols | dct_stage__parameterized0 | 505 | 36 | 0 | 11 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rows | dct_stage | 301 | 33 | 0 | 11 |
| &nbsp;&nbsp;u_enc | selective_enc | 92 | 24 | 0 | 0 |
| &nbsp;&nbsp;u_huff | huffman_enc | 283 | 34 | 0 | 0 |
| &nbsp;&nbsp;u_ks | keystream_gen | 955 | 851 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_ks) | keystream_gen | 92 | 266 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core_0 | 863 | 585 | 0 | 0 |
| &nbsp;&nbsp;u_pack | bit_packer | 224 | 84 | 0 | 0 |
| &nbsp;&nbsp;u_quant | quantiser | 92 | 36 | 0 | 1 |
| &nbsp;&nbsp;u_regs | axil_regs | 352 | 355 | 0 | 0 |
| &nbsp;&nbsp;u_rle | zigzag_rle | 230 | 110 | 0 | 0 |
| &nbsp;&nbsp;u_tag | tag_unit | 1345 | 1072 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_tag) | tag_unit | 376 | 614 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core | 969 | 458 | 0 | 0 |
| &nbsp;&nbsp;u_words | scan_word_packer | 22 | 95 | 0 | 0 |

### Resource breakdown: secure_jpeg_top_8.0ns

| Block | Module | LUT | FF | BRAM | DSP |
|---|---|---|---|---|---|
| secure_jpeg_top | (top) | 5057 | 2954 | 24.5 | 23 |
| &nbsp;&nbsp;(secure_jpeg_top) | (top) | 0 | 5 | 0 | 0 |
| &nbsp;&nbsp;u_conv | rgb2ycbcr_block | 773 | 219 | 24 | 0 |
| &nbsp;&nbsp;u_dct | dct8x8 | 805 | 69 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_cols | dct_stage__parameterized0 | 505 | 36 | 0 | 11 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rows | dct_stage | 300 | 33 | 0 | 11 |
| &nbsp;&nbsp;u_enc | selective_enc | 82 | 24 | 0 | 0 |
| &nbsp;&nbsp;u_huff | huffman_enc | 268 | 34 | 0 | 0 |
| &nbsp;&nbsp;u_ks | keystream_gen | 951 | 851 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_ks) | keystream_gen | 90 | 266 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core_0 | 861 | 585 | 0 | 0 |
| &nbsp;&nbsp;u_pack | bit_packer | 216 | 84 | 0 | 0 |
| &nbsp;&nbsp;u_regs | axil_regs | 349 | 355 | 0 | 0 |
| &nbsp;&nbsp;u_rle | zigzag_rle | 221 | 110 | 0 | 0 |
| &nbsp;&nbsp;u_tag | tag_unit | 1346 | 1072 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_tag) | tag_unit | 377 | 614 | 0 | 0 |
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

### Resource breakdown: overlay

| Block | Module | LUT | FF | BRAM | DSP |
|---|---|---|---|---|---|
| system_wrapper | (top) | 6933 | 5575 | 26.5 | 23 |
| &nbsp;&nbsp;system_i | system | 6933 | 5575 | 26.5 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;sjpeg | system_sjpeg_0 | 5001 | 2950 | 24.5 | 23 |
| &nbsp;&nbsp;&nbsp;&nbsp;axi_mem_intercon | system_axi_mem_intercon_0 | 202 | 315 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;dma | system_dma_0 | 1199 | 1601 | 2 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;ps7_axi_periph | system_ps7_axi_periph_0 | 514 | 675 | 0 | 0 |

### Resource breakdown: overlay_lanes

| Block | Module | LUT | FF | BRAM | DSP |
|---|---|---|---|---|---|
| system_wrapper | (top) | 11716 | 7844 | 52.5 | 46 |
| &nbsp;&nbsp;system_i | system | 11716 | 7844 | 52.5 | 46 |
| &nbsp;&nbsp;&nbsp;&nbsp;sjpeg | system_sjpeg_0 | 9886 | 5375 | 50 | 46 |
| &nbsp;&nbsp;&nbsp;&nbsp;axi_mem_intercon | system_axi_mem_intercon_0 | 43 | 89 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;dma | system_dma_0 | 1256 | 1671 | 2.5 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;ps7_axi_periph | system_ps7_axi_periph_0 | 515 | 675 | 0 | 0 |

