// nv_trailer: counts the payload, inserts padding dummies, records the masked bitmap and emits the trailer (DESIGN §3.3, §5).
// Golden model: software/neuro/pad.py :: pad_packet(), dummy_word(), bucket_target();
//               software/neuro/packet.py :: Trailer.pack()
//
// Input: 12 header words (kind 0), payload words (kind 1), one EOP marker (kind 3) from nv_packetizer.
// Output: header and payload words (with dummies), then the trailer words (kind 2): the masked bitmap (only with
// PAD), n_words, n_cd, rsvd (big-endian fields), `last` on rsvd.
// The packet's parameters are read from its own header (in-band): PAD flag, pad_policy, ts, sid, ctr, t_start,
// W, H, T_us. PAD_MIN, PAD_CAP and K_dum come from the active register set (constant while packets are in flight).
// With PAD (parameter PAD = 1 builds the logic; the header flag enables it per packet), per 64 µs bucket:
//   every bucket gets a TIME_HIGH (inserted if absent); after its real words, `target - n_real` dummies, with
//   target = max(n_real, PAD_MIN) (floor) or the smallest PAD_MIN * 2^k >= n_real, n_real above PAD_CAP unpadded
//   (ladder). One K_dum keystream (nonce sid, ctr, 0) per packet, consumed in payload order: 1 mask bit per CD word;
//   a dummy then takes x: 16, y: 16, p: 1, ts: 6 bits (taken 8 + 8, 8 + 8, 7); x = (r16 W) >> 16, y = (r16 H) >> 16.
//   Bitmap bit i = d_i XOR m_i; after the last CD word the mask bits of the zero padding up to a multiple of 32.
//   MAX_CD CD words per packet; further real CD words are dropped (ERR_PADOVF) and no dummy is added.
`default_nettype none
module nv_trailer #(
    parameter PAD    = 1,
    parameter MAX_CD = 131072,          // multiple of 32
    parameter BM_AW  = 12               // log2(MAX_CD / 32), at least 1
) (
    input  wire         clk,
    input  wire         rst,
    input  wire [31:0]  pad_min,
    input  wire [31:0]  pad_cap,
    input  wire [127:0] key_dum,
    input  wire         i_valid,
    output reg          i_ready,
    input  wire [31:0]  i_word,
    input  wire [1:0]   i_kind,
    input  wire         i_xor,
    input  wire         i_perm,
    input  wire         i_bank,
    output reg          o_valid,
    input  wire         o_ready,
    output reg  [31:0]  o_word,
    output reg  [1:0]   o_kind,
    output reg          o_last,
    output reg          o_xor,
    output reg          o_perm,
    output reg          o_bank,
    output reg          e_padovf,
    output wire         busy
);
    localparam T_HDR = 4'd0, T_PAY = 4'd1, T_CLOSEB = 4'd2, T_TGT = 4'd3, T_DUM = 4'd4, T_NEXTB = 4'd5,
               T_PADB = 4'd6, T_BMRD = 4'd7, T_BMEM = 4'd8, T_FIX = 4'd9;

    reg  [3:0]   st;
    reg  [3:0]   hi;
    // header fields of the current packet
    reg          pad_on;
    reg  [1:0]   policy;
    reg  [63:0]  sid, ctr;
    reg  [33:0]  t_start;
    reg  [10:0]  W, H;
    reg  [15:0]  T_us;
    // counts
    reg  [31:0]  n_words, n_cd;
    reg  [1:0]   fi;                    // fixed trailer word index
    // buckets
    reg          bopen;
    reg  [9:0]   cur_b;
    reg  [10:0]  tj;                    // first bucket that must not be closed (target of the walk)
    reg          eop_walk;              // the walk ends the packet (EOP) rather than meeting a TIME_HIGH
    reg  [31:0]  n_real;
    reg  [32:0]  tgt;
    reg  [32:0]  ndum;
    // dummy sub-steps
    reg  [2:0]   ds;
    reg          dm;                    // mask bit of the dummy
    reg  [7:0]   xlo, ylo;
    reg  [15:0]  xr, yr;
    // bitmap
    reg  [31:0]  bm_acc;
    reg  [4:0]   bm_n;
    reg  [BM_AW:0]   bm_w, bm_r;         // one bit wider than the RAM address: MAX_CD/32 words fit
    reg          bm_we;
    reg  [31:0]  bm_wd;
    reg  [BM_AW-1:0] bm_wa;
    wire [31:0]  bm_rd;

    function [31:0] bswap(input [31:0] v);
        bswap = {v[7:0], v[15:8], v[23:16], v[31:24]};
    endfunction

    // K_dum keystream
    reg          k_start;
    reg  [4:0]   kn;
    wire [15:0]  ks_bits;
    wire [4:0]   ks_avail;
    wire         ks_take;
    generate if (PAD) begin : g_pad
        keystream_gen ksg (
            .clk(clk), .rst(rst), .start(k_start), .key(key_dum), .nonce({ctr[62:0], 1'b0, sid}),
            .ks_bits(ks_bits), .ks_avail(ks_avail), .ks_take(ks_take), .ks_n(kn));
        nv_sdp_ram #(.DEPTH(MAX_CD / 32), .AW(BM_AW), .WIDTH(32)) bm_ram (
            .clk(clk), .we(bm_we), .waddr(bm_wa), .wdata(bm_wd), .raddr(bm_r[BM_AW-1:0]), .rdata(bm_rd));
    end else begin : g_nopad
        assign ks_bits = 16'd0;
        assign ks_avail = 5'd0;
        assign bm_rd = 32'd0;
    end endgenerate

    wire        o_free  = !o_valid || o_ready;
    wire [3:0]  typ     = i_word[31:28];
    wire        is_th   = (typ == 4'h8);
    wire        is_cd   = (typ[3:1] == 3'b000);
    wire [27:0] th0     = t_start[33:6];
    wire [27:0] jb      = i_word[27:0] - th0;
    wire [10:0] nb      = T_us[15:6];
    wire        cd_full = (n_cd >= MAX_CD);
    wire        ks1     = (ks_avail >= 5'd1);

    // keystream take: real CD word (1 bit), dummy sub-steps (1, 8, 8, 8, 8, 7), padding mask bits (1)
    wire take_real = (st == T_PAY) && pad_on && i_valid && i_kind == 2'd1 && is_cd && !cd_full && ks1 && o_free;
    wire take_dum  = (st == T_DUM) && (ndum != 0) && !cd_full && (ds != 3'd6) && (ks_avail >= kn);
    wire take_pad  = (st == T_PADB) && (bm_n != 5'd0) && ks1;
    assign ks_take = take_real || take_dum || take_pad;
    always @* begin
        case (ds)
            3'd1, 3'd2, 3'd3, 3'd4: kn = 5'd8;
            3'd5:                   kn = 5'd7;
            default:                kn = 5'd1;
        endcase
        if (st != T_DUM) kn = 5'd1;
    end

    // dummy word from the drawn bits
    wire [26:0] xp = xr * W;
    wire [26:0] yp = yr * H;
    reg  [6:0]  pts;
    wire [31:0] dummy = {3'b000, pts[0], pts[6:1], xp[26:16], yp[26:16]};

    // input acceptance
    always @* begin
        i_ready = 1'b0;
        case (st)
        T_HDR: i_ready = o_free;
        T_PAY:
            if (i_kind == 2'd3)                       i_ready = 1'b1;
            else if (!pad_on)                         i_ready = o_free;
            else if (is_th)                           i_ready = bopen && (jb == {18'd0, cur_b}) && o_free;
            else if (is_cd)                           i_ready = cd_full || take_real;
            else                                      i_ready = o_free;
        default: ;
        endcase
    end
    wire i_fire = i_valid && i_ready;

    assign busy = (st != T_HDR) || (hi != 4'd0) || o_valid;

    // push one bitmap bit (bit position = bm_n)
    task push_bit(input b);
        begin
            if (bm_n == 5'd31) begin
                bm_we  <= 1'b1;
                bm_wa  <= bm_w[BM_AW-1:0];
                bm_wd  <= {b, bm_acc[30:0]};
                bm_w   <= bm_w + 1'b1;
                bm_n   <= 5'd0;
                bm_acc <= 32'd0;
            end else begin
                bm_acc[bm_n] <= b;
                bm_n <= bm_n + 5'd1;
            end
        end
    endtask

    task emit(input [31:0] w, input [1:0] k, input l, input x, input p);
        begin
            o_valid <= 1'b1;
            o_word  <= w;
            o_kind  <= k;
            o_last  <= l;
            o_xor   <= x;
            o_perm  <= p;
        end
    endtask

    always @(posedge clk) begin
        k_start  <= 1'b0;
        e_padovf <= 1'b0;
        bm_we    <= 1'b0;
        if (o_valid && o_ready) o_valid <= 1'b0;
        if (rst) begin
            st <= T_HDR; hi <= 4'd0; o_valid <= 1'b0; pad_on <= 1'b0;
        end else begin
            case (st)
            T_HDR: if (i_fire) begin
                emit(i_word, 2'd0, 1'b0, 1'b0, 1'b0);
                case (hi)
                4'd1: begin pad_on <= (PAD != 0) && i_word[16]; end
                4'd2: sid[63:32] <= bswap(i_word);
                4'd3: sid[31:0]  <= bswap(i_word);
                4'd4: ctr[63:32] <= bswap(i_word);
                4'd5: ctr[31:0]  <= bswap(i_word);
                4'd6: t_start[33:32] <= bswap(i_word) & 32'h3;
                4'd7: t_start[31:0]  <= bswap(i_word);
                4'd8: begin W <= {i_word[2:0], i_word[15:8]}; H <= {i_word[18:16], i_word[31:24]}; end
                4'd9: begin T_us <= {i_word[7:0], i_word[15:8]}; policy <= i_word[25:24]; end
                default: ;
                endcase
                hi <= hi + 4'd1;
                if (hi == 4'd11) begin
                    hi <= 4'd0;
                    n_words <= 32'd0; n_cd <= 32'd0;
                    bopen <= 1'b0; cur_b <= 10'd0; n_real <= 32'd0;
                    bm_acc <= 32'd0; bm_n <= 5'd0; bm_w <= {(BM_AW+1){1'b0}};
                    k_start <= pad_on;
                    st <= T_PAY;
                end
            end
            T_PAY: if (i_fire) begin
                if (i_kind == 2'd3) begin
                    if (pad_on) begin
                        tj <= nb; eop_walk <= 1'b1;
                        st <= T_CLOSEB;
                    end else begin
                        fi <= 2'd0;
                        st <= T_FIX;
                    end
                end else if (pad_on && is_cd && cd_full) begin
                    e_padovf <= 1'b1;                       // dropped, no output
                end else begin
                    emit(i_word, 2'd1, 1'b0, i_xor, i_perm);
                    o_bank  <= i_bank;
                    n_words <= n_words + 32'd1;
                    if (is_cd) begin
                        n_cd <= n_cd + 32'd1;
                        if (pad_on) begin
                            n_real <= n_real + 32'd1;
                            push_bit(ks_bits[0]);            // real word: d = 0, bit = mask
                        end
                    end
                end
            end else if (pad_on && i_valid && i_kind == 2'd1 && is_th && !(bopen && jb == {18'd0, cur_b})) begin
                tj <= jb[10:0]; eop_walk <= 1'b0;          // walk to this TIME_HIGH's bucket
                st <= T_CLOSEB;
            end
            // ---------------------------------------------------- bucket walk
            T_CLOSEB: begin
                if (bopen) begin
                    tgt <= (policy == 2'd2 && n_real > pad_cap) ? {1'b0, n_real} : {1'b0, pad_min};
                    st  <= T_TGT;
                end else
                    st  <= T_NEXTB;
            end
            T_TGT: begin
                if (policy == 2'd2) begin
                    if (tgt < {1'b0, n_real}) tgt <= tgt << 1;
                    else begin ndum <= tgt - {1'b0, n_real}; ds <= 3'd0; st <= T_DUM; end
                end else begin
                    ndum <= (n_real > pad_min) ? 33'd0 : ({1'b0, pad_min} - {1'b0, n_real});
                    ds <= 3'd0;
                    st <= T_DUM;
                end
            end
            T_DUM: begin
                if (ndum == 0 || cd_full) st <= T_NEXTB;
                else if (ds == 3'd6) begin
                    if (o_free) begin
                        emit(dummy, 2'd1, 1'b0, 1'b0, 1'b0);
                        push_bit(~dm);
                        n_cd    <= n_cd + 32'd1;
                        n_words <= n_words + 32'd1;
                        ndum    <= ndum - 33'd1;
                        ds      <= 3'd0;
                    end
                end else if (take_dum) begin
                    case (ds)
                    3'd0: dm  <= ks_bits[0];
                    3'd1: xlo <= ks_bits[7:0];
                    3'd2: xr  <= {ks_bits[7:0], xlo};
                    3'd3: ylo <= ks_bits[7:0];
                    3'd4: yr  <= {ks_bits[7:0], ylo};
                    3'd5: pts <= ks_bits[6:0];
                    default: ;
                    endcase
                    ds <= ds + 3'd1;
                end
            end
            T_NEXTB: begin
                // next bucket: cur_b + 1 if one is open, else 0
                if ((bopen ? {1'b0, cur_b} + 11'd1 : 11'd0) < tj) begin
                    if (o_free) begin
                        emit({4'h8, th0 + (bopen ? {18'd0, cur_b} + 28'd1 : 28'd0)}, 2'd1, 1'b0, 1'b0, 1'b0);
                        n_words <= n_words + 32'd1;
                        cur_b   <= bopen ? cur_b + 10'd1 : 10'd0;
                        bopen   <= 1'b1;
                        n_real  <= 32'd0;
                        st      <= T_CLOSEB;
                    end
                end else if (eop_walk) begin
                    st <= T_PADB;
                end else begin
                    cur_b  <= tj[9:0];
                    bopen  <= 1'b1;
                    n_real <= 32'd0;
                    st     <= T_PAY;              // the TIME_HIGH now passes (same bucket)
                end
            end
            T_PADB: begin
                if (bm_n == 5'd0) begin
                    bm_r <= {(BM_AW+1){1'b0}};
                    st   <= (bm_w == 0) ? T_FIX : T_BMRD;
                    fi   <= 2'd0;
                end else if (take_pad)
                    push_bit(ks_bits[0]);
            end
            T_BMRD: st <= T_BMEM;                  // RAM read latency
            T_BMEM: if (o_free) begin
                emit(bm_rd, 2'd2, 1'b0, 1'b0, 1'b0);
                bm_r <= bm_r + 1'b1;
                st   <= (bm_r + 1'b1 == bm_w) ? T_FIX : T_BMRD;
            end
            T_FIX: if (o_free) begin
                case (fi)
                2'd0: emit(bswap(n_words), 2'd2, 1'b0, 1'b0, 1'b0);
                2'd1: emit(bswap(n_cd),    2'd2, 1'b0, 1'b0, 1'b0);
                default: emit(32'd0,       2'd2, 1'b1, 1'b0, 1'b0);
                endcase
                fi <= fi + 2'd1;
                if (fi == 2'd2) st <= T_HDR;
            end
            default: st <= T_HDR;
            endcase
        end
    end
endmodule
`default_nettype wire
