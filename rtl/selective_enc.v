// selective_enc.v -- XOR keystream onto selected symbol bits (format compliant).
//
// mode: 0 off | 1 E1 AC signs | 2 E2 +DC signs | 3 E3 +AC amplitude bits
//       | 4 E4 +DC amplitude bits
// For a symbol with size s > 0 that is selected:
//   keystream bit 0 -> sign: if 1, invert all s amplitude bits (= negate value)
//   keystream bits 1..s-1 -> XORed onto the low s-1 amplitude bits (E3/E4)
// Sizes, runs and therefore Huffman code lengths never change.
// Golden model: model/hw.py :: bits_needed(), encrypt_symbol()  (= model/selective.py)
`default_nettype none
module selective_enc (
    input  wire        clk,
    input  wire        rst,
    input  wire [2:0]  mode,
    // keystream window (keystream_gen.v)
    input  wire [15:0] ks_bits,
    input  wire [4:0]  ks_avail,
    output wire        ks_take,
    output wire [4:0]  ks_n,
    // symbol in
    input  wire        i_valid,
    output wire        i_ready,
    input  wire        i_is_dc,
    input  wire [3:0]  i_run,
    input  wire [3:0]  i_size,
    input  wire [10:0] i_amp,
    input  wire        i_eob,
    input  wire [1:0]  i_comp,
    input  wire        i_flast,
    // symbol out
    output reg         o_valid,
    input  wire        o_ready,
    output reg         o_is_dc,
    output reg  [3:0]  o_run,
    output reg  [3:0]  o_size,
    output reg  [10:0] o_amp,
    output reg         o_eob,
    output reg  [1:0]  o_comp,
    output reg         o_flast
);
    wire has_bits = (i_size != 4'd0);
    wire sgn_en   = has_bits && (i_is_dc ? (mode >= 3'd2) : (mode >= 3'd1));
    wire amp_en   = has_bits && (i_is_dc ? (mode >= 3'd4) : (mode >= 3'd3));
    wire [4:0] need = (sgn_en ? 5'd1 : 5'd0) + (amp_en ? {1'b0, i_size} - 5'd1 : 5'd0);

    wire [10:0] mask_s  = (11'd1 << i_size) - 11'd1;           // s bits
    wire [10:0] mask_s1 = mask_s >> 1;                          // s-1 bits
    wire [10:0] flip    = ((sgn_en && ks_bits[0]) ? mask_s : 11'd0)
                        ^ (amp_en ? (ks_bits[11:1] & mask_s1) : 11'd0);

    wire out_free = !o_valid || o_ready;
    wire ks_ok    = (ks_avail >= need);
    assign i_ready = out_free && ks_ok;
    wire go = i_valid && i_ready;
    assign ks_take = go && (need != 5'd0);
    assign ks_n    = need;

    always @(posedge clk) begin
        if (rst) o_valid <= 1'b0;
        else begin
            if (o_valid && o_ready) o_valid <= 1'b0;
            if (go) begin
                o_valid <= 1'b1;
                o_is_dc <= i_is_dc; o_run <= i_run; o_size <= i_size;
                o_amp   <= i_amp ^ flip;
                o_eob   <= i_eob; o_comp <= i_comp; o_flast <= i_flast;
            end
        end
    end
endmodule
`default_nettype wire
