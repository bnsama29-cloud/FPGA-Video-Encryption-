// nv_feistel: V2/V3 position permutation, mixed-radix table Feistel on Z_W x Z_H, r = 8 (DESIGN §4.3, §6.2).
// Golden model: software/neuro/feistel.py :: permute()  (stage view software/neuro/hw.py :: feistel_round())
//
// Round j (2 clk): clock A presents the table address (y for even j, x for odd j) to bank `bank` of table j;
// clock B adds the table value to the other coordinate with one compare-and-subtract (both operands < M).
//     j even: x = (x + T_j[y]) mod W        j odd: y = (y + T_j[x]) mod H
// Fixed latency LAT = 16 clk, no stage enable, no ready: the caller admits a word only when the FIFO behind
// has credit (DESIGN §6.1). Words with perm = 0 (non-CD words, dummies, V0/V1) ride through unchanged, so word
// order is kept. Two banks x 8 tables (double buffer: the fill of packet k+1 writes the free bank).
`default_nettype none
module nv_feistel #(
    parameter MAXW = 1280,
    parameter MAXH = 720
) (
    input  wire        clk,
    input  wire        rst,
    input  wire [10:0] W,
    input  wire [10:0] H,
    // input word (one per clock at most)
    input  wire        in_valid,
    input  wire [31:0] in_word,
    input  wire        in_perm,     // permute (x, y) of this word
    input  wire        in_bank,     // table bank of its packet
    input  wire [1:0]  in_kind,
    input  wire        in_last,
    // output, exactly LAT clk later
    output wire        out_valid,
    output wire [31:0] out_word,
    output wire [1:0]  out_kind,
    output wire        out_last,
    // table write port (from nv_table_gen)
    input  wire        tw_en,
    input  wire        tw_bank,
    input  wire [2:0]  tw_tab,
    input  wire [10:0] tw_addr,
    input  wire [10:0] tw_data
);
    localparam MW = 16;   // meta: [15] valid, [14] perm, [13] bank, [12:11] kind, [10] last, [9:0] word[31:22]

    wire [MW-1:0] a_m [0:8];
    wire [10:0]   a_x [0:8];
    wire [10:0]   a_y [0:8];

    assign a_m[0] = {in_valid, in_perm, in_bank, in_kind, in_last, in_word[31:22]};
    assign a_x[0] = in_word[21:11];
    assign a_y[0] = in_word[10:0];

    genvar j;
    generate
        for (j = 0; j < 8; j = j + 1) begin : rnd
            localparam EVEN  = (j % 2) == 0;
            localparam DEPTH = EVEN ? MAXH : MAXW;     // even tables are indexed by y, odd by x
            wire [10:0] raddr = EVEN ? a_y[j] : a_x[j];
            wire [10:0] rd0, rd1;
            nv_sdp_ram #(.DEPTH(DEPTH), .AW(11), .WIDTH(11)) bank0 (
                .clk(clk), .we(tw_en && !tw_bank && tw_tab == j), .waddr(tw_addr), .wdata(tw_data),
                .raddr(raddr), .rdata(rd0));
            nv_sdp_ram #(.DEPTH(DEPTH), .AW(11), .WIDTH(11)) bank1 (
                .clk(clk), .we(tw_en && tw_bank && tw_tab == j), .waddr(tw_addr), .wdata(tw_data),
                .raddr(raddr), .rdata(rd1));

            // clock A: register the word next to the RAM read
            reg [MW-1:0] b_m;
            reg [10:0]   b_x, b_y;
            always @(posedge clk) begin
                if (rst) b_m <= {MW{1'b0}};
                else     b_m <= a_m[j];
                b_x <= a_x[j];
                b_y <= a_y[j];
            end

            // clock B: add and reduce
            wire [10:0] t   = b_m[13] ? rd1 : rd0;
            wire [10:0] M   = EVEN ? W : H;
            wire [10:0] c   = EVEN ? b_x : b_y;
            wire [11:0] s   = {1'b0, c} + {1'b0, t};
            wire [10:0] r   = (s >= {1'b0, M}) ? (s - {1'b0, M}) : s[10:0];
            reg  [MW-1:0] n_m;
            reg  [10:0]   n_x, n_y;
            always @(posedge clk) begin
                if (rst) n_m <= {MW{1'b0}};
                else     n_m <= b_m;
                n_x <= (b_m[14] &&  EVEN) ? r : b_x;
                n_y <= (b_m[14] && !EVEN) ? r : b_y;
            end
            assign a_m[j + 1] = n_m;
            assign a_x[j + 1] = n_x;
            assign a_y[j + 1] = n_y;
        end
    endgenerate

    assign out_valid = a_m[8][15];
    assign out_kind  = a_m[8][12:11];
    assign out_last  = a_m[8][10];
    assign out_word  = {a_m[8][9:0], a_x[8], a_y[8]};
endmodule
`default_nettype wire
