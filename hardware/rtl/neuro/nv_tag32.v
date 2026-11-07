// nv_tag32: per-packet tag (V0-V3) or AEAD encryption (V4) over the ordered 32-bit word stream (DESIGN §3.3, §6.2).
// Golden model: software/model/ascon.py :: mac() (MAC), encrypt() (ENC);
//               block sequence software/neuro/hw.py :: tag_blocks()
//
// Input: one packet = 12 header words (kind 0), then payload and trailer words (kind 1, 2), `last` on the last
// trailer word. The header words are kept in a 12-word buffer: sid (words 2-3), ctr (words 4-5) and the level
// (word 1, byte 1) are read from it, so the per-packet nonce travels in-band. The key comes from the active
// register set, which is constant while packets are in flight (nv_packetizer drains the pipeline before a
// commit changes it).
//     level 0-3 (MAC): key K_tag, nonce (sid, ctr, 1), AD = header || payload || trailer, empty final PT block
//     level 4   (ENC): key K_aead, nonce (sid, ctr, 0), AD = header, PT = payload || trailer
// The end of each type is known exactly (12 header words; `last`), so no look-ahead is needed: a type that ends
// on a full block is followed by an empty last block (the core needs blk_bytes < 16 on the last block).
// Output: the body words in order (header words and, at V0-V3, payload/trailer words as they are absorbed; at V4
// the ciphertext words), `o_last` on the last body word, and the tag, held until nv_out_mux acknowledges it.
// ENC backpressure: a PT block is sent only when the ciphertext buffer is empty (ct_valid has no ready).
`default_nettype none
module nv_tag32 #(
    parameter U = 1
) (
    input  wire         clk,
    input  wire         rst,
    input  wire [127:0] key_tag,
    input  wire [127:0] key_aead,
    // ordered word stream (from nv_word_fifo)
    input  wire         in_valid,
    output reg          in_ready,
    input  wire [31:0]  in_word,
    input  wire         in_last,
    // body words out (to nv_out_mux)
    output reg          o_valid,
    input  wire         o_ready,
    output reg  [31:0]  o_word,
    output reg          o_last,
    // tag out
    output reg          t_valid,
    output reg  [127:0] t_data,
    input  wire         t_ack,
    output wire         busy,
    output wire         blk_wait          // a block is offered and the core is not ready (tag-bound clocks)
);
    localparam S_HDR = 4'd0, S_INIT = 4'd1, S_HB = 4'd2, S_ADE = 4'd3, S_COL = 4'd4, S_SEND = 4'd5,
               S_E = 4'd6, S_FIN = 4'd7, S_CT = 4'd8, S_CTD = 4'd9, S_TAG = 4'd10;

    reg  [3:0]   st;
    reg  [31:0]  hbuf [0:11];
    reg  [3:0]   hi;
    reg  [1:0]   hb;
    reg          enc;
    reg  [31:0]  cbuf [0:3];
    reg  [2:0]   n;              // words collected in cbuf
    reg  [2:0]   cnt;            // words in the block being sent
    reg          lastflag;       // the block being sent holds the last body word
    reg  [127:0] ctbuf;
    reg  [1:0]   cc;
    reg          tag_got;
    reg  [127:0] tag_r;

    // core
    reg          c_init;
    reg  [127:0] c_key, c_nonce;
    reg          c_valid;
    reg  [127:0] c_data;
    reg  [4:0]   c_bytes;
    reg          c_type, c_last;
    wire         c_ready, ct_valid, tag_valid;
    wire [127:0] ct_data, tag;
    nv_ascon_core_u #(.U(U)) u_core (
        .clk(clk), .rst(rst), .init(c_init), .key(c_key), .nonce(c_nonce),
        .blk_valid(c_valid), .blk_ready(c_ready), .blk_data(c_data), .blk_bytes(c_bytes),
        .blk_type(c_type), .blk_last(c_last), .ct_valid(ct_valid), .ct_data(ct_data),
        .tag_valid(tag_valid), .tag(tag));
    wire c_fire = c_valid && c_ready;
    assign blk_wait = c_valid && !c_ready;

    wire o_free = !o_valid || o_ready;
    wire in_fire = in_valid && in_ready;

    // header fields (header bytes are big-endian; AXI word = 4 bytes little-endian)
    function [31:0] bswap(input [31:0] v);
        bswap = {v[7:0], v[15:8], v[23:16], v[31:24]};
    endfunction
    wire [63:0] h_sid   = {bswap(hbuf[2]), bswap(hbuf[3])};
    wire [63:0] h_ctr   = {bswap(hbuf[4]), bswap(hbuf[5])};
    wire [7:0]  h_level = hbuf[1][15:8];

    // combinational: input ready, core block
    always @* begin
        in_ready = 1'b0;
        c_valid  = 1'b0;
        c_data   = {cbuf[3], cbuf[2], cbuf[1], cbuf[0]};
        c_bytes  = 5'd16;
        c_type   = 1'b0;
        c_last   = 1'b0;
        case (st)
        S_HDR: in_ready = o_free;
        S_HB: begin
            c_valid = 1'b1;
            c_data  = {hbuf[4*hb + 3], hbuf[4*hb + 2], hbuf[4*hb + 1], hbuf[4*hb]};
        end
        S_ADE: begin c_valid = 1'b1; c_bytes = 5'd0; c_last = 1'b1; end
        S_COL: in_ready = (n < 3'd4) && (enc || o_free);
        S_SEND: begin
            c_valid = 1'b1;
            c_type  = enc;
            c_last  = lastflag && (cnt < 3'd4);
            c_bytes = c_last ? {cnt, 2'b00} : 5'd16;
        end
        S_E:   begin c_valid = 1'b1; c_type = enc; c_bytes = 5'd0; c_last = 1'b1; end
        S_FIN: begin c_valid = 1'b1; c_type = 1'b1; c_bytes = 5'd0; c_last = 1'b1; end
        default: ;
        endcase
    end

    assign busy = (st != S_HDR) || (hi != 4'd0) || o_valid || t_valid;

    always @(posedge clk) begin
        c_init <= 1'b0;
        if (o_valid && o_ready) o_valid <= 1'b0;
        if (tag_valid) begin
            tag_r   <= tag;
            tag_got <= 1'b1;
        end
        if (rst) begin
            st      <= S_HDR;
            hi      <= 4'd0;
            o_valid <= 1'b0;
            t_valid <= 1'b0;
            tag_got <= 1'b0;
            n       <= 3'd0;
        end else begin
            case (st)
            S_HDR: if (in_fire) begin
                hbuf[hi] <= in_word;
                o_valid  <= 1'b1;
                o_word   <= in_word;
                o_last   <= 1'b0;
                hi       <= hi + 4'd1;
                if (hi == 4'd11) st <= S_INIT;
            end
            S_INIT: begin
                enc     <= (h_level == 8'd4);
                c_key   <= (h_level == 8'd4) ? key_aead : key_tag;
                c_nonce <= {h_ctr[62:0], (h_level != 8'd4), h_sid};
                c_init  <= 1'b1;
                hb      <= 2'd0;
                n       <= 3'd0;
                st      <= S_HB;
            end
            S_HB: if (c_fire) begin
                hb <= hb + 2'd1;
                if (hb == 2'd2) st <= enc ? S_ADE : S_COL;
            end
            S_ADE: if (c_fire) st <= S_COL;
            S_COL: if (in_fire) begin
                cbuf[n[1:0]] <= in_word;
                n <= n + 3'd1;
                if (!enc) begin
                    o_valid <= 1'b1;
                    o_word  <= in_word;
                    o_last  <= in_last;
                end
                if (in_last || n == 3'd3) begin
                    cnt      <= n + 3'd1;
                    lastflag <= in_last;
                    st       <= S_SEND;
                end
            end
            S_SEND: if (c_fire) begin
                n <= 3'd0;
                if (enc)               st <= S_CT;
                else if (!lastflag)    st <= S_COL;
                else if (cnt == 3'd4)  st <= S_E;
                else                   st <= S_FIN;
                // zero the unused words of a partial block (the core masks them anyway)
            end
            S_E: if (c_fire) st <= enc ? S_TAG : S_FIN;
            S_FIN: if (c_fire) st <= S_TAG;
            S_CT: if (ct_valid) begin
                ctbuf <= ct_data;
                cc    <= 2'd0;
                st    <= S_CTD;
            end
            S_CTD: if (o_free) begin
                o_valid <= 1'b1;
                o_word  <= ctbuf[32*cc +: 32];
                o_last  <= lastflag && ({1'b0, cc} == cnt - 3'd1);
                cc      <= cc + 2'd1;
                if ({1'b0, cc} == cnt - 3'd1) begin
                    if (!lastflag)        st <= S_COL;
                    else if (cnt == 3'd4) st <= S_E;
                    else                  st <= S_TAG;
                end
            end
            S_TAG: if (tag_got && !t_valid) begin
                t_valid <= 1'b1;
                t_data  <= tag_r;
                tag_got <= 1'b0;
                hi      <= 4'd0;
                st      <= S_HDR;
            end
            default: st <= S_HDR;
            endcase
            if (t_valid && t_ack) t_valid <= 1'b0;
        end
    end
endmodule
`default_nettype wire
