// sjpeg_bd_top.v -- block-design wrapper for secure_jpeg_top (PYNQ-Z2 overlay).
//
// Same ports as rtl/secure_jpeg_top.v, plus Vivado interface attributes so that the
// block design (future_work/board/block_design.tcl) sees one AXI4-Lite slave
// (s_axil), one AXI4-Stream slave (s_axis, pixels from the DMA), one AXI4-Stream
// master (m_axis, scan bytes to the DMA), the clock, an active-high reset and a
// level interrupt. No logic here: the verified RTL is used unchanged.
`default_nettype none
module sjpeg_bd_top (
    (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 clk CLK" *)
    (* X_INTERFACE_PARAMETER = "ASSOCIATED_BUSIF s_axil:s_axis:m_axis, ASSOCIATED_RESET rst, FREQ_HZ 100000000" *)
    input  wire        clk,
    (* X_INTERFACE_INFO = "xilinx.com:signal:reset:1.0 rst RST" *)
    (* X_INTERFACE_PARAMETER = "POLARITY ACTIVE_HIGH" *)
    input  wire        rst,

    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axil AWADDR" *)
    (* X_INTERFACE_PARAMETER = "PROTOCOL AXI4LITE, DATA_WIDTH 32, ADDR_WIDTH 8" *)
    input  wire [7:0]  s_axil_awaddr,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axil AWPROT" *)  input  wire [2:0]  s_axil_awprot,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axil AWVALID" *) input  wire        s_axil_awvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axil AWREADY" *) output wire        s_axil_awready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axil WDATA" *)   input  wire [31:0] s_axil_wdata,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axil WSTRB" *)   input  wire [3:0]  s_axil_wstrb,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axil WVALID" *)  input  wire        s_axil_wvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axil WREADY" *)  output wire        s_axil_wready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axil BRESP" *)   output wire [1:0]  s_axil_bresp,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axil BVALID" *)  output wire        s_axil_bvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axil BREADY" *)  input  wire        s_axil_bready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axil ARADDR" *)  input  wire [7:0]  s_axil_araddr,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axil ARPROT" *)  input  wire [2:0]  s_axil_arprot,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axil ARVALID" *) input  wire        s_axil_arvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axil ARREADY" *) output wire        s_axil_arready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axil RDATA" *)   output wire [31:0] s_axil_rdata,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axil RRESP" *)   output wire [1:0]  s_axil_rresp,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axil RVALID" *)  output wire        s_axil_rvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axil RREADY" *)  input  wire        s_axil_rready,

    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 s_axis TDATA" *)
    (* X_INTERFACE_PARAMETER = "TDATA_NUM_BYTES 4, HAS_TLAST 1, HAS_TKEEP 0" *)
    input  wire [31:0] s_axis_tdata,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 s_axis TVALID" *) input  wire        s_axis_tvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 s_axis TREADY" *) output wire        s_axis_tready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 s_axis TLAST" *)  input  wire        s_axis_tlast,

    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 m_axis TDATA" *)
    (* X_INTERFACE_PARAMETER = "TDATA_NUM_BYTES 4, HAS_TLAST 1, HAS_TKEEP 1" *)
    output wire [31:0] m_axis_tdata,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 m_axis TKEEP" *)  output wire [3:0]  m_axis_tkeep,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 m_axis TVALID" *) output wire        m_axis_tvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 m_axis TREADY" *) input  wire        m_axis_tready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 m_axis TLAST" *)  output wire        m_axis_tlast,

    (* X_INTERFACE_INFO = "xilinx.com:signal:interrupt:1.0 irq_done INTERRUPT" *)
    (* X_INTERFACE_PARAMETER = "SENSITIVITY LEVEL_HIGH" *)
    output wire        irq_done
);
    secure_jpeg_top #(.LOG_MAXW(11)) u_core (
        .clk(clk), .rst(rst),
        .s_axil_awaddr(s_axil_awaddr), .s_axil_awprot(s_axil_awprot), .s_axil_awvalid(s_axil_awvalid),
        .s_axil_awready(s_axil_awready), .s_axil_wdata(s_axil_wdata), .s_axil_wstrb(s_axil_wstrb),
        .s_axil_wvalid(s_axil_wvalid), .s_axil_wready(s_axil_wready), .s_axil_bresp(s_axil_bresp),
        .s_axil_bvalid(s_axil_bvalid), .s_axil_bready(s_axil_bready), .s_axil_araddr(s_axil_araddr),
        .s_axil_arprot(s_axil_arprot), .s_axil_arvalid(s_axil_arvalid), .s_axil_arready(s_axil_arready),
        .s_axil_rdata(s_axil_rdata), .s_axil_rresp(s_axil_rresp), .s_axil_rvalid(s_axil_rvalid),
        .s_axil_rready(s_axil_rready),
        .s_axis_tdata(s_axis_tdata), .s_axis_tvalid(s_axis_tvalid), .s_axis_tready(s_axis_tready),
        .s_axis_tlast(s_axis_tlast),
        .m_axis_tdata(m_axis_tdata), .m_axis_tkeep(m_axis_tkeep), .m_axis_tvalid(m_axis_tvalid),
        .m_axis_tready(m_axis_tready), .m_axis_tlast(m_axis_tlast),
        .irq_done(irq_done));
endmodule
`default_nettype wire
