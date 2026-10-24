// axil_buttons.v -- BTN1..BTN3 of the PYNQ-Z2 as a read-only AXI-Lite peripheral (overlay
// secure_jpeg_lanes_tamper.bit only, board-day demonstration of the protection level).
//
// The protection level (E0..E5) is chosen by the ARM: the sender writes it to the encoder's MODE register
// and into the authenticated APP11 header of every frame. A button may therefore not change the mode in
// the fabric (header and scan would disagree and every frame would fail its tag); it only tells the ARM,
// and system/board/board_sender.py turns presses into the sender's existing "mode" command:
//   BTN1 = one level down, BTN2 = one level up, BTN3 = back to the automatic (adaptive) policy.
// BTN0 stays the tamper injector's one-shot button (system/board/axis_tamper.v); it is ignored here.
//
// Registers (32 bit, read-only; writes are accepted with OKAY and ignored):
//   0x0 ID     0xB7750001
//   0x4 STATE  bits [2:0] = debounced BTN3..BTN1 (1 = pressed)
//   0x8 COUNT  [7:0] presses of BTN1, [15:8] BTN2, [23:16] BTN3 (wrap at 256)
// A press counts once on the debounced rising edge, so the ARM can poll slowly and miss none.
// Debounce: the synchronised input must hold a new value for DEBOUNCE clocks (20 ms at 100 MHz).
// Golden model: none (test equipment, not part of the encoder); tb/test_axil_buttons.py checks it.
`default_nettype none
module axil_buttons #(
    parameter DEBOUNCE = 2000000
) (
    (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 clk CLK" *)
    (* X_INTERFACE_PARAMETER = "ASSOCIATED_BUSIF s_axil, ASSOCIATED_RESET rst" *)
    input  wire        clk,
    (* X_INTERFACE_INFO = "xilinx.com:signal:reset:1.0 rst RST" *)
    (* X_INTERFACE_PARAMETER = "POLARITY ACTIVE_HIGH" *)
    input  wire        rst,

    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axil AWADDR" *)
    (* X_INTERFACE_PARAMETER = "PROTOCOL AXI4LITE, DATA_WIDTH 32, ADDR_WIDTH 4" *)
    input  wire [3:0]  s_axil_awaddr,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axil AWPROT" *)  input  wire [2:0]  s_axil_awprot,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axil AWVALID" *) input  wire        s_axil_awvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axil AWREADY" *) output wire        s_axil_awready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axil WDATA" *)   input  wire [31:0] s_axil_wdata,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axil WSTRB" *)   input  wire [3:0]  s_axil_wstrb,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axil WVALID" *)  input  wire        s_axil_wvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axil WREADY" *)  output wire        s_axil_wready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axil BRESP" *)   output wire [1:0]  s_axil_bresp,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axil BVALID" *)  output reg         s_axil_bvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axil BREADY" *)  input  wire        s_axil_bready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axil ARADDR" *)  input  wire [3:0]  s_axil_araddr,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axil ARPROT" *)  input  wire [2:0]  s_axil_arprot,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axil ARVALID" *) input  wire        s_axil_arvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axil ARREADY" *) output wire        s_axil_arready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axil RDATA" *)   output reg  [31:0] s_axil_rdata,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axil RRESP" *)   output wire [1:0]  s_axil_rresp,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axil RVALID" *)  output reg         s_axil_rvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axil RREADY" *)  input  wire        s_axil_rready,

    input  wire [3:0]  btn              // PYNQ-Z2 push buttons; bit 0 (BTN0) belongs to axis_tamper
);
    localparam [31:0] ID = 32'hB7750001;

    // ---- per button: two-flip-flop synchroniser, debounce counter, press counter
    reg  [2:0]  s1, s2, deb;
    reg  [21:0] dcnt [0:2];
    reg  [7:0]  pcnt [0:2];
    integer i;
    always @(posedge clk) begin
        s1 <= btn[3:1];
        s2 <= s1;
        if (rst) begin
            deb <= 3'b000;
            for (i = 0; i < 3; i = i + 1) begin dcnt[i] <= 22'd0; pcnt[i] <= 8'd0; end
        end else begin
            for (i = 0; i < 3; i = i + 1) begin
                if (s2[i] == deb[i]) dcnt[i] <= 22'd0;
                else if (dcnt[i] == DEBOUNCE - 1) begin
                    dcnt[i] <= 22'd0;
                    deb[i]  <= s2[i];
                    if (s2[i]) pcnt[i] <= pcnt[i] + 8'd1;     // debounced rising edge = one press
                end else dcnt[i] <= dcnt[i] + 22'd1;
            end
        end
    end

    // ---- AXI-Lite: writes are acknowledged and ignored, reads return the registers
    wire wr = s_axil_awvalid && s_axil_wvalid && !s_axil_bvalid;
    assign s_axil_awready = wr;
    assign s_axil_wready  = wr;
    assign s_axil_bresp   = 2'b00;
    always @(posedge clk)
        if (rst) s_axil_bvalid <= 1'b0;
        else if (wr) s_axil_bvalid <= 1'b1;
        else if (s_axil_bready) s_axil_bvalid <= 1'b0;

    assign s_axil_arready = !s_axil_rvalid;
    assign s_axil_rresp   = 2'b00;
    always @(posedge clk) begin
        if (rst) begin
            s_axil_rvalid <= 1'b0;
            s_axil_rdata  <= 32'd0;
        end else begin
            if (s_axil_rvalid && s_axil_rready) s_axil_rvalid <= 1'b0;
            if (s_axil_arvalid && s_axil_arready) begin
                s_axil_rvalid <= 1'b1;
                case (s_axil_araddr[3:2])
                    2'd0:    s_axil_rdata <= ID;
                    2'd1:    s_axil_rdata <= {29'd0, deb};
                    2'd2:    s_axil_rdata <= {8'd0, pcnt[2], pcnt[1], pcnt[0]};
                    default: s_axil_rdata <= 32'd0;
                endcase
            end
        end
    end
endmodule
`default_nettype wire
