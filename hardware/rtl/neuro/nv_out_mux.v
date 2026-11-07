// nv_out_mux: forwards the body words of each packet and appends its 4 tag words, tlast on the last (DESIGN §6.2).
// Golden model: software/neuro/packet.py :: Packet.to_words()   (stage view software/neuro/hw.py :: out_words())
//
// Tag word j = tag bytes 4j..4j+3 (Ascon byte order, byte 4j in [7:0]), i.e. t_data[32j +: 32].
// The body path is combinational (b_ready = m_tready); nv_tag32's output register isolates the timing.
`default_nettype none
module nv_out_mux (
    input  wire         clk,
    input  wire         rst,
    input  wire         b_valid,
    output wire         b_ready,
    input  wire [31:0]  b_word,
    input  wire         b_last,
    input  wire         t_valid,
    input  wire [127:0] t_data,
    output wire         t_ack,
    output wire         m_tvalid,
    input  wire         m_tready,
    output wire [31:0]  m_tdata,
    output wire         m_tlast
);
    reg       in_tag;
    reg [1:0] ti;
    assign b_ready  = !in_tag && m_tready;
    assign m_tvalid = in_tag ? t_valid : b_valid;
    assign m_tdata  = in_tag ? t_data[32*ti +: 32] : b_word;
    assign m_tlast  = in_tag && (ti == 2'd3);
    assign t_ack    = in_tag && t_valid && m_tready && (ti == 2'd3);
    always @(posedge clk) begin
        if (rst) begin
            in_tag <= 1'b0;
            ti     <= 2'd0;
        end else if (!in_tag) begin
            if (b_valid && m_tready && b_last) begin
                in_tag <= 1'b1;
                ti     <= 2'd0;
            end
        end else if (t_valid && m_tready) begin
            ti <= ti + 2'd1;
            if (ti == 2'd3) in_tag <= 1'b0;
        end
    end
endmodule
`default_nettype wire
