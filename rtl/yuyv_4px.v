// yuyv_4px.v -- one encoder lane's front end for contract v3 with camera-native input: YCbCr 4:2:2
// (YUYV) in, 4:2:0 blocks out, FOUR pixels per clock. Built instead of rgb2ycbcr_2px.v when the lane
// encoder has PIXFMT = 1 (secure_jpeg_lanes_top.v).
//
// In : 64-bit beats of the YUYV raster stream, byte 0 first: {Cr1, Y3, Cb1, Y2, Cr0, Y1, Cb0, Y0} for
//      the pixels x .. x+3 (x a multiple of 4); Cb0/Cr0 belong to pixels x, x+1 and Cb1/Cr1 to x+2, x+3.
//      Only the MCU rows this lane owns arrive (the dealer sends MCU row r to lane r mod LANES).
// Out: exactly as rgb2ycbcr_2px.v: 8-bit samples, 64 per block row-major, Y0 Y1 Y2 Y3 Cb Cr per MCU,
//      m_blast on the last sample of each block, m_flast on the last sample of every MCU row.
// Why: cameras and ISPs produce YCbCr; RGB is converted from it. Taking YUYV skips the colour
// conversion (no multiplies), halves the DDR traffic (2 bytes per pixel instead of 4) and doubles the
// pixels per beat, so the 64-bit input stops limiting four lanes (0.5 -> 0.25 clocks per pixel).
// 4:2:0 chroma = vertical average of two 4:2:2 lines, (a + b + 1) >> 1: even lines store their chroma
// in a row memory, odd lines read it back, average and write the chroma buffer.
// The Y buffer has four banks (x mod 4) so a beat's four samples are written in one clock; the chroma
// buffers two banks (chroma column mod 2). NBUF as in rgb2ycbcr_2px.v (2 = ping-pong).
// width must be a multiple of 16, width <= 2^LOG_MAXW.
// Golden model: model/hw.py :: planes_yuyv(), blocks_in_hw_order(..., pixfmt="yuyv")  (rows of one lane)
`default_nettype none
module yuyv_4px #(
    parameter LOG_MAXW = 11,
    parameter NBUF = 2
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
    localparam LQ = LOG_MAXW - 2;            // bits of x/4

    // ------------------------------------------------------------- line buffers
    reg [7:0] yb0 [0:NBUF*16*(MAXW/4)-1];    // {sel, row[3:0], x/4}, x mod 4 = 0
    reg [7:0] yb1 [0:NBUF*16*(MAXW/4)-1];    //                        x mod 4 = 1
    reg [7:0] yb2 [0:NBUF*16*(MAXW/4)-1];
    reg [7:0] yb3 [0:NBUF*16*(MAXW/4)-1];
    reg [7:0] cbb0 [0:NBUF*8*(MAXW/4)-1];    // {sel, row[2:0], cx/2}, chroma column cx even
    reg [7:0] cbb1 [0:NBUF*8*(MAXW/4)-1];    //                        cx odd
    reg [7:0] crb0 [0:NBUF*8*(MAXW/4)-1];
    reg [7:0] crb1 [0:NBUF*8*(MAXW/4)-1];
    reg [7:0] cbs0 [0:MAXW/4-1];             // chroma of the even line of a pair, per beat
    reg [7:0] cbs1 [0:MAXW/4-1];
    reg [7:0] crs0 [0:MAXW/4-1];
    reg [7:0] crs1 [0:MAXW/4-1];

    reg [1:0]  full;
    reg        wsel, rsel;
    reg [11:0] wx;                           // x of the first pixel of the beat (multiple of 4)
    reg [3:0]  wy;
    reg [7:0]  wrow;
    reg        wactive;
    reg        wdone;                        // NBUF = 1: the set holds a whole MCU row not yet read out

    assign s_ready = wactive && ((NBUF == 2) ? !full[wsel] : !wdone);
    wire take = s_valid && s_ready;
    wire last_px_of_row = (wx == width - 12'd4) && (wy == 4'd15);

    // ------------------------------------------------------------ write pipeline
    // D1: the beat and its coordinates; D2: the even line's chroma read back (odd lines); then write.
    reg          d1_v, d2_v;
    reg [63:0]   d1_d;
    reg          d1_sel, d1_last, d2_sel, d2_last;
    reg [3:0]    d1_y, d2_y;
    reg [LQ-1:0] d1_x, d2_x;
    reg [63:0]   d2_d;
    reg [7:0]    d2_cbe0, d2_cbe1, d2_cre0, d2_cre1;   // the even line's chroma at this beat
    wire [8:0]   cb0_avg = d2_cbe0 + d2_d[15:8]  + 9'd1;
    wire [8:0]   cb1_avg = d2_cbe1 + d2_d[47:40] + 9'd1;
    wire [8:0]   cr0_avg = d2_cre0 + d2_d[31:24] + 9'd1;
    wire [8:0]   cr1_avg = d2_cre1 + d2_d[63:56] + 9'd1;

    always @(posedge clk) begin
        d1_d <= s_data; d1_sel <= wsel; d1_y <= wy; d1_x <= wx[LOG_MAXW-1:2]; d1_last <= last_px_of_row;
        d2_d <= d1_d; d2_sel <= d1_sel; d2_y <= d1_y; d2_x <= d1_x; d2_last <= d1_last;
        d2_cbe0 <= cbs0[d1_x]; d2_cbe1 <= cbs1[d1_x]; d2_cre0 <= crs0[d1_x]; d2_cre1 <= crs1[d1_x];
        if (d2_v) begin
            yb0[{d2_sel, d2_y, d2_x}] <= d2_d[7:0];
            yb1[{d2_sel, d2_y, d2_x}] <= d2_d[23:16];
            yb2[{d2_sel, d2_y, d2_x}] <= d2_d[39:32];
            yb3[{d2_sel, d2_y, d2_x}] <= d2_d[55:48];
            if (!d2_y[0]) begin
                cbs0[d2_x] <= d2_d[15:8];  cbs1[d2_x] <= d2_d[47:40];
                crs0[d2_x] <= d2_d[31:24]; crs1[d2_x] <= d2_d[63:56];
            end else begin
                cbb0[{d2_sel, d2_y[3:1], d2_x}] <= cb0_avg[8:1];
                cbb1[{d2_sel, d2_y[3:1], d2_x}] <= cb1_avg[8:1];
                crb0[{d2_sel, d2_y[3:1], d2_x}] <= cr0_avg[8:1];
                crb1[{d2_sel, d2_y[3:1], d2_x}] <= cr1_avg[8:1];
            end
        end
    end

    // ------------------------------------------------------------------ reader
    reg [7:0]  rmcu;
    reg [2:0]  rblk;
    reg [5:0]  rpos;
    reg [7:0]  yq0, yq1, yq2, yq3, cbq0, cbq1, crq0, crq1;
    reg [1:0]  ybank;
    reg        cbank;
    wire [7:0] mcus_per_row = width[11:4];
    wire       rd_go  = full[rsel] && (!m_valid || m_ready);
    wire       last_s = (rpos == 6'd63);
    wire       last_b = last_s && (rblk == 3'd5);
    wire       last_m = last_b && (rmcu == mcus_per_row - 8'd1);

    wire [3:0]    yrow = {rblk[1], rpos[5:3]};
    wire [LQ-1:0] ycol = {rmcu, rblk[0], rpos[2]};       // x/4 of the Y sample, bank = rpos[1:0]
    wire [LQ-1:0] ccol = {rmcu, rpos[2:1]};              // chroma column / 2, bank = rpos[0]
    wire [7:0]    yq   = (ybank == 2'd0) ? yq0 : (ybank == 2'd1) ? yq1 : (ybank == 2'd2) ? yq2 : yq3;
    wire [7:0]    cbq  = cbank ? cbq1 : cbq0;
    wire [7:0]    crq  = cbank ? crq1 : crq0;
    assign m_data = (m_comp == 2'd0) ? yq : (m_comp == 2'd1) ? cbq : crq;

    always @(posedge clk) begin
        if (rst || start) begin
            full <= 2'b00; wsel <= 1'b0; rsel <= 1'b0;
            wx <= 12'd0; wy <= 4'd0; wrow <= 8'd0; wactive <= start && (rows != 8'd0); wdone <= 1'b0;
            rmcu <= 8'd0; rblk <= 3'd0; rpos <= 6'd0;
            m_valid <= 1'b0;
            d1_v <= 1'b0; d2_v <= 1'b0;
        end else begin
            d1_v <= take; d2_v <= d1_v;
            if (take) begin
                if (wx == width - 12'd4) begin
                    wx <= 12'd0;
                    wy <= wy + 4'd1;
                end else
                    wx <= wx + 12'd4;
                if (last_px_of_row) begin
                    if (NBUF == 2) wsel <= ~wsel;
                    else           wdone <= 1'b1;
                    wrow <= wrow + 8'd1;
                    if (wrow == rows - 8'd1) wactive <= 1'b0;
                end
            end
            if (m_valid && m_ready) m_valid <= 1'b0;
            if (rd_go) begin
                yq0  <= yb0[{rsel, yrow, ycol}];
                yq1  <= yb1[{rsel, yrow, ycol}];
                yq2  <= yb2[{rsel, yrow, ycol}];
                yq3  <= yb3[{rsel, yrow, ycol}];
                ybank <= rpos[1:0];
                cbq0 <= cbb0[{rsel, rpos[5:3], ccol}];
                cbq1 <= cbb1[{rsel, rpos[5:3], ccol}];
                crq0 <= crb0[{rsel, rpos[5:3], ccol}];
                crq1 <= crb1[{rsel, rpos[5:3], ccol}];
                cbank <= rpos[0];
                m_comp  <= (rblk == 3'd4) ? 2'd1 : (rblk == 3'd5) ? 2'd2 : 2'd0;
                m_blast <= last_s;
                m_flast <= last_m;
                m_valid <= 1'b1;
                rpos <= rpos + 6'd1;
                if (last_s) rblk <= (rblk == 3'd5) ? 3'd0 : rblk + 3'd1;
                if (last_b) rmcu <= last_m ? 8'd0 : rmcu + 8'd1;
                if (last_m && NBUF == 2) rsel <= ~rsel;
            end
            if (d2_v && d2_last)  full[d2_sel] <= 1'b1;
            if (rd_go && last_m)  full[rsel] <= 1'b0;
            if (rd_go && last_m)  wdone <= 1'b0;
        end
    end
endmodule
`default_nettype wire
