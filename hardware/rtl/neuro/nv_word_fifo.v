// nv_word_fifo: BRAM FIFO behind the fixed-latency section, 512 x 35 b (word, kind, last) (DESIGN §6.1, §6.2).
// Golden model: n/a (storage; order and content are checked through nv_top against software/neuro/sender.py).
//
// Write side has no ready: nv_top admits a word into nv_feistel only while the credit counter is > 0, so a
// word never finds the FIFO full (`overflow` is a sticky error flag for the testbench). Read side is
// first-word-fall-through: a synchronous BRAM read into the output register, so Vivado maps `mem` to one
// RAMB18 in 512 x 36 mode. Capacity DEPTH (memory) + 1 (output register); the credit counter starts at DEPTH.
`default_nettype none
module nv_word_fifo #(
    parameter DEPTH = 512,
    parameter AW    = 9,
    parameter WIDTH = 35
) (
    input  wire             clk,
    input  wire             rst,
    input  wire             w_en,
    input  wire [WIDTH-1:0] w_data,
    output reg              o_valid,
    input  wire             o_ready,
    output reg  [WIDTH-1:0] o_data,
    output reg  [AW:0]      count,         // words in memory (not counting the output register)
    output reg              overflow
);
    reg [WIDTH-1:0] mem [0:DEPTH-1];
    reg [AW-1:0]    wp, rp;
    wire load = (count != 0) && (!o_valid || o_ready);
    always @(posedge clk) begin
        if (w_en) mem[wp] <= w_data;
        if (load) o_data <= mem[rp];
    end
    always @(posedge clk) begin
        if (rst) begin
            wp <= 0; rp <= 0; count <= 0; o_valid <= 1'b0; overflow <= 1'b0;
        end else begin
            if (w_en) wp <= wp + 1'b1;
            if (load) rp <= rp + 1'b1;
            count <= count + (w_en ? 1'b1 : 1'b0) - (load ? 1'b1 : 1'b0);
            if (w_en && !load && count == DEPTH) overflow <= 1'b1;
            if (load)                 o_valid <= 1'b1;
            else if (o_valid && o_ready) o_valid <= 1'b0;
        end
    end
endmodule
`default_nettype wire
