// quantiser.v -- q = sign(F) * ((|F| * R + 2^15) >> 16), R = round(65536 / Q).
// Division replaced by a reciprocal multiply (one DSP); clamps to the JPEG
// baseline range (DC -1024..1023, AC -1023..1023).
// Tables: 2 x 64 reciprocals (luma, chroma) in natural order, written through
// qt_we/qt_addr/qt_data (addr[6] = table, addr[5:0] = coefficient index).
// Pipelined: 3 clocks from input to out_valid (bug #17).
// Golden model: model/hw.py :: reciprocal(), quantise()
`default_nettype none
module quantiser (
    input  wire               clk,
    input  wire               rst,
    input  wire               qt_we,
    input  wire [6:0]         qt_addr,
    input  wire [16:0]        qt_data,
    input  wire               in_valid,
    output wire               in_ready,
    input  wire signed [15:0] in_data,
    input  wire [1:0]         in_comp,
    input  wire               in_blast,
    input  wire               in_flast,
    output reg                out_valid,
    input  wire               out_ready,
    output reg  signed [15:0] out_data,
    output reg  [1:0]         out_comp,
    output reg                out_blast,
    output reg                out_flast
);
    reg [16:0] rtab [0:127];
    reg [5:0]  idx;                               // coefficient index in block

    always @(posedge clk)
        if (qt_we) rtab[qt_addr] <= qt_data;

    // 3-stage pipeline (bug #17: the single-cycle version missed 100 MHz by 1.2 ns):
    //   S1  |F|, sign, reciprocal from the table, clamp limit
    //   S2  |F| * R + 2^15                    (one DSP48, product registered)
    //   out >> 16, clamp, restore the sign
    // All stages move together when the output register can take data, so backpressure
    // freezes the pipeline (in_ready = advance, exactly as before).
    wire advance = !out_valid || out_ready;
    assign in_ready = advance;
    wire go = in_valid && advance;

    wire        neg  = in_data[15];
    wire [15:0] absf = neg ? -in_data : in_data;

    reg         q1_v, q2_v;
    reg [15:0]  q1_absf;
    reg [16:0]  q1_rcp;
    reg         q1_neg, q2_neg;
    reg [10:0]  q1_lim, q2_lim;
    reg [33:0]  q2_prod;
    reg [1:0]   q1_comp, q2_comp;
    reg         q1_blast, q2_blast, q1_flast, q2_flast;

    wire [17:0] mag  = q2_prod[33:16];
    wire [10:0] magc = (mag > q2_lim) ? q2_lim : mag[10:0];
    wire signed [15:0] q = q2_neg ? -$signed({5'd0, magc}) : $signed({5'd0, magc});

    // datapath registers: no reset needed (qualified by the valid bits)
    always @(posedge clk) begin
        if (advance) begin
            q1_absf  <= absf;
            q1_rcp   <= rtab[{in_comp != 2'd0, idx}];
            q1_neg   <= neg;
            q1_lim   <= (idx == 6'd0 && neg) ? 11'd1024 : 11'd1023;
            q2_prod  <= q1_absf * q1_rcp + 34'd32768;
            q2_neg   <= q1_neg;
            q2_lim   <= q1_lim;
            {q1_comp, q1_blast, q1_flast} <= {in_comp, in_blast, in_flast};
            {q2_comp, q2_blast, q2_flast} <= {q1_comp, q1_blast, q1_flast};
            if (q2_v) begin
                out_data  <= q;
                out_comp  <= q2_comp;
                out_blast <= q2_blast;
                out_flast <= q2_flast;
            end
        end
    end

    always @(posedge clk) begin
        if (rst) begin
            out_valid <= 1'b0; idx <= 6'd0; q1_v <= 1'b0; q2_v <= 1'b0;
        end else begin
            if (advance) begin
                q1_v <= go; q2_v <= q1_v; out_valid <= q2_v;
            end
            if (go) idx <= in_blast ? 6'd0 : idx + 6'd1;
        end
    end
endmodule
`default_nettype wire
