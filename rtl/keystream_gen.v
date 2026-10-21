// keystream_gen.v -- Ascon-AEAD128(K, N_enc) keystream = ciphertext of zeros.
//
// Keystream port (to selective_enc.v): a 16-bit look-ahead window.
//   ks_bits[0] is the next unused keystream bit, ks_avail = number of valid
//   bits in the window (0..16). The consumer pulses ks_take with ks_n (1..12)
//   bits, ks_n <= ks_avail. This lets the encryption stage take all bits for
//   one symbol in one clock (the 1-bit-per-request port in the project plan
//   would cost up to 12 clocks per symbol in mode E3/E4).
// Bit order: bit i = bit (i mod 8) of keystream byte (i div 8).
// Golden model: model/ascon.py :: keystream_bits()
`default_nettype none
module keystream_gen (
    input  wire         clk,
    input  wire         rst,
    input  wire         start,          // pulse at frame start (new nonce)
    input  wire [127:0] key,
    input  wire [127:0] nonce,
    output wire [15:0]  ks_bits,
    output wire [4:0]   ks_avail,
    input  wire         ks_take,
    input  wire [4:0]   ks_n
);
    // Two 128-bit keystream slots used as a ring (150 MHz work, Vivado run 9). The old version
    // copied nxt into cur when cur was used up: a 128-bit multiplexer whose select came from
    // ptr + ks_n, i.e. from the consumer's stall decision (9 logic levels, fan-out 133, the
    // slowest path of the single pipeline at 125 MHz). Now the blocks never move. ptr[7] names the
    // slot being read, a new block is written only into a slot that is free according to
    // registers, and ks_avail is a register computed from the next state. The bits handed out,
    // their order and the clock on which each becomes available are exactly as before.
    reg [127:0] slot0, slot1;
    reg         v0, v1, inflight;
    reg [7:0]   ptr;                    // ptr[7]: current slot, ptr[6:0]: bits of it already used
    reg [4:0]   avail;
    initial begin slot0 = 128'd0; slot1 = 128'd0; end   // power-up value (no X window in simulation)

    wire         blk_ready, ct_valid, tag_valid_unused;
    wire [127:0] ct_data, tag_unused;
    wire blk_valid = !start && ((v0 ? 1 : 0) + (v1 ? 1 : 0) + (inflight ? 1 : 0) < 2);

    ascon_aead128_core u_core (
        .clk(clk), .rst(rst), .init(start), .key(key), .nonce(nonce),
        .blk_valid(blk_valid), .blk_ready(blk_ready),
        .blk_data(128'd0), .blk_bytes(5'd16), .blk_type(1'b1), .blk_last(1'b0),
        .ct_valid(ct_valid), .ct_data(ct_data),
        .tag_valid(tag_valid_unused), .tag(tag_unused));

    wire         cs     = ptr[7];
    wire         v_cur  = cs ? v1 : v0;
    // look-ahead window: the current slot from bit ptr[6:0] on, then the other slot
    wire [255:0] both   = cs ? {slot0, slot1} : {slot1, slot0};
    wire [255:0] window = both >> ptr[6:0];
    assign ks_bits  = window[15:0];
    assign ks_avail = avail;

    // next state: consume, then a new block goes into the free slot (decided from registers only:
    // the current slot if nothing is held, else the other one; at most one slot is ever valid
    // when a block arrives, because at most two blocks are held or in flight)
    wire [7:0] used = {1'b0, ptr[6:0]} + ((ks_take && v_cur) ? {3'd0, ks_n} : 8'd0);
    wire       done = used[7];                       // the current slot is used up
    wire       wsel = v_cur ? ~cs : cs;              // slot that takes a new block
    wire       wr   = ct_valid;
    wire [7:0] n_ptr = {cs ^ done, used[6:0]};
    wire       n_v0 = (wr && !wsel) ? 1'b1 : ((done && !cs) ? 1'b0 : v0);
    wire       n_v1 = (wr &&  wsel) ? 1'b1 : ((done &&  cs) ? 1'b0 : v1);
    wire       n_vc = n_ptr[7] ? n_v1 : n_v0;
    wire       n_vo = n_ptr[7] ? n_v0 : n_v1;
    wire [7:0] left = 8'd128 - {1'b0, n_ptr[6:0]};   // bits left in the (next) current slot
    wire [4:0] n_avail = !n_vc ? 5'd0 : ((n_vo || left >= 8'd16) ? 5'd16 : left[4:0]);

    always @(posedge clk) begin
        if (wr && !wsel) slot0 <= ct_data;
        if (wr &&  wsel) slot1 <= ct_data;
    end

    always @(posedge clk) begin
        if (rst || start) begin
            v0 <= 1'b0; v1 <= 1'b0; inflight <= 1'b0; ptr <= 8'd0; avail <= 5'd0;
        end else begin
            v0 <= n_v0; v1 <= n_v1; ptr <= n_ptr; avail <= n_avail;
            if (blk_valid && blk_ready) inflight <= 1'b1;
            else if (ct_valid)          inflight <= 1'b0;
        end
    end
endmodule
`default_nettype wire
