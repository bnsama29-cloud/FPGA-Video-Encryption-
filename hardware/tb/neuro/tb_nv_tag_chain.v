// Test wrapper (testbench only): nv_word_fifo -> nv_tag32 -> nv_out_mux, as in nv_top behind the Feistel.
`default_nettype none
module tb_nv_tag_chain #(parameter U = 1) (
    input  wire         clk,
    input  wire         rst,
    input  wire [127:0] key_tag,
    input  wire [127:0] key_aead,
    input  wire         w_en,
    input  wire [31:0]  w_word,
    input  wire         w_last,
    output wire [9:0]   count,
    output wire         m_tvalid,
    input  wire         m_tready,
    output wire [31:0]  m_tdata,
    output wire         m_tlast,
    output wire         overflow
);
    wire        f_valid, f_ready;
    wire [34:0] f_data;
    nv_word_fifo #(.DEPTH(512), .AW(9), .WIDTH(35)) u_fifo (
        .clk(clk), .rst(rst), .w_en(w_en), .w_data({2'b00, w_last, w_word}),
        .o_valid(f_valid), .o_ready(f_ready), .o_data(f_data), .count(count), .overflow(overflow));
    wire        b_valid, b_ready, b_last, t_valid, t_ack, busy, bw;
    wire [31:0] b_word;
    wire [127:0] t_data;
    nv_tag32 #(.U(U)) u_tag (
        .clk(clk), .rst(rst), .key_tag(key_tag), .key_aead(key_aead),
        .in_valid(f_valid), .in_ready(f_ready), .in_word(f_data[31:0]), .in_last(f_data[32]),
        .o_valid(b_valid), .o_ready(b_ready), .o_word(b_word), .o_last(b_last),
        .t_valid(t_valid), .t_data(t_data), .t_ack(t_ack), .busy(busy), .blk_wait(bw));
    nv_out_mux u_mux (
        .clk(clk), .rst(rst), .b_valid(b_valid), .b_ready(b_ready), .b_word(b_word), .b_last(b_last),
        .t_valid(t_valid), .t_data(t_data), .t_ack(t_ack),
        .m_tvalid(m_tvalid), .m_tready(m_tready), .m_tdata(m_tdata), .m_tlast(m_tlast));
endmodule
`default_nettype wire
