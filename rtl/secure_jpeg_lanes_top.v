// secure_jpeg_lanes_top.v -- contract v3 encoder: parallel lanes over restart segments.
//
//  s_axis (2 RGB pixels per beat, 64-bit) -> dealer: MCU row r -> lane r mod LANES
//     lane l: rgb2ycbcr_2px -> dct8x8 -> quantiser -> zigzag_rle -> selective_enc -> huffman_enc
//             -> bit_packer -> byte FIFO                                    (encoder_lane.v)
//  -> segment_merger (segments in order, RST0..7 between them)
//  -> { tag_unit (Ascon MAC over the 26-byte prefix, version 3, + scan), scan_word_packer -> m_axis }
//  kseg_unit derives K_seg once per frame; every lane keys its segment keystreams with it.
//
// Why it is faster (experiments/parallel_lanes.py R2, measured here by tb/test_lanes_top.py):
// one contract-v2 pipeline consumes 1 sample per clock and 4:2:0 has 1.5 samples per pixel, so it
// is capped at 1.5 clocks per pixel (65 Mpx/s at 100 MHz). Two lanes consume 2 samples per clock
// and the 64-bit input brings 2 pixels per clock, so the cap becomes 0.75 clocks per pixel.
// The idea is the one the retina uses (parallel channels that each see part of the image, merged
// later) and the one camera ISPs use (several pixels per clock on a wide stream bus); the JPEG
// restart marker is what makes the parts independent, and it already exists for E5.
//
// Same AXI4-Lite register map as secure_jpeg_top.v (rtl/axil_regs.v), except
//   VERSION = 0x5EC0_03LL (contract v3, LL = LANES) and the input stream is 64 bits wide:
//   tdata[31:0] = left pixel {pad, B, G, R}, tdata[63:32] = right pixel. Width multiple of 16.
//   Modes 0..4 (E5 is contract v2 only). The ARM adds a DRI segment (restart interval =
//   width/16) to the headers (model/hw.py :: build_frame(..., version=3)).
// Golden model: model/hw.py :: encode_frame_v3()  (== model/jpeg.py :: encode_frame(segmented=True))
`default_nettype none
module secure_jpeg_lanes_top #(
    parameter LANES    = 2,             // 1, 2 or 4
    parameter LOG_L    = 1,             // log2(LANES), 1 when LANES = 1
    parameter LOG_MAXW = 11,
    parameter LOG_FIFO = 11             // per-lane output FIFO: 2^LOG_FIFO bytes
) (
    input  wire        clk,
    input  wire        rst,
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
    input  wire [63:0] s_axis_tdata,
    input  wire        s_axis_tvalid,
    output wire        s_axis_tready,
    input  wire        s_axis_tlast,
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

    axil_regs #(.VERSION(32'h5EC0_0300 + LANES)) u_regs (
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
        .done(done), .busy(busy), .tag_valid(tag_valid), .out_bytes(out_bytes), .tag(tag));

    reg [2:0] mode_l;
    always @(posedge clk) if (start) mode_l <= mode;

    wire [127:0] n_enc = {frame_ctr, 1'b0, session_id};
    wire [127:0] n_mac = {frame_ctr, 1'b1, session_id};

    function [63:0] bswap64;
        input [63:0] v;
        integer b;
        begin
            for (b = 0; b < 8; b = b + 1) bswap64[8*b +: 8] = v[8*(7-b) +: 8];
        end
    endfunction
    // as secure_jpeg_top.v, but version byte 3 (model/hw.py :: tag_prefix(..., version=3))
    wire [207:0] tag_prefix = {
        height[7:0], 4'd0, height[11:8], width[7:0], 4'd0, width[11:8],
        bswap64({1'b0, frame_ctr}), bswap64(session_id),
        5'd0, mode, 8'h03, 8'h31, 8'h56, 8'h4A, 8'h53};

    // --------------------------------------------------------- segment key
    wire         kseg_valid;
    wire [127:0] kseg;
    kseg_unit u_kseg (
        .clk(clk), .rst(rst), .start(start), .key(key), .nonce(n_enc),
        .kseg_valid(kseg_valid), .kseg(kseg));

    // ---------------------------------------------------------------- dealer
    // Counts pixel pairs in raster order; MCU row r goes to lane r mod LANES.
    wire [7:0]  mcu_rows = height[11:4];
    reg  [11:0] dx;                     // x of the left pixel of the pair
    reg  [3:0]  dy;                     // line within the MCU row
    reg  [7:0]  drow;                   // MCU row
    wire [LANES-1:0] lane_ready;
    wire [LOG_L-1:0] dlane;
    generate
        if (LANES == 1) begin : g_d1
            assign dlane = 1'b0;
        end else begin : g_dn
            assign dlane = drow[LOG_L-1:0];
        end
    endgenerate
    assign s_axis_tready = lane_ready[dlane];
    wire dtake = s_axis_tvalid && s_axis_tready;
    always @(posedge clk) begin
        if (rst || start) begin
            dx <= 12'd0; dy <= 4'd0; drow <= 8'd0;
        end else if (dtake) begin
            if (dx == width - 12'd2) begin
                dx <= 12'd0;
                dy <= dy + 4'd1;
                if (dy == 4'd15) drow <= drow + 8'd1;
            end else
                dx <= dx + 12'd2;
        end
    end

    // ----------------------------------------------------------------- lanes
    wire [LANES-1:0]   l_valid, l_ready, l_slast;
    wire [8*LANES-1:0] l_data;
    genvar g;
    generate
        for (g = 0; g < LANES; g = g + 1) begin : g_lane
            // MCU rows of lane g: ceil((rows - g) / LANES)
            wire [8:0] rows_g = ({1'b0, mcu_rows} + (LANES - 1 - g)) >> LOG_L;
            encoder_lane #(.LANE(g), .LANES(LANES), .LOG_MAXW(LOG_MAXW), .LOG_FIFO(LOG_FIFO)) u_lane (
                .clk(clk), .rst(rst), .start(start), .width(width),
                .rows(LANES == 1 ? mcu_rows : rows_g[7:0]), .mode(mode_l),
                .frame_ctr(frame_ctr), .kseg(kseg), .kseg_valid(kseg_valid),
                .qt_we(qt_we), .qt_addr(qt_addr), .qt_data(qt_data),
                .s_valid(s_axis_tvalid && (dlane == g)), .s_ready(lane_ready[g]), .s_data(s_axis_tdata),
                .o_valid(l_valid[g]), .o_ready(l_ready[g]), .o_data(l_data[8*g +: 8]),
                .o_slast(l_slast[g]));
        end
    endgenerate

    // ---------------------------------------------------------------- merger
    wire       b_valid, b_ready, b_last;
    wire [7:0] b_data;
    segment_merger #(.LANES(LANES), .LOG_L(LOG_L)) u_merge (
        .clk(clk), .rst(rst), .start(start), .segs(mcu_rows),
        .i_valid(l_valid), .i_ready(l_ready), .i_data(l_data), .i_slast(l_slast),
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
