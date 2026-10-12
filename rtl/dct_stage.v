// dct_stage.v -- one 1-D DCT pass over the 8 rows of a block, output transposed.
//   out[u*8 + y] = (sum_x C[u][x] * in[y*8 + x] + 2^(SHIFT-1)) >>> SHIFT
// Two of these in series give the 2-D DCT (see dct8x8.v).
// 64 samples in (row-major), 64 out (row-major). Ping-pong input buffers, so
// a new block can be loaded while the previous one is computed: 1 sample/clock.
// Uses 8 multipliers (one output per clock).
// Golden model: model/jpeg.py :: dct_stage()
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

    // dot product of row y (= ridx[2:0]) of the read buffer with C[u] (u = ridx[5:3])
    wire [2:0] u = ridx[5:3];
    wire [2:0] y = ridx[2:0];
    reg signed [31:0] acc;
    integer x;
    always @* begin
        acc = 32'sd0;
        for (x = 0; x < 8; x = x + 1)
            acc = acc + (rsel ? buf1[{y, x[2:0]}] : buf0[{y, x[2:0]}]) * dct_c({u, x[2:0]});
    end
    wire signed [31:0] rounded = (acc + (32'sd1 <<< (SHIFT - 1))) >>> SHIFT;

    wire rd = full[rsel] && (!out_valid || out_ready);

    always @(posedge clk) begin
        if (wr) begin
            if (wsel) buf1[wptr] <= in_data; else buf0[wptr] <= in_data;
        end
        if (rst) begin
            full <= 2'b00; wsel <= 1'b0; rsel <= 1'b0; wptr <= 6'd0; ridx <= 6'd0;
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
            if (out_valid && out_ready) out_valid <= 1'b0;
            if (rd) begin
                out_data  <= rounded[15:0];
                out_comp  <= rsel ? bcomp1 : bcomp0;
                out_blast <= (ridx == 6'd63);
                out_flast <= (ridx == 6'd63) && bflast[rsel];
                out_valid <= 1'b1;
                ridx <= ridx + 6'd1;
                if (ridx == 6'd63) rsel <= ~rsel;
            end
            if (wr && wptr == 6'd63) full[wsel] <= 1'b1;
            if (rd && ridx == 6'd63) full[rsel] <= 1'b0;
        end
    end
endmodule
`default_nettype wire
