// tb_secure_jpeg_top.v -- self-checking testbench for Vivado XSim (also runs in Icarus).
//
// Plays a command file generated from the golden model (vivado/gen_xsim_vectors.py):
//   W <addr> <data>      AXI4-Lite write (hex)
//   R <addr> <expect>    AXI4-Lite read, compare (hex)
//   S <npix>             stream the next <npix> pixels (decimal) while collecting the
//                        scan bytes from m_axis (random backpressure), wait for DONE
//   C <nbytes>           compare the collected scan with the next <nbytes> expected bytes
//                        and check OUT_BYTES
//   G <t0> <t1> <t2> <t3>  compare TAG0..TAG3 (hex words)
//   F <frame index>      label for the log
//   E                    end of file
// Files (in the directory given by +VEC_DIR=<dir>, default the simulator's
// working directory; see vivado/run_xsim.sh and vivado/xsim_project.tcl):
//   commands.txt, pixels.hex (32-bit {pad,B,G,R}), expect_scan.hex (bytes)
// Writes out_scan.hex (every scan byte the DUT produced) and out_tags.txt so
// vivado/check_xsim_output.py can rebuild the JPEGs and run the real receiver.
// Prints "XSIM RESULT: PASS" or "XSIM RESULT: FAIL (<n> errors)" at the end.
`timescale 1ns / 1ps
`default_nettype none
module tb_secure_jpeg_top;
    parameter MAXPIX   = 640 * 480 * 4;   // pixels over all frames
    parameter MAXBYTES = 1 << 22;         // expected scan bytes over all frames
    parameter STALL_PCT = 25;             // % of cycles with m_axis_tready low
    parameter SEED = 12345;

    reg clk = 1'b0;
    reg rst = 1'b1;
    always #5 clk = ~clk;                 // 100 MHz

    // ------------------------------------------------------------- DUT ports
    reg  [7:0]  awaddr = 0, araddr = 0;
    reg         awvalid = 0, wvalid = 0, arvalid = 0;
    reg  [31:0] wdata = 0;
    reg  [3:0]  wstrb = 4'hF;
    wire        awready, wready, bvalid, arready, rvalid;
    wire [1:0]  bresp, rresp;
    wire [31:0] rdata;
    reg  [31:0] s_tdata = 0;
    reg         s_tvalid = 0;
    wire        s_tready;
    wire [31:0] m_tdata;
    wire [3:0]  m_tkeep;
    wire        m_tvalid, m_tlast, irq_done;
    reg         m_tready = 0;

    secure_jpeg_top dut (
        .clk(clk), .rst(rst),
        .s_axil_awaddr(awaddr), .s_axil_awprot(3'd0), .s_axil_awvalid(awvalid), .s_axil_awready(awready),
        .s_axil_wdata(wdata), .s_axil_wstrb(wstrb), .s_axil_wvalid(wvalid), .s_axil_wready(wready),
        .s_axil_bresp(bresp), .s_axil_bvalid(bvalid), .s_axil_bready(1'b1),
        .s_axil_araddr(araddr), .s_axil_arprot(3'd0), .s_axil_arvalid(arvalid), .s_axil_arready(arready),
        .s_axil_rdata(rdata), .s_axil_rresp(rresp), .s_axil_rvalid(rvalid), .s_axil_rready(1'b1),
        .s_axis_tdata(s_tdata), .s_axis_tvalid(s_tvalid), .s_axis_tready(s_tready), .s_axis_tlast(1'b0),
        .m_axis_tdata(m_tdata), .m_axis_tkeep(m_tkeep), .m_axis_tvalid(m_tvalid),
        .m_axis_tready(m_tready), .m_axis_tlast(m_tlast), .irq_done(irq_done));

    // ------------------------------------------------------------- memories
    reg [31:0] pix  [0:MAXPIX-1];
    reg [7:0]  expb [0:MAXBYTES-1];
    reg [7:0]  got  [0:MAXBYTES-1];
    integer pix_ptr = 0, exp_ptr = 0, got_n = 0, frame_start = 0;
    integer errors = 0, frames = 0, seed = SEED;
    integer fd, fo, ft, r;

    // All TB signals change just after a falling edge and are sampled 1 ns
    // later, so a handshake seen then happens at the next rising edge.
    task axil_write(input [7:0] a, input [31:0] d);
        begin
            @(negedge clk); awaddr = a; wdata = d; awvalid = 1; wvalid = 1;
            #1;
            while (!awready) begin @(negedge clk); #1; end
            @(posedge clk); #1 awvalid = 0; wvalid = 0;
        end
    endtask

    task axil_read(input [7:0] a, output [31:0] d);
        begin
            @(negedge clk); araddr = a; arvalid = 1;
            #1;
            while (!arready) begin @(negedge clk); #1; end
            @(posedge clk); #1 arvalid = 0;
            while (!rvalid) begin @(negedge clk); #1; end
            d = rdata;
            @(posedge clk); #1;
        end
    endtask

    // pixel source (no stalls on the input; the DUT applies its own backpressure)
    task send_pixels(input integer n);
        integer sent;
        reg hs;
        begin
            sent = 0;
            @(negedge clk); s_tdata = pix[pix_ptr]; s_tvalid = (n > 0); #1;
            hs = s_tvalid && s_tready;
            while (sent < n) begin
                @(negedge clk);
                if (hs) begin
                    sent = sent + 1;
                    if (sent < n) s_tdata = pix[pix_ptr + sent];
                    else s_tvalid = 0;
                end
                #1 hs = s_tvalid && s_tready;
            end
            pix_ptr = pix_ptr + n;
        end
    endtask

    // scan sink with random backpressure, until TLAST
    task collect_scan;
        reg done_l;
        integer k;
        begin
            done_l = 0;
            while (!done_l) begin
                @(negedge clk);
                m_tready = (($random(seed) % 100 + 100) % 100) >= STALL_PCT;
                #1;
                if (m_tvalid && m_tready) begin
                    for (k = 0; k < 4; k = k + 1)
                        if (m_tkeep[k]) begin
                            got[got_n] = m_tdata[8*k +: 8];
                            got_n = got_n + 1;
                        end
                    if (m_tlast) done_l = 1;
                end
            end
            @(posedge clk); #1 m_tready = 0;
        end
    endtask

    reg [8*4:1]   op;
    reg [8*512:1] vdir, fname;
    reg [31:0]  a1, a2, a3, a4, rv;
    integer     n, i, t0, label;
    reg         first_bad;

    initial begin
        if (!$value$plusargs("VEC_DIR=%s", vdir)) vdir = ".";
        $sformat(fname, "%0s/pixels.hex", vdir);      $readmemh(fname, pix);
        $sformat(fname, "%0s/expect_scan.hex", vdir); $readmemh(fname, expb);
        $sformat(fname, "%0s/commands.txt", vdir);    fd = $fopen(fname, "r");
        $sformat(fname, "%0s/out_scan.hex", vdir);    fo = $fopen(fname, "w");
        $sformat(fname, "%0s/out_tags.txt", vdir);    ft = $fopen(fname, "w");
        if (fd == 0) begin
            $display("ERROR: %0s/commands.txt not found (run vivado/gen_xsim_vectors.py, pass +VEC_DIR=...)", vdir);
            $finish;
        end
        repeat (10) @(posedge clk);
        rst = 0;
        repeat (5) @(posedge clk);
        label = -1;
        op = "";
        while (op != "E") begin
            r = $fscanf(fd, "%s", op);
            if (r != 1) op = "E";
            if (op == "W") begin
                r = $fscanf(fd, "%h %h", a1, a2);
                axil_write(a1[7:0], a2);
            end else if (op == "R") begin
                r = $fscanf(fd, "%h %h", a1, a2);
                axil_read(a1[7:0], rv);
                if (rv !== a2) begin
                    errors = errors + 1;
                    $display("ERROR frame %0d: reg 0x%02h read 0x%08h, expected 0x%08h", label, a1[7:0], rv, a2);
                end
            end else if (op == "F") begin
                r = $fscanf(fd, "%d", label);
            end else if (op == "S") begin
                r = $fscanf(fd, "%d", n);
                frame_start = got_n;
                t0 = $time;
                fork
                    send_pixels(n);
                    collect_scan;
                join
                rv = 0;
                while (!rv[0]) axil_read(8'h04, rv);           // STATUS.DONE
                $display("frame %0d: %0d pixels -> %0d scan bytes in %0d cycles (%0d.%02d cycles/pixel)",
                         label, n, got_n - frame_start, ($time - t0) / 10,
                         ($time - t0) / 10 / n, (($time - t0) / 10 * 100 / n) % 100);
                frames = frames + 1;
            end else if (op == "C") begin
                r = $fscanf(fd, "%d", n);
                if (got_n - frame_start != n) begin
                    errors = errors + 1;
                    $display("ERROR frame %0d: DUT produced %0d scan bytes, model %0d",
                             label, got_n - frame_start, n);
                end
                first_bad = 1;
                for (i = 0; i < n && i < got_n - frame_start; i = i + 1)
                    if (got[frame_start + i] !== expb[exp_ptr + i] && first_bad) begin
                        first_bad = 0;
                        errors = errors + 1;
                        $display("ERROR frame %0d: first scan mismatch at byte %0d: got 0x%02h expected 0x%02h",
                                 label, i, got[frame_start + i], expb[exp_ptr + i]);
                    end
                exp_ptr = exp_ptr + n;
                axil_read(8'h30, rv);                          // OUT_BYTES
                if (rv != got_n - frame_start) begin
                    errors = errors + 1;
                    $display("ERROR frame %0d: OUT_BYTES=%0d but %0d bytes received", label, rv, got_n - frame_start);
                end
                for (i = frame_start; i < got_n; i = i + 1) $fdisplay(fo, "%02h", got[i]);
            end else if (op == "G") begin
                r = $fscanf(fd, "%h %h %h %h", a1, a2, a3, a4);
                $fwrite(ft, "%0d", label);
                for (i = 0; i < 4; i = i + 1) begin
                    axil_read(8'h34 + 4 * i, rv);
                    $fwrite(ft, " %08h", rv);
                    if (rv !== (i == 0 ? a1 : i == 1 ? a2 : i == 2 ? a3 : a4)) begin
                        errors = errors + 1;
                        $display("ERROR frame %0d: TAG%0d = 0x%08h, expected 0x%08h", label, i, rv,
                                 (i == 0 ? a1 : i == 1 ? a2 : i == 2 ? a3 : a4));
                    end
                end
                $fwrite(ft, "\n");
            end
        end
        $fclose(fd); $fclose(fo); $fclose(ft);
        if (errors == 0) $display("XSIM RESULT: PASS (%0d frames bit-exact with the golden model)", frames);
        else             $display("XSIM RESULT: FAIL (%0d errors)", errors);
        $finish;
    end

    // watchdog: 200 ms of simulated time
    initial begin
        #200_000_000;
        $display("XSIM RESULT: FAIL (timeout)");
        $finish;
    end
endmodule
`default_nettype wire
