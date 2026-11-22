// tb_nv_power.v -- replays experiments/neuro_power_vectors.py's script on nv_top for the SAIF power run (N2).
// Golden model: software/neuro/sender.py :: Encryptor (through neuro.vectors.run_model, expect.hex).
//
// Plain Verilog-2001 (Icarus 12 and Vivado XSim). Reads script.hex and expect.hex from the current folder:
//   1 a d     AXI-Lite write of d to address a
//   2 n w..   stream n words with s_axis_tvalid held high (the input runs at the rate nv_top accepts)
//   3         wait until every streamed word was accepted
//   4 n       wait n clocks
//   0         end: wait for every expected output word (m_axis_tready = 1), then report
// Prints "RESULT nv_power mismatches=<m> words=<n> events=<e> cycles=<c>"; cycles count from the first streamed
// word to the last output word (the interval whose switching activity the SAIF records). The parameters are those
// of the routed build sim_build/vivado_neuro_nv_top_u2 (1280 x 720, U = 2, PAD = 1, defaults otherwise), so the
// SAIF names match its netlist.
`timescale 1ns/1ps
`default_nettype none
module tb_nv_power;
    localparam SCRIPT_MAX = 1 << 20, EXPECT_MAX = 1 << 20;
    reg clk = 1'b0;
    reg rst = 1'b1;
    always #5 clk = ~clk;                          // 100 MHz, the clock of every N2 build

    reg  [31:0] script [0:SCRIPT_MAX-1];
    reg  [32:0] expect [0:EXPECT_MAX-1];
    integer n_expect;

    reg         s_valid = 1'b0;
    reg  [31:0] s_data = 32'd0;
    wire        s_ready;
    wire        m_valid, m_last;
    wire [31:0] m_data;
    reg  [7:0]  awaddr = 8'd0;
    reg         awvalid = 1'b0, wvalid = 1'b0;
    reg  [31:0] wdata = 32'd0;
    wire        awready, wready, bvalid, arready, rvalid;
    wire [1:0]  bresp, rresp;
    wire [31:0] rdata;
    wire        fifo_overflow;

    nv_top #(.MAXW(1280), .MAXH(720), .U(2), .PAD(1)) dut (
        .clk(clk), .rst(rst),
        .s_axis_tvalid(s_valid), .s_axis_tready(s_ready), .s_axis_tdata(s_data),
        .m_axis_tvalid(m_valid), .m_axis_tready(1'b1), .m_axis_tdata(m_data), .m_axis_tlast(m_last),
        .s_axil_awaddr(awaddr), .s_axil_awprot(3'd0), .s_axil_awvalid(awvalid), .s_axil_awready(awready),
        .s_axil_wdata(wdata), .s_axil_wstrb(4'hF), .s_axil_wvalid(wvalid), .s_axil_wready(wready),
        .s_axil_bresp(bresp), .s_axil_bvalid(bvalid), .s_axil_bready(1'b1),
        .s_axil_araddr(8'd0), .s_axil_arprot(3'd0), .s_axil_arvalid(1'b0), .s_axil_arready(arready),
        .s_axil_rdata(rdata), .s_axil_rresp(rresp), .s_axil_rvalid(rvalid), .s_axil_rready(1'b1),
        .fifo_overflow(fifo_overflow));

    // output checker: every word against expect.hex, first mismatch printed
    integer n_out = 0, mismatches = 0;
    always @(posedge clk) begin
        if (!rst && m_valid) begin
            if (n_out >= n_expect || {m_last, m_data} !== expect[n_out]) begin
                if (mismatches == 0)
                    $display("first mismatch at output word %0d: got %08x last=%0d, expected %09x",
                             n_out, m_data, m_last, (n_out < n_expect) ? expect[n_out] : 33'h0);
                mismatches = mismatches + 1;
            end
            n_out = n_out + 1;
        end
    end

    // cycle counter: first streamed word to last output word
    reg counting = 1'b0;
    integer cycles = 0;
    always @(posedge clk) if (counting) cycles = cycles + 1;

    integer pc, k, n, events, accepted, pushed;

    task axil_write(input [7:0] a, input [31:0] d);
        begin
            @(negedge clk);
            awaddr = a; wdata = d; awvalid = 1'b1; wvalid = 1'b1;
            while (awvalid || wvalid) begin
                @(posedge clk);
                if (awready) awvalid = 1'b0;   // sampled at the edge: hold until accepted
                if (wready)  wvalid  = 1'b0;
                @(negedge clk);
            end
            while (!bvalid) @(negedge clk);
        end
    endtask

    initial begin
        for (k = 0; k < EXPECT_MAX; k = k + 1) expect[k] = 33'h1_FFFF_FFFF;
        $readmemh("script.hex", script);
        $readmemh("expect.hex", expect);
        n_expect = 0;
        while (n_expect < EXPECT_MAX && expect[n_expect] !== 33'h1_FFFF_FFFF) n_expect = n_expect + 1;
        events = 0; accepted = 0; pushed = 0;
        repeat (10) @(posedge clk);
        rst = 1'b0;
        repeat (5) @(posedge clk);
        pc = 0;
        while (script[pc] != 32'd0) begin
            case (script[pc])
                32'd1: begin axil_write(script[pc + 1][7:0], script[pc + 2]); pc = pc + 3; end
                32'd2: begin
                    n = script[pc + 1];
                    counting = 1'b1;
                    for (k = 0; k < n; k = k + 1) begin
                        @(negedge clk);
                        s_valid = 1'b1; s_data = script[pc + 2 + k];
                        if (s_data[31:28] == 4'h0 || s_data[31:28] == 4'h1) events = events + 1;   // CD_OFF / CD_ON
                        @(posedge clk);
                        while (!s_ready) @(posedge clk);
                        accepted = accepted + 1;
                    end
                    @(negedge clk);
                    s_valid = 1'b0;
                    pushed = pushed + n;
                    pc = pc + 2 + n;
                end
                32'd3: begin while (accepted < pushed) @(posedge clk); pc = pc + 1; end
                32'd4: begin repeat (script[pc + 1]) @(posedge clk); pc = pc + 2; end
                default: begin $display("bad script command %0d at %0d", script[pc], pc); $finish; end
            endcase
        end
        k = 0;
        while (n_out < n_expect && k < 2000000) begin @(posedge clk); k = k + 1; end
        counting = 1'b0;
        repeat (20) @(posedge clk);
        if (n_out != n_expect) mismatches = mismatches + 1;
        if (fifo_overflow) mismatches = mismatches + 1;
        $display("RESULT nv_power mismatches=%0d words=%0d events=%0d cycles=%0d", mismatches, n_out, events, cycles);
        if (mismatches == 0) $display("XSIM RESULT: PASS"); else $display("XSIM RESULT: FAIL");
        $finish;
    end
endmodule
`default_nettype wire
