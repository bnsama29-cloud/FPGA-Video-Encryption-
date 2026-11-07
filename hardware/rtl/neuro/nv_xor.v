// nv_xor: V1/V3 field XOR with keystream K_pol (DESIGN §4.2, §6.2).
// Golden model: software/neuro/levels.py :: xor_fields()   (stage view software/neuro/hw.py :: xor_word())
//
// Each word marked in_xor (a real CD word at V1/V3) takes 1 + b keystream bits k (bit 0 = first bit) and
//     word ^= (k[0] << 28) | ((k >> 1) & (2^b - 1)) << 22          (b = 0 at V1)
// Other words pass unchanged and take no bits. keystream_gen restarts at `start` (nonce (sid, ctr, 0) of the
// next packet); the stage stalls while ks_avail < 1 + b (counted outside as KS_WAIT). ks_n comes from a
// register (paper-1 bug #38). valid/ready on both sides; data held while valid && !ready.
`default_nettype none
module nv_xor #(
    parameter MW = 8                    // width of the side-band passed along with each word
) (
    input  wire         clk,
    input  wire         rst,
    input  wire         start,
    input  wire [127:0] key,
    input  wire [127:0] nonce,
    input  wire [2:0]   b,              // ts_bits (0 at V1, 1..6 at V3); held stable during a packet
    // input
    input  wire         in_valid,
    output wire         in_ready,
    input  wire [31:0]  in_word,
    input  wire         in_xor,
    input  wire [MW-1:0] in_meta,
    // output
    output reg          out_valid,
    input  wire         out_ready,
    output reg  [31:0]  out_word,
    output reg  [MW-1:0] out_meta,
    output wire         ks_stall        // input waiting only for keystream
);
    wire [15:0] ks_bits;
    wire [4:0]  ks_avail;
    reg  [4:0]  ks_n;
    always @(posedge clk) ks_n <= {2'b00, b} + 5'd1;

    wire need    = in_valid && in_xor;
    wire ks_ok   = !need || (ks_avail >= ks_n);
    wire space   = !out_valid || out_ready;
    assign in_ready = space && ks_ok && !start;
    wire fire    = in_valid && in_ready;
    wire ks_take = fire && in_xor;
    assign ks_stall = in_valid && space && !ks_ok;

    keystream_gen ksg (
        .clk(clk), .rst(rst), .start(start), .key(key), .nonce(nonce),
        .ks_bits(ks_bits), .ks_avail(ks_avail), .ks_take(ks_take), .ks_n(ks_n));

    wire [5:0]  tsmask = (6'b111111 >> (3'd6 - b));
    wire [31:0] mask   = {3'b000, ks_bits[0], (ks_bits[6:1] & tsmask), 22'd0};

    always @(posedge clk) begin
        if (rst) begin
            out_valid <= 1'b0;
        end else if (space) begin
            out_valid <= fire;
            if (fire) begin
                out_word <= in_xor ? (in_word ^ mask) : in_word;
                out_meta <= in_meta;
            end
        end
    end
endmodule
`default_nettype wire
