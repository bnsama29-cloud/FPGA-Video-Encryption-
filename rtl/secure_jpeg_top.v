// secure_jpeg_top.v -- complete fabric datapath of the secure JPEG/MJPEG encoder.
//
//  s_axis (RGB pixels from DMA) -> rgb2ycbcr_block -> dct8x8 -> quantiser
//    -> zigzag_rle -> selective_enc (+ keystream_gen) -> huffman_enc -> bit_packer
//    -> { tag_unit (Ascon MAC over 26-byte header prefix + scan bytes),
//         scan_word_packer -> m_axis (DMA) }
//  s_axil: register file (axil_regs.v) for the ARM.
//
// Per frame (what the PYNQ Python does): write WIDTH/HEIGHT/FRAME_CTR(_HI)/
// SESSION_ID(_HI)/KEY (key once per session), write CTRL = start | mode<<1, start
// both DMA channels, wait for STATUS.DONE, read OUT_BYTES and TAG0..3.
// Golden model: model/hw.py :: encode_frame()  (== model/jpeg.py :: encode_frame)
`default_nettype none
module secure_jpeg_top #(
    parameter LOG_MAXW = 11
) (
    input  wire        clk,
    input  wire        rst,
    // AXI4-Lite control
    input  wire [7:0]  s_axil_awaddr,
    input  wire [2:0]  s_axil_awprot,
    input  wire        s_axil_awvalid,
    output wire        s_axil_awready,
    input  wire [31:0] s_axil_wdata,
    input  wire [3:0]  s_axil_wstrb,
    input  wire        s_axil_wvalid,
    output wire        s_axil_wready,
    output wire [1:0]  s_axil_bresp,
    output wire        s_axil_bvalid,
    input  wire        s_axil_bready,
    input  wire [7:0]  s_axil_araddr,
    input  wire [2:0]  s_axil_arprot,
    input  wire        s_axil_arvalid,
    output wire        s_axil_arready,
    output wire [31:0] s_axil_rdata,
    output wire [1:0]  s_axil_rresp,
    output wire        s_axil_rvalid,
    input  wire        s_axil_rready,
    // AXI4-Stream pixels in: {pad, B, G, R}
    input  wire [31:0] s_axis_tdata,
    input  wire        s_axis_tvalid,
    output wire        s_axis_tready,
    input  wire        s_axis_tlast,
    // AXI4-Stream scan data out
    output wire [31:0] m_axis_tdata,
    output wire [3:0]  m_axis_tkeep,
    output wire        m_axis_tvalid,
    input  wire        m_axis_tready,
    output wire        m_axis_tlast,
    output wire        irq_done
);
    // ------------------------------------------------------------ registers
    wire         start;
    wire [2:0]   mode;
    wire [11:0]  width, height;
    wire [62:0]  frame_ctr;
    wire [63:0]  session_id;
    wire [31:0]  out_bytes;
    wire [127:0] key, tag;
    wire         qt_we, tag_valid;
    wire [6:0]   qt_addr;
    wire [16:0]  qt_data;
    reg          busy, scan_done;
    wire         done = scan_done && tag_valid;
    assign irq_done = done;

    axil_regs u_regs (
        .clk(clk), .rst(rst),
        .s_axil_awaddr(s_axil_awaddr), .s_axil_awprot(s_axil_awprot),
        .s_axil_awvalid(s_axil_awvalid), .s_axil_awready(s_axil_awready),
        .s_axil_wdata(s_axil_wdata), .s_axil_wstrb(s_axil_wstrb),
        .s_axil_wvalid(s_axil_wvalid), .s_axil_wready(s_axil_wready),
        .s_axil_bresp(s_axil_bresp), .s_axil_bvalid(s_axil_bvalid), .s_axil_bready(s_axil_bready),
        .s_axil_araddr(s_axil_araddr), .s_axil_arprot(s_axil_arprot),
        .s_axil_arvalid(s_axil_arvalid), .s_axil_arready(s_axil_arready),
        .s_axil_rdata(s_axil_rdata), .s_axil_rresp(s_axil_rresp),
        .s_axil_rvalid(s_axil_rvalid), .s_axil_rready(s_axil_rready),
        .start(start), .mode(mode), .width(width), .height(height),
        .frame_ctr(frame_ctr), .session_id(session_id), .key(key),
        .qt_we(qt_we), .qt_addr(qt_addr), .qt_data(qt_data),
        .done(done), .busy(busy), .tag_valid(tag_valid), .out_bytes(out_bytes), .tag(tag),
        .in_wait(busy && s_axis_tready && !s_axis_tvalid), .out_stall(m_axis_tvalid && !m_axis_tready));

    wire prst = rst | start;                  // pipeline stages restart per frame
    reg  [2:0] mode_l;                        // mode latched for the whole frame
    always @(posedge clk) if (start) mode_l <= mode;

    // nonces (contract v2): bytes 0..7 = session_id LE, bytes 8..15 =
    // (frame_ctr << 1 | purpose) LE  ->  Ascon state x3 = session_id,
    // x4 = {frame_ctr, purpose}.  purpose 0 = keystream, 1 = tag.
    wire [127:0] n_enc = {frame_ctr, 1'b0, session_id};
    wire [127:0] n_mac = {frame_ctr, 1'b1, session_id};

    // 26-byte tag AD prefix = APP11 metadata + frame size, byte 0 in [7:0]:
    //   'S' 'J' 'V' '1', version 2, mode, session_id (8 B, big-endian),
    //   frame_ctr (8 B, big-endian), width (2 B BE), height (2 B BE)
    // Golden model: model/hw.py :: tag_prefix()
    function [63:0] bswap64;
        input [63:0] v;
        integer b;
        begin
            for (b = 0; b < 8; b = b + 1) bswap64[8*b +: 8] = v[8*(7-b) +: 8];
        end
    endfunction
    wire [207:0] tag_prefix = {
        height[7:0], 4'd0, height[11:8], width[7:0], 4'd0, width[11:8],
        bswap64({1'b0, frame_ctr}), bswap64(session_id),
        5'd0, mode, 8'h02, 8'h31, 8'h56, 8'h4A, 8'h53};

    // ------------------------------------------------------- colour + blocks
    wire       c_valid, c_ready, c_blast_unused, c_flast;
    wire [7:0] c_data;
    wire [1:0] c_comp;
    rgb2ycbcr_block #(.LOG_MAXW(LOG_MAXW)) u_conv (
        .clk(clk), .rst(rst), .start(start), .width(width), .height(height),
        .s_valid(s_axis_tvalid), .s_ready(s_axis_tready), .s_data(s_axis_tdata),
        .m_valid(c_valid), .m_ready(c_ready), .m_data(c_data), .m_comp(c_comp),
        .m_blast(c_blast_unused), .m_flast(c_flast));

    // ------------------------------------------------------------------ DCT
    wire               d_valid, d_ready, d_blast, d_flast;
    wire signed [15:0] d_data;
    wire [1:0]         d_comp;
    dct8x8 u_dct (
        .clk(clk), .rst(prst),
        .in_valid(c_valid), .in_ready(c_ready), .in_data(c_data), .in_comp(c_comp), .in_flast(c_flast),
        .out_valid(d_valid), .out_ready(d_ready), .out_data(d_data), .out_comp(d_comp),
        .out_blast(d_blast), .out_flast(d_flast));

    // ------------------------------------------------------------ quantiser
    wire               q_valid, q_ready, q_blast, q_flast;
    wire signed [15:0] q_data;
    wire [1:0]         q_comp;
    quantiser u_quant (
        .clk(clk), .rst(prst), .qt_we(qt_we), .qt_addr(qt_addr), .qt_data(qt_data),
        .in_valid(d_valid), .in_ready(d_ready), .in_data(d_data), .in_comp(d_comp),
        .in_blast(d_blast), .in_flast(d_flast),
        .out_valid(q_valid), .out_ready(q_ready), .out_data(q_data), .out_comp(q_comp),
        .out_blast(q_blast), .out_flast(q_flast));

    // -------------------------------------------------- zig-zag + run-length
    wire        r_valid, r_ready, r_is_dc, r_eob, r_flast;
    wire [3:0]  r_run, r_size;
    wire [10:0] r_amp;
    wire [1:0]  r_comp;
    zigzag_rle u_rle (
        .clk(clk), .rst(rst), .start(start),
        .in_valid(q_valid), .in_ready(q_ready), .in_data(q_data), .in_comp(q_comp),
        .in_blast(q_blast), .in_flast(q_flast),
        .o_valid(r_valid), .o_ready(r_ready), .o_is_dc(r_is_dc), .o_run(r_run),
        .o_size(r_size), .o_amp(r_amp), .o_eob(r_eob), .o_comp(r_comp), .o_flast(r_flast));

    // ------------------------------------------------ selective encryption
    wire [15:0] ks_bits;
    wire [4:0]  ks_avail, ks_n;
    wire        ks_take;
    keystream_gen u_ks (
        .clk(clk), .rst(rst), .start(start), .key(key), .nonce(n_enc),
        .ks_bits(ks_bits), .ks_avail(ks_avail), .ks_take(ks_take), .ks_n(ks_n));

    wire        e_valid, e_ready, e_is_dc, e_eob_unused, e_flast;
    wire [3:0]  e_run, e_size;
    wire [10:0] e_amp;
    wire [1:0]  e_comp;
    selective_enc u_enc (
        .clk(clk), .rst(prst), .mode(mode_l),
        .ks_bits(ks_bits), .ks_avail(ks_avail), .ks_take(ks_take), .ks_n(ks_n),
        .i_valid(r_valid), .i_ready(r_ready), .i_is_dc(r_is_dc), .i_run(r_run),
        .i_size(r_size), .i_amp(r_amp), .i_eob(r_eob), .i_comp(r_comp), .i_flast(r_flast),
        .o_valid(e_valid), .o_ready(e_ready), .o_is_dc(e_is_dc), .o_run(e_run),
        .o_size(e_size), .o_amp(e_amp), .o_eob(e_eob_unused), .o_comp(e_comp), .o_flast(e_flast));

    // -------------------------------------------------- Huffman + bit packer
    wire        h_valid, h_ready, h_flast;
    wire [26:0] h_bits;
    wire [4:0]  h_len;
    huffman_enc u_huff (
        .clk(clk), .rst(prst),
        .i_valid(e_valid), .i_ready(e_ready), .i_is_dc(e_is_dc), .i_run(e_run),
        .i_size(e_size), .i_amp(e_amp), .i_comp(e_comp), .i_flast(e_flast),
        .o_valid(h_valid), .o_ready(h_ready), .o_bits(h_bits), .o_len(h_len), .o_flast(h_flast));

    wire       b_valid, b_ready, b_last;
    wire [7:0] b_data;
    bit_packer u_pack (
        .clk(clk), .rst(prst),
        .i_valid(h_valid), .i_ready(h_ready), .i_bits(h_bits), .i_len(h_len), .i_flast(h_flast),
        .o_valid(b_valid), .o_ready(b_ready), .o_data(b_data), .o_last(b_last));

    // ---------------------------------- fork scan bytes to tag + DMA output
    wire t_ready, w_ready;
    assign b_ready = t_ready && w_ready;

    tag_unit #(.PREFIX_BYTES(26)) u_tag (
        .clk(clk), .rst(rst), .start(start), .key(key), .nonce(n_mac), .ad_prefix(tag_prefix),
        .ad_valid(b_valid && w_ready), .ad_ready(t_ready), .ad_data(b_data), .ad_last(b_last),
        .tag_valid(tag_valid), .tag(tag));

    scan_word_packer u_words (
        .clk(clk), .rst(rst), .start(start),
        .i_valid(b_valid && t_ready), .i_ready(w_ready), .i_data(b_data), .i_last(b_last),
        .m_tvalid(m_axis_tvalid), .m_tready(m_axis_tready), .m_tdata(m_axis_tdata),
        .m_tkeep(m_axis_tkeep), .m_tlast(m_axis_tlast), .out_bytes(out_bytes));

    // ---------------------------------------------------------------- status
    always @(posedge clk) begin
        if (rst) begin
            busy <= 1'b0; scan_done <= 1'b0;
        end else if (start) begin
            busy <= 1'b1; scan_done <= 1'b0;
        end else begin
            if (m_axis_tvalid && m_axis_tready && m_axis_tlast) scan_done <= 1'b1;
            if (done) busy <= 1'b0;
        end
    end
endmodule
`default_nettype wire
