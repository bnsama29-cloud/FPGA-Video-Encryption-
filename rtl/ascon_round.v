// ascon_round.v -- one Ascon permutation round (combinational).
// State packing: s = {x4, x3, x2, x1, x0}, x0 = s[63:0].
// Golden model: model/ascon.py :: permutation() (one round of it)
`default_nettype none
module ascon_round (
    input  wire [319:0] s_in,
    input  wire [7:0]   rc,      // round constant
    output wire [319:0] s_out
);
    wire [63:0] x0 = s_in[63:0];
    wire [63:0] x1 = s_in[127:64];
    wire [63:0] x2 = s_in[191:128] ^ {56'd0, rc};
    wire [63:0] x3 = s_in[255:192];
    wire [63:0] x4 = s_in[319:256];

    // substitution layer
    wire [63:0] a0 = x0 ^ x4;
    wire [63:0] a4 = x4 ^ x3;
    wire [63:0] a2 = x2 ^ x1;
    wire [63:0] b0 = a0 ^ (~x1 & a2);
    wire [63:0] b1 = x1 ^ (~a2 & x3);
    wire [63:0] b2 = a2 ^ (~x3 & a4);
    wire [63:0] b3 = x3 ^ (~a4 & a0);
    wire [63:0] b4 = a4 ^ (~a0 & x1);
    wire [63:0] c1 = b1 ^ b0;
    wire [63:0] c0 = b0 ^ b4;
    wire [63:0] c3 = b3 ^ b2;
    wire [63:0] c2 = ~b2;
    wire [63:0] c4 = b4;

    // linear diffusion layer: x ^= ror(x, n1) ^ ror(x, n2)
    function [63:0] ror;
        input [63:0] v;
        input integer n;
        begin
            ror = (v >> n) | (v << (64 - n));
        end
    endfunction

    assign s_out[63:0]    = c0 ^ ror(c0, 19) ^ ror(c0, 28);
    assign s_out[127:64]  = c1 ^ ror(c1, 61) ^ ror(c1, 39);
    assign s_out[191:128] = c2 ^ ror(c2, 1)  ^ ror(c2, 6);
    assign s_out[255:192] = c3 ^ ror(c3, 10) ^ ror(c3, 17);
    assign s_out[319:256] = c4 ^ ror(c4, 7)  ^ ror(c4, 41);
endmodule
`default_nettype wire
