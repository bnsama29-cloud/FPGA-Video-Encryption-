// nv_sdp_ram: simple dual-port RAM, one write port and one registered read port (Vivado SDP template).
// Golden model: n/a (storage for software/neuro/feistel.py :: Tables).
// Read latency 1 clk: rdata = mem[raddr] of the previous clock.
`default_nettype none
module nv_sdp_ram #(
    parameter DEPTH = 2048,
    parameter AW    = 11,
    parameter WIDTH = 11
) (
    input  wire             clk,
    input  wire             we,
    input  wire [AW-1:0]    waddr,
    input  wire [WIDTH-1:0] wdata,
    input  wire [AW-1:0]    raddr,
    output reg  [WIDTH-1:0] rdata
);
    reg [WIDTH-1:0] mem [0:DEPTH-1];
    always @(posedge clk) begin
        if (we) mem[waddr] <= wdata;
        rdata <= mem[raddr];
    end
endmodule
`default_nettype wire
