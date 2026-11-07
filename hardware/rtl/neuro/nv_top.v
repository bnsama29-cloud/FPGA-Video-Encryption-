// nv_top: authenticated, format-preserving encryptor for EVT 2.0 event streams, contract n1 (DESIGN §6.1).
// Golden model: software/neuro/sender.py :: Encryptor.push()
//
//   AXI-S in -> nv_packetizer -> nv_trailer -> nv_xor (K_pol) -> skid_buf -> [credit gate] -> nv_feistel (LAT 16)
//            -> nv_word_fifo (512 x 35) -> nv_tag32 (K_tag / K_aead, U rounds/clk) -> nv_out_mux -> AXI-S out
//   nv_table_gen (K_perm) -> nv_feistel table banks;  AXI-Lite -> nv_axil_regs (shadow set, commit, counters)
// Every stage that can stall is in front of the Feistel. The credit gate (credits = FIFO depth, minus one when a
// word enters nv_feistel, plus one when nv_tag32 pops the FIFO) means no word that enters the fixed-latency
// section can find the FIFO full. Per-packet parameters (sid, ctr, level, ts_bits, PAD, geometry, t_start) travel
// in-band in the header; the keys are the active register set, which changes only with the pipeline drained.
// nv_xor restarts its keystream with nonce (sid, ctr, 0) after each header has passed it (header snooped here).
`default_nettype none
module nv_top #(
    parameter MAXW   = 1280,
    parameter MAXH   = 720,
    parameter U      = 2,
    parameter PAD    = 1,
    parameter MAX_CD = 131072,
    parameter BM_AW  = 12
) (
    input  wire         clk,
    input  wire         rst,
    input  wire         s_axis_tvalid,
    output wire         s_axis_tready,
    input  wire [31:0]  s_axis_tdata,
    output wire         m_axis_tvalid,
    input  wire         m_axis_tready,
    output wire [31:0]  m_axis_tdata,
    output wire         m_axis_tlast,
    input  wire [7:0]   s_axil_awaddr,
    input  wire [2:0]   s_axil_awprot,
    input  wire         s_axil_awvalid,
    output wire         s_axil_awready,
    input  wire [31:0]  s_axil_wdata,
    input  wire [3:0]   s_axil_wstrb,
    input  wire         s_axil_wvalid,
    output wire         s_axil_wready,
    output wire [1:0]   s_axil_bresp,
    output wire         s_axil_bvalid,
    input  wire         s_axil_bready,
    input  wire [7:0]   s_axil_araddr,
    input  wire [2:0]   s_axil_arprot,
    input  wire         s_axil_arvalid,
    output wire         s_axil_arready,
    output wire [31:0]  s_axil_rdata,
    output wire [1:0]   s_axil_rresp,
    output wire         s_axil_rvalid,
    input  wire         s_axil_rready,
    output wire         fifo_overflow       // sticky; must stay 0 (checked by the testbench)
);
    localparam [1:0] LOG2U = (U == 4) ? 2'd2 : (U == 2) ? 2'd1 : 2'd0;
    localparam [7:0] BUILD = {1'b0, (PAD != 0) ? 1'b1 : 1'b0, LOG2U, 4'd1};
    localparam FIFO_DEPTH = 512;

    // ---------------------------------------------------------------- registers
    wire         srst, enable;
    wire [2:0]   a_level, a_ts;
    wire         a_pad, a_jump, a_first;
    wire [1:0]   a_policy;
    wire [10:0]  a_W, a_H;
    wire [15:0]  a_T;
    wire [63:0]  a_sid, a_ctr0, a_link, p_at, p_ctr0, apply_ctr, ld_ctr0, open_ctr, pkt_done_ctr;
    wire [31:0]  a_maxgap, a_padmin, a_padcap;
    wire [127:0] k_tag, k_pol, k_perm, k_dum, k_aead;
    wire         p_valid, p_newsid, apply, load, resume, flush, halted, started, pkt_done, pk_idle;
    wire         e_pre, e_order, e_range, e_jump, e_padovf, table_wait, ks_stall;
    wire         ds_idle;

    nv_axil_regs #(.MAXW(MAXW), .MAXH(MAXH), .PAD_BUILT(PAD), .BUILD(BUILD)) u_regs (
        .clk(clk), .por(rst), .soft_rst(srst),
        .s_axil_awaddr(s_axil_awaddr), .s_axil_awprot(s_axil_awprot), .s_axil_awvalid(s_axil_awvalid),
        .s_axil_awready(s_axil_awready), .s_axil_wdata(s_axil_wdata), .s_axil_wstrb(s_axil_wstrb),
        .s_axil_wvalid(s_axil_wvalid), .s_axil_wready(s_axil_wready), .s_axil_bresp(s_axil_bresp),
        .s_axil_bvalid(s_axil_bvalid), .s_axil_bready(s_axil_bready), .s_axil_araddr(s_axil_araddr),
        .s_axil_arprot(s_axil_arprot), .s_axil_arvalid(s_axil_arvalid), .s_axil_arready(s_axil_arready),
        .s_axil_rdata(s_axil_rdata), .s_axil_rresp(s_axil_rresp), .s_axil_rvalid(s_axil_rvalid),
        .s_axil_rready(s_axil_rready),
        .enable(enable), .a_level(a_level), .a_ts(a_ts), .a_pad(a_pad), .a_policy(a_policy), .a_jump(a_jump),
        .a_W(a_W), .a_H(a_H), .a_T(a_T), .a_sid(a_sid), .a_ctr0(a_ctr0), .a_first(a_first), .a_link(a_link),
        .a_maxgap(a_maxgap), .a_padmin(a_padmin), .a_padcap(a_padcap),
        .k_tag(k_tag), .k_pol(k_pol), .k_perm(k_perm), .k_dum(k_dum), .k_aead(k_aead),
        .p_valid(p_valid), .p_at(p_at), .p_newsid(p_newsid), .p_ctr0(p_ctr0), .apply(apply), .apply_ctr(apply_ctr),
        .load(load), .resume(resume), .ld_ctr0(ld_ctr0), .flush(flush),
        .open_ctr(open_ctr), .halted(halted), .busy(!ds_idle || !pk_idle), .table_ready(!table_wait),
        .open_packet(started), .pkt_done(pkt_done), .pkt_done_ctr(pkt_done_ctr),
        .ev_word_in(s_axis_tvalid && s_axis_tready), .ev_word_out(m_axis_tvalid && m_axis_tready),
        .ev_pkt(m_axis_tvalid && m_axis_tready && m_axis_tlast), .ev_in_wait(pk_idle && !s_axis_tvalid),
        .ev_out_stall(m_axis_tvalid && !m_axis_tready), .ev_table_wait(table_wait), .ev_ks_wait(ks_stall),
        .ev_range(e_range), .ev_order(e_order), .ev_pre(e_pre), .ev_jump(e_jump), .ev_padovf(e_padovf));

    // ---------------------------------------------------------------- packetizer
    wire        pk_valid, pk_ready, pk_xor, pk_perm, pk_bank;
    wire [31:0] pk_word;
    wire [1:0]  pk_kind;
    wire        tg_start, tg_bank, tg_done, fe_valid, fe_perm, fe_bank;
    wire [63:0] tg_ctr;
    nv_packetizer u_pk (
        .clk(clk), .rst(srst), .enable(enable),
        .s_tvalid(s_axis_tvalid), .s_tready(s_axis_tready), .s_tdata(s_axis_tdata),
        .o_valid(pk_valid), .o_ready(pk_ready), .o_word(pk_word), .o_kind(pk_kind), .o_xor(pk_xor),
        .o_perm(pk_perm), .o_bank(pk_bank),
        .a_level(a_level), .a_ts(a_ts), .a_pad(a_pad), .a_policy(a_policy), .a_jump(a_jump), .a_W(a_W), .a_H(a_H),
        .a_T(a_T), .a_sid(a_sid), .a_ctr0(a_ctr0), .a_first(a_first), .a_link(a_link), .a_maxgap(a_maxgap),
        .p_valid(p_valid), .p_at(p_at), .p_newsid(p_newsid), .p_ctr0(p_ctr0), .apply(apply), .apply_ctr(apply_ctr),
        .load(load), .resume(resume), .ld_ctr0(ld_ctr0), .flush(flush), .ds_idle(ds_idle),
        .open_ctr(open_ctr), .started(started), .halted(halted), .pkt_done(pkt_done), .pkt_done_ctr(pkt_done_ctr),
        .idle(pk_idle), .e_pre(e_pre), .e_order(e_order), .e_range(e_range), .e_jump(e_jump),
        .table_wait(table_wait), .tg_start(tg_start), .tg_ctr(tg_ctr), .tg_bank(tg_bank), .tg_done(tg_done),
        .fe_exit_perm(fe_valid && fe_perm), .fe_exit_bank(fe_bank));

    // ---------------------------------------------------------------- trailer (counts, padding)
    wire        tr_valid, tr_ready, tr_last, tr_xor, tr_perm, tr_bank, tr_busy;
    wire [31:0] tr_word;
    wire [1:0]  tr_kind;
    nv_trailer #(.PAD(PAD), .MAX_CD(MAX_CD), .BM_AW(BM_AW)) u_tr (
        .clk(clk), .rst(srst), .pad_min(a_padmin), .pad_cap(a_padcap), .key_dum(k_dum),
        .i_valid(pk_valid), .i_ready(pk_ready), .i_word(pk_word), .i_kind(pk_kind), .i_xor(pk_xor),
        .i_perm(pk_perm), .i_bank(pk_bank),
        .o_valid(tr_valid), .o_ready(tr_ready), .o_word(tr_word), .o_kind(tr_kind), .o_last(tr_last),
        .o_xor(tr_xor), .o_perm(tr_perm), .o_bank(tr_bank), .e_padovf(e_padovf), .busy(tr_busy));

    // ---------------------------------------------------------------- XOR (K_pol), restarted after each header
    function [31:0] bswap(input [31:0] v);
        bswap = {v[7:0], v[15:8], v[23:16], v[31:24]};
    endfunction
    reg  [3:0]  xh;
    reg  [2:0]  x_b;
    reg  [63:0] x_sid, x_ctr;
    reg         x_start;
    wire        tr_fire = tr_valid && tr_ready;
    always @(posedge clk) begin
        x_start <= 1'b0;
        if (srst) begin
            xh  <= 4'd0;
            x_b <= 3'd0;
        end else if (tr_fire && tr_kind == 2'd0) begin
            xh <= (xh == 4'd11) ? 4'd0 : xh + 4'd1;
            case (xh)
            4'd1:  x_b <= (tr_word[15:8] == 8'd3) ? tr_word[26:24] : 3'd0;   // ts_bits at V3, 0 at V1
            4'd2:  x_sid[63:32] <= bswap(tr_word);
            4'd3:  x_sid[31:0]  <= bswap(tr_word);
            4'd4:  x_ctr[63:32] <= bswap(tr_word);
            4'd5:  x_ctr[31:0]  <= bswap(tr_word);
            4'd11: x_start <= 1'b1;
            default: ;
            endcase
        end
    end
    wire        xo_valid, xo_ready;
    wire [31:0] xo_word;
    wire [4:0]  xo_meta;
    nv_xor #(.MW(5)) u_xor (
        .clk(clk), .rst(srst), .start(x_start), .key(k_pol), .nonce({x_ctr[62:0], 1'b0, x_sid}), .b(x_b),
        .in_valid(tr_valid), .in_ready(tr_ready), .in_word(tr_word), .in_xor(tr_xor),
        .in_meta({tr_kind, tr_last, tr_perm, tr_bank}),
        .out_valid(xo_valid), .out_ready(xo_ready), .out_word(xo_word), .out_meta(xo_meta), .ks_stall(ks_stall));

    // ---------------------------------------------------------------- skid buffer and credit gate
    wire        sk_valid, sk_ready;
    wire [36:0] sk_data;
    skid_buf #(.W(37)) u_skid (
        .clk(clk), .rst(srst), .i_valid(xo_valid), .i_ready(xo_ready), .i_data({xo_meta, xo_word}),
        .o_valid(sk_valid), .o_ready(sk_ready), .o_data(sk_data));
    reg  [9:0]  credit;
    wire        f_pop;
    assign sk_ready = (credit != 10'd0);
    wire        fe_in = sk_valid && sk_ready;
    always @(posedge clk) begin
        if (srst) credit <= FIFO_DEPTH;
        else      credit <= credit - (fe_in ? 10'd1 : 10'd0) + (f_pop ? 10'd1 : 10'd0);
    end

    // ---------------------------------------------------------------- Feistel (fixed latency) and table generator
    wire        fe_last;
    wire [31:0] fe_word;
    wire [1:0]  fe_kind;
    wire        tw_en, tw_bank, tg_busy;
    wire [2:0]  tw_tab;
    wire [10:0] tw_addr, tw_data;
    nv_feistel #(.MAXW(MAXW), .MAXH(MAXH)) u_fe (
        .clk(clk), .rst(srst), .W(a_W), .H(a_H),
        .in_valid(fe_in), .in_word(sk_data[31:0]), .in_perm(sk_data[33]), .in_bank(sk_data[32]),
        .in_kind(sk_data[36:35]), .in_last(sk_data[34]),
        .out_valid(fe_valid), .out_word(fe_word), .out_kind(fe_kind), .out_last(fe_last),
        .out_perm(fe_perm), .out_bank(fe_bank),
        .tw_en(tw_en), .tw_bank(tw_bank), .tw_tab(tw_tab), .tw_addr(tw_addr), .tw_data(tw_data));
    nv_table_gen u_tg (
        .clk(clk), .rst(srst), .start(tg_start), .key(k_perm), .nonce({tg_ctr[62:0], 1'b0, a_sid}),
        .W(a_W), .H(a_H), .bank(tg_bank), .busy(tg_busy), .done(tg_done),
        .tw_en(tw_en), .tw_bank(tw_bank), .tw_tab(tw_tab), .tw_addr(tw_addr), .tw_data(tw_data));
    reg  [5:0]  fe_cnt;              // words inside nv_feistel
    always @(posedge clk) begin
        if (srst) fe_cnt <= 6'd0;
        else      fe_cnt <= fe_cnt + (fe_in ? 6'd1 : 6'd0) - (fe_valid ? 6'd1 : 6'd0);
    end

    // ---------------------------------------------------------------- FIFO, tag, output
    wire        f_valid, f_ready;
    wire [34:0] f_data;
    wire [9:0]  f_count;
    nv_word_fifo #(.DEPTH(FIFO_DEPTH), .AW(9), .WIDTH(35)) u_fifo (
        .clk(clk), .rst(srst), .w_en(fe_valid), .w_data({fe_kind, fe_last, fe_word}),
        .o_valid(f_valid), .o_ready(f_ready), .o_data(f_data), .count(f_count), .overflow(fifo_overflow));
    assign f_pop = f_valid && f_ready;
    wire        b_valid, b_ready, b_last, t_valid, t_ack, tag_busy, blk_wait;
    wire [31:0] b_word;
    wire [127:0] t_data;
    nv_tag32 #(.U(U)) u_tag (
        .clk(clk), .rst(srst), .key_tag(k_tag), .key_aead(k_aead),
        .in_valid(f_valid), .in_ready(f_ready), .in_word(f_data[31:0]), .in_last(f_data[32]),
        .o_valid(b_valid), .o_ready(b_ready), .o_word(b_word), .o_last(b_last),
        .t_valid(t_valid), .t_data(t_data), .t_ack(t_ack), .busy(tag_busy), .blk_wait(blk_wait));
    nv_out_mux u_mux (
        .clk(clk), .rst(srst), .b_valid(b_valid), .b_ready(b_ready), .b_word(b_word), .b_last(b_last),
        .t_valid(t_valid), .t_data(t_data), .t_ack(t_ack),
        .m_tvalid(m_axis_tvalid), .m_tready(m_axis_tready), .m_tdata(m_axis_tdata), .m_tlast(m_axis_tlast));

    assign ds_idle = !tr_busy && !xo_valid && !sk_valid && (fe_cnt == 6'd0) && (f_count == 10'd0) && !f_valid &&
                     !tag_busy;
endmodule
`default_nettype wire
