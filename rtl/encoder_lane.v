// encoder_lane.v -- one complete encoder lane of contract v3 (secure_jpeg_lanes_top.v).
//
//   pixel pairs -> rgb2ycbcr_2px -> dct8x8 -> quantiser -> zigzag_rle (SEG_RESET=1)
//     -> selective_enc (+ keystream_gen keyed by K_seg, restarted per segment)
//     -> huffman_enc -> bit_packer -> byte_fifo -> {byte, segment-last} to the merger
//
// Lane LANE of LANES codes the MCU rows (= restart segments) s = LANE, LANE+LANES, ...
// Everything that makes a segment independent of the others happens here:
//   * the front end marks the last sample of every MCU row with the "last" flag;
//   * zigzag_rle resets its DC predictors after that flag (T.81 restart rule);
//   * the bit packer pads the segment to a byte with 1s and marks its final byte;
//   * the keystream restarts for every segment with nonce (s, frame_ctr) under K_seg.
// The stages between are the contract-v2 blocks, unchanged.
//
// Mode 5 (E5, contract v3 §8.6): every MCU is its own restart segment. The lane ends a segment
// after the 6th block of each MCU (Y0 Y1 Y2 Y3 Cb Cr) instead of after the MCU row, and the
// segment index is the raster MCU index row * cols + col. The encrypted fields are those of E4
// (selective_enc treats mode 5 like mode 4). The ARM permutes the segments afterwards.
//
// Keystream restart (the subtle part). When the encryption stage hands on a segment's last
// symbol, `pend` is set and the lane's keystream window is hidden (ks_avail forced to 0) until the
// generator has restarted with the next segment's nonce, so no bit of segment s can leak into
// segment s + LANES. The restart waits for K_seg (kseg_valid) at the start of a frame.
// Golden model: model/hw.py :: encode_frame_v3()  (the segments with s mod LANES == LANE)
`default_nettype none
module encoder_lane #(
    parameter LANE      = 0,
    parameter LANES     = 2,
    parameter LOG_MAXW  = 11,
    parameter LOG_FIFO  = 11
) (
    input  wire         clk,
    input  wire         rst,
    input  wire         start,
    input  wire [11:0]  width,
    input  wire [7:0]   rows,           // MCU rows of this lane
    input  wire [2:0]   mode,
    input  wire [62:0]  frame_ctr,
    input  wire [127:0] kseg,
    input  wire         kseg_valid,
    input  wire         qt_we,
    input  wire [6:0]   qt_addr,
    input  wire [16:0]  qt_data,
    input  wire         s_valid,
    output wire         s_ready,
    input  wire [63:0]  s_data,
    output wire         o_valid,
    input  wire         o_ready,
    output wire [7:0]   o_data,
    output wire         o_slast         // last byte of a segment
);
    wire prst = rst | start;

    wire       e5 = (mode == 3'd5);
    wire [7:0] cols = width[11:4];          // MCUs per MCU row

    wire       c_valid, c_ready, c_blast, c_rlast;
    wire [7:0] c_data;
    wire [1:0] c_comp;
    rgb2ycbcr_2px #(.LOG_MAXW(LOG_MAXW)) u_conv (
        .clk(clk), .rst(rst), .start(start), .width(width), .rows(rows),
        .s_valid(s_valid), .s_ready(s_ready), .s_data(s_data),
        .m_valid(c_valid), .m_ready(c_ready), .m_data(c_data), .m_comp(c_comp),
        .m_blast(c_blast), .m_flast(c_rlast));

    // segment end at the converter output: the MCU row's last sample, or in E5 every MCU's last
    // sample (the 6th block of the MCU; the row end is always also an MCU end)
    reg  [2:0] blk6;
    always @(posedge clk) begin
        if (rst || start) blk6 <= 3'd0;
        else if (c_valid && c_ready && c_blast) blk6 <= (blk6 == 3'd5) ? 3'd0 : blk6 + 3'd1;
    end
    wire c_slast = e5 ? (c_blast && blk6 == 3'd5) : c_rlast;

    wire               d_valid, d_ready, d_blast, d_slast;
    wire signed [15:0] d_data;
    wire [1:0]         d_comp;
    dct8x8 u_dct (
        .clk(clk), .rst(prst),
        .in_valid(c_valid), .in_ready(c_ready), .in_data(c_data), .in_comp(c_comp), .in_flast(c_slast),
        .out_valid(d_valid), .out_ready(d_ready), .out_data(d_data), .out_comp(d_comp),
        .out_blast(d_blast), .out_flast(d_slast));

    wire               q_valid, q_ready, q_blast, q_slast;
    wire signed [15:0] q_data;
    wire [1:0]         q_comp;
    quantiser u_quant (
        .clk(clk), .rst(prst), .qt_we(qt_we), .qt_addr(qt_addr), .qt_data(qt_data),
        .in_valid(d_valid), .in_ready(d_ready), .in_data(d_data), .in_comp(d_comp),
        .in_blast(d_blast), .in_flast(d_slast),
        .out_valid(q_valid), .out_ready(q_ready), .out_data(q_data), .out_comp(q_comp),
        .out_blast(q_blast), .out_flast(q_slast));

    wire        r_valid, r_ready, r_is_dc, r_eob, r_slast;
    wire [3:0]  r_run, r_size;
    wire [10:0] r_amp;
    wire [1:0]  r_comp;
    zigzag_rle #(.SEG_RESET(1)) u_rle (
        .clk(clk), .rst(rst), .start(start),
        .in_valid(q_valid), .in_ready(q_ready), .in_data(q_data), .in_comp(q_comp),
        .in_blast(q_blast), .in_flast(q_slast),
        .o_valid(r_valid), .o_ready(r_ready), .o_is_dc(r_is_dc), .o_run(r_run),
        .o_size(r_size), .o_amp(r_amp), .o_eob(r_eob), .o_comp(r_comp), .o_flast(r_slast));

    // ------------------------------------------------ per-segment keystream
    // seg = MCU row (modes 0..4) or raster MCU index row * cols + col (E5). The lane codes MCU
    // rows LANE, LANE + LANES, ...; rowbase = row * cols is kept as a running sum, no multiplier.
    reg  [15:0] row, rowbase;
    reg  [7:0]  col;
    reg         wait_k, pend;
    wire        seg_end = r_valid && r_ready && r_slast;
    wire        row_end = seg_end && (!e5 || col == cols - 8'd1);
    wire [15:0] seg     = e5 ? rowbase + {8'd0, col} : row;
    wire        ks_start = (wait_k || pend) && kseg_valid && !seg_end;
    always @(posedge clk) begin
        if (rst || start) begin
            row <= LANE; rowbase <= LANE * {8'd0, cols}; col <= 8'd0;
            wait_k <= 1'b1; pend <= 1'b0;
        end else begin
            if (ks_start) begin wait_k <= 1'b0; pend <= 1'b0; end
            if (seg_end) begin
                pend <= 1'b1;
                col  <= row_end ? 8'd0 : col + 8'd1;
            end
            if (row_end) begin
                row     <= row + LANES;
                rowbase <= rowbase + LANES * {8'd0, cols};
            end
        end
    end

    wire [15:0] ks_bits;
    wire [4:0]  ks_avail_raw, ks_n;
    wire        ks_take;
    keystream_gen u_ks (
        .clk(clk), .rst(rst), .start(ks_start), .key(kseg), .nonce({frame_ctr, 1'b0, 48'd0, seg}),
        .ks_bits(ks_bits), .ks_avail(ks_avail_raw), .ks_take(ks_take), .ks_n(ks_n));
    wire [4:0] ks_avail = (wait_k || pend) ? 5'd0 : ks_avail_raw;

    wire        e_valid, e_ready, e_is_dc, e_eob_unused, e_slast;
    wire [3:0]  e_run, e_size;
    wire [10:0] e_amp;
    wire [1:0]  e_comp;
    selective_enc u_enc (
        .clk(clk), .rst(prst), .mode(mode),
        .ks_bits(ks_bits), .ks_avail(ks_avail), .ks_take(ks_take), .ks_n(ks_n),
        .i_valid(r_valid), .i_ready(r_ready), .i_is_dc(r_is_dc), .i_run(r_run),
        .i_size(r_size), .i_amp(r_amp), .i_eob(r_eob), .i_comp(r_comp), .i_flast(r_slast),
        .o_valid(e_valid), .o_ready(e_ready), .o_is_dc(e_is_dc), .o_run(e_run),
        .o_size(e_size), .o_amp(e_amp), .o_eob(e_eob_unused), .o_comp(e_comp), .o_flast(e_slast));

    wire        h_valid, h_ready, h_slast;
    wire [26:0] h_bits;
    wire [4:0]  h_len;
    huffman_enc u_huff (
        .clk(clk), .rst(prst),
        .i_valid(e_valid), .i_ready(e_ready), .i_is_dc(e_is_dc), .i_run(e_run),
        .i_size(e_size), .i_amp(e_amp), .i_comp(e_comp), .i_flast(e_slast),
        .o_valid(h_valid), .o_ready(h_ready), .o_bits(h_bits), .o_len(h_len), .o_flast(h_slast));

    wire       b_valid, b_ready, b_last;
    wire [7:0] b_data;
    bit_packer u_pack (
        .clk(clk), .rst(prst),
        .i_valid(h_valid), .i_ready(h_ready), .i_bits(h_bits), .i_len(h_len), .i_flast(h_slast),
        .o_valid(b_valid), .o_ready(b_ready), .o_data(b_data), .o_last(b_last));

    wire [8:0] f_data;
    byte_fifo #(.LOG_DEPTH(LOG_FIFO)) u_fifo (
        .clk(clk), .rst(prst),
        .i_valid(b_valid), .i_ready(b_ready), .i_data({b_last, b_data}),
        .o_valid(o_valid), .o_ready(o_ready), .o_data(f_data));
    assign o_data  = f_data[7:0];
    assign o_slast = f_data[8];
endmodule
`default_nettype wire
