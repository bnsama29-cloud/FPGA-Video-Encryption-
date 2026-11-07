// nv_ascon_core_u: Ascon-AEAD128 (NIST SP 800-232) with U rounds per clock, U in {1, 2, 4} (DESIGN §6.2, §6.3).
// Golden model: software/model/ascon.py :: encrypt()
//
// Same block interface and the same function as hardware/rtl/ascon_aead128_core.v (paper 1, U = 1), which is
// not edited: init, AD blocks (type 0), PT blocks (type 1), blk_bytes < 16 on the last block of each type,
// ct_valid pulses with each PT block, tag_valid pulses with the tag. U chained ascon_round instances run U
// rounds per clock; U divides both 12 (p12) and 8 (p8), so a permutation takes 12/U or 8/U clocks.
// Block cost: 8/U + 1 clk (U = 1: 9, U = 2: 5, U = 4: 3).
`default_nettype none
module nv_ascon_core_u #(
    parameter U = 1
) (
    input  wire         clk,
    input  wire         rst,
    input  wire         init,
    input  wire [127:0] key,
    input  wire [127:0] nonce,
    input  wire         blk_valid,
    output wire         blk_ready,
    input  wire [127:0] blk_data,
    input  wire [4:0]   blk_bytes,
    input  wire         blk_type,
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
    localparam [3:0] LAST_RND = 4'd12 - U;          // round index at the start of the last clock

    reg [1:0]   state;
    reg [1:0]   after;
    reg [3:0]   rnd;
    reg [319:0] s;
    reg [127:0] k;
    reg         dsep_done;

    // U rounds in one clock: round rnd, rnd+1, ..., rnd+U-1
    wire [319:0] chain [0:U];
    assign chain[0] = s;
    genvar g;
    generate
        for (g = 0; g < U; g = g + 1) begin : rounds
            wire [3:0] r = rnd + g;
            ascon_round u_round (.s_in(chain[g]), .rc({~r, r}), .s_out(chain[g + 1]));
        end
    endgenerate
    wire [319:0] s_next = chain[U];

    assign blk_ready = (state == S_READY);
    wire accept = blk_valid && blk_ready;

    reg [127:0] mask, pad;
    integer i;
    always @* begin
        for (i = 0; i < 16; i = i + 1) begin
            mask[8*i +: 8] = (i < blk_bytes) ? 8'hFF : 8'h00;
            pad[8*i +: 8]  = (blk_last && (i == blk_bytes)) ? 8'h01 : 8'h00;
        end
    end
    wire [127:0] blk_in = (blk_data & mask) ^ pad;
    wire [63:0]  x0_new = s[63:0]    ^ blk_in[63:0];
    wire [63:0]  x1_new = s[127:64]  ^ blk_in[127:64];
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
                rnd <= rnd + U;
                if (rnd == LAST_RND) begin
                    state <= S_READY;
                    case (after)
                    A_INIT: begin
                        s[255:192] <= s_next[255:192] ^ k[63:0];
                        s[319:256] <= s_next[319:256] ^ k[127:64];
                    end
                    A_ADLAST: begin
                        s[319:256] <= s_next[319:256] ^ DSEP;
                        dsep_done  <= 1'b1;
                    end
                    A_FINAL: begin
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
                if (blk_type == 1'b0) begin
                    rnd   <= 4'd4;
                    after <= blk_last ? A_ADLAST : A_BLOCK;
                end else begin
                    ct_valid <= 1'b1;
                    ct_data  <= {x1_new, x0_new} & mask;
                    if (blk_last) begin
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
