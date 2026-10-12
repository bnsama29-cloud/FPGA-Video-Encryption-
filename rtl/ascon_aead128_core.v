// ascon_aead128_core.v -- NIST SP 800-232 Ascon-AEAD128, 1 round per clock.
//
// Block interface (one 128-bit block per handshake, byte i = blk_data[8i+7:8i]):
//   1. Pulse `init` with key/nonce. p12 runs (12 cycles).
//   2. Optional AD blocks (blk_type=0). Full blocks: blk_bytes=16, blk_last=0.
//      The LAST AD block must have blk_bytes < 16 (send an empty one with
//      blk_bytes=0 if the AD length is a multiple of 16). No AD -> send none.
//   3. Plaintext blocks (blk_type=1), same rule: full blocks blk_last=0, the
//      final block blk_bytes < 16 with blk_last=1. ct_data pulses with each.
//      The final PT block triggers finalisation; `tag_valid` pulses with the tag.
//   A keystream generator simply never sends the final PT block.
// Golden model: model/ascon.py :: encrypt()
`default_nettype none
module ascon_aead128_core (
    input  wire         clk,
    input  wire         rst,
    input  wire         init,
    input  wire [127:0] key,
    input  wire [127:0] nonce,
    input  wire         blk_valid,
    output wire         blk_ready,
    input  wire [127:0] blk_data,
    input  wire [4:0]   blk_bytes,
    input  wire         blk_type,     // 0 = associated data, 1 = plaintext
    input  wire         blk_last,
    output reg          ct_valid,
    output reg  [127:0] ct_data,
    output reg          tag_valid,
    output reg  [127:0] tag
);
    localparam [63:0] IV   = 64'h00001000808C0001;
    localparam [63:0] DSEP = 64'h8000000000000000;

    localparam S_IDLE = 2'd0, S_PERM = 2'd1, S_READY = 2'd2;
    localparam A_INIT = 2'd0, A_BLOCK = 2'd1, A_ADLAST = 2'd2, A_FINAL = 2'd3;

    reg [1:0]   state;
    reg [1:0]   after;        // what to do when the permutation finishes
    reg [3:0]   rnd;          // current round index (0..11)
    reg [319:0] s;
    reg [127:0] k;
    reg         dsep_done;

    wire [319:0] s_next;
    ascon_round u_round (.s_in(s), .rc({~rnd, rnd}), .s_out(s_next));

    assign blk_ready = (state == S_READY);
    wire accept = blk_valid && blk_ready;

    // byte mask for a partial block and the 0x01 padding byte
    reg [127:0] mask, pad;
    integer i;
    always @* begin
        for (i = 0; i < 16; i = i + 1) begin
            mask[8*i +: 8] = (i < blk_bytes) ? 8'hFF : 8'h00;
            pad[8*i +: 8]  = (blk_last && (i == blk_bytes)) ? 8'h01 : 8'h00;
        end
    end
    wire [127:0] blk_in = (blk_data & mask) ^ pad;

    // state after XORing the incoming block (and the domain-separation bit
    // if this is the first PT block and it has not been applied yet)
    wire [63:0]  x0_new = s[63:0]   ^ blk_in[63:0];
    wire [63:0]  x1_new = s[127:64] ^ blk_in[127:64];
    wire [63:0]  x4_new = s[319:256] ^ ((blk_type && !dsep_done) ? DSEP : 64'd0);

    always @(posedge clk) begin
        ct_valid  <= 1'b0;
        tag_valid <= 1'b0;
        if (rst) begin
            state     <= S_IDLE;
            dsep_done <= 1'b0;
        end else if (init) begin
            s         <= {nonce[127:64], nonce[63:0], key[127:64], key[63:0], IV};
            k         <= key;
            rnd       <= 4'd0;
            after     <= A_INIT;
            dsep_done <= 1'b0;
            state     <= S_PERM;
        end else begin
            case (state)
            S_PERM: begin
                s   <= s_next;
                rnd <= rnd + 4'd1;
                if (rnd == 4'd11) begin
                    state <= S_READY;
                    case (after)
                    A_INIT: begin                    // S3||S4 ^= K
                        s[255:192] <= s_next[255:192] ^ k[63:0];
                        s[319:256] <= s_next[319:256] ^ k[127:64];
                    end
                    A_ADLAST: begin                  // domain separation
                        s[319:256] <= s_next[319:256] ^ DSEP;
                        dsep_done  <= 1'b1;
                    end
                    A_FINAL: begin                   // tag = (S3, S4) ^ K
                        tag       <= {s_next[319:256] ^ k[127:64], s_next[255:192] ^ k[63:0]};
                        tag_valid <= 1'b1;
                        state     <= S_IDLE;
                    end
                    default: ;
                    endcase
                end
            end
            S_READY: if (accept) begin
                s[63:0]    <= x0_new;
                s[127:64]  <= x1_new;
                s[319:256] <= x4_new;
                if (blk_type) dsep_done <= 1'b1;
                state <= S_PERM;
                if (blk_type == 1'b0) begin               // associated data
                    rnd   <= 4'd4;                        // p8
                    after <= blk_last ? A_ADLAST : A_BLOCK;
                end else begin                            // plaintext
                    ct_valid <= 1'b1;
                    ct_data  <= {x1_new, x0_new} & mask;
                    if (blk_last) begin                   // finalisation, p12
                        s[191:128] <= s[191:128] ^ k[63:0];
                        s[255:192] <= s[255:192] ^ k[127:64];
                        rnd   <= 4'd0;
                        after <= A_FINAL;
                    end else begin
                        rnd   <= 4'd4;
                        after <= A_BLOCK;
                    end
                end
            end
            default: ;
            endcase
        end
    end
endmodule
`default_nettype wire
