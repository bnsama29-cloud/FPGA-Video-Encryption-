// axil_regs.v -- AXI4-Lite register file (ARM <-> fabric).
//
//  Offset Name        Access  Description
//  0x00   CTRL        RW      [0] START (write 1, self-clearing) [3:1] MODE (0 off, 1..4 = E1..E4)
//  0x04   STATUS      RO      [0] DONE [1] BUSY [2] TAG_VALID
//  0x08   VERSION     RO      0x5EC0_0100
//  0x10   WIDTH       RW      frame width  (multiple of 16)
//  0x14   HEIGHT      RW      frame height (multiple of 16)
//  0x18   FRAME_CTR   RW      frame counter (goes into both nonces)
//  0x1C   SESSION_ID  RW      random per session (goes into both nonces)
//  0x20.. KEY0..KEY3  WO      128-bit key, KEY0 = key bytes 0..3 (reads return 0)
//  0x30   OUT_BYTES   RO      scan bytes produced for the last frame
//  0x34.. TAG0..TAG3  RO      per-frame tag, TAG0 = tag bytes 0..3
//  0x44   QT_ADDR     RW      quantiser table address ([6] table, [5:0] index)
//  0x48   QT_DATA     WO      write a 17-bit reciprocal at QT_ADDR, QT_ADDR++
// WSTRB is honoured for RW registers.
`default_nettype none
module axil_regs (
    input  wire         clk,
    input  wire         rst,
    // AXI4-Lite slave
    input  wire [7:0]   s_axil_awaddr,
    input  wire [2:0]   s_axil_awprot,
    input  wire         s_axil_awvalid,
    output wire         s_axil_awready,
    input  wire [31:0]  s_axil_wdata,
    input  wire [3:0]   s_axil_wstrb,
    input  wire         s_axil_wvalid,
    output wire         s_axil_wready,
    output wire [1:0]   s_axil_bresp,
    output reg          s_axil_bvalid,
    input  wire         s_axil_bready,
    input  wire [7:0]   s_axil_araddr,
    input  wire [2:0]   s_axil_arprot,
    input  wire         s_axil_arvalid,
    output wire         s_axil_arready,
    output reg  [31:0]  s_axil_rdata,
    output wire [1:0]   s_axil_rresp,
    output reg          s_axil_rvalid,
    input  wire         s_axil_rready,
    // to the datapath
    output reg          start,
    output reg  [2:0]   mode,
    output reg  [11:0]  width,
    output reg  [11:0]  height,
    output reg  [31:0]  frame_ctr,
    output reg  [31:0]  session_id,
    output reg  [127:0] key,
    output reg          qt_we,
    output reg  [6:0]   qt_addr,
    output reg  [16:0]  qt_data,
    // from the datapath
    input  wire         done,
    input  wire         busy,
    input  wire         tag_valid,
    input  wire [31:0]  out_bytes,
    input  wire [127:0] tag
);
    localparam [31:0] VERSION = 32'h5EC0_0100;
    reg [6:0] qt_ptr;                         // the QT_ADDR register

    assign s_axil_bresp = 2'b00;
    assign s_axil_rresp = 2'b00;

    // write: accept address and data together
    wire wr = s_axil_awvalid && s_axil_wvalid && !s_axil_bvalid;
    assign s_axil_awready = wr;
    assign s_axil_wready  = wr;

    function [31:0] merge;                    // apply WSTRB to an old value
        input [31:0] old, data;
        input [3:0]  strb;
        integer i;
        begin
            for (i = 0; i < 4; i = i + 1)
                merge[8*i +: 8] = strb[i] ? data[8*i +: 8] : old[8*i +: 8];
        end
    endfunction

    wire [31:0] wd = s_axil_wdata;
    wire [3:0]  ws = s_axil_wstrb;

    always @(posedge clk) begin
        start <= 1'b0;
        qt_we <= 1'b0;
        if (rst) begin
            s_axil_bvalid <= 1'b0;
            mode <= 3'd0; width <= 12'd0; height <= 12'd0;
            frame_ctr <= 32'd0; session_id <= 32'd0; key <= 128'd0; qt_ptr <= 7'd0;
        end else begin
            if (s_axil_bvalid && s_axil_bready) s_axil_bvalid <= 1'b0;
            if (wr) begin
                s_axil_bvalid <= 1'b1;
                case (s_axil_awaddr[7:2])
                6'h00: if (ws[0]) begin start <= wd[0]; mode <= wd[3:1]; end
                6'h04: width      <= merge({20'd0, width},  wd, ws);
                6'h05: height     <= merge({20'd0, height}, wd, ws);
                6'h06: frame_ctr  <= merge(frame_ctr,  wd, ws);
                6'h07: session_id <= merge(session_id, wd, ws);
                6'h08: key[31:0]   <= merge(key[31:0],   wd, ws);
                6'h09: key[63:32]  <= merge(key[63:32],  wd, ws);
                6'h0A: key[95:64]  <= merge(key[95:64],  wd, ws);
                6'h0B: key[127:96] <= merge(key[127:96], wd, ws);
                6'h11: qt_ptr <= wd[6:0];
                6'h12: begin qt_we <= 1'b1; qt_data <= wd[16:0]; qt_addr <= qt_ptr; qt_ptr <= qt_ptr + 7'd1; end
                default: ;                    // read-only / unused: ignored, still OKAY
                endcase
            end
        end
    end

    // read
    assign s_axil_arready = !s_axil_rvalid;
    always @(posedge clk) begin
        if (rst) s_axil_rvalid <= 1'b0;
        else begin
            if (s_axil_rvalid && s_axil_rready) s_axil_rvalid <= 1'b0;
            if (s_axil_arvalid && s_axil_arready) begin
                s_axil_rvalid <= 1'b1;
                case (s_axil_araddr[7:2])
                6'h00: s_axil_rdata <= {28'd0, mode, 1'b0};
                6'h01: s_axil_rdata <= {29'd0, tag_valid, busy, done};
                6'h02: s_axil_rdata <= VERSION;
                6'h04: s_axil_rdata <= {20'd0, width};
                6'h05: s_axil_rdata <= {20'd0, height};
                6'h06: s_axil_rdata <= frame_ctr;
                6'h07: s_axil_rdata <= session_id;
                6'h0C: s_axil_rdata <= out_bytes;
                6'h0D: s_axil_rdata <= tag[31:0];
                6'h0E: s_axil_rdata <= tag[63:32];
                6'h0F: s_axil_rdata <= tag[95:64];
                6'h10: s_axil_rdata <= tag[127:96];
                6'h11: s_axil_rdata <= {25'd0, qt_ptr};
                default: s_axil_rdata <= 32'd0;   // KEYx and unused read as 0
                endcase
            end
        end
    end
endmodule
`default_nettype wire
