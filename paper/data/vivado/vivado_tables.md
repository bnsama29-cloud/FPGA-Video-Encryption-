## Hardware results from Vivado (post-route, xc7z020clg400-1)

| Design | LUT | FF | BRAM | DSP | Clock (MHz) | WNS (ns) | Timing met | Est. fmax (MHz) | Power total / dynamic (W) |
|---|---|---|---|---|---|---|---|---|---|
| secure_jpeg_top | 5039 (9.5%) | 2911 (2.7%) | 24.5 (17.5%) | 23 (10.4%) | 100 | 0.045 | yes | 100.5 | 0.221 / 0.116 |

Power is Vivado's vectorless estimate (confidence shown in power.txt); measure the board for real power.
Est. fmax = 1000 / (period - WNS): a single-run estimate, confirm by re-running at that period.

### Resource breakdown: secure_jpeg_top

| Block | Module | LUT | FF | BRAM | DSP |
|---|---|---|---|---|---|
| secure_jpeg_top | (top) | 5039 | 2911 | 24.5 | 23 |
| &nbsp;&nbsp;(secure_jpeg_top) | (top) | 0 | 5 | 0 | 0 |
| &nbsp;&nbsp;u_conv | rgb2ycbcr_block | 759 | 199 | 24 | 0 |
| &nbsp;&nbsp;u_dct | dct8x8 | 806 | 68 | 0 | 22 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_cols | dct_stage__parameterized0 | 505 | 35 | 0 | 11 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_rows | dct_stage | 301 | 33 | 0 | 11 |
| &nbsp;&nbsp;u_enc | selective_enc | 82 | 24 | 0 | 0 |
| &nbsp;&nbsp;u_huff | huffman_enc | 268 | 34 | 0 | 0 |
| &nbsp;&nbsp;u_ks | keystream_gen | 952 | 851 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_ks) | keystream_gen | 92 | 266 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core_0 | 860 | 585 | 0 | 0 |
| &nbsp;&nbsp;u_pack | bit_packer | 211 | 84 | 0 | 0 |
| &nbsp;&nbsp;u_regs | axil_regs | 348 | 355 | 0 | 0 |
| &nbsp;&nbsp;u_rle | zigzag_rle | 226 | 88 | 0 | 0 |
| &nbsp;&nbsp;u_tag | tag_unit | 1345 | 1072 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;(u_tag) | tag_unit | 376 | 614 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;u_core | ascon_aead128_core | 969 | 458 | 0 | 0 |
| &nbsp;&nbsp;u_words | scan_word_packer | 22 | 95 | 0 | 0 |

