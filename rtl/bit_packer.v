// bit_packer.v -- MSB-first bit packer, 0xFF -> 0xFF 0x00 byte stuffing,
// final byte padded with 1s. Accepts one chunk (<= 27 bits) per clock while
// there is room in the 64-bit accumulator, emits one byte per clock.
// The chunk carrying i_flast ends the frame: the packer flushes and marks the
// final output byte with o_last.
// Input and output each pass a skid buffer (skid_buf.v): 2 clocks more latency, same bytes.
// Golden model: model/hw.py :: pack_bytes()
`default_nettype none
module bit_packer (
    input  wire        clk,
    input  wire        rst,
    input  wire        i_valid,
    output wire        i_ready,
    input  wire [26:0] i_bits,
    input  wire [4:0]  i_len,
    input  wire        i_flast,
    output wire        o_valid,
    input  wire        o_ready,
    output wire [7:0]  o_data,
    output wire        o_last
);
    wire       o_valid_w, o_last_w;
    wire [7:0] o_data_w;
    assign o_valid = o_valid_w;
    assign o_data  = o_data_w;
    assign o_last  = o_last_w;

    // ---- input slice (150 MHz work, Vivado run 9). The chunk is masked to i_len bits and
    // left-aligned in 32 bits on the way in, and stored in a skid buffer, so i_ready is a
    // flip-flop and the accumulator update below shifts by the registered fill level n only.
    // The old version shifted by 64 - n1 - len, where n1 already depended on this clock's
    // output decision: 9 logic levels through a carry chain, the slowest path at 125 MHz.
    wire [31:0] in_al = ({5'd0, i_bits} & ((32'd1 << i_len) - 32'd1)) << (6'd32 - {1'b0, i_len});
    wire        a_valid;
    wire        a_ready;
    wire [37:0] a_data;
    skid_buf #(.W(38)) u_in (
        .clk(clk), .rst(rst),
        .i_valid(i_valid), .i_ready(i_ready), .i_data({i_flast, i_len, in_al}),
        .o_valid(a_valid), .o_ready(a_ready), .o_data(a_data));
    wire        a_flast = a_data[37];
    wire [4:0]  a_len   = a_data[36:32];
    wire [31:0] a_al    = a_data[31:0];

    // ---- output slice: emitted bytes go through a skid buffer too, so the downstream ready
    // (tag unit, word packer or FIFO) does not reach the accumulator in the same clock.
    wire       q_ready;
    reg        q_valid;
    reg  [7:0] q_data;
    reg        q_last;
    skid_buf #(.W(9)) u_out (
        .clk(clk), .rst(rst),
        .i_valid(q_valid), .i_ready(q_ready), .i_data({q_last, q_data}),
        .o_valid(o_valid_w), .o_ready(o_ready), .o_data({o_last_w, o_data_w}));

    reg [63:0] acc;            // left-aligned: valid bits are acc[63 -: n], the rest are 0
    reg [6:0]  n;
    reg        flushing;       // frame's last chunk accepted, draining
    reg        stuff;          // a 0x00 must follow the 0xFF just sent
    reg        stuff_last;

    wire out_free = !q_valid || q_ready;
    assign a_ready = !flushing && (n <= 7'd37);
    wire take = a_valid && a_ready;

    // ---- output decision for this clock (from registers)
    reg        emit, emit_last, emit_stuff, take_byte, pad;
    reg [7:0]  emit_byte;
    always @* begin
        emit = 1'b0; emit_last = 1'b0; emit_stuff = 1'b0; take_byte = 1'b0; pad = 1'b0;
        emit_byte = 8'h00;
        if (out_free) begin
            if (stuff) begin
                emit = 1'b1; emit_byte = 8'h00; emit_last = stuff_last;
            end else if (n >= 7'd8) begin
                emit = 1'b1; take_byte = 1'b1;
                emit_byte = acc[63:56];
                emit_last = flushing && (n == 7'd8);
            end else if (flushing && n != 7'd0) begin   // pad final byte with 1s
                emit = 1'b1; pad = 1'b1;
                emit_byte = acc[63:56] | (8'hFF >> n);
                emit_last = 1'b1;
            end
            emit_stuff = (take_byte || pad) && (emit_byte == 8'hFF);
        end
    end

    // ---- append the chunk right after the n valid bits, then drop the emitted byte. Same bits
    // as appending after n - 8 bits of the shifted accumulator: a byte is only emitted when
    // n >= 8, so the chunk never touches acc[63:56].
    wire [63:0] acc_a = take ? (acc | ({a_al, 32'd0} >> n[5:0])) : acc;   // n <= 37 whenever take
    wire [63:0] acc2  = pad ? 64'd0 : (take_byte ? (acc_a << 8) : acc_a);
    wire [6:0]  n2    = pad ? 7'd0 : (n - (take_byte ? 7'd8 : 7'd0) + (take ? {2'd0, a_len} : 7'd0));

    always @(posedge clk) begin
        if (rst) begin
            acc <= 64'd0; n <= 7'd0; flushing <= 1'b0; stuff <= 1'b0;
            q_valid <= 1'b0; q_last <= 1'b0;
        end else begin
            acc <= acc2;
            n   <= n2;
            if (take && a_flast) flushing <= 1'b1;
            if (q_valid && q_ready) q_valid <= 1'b0;
            if (emit) begin
                q_valid <= 1'b1;
                q_data  <= emit_byte;
                q_last  <= emit_last && !emit_stuff;
                if (stuff) stuff <= 1'b0;
                if (emit_stuff) begin stuff <= 1'b1; stuff_last <= emit_last; end
                if (emit_last && !emit_stuff) flushing <= 1'b0;
                if (stuff && stuff_last) flushing <= 1'b0;
            end
        end
    end
endmodule
`default_nettype wire
