// zigzag_rle.v -- zig-zag reorder + DC differencing + AC run-length symbols.
//
// In : 64 quantised coefficients per block, natural (row-major) order.
// Out: one symbol per handshake (the symbol stream of the interface contract):
//   o_is_dc, o_run[3:0], o_size[3:0], o_amp[10:0] (JPEG-coded amplitude bits),
//   o_eob (end of block), o_comp[1:0], o_flast (last symbol of the frame).
//   ZRL (16 zeros) = run 15, size 0, eob 0.
// DC predictors (one per component) reset on `start`.
// SEG_RESET = 1 (contract v3, secure_jpeg_lanes_top.v): in_flast marks the end of a restart
// segment (one MCU row) instead of the frame, and the DC predictors also reset after the
// segment's last symbol, as T.81 requires after a restart marker (F.1.2.3).
// Ping-pong block buffers: scanning one block while the next is written. Two pipeline stages
// (scan, then size/amplitude coding); see the comment at the scanner.
// Golden model: model/hw.py :: run_length(), category(), amp_bits()
`default_nettype none
module zigzag_rle #(
    parameter SEG_RESET = 0
) (
    input  wire               clk,
    input  wire               rst,
    input  wire               start,
    input  wire               in_valid,
    output wire               in_ready,
    input  wire signed [15:0] in_data,
    input  wire [1:0]         in_comp,
    input  wire               in_blast,
    input  wire               in_flast,
    output reg                o_valid,
    input  wire               o_ready,
    output reg                o_is_dc,
    output reg  [3:0]         o_run,
    output reg  [3:0]         o_size,
    output reg  [10:0]        o_amp,
    output reg                o_eob,
    output reg  [1:0]         o_comp,
    output reg                o_flast
);
    `include "zigzag.vh"

    // Coefficients are stored in zig-zag order (written at zz position nat_zz(wptr)), so the scanner
    // reads buffer[k] directly: the zig-zag lookup moved from the read path to the write path.
    function [5:0] nat_zz;
        input [5:0] n;
        integer i;
        begin
            nat_zz = 6'd0;
            for (i = 0; i < 64; i = i + 1)
                if (zz_nat(i[5:0]) == n) nat_zz = i[5:0];
        end
    endfunction

    reg signed [11:0] cb0 [0:63];
    reg signed [11:0] cb1 [0:63];
    reg [1:0]  full, bcomp0, bcomp1, bflast;
    reg        wsel, rsel;
    reg [5:0]  wptr;
    wire [5:0] waddr = nat_zz(wptr);

    assign in_ready = !full[wsel];
    wire wr = in_valid && in_ready;

    // ------------------------------------------------------------- scanner (stage 1)
    // Stage 1 decides the symbol and forms the value to code (DC difference or AC coefficient);
    // stage 2 turns that value into size + amplitude bits. Split in two for timing (Vivado run 5:
    // the single-stage version was the critical path, 14 logic levels, -0.13 ns at 100 MHz in the
    // lane overlay). The symbol stream is unchanged; it comes out one clock later.
    reg [5:0] k;                     // zig-zag position
    reg [5:0] run;                   // pending zero run (0..62)
    reg signed [11:0] pred [0:2];

    wire [1:0]  comp  = rsel ? bcomp1 : bcomp0;
    wire        flast = bflast[rsel];
    wire signed [11:0] coef = rsel ? cb1[k] : cb0[k];
    wire signed [12:0] diff = coef - pred[comp];      // DC difference

    reg                s_valid, s_is_dc, s_eob, s_flast;
    reg  [3:0]         s_run;
    reg  [1:0]         s_comp;
    reg  signed [12:0] s_val;        // value to code; 0 for EOB and ZRL (size 0, no amplitude bits)

    wire o_free = !o_valid || o_ready;
    wire s_free = !s_valid || o_free;
    wire step   = full[rsel] && s_free;

    // ------------------------------------------------------------- coder (stage 2)
    wire [12:0] mag  = s_val[12] ? -s_val : s_val;
    reg  [3:0]  cat;
    integer b;
    always @* begin
        cat = 4'd0;
        for (b = 0; b < 12; b = b + 1)
            if (mag[b]) cat = b[3:0] + 4'd1;
    end
    wire [12:0] vm1  = s_val - 13'sd1;
    wire [10:0] amp  = (s_val[12] ? vm1[10:0] : s_val[10:0]) & ((11'd1 << cat) - 11'd1);

    always @(posedge clk) begin
        if (wr) begin
            if (wsel) cb1[waddr] <= in_data[11:0]; else cb0[waddr] <= in_data[11:0];
        end
        if (rst || start) begin
            pred[0] <= 12'sd0; pred[1] <= 12'sd0; pred[2] <= 12'sd0;
        end
        if (rst || start) begin
            full <= 2'b00; wsel <= 1'b0; rsel <= 1'b0; wptr <= 6'd0;
            k <= 6'd0; run <= 6'd0; s_valid <= 1'b0; o_valid <= 1'b0;
        end else begin
            if (wr) begin
                wptr <= wptr + 6'd1;
                if (wptr == 6'd63) begin
                    wsel <= ~wsel;
                    if (wsel) begin bcomp1 <= in_comp; bflast[1] <= in_flast; end
                    else      begin bcomp0 <= in_comp; bflast[0] <= in_flast; end
                end
            end
            // stage 2: code the held symbol
            if (o_valid && o_ready) o_valid <= 1'b0;
            if (s_valid && o_free) begin
                o_valid <= 1'b1;
                o_is_dc <= s_is_dc; o_run <= s_run; o_size <= cat; o_amp <= amp;
                o_eob   <= s_eob;   o_comp <= s_comp; o_flast <= s_flast;
                s_valid <= 1'b0;
            end
            // stage 1: scan
            if (step) begin
                s_comp  <= comp;
                s_is_dc <= 1'b0;
                s_eob   <= 1'b0;
                s_flast <= 1'b0;
                if (k == 6'd0) begin                        // DC symbol
                    pred[comp] <= coef;
                    s_is_dc <= 1'b1; s_run <= 4'd0; s_val <= diff;
                    s_valid <= 1'b1;
                    k <= 6'd1; run <= 6'd0;
                end else if (coef == 12'sd0) begin
                    if (k == 6'd63) begin                   // trailing zeros: EOB
                        s_eob <= 1'b1; s_run <= 4'd0; s_val <= 13'sd0;
                        s_flast <= flast; s_valid <= 1'b1;
                        k <= 6'd0; run <= 6'd0;
                        if (SEG_RESET && flast) begin
                            pred[0] <= 12'sd0; pred[1] <= 12'sd0; pred[2] <= 12'sd0;
                        end
                        rsel <= ~rsel;
                        full[rsel] <= 1'b0;
                    end else begin
                        run <= run + 6'd1; k <= k + 6'd1;   // no output this step
                    end
                end else if (run >= 6'd16) begin            // emit ZRL, stay at k
                    s_run <= 4'd15; s_val <= 13'sd0;
                    s_valid <= 1'b1;
                    run <= run - 6'd16;
                end else begin                              // AC symbol
                    s_run <= run[3:0]; s_val <= {coef[11], coef};
                    s_valid <= 1'b1;
                    run <= 6'd0;
                    if (k == 6'd63) begin                   // last coefficient non-zero
                        s_flast <= flast;
                        k <= 6'd0;
                        if (SEG_RESET && flast) begin
                            pred[0] <= 12'sd0; pred[1] <= 12'sd0; pred[2] <= 12'sd0;
                        end
                        rsel <= ~rsel;
                        full[rsel] <= 1'b0;
                    end else
                        k <= k + 6'd1;
                end
            end
            if (wr && wptr == 6'd63) full[wsel] <= 1'b1;
        end
    end
endmodule
`default_nettype wire
