// nv_axil_regs: AXI4-Lite register file of nv_top: shadow set, commit rules, counters (DESIGN §6.7).
// Golden model: software/neuro/sender.py :: check_config(), commit_ok(), Encryptor.commit()
//
// Writes go to the shadow set {MODE, GEOM, T_US, SID, CTR0, PAD_MIN, PAD_CAP, MAX_GAP_US, keys}. CTRL.COMMIT
// checks it (codes: 1 LATE, 2 GEOM, 3 LEVEL/TS/PAD, 4 T_US, 5 REWIND, in the model's order) and then
//   ENABLE = 0: makes it active at once (fresh start at CTR0, FIRST with link 2^64-1; `load`), the
//               counterpart of the model's Encryptor constructor. A SID with the base of LAST_SID must pass the
//               REWIND rule, so SOFT_RST followed by the old SID and CTR0 is refused;
//   halted:     makes it active at once (`resume`); the SID must differ from the active one;
//   otherwise:  holds it as the pending set for COMMIT_AT, refused (LATE) if COMMIT_AT < open ctr + 2 or a
//               commit is already pending, or (REWIND) if a new SID with the base of LAST_SID has a lower epoch,
//               or the same epoch and CTR0 <= LAST_CTR.
// The pending set becomes active on nv_packetizer's `apply` (packet COMMIT_AT-1 closed, pipeline drained): a new
// SID starts a new epoch (ctr0 = CTR0, FIRST with link = closed ctr if the base is unchanged, else 2^64-1); the same
// SID keeps the counter, ctr0 and link.
// Counters run while ENABLE (and KEYS_VALID) are set; CTRL.SNAP copies all of them at once into the read registers.
// LAST_SID / LAST_CTR are cleared only by the power-on reset (`por`), not by SOFT_RST.
`default_nettype none
module nv_axil_regs #(
    parameter MAXW = 1280,
    parameter MAXH = 720,
    parameter PAD_BUILT = 1,
    parameter [7:0] BUILD = 8'h00
) (
    input  wire         clk,
    input  wire         por,               // power-on reset
    output wire         soft_rst,          // datapath reset: por or CTRL.SOFT_RST
    // AXI4-Lite slave
    input  wire [7:0]   s_axil_awaddr,
    input  wire [2:0]   s_axil_awprot,
    input  wire         s_axil_awvalid,
    output wire         s_axil_awready,
    input  wire [31:0]  s_axil_wdata,
    input  wire [3:0]   s_axil_wstrb,
    input  wire         s_axil_wvalid,
    output wire         s_axil_wready,
    output wire [1:0]   s_axil_bresp,
    output reg          s_axil_bvalid,
    input  wire         s_axil_bready,
    input  wire [7:0]   s_axil_araddr,
    input  wire [2:0]   s_axil_arprot,
    input  wire         s_axil_arvalid,
    output wire         s_axil_arready,
    output reg  [31:0]  s_axil_rdata,
    output wire [1:0]   s_axil_rresp,
    output reg          s_axil_rvalid,
    input  wire         s_axil_rready,
    // active set
    output wire         enable,
    output reg  [2:0]   a_level,
    output reg  [2:0]   a_ts,
    output reg          a_pad,
    output reg  [1:0]   a_policy,
    output reg          a_jump,
    output reg  [10:0]  a_W,
    output reg  [10:0]  a_H,
    output reg  [15:0]  a_T,
    output reg  [63:0]  a_sid,
    output reg  [63:0]  a_ctr0,
    output reg          a_first,
    output reg  [63:0]  a_link,
    output reg  [31:0]  a_maxgap,
    output reg  [31:0]  a_padmin,
    output reg  [31:0]  a_padcap,
    output reg  [127:0] k_tag, k_pol, k_perm, k_dum, k_aead,
    // pending set
    output reg          p_valid,
    output reg  [63:0]  p_at,
    output wire         p_newsid,
    output reg  [63:0]  p_ctr0,
    input  wire         apply,
    input  wire [63:0]  apply_ctr,
    output reg          load,
    output reg          resume,
    output wire [63:0]  ld_ctr0,
    output reg          flush,
    // datapath state
    input  wire [63:0]  open_ctr,
    input  wire         halted,
    input  wire         busy,
    input  wire         table_ready,
    input  wire         open_packet,
    input  wire         pkt_done,
    input  wire [63:0]  pkt_done_ctr,
    // counter events
    input  wire         ev_word_in, ev_word_out, ev_pkt, ev_in_wait, ev_out_stall, ev_table_wait, ev_ks_wait,
    input  wire         ev_range, ev_order, ev_pre, ev_jump, ev_padovf
);
    localparam C_NONE = 3'd0, C_LATE = 3'd1, C_GEOM = 3'd2, C_LEVEL = 3'd3, C_TUS = 3'd4, C_REWIND = 3'd5,
               C_NOKEYS = 3'd6;

    // ------------------------------------------------------------ shadow set
    reg [31:0]  s_mode, s_geom, s_tus, s_padmin, s_padcap, s_maxgap;
    reg [63:0]  s_sid, s_ctr0, s_at;
    reg [127:0] s_ktag, s_kpol, s_kperm, s_kdum, s_kaead;
    // pending copy of the shadow set
    reg [31:0]  q_mode, q_geom, q_tus, q_padmin, q_padcap, q_maxgap;
    reg [63:0]  q_sid;
    reg [127:0] q_ktag, q_kpol, q_kperm, q_kdum, q_kaead;
    reg         ctl_enable, ctl_srst, keys_valid, commit_late, cfg_err;
    reg [2:0]   cfg_code;
    reg [63:0]  last_sid, last_ctr;
    reg         last_valid;

    assign soft_rst = por || ctl_srst;
    assign enable   = ctl_enable && keys_valid;
    assign p_newsid = (q_sid != a_sid);
    assign ld_ctr0  = s_ctr0;

    // ------------------------------------------------------------ commit check (combinational on the shadow set)
    wire [2:0]  c_level = s_mode[2:0];
    wire [2:0]  c_ts    = s_mode[6:4];
    wire        c_pad   = s_mode[8];
    wire [1:0]  c_pol   = s_mode[10:9];
    wire [10:0] c_W     = s_geom[10:0];
    wire [10:0] c_H     = s_geom[26:16];
    wire        c_perm  = (c_level == 3'd2) || (c_level == 3'd3);
    wire        same_base = last_valid && (s_sid[63:16] == last_sid[63:16]);
    wire        rewind_bad = same_base && !((s_sid[15:0] > last_sid[15:0]) ||
                                            (s_sid[15:0] == last_sid[15:0] && s_ctr0 > last_ctr));
    reg  [2:0]  code;
    always @* begin
        code = C_NONE;
        if (c_W == 0 || c_H == 0 || c_W > MAXW || c_H > MAXH || s_geom[15:11] != 0 || s_geom[31:27] != 0)
            code = C_GEOM;
        else if (c_perm && (c_W < 16 || c_H < 16))
            code = C_GEOM;
        else if (c_level > 3'd4)
            code = C_LEVEL;
        else if ((c_level == 3'd3) ? (c_ts == 3'd0 || c_ts > 3'd6) : (c_ts != 3'd0))
            code = C_LEVEL;
        else if (c_pad && (PAD_BUILT == 0 || !((c_level == 3'd3 && c_ts == 3'd6) || c_level == 3'd4) ||
                           c_pol == 2'd0 || c_pol == 2'd3 || s_padmin == 0))
            code = C_LEVEL;
        else if (s_tus[5:0] != 0 || s_tus < 64 || s_tus > 65472)
            code = C_TUS;
        else if (s_sid == 0)
            code = C_REWIND;
        else if (!ctl_enable)
            code = rewind_bad ? C_REWIND : C_NONE;
        else if (halted)
            code = (s_sid == a_sid || rewind_bad) ? C_REWIND : C_NONE;
        else if (s_at < open_ctr + 64'd2)
            code = C_LATE;
        else if (s_sid != a_sid && rewind_bad)
            code = C_REWIND;
        else if (p_valid)
            code = C_LATE;
    end

    // ------------------------------------------------------------ counters
    reg [63:0] c_pkts, c_win, c_wout, c_cyc;
    reg [31:0] c_iw, c_os, c_tw, c_kw, c_rng, c_ord, c_pre, c_jmp, c_ovf, c_cfg;
    reg [63:0] r_pkts, r_win, r_wout, r_cyc;
    reg [31:0] r_iw, r_os, r_tw, r_kw, r_rng, r_ord, r_pre, r_jmp, r_ovf, r_cfg;
    function [31:0] sat(input [31:0] c, input e);
        sat = (e && c != 32'hFFFF_FFFF) ? c + 32'd1 : c;
    endfunction

    // ------------------------------------------------------------ AXI-Lite
    assign s_axil_bresp = 2'b00;
    assign s_axil_rresp = 2'b00;
    wire wr = s_axil_awvalid && s_axil_wvalid && !s_axil_bvalid;
    assign s_axil_awready = wr;
    assign s_axil_wready  = wr;
    assign s_axil_arready = !s_axil_rvalid;
    function [31:0] merge(input [31:0] old, input [31:0] data, input [3:0] strb);
        integer i;
        begin
            for (i = 0; i < 4; i = i + 1) merge[8*i +: 8] = strb[i] ? data[8*i +: 8] : old[8*i +: 8];
        end
    endfunction
    wire [31:0] wd = s_axil_wdata;
    wire [3:0]  ws = s_axil_wstrb;
    wire [5:0]  wa = s_axil_awaddr[7:2];
    wire        do_commit = wr && wa == 6'h01 && ws[0] && wd[3];
    wire        do_snap   = wr && wa == 6'h01 && ws[0] && wd[4];

    always @(posedge clk) begin
        load   <= 1'b0;
        resume <= 1'b0;
        flush  <= 1'b0;
        ctl_srst <= 1'b0;
        if (por) begin
            s_axil_bvalid <= 1'b0;
            ctl_enable <= 1'b0; keys_valid <= 1'b0; commit_late <= 1'b0; cfg_err <= 1'b0; cfg_code <= C_NONE;
            last_valid <= 1'b0; last_sid <= 64'd0; last_ctr <= 64'd0; p_valid <= 1'b0;
            s_mode <= 0; s_geom <= 0; s_tus <= 32'd1024; s_padmin <= 0; s_padcap <= 0; s_maxgap <= 32'd1000000;
            s_sid <= 0; s_ctr0 <= 0; s_at <= 0;
            s_ktag <= 0; s_kpol <= 0; s_kperm <= 0; s_kdum <= 0; s_kaead <= 0;
            a_level <= 0; a_ts <= 0; a_pad <= 0; a_policy <= 0; a_jump <= 0; a_W <= 0; a_H <= 0; a_T <= 16'd1024;
            a_sid <= 0; a_ctr0 <= 0; a_first <= 0; a_link <= 64'hFFFF_FFFF_FFFF_FFFF; a_maxgap <= 32'd1000000;
            a_padmin <= 0; a_padcap <= 0;
        end else begin
            if (s_axil_bvalid && s_axil_bready) s_axil_bvalid <= 1'b0;
            if (pkt_done) begin
                last_valid <= 1'b1;
                last_sid   <= a_sid;
                last_ctr   <= pkt_done_ctr;
            end
            if (wr) begin
                s_axil_bvalid <= 1'b1;
                case (wa)
                6'h01: if (ws[0]) begin
                    ctl_enable <= wd[0];
                    if (wd[1]) begin ctl_srst <= 1'b1; keys_valid <= 1'b0; p_valid <= 1'b0; ctl_enable <= 1'b0; end
                    if (wd[2]) flush <= 1'b1;
                end
                6'h03: s_mode   <= merge(s_mode, wd, ws);
                6'h04: s_geom   <= merge(s_geom, wd, ws);
                6'h05: s_tus    <= merge(s_tus, wd, ws);
                6'h06: s_sid[31:0]   <= merge(s_sid[31:0], wd, ws);
                6'h07: s_sid[63:32]  <= merge(s_sid[63:32], wd, ws);
                6'h08: s_ctr0[31:0]  <= merge(s_ctr0[31:0], wd, ws);
                6'h09: s_ctr0[63:32] <= merge(s_ctr0[63:32], wd, ws) & 32'h7FFF_FFFF;
                6'h0A: s_padmin <= merge(s_padmin, wd, ws);
                6'h0B: s_padcap <= merge(s_padcap, wd, ws);
                6'h0C: s_maxgap <= merge(s_maxgap, wd, ws);
                6'h0D: s_at[31:0]  <= merge(s_at[31:0], wd, ws);
                6'h0E: s_at[63:32] <= merge(s_at[63:32], wd, ws);
                6'h10: s_ktag[31:0]    <= wd;  6'h11: s_ktag[63:32]   <= wd;
                6'h12: s_ktag[95:64]   <= wd;  6'h13: s_ktag[127:96]  <= wd;
                6'h14: s_kpol[31:0]    <= wd;  6'h15: s_kpol[63:32]   <= wd;
                6'h16: s_kpol[95:64]   <= wd;  6'h17: s_kpol[127:96]  <= wd;
                6'h18: s_kperm[31:0]   <= wd;  6'h19: s_kperm[63:32]  <= wd;
                6'h1A: s_kperm[95:64]  <= wd;  6'h1B: s_kperm[127:96] <= wd;
                6'h1C: s_kdum[31:0]    <= wd;  6'h1D: s_kdum[63:32]   <= wd;
                6'h1E: s_kdum[95:64]   <= wd;  6'h1F: s_kdum[127:96]  <= wd;
                6'h20: s_kaead[31:0]   <= wd;  6'h21: s_kaead[63:32]  <= wd;
                6'h22: s_kaead[95:64]  <= wd;  6'h23: s_kaead[127:96] <= wd;
                default: ;
                endcase
            end
            // -------------------------------------------- commit
            if (do_commit) begin
                if (code != C_NONE) begin
                    cfg_code <= code;
                    cfg_err  <= 1'b1;
                    if (code == C_LATE) commit_late <= 1'b1;
                end else begin
                    cfg_code    <= C_NONE;
                    commit_late <= 1'b0;
                    keys_valid  <= 1'b1;
                    if (!ctl_enable || halted) begin
                        take_shadow;
                        a_ctr0  <= s_ctr0;
                        a_first <= 1'b1;
                        a_link  <= 64'hFFFF_FFFF_FFFF_FFFF;
                        if (!ctl_enable) load <= 1'b1;
                        else             resume <= 1'b1;
                    end else begin
                        q_mode <= s_mode; q_geom <= s_geom; q_tus <= s_tus; q_padmin <= s_padmin;
                        q_padcap <= s_padcap; q_maxgap <= s_maxgap; q_sid <= s_sid;
                        q_ktag <= s_ktag; q_kpol <= s_kpol; q_kperm <= s_kperm; q_kdum <= s_kdum; q_kaead <= s_kaead;
                        p_ctr0  <= s_ctr0;
                        p_at    <= s_at;
                        p_valid <= 1'b1;
                    end
                end
            end
            if (apply && p_valid) begin
                a_level <= q_mode[2:0]; a_ts <= q_mode[6:4]; a_pad <= q_mode[8]; a_policy <= q_mode[10:9];
                a_jump <= q_mode[12]; a_W <= q_geom[10:0]; a_H <= q_geom[26:16]; a_T <= q_tus[15:0];
                a_padmin <= q_padmin; a_padcap <= q_padcap; a_maxgap <= q_maxgap;
                k_tag <= q_ktag; k_pol <= q_kpol; k_perm <= q_kperm; k_dum <= q_kdum; k_aead <= q_kaead;
                if (q_sid != a_sid) begin
                    a_sid   <= q_sid;
                    a_ctr0  <= p_ctr0;
                    a_first <= 1'b1;
                    a_link  <= (q_sid[63:16] == a_sid[63:16]) ? apply_ctr : 64'hFFFF_FFFF_FFFF_FFFF;
                end
                p_valid <= 1'b0;
            end
        end
    end

    task take_shadow;
        begin
            a_level <= s_mode[2:0]; a_ts <= s_mode[6:4]; a_pad <= s_mode[8]; a_policy <= s_mode[10:9];
            a_jump <= s_mode[12]; a_W <= s_geom[10:0]; a_H <= s_geom[26:16]; a_T <= s_tus[15:0];
            a_padmin <= s_padmin; a_padcap <= s_padcap; a_maxgap <= s_maxgap; a_sid <= s_sid;
            k_tag <= s_ktag; k_pol <= s_kpol; k_perm <= s_kperm; k_dum <= s_kdum; k_aead <= s_kaead;
        end
    endtask

    // ------------------------------------------------------------ counters
    always @(posedge clk) begin
        if (por || ctl_srst) begin
            c_pkts <= 0; c_win <= 0; c_wout <= 0; c_cyc <= 0;
            c_iw <= 0; c_os <= 0; c_tw <= 0; c_kw <= 0; c_rng <= 0; c_ord <= 0; c_pre <= 0; c_jmp <= 0; c_ovf <= 0;
            c_cfg <= 0;
        end else begin
            if (do_commit && code != C_NONE) c_cfg <= sat(c_cfg, 1'b1);
            if (enable) begin
                c_cyc  <= c_cyc + 64'd1;
                c_pkts <= c_pkts + (ev_pkt ? 64'd1 : 64'd0);
                c_win  <= c_win  + (ev_word_in ? 64'd1 : 64'd0);
                c_wout <= c_wout + (ev_word_out ? 64'd1 : 64'd0);
                c_iw  <= sat(c_iw, ev_in_wait);    c_os  <= sat(c_os, ev_out_stall);
                c_tw  <= sat(c_tw, ev_table_wait); c_kw  <= sat(c_kw, ev_ks_wait);
                c_rng <= sat(c_rng, ev_range);     c_ord <= sat(c_ord, ev_order);
                c_pre <= sat(c_pre, ev_pre);       c_jmp <= sat(c_jmp, ev_jump);
                c_ovf <= sat(c_ovf, ev_padovf);
            end
        end
        if (do_snap) begin
            r_pkts <= c_pkts; r_win <= c_win; r_wout <= c_wout; r_cyc <= c_cyc;
            r_iw <= c_iw; r_os <= c_os; r_tw <= c_tw; r_kw <= c_kw; r_rng <= c_rng; r_ord <= c_ord;
            r_pre <= c_pre; r_jmp <= c_jmp; r_ovf <= c_ovf; r_cfg <= c_cfg;
        end
    end

    // ------------------------------------------------------------ read
    reg [31:0] rd;
    always @* begin
        case (s_axil_araddr[7:2])
        6'h00: rd = {8'h4E, 8'h56, 8'h01, BUILD};
        6'h01: rd = {31'd0, ctl_enable};
        6'h02: rd = {24'd0, cfg_err, halted, commit_late, keys_valid, open_packet, table_ready, p_valid, busy};
        6'h03: rd = s_mode;      6'h04: rd = s_geom;      6'h05: rd = s_tus;
        6'h06: rd = s_sid[31:0]; 6'h07: rd = s_sid[63:32];
        6'h08: rd = s_ctr0[31:0]; 6'h09: rd = s_ctr0[63:32];
        6'h0A: rd = s_padmin;    6'h0B: rd = s_padcap;    6'h0C: rd = s_maxgap;
        6'h0D: rd = s_at[31:0];  6'h0E: rd = s_at[63:32];
        6'h0F: rd = {29'd0, cfg_code};
        6'h24: rd = open_ctr[31:0]; 6'h25: rd = open_ctr[63:32];
        6'h26: rd = last_sid[31:0]; 6'h27: rd = last_sid[63:32];
        6'h28: rd = last_ctr[31:0]; 6'h29: rd = last_ctr[63:32];
        6'h2A: rd = r_pkts[31:0];   6'h2B: rd = r_pkts[63:32];
        6'h2C: rd = r_win[31:0];    6'h2D: rd = r_win[63:32];
        6'h2E: rd = r_wout[31:0];   6'h2F: rd = r_wout[63:32];
        6'h30: rd = r_cyc[31:0];    6'h31: rd = r_cyc[63:32];
        6'h32: rd = r_iw;  6'h33: rd = r_os;  6'h34: rd = r_tw;  6'h35: rd = r_kw;
        6'h36: rd = r_rng; 6'h37: rd = r_ord; 6'h38: rd = r_pre; 6'h39: rd = r_jmp;
        6'h3A: rd = r_ovf; 6'h3B: rd = r_cfg;
        default: rd = 32'd0;
        endcase
    end
    always @(posedge clk) begin
        if (por) s_axil_rvalid <= 1'b0;
        else begin
            if (s_axil_rvalid && s_axil_rready) s_axil_rvalid <= 1'b0;
            if (s_axil_arvalid && !s_axil_rvalid) begin
                s_axil_rvalid <= 1'b1;
                s_axil_rdata  <= rd;
            end
        end
    end
endmodule
`default_nettype wire
