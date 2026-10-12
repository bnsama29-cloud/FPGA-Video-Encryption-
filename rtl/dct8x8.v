// dct8x8.v -- 2-D 8x8 DCT = level shift + two dct_stage passes.
//   stage 1: rows,  shift 11 (keeps 2 fractional bits)
//   stage 2: cols,  shift 15 (integer result, natural row-major order F[v*8+u])
// Drop-in alternative to the Vitis HLS DCT in hls/ (same streams, same
// arithmetic) so the whole pipeline can be simulated with free tools.
// Golden model: model/jpeg.py :: dct2d()
`default_nettype none
module dct8x8 (
    input  wire               clk,
    input  wire               rst,
    input  wire               in_valid,
    output wire               in_ready,
    input  wire [7:0]         in_data,       // unsigned pixel sample
    input  wire [1:0]         in_comp,
    input  wire               in_flast,
    output wire               out_valid,
    input  wire               out_ready,
    output wire signed [15:0] out_data,
    output wire [1:0]         out_comp,
    output wire               out_blast,
    output wire               out_flast
);
    wire signed [8:0] shifted = $signed({1'b0, in_data}) - 9'sd128;

    wire               m_valid, m_ready, m_blast_unused, m_flast;
    wire signed [15:0] m_data;
    wire [1:0]         m_comp;

    dct_stage #(.IN_W(9), .SHIFT(11)) u_rows (
        .clk(clk), .rst(rst),
        .in_valid(in_valid), .in_ready(in_ready), .in_data(shifted),
        .in_comp(in_comp), .in_flast(in_flast),
        .out_valid(m_valid), .out_ready(m_ready), .out_data(m_data),
        .out_comp(m_comp), .out_blast(m_blast_unused), .out_flast(m_flast));

    dct_stage #(.IN_W(16), .SHIFT(15)) u_cols (
        .clk(clk), .rst(rst),
        .in_valid(m_valid), .in_ready(m_ready), .in_data(m_data),
        .in_comp(m_comp), .in_flast(m_flast),
        .out_valid(out_valid), .out_ready(out_ready), .out_data(out_data),
        .out_comp(out_comp), .out_blast(out_blast), .out_flast(out_flast));
endmodule
`default_nettype wire
