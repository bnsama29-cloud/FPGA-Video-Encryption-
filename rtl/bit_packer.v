// bit_packer.v -- MSB-first bit packer, 0xFF -> 0xFF 0x00 byte stuffing,
// final byte padded with 1s. Accepts one chunk (<= 27 bits) per clock while
// there is room in the 64-bit accumulator, emits one byte per clock.
// The chunk carrying i_flast ends the frame: the packer flushes and marks the
// final output byte with o_last.
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
    output reg         o_valid,
    input  wire        o_ready,
    output reg  [7:0]  o_data,
    output reg         o_last
);
    reg [63:0] acc;            // left-aligned: valid bits are acc[63 -: n]
    reg [6:0]  n;
    reg        flushing;       // frame's last chunk accepted, draining
    reg        stuff;          // a 0x00 must follow the 0xFF just sent
    reg        stuff_last;

    wire out_free = !o_valid || o_ready;
    assign i_ready = !flushing && (n <= 7'd37);
    wire take = i_valid && i_ready;

    // ---- output decision for this clock
    reg        emit, emit_last, emit_stuff, take_byte;
    reg [7:0]  emit_byte;
    reg [63:0] acc1;           // after removing an emitted byte
    reg [6:0]  n1;
    always @* begin
        emit = 1'b0; emit_last = 1'b0; emit_stuff = 1'b0; take_byte = 1'b0;
        emit_byte = 8'h00; acc1 = acc; n1 = n;
        if (out_free) begin
            if (stuff) begin
                emit = 1'b1; emit_byte = 8'h00; emit_last = stuff_last;
            end else if (n >= 7'd8) begin
                emit = 1'b1; take_byte = 1'b1;
                emit_byte = acc[63:56];
                acc1 = acc << 8; n1 = n - 7'd8;
                emit_last = flushing && (n == 7'd8);
            end else if (flushing && n != 7'd0) begin   // pad final byte with 1s
                emit = 1'b1; take_byte = 1'b1;
                emit_byte = acc[63:56] | (8'hFF >> n);
                acc1 = 64'd0; n1 = 7'd0;
                emit_last = 1'b1;
            end
            emit_stuff = take_byte && (emit_byte == 8'hFF);
        end
    end

    // ---- append the incoming chunk after the emitted byte is removed
    wire [63:0] chunk = {37'd0, i_bits} & ((64'd1 << i_len) - 64'd1);
    wire [6:0]  shamt = 7'd64 - n1 - {2'd0, i_len};
    wire [63:0] acc2  = take ? (acc1 | (chunk << shamt)) : acc1;
    wire [6:0]  n2    = take ? (n1 + {2'd0, i_len}) : n1;

    always @(posedge clk) begin
        if (rst) begin
            acc <= 64'd0; n <= 7'd0; flushing <= 1'b0; stuff <= 1'b0;
            o_valid <= 1'b0; o_last <= 1'b0;
        end else begin
            acc <= acc2;
            n   <= n2;
            if (take && i_flast) flushing <= 1'b1;
            if (o_valid && o_ready) o_valid <= 1'b0;
            if (emit) begin
                o_valid <= 1'b1;
                o_data  <= emit_byte;
                o_last  <= emit_last && !emit_stuff;
                if (stuff) stuff <= 1'b0;
                if (emit_stuff) begin stuff <= 1'b1; stuff_last <= emit_last; end
                if (emit_last && !emit_stuff) flushing <= 1'b0;
                if (stuff && stuff_last) flushing <= 1'b0;
            end
        end
    end
endmodule
`default_nettype wire
