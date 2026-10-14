// dct_stage.v -- one 1-D DCT pass over the 8 rows of a block, output transposed.
//   out[u*8 + y] = (sum_x C[u][x] * in[y*8 + x] + 2^(SHIFT-1)) >>> SHIFT
// Two of these in series give the 2-D DCT (see dct8x8.v).
// 64 samples in (row-major), 64 out (row-major). Ping-pong input buffers, so
// a new block can be loaded while the previous one is computed: 1 sample/clock.
// Uses 8 multipliers (one output per clock). Read side pipelined: 5 clocks from
// the read of a row to out_valid (see bug #17 in docs/TESTING.md).
// Golden model: model/hw.py :: dct_stage()
`default_nettype none
module dct_stage #(
    parameter IN_W  = 16,
    parameter SHIFT = 15
) (
    input  wire                   clk,
    input  wire                   rst,
    input  wire                   in_valid,
    output wire                   in_ready,
    input  wire signed [IN_W-1:0] in_data,
    input  wire [1:0]             in_comp,
    input  wire                   in_flast,     // sampled with the last sample of a block
    output reg                    out_valid,
    input  wire                   out_ready,
    output reg  signed [15:0]     out_data,
    output reg  [1:0]             out_comp,
    output reg                    out_blast,
    output reg                    out_flast
);
    `include "dct_coeffs.vh"

    reg signed [IN_W-1:0] buf0 [0:63];
    reg signed [IN_W-1:0] buf1 [0:63];
    reg [1:0] full;
    reg [1:0] bcomp0, bcomp1;
    reg [1:0] bflast;
    reg       wsel, rsel;
    reg [5:0] wptr, ridx;

    assign in_ready = !full[wsel];
    wire wr = in_valid && in_ready;

    // ---- read side: a 5-stage pipeline (bug #17: the old version did 8 multiplies and a
    // chain of 8 additions in one clock, ~20 ns, so the encoder only closed at ~47 MHz).
    //   S1  read the 8 samples of row y and the 8 coefficients of C[u]   (u = ridx[5:3])
    //   S2  8 products                                                    (DSP48)
    //   S3  4 pair sums      S4  2 sums      out  final sum, round, shift
    // All stages move together when the output register can take data ("advance"), so
    // backpressure simply freezes the pipeline. Sums are 32-bit two's complement exactly as
    // before; addition modulo 2^32 is associative, so the tree gives the same bits as the
    // old sequential chain.
    wire [2:0] u = ridx[5:3];
    wire [2:0] y = ridx[2:0];
    wire advance = !out_valid || out_ready;
    wire rd = full[rsel] && advance;

    reg               s1_v, s2_v, s3_v, s4_v;
    reg [1:0]         s1_comp, s2_comp, s3_comp, s4_comp;
    reg               s1_blast, s2_blast, s3_blast, s4_blast;
    reg               s1_flast, s2_flast, s3_flast, s4_flast;
    reg signed [IN_W-1:0] s1_a [0:7];
    reg signed [14:0]     s1_c [0:7];
    reg signed [31:0]     s2_p [0:7];
    reg signed [31:0]     s3_s [0:3];
    reg signed [31:0]     s4_t [0:1];
    wire signed [31:0] acc = s4_t[0] + s4_t[1];
    wire signed [31:0] rounded = (acc + (32'sd1 <<< (SHIFT - 1))) >>> SHIFT;
    integer x;

    // datapath registers: no reset needed (qualified by the valid bits)
    always @(posedge clk) begin
        if (wr) begin
            if (wsel) buf1[wptr] <= in_data; else buf0[wptr] <= in_data;
        end
        if (advance) begin
            for (x = 0; x < 8; x = x + 1) begin
                s1_a[x] <= rsel ? buf1[{y, x[2:0]}] : buf0[{y, x[2:0]}];
                s1_c[x] <= dct_c({u, x[2:0]});
                s2_p[x] <= s1_a[x] * s1_c[x];
            end
            for (x = 0; x < 4; x = x + 1)
                s3_s[x] <= s2_p[2*x] + s2_p[2*x+1];
            s4_t[0] <= s3_s[0] + s3_s[1];
            s4_t[1] <= s3_s[2] + s3_s[3];
            s1_comp <= rsel ? bcomp1 : bcomp0;
            s1_blast <= (ridx == 6'd63);
            s1_flast <= (ridx == 6'd63) && bflast[rsel];
            {s2_comp, s2_blast, s2_flast} <= {s1_comp, s1_blast, s1_flast};
            {s3_comp, s3_blast, s3_flast} <= {s2_comp, s2_blast, s2_flast};
            {s4_comp, s4_blast, s4_flast} <= {s3_comp, s3_blast, s3_flast};
            if (s4_v) begin
                out_data  <= rounded[15:0];
                out_comp  <= s4_comp;
                out_blast <= s4_blast;
                out_flast <= s4_flast;
            end
        end
    end

    always @(posedge clk) begin
        if (rst) begin
            full <= 2'b00; wsel <= 1'b0; rsel <= 1'b0; wptr <= 6'd0; ridx <= 6'd0;
            s1_v <= 1'b0; s2_v <= 1'b0; s3_v <= 1'b0; s4_v <= 1'b0;
            out_valid <= 1'b0;
        end else begin
            if (wr) begin
                wptr <= wptr + 6'd1;
                if (wptr == 6'd63) begin
                    wsel <= ~wsel;
                    if (wsel) begin bcomp1 <= in_comp; bflast[1] <= in_flast; end
                    else      begin bcomp0 <= in_comp; bflast[0] <= in_flast; end
                end
            end
            if (advance) begin
                s1_v <= rd; s2_v <= s1_v; s3_v <= s2_v; s4_v <= s3_v;
                out_valid <= s4_v;
            end
            if (rd) begin
                ridx <= ridx + 6'd1;
                if (ridx == 6'd63) rsel <= ~rsel;
            end
            if (wr && wptr == 6'd63) full[wsel] <= 1'b1;
            if (rd && ridx == 6'd63) full[rsel] <= 1'b0;
        end
    end
endmodule
`default_nettype wire
