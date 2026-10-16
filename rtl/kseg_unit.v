// kseg_unit.v -- contract v3: per-frame segment key
//   K_seg = Ascon-AEAD128(K, N_enc, AD = "lanes", P = empty).tag
// computed once at frame start (init p12, one AD block p8, final p12: about 35 clocks).
// Every lane then keys its segment keystreams with K_seg and the nonce (segment index, frame_ctr).
// Why a derived key: in contract v2 the whole frame used ONE keystream, so the bits a segment
// consumed depended on every earlier segment and lanes could not encrypt on their own. With K_seg
// each segment's keystream starts fresh and is seekable by segment index; K_seg is unique per
// (key, session, frame), so no (key, nonce) pair is ever reused.
// Golden model: model/hw.py :: segment_key()  (= model/jpeg.py :: segment_key)
`default_nettype none
module kseg_unit (
    input  wire         clk,
    input  wire         rst,
    input  wire         start,
    input  wire [127:0] key,
    input  wire [127:0] nonce,           // N_enc of the frame
    output reg          kseg_valid,      // stays high until the next start
    output reg  [127:0] kseg
);
    localparam S_IDLE = 2'd0, S_AD = 2'd1, S_PT = 2'd2, S_WAIT = 2'd3;
    reg [1:0] state;
    reg       pend, p_type;
    wire      blk_ready, ct_valid_unused, tag_valid;
    wire [127:0] ct_unused, tag;

    // "lanes" as AD bytes 0..4 (byte i = bits 8i+7:8i)
    localparam [127:0] AD = {88'd0, 8'h73, 8'h65, 8'h6E, 8'h61, 8'h6C};

    ascon_aead128_core u_core (
        .clk(clk), .rst(rst), .init(start), .key(key), .nonce(nonce),
        .blk_valid(pend), .blk_ready(blk_ready),
        .blk_data(p_type ? 128'd0 : AD), .blk_bytes(p_type ? 5'd0 : 5'd5),
        .blk_type(p_type), .blk_last(1'b1),
        .ct_valid(ct_valid_unused), .ct_data(ct_unused),
        .tag_valid(tag_valid), .tag(tag));

    always @(posedge clk) begin
        if (rst) begin
            state <= S_IDLE; pend <= 1'b0; kseg_valid <= 1'b0;
        end else if (start) begin
            state <= S_AD; pend <= 1'b1; p_type <= 1'b0; kseg_valid <= 1'b0;
        end else begin
            case (state)
            S_AD: if (pend && blk_ready) begin               // AD "lanes" accepted
                p_type <= 1'b1; state <= S_PT;
            end
            S_PT: if (pend && blk_ready) begin               // empty plaintext -> finalise
                pend <= 1'b0; state <= S_WAIT;
            end
            S_WAIT: if (tag_valid) begin
                kseg <= tag; kseg_valid <= 1'b1; state <= S_IDLE;
            end
            default: ;
            endcase
        end
    end
endmodule
`default_nettype wire
