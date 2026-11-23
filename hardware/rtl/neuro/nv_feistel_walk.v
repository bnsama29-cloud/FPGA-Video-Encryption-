// nv_feistel_walk: ABLATION N2b ONLY, not part of the IP. Cycle walking on the binary domain 2^A x 2^B that
// contains W x H, A = clog2(W), B = clog2(H), with the same eight-round table Feistel as nv_feistel but plain
// binary additions (DESIGN §4.3.4, "pow2" domain).
// Golden model: software/neuro/feistel.py :: permute_walk(..., domain="pow2")  (tables: walk_tables)
//
// K passes are unrolled (K x 8 rounds, 2 clk per round, latency K x 16 clk). A pass leaves a word unchanged once
// it is in range ("first in domain"). A permuted word still out of range after K passes freezes the whole
// pipeline (in_ready = 0) while a side unit with its own table copy walks it on, 16 clk per pass; it then leaves
// in order and the pipeline resumes. The geometry is fixed at synthesis (parameters W, H): this module exists to
// measure area, Fmax and stall cost against nv_feistel, not to be deployed.
`default_nettype none
module nv_feistel_walk #(
    parameter W = 1280,
    parameter H = 720,
    parameter K = 4
) (
    input  wire        clk,
    input  wire        rst,
    input  wire        in_valid,
    output wire        in_ready,
    input  wire [31:0] in_word,
    input  wire        in_perm,
    input  wire        in_bank,
    output wire        out_valid,
    output wire [31:0] out_word,
    output wire        stall,       // pipeline frozen this clock (for the cycle count)
    input  wire        tw_en,
    input  wire        tw_bank,
    input  wire [2:0]  tw_tab,
    input  wire [10:0] tw_addr,
    input  wire [10:0] tw_data
);
    localparam A = (W <= 1) ? 1 : $clog2(W);
    localparam B = (H <= 1) ? 1 : $clog2(H);
    localparam NS = 8 * K;                      // round stages
    localparam MW = 14;                         // meta: [13] valid, [12] perm, [11] bank, [10] done, [9:0] hi

    wire adv;

    wire [MW-1:0] a_m [0:NS];
    wire [10:0]   a_x [0:NS];
    wire [10:0]   a_y [0:NS];
    // non-permuted words are "done" on entry
    assign a_m[0] = {in_valid, in_perm, in_bank, !in_perm, in_word[31:22]};
    assign a_x[0] = in_word[21:11];
    assign a_y[0] = in_word[10:0];

    genvar s;
    generate
        for (s = 0; s < NS; s = s + 1) begin : st
            localparam J    = s % 8;
            localparam EVEN = (J % 2) == 0;
            localparam DEPTH = EVEN ? (1 << B) : (1 << A);
            reg  [10:0] b_x, b_y;
            // while frozen, re-read the address of the word held in stage b, so rdata stays paired with it
            wire [10:0] raddr = adv ? (EVEN ? a_y[s] : a_x[s]) : (EVEN ? b_y : b_x);
            wire [10:0] rd0, rd1;
            nv_sdp_ram #(.DEPTH(DEPTH), .AW(11), .WIDTH(11)) bank0 (
                .clk(clk), .we(tw_en && !tw_bank && tw_tab == J), .waddr(tw_addr), .wdata(tw_data),
                .raddr(raddr), .rdata(rd0));
            nv_sdp_ram #(.DEPTH(DEPTH), .AW(11), .WIDTH(11)) bank1 (
                .clk(clk), .we(tw_en && tw_bank && tw_tab == J), .waddr(tw_addr), .wdata(tw_data),
                .raddr(raddr), .rdata(rd1));

            reg [MW-1:0] b_m;
            always @(posedge clk) begin
                if (rst)      b_m <= {MW{1'b0}};
                else if (adv) b_m <= a_m[s];
                if (adv) begin
                    b_x <= a_x[s];
                    b_y <= a_y[s];
                end
            end

            wire [10:0] t   = b_m[11] ? rd1 : rd0;
            wire        go  = b_m[12] && !b_m[10];             // permuted and not yet in range
            wire [10:0] nx  = EVEN ? ((b_x + t) & ((11'd1 << A) - 11'd1)) : b_x;
            wire [10:0] ny  = EVEN ? b_y : ((b_y + t) & ((11'd1 << B) - 11'd1));
            wire        ind = (J == 7) && go && (nx < W) && (ny < H);
            reg [MW-1:0] n_m;
            reg [10:0]   n_x, n_y;
            always @(posedge clk) begin
                if (rst)      n_m <= {MW{1'b0}};
                else if (adv) n_m <= {b_m[13:11], b_m[10] | ind, b_m[9:0]};
                if (adv) begin
                    n_x <= go ? nx : b_x;
                    n_y <= go ? ny : b_y;
                end
            end
            assign a_m[s + 1] = n_m;
            assign a_x[s + 1] = n_x;
            assign a_y[s + 1] = n_y;
        end
    endgenerate

    // ---------------------------------------------------------------- side unit: walks one word on, in order
    wire        f_valid = a_m[NS][13];
    wire        f_done  = a_m[NS][10];
    reg         s_busy, s_ready, s_ph, s_bank;
    reg  [2:0]  s_j;
    reg  [10:0] s_x, s_y;
    reg  [9:0]  s_hi;
    wire        s_even = !s_j[0];
    wire [10:0] s_raddr = s_even ? s_y : s_x;
    wire [10:0] s_rd [0:7];
    wire [10:0] s_rd0 [0:7];
    wire [10:0] s_rd1 [0:7];

    genvar q;
    generate
        for (q = 0; q < 8; q = q + 1) begin : sidetab
            localparam EVQ = (q % 2) == 0;
            localparam DQ  = EVQ ? (1 << B) : (1 << A);
            nv_sdp_ram #(.DEPTH(DQ), .AW(11), .WIDTH(11)) sb0 (
                .clk(clk), .we(tw_en && !tw_bank && tw_tab == q), .waddr(tw_addr), .wdata(tw_data),
                .raddr(s_raddr), .rdata(s_rd0[q]));
            nv_sdp_ram #(.DEPTH(DQ), .AW(11), .WIDTH(11)) sb1 (
                .clk(clk), .we(tw_en && tw_bank && tw_tab == q), .waddr(tw_addr), .wdata(tw_data),
                .raddr(s_raddr), .rdata(s_rd1[q]));
            assign s_rd[q] = s_bank ? s_rd1[q] : s_rd0[q];
        end
    endgenerate

    wire        trig = f_valid && !f_done && !s_busy && !s_ready;
    wire [10:0] s_t  = s_rd[s_j];
    wire [10:0] s_nx = s_even ? ((s_x + s_t) & ((11'd1 << A) - 11'd1)) : s_x;
    wire [10:0] s_ny = s_even ? s_y : ((s_y + s_t) & ((11'd1 << B) - 11'd1));

    always @(posedge clk) begin
        if (rst) begin
            s_busy <= 1'b0; s_ready <= 1'b0; s_ph <= 1'b0; s_j <= 3'd0;
        end else if (trig) begin
            s_busy <= 1'b1; s_ph <= 1'b0; s_j <= 3'd0;
            s_x <= a_x[NS]; s_y <= a_y[NS]; s_hi <= a_m[NS][9:0]; s_bank <= a_m[NS][11];
        end else if (s_busy) begin
            if (!s_ph) s_ph <= 1'b1;                       // table address presented, data next clock
            else begin
                s_ph <= 1'b0;
                s_x  <= s_nx;
                s_y  <= s_ny;
                if (s_j == 3'd7) begin
                    if (s_nx < W && s_ny < H) begin s_busy <= 1'b0; s_ready <= 1'b1; end
                    s_j <= 3'd0;
                end else s_j <= s_j + 3'd1;
            end
        end else if (s_ready) s_ready <= 1'b0;
    end

    // the stalled word leaves from the side unit in the clock the pipeline resumes
    assign adv       = !(f_valid && !f_done) || s_ready;
    assign in_ready  = adv;
    assign stall     = !adv;
    assign out_valid = s_ready || (f_valid && f_done);
    assign out_word  = s_ready ? {s_hi, s_x, s_y} : {a_m[NS][9:0], a_x[NS], a_y[NS]};
endmodule
`default_nettype wire
