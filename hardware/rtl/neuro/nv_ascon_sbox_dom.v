// nv_ascon_sbox_dom: VERIFICATION ONLY, not part of the IP. One 5-bit column of the S-box layer of
// nv_ascon_round_dom.v (the round is bit-sliced: 64 identical columns between the share-wise linear layers), with the
// same DOM-indep structure, used for the PROLEAD robust-probing check (glitches and transitions).
// Golden model: software/model/ascon.py :: permutation() (the S-box column of one round; tb checks the recombined
// output against the 5-bit Ascon S-box)
//
// Every AND has independently shared operands (bug #84): the textbook form b_i = l_i ^ (~u & v) pairs operands that
// share a variable ((x1, x1^x2), (x3, x3^x4), (x3^x4, x0^x4)), and a glitch on the cross-domain product then sees
// both shares of that variable (PROLEAD: leakage). Rewritten, equal on all 32 inputs:
//   ~x1 & (x1^x2) = ~x1 & x2,   ~x3 & (x3^x4) = ~x3 & x4,
//   ~(x3^x4) & (x0^x4) = x0 ^ x3 x0 ^ x3 x4 ^ x4 x0     (three ANDs of independent pairs)
// Seven ANDs per column, one fresh bit each; products registered before compression.
`default_nettype none
module nv_ascon_sbox_dom (
    input  wire       clk,
    input  wire [4:0] x_s0,       // column bits x0..x4, share 0
    input  wire [4:0] x_s1,       // share 1
    input  wire [6:0] r,          // fresh randomness, one bit per AND
    output wire [4:0] y_s0,
    output wire [4:0] y_s1
);
    // share-wise linear inputs
    wire a0_0 = x_s0[0] ^ x_s0[4], a0_1 = x_s1[0] ^ x_s1[4];
    wire a2_0 = x_s0[2] ^ x_s0[1], a2_1 = x_s1[2] ^ x_s1[1];
    wire a4_0 = x_s0[4] ^ x_s0[3], a4_1 = x_s1[4] ^ x_s1[3];

    // AND operands (u, v); u inverted on share 0 where the S-box needs ~u
    //   k: 0 ~x1&x2  1 ~a2&x3  2 ~x3&x4  3 x3&x0  4 x3&x4  5 x4&x0  6 ~a0&x1
    wire [6:0] u0 = {~a0_0, x_s0[4], x_s0[3], x_s0[3], ~x_s0[3], ~a2_0, ~x_s0[1]};
    wire [6:0] u1 = { a0_1, x_s1[4], x_s1[3], x_s1[3],  x_s1[3],  a2_1,  x_s1[1]};
    wire [6:0] v0 = {x_s0[1], x_s0[0], x_s0[4], x_s0[0], x_s0[4], x_s0[3], x_s0[2]};
    wire [6:0] v1 = {x_s1[1], x_s1[0], x_s1[4], x_s1[0], x_s1[4], x_s1[3], x_s1[2]};
    // linear terms of b0..b4: a0, x1, a2, x3 ^ x0, a4
    wire [4:0] l0 = {a4_0, x_s0[3] ^ x_s0[0], a2_0, x_s0[1], a0_0};
    wire [4:0] l1 = {a4_1, x_s1[3] ^ x_s1[0], a2_1, x_s1[1], a0_1};

    reg [6:0] p00, p01, p10, p11;
    reg [4:0] q0, q1;
    always @(posedge clk) begin
        p00 <= u0 & v0;
        p11 <= u1 & v1;
        p01 <= (u0 & v1) ^ r;
        p10 <= (u1 & v0) ^ r;
        q0  <= l0;
        q1  <= l1;
    end
    wire [6:0] z0 = p00 ^ p01;           // share 0 of each AND
    wire [6:0] z1 = p11 ^ p10;           // share 1
    wire [4:0] b0 = q0 ^ {z0[6], z0[3] ^ z0[4] ^ z0[5], z0[2], z0[1], z0[0]};
    wire [4:0] b1 = q1 ^ {z1[6], z1[3] ^ z1[4] ^ z1[5], z1[2], z1[1], z1[0]};

    // post-S-box affine part, share-wise (inversion of c2 on share 0 only)
    assign y_s0 = {b0[4], b0[3] ^ b0[2], ~b0[2], b0[1] ^ b0[0], b0[0] ^ b0[4]};
    assign y_s1 = {b1[4], b1[3] ^ b1[2],  b1[2], b1[1] ^ b1[0], b1[0] ^ b1[4]};
endmodule
`default_nettype wire
