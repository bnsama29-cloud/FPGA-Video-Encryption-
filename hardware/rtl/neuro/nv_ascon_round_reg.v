// nv_ascon_round_reg: ABLATION reference only, not part of the IP. The unmasked ascon_round.v with registered input
// and output, so that its post-route area and Fmax compare with nv_ascon_round_dom (whose ANDs are registered).
// Golden model: software/model/ascon.py :: permutation() (one round)
`default_nettype none
module nv_ascon_round_reg (
    input  wire         clk,
    input  wire [319:0] s_in,
    input  wire [7:0]   rc,
    output reg  [319:0] s_out
);
    reg  [319:0] s_q;
    reg  [7:0]   rc_q;
    wire [319:0] s_n;
    ascon_round u (.s_in(s_q), .rc(rc_q), .s_out(s_n));
    always @(posedge clk) begin
        s_q   <= s_in;
        rc_q  <= rc;
        s_out <= s_n;
    end
endmodule
`default_nettype wire
