// nv_table_gen: fills the 8 round tables of one packet from Ascon keystream K_perm (DESIGN §4.3.2, §6.2).
// Golden model: software/neuro/feistel.py :: make_tables()   (fill order: neuro/hw.py :: table_fill_entries())
//
// For j = 0..7 (T_0 first), M = W and n = H for even j, M = H and n = W for odd j; for i = 0..n-1:
//     r16 = next 16 keystream bits (LSB = first bit; taken as 8 + 8 because keystream_gen gives <= 12 per take)
//     T_j[i] = (r16 * M) >> 16
// keystream_gen restarts at `start` with nonce (sid, ctr, 0). One write per entry on the table port.
`default_nettype none
module nv_table_gen (
    input  wire         clk,
    input  wire         rst,
    input  wire         start,        // pulse: begin a fill
    input  wire [127:0] key,          // K_perm
    input  wire [127:0] nonce,        // make_nonce(sid, ctr, 0)
    input  wire [10:0]  W,
    input  wire [10:0]  H,
    input  wire         bank,         // bank to fill
    output reg          busy,
    output reg          done,         // one-clock pulse when the last entry is written
    output reg          tw_en,
    output reg          tw_bank,
    output reg  [2:0]   tw_tab,
    output reg  [10:0]  tw_addr,
    output reg  [10:0]  tw_data
);
    wire [15:0] ks_bits;
    wire [4:0]  ks_avail;
    wire        ks_take;
    keystream_gen ksg (
        .clk(clk), .rst(rst), .start(start), .key(key), .nonce(nonce),
        .ks_bits(ks_bits), .ks_avail(ks_avail), .ks_take(ks_take), .ks_n(5'd8));

    reg  [10:0] w_l, h_l;
    reg  [3:0]  j;          // table 0..7, 8 = finished
    reg  [10:0] i;
    reg         hi;         // 0: next take is the low byte
    reg  [7:0]  lo;
    reg         bk;

    wire        even = !j[0];
    wire [10:0] M    = even ? w_l : h_l;
    wire [10:0] n    = even ? h_l : w_l;
    assign ks_take = busy && (j < 4'd8) && (ks_avail >= 5'd8);

    wire [15:0] r16  = {ks_bits[7:0], lo};
    wire [26:0] prod = r16 * M;                  // 16 x 11

    always @(posedge clk) begin
        tw_en <= 1'b0;
        done  <= 1'b0;
        if (rst) begin
            busy <= 1'b0;
            j    <= 4'd8;
        end else if (start) begin
            busy <= 1'b1;
            w_l  <= W;
            h_l  <= H;
            bk   <= bank;
            j    <= 4'd0;
            i    <= 11'd0;
            hi   <= 1'b0;
        end else if (ks_take) begin
            if (!hi) begin
                lo <= ks_bits[7:0];
                hi <= 1'b1;
            end else begin
                hi      <= 1'b0;
                tw_en   <= 1'b1;
                tw_bank <= bk;
                tw_tab  <= j[2:0];
                tw_addr <= i;
                tw_data <= prod[26:16];
                if (i == n - 11'd1) begin
                    i <= 11'd0;
                    j <= j + 4'd1;
                    if (j == 4'd7) begin
                        busy <= 1'b0;
                        done <= 1'b1;
                    end
                end else begin
                    i <= i + 11'd1;
                end
            end
        end
    end
endmodule
`default_nettype wire
