// tag_unit.v -- per-frame tag (contract v2):
//   Ascon-AEAD128(K, N_mac, AD = prefix (26 bytes) || scan bytes, P = empty).
// The 26-byte prefix is the APP11 metadata + frame size ('SJV1', version, mode,
// session_id BE, frame_ctr BE, width BE, height BE); it is latched at `start`
// and absorbed first, so the mode, counter, session and size are authenticated
// (contract v1 tagged the scan only, so an attacker could change the mode byte).
// Byte i of the prefix = ad_prefix[8i+7:8i]. Scan bytes (after 0xFF stuffing)
// then stream in one per handshake; ad_last marks the final byte of the frame.
// tag_valid stays high until the next start.
// Golden model: model/hw.py :: frame_tag()  (= model/jpeg.py tag)
`default_nettype none
module tag_unit #(
    parameter PREFIX_BYTES = 26          // 1..63
) (
    input  wire         clk,
    input  wire         rst,
    input  wire         start,
    input  wire [127:0] key,
    input  wire [127:0] nonce,
    input  wire [8*PREFIX_BYTES-1:0] ad_prefix,
    input  wire         ad_valid,
    output wire         ad_ready,
    input  wire [7:0]   ad_data,
    input  wire         ad_last,
    output reg          tag_valid,
    output reg  [127:0] tag
);
    localparam S_IDLE = 3'd0, S_COLLECT = 3'd1, S_ADEMPTY = 3'd2, S_PT = 3'd3, S_WAIT = 3'd4,
               S_PREFIX = 3'd5;
    reg [2:0]   state;
    reg [8*PREFIX_BYTES-1:0] pref;   // prefix latched at start, shifted out byte 0 first
    reg [5:0]   pleft;               // prefix bytes still to absorb
    reg [127:0] buffer;
    reg [4:0]   cnt;          // bytes in buffer (0..15)

    // one pending block towards the core
    reg         pend;
    reg [127:0] p_data;
    reg [4:0]   p_bytes;
    reg         p_type, p_last;

    wire         blk_ready, ct_valid_unused, core_tag_valid;
    wire [127:0] ct_unused, core_tag;
    ascon_aead128_core u_core (
        .clk(clk), .rst(rst), .init(start), .key(key), .nonce(nonce),
        .blk_valid(pend), .blk_ready(blk_ready),
        .blk_data(p_data), .blk_bytes(p_bytes), .blk_type(p_type), .blk_last(p_last),
        .ct_valid(ct_valid_unused), .ct_data(ct_unused),
        .tag_valid(core_tag_valid), .tag(core_tag));

    // byte source: the latched prefix first (S_PREFIX), then the scan stream
    wire       in_pref = (state == S_PREFIX);
    assign ad_ready = (state == S_COLLECT) && !pend;
    wire       take = in_pref ? !pend : (ad_valid && ad_ready);
    wire [7:0] in_data = in_pref ? pref[7:0] : ad_data;
    wire       in_last = in_pref ? 1'b0 : ad_last;   // scan data always follows
    wire [4:0] cnt1 = cnt + 5'd1;

    // buffer with the incoming byte inserted at position cnt
    reg [127:0] buf_new;
    always @* begin
        buf_new = buffer;
        buf_new[8*cnt[3:0] +: 8] = in_data;
    end

    always @(posedge clk) begin
        if (rst) begin
            state <= S_IDLE; pend <= 1'b0; tag_valid <= 1'b0; cnt <= 5'd0;
        end else if (start) begin
            state <= S_PREFIX;
            pend <= 1'b0; tag_valid <= 1'b0; cnt <= 5'd0;
            buffer <= 128'd0; pref <= ad_prefix; pleft <= PREFIX_BYTES;
        end else begin
            if (pend && blk_ready) pend <= 1'b0;
            if (in_pref && take) begin
                pref <= pref >> 8;
                pleft <= pleft - 6'd1;
                if (pleft == 6'd1) state <= S_COLLECT;
            end
            case (state)
            S_PREFIX, S_COLLECT: if (take) begin
                if (cnt1 == 5'd16) begin                 // full block
                    pend <= 1'b1; p_data <= buf_new; p_bytes <= 5'd16;
                    p_type <= 1'b0; p_last <= 1'b0;
                    cnt <= 5'd0; buffer <= 128'd0;
                    if (in_last) state <= S_ADEMPTY;     // AD length multiple of 16
                end else begin
                    buffer <= buf_new; cnt <= cnt1;
                    if (in_last) begin                   // final partial AD block
                        pend <= 1'b1; p_data <= buf_new; p_bytes <= cnt1;
                        p_type <= 1'b0; p_last <= 1'b1;
                        state <= S_PT;
                    end
                end
            end
            S_ADEMPTY: if (!pend) begin
                pend <= 1'b1; p_data <= 128'd0; p_bytes <= 5'd0;
                p_type <= 1'b0; p_last <= 1'b1;
                state <= S_PT;
            end
            S_PT: if (!pend) begin                       // empty plaintext
                pend <= 1'b1; p_data <= 128'd0; p_bytes <= 5'd0;
                p_type <= 1'b1; p_last <= 1'b1;
                state <= S_WAIT;
            end
            S_WAIT: if (core_tag_valid) begin
                tag <= core_tag; tag_valid <= 1'b1; state <= S_IDLE;
            end
            default: ;
            endcase
        end
    end
endmodule
`default_nettype wire
