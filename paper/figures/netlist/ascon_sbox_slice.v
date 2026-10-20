// One bit slice j of the substitution layer of rtl/ascon_round.v (p_C on x2, then p_S), operator for
// operator, for schematic generation only. rc_j is bit j of the round constant (zero for j >= 8).
// tests/test_paper_figures.py checks it against the full RTL round on random states.
module ascon_sbox_slice (
    input  wire x0, x1, x2, x3, x4, rc_j,
    output wire c0, c1, c2, c3, c4
);
    wire x2c = x2 ^ rc_j;
    wire a0 = x0 ^ x4;
    wire a4 = x4 ^ x3;
    wire a2 = x2c ^ x1;
    wire b0 = a0 ^ (~x1 & a2);
    wire b1 = x1 ^ (~a2 & x3);
    wire b2 = a2 ^ (~x3 & a4);
    wire b3 = x3 ^ (~a4 & a0);
    wire b4 = a4 ^ (~a0 & x1);
    assign c1 = b1 ^ b0;
    assign c0 = b0 ^ b4;
    assign c3 = b3 ^ b2;
    assign c2 = ~b2;
    assign c4 = b4;
endmodule
