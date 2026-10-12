// huffman_packer.v -- test wrapper: huffman_enc -> bit_packer (symbols in, bytes out).
`default_nettype none
module huffman_packer (
    input  wire        clk,
    input  wire        rst,
    input  wire        i_valid,
    output wire        i_ready,
    input  wire        i_is_dc,
    input  wire [3:0]  i_run,
    input  wire [3:0]  i_size,
    input  wire [10:0] i_amp,
    input  wire [1:0]  i_comp,
    input  wire        i_flast,
    output wire        o_valid,
    input  wire        o_ready,
    output wire [7:0]  o_data,
    output wire        o_last
);
    wire        h_valid, h_ready, h_flast;
    wire [26:0] h_bits;
    wire [4:0]  h_len;
    huffman_enc u_huff (
        .clk(clk), .rst(rst), .i_valid(i_valid), .i_ready(i_ready),
        .i_is_dc(i_is_dc), .i_run(i_run), .i_size(i_size), .i_amp(i_amp),
        .i_comp(i_comp), .i_flast(i_flast),
        .o_valid(h_valid), .o_ready(h_ready), .o_bits(h_bits), .o_len(h_len), .o_flast(h_flast));
    bit_packer u_pack (
        .clk(clk), .rst(rst), .i_valid(h_valid), .i_ready(h_ready),
        .i_bits(h_bits), .i_len(h_len), .i_flast(h_flast),
        .o_valid(o_valid), .o_ready(o_ready), .o_data(o_data), .o_last(o_last));
endmodule
`default_nettype wire
