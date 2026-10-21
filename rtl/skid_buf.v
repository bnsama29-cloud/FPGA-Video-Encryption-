// skid_buf.v -- two-entry register slice for a valid/ready stream (a "skid buffer").
//
// Why it exists (Vivado run 9): once the colour converter was pipelined, the slowest paths at
// 125 MHz were handshake chains. A ready signal travelled combinationally from the bit packer
// back through the Huffman coder and the encryption stage into the keystream pointer and the
// run-length scanner (9 logic levels, 7.4 ns). A skid buffer cuts such a chain: i_ready leaves
// this module straight from a flip-flop (!s_v) and o_valid/o_data straight from flip-flops,
// yet a word can still pass every clock (the second entry catches the word that was already
// on its way when the consumer stopped).
//
// Behaviour: a FIFO of depth 2. Data never changes order and never duplicates, so inserting it
// anywhere in a stream leaves the byte stream unchanged; only the latency grows by one clock.
// Not part of the golden model (pure plumbing): model/hw.py has no counterpart.
`default_nettype none
module skid_buf #(
    parameter W = 8
) (
    input  wire         clk,
    input  wire         rst,
    input  wire         i_valid,
    output wire         i_ready,
    input  wire [W-1:0] i_data,
    output wire         o_valid,
    input  wire         o_ready,
    output wire [W-1:0] o_data
);
    reg [W-1:0] m_d, s_d;      // main entry (drives the output) and skid entry
    reg         m_v, s_v;
    // power-up value of the data registers (an FPGA flip-flop INIT, no reset logic): keeps the
    // outputs 0 instead of X in simulation before the first word, e.g. a downstream ks_n
    initial begin m_d = {W{1'b0}}; s_d = {W{1'b0}}; end

    assign i_ready = !s_v;
    assign o_valid = m_v;
    assign o_data  = m_d;

    wire push = i_valid && !s_v;
    wire pop  = m_v && o_ready;

    // datapath registers: no reset needed (qualified by the valid bits)
    always @(posedge clk) begin
        if (pop) begin
            if (s_v)       m_d <= s_d;
            else if (push) m_d <= i_data;
        end else if (push) begin
            if (m_v) s_d <= i_data;
            else     m_d <= i_data;
        end
    end

    always @(posedge clk) begin
        if (rst) begin
            m_v <= 1'b0; s_v <= 1'b0;
        end else if (pop) begin
            if (s_v)        s_v <= 1'b0;            // skid entry moves to the main entry
            else if (!push) m_v <= 1'b0;
        end else if (push) begin
            if (m_v) s_v <= 1'b1;
            else     m_v <= 1'b1;
        end
    end
endmodule
`default_nettype wire
