// rgb2ycbcr_2px.v -- one encoder lane's front end for contract v3: BT.601 RGB->YCbCr, 4:2:0 chroma
// averaging and 8x8 blocking, taking TWO pixels per clock.
//
// In : raster-order pixel PAIRS, 64-bit {pad, B1, G1, R1, pad, B0, G0, R0}; pixel 0 (bits 31:0) is
//      the left one (even x). Only the MCU rows this lane owns arrive here (the dealer in
//      secure_jpeg_lanes_top.v sends MCU row r to lane r mod LANES), `rows` of them.
// Out: 8-bit samples, 64 per block row-major, blocks per MCU: Y0 Y1 Y2 Y3 Cb Cr (as rgb2ycbcr_block.v).
//      m_comp = 0/1/2, m_blast on the last sample of each block, m_flast on the last sample of the
//      last block of EVERY MCU row: in contract v3 an MCU row is one restart segment, and the
//      downstream stages already treat that flag as "flush and restart" (bit_packer pads the byte,
//      zigzag_rle with SEG_RESET=1 resets the DC predictors).
// Why two pixels per clock: the lanes downstream consume 1 sample per clock each, and 4:2:0 has
// 1.5 samples per pixel, so a lane needs 1.5 clocks per pixel. With 1 pixel per clock in, the
// input alone would cap the whole encoder at 1 clock per pixel however many lanes there are
// (experiments/parallel_lanes.py, R2). Two pixels per clock lets two lanes reach 0.75 clocks/pixel.
// Same pipeline as rgb2ycbcr_block.v (bug #20: D1 -> P products -> C sums -> D2 clamp -> D3 buffer write),
// duplicated for the two pixels. The Y line buffer is split into an even-x and an odd-x bank so
// both pixels are written in one clock; the chroma pair (x, x+1) arrives in the same beat, so the
// horizontal sum needs no "previous pixel" register.
// width must be a multiple of 16, width <= 2^LOG_MAXW.
// Golden model: model/hw.py :: rgb_to_ycbcr(), planes(), blocks_in_hw_order()  (rows of one lane)
`default_nettype none
module rgb2ycbcr_2px #(
    parameter LOG_MAXW = 11
) (
    input  wire        clk,
    input  wire        rst,
    input  wire        start,
    input  wire [11:0] width,
    input  wire [7:0]  rows,                 // MCU rows this lane receives in this frame (may be 0)
    input  wire        s_valid,
    output wire        s_ready,
    input  wire [63:0] s_data,
    output reg         m_valid,
    input  wire        m_ready,
    output wire [7:0]  m_data,
    output reg  [1:0]  m_comp,
    output reg         m_blast,
    output reg         m_flast
);
    localparam MAXW = 1 << LOG_MAXW;
    localparam LH = LOG_MAXW - 1;            // bits of x/2

    // ------------------------------------------------------------ write pipeline
    // D3 (21 Oct 2026, for 125 MHz): pair sums and row-sum reads registered, all buffer writes one clock
    // later (same order, same contents; a row sum is read one line after it is written).
    // P (21 Oct 2026, run 8: the multiply-add D1 -> C failed 125 MHz by 0.914 ns): products registered
    // first, C only adds them. Same integers, one clock more latency.
    reg              d1_v, p_v, c_v, d2_v, d3_v;
    reg              p_sel, p_last;
    reg [3:0]        p_y;
    reg [LH-1:0]     p_x;
    reg signed [18:0] p0 [0:8], p1 [0:8];
    integer k;  // per pixel: 77r 150g 29b, -43r -85g 128b, 128r -107g -21b
    reg              d3_sel, d3_last;
    reg [3:0]        d3_y;
    reg [LH-1:0]     d3_x;
    reg [7:0]        d3_y0, d3_y1;
    reg [9:0]        d3_cbp, d3_crp, d3_cbs, d3_crs;
    reg [23:0]       d1_rgb0, d1_rgb1;
    reg              d1_sel, c_sel, d2_sel, d1_last, c_last, d2_last;
    reg [3:0]        d1_y, c_y, d2_y;
    reg [LH-1:0]     d1_x, c_x, d2_x;        // x/2 of the pair
    reg signed [18:0] c_yt0, c_cbt0, c_crt0, c_yt1, c_cbt1, c_crt1;
    reg [7:0]        d2_y0, d2_cb0, d2_cr0, d2_y1, d2_cb1, d2_cr1;

    function signed [18:0] prod;             // product k of pixel p (the nine constant multiplies)
        input [23:0] p; input [3:0] k;
        reg signed [9:0] r, g, b;
        begin
            r = $signed({2'b0, p[7:0]}); g = $signed({2'b0, p[15:8]}); b = $signed({2'b0, p[23:16]});
            case (k)
                4'd0: prod = 77 * r;   4'd1: prod = 150 * g;  4'd2: prod = 29 * b;
                4'd3: prod = -43 * r;  4'd4: prod = -85 * g;  4'd5: prod = 128 * b;
                4'd6: prod = 128 * r;  4'd7: prod = -107 * g; default: prod = -21 * b;
            endcase
        end
    endfunction
    function [7:0] sat8;                     // (v >> 8) clamped to 0..255
        input signed [18:0] v;
        begin
            if (v < 0)               sat8 = 8'd0;
            else if (v[18:8] > 255)  sat8 = 8'd255;
            else                     sat8 = v[15:8];
        end
    endfunction

    // ------------------------------------------------------------- line buffers
    reg [7:0] ybuf_e [0:2*16*(MAXW/2)-1];    // {sel, row[3:0], x/2}, even x
    reg [7:0] ybuf_o [0:2*16*(MAXW/2)-1];    // odd x
    reg [7:0] cbbuf  [0:2*8*(MAXW/2)-1];     // {sel, row[2:0], x/2}
    reg [7:0] crbuf  [0:2*8*(MAXW/2)-1];
    reg [9:0] cbsum  [0:MAXW/2-1];           // even-line pair sums
    reg [9:0] crsum  [0:MAXW/2-1];

    reg [1:0]  full;
    reg        wsel, rsel;
    reg [11:0] wx;                           // x of the left pixel (even)
    reg [3:0]  wy;
    reg [7:0]  wrow;
    reg        wactive;

    assign s_ready = wactive && !full[wsel];
    wire take = s_valid && s_ready;
    wire last_px_of_row = (wx == width - 12'd2) && (wy == 4'd15);

    wire [9:0] cb_pair = d2_cb0 + d2_cb1;
    wire [9:0] cr_pair = d2_cr0 + d2_cr1;
    wire [9:0] cb_avg  = (d3_cbs + d3_cbp + 10'd2) >> 2;
    wire [9:0] cr_avg  = (d3_crs + d3_crp + 10'd2) >> 2;

    always @(posedge clk) begin
        d1_rgb0 <= s_data[23:0]; d1_rgb1 <= s_data[55:32];
        d1_sel <= wsel; d1_y <= wy; d1_x <= wx[LOG_MAXW-1:1]; d1_last <= last_px_of_row;
        for (k = 0; k < 9; k = k + 1) begin
            p0[k] <= prod(d1_rgb0, k); p1[k] <= prod(d1_rgb1, k);
        end
        p_sel <= d1_sel; p_y <= d1_y; p_x <= d1_x; p_last <= d1_last;
        c_yt0  <= p0[0] + p0[1] + p0[2] + 19'sd128;
        c_cbt0 <= p0[3] + p0[4] + p0[5] + 19'sd32896;
        c_crt0 <= p0[6] + p0[7] + p0[8] + 19'sd32896;
        c_yt1  <= p1[0] + p1[1] + p1[2] + 19'sd128;
        c_cbt1 <= p1[3] + p1[4] + p1[5] + 19'sd32896;
        c_crt1 <= p1[6] + p1[7] + p1[8] + 19'sd32896;
        c_sel <= p_sel; c_y <= p_y; c_x <= p_x; c_last <= p_last;
        d2_y0 <= sat8(c_yt0); d2_cb0 <= sat8(c_cbt0); d2_cr0 <= sat8(c_crt0);
        d2_y1 <= sat8(c_yt1); d2_cb1 <= sat8(c_cbt1); d2_cr1 <= sat8(c_crt1);
        d2_sel <= c_sel; d2_y <= c_y; d2_x <= c_x; d2_last <= c_last;
        d3_sel <= d2_sel; d3_y <= d2_y; d3_x <= d2_x; d3_last <= d2_last; d3_y0 <= d2_y0; d3_y1 <= d2_y1;
        d3_cbp <= cb_pair; d3_crp <= cr_pair; d3_cbs <= cbsum[d2_x]; d3_crs <= crsum[d2_x];
        if (d3_v) begin
            ybuf_e[{d3_sel, d3_y, d3_x}] <= d3_y0;
            ybuf_o[{d3_sel, d3_y, d3_x}] <= d3_y1;
            if (!d3_y[0]) begin
                cbsum[d3_x] <= d3_cbp; crsum[d3_x] <= d3_crp;
            end else begin
                cbbuf[{d3_sel, d3_y[3:1], d3_x}] <= cb_avg[7:0];
                crbuf[{d3_sel, d3_y[3:1], d3_x}] <= cr_avg[7:0];
            end
        end
    end

    // ------------------------------------------------------------------ reader
    reg [7:0]  rmcu;
    reg [2:0]  rblk;
    reg [5:0]  rpos;
    reg [7:0]  yeq, yoq, cbq, crq;
    reg        yodd;
    wire [7:0] mcus_per_row = width[11:4];
    wire       rd_go  = full[rsel] && (!m_valid || m_ready);
    wire       last_s = (rpos == 6'd63);
    wire       last_b = last_s && (rblk == 3'd5);
    wire       last_m = last_b && (rmcu == mcus_per_row - 8'd1);

    wire [3:0]    yrow = {rblk[1], rpos[5:3]};
    wire [LH-1:0] ycol = {rmcu, rblk[0], rpos[2:1]};      // x/2 of the Y sample
    wire [LH-1:0] ccol = {rmcu, rpos[2:0]};
    wire [7:0]    yq   = yodd ? yoq : yeq;
    assign m_data = (m_comp == 2'd0) ? yq : (m_comp == 2'd1) ? cbq : crq;

    always @(posedge clk) begin
        if (rst || start) begin
            full <= 2'b00; wsel <= 1'b0; rsel <= 1'b0;
            wx <= 12'd0; wy <= 4'd0; wrow <= 8'd0; wactive <= start && (rows != 8'd0);
            rmcu <= 8'd0; rblk <= 3'd0; rpos <= 6'd0;
            m_valid <= 1'b0;
            d1_v <= 1'b0; p_v <= 1'b0; c_v <= 1'b0; d2_v <= 1'b0; d3_v <= 1'b0;
        end else begin
            d1_v <= take; p_v <= d1_v; c_v <= p_v; d2_v <= c_v; d3_v <= d2_v;
            if (take) begin
                if (wx == width - 12'd2) begin
                    wx <= 12'd0;
                    wy <= wy + 4'd1;
                end else
                    wx <= wx + 12'd2;
                if (last_px_of_row) begin
                    wsel <= ~wsel;
                    wrow <= wrow + 8'd1;
                    if (wrow == rows - 8'd1) wactive <= 1'b0;
                end
            end
            if (m_valid && m_ready) m_valid <= 1'b0;
            if (rd_go) begin
                yeq  <= ybuf_e[{rsel, yrow, ycol}];
                yoq  <= ybuf_o[{rsel, yrow, ycol}];
                yodd <= rpos[0];
                cbq  <= cbbuf[{rsel, rpos[5:3], ccol}];
                crq  <= crbuf[{rsel, rpos[5:3], ccol}];
                m_comp  <= (rblk == 3'd4) ? 2'd1 : (rblk == 3'd5) ? 2'd2 : 2'd0;
                m_blast <= last_s;
                m_flast <= last_m;
                m_valid <= 1'b1;
                rpos <= rpos + 6'd1;
                if (last_s) rblk <= (rblk == 3'd5) ? 3'd0 : rblk + 3'd1;
                if (last_b) rmcu <= last_m ? 8'd0 : rmcu + 8'd1;
                if (last_m) rsel <= ~rsel;
            end
            if (d3_v && d3_last)  full[d3_sel] <= 1'b1;
            if (rd_go && last_m)  full[rsel] <= 1'b0;
        end
    end
endmodule
`default_nettype wire
