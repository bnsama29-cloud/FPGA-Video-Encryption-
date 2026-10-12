// huffman_enc.v -- symbol -> {Huffman code, amplitude bits} chunk for the packer.
// Standard JPEG tables (Annex K) in ROM; component 0 uses luminance tables,
// components 1 and 2 chrominance. Output chunk is right-aligned:
// o_bits[o_len-1] is the first bit to be written.
// Golden model: model/jpeg.py :: huffman_bits()
`default_nettype none
module huffman_enc (
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
    output reg         o_valid,
    input  wire        o_ready,
    output reg  [26:0] o_bits,
    output reg  [4:0]  o_len,
    output reg         o_flast
);
    `include "huff_tables.vh"

    wire        tbl  = (i_comp != 2'd0);
    wire [20:0] e    = i_is_dc ? huff_dc(tbl, i_size) : huff_ac(tbl, {i_run, i_size});
    wire [4:0]  clen = e[20:16];
    wire [15:0] code = e[15:0];
    wire [10:0] amp  = i_amp & ((11'd1 << i_size) - 11'd1);

    assign i_ready = !o_valid || o_ready;

    always @(posedge clk) begin
        if (rst) o_valid <= 1'b0;
        else begin
            if (o_valid && o_ready) o_valid <= 1'b0;
            if (i_valid && i_ready) begin
                o_valid <= 1'b1;
                o_bits  <= ({11'd0, code} << i_size) | {16'd0, amp};
                o_len   <= clen + {1'b0, i_size};
                o_flast <= i_flast;
            end
        end
    end
endmodule
`default_nettype wire
