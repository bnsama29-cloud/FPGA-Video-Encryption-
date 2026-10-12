// zigzag_rle.v -- zig-zag reorder + DC differencing + AC run-length symbols.
//
// In : 64 quantised coefficients per block, natural (row-major) order.
// Out: one symbol per handshake (the symbol stream of the interface contract):
//   o_is_dc, o_run[3:0], o_size[3:0], o_amp[10:0] (JPEG-coded amplitude bits),
//   o_eob (end of block), o_comp[1:0], o_flast (last symbol of the frame).
//   ZRL (16 zeros) = run 15, size 0, eob 0.
// DC predictors (one per component) reset on `start`.
// Ping-pong block buffers: scanning one block while the next is written.
// Golden model: model/jpeg.py :: run_length(), category(), amp_bits()
`default_nettype none
module zigzag_rle (
    input  wire               clk,
    input  wire               rst,
    input  wire               start,
    input  wire               in_valid,
    output wire               in_ready,
    input  wire signed [15:0] in_data,
    input  wire [1:0]         in_comp,
    input  wire               in_blast,
    input  wire               in_flast,
    output reg                o_valid,
    input  wire               o_ready,
    output reg                o_is_dc,
    output reg  [3:0]         o_run,
    output reg  [3:0]         o_size,
    output reg  [10:0]        o_amp,
    output reg                o_eob,
    output reg  [1:0]         o_comp,
    output reg                o_flast
);
    `include "zigzag.vh"

    reg signed [11:0] cb0 [0:63];
    reg signed [11:0] cb1 [0:63];
    reg [1:0]  full, bcomp0, bcomp1, bflast;
    reg        wsel, rsel;
    reg [5:0]  wptr;

    assign in_ready = !full[wsel];
    wire wr = in_valid && in_ready;

    // ------------------------------------------------------------- scanner
    reg [5:0] k;                     // zig-zag position
    reg [5:0] run;                   // pending zero run (0..62)
    reg signed [11:0] pred [0:2];

    wire [1:0]  comp  = rsel ? bcomp1 : bcomp0;
    wire        flast = bflast[rsel];
    wire [5:0]  nat   = zz_nat(k);
    wire signed [11:0] coef = rsel ? cb1[nat] : cb0[nat];
    wire signed [12:0] diff = coef - pred[comp];      // DC difference

    // value to code this step: DC difference at k == 0, else the AC coefficient
    wire signed [12:0] val  = (k == 6'd0) ? diff : {coef[11], coef};
    wire [12:0] mag  = val[12] ? -val : val;
    reg  [3:0]  cat;
    integer b;
    always @* begin
        cat = 4'd0;
        for (b = 0; b < 12; b = b + 1)
            if (mag[b]) cat = b[3:0] + 4'd1;
    end
    wire [12:0] vm1  = val - 13'sd1;
    wire [10:0] amp  = (val[12] ? vm1[10:0] : val[10:0]) & ((11'd1 << cat) - 11'd1);

    wire step = full[rsel] && (!o_valid || o_ready);

    always @(posedge clk) begin
        if (wr) begin
            if (wsel) cb1[wptr] <= in_data[11:0]; else cb0[wptr] <= in_data[11:0];
        end
        if (rst || start) begin
            pred[0] <= 12'sd0; pred[1] <= 12'sd0; pred[2] <= 12'sd0;
        end
        if (rst || start) begin
            full <= 2'b00; wsel <= 1'b0; rsel <= 1'b0; wptr <= 6'd0;
            k <= 6'd0; run <= 6'd0; o_valid <= 1'b0;
        end else begin
            if (wr) begin
                wptr <= wptr + 6'd1;
                if (wptr == 6'd63) begin
                    wsel <= ~wsel;
                    if (wsel) begin bcomp1 <= in_comp; bflast[1] <= in_flast; end
                    else      begin bcomp0 <= in_comp; bflast[0] <= in_flast; end
                end
            end
            if (o_valid && o_ready) o_valid <= 1'b0;
            if (step) begin
                o_comp  <= comp;
                o_is_dc <= 1'b0;
                o_eob   <= 1'b0;
                o_flast <= 1'b0;
                if (k == 6'd0) begin                        // DC symbol
                    pred[comp] <= coef;
                    o_is_dc <= 1'b1; o_run <= 4'd0; o_size <= cat; o_amp <= amp;
                    o_valid <= 1'b1;
                    k <= 6'd1; run <= 6'd0;
                end else if (coef == 12'sd0) begin
                    if (k == 6'd63) begin                   // trailing zeros: EOB
                        o_eob <= 1'b1; o_run <= 4'd0; o_size <= 4'd0; o_amp <= 11'd0;
                        o_flast <= flast; o_valid <= 1'b1;
                        k <= 6'd0; run <= 6'd0;
                        rsel <= ~rsel;
                        full[rsel] <= 1'b0;
                    end else begin
                        run <= run + 6'd1; k <= k + 6'd1;   // no output this step
                    end
                end else if (run >= 6'd16) begin            // emit ZRL, stay at k
                    o_run <= 4'd15; o_size <= 4'd0; o_amp <= 11'd0;
                    o_valid <= 1'b1;
                    run <= run - 6'd16;
                end else begin                              // AC symbol
                    o_run <= run[3:0]; o_size <= cat; o_amp <= amp;
                    o_valid <= 1'b1;
                    run <= 6'd0;
                    if (k == 6'd63) begin                   // last coefficient non-zero
                        o_flast <= flast;
                        k <= 6'd0;
                        rsel <= ~rsel;
                        full[rsel] <= 1'b0;
                    end else
                        k <= k + 6'd1;
                end
            end
            if (wr && wptr == 6'd63) full[wsel] <= 1'b1;
        end
    end
endmodule
`default_nettype wire
