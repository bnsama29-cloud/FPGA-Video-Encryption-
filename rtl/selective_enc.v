// selective_enc.v -- XOR keystream onto selected symbol bits (format compliant).
//
// mode: 0 off | 1 E1 AC signs | 2 E2 +DC signs | 3 E3 +AC amplitude bits
//       | 4 E4 +DC amplitude bits | 5 E5 (contract v3): the same fields as E4
//       (the comparisons below are ">=", so mode 5 selects exactly what mode 4 selects)
// For a symbol with size s > 0 that is selected:
//   keystream bit 0 -> sign: if 1, invert all s amplitude bits (= negate value)
//   keystream bits 1..s-1 -> XORed onto the low s-1 amplitude bits (E3/E4)
// Sizes, runs and therefore Huffman code lengths never change.
// One clock of input buffering (skid_buf.v): i_ready comes from a flip-flop (150 MHz work, run 10).
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
    output reg         o_flast,
    // pulses when the symbol marked i_flast takes its keystream bits (contract v3: the end of a
    // restart segment, after which the lane restarts the keystream with the next nonce)
    output wire        ks_last
);
    // ---- input register slice (Vivado run 9, 150 MHz work): the symbol and everything derived
    // from it alone (keystream bits needed, flip masks) are computed here and stored in a
    // skid buffer, so i_ready is a flip-flop and the stall decision below starts from registers.
    wire has_bits = (i_size != 4'd0);
    wire sgn_en   = has_bits && (i_is_dc ? (mode >= 3'd2) : (mode >= 3'd1));
    wire amp_en   = has_bits && (i_is_dc ? (mode >= 3'd4) : (mode >= 3'd3));
    wire [4:0]  need    = (sgn_en ? 5'd1 : 5'd0) + (amp_en ? {1'b0, i_size} - 5'd1 : 5'd0);
    wire [10:0] mask_s  = (11'd1 << i_size) - 11'd1;           // s bits
    wire [10:0] smask   = sgn_en ? mask_s : 11'd0;              // inverted when keystream bit 0 is 1
    wire [10:0] amask   = amp_en ? (mask_s >> 1) : 11'd0;       // s-1 bits XORed with bits 1..s-1

    localparam W = 1 + 4 + 4 + 11 + 1 + 2 + 1 + 5 + 11 + 11;
    wire          p_valid;
    wire          p_ready;
    wire [W-1:0]  p_data;
    skid_buf #(.W(W)) u_in (
        .clk(clk), .rst(rst),
        .i_valid(i_valid), .i_ready(i_ready),
        .i_data({i_is_dc, i_run, i_size, i_amp, i_eob, i_comp, i_flast, need, smask, amask}),
        .o_valid(p_valid), .o_ready(p_ready), .o_data(p_data));
    wire        p_is_dc, p_eob, p_flast;
    wire [3:0]  p_run, p_size;
    wire [10:0] p_amp, p_smask, p_amask;
    wire [1:0]  p_comp;
    wire [4:0]  p_need;
    assign {p_is_dc, p_run, p_size, p_amp, p_eob, p_comp, p_flast, p_need, p_smask, p_amask} = p_data;

    wire [10:0] flip  = (ks_bits[0] ? p_smask : 11'd0) ^ (ks_bits[11:1] & p_amask);

    wire out_free = !o_valid || o_ready;
    wire ks_ok    = (ks_avail >= p_need);
    assign p_ready = out_free && ks_ok;
    wire go = p_valid && p_ready;
    assign ks_take = go && (p_need != 5'd0);
    assign ks_n    = p_need;
    assign ks_last = go && p_flast;

    always @(posedge clk) begin
        if (rst) o_valid <= 1'b0;
        else begin
            if (o_valid && o_ready) o_valid <= 1'b0;
            if (go) begin
                o_valid <= 1'b1;
                o_is_dc <= p_is_dc; o_run <= p_run; o_size <= p_size;
                o_amp   <= p_amp ^ flip;
                o_eob   <= p_eob; o_comp <= p_comp; o_flast <= p_flast;
            end
        end
    end
endmodule
`default_nettype wire
