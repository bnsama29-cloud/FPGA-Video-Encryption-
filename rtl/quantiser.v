// quantiser.v -- q = sign(F) * ((|F| * R + 2^15) >> 16), R = round(65536 / Q).
// Division replaced by a reciprocal multiply (one DSP); clamps to the JPEG
// baseline range (DC -1024..1023, AC -1023..1023).
// Tables: 2 x 64 reciprocals (luma, chroma) in natural order, written through
// qt_we/qt_addr/qt_data (addr[6] = table, addr[5:0] = coefficient index).
// Golden model: model/jpeg.py :: reciprocal(), quantise()
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

    assign in_ready = !out_valid || out_ready;
    wire go = in_valid && in_ready;

    wire        neg  = in_data[15];
    wire [15:0] absf = neg ? -in_data : in_data;
    wire [16:0] rcp  = rtab[{in_comp != 2'd0, idx}];
    wire [33:0] prod = absf * rcp + 34'd32768;
    wire [17:0] mag  = prod[33:16];
    wire [10:0] lim  = (idx == 6'd0 && neg) ? 11'd1024 : 11'd1023;
    wire [10:0] magc = (mag > lim) ? lim : mag[10:0];
    wire signed [15:0] q = neg ? -$signed({5'd0, magc}) : $signed({5'd0, magc});

    always @(posedge clk) begin
        if (rst) begin
            out_valid <= 1'b0; idx <= 6'd0;
        end else begin
            if (out_valid && out_ready) out_valid <= 1'b0;
            if (go) begin
                out_data  <= q;
                out_comp  <= in_comp;
                out_blast <= in_blast;
                out_flast <= in_flast;
                out_valid <= 1'b1;
                idx <= in_blast ? 6'd0 : idx + 6'd1;
            end
        end
    end
endmodule
`default_nettype wire
