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
    // two 128-bit keystream slots: cur (being consumed) and nxt (prefetched)
    reg [127:0] cur, nxt;
    reg         cur_v, nxt_v, inflight;
    reg [6:0]   ptr;                    // bits of cur already used

    wire         blk_ready, ct_valid, tag_valid_unused;
    wire [127:0] ct_data, tag_unused;
    wire blk_valid = !start && ((cur_v ? 1 : 0) + (nxt_v ? 1 : 0) + (inflight ? 1 : 0) < 2);

    ascon_aead128_core u_core (
        .clk(clk), .rst(rst), .init(start), .key(key), .nonce(nonce),
        .blk_valid(blk_valid), .blk_ready(blk_ready),
        .blk_data(128'd0), .blk_bytes(5'd16), .blk_type(1'b1), .blk_last(1'b0),
        .ct_valid(ct_valid), .ct_data(ct_data),
        .tag_valid(tag_valid_unused), .tag(tag_unused));

    // look-ahead window
    wire [255:0] both    = {nxt, cur} >> ptr;
    wire [8:0]   bits_in = (cur_v ? (9'd128 - ptr) : 9'd0) + ((cur_v && nxt_v) ? 9'd128 : 9'd0);
    assign ks_bits  = both[15:0];
    assign ks_avail = (bits_in >= 9'd16) ? 5'd16 : bits_in[4:0];

    // consume, then insert a newly generated block
    reg [127:0] c_cur, c_nxt;
    reg         c_cv, c_nv;
    reg [7:0]   c_ptr;
    always @* begin
        c_cur = cur; c_nxt = nxt; c_cv = cur_v; c_nv = nxt_v;
        c_ptr = {1'b0, ptr} + ((ks_take && cur_v) ? {3'd0, ks_n} : 8'd0);
        if (c_ptr >= 8'd128) begin           // finished the current block
            c_cur = nxt; c_cv = nxt_v; c_nv = 1'b0;
            c_ptr = c_ptr - 8'd128;
        end
        if (ct_valid) begin
            if (!c_cv) begin c_cur = ct_data; c_cv = 1'b1; c_ptr = 8'd0; end
            else       begin c_nxt = ct_data; c_nv = 1'b1; end
        end
    end

    always @(posedge clk) begin
        if (rst || start) begin
            cur_v <= 1'b0; nxt_v <= 1'b0; inflight <= 1'b0; ptr <= 7'd0;
            cur <= 128'd0; nxt <= 128'd0;
        end else begin
            cur <= c_cur; nxt <= c_nxt; cur_v <= c_cv; nxt_v <= c_nv;
            ptr <= c_ptr[6:0];
            if (blk_valid && blk_ready) inflight <= 1'b1;
            else if (ct_valid)          inflight <= 1'b0;
        end
    end
endmodule
`default_nettype wire
