// axis_tamper.v -- hardware tamper injector for the attack demonstration (board day, docs/BOARD_DAY.html).
//
// Sits between the encoder's scan stream (sjpeg/m_axis) and the receive DMA (S2MM) in the overlay
// secure_jpeg_lanes_tamper.bit, i.e. AFTER the frame tag has been computed inside the encoder. When
// triggered it flips one bit of the scan of a frame on its way to DDR, the ARM and the network.
// It models a fault or an implant on the path encoder -> DMA -> DDR -> ARM -> NIC: the receiver must
// reject exactly the tampered frames (tag mismatch) and accept every other one.
//
// Controls (PYNQ-Z2):  SW1 = enable (nothing is ever changed while SW1 is down)
//                      SW0 = continuous: every frame is tampered
//                      BTN0 or a rising edge on PMOD A pin 1 (JA1, 3.3 V only) = one shot: the next frame
//                      LED0 = enabled, LED1 = shot pending, LED2 = continuous, LED3 toggles per tampered frame
// Which bit: byte 0 of the first safe beat from a pseudo-random beat 1..15 of the frame on (or the
// last beat of a shorter frame), bit chosen by the same LFSR. Marker bytes are never touched (byte 0 = 0xFF, a flip
// that would make 0xFF, or a byte right after 0xFF): the frame keeps its JPEG structure, so the
// receiver's only way to notice is the Ascon tag. If no safe beat is left, the shot waits for the
// next frame (tampered_frames counts only frames that were changed).
// Everything else (valid, ready, last, keep, every other bit) passes through unchanged, combinationally.
// Golden model: none (test equipment, not part of the encoder); tb/test_axis_tamper.py checks it.
`default_nettype none
module axis_tamper (
    (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 clk CLK" *)
    (* X_INTERFACE_PARAMETER = "ASSOCIATED_BUSIF s_axis:m_axis, ASSOCIATED_RESET rst" *)
    input  wire        clk,
    (* X_INTERFACE_INFO = "xilinx.com:signal:reset:1.0 rst RST" *)
    (* X_INTERFACE_PARAMETER = "POLARITY ACTIVE_HIGH" *)
    input  wire        rst,

    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 s_axis TDATA" *)
    (* X_INTERFACE_PARAMETER = "TDATA_NUM_BYTES 4, HAS_TLAST 1, HAS_TKEEP 1" *)
    input  wire [31:0] s_axis_tdata,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 s_axis TKEEP" *)  input  wire [3:0]  s_axis_tkeep,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 s_axis TVALID" *) input  wire        s_axis_tvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 s_axis TREADY" *) output wire        s_axis_tready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 s_axis TLAST" *)  input  wire        s_axis_tlast,

    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 m_axis TDATA" *)
    (* X_INTERFACE_PARAMETER = "TDATA_NUM_BYTES 4, HAS_TLAST 1, HAS_TKEEP 1" *)
    output wire [31:0] m_axis_tdata,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 m_axis TKEEP" *)  output wire [3:0]  m_axis_tkeep,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 m_axis TVALID" *) output wire        m_axis_tvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 m_axis TREADY" *) input  wire        m_axis_tready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 m_axis TLAST" *)  output wire        m_axis_tlast,

    input  wire [3:0]  btn,             // PYNQ-Z2 push buttons (BTN0 used)
    input  wire [1:0]  sw,              // PYNQ-Z2 slide switches
    input  wire        pmod_trig,       // PMOD A pin 1: external trigger (e.g. a Raspberry Pi Pico)
    output wire [3:0]  led,
    output reg  [15:0] tampered_frames  // for the testbench (left open in the overlay)
);
    // ---- asynchronous inputs: two flip-flops each, then edge detection
    reg [1:0] s_btn, s_sw0, s_sw1, s_trg;
    reg       btn_d, trg_d;
    always @(posedge clk) begin
        s_btn <= {s_btn[0], btn[0]};
        s_sw0 <= {s_sw0[0], sw[0]};
        s_sw1 <= {s_sw1[0], sw[1]};
        s_trg <= {s_trg[0], pmod_trig};
        btn_d <= s_btn[1];
        trg_d <= s_trg[1];
    end
    wire en    = s_sw1[1];
    wire cont  = s_sw0[1];
    wire shot  = (s_btn[1] && !btn_d) || (s_trg[1] && !trg_d);   // a bouncing button just re-arms

    // ---- free-running LFSR (x^16 + x^14 + x^13 + x^11 + 1)
    reg [15:0] lfsr;
    always @(posedge clk)
        if (rst) lfsr <= 16'hACE1;
        else     lfsr <= {lfsr[14:0], lfsr[15] ^ lfsr[13] ^ lfsr[12] ^ lfsr[10]};

    // ---- frame tracking; the decision for a frame is taken while waiting for its first beat
    wire       hs = s_axis_tvalid && m_axis_tready;
    reg        sof;                     // next beat is the first of a frame
    reg  [6:0] beat;                    // beat index in the frame, saturates at 127
    reg        fire, applied, armed, prev_ff, blink;
    reg  [3:0] tgt;
    reg  [2:0] bsel;

    wire [7:0] b0      = s_axis_tdata[7:0];
    wire [7:0] mask    = 8'd1 << bsel;
    wire       safe    = (b0 != 8'hFF) && ((b0 ^ mask) != 8'hFF) && !(prev_ff && !sof);
    wire       hit     = fire && !applied && !sof && safe && (beat >= {3'b0, tgt} || s_axis_tlast);
    // the first beat of a frame is never a target (sof): the decision registers are still being loaded

    assign m_axis_tdata  = {s_axis_tdata[31:8], b0 ^ (hit ? mask : 8'd0)};
    assign m_axis_tkeep  = s_axis_tkeep;
    assign m_axis_tvalid = s_axis_tvalid;
    assign m_axis_tlast  = s_axis_tlast;
    assign s_axis_tready = m_axis_tready;

    always @(posedge clk) begin
        if (rst) begin
            sof <= 1'b1; beat <= 7'd0; fire <= 1'b0; applied <= 1'b0; armed <= 1'b0; prev_ff <= 1'b0;
            blink <= 1'b0; tgt <= 4'd1; bsel <= 3'd0; tampered_frames <= 16'd0;
        end else begin
            if (shot && en) armed <= 1'b1;
            if (sof && !hs) begin           // between frames: (re)decide for the coming frame
                fire    <= en && (armed || cont);
                tgt     <= (lfsr[3:0] == 4'd0) ? 4'd1 : lfsr[3:0];
                bsel    <= lfsr[8:6];
                applied <= 1'b0;
            end
            if (hs) begin
                prev_ff <= s_axis_tkeep[3] ? (s_axis_tdata[31:24] == 8'hFF) :
                           s_axis_tkeep[2] ? (s_axis_tdata[23:16] == 8'hFF) :
                           s_axis_tkeep[1] ? (s_axis_tdata[15:8]  == 8'hFF) : (b0 == 8'hFF);
                sof  <= s_axis_tlast;
                beat <= s_axis_tlast ? 7'd0 : (beat == 7'd127 ? beat : beat + 7'd1);
                if (hit) begin
                    applied <= 1'b1;
                    blink   <= ~blink;
                    tampered_frames <= tampered_frames + 16'd1;
                    if (!cont) armed <= shot && en;   // consumed (unless re-armed on this very clock)
                end
                if (s_axis_tlast) fire <= 1'b0;
            end
        end
    end

    assign led = {blink, cont && en, armed, en};
endmodule
`default_nettype wire
