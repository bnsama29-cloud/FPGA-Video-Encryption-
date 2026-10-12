// tag_unit.v -- per-frame tag: Ascon-AEAD128(K, N_mac, AD = scan bytes, P = empty).
// Scan bytes (after 0xFF stuffing) stream in one per handshake; ad_last marks
// the final byte of the frame. tag_valid stays high until the next start.
// Golden model: model/ascon.py :: mac()
`default_nettype none
module tag_unit (
    input  wire         clk,
    input  wire         rst,
    input  wire         start,
    input  wire [127:0] key,
    input  wire [127:0] nonce,
    input  wire         ad_valid,
    output wire         ad_ready,
    input  wire [7:0]   ad_data,
    input  wire         ad_last,
    output reg          tag_valid,
    output reg  [127:0] tag
);
    localparam S_IDLE = 3'd0, S_COLLECT = 3'd1, S_ADEMPTY = 3'd2, S_PT = 3'd3, S_WAIT = 3'd4;
    reg [2:0]   state;
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

    assign ad_ready = (state == S_COLLECT) && !pend;
    wire       take = ad_valid && ad_ready;
    wire [4:0] cnt1 = cnt + 5'd1;

    // buffer with the incoming byte inserted at position cnt
    reg [127:0] buf_new;
    always @* begin
        buf_new = buffer;
        buf_new[8*cnt[3:0] +: 8] = ad_data;
    end

    always @(posedge clk) begin
        if (rst) begin
            state <= S_IDLE; pend <= 1'b0; tag_valid <= 1'b0; cnt <= 5'd0;
        end else if (start) begin
            state <= S_COLLECT; pend <= 1'b0; tag_valid <= 1'b0; cnt <= 5'd0;
            buffer <= 128'd0;
        end else begin
            if (pend && blk_ready) pend <= 1'b0;
            case (state)
            S_COLLECT: if (take) begin
                if (cnt1 == 5'd16) begin                 // full block
                    pend <= 1'b1; p_data <= buf_new; p_bytes <= 5'd16;
                    p_type <= 1'b0; p_last <= 1'b0;
                    cnt <= 5'd0; buffer <= 128'd0;
                    if (ad_last) state <= S_ADEMPTY;     // AD length multiple of 16
                end else begin
                    buffer <= buf_new; cnt <= cnt1;
                    if (ad_last) begin                   // final partial AD block
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
