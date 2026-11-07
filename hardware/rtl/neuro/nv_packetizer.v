// nv_packetizer: EVT 2.0 input rules and the packet FSM; emits header, payload and EOP words in-band (DESIGN §2.4, §3).
// Golden model: software/neuro/packet.py :: Packetizer, PacketHeader.pack(); commit boundary
//               software/neuro/sender.py :: Encryptor._account() / _apply()
//
// Input rules (§2.4): words before the first TIME_HIGH are dropped (ERR_PRE_TH); a TIME_HIGH below the current one
// is dropped (ERR_ORDER); a CD word with x >= W or y >= H is dropped (ERR_RANGE); a TIME_HIGH with
// 64*v - t_start > MAX_GAP_US is a jump: JUMP_MODE 0 drops it and every following non-TIME_HIGH word up to the next
// non-jump TIME_HIGH (ERR_JUMP); JUMP_MODE 1 closes the open packet, emits one empty FINAL packet and halts with
// the jumping TIME_HIGH left in the input (tready low) until a commit with a new SID resumes.
// Closing rule (§3.2): a TIME_HIGH with 64*v >= t_start + T closes the open packet; the word is then evaluated
// again, so the empty packets of a skip are closed one by one (each close may apply a pending commit, exactly as
// the model's hook). FLUSH closes the open packet and one empty FINAL packet.
// The header of a packet is emitted lazily, before its first payload word or at its close, so its fields are
// those of the active set at that time (FINAL is set when a pending commit with a new SID applies at ctr + 1;
// the commit rule at >= open + 2 guarantees that the commit is known before that header is emitted).
// Output words: kind 0 header (12 words), kind 1 payload, kind 3 EOP marker (consumed by nv_trailer). Side band:
// xor (real CD word at V1/V3), perm (real CD word at V2/V3), bank (table bank of the packet).
// Commit boundary: when the packet at-1 has been closed, the pipeline is drained (ds_idle) before `apply`, so the
// downstream stages, which read the active keys, never see two key sets at once.
// Tables: a payload CD word at V2/V3 waits until its packet's tables are in a bank (TABLE_WAIT). A fill for the open
// packet starts in the bank not used last, once no permuted word of that bank is still in front of the Feistel
// output; after that, the tables of open_ctr + 1 are prefetched into the other bank on the same condition.
`default_nettype none
module nv_packetizer (
    input  wire         clk,
    input  wire         rst,
    input  wire         enable,
    // input stream
    input  wire         s_tvalid,
    output reg          s_tready,
    input  wire [31:0]  s_tdata,
    // output stream
    output reg          o_valid,
    input  wire         o_ready,
    output reg  [31:0]  o_word,
    output reg  [1:0]   o_kind,
    output reg          o_xor,
    output reg          o_perm,
    output reg          o_bank,
    // active set (nv_axil_regs)
    input  wire [2:0]   a_level,
    input  wire [2:0]   a_ts,
    input  wire         a_pad,
    input  wire [1:0]   a_policy,
    input  wire         a_jump,
    input  wire [10:0]  a_W,
    input  wire [10:0]  a_H,
    input  wire [15:0]  a_T,
    input  wire [63:0]  a_sid,
    input  wire [63:0]  a_ctr0,
    input  wire         a_first,      // new epoch: the packet with ctr == a_ctr0 carries FIRST
    input  wire [63:0]  a_link,       // link of the FIRST packet
    input  wire [31:0]  a_maxgap,
    // pending commit
    input  wire         p_valid,
    input  wire [63:0]  p_at,
    input  wire         p_newsid,
    input  wire [63:0]  p_ctr0,
    output reg          apply,        // pulse: pending set becomes active (pipeline drained)
    output reg  [63:0]  apply_ctr,    // counter of the packet just closed (at - 1)
    input  wire         load,         // pulse: commit while ENABLE = 0 (fresh start at ld_ctr0)
    input  wire         resume,       // pulse: commit while halted
    input  wire [63:0]  ld_ctr0,
    input  wire         flush,        // pulse: CTRL.FLUSH
    input  wire         ds_idle,      // everything behind this stage is empty
    // status
    output reg  [63:0]  open_ctr,
    output reg          started,
    output reg          halted,
    output reg          pkt_done,     // pulse: a packet's EOP was emitted
    output reg  [63:0]  pkt_done_ctr,
    output wire         idle,
    output reg          e_pre, e_order, e_range, e_jump,
    output wire         table_wait,
    // table generator
    output reg          tg_start,
    output reg  [63:0]  tg_ctr,
    output reg          tg_bank,
    input  wire         tg_done,
    input  wire         fe_exit_perm, // a permuted word left nv_feistel
    input  wire         fe_exit_bank
);
    localparam S_RUN = 3'd0, S_HDR = 3'd1, S_CLOSE = 3'd2, S_EOP = 3'd3, S_POST = 3'd4, S_DRAIN = 3'd5,
               S_HALT = 3'd6;
    localparam A_NONE = 3'd0, A_DROP = 3'd1, A_EMIT = 3'd2, A_CLOSE = 3'd3, A_JHALT = 3'd4, A_START = 3'd5,
               A_HDR = 3'd6, A_WAIT = 3'd7;

    reg  [2:0]  st;
    reg  [3:0]  hw;            // header word index
    reg  [39:0] t_start;
    reg  [27:0] cur_th;
    reg         dropping;
    reg         hdr_sent;
    reg         close_final;   // the packet being closed is the extra empty FINAL packet
    reg         after_final;   // after this close: emit the FINAL packet
    reg         after_halt;    // after the FINAL packet: halt
    reg         flush_req;
    reg         hdr_ret;       // header emitted from S_CLOSE: continue with the EOP
    reg         in_loop;       // a closing TIME_HIGH is being re-evaluated (jump/order checked once, as the model)

    // tables
    reg         bank_ok  [0:1];
    reg  [63:0] bank_ctr [0:1];
    reg  [15:0] inflight [0:1];
    reg         filling;
    reg  [63:0] fill_ctr;
    reg         fill_bank;
    reg         last_used;

    function [31:0] bswap(input [31:0] v);
        bswap = {v[7:0], v[15:8], v[23:16], v[31:24]};
    endfunction

    // ------------------------------------------------------------------ header words
    wire        fin_by_commit = p_valid && p_newsid && (p_at == open_ctr + 64'd1);
    wire        f_final = close_final || fin_by_commit;
    wire        f_first = a_first && (open_ctr == a_ctr0);
    wire [7:0]  flags   = {5'd0, f_final, f_first, a_pad};
    wire [63:0] link    = f_first ? a_link : a_ctr0;
    wire [63:0] t64     = {24'd0, t_start};
    reg  [31:0] hword;
    always @* begin
        case (hw)
        4'd0:  hword = 32'h3145564E;                                   // "NVE1"
        4'd1:  hword = {5'd0, a_ts, flags, 5'd0, a_level, 8'd1};
        4'd2:  hword = bswap(a_sid[63:32]);
        4'd3:  hword = bswap(a_sid[31:0]);
        4'd4:  hword = bswap(open_ctr[63:32]);
        4'd5:  hword = bswap(open_ctr[31:0]);
        4'd6:  hword = bswap(t64[63:32]);
        4'd7:  hword = bswap(t64[31:0]);
        4'd8:  hword = {a_H[7:0], 5'd0, a_H[10:8], a_W[7:0], 5'd0, a_W[10:8]};
        4'd9:  hword = {6'd0, a_pad ? a_policy : 2'd0, 8'd8, a_T[7:0], a_T[15:8]};
        4'd10: hword = bswap(link[63:32]);
        default: hword = bswap(link[31:0]);
        endcase
    end

    // ------------------------------------------------------------------ input evaluation
    wire [3:0]  typ    = s_tdata[31:28];
    wire [27:0] v      = s_tdata[27:0];
    wire [39:0] v64    = {6'd0, v, 6'd0};
    wire signed [40:0] diff = $signed({1'b0, v64}) - $signed({1'b0, t_start});
    wire        is_jump  = (diff > $signed({9'd0, a_maxgap}));
    wire        closes   = (v64 >= t_start + {24'd0, a_T});
    wire        is_cd    = (typ[3:1] == 3'b000);
    wire        in_range = (s_tdata[21:11] < a_W) && (s_tdata[10:0] < a_H);
    wire        lv_xor   = (a_level == 3'd1) || (a_level == 3'd3);
    wire        lv_perm  = (a_level == 3'd2) || (a_level == 3'd3);
    wire        o_free   = !o_valid || o_ready;
    wire        tab0     = bank_ok[0] && (bank_ctr[0] == open_ctr);
    wire        tab1     = bank_ok[1] && (bank_ctr[1] == open_ctr);
    wire        tab_rdy  = tab0 || tab1;
    wire        tab_bank = tab1;

    reg [2:0] act;
    always @* begin
        act = A_NONE;
        if (st == S_RUN && enable && !halted && !flush_req && s_tvalid) begin
            if (!started)
                act = (typ == 4'h8) ? A_START : A_DROP;
            else if (typ == 4'h8) begin
                if (!in_loop && v < cur_th)         act = A_DROP;
                else if (!in_loop && is_jump)       act = a_jump ? A_JHALT : A_DROP;
                else if (closes)                    act = A_CLOSE;
                else if (!hdr_sent)                 act = A_HDR;
                else                                act = o_free ? A_EMIT : A_WAIT;
            end else if (dropping || (is_cd && !in_range))
                act = A_DROP;
            else if (!hdr_sent)
                act = A_HDR;
            else if (is_cd && lv_perm && !tab_rdy)
                act = A_WAIT;
            else
                act = o_free ? A_EMIT : A_WAIT;
        end
    end
    always @* s_tready = (act == A_DROP) || (act == A_EMIT);
    assign table_wait = (act == A_WAIT) && is_cd && lv_perm && !tab_rdy;
    assign idle = (st == S_RUN) && !o_valid && !flush_req;

    // table fill decisions
    wire        need_fill = table_wait && !(filling && fill_ctr == open_ctr) && (inflight[!last_used] == 16'd0);
    wire        pre_bank  = !tab_bank;
    wire [63:0] next_ctr  = open_ctr + 64'd1;
    wire        prefetch  = !need_fill && !filling && started && lv_perm && tab_rdy && (st == S_RUN) &&
                            !(p_valid && p_at == next_ctr) && (inflight[pre_bank] == 16'd0) &&
                            !(bank_ok[pre_bank] && bank_ctr[pre_bank] == next_ctr);
    wire        emit_perm = (act == A_EMIT) && is_cd && lv_perm;

    always @(posedge clk) begin
        apply    <= 1'b0;
        pkt_done <= 1'b0;
        tg_start <= 1'b0;
        e_pre <= 1'b0; e_order <= 1'b0; e_range <= 1'b0; e_jump <= 1'b0;
        if (o_valid && o_ready) o_valid <= 1'b0;
        if (rst) begin
            st <= S_RUN; o_valid <= 1'b0; started <= 1'b0; halted <= 1'b0; dropping <= 1'b0;
            hdr_sent <= 1'b0; hdr_ret <= 1'b0; in_loop <= 1'b0; close_final <= 1'b0; after_final <= 1'b0; after_halt <= 1'b0; flush_req <= 1'b0;
            open_ctr <= 64'd0; t_start <= 40'd0; cur_th <= 28'd0; hw <= 4'd0;
            bank_ok[0] <= 1'b0; bank_ok[1] <= 1'b0; inflight[0] <= 16'd0; inflight[1] <= 16'd0;
            filling <= 1'b0; last_used <= 1'b1;
        end else begin
            // -------------------------------------------- tables
            inflight[0] <= inflight[0] + ((emit_perm && !tab_bank) ? 16'd1 : 16'd0)
                                       - ((fe_exit_perm && !fe_exit_bank) ? 16'd1 : 16'd0);
            inflight[1] <= inflight[1] + ((emit_perm && tab_bank) ? 16'd1 : 16'd0)
                                       - ((fe_exit_perm && fe_exit_bank) ? 16'd1 : 16'd0);
            if (emit_perm) last_used <= tab_bank;
            if (tg_done && filling) begin
                bank_ok[fill_bank] <= 1'b1;
                filling <= 1'b0;
            end
            if (need_fill || prefetch) begin
                tg_start  <= 1'b1;
                tg_ctr    <= need_fill ? open_ctr : next_ctr;
                tg_bank   <= need_fill ? !last_used : pre_bank;
                fill_ctr  <= need_fill ? open_ctr : next_ctr;
                fill_bank <= need_fill ? !last_used : pre_bank;
                filling   <= 1'b1;
                bank_ok[need_fill ? !last_used : pre_bank]  <= 1'b0;
                bank_ctr[need_fill ? !last_used : pre_bank] <= need_fill ? open_ctr : next_ctr;
            end

            if (flush) flush_req <= 1'b1;

            // -------------------------------------------- main FSM
            case (st)
            S_RUN: begin
                if (flush_req && o_free) begin
                    flush_req <= 1'b0;
                    if (started) begin
                        close_final <= 1'b0; after_final <= 1'b1; after_halt <= 1'b0;
                        st <= S_CLOSE;
                    end
                end else case (act)
                A_DROP: begin
                    if (!started)               e_pre   <= 1'b1;
                    else if (typ == 4'h8 && v < cur_th) e_order <= 1'b1;
                    else if (typ == 4'h8 || dropping) begin
                        e_jump <= 1'b1;
                        if (typ == 4'h8) dropping <= 1'b1;
                    end else                    e_range <= 1'b1;
                end
                A_START: begin
                    started  <= 1'b1;
                    cur_th   <= v;
                    t_start  <= v64;
                    dropping <= 1'b0;
                end
                A_CLOSE: begin
                    dropping <= 1'b0;
                    in_loop  <= 1'b1;
                    close_final <= 1'b0; after_final <= 1'b0; after_halt <= 1'b0;
                    st <= S_CLOSE;
                end
                A_JHALT: begin
                    close_final <= 1'b0; after_final <= 1'b1; after_halt <= 1'b1;
                    st <= S_CLOSE;
                end
                A_HDR: begin
                    hw <= 4'd0;
                    hdr_ret <= 1'b0;
                    st <= S_HDR;
                end
                A_EMIT: begin
                    o_valid <= 1'b1;
                    o_word  <= s_tdata;
                    o_kind  <= 2'd1;
                    o_xor   <= is_cd && lv_xor;
                    o_perm  <= is_cd && lv_perm;
                    o_bank  <= tab_bank;
                    if (typ == 4'h8) begin
                        cur_th   <= v;
                        dropping <= 1'b0;
                        in_loop  <= 1'b0;
                    end
                end
                default: ;
                endcase
            end
            S_HDR: if (o_free) begin
                o_valid <= 1'b1;
                o_word  <= hword;
                o_kind  <= 2'd0;
                o_xor   <= 1'b0;
                o_perm  <= 1'b0;
                hw      <= hw + 4'd1;
                if (hw == 4'd11) begin
                    hdr_sent <= 1'b1;
                    st <= hdr_ret ? S_EOP : S_RUN;
                end
            end
            S_CLOSE: begin
                if (!hdr_sent) begin
                    hw <= 4'd0;
                    hdr_ret <= 1'b1;
                    st <= S_HDR;
                end else
                    st <= S_EOP;
            end
            S_EOP: if (o_free) begin
                o_valid <= 1'b1;
                o_word  <= 32'd0;
                o_kind  <= 2'd3;
                o_xor   <= 1'b0;
                o_perm  <= 1'b0;
                pkt_done     <= 1'b1;
                pkt_done_ctr <= open_ctr;
                st <= S_POST;
            end
            S_POST: begin
                if (p_valid && p_at == open_ctr + 64'd1) st <= S_DRAIN;
                else begin
                    t_start  <= t_start + {24'd0, a_T};
                    open_ctr <= open_ctr + 64'd1;
                    hdr_sent <= 1'b0;
                    st <= next_after_close(close_final, after_final);
                    advance_flags;
                end
            end
            S_DRAIN: if (!o_valid && ds_idle) begin
                apply     <= 1'b1;
                apply_ctr <= open_ctr;
                t_start   <= t_start + {24'd0, a_T};
                open_ctr  <= p_newsid ? p_ctr0 : open_ctr + 64'd1;
                hdr_sent  <= 1'b0;
                bank_ok[0] <= 1'b0; bank_ok[1] <= 1'b0; filling <= 1'b0;
                st <= next_after_close(close_final, after_final);
                advance_flags;
            end
            S_HALT: ;
            default: st <= S_RUN;
            endcase

            if (resume && halted) begin
                halted  <= 1'b0;
                started <= 1'b0;
                open_ctr <= ld_ctr0;
                hdr_sent <= 1'b0;
                dropping <= 1'b0;
                in_loop  <= 1'b0;
                bank_ok[0] <= 1'b0; bank_ok[1] <= 1'b0; filling <= 1'b0;
                st <= S_RUN;
            end
            if (load) begin
                halted  <= 1'b0;
                started <= 1'b0;
                open_ctr <= ld_ctr0;
                hdr_sent <= 1'b0;
                dropping <= 1'b0;
                flush_req <= 1'b0;
                in_loop  <= 1'b0;
                bank_ok[0] <= 1'b0; bank_ok[1] <= 1'b0; filling <= 1'b0;
                st <= S_RUN;
            end
        end
    end

    // after a close: the extra FINAL packet (flush / jump halt), the halt, or back to the input
    function [2:0] next_after_close(input cf, input af);
        if (cf)      next_after_close = after_halt ? S_HALT : S_RUN;
        else if (af) next_after_close = S_CLOSE;
        else         next_after_close = S_RUN;
    endfunction
    task advance_flags;
        begin
            if (close_final) begin
                close_final <= 1'b0;
                after_final <= 1'b0;
                if (after_halt) begin
                    halted     <= 1'b1;
                    after_halt <= 1'b0;
                end
            end else if (after_final) begin
                close_final <= 1'b1;
            end
        end
    endtask
endmodule
`default_nettype wire
