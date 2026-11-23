// nv_ascon_round_dom: ABLATION (leveled-masking cost estimate) only, not part of the IP. One Ascon round on a
// first-order Boolean sharing s = s0 ^ s1, with domain-oriented masking (DOM-indep) of the five AND terms of the
// S-box: every partial product is registered before the shares are compressed, so the round takes 1 clk and 320
// fresh random bits (64 per AND). Linear layers act share-wise; constants and inversions go to share 0 only.
// Golden model: software/model/ascon.py :: permutation() (one round; the recombined output equals ascon_round.v)
// Side-channel security is NOT evaluated here (no leakage test, no formal probing check): it is an area / Fmax
// estimate for the masked initialisation and finalisation of a leveled implementation.
`default_nettype none
module nv_ascon_round_dom (
    input  wire         clk,
    input  wire [319:0] s0_in,
    input  wire [319:0] s1_in,
    input  wire [7:0]   rc,
    input  wire [319:0] rnd,       // fresh randomness, 64 bits per AND (5 ANDs)
    output wire [319:0] s0_out,
    output wire [319:0] s1_out
);
    function [63:0] ror;
        input [63:0] v;
        input integer n;
        begin
            ror = (v >> n) | (v << (64 - n));
        end
    endfunction

    // share-wise pre-S-box affine part (constant on share 0 only)
    wire [63:0] x0_0 = s0_in[63:0],    x0_1 = s1_in[63:0];
    wire [63:0] x1_0 = s0_in[127:64],  x1_1 = s1_in[127:64];
    wire [63:0] x2_0 = s0_in[191:128] ^ {56'd0, rc}, x2_1 = s1_in[191:128];
    wire [63:0] x3_0 = s0_in[255:192], x3_1 = s1_in[255:192];
    wire [63:0] x4_0 = s0_in[319:256], x4_1 = s1_in[319:256];
    wire [63:0] a0_0 = x0_0 ^ x4_0, a0_1 = x0_1 ^ x4_1;
    wire [63:0] a4_0 = x4_0 ^ x3_0, a4_1 = x4_1 ^ x3_1;
    wire [63:0] a2_0 = x2_0 ^ x1_0, a2_1 = x2_1 ^ x1_1;

    // the five ANDs (~u & v): u inverted on share 0. Operands (u, v):
    //   b0: (x1, a2)  b1: (a2, x3)  b2: (x3, a4)  b3: (a4, a0)  b4: (a0, x1)
    wire [63:0] u0 [0:4];
    wire [63:0] u1 [0:4];
    wire [63:0] v0 [0:4];
    wire [63:0] v1 [0:4];
    assign u0[0] = ~x1_0; assign u1[0] = x1_1; assign v0[0] = a2_0; assign v1[0] = a2_1;
    assign u0[1] = ~a2_0; assign u1[1] = a2_1; assign v0[1] = x3_0; assign v1[1] = x3_1;
    assign u0[2] = ~x3_0; assign u1[2] = x3_1; assign v0[2] = a4_0; assign v1[2] = a4_1;
    assign u0[3] = ~a4_0; assign u1[3] = a4_1; assign v0[3] = a0_0; assign v1[3] = a0_1;
    assign u0[4] = ~a0_0; assign u1[4] = a0_1; assign v0[4] = x1_0; assign v1[4] = x1_1;

    // DOM-indep: inner-domain and refreshed cross-domain products, all registered
    reg [63:0] p00 [0:4];
    reg [63:0] p01 [0:4];
    reg [63:0] p10 [0:4];
    reg [63:0] p11 [0:4];
    // the linear terms each b_i adds, registered next to the products
    reg [63:0] l0 [0:4];
    reg [63:0] l1 [0:4];
    integer i;
    always @(posedge clk) begin
        for (i = 0; i < 5; i = i + 1) begin
            p00[i] <= u0[i] & v0[i];
            p11[i] <= u1[i] & v1[i];
            p01[i] <= (u0[i] & v1[i]) ^ rnd[64 * i +: 64];
            p10[i] <= (u1[i] & v0[i]) ^ rnd[64 * i +: 64];
        end
        l0[0] <= a0_0; l1[0] <= a0_1;      // b0 = a0 ^ (~x1 & a2)
        l0[1] <= x1_0; l1[1] <= x1_1;      // b1 = x1 ^ (~a2 & x3)
        l0[2] <= a2_0; l1[2] <= a2_1;      // b2 = a2 ^ (~x3 & a4)
        l0[3] <= x3_0; l1[3] <= x3_1;      // b3 = x3 ^ (~a4 & a0)
        l0[4] <= a4_0; l1[4] <= a4_1;      // b4 = a4 ^ (~a0 & x1)
    end

    wire [63:0] b0 [0:4];
    wire [63:0] b1 [0:4];
    genvar k;
    generate
        for (k = 0; k < 5; k = k + 1) begin : comp
            assign b0[k] = l0[k] ^ p00[k] ^ p01[k];
            assign b1[k] = l1[k] ^ p11[k] ^ p10[k];
        end
    endgenerate

    // share-wise post-S-box affine part (inversion of c2 on share 0 only) and linear diffusion
    wire [63:0] c1_0 = b0[1] ^ b0[0], c1_1 = b1[1] ^ b1[0];
    wire [63:0] c0_0 = b0[0] ^ b0[4], c0_1 = b1[0] ^ b1[4];
    wire [63:0] c3_0 = b0[3] ^ b0[2], c3_1 = b1[3] ^ b1[2];
    wire [63:0] c2_0 = ~b0[2],        c2_1 = b1[2];
    wire [63:0] c4_0 = b0[4],         c4_1 = b1[4];

    assign s0_out[63:0]    = c0_0 ^ ror(c0_0, 19) ^ ror(c0_0, 28);
    assign s0_out[127:64]  = c1_0 ^ ror(c1_0, 61) ^ ror(c1_0, 39);
    assign s0_out[191:128] = c2_0 ^ ror(c2_0, 1)  ^ ror(c2_0, 6);
    assign s0_out[255:192] = c3_0 ^ ror(c3_0, 10) ^ ror(c3_0, 17);
    assign s0_out[319:256] = c4_0 ^ ror(c4_0, 7)  ^ ror(c4_0, 41);
    assign s1_out[63:0]    = c0_1 ^ ror(c0_1, 19) ^ ror(c0_1, 28);
    assign s1_out[127:64]  = c1_1 ^ ror(c1_1, 61) ^ ror(c1_1, 39);
    assign s1_out[191:128] = c2_1 ^ ror(c2_1, 1)  ^ ror(c2_1, 6);
    assign s1_out[255:192] = c3_1 ^ ror(c3_1, 10) ^ ror(c3_1, 17);
    assign s1_out[319:256] = c4_1 ^ ror(c4_1, 7)  ^ ror(c4_1, 41);
endmodule
`default_nettype wire
