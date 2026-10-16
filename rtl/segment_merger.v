// segment_merger.v -- contract v3: joins the lanes' restart segments back into one scan.
//
// Segment s (MCU row s) comes from lane s mod LANES. The merger copies segment s byte by byte
// from that lane until the byte marked "segment last", then (unless s is the frame's last
// segment) writes the restart marker 0xFF, 0xD0 + (s mod 8) and moves on to the next lane.
// The result is exactly model/entropy.py :: join_restart() of the segments in natural order,
// so the bytes do not depend on LANES. Restart markers are not byte-stuffed (T.81 B.1.1.5).
// One output byte per clock.
// Golden model: model/hw.py :: encode_frame_v3() (scan = seg0 RST0 seg1 RST1 ...)
`default_nettype none
module segment_merger #(
    parameter LANES = 2,
    parameter LOG_L = 1                 // log2(LANES); LANES must be a power of two
) (
    input  wire               clk,
    input  wire               rst,
    input  wire               start,
    input  wire [7:0]         segs,     // number of segments in the frame (MCU rows)
    input  wire [LANES-1:0]   i_valid,
    output wire [LANES-1:0]   i_ready,
    input  wire [8*LANES-1:0] i_data,
    input  wire [LANES-1:0]   i_slast,
    output reg                o_valid,
    input  wire               o_ready,
    output reg  [7:0]         o_data,
    output reg                o_last    // final byte of the frame
);
    localparam P_DATA = 2'd0, P_FF = 2'd1, P_RST = 2'd2, P_DONE = 2'd3;
    reg [1:0] phase;
    reg [7:0] s;
    wire [LOG_L-1:0] lane;
    generate
        if (LANES == 1) begin : g_one
            assign lane = 1'b0;
        end else begin : g_many
            assign lane = s[LOG_L-1:0];
        end
    endgenerate

    wire       out_free = !o_valid || o_ready;
    wire       in_v     = i_valid[lane];
    wire [7:0] in_d     = i_data[8*lane +: 8];
    wire       in_l     = i_slast[lane];
    wire       pop      = (phase == P_DATA) && out_free && in_v;
    assign i_ready = pop ? ({{(LANES-1){1'b0}}, 1'b1} << lane) : {LANES{1'b0}};

    always @(posedge clk) begin
        if (rst || start) begin
            phase <= P_DATA; s <= 8'd0; o_valid <= 1'b0; o_last <= 1'b0;
        end else begin
            if (o_valid && o_ready) o_valid <= 1'b0;
            case (phase)
            P_DATA: if (pop) begin
                o_valid <= 1'b1; o_data <= in_d;
                o_last  <= in_l && (s == segs - 8'd1);
                if (in_l) phase <= (s == segs - 8'd1) ? P_DONE : P_FF;
            end
            P_FF: if (out_free) begin
                o_valid <= 1'b1; o_data <= 8'hFF; o_last <= 1'b0; phase <= P_RST;
            end
            P_RST: if (out_free) begin
                o_valid <= 1'b1; o_data <= {5'b11010, s[2:0]}; o_last <= 1'b0;
                s <= s + 8'd1; phase <= P_DATA;
            end
            default: ;
            endcase
        end
    end
endmodule
`default_nettype wire
