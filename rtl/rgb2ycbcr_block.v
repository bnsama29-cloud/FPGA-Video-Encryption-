// rgb2ycbcr_block.v -- BT.601 RGB->YCbCr, 4:2:0 chroma averaging, 8x8 blocking.
//
// In : raster-order pixels, 32-bit {pad, B, G, R} (R = bits 7:0), 1 per handshake.
// Out: 8-bit samples, 64 per block row-major, blocks per MCU: Y0 Y1 Y2 Y3 Cb Cr.
//      m_comp = 0/1/2 (Y/Cb/Cr), m_blast on the last sample of each block,
//      m_flast on the last sample of the last block of the frame.
// Two MCU-row buffers (ping-pong): one fills while the other is emitted.
// width and height must be multiples of 16, width <= 2^LOG_MAXW.
// Golden model: model/hw.py :: rgb_to_ycbcr(), planes(), blocks_in_hw_order()
`default_nettype none
module rgb2ycbcr_block #(
    parameter LOG_MAXW = 11                  // 2048 pixels max line width
) (
    input  wire        clk,
    input  wire        rst,
    input  wire        start,                // pulse: new frame
    input  wire [11:0] width,
    input  wire [11:0] height,
    input  wire        s_valid,
    output wire        s_ready,
    input  wire [31:0] s_data,
    output reg         m_valid,
    input  wire        m_ready,
    output wire [7:0]  m_data,
    output reg  [1:0]  m_comp,
    output reg         m_blast,
    output reg         m_flast
);
    localparam MAXW = 1 << LOG_MAXW;

    // ---------------------------------------------------- write pipeline (bug #20)
    // The first overlay run missed 100 MHz by 3.1 ns: the DMA's output register fed the colour
    // conversion, the clamp, the chroma average and the line-buffer write in ONE clock (the
    // out-of-context run could not see it: its input ports have no input delay). Now:
    //   take  the counters (wx, wy, wsel, wactive) advance exactly as before, so s_ready is unchanged
    //   D1    registered pixel + where it goes
    //   C     registered sums (multiply-add)            D2  registered, clamped Y, Cb, Cr
    //   (C added after the second overlay run: multiply-add + clamp in one clock missed by 0.24 ns)
    //   D3    registered pair sums and row-sum reads; line buffers / chroma sums written from D3, `full` set there
    // The writes happen 5 clocks after the handshake (P added 21 Oct 2026), in the same order, so the buffers
    // end up with the same contents; the reader starts 5 clocks later.
    //   D3 (21 Oct 2026, for 125 MHz: Vivado placed the converter on the critical path, -0.875 ns at
    //   8 ns): the chroma pair sum and the read of the row-sum memory are registered, and every buffer
    //   write happens one clock later from D3. The row sum of column cx is written on an even line and
    //   read on the next odd line, at least 8 pixels later, so the extra clock cannot read a stale value.
    //   P  (21 Oct 2026, run 8: at 125 MHz the multiply-add D1 -> C was the critical path, 12 logic levels,
    //   -0.487 ns): the nine constant products are registered first and C only adds them, so each stage
    //   has about half the carry chain. Same integers, so the same bytes; one clock more latency.
    reg                d1_v, p_v, c_v, d2_v, d3_v;
    reg                p_sel, p_last;
    reg [3:0]          p_y;
    reg [LOG_MAXW-1:0] p_x;
    reg signed [18:0]  p_y1, p_y2, p_y3, p_cb1, p_cb2, p_cb3, p_cr1, p_cr2, p_cr3;
    reg                d3_sel, d3_last;
    reg [3:0]          d3_y;
    reg [LOG_MAXW-1:0] d3_x;
    reg [7:0]          d3_yp;
    reg [9:0]          d3_cbp, d3_crp, d3_cbs, d3_crs;
    reg [23:0]         d1_rgb;
    reg                d1_sel, c_sel, d2_sel, d1_last, c_last, d2_last;
    reg [3:0]          d1_y, c_y, d2_y;
    reg [LOG_MAXW-1:0] d1_x, c_x, d2_x;
    reg signed [18:0]  c_yt, c_cbt, c_crt;
    reg [7:0]          d2_yp, d2_cb, d2_cr;

    // ---------------------------------------------------- colour conversion (on D1)
    wire [7:0] r = d1_rgb[7:0], g = d1_rgb[15:8], b = d1_rgb[23:16];
    // y_t  = 77 r + 150 g + 29 b + 128
    // cb_t = -43 r - 85 g + 128 b + 32896
    // cr_t = 128 r - 107 g - 21 b + 32896          (products on P, sums on C)
    wire signed [18:0] y_t  = p_y1 + p_y2 + p_y3 + 19'sd128;
    wire signed [18:0] cb_t = p_cb1 + p_cb2 + p_cb3 + 19'sd32896;
    wire signed [18:0] cr_t = p_cr1 + p_cr2 + p_cr3 + 19'sd32896;
    function [7:0] sat8;                     // (v >> 8) clamped to 0..255
        input signed [18:0] v;
        begin
            if (v < 0)               sat8 = 8'd0;
            else if (v[18:8] > 255)  sat8 = 8'd255;
            else                     sat8 = v[15:8];
        end
    endfunction
    wire [7:0] y_px = sat8(c_yt), cb_px = sat8(c_cbt), cr_px = sat8(c_crt);

    // ---------------------------------------------------------- line buffers
    reg [7:0] ybuf  [0:2*16*MAXW-1];         // {sel, row[3:0], x}
    reg [7:0] cbbuf [0:2*8*(MAXW/2)-1];      // {sel, row[2:0], x/2}
    reg [7:0] crbuf [0:2*8*(MAXW/2)-1];
    reg [9:0] cbsum [0:MAXW/2-1];            // even-row pair sums
    reg [9:0] crsum [0:MAXW/2-1];

    reg [1:0] full;                          // buffer holds a complete MCU row
    reg       wsel, rsel;
    reg [11:0] wx;                           // writer: x in line
    reg [3:0]  wy;                           // writer: line within MCU row
    reg [7:0]  wrow;                         // writer: MCU row index
    reg        wactive;
    reg [8:0]  cb_prev, cr_prev;             // previous pixel's chroma (even x)

    wire [7:0] mcu_rows = height[11:4];
    assign s_ready = wactive && !full[wsel];
    wire take = s_valid && s_ready;

    wire [9:0] cb_pair = cb_prev + d2_cb;
    wire [9:0] cr_pair = cr_prev + d2_cr;
    wire [LOG_MAXW-2:0] cx  = d2_x[LOG_MAXW-1:1];
    wire [LOG_MAXW-2:0] cx3 = d3_x[LOG_MAXW-1:1];
    wire [9:0] cb_avg = (d3_cbs + d3_cbp + 10'd2) >> 2;
    wire [9:0] cr_avg = (d3_crs + d3_crp + 10'd2) >> 2;
    wire last_px_of_row = (wx == width - 12'd1) && (wy == 4'd15);

    // datapath registers (no reset: qualified by d1_v / d2_v)
    always @(posedge clk) begin
        d1_rgb <= s_data[23:0];
        d1_sel <= wsel; d1_y <= wy; d1_x <= wx[LOG_MAXW-1:0]; d1_last <= last_px_of_row;
        p_y1  <= 77 * $signed({1'b0, r});  p_y2  <= 150 * $signed({1'b0, g}); p_y3  <= 29 * $signed({1'b0, b});
        p_cb1 <= -43 * $signed({1'b0, r}); p_cb2 <= -85 * $signed({1'b0, g}); p_cb3 <= 128 * $signed({1'b0, b});
        p_cr1 <= 128 * $signed({1'b0, r}); p_cr2 <= -107 * $signed({1'b0, g}); p_cr3 <= -21 * $signed({1'b0, b});
        p_sel <= d1_sel; p_y <= d1_y; p_x <= d1_x; p_last <= d1_last;
        c_yt <= y_t; c_cbt <= cb_t; c_crt <= cr_t;
        c_sel <= p_sel; c_y <= p_y; c_x <= p_x; c_last <= p_last;
        d2_yp <= y_px; d2_cb <= cb_px; d2_cr <= cr_px;
        d2_sel <= c_sel; d2_y <= c_y; d2_x <= c_x; d2_last <= c_last;
        if (d2_v && !d2_x[0]) begin
            cb_prev <= d2_cb; cr_prev <= d2_cr;
        end
        // D3: registered pair sums and row-sum reads; all buffer writes from here
        d3_sel <= d2_sel; d3_y <= d2_y; d3_x <= d2_x; d3_last <= d2_last; d3_yp <= d2_yp;
        d3_cbp <= cb_pair; d3_crp <= cr_pair; d3_cbs <= cbsum[cx]; d3_crs <= crsum[cx];
        if (d3_v) begin
            ybuf[{d3_sel, d3_y, d3_x}] <= d3_yp;
            if (d3_x[0] && !d3_y[0]) begin
                cbsum[cx3] <= d3_cbp; crsum[cx3] <= d3_crp;
            end else if (d3_x[0]) begin
                cbbuf[{d3_sel, d3_y[3:1], cx3}] <= cb_avg[7:0];
                crbuf[{d3_sel, d3_y[3:1], cx3}] <= cr_avg[7:0];
            end
        end
    end

    // ---------------------------------------------------------------- reader
    reg [7:0]  rrow;                         // reader MCU row
    reg [7:0]  rmcu;                         // MCU within row
    reg [2:0]  rblk;                         // 0..3 = Y0..Y3, 4 = Cb, 5 = Cr
    reg [5:0]  rpos;                         // sample within block (i*8 + j)
    reg [7:0]  yq, cbq, crq;
    wire [7:0] mcus_per_row = width[11:4];
    wire       rd_go  = full[rsel] && (!m_valid || m_ready);
    wire       last_s = (rpos == 6'd63);
    wire       last_b = last_s && (rblk == 3'd5);
    wire       last_m = last_b && (rmcu == mcus_per_row - 8'd1);

    wire [3:0] yrow = {rblk[1], rpos[5:3]};
    wire [LOG_MAXW-1:0] ycol = {rmcu, rblk[0], rpos[2:0]};
    wire [LOG_MAXW-2:0] ccol = {rmcu, rpos[2:0]};
    assign m_data = (m_comp == 2'd0) ? yq : (m_comp == 2'd1) ? cbq : crq;

    always @(posedge clk) begin
        if (rst || start) begin
            full <= 2'b00; wsel <= 1'b0; rsel <= 1'b0;
            wx <= 12'd0; wy <= 4'd0; wrow <= 8'd0; wactive <= start;
            rrow <= 8'd0; rmcu <= 8'd0; rblk <= 3'd0; rpos <= 6'd0;
            m_valid <= 1'b0;
            d1_v <= 1'b0; p_v <= 1'b0; c_v <= 1'b0; d2_v <= 1'b0; d3_v <= 1'b0;
        end else begin
            d1_v <= take; p_v <= d1_v; c_v <= p_v; d2_v <= c_v; d3_v <= d2_v;
            // writer counters
            if (take) begin
                if (wx == width - 12'd1) begin
                    wx <= 12'd0;
                    wy <= wy + 4'd1;
                end else
                    wx <= wx + 12'd1;
                if (last_px_of_row) begin
                    wsel <= ~wsel;
                    wrow <= wrow + 8'd1;
                    if (wrow == mcu_rows - 8'd1) wactive <= 1'b0;
                end
            end
            // reader
            if (m_valid && m_ready) m_valid <= 1'b0;
            if (rd_go) begin
                yq  <= ybuf[{rsel, yrow, ycol}];
                cbq <= cbbuf[{rsel, rpos[5:3], ccol}];
                crq <= crbuf[{rsel, rpos[5:3], ccol}];
                m_comp  <= (rblk == 3'd4) ? 2'd1 : (rblk == 3'd5) ? 2'd2 : 2'd0;
                m_blast <= last_s;
                m_flast <= last_m && (rrow == mcu_rows - 8'd1);
                m_valid <= 1'b1;
                rpos <= rpos + 6'd1;
                if (last_s) rblk <= (rblk == 3'd5) ? 3'd0 : rblk + 3'd1;
                if (last_b) rmcu <= last_m ? 8'd0 : rmcu + 8'd1;
                if (last_m) begin
                    rsel <= ~rsel;
                    rrow <= rrow + 8'd1;
                end
            end
            // buffer ownership: set by writer, cleared by reader
            if (d3_v && d3_last)        full[d3_sel] <= 1'b1;
            if (rd_go && last_m)        full[rsel] <= 1'b0;
        end
    end
endmodule
`default_nettype wire
