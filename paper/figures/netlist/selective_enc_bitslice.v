// One bit slice k of rtl/selective_enc.v, operator for operator, for schematic generation only
// (paper/figures/netlist/make_schematics.sh). In the RTL:
//   has_bits = (i_size != 0)
//   sgn_en   = has_bits && (i_is_dc ? (mode >= 2) : (mode >= 1))
//   amp_en   = has_bits && (i_is_dc ? (mode >= 4) : (mode >= 3))
//   flip     = ((sgn_en && ks_bits[0]) ? mask_s : 0) ^ (amp_en ? (ks_bits[11:1] & mask_s1) : 0)
//   o_amp   <= i_amp ^ flip                  with mask_s = (1 << size) - 1, mask_s1 = mask_s >> 1
// so bit k:  o_amp[k] = amp[k] ^ (sgn_en & ks[0] & m[k]) ^ (amp_en & ks[k+1] & m[k+1]).
// tests/test_paper_figures.py checks this slice against the full RTL module for every input.
module selective_enc_bitslice (
    input  wire [2:0] mode,
    input  wire       is_dc,
    input  wire [3:0] size,
    input  wire       ks0,      // ks_bits[0]: sign bit of the keystream window
    input  wire       ks_k1,    // ks_bits[k+1]
    input  wire       m_k,      // mask_s[k]   = (k < size)
    input  wire       m_k1,     // mask_s[k+1] = (k + 1 < size)
    input  wire       amp_k,    // i_amp[k]
    output wire       amp_out_k // D input of o_amp[k]
);
    wire has_bits = size[3] | size[2] | size[1] | size[0];      // (size != 0)
    wire sgn_en   = has_bits & (is_dc ? (mode >= 3'd2) : (mode >= 3'd1));
    wire amp_en   = has_bits & (is_dc ? (mode >= 3'd4) : (mode >= 3'd3));
    assign amp_out_k = amp_k ^ (sgn_en & ks0 & m_k) ^ (amp_en & ks_k1 & m_k1);
endmodule
