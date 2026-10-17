// byte_fifo.v -- synchronous FIFO of 8-bit bytes + 1 flag bit, show-ahead output register.
// Used between an encoder lane's bit packer and the segment merger (contract v3): while the
// merger copies another lane's segment, this lane keeps coding into its FIFO instead of stalling.
// The memory is read with an enable into the output register, so it maps to block RAM.
// The size does not affect correctness (a full FIFO just stalls the lane), only how much the
// lanes overlap; see experiments/lanes_rtl_throughput.py for the measured effect.
`default_nettype none
module byte_fifo #(
    parameter LOG_DEPTH = 11
) (
    input  wire       clk,
    input  wire       rst,
    input  wire       i_valid,
    output wire       i_ready,
    input  wire [8:0] i_data,
    output reg        o_valid,
    input  wire       o_ready,
    output reg  [8:0] o_data
);
    localparam DEPTH = 1 << LOG_DEPTH;
    reg [8:0] mem [0:DEPTH-1];
    reg [LOG_DEPTH:0] wptr, rptr;
    wire empty = (wptr == rptr);
    // `full` is a flip-flop computed from the next pointers, so i_ready leaves this module straight
    // from a register (Vivado run 5: the pointer compare -> bit packer accumulator path was -0.05 ns).
    reg  full;
    assign i_ready = !full;
    wire wr = i_valid && !full;
    wire rd = !empty && (!o_valid || o_ready);
    wire [LOG_DEPTH:0] cnt_next = (wptr + wr) - (rptr + rd);   // wraps at the pointer width

    always @(posedge clk) begin
        if (wr) mem[wptr[LOG_DEPTH-1:0]] <= i_data;
        if (rd) o_data <= mem[rptr[LOG_DEPTH-1:0]];
    end
    always @(posedge clk) begin
        if (rst) begin
            wptr <= 0; rptr <= 0; o_valid <= 1'b0; full <= 1'b0;
        end else begin
            if (wr) wptr <= wptr + 1'b1;
            if (rd) rptr <= rptr + 1'b1;
            full <= (cnt_next == DEPTH);
            if (rd) o_valid <= 1'b1;
            else if (o_ready) o_valid <= 1'b0;
        end
    end
endmodule
`default_nettype wire
