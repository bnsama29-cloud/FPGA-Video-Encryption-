// scan_word_packer.v -- scan bytes -> 32-bit AXI4-Stream words for the DMA.
// Little-endian: the first byte goes to bits [7:0] (so numpy .view(uint8)
// on the ARM gives the bytes in order). TLAST on the word holding the final
// byte; TKEEP marks valid bytes; out_bytes counts bytes since `start`.
`default_nettype none
module scan_word_packer (
    input  wire        clk,
    input  wire        rst,
    input  wire        start,
    input  wire        i_valid,
    output wire        i_ready,
    input  wire [7:0]  i_data,
    input  wire        i_last,
    output reg         m_tvalid,
    input  wire        m_tready,
    output reg  [31:0] m_tdata,
    output reg  [3:0]  m_tkeep,
    output reg         m_tlast,
    output reg  [31:0] out_bytes
);
    reg [23:0] hold;
    reg [1:0]  cnt;

    assign i_ready = !m_tvalid || m_tready;
    wire take = i_valid && i_ready;

    always @(posedge clk) begin
        if (rst || start) begin
            cnt <= 2'd0; m_tvalid <= 1'b0; out_bytes <= 32'd0; hold <= 24'd0;
        end else begin
            if (m_tvalid && m_tready) m_tvalid <= 1'b0;
            if (take) begin
                out_bytes <= out_bytes + 32'd1;
                if (cnt == 2'd3 || i_last) begin
                    m_tvalid <= 1'b1;
                    m_tlast  <= i_last;
                    case (cnt)
                    2'd0: begin m_tdata <= {24'd0, i_data};       m_tkeep <= 4'b0001; end
                    2'd1: begin m_tdata <= {16'd0, i_data, hold[7:0]};  m_tkeep <= 4'b0011; end
                    2'd2: begin m_tdata <= {8'd0, i_data, hold[15:0]};  m_tkeep <= 4'b0111; end
                    default: begin m_tdata <= {i_data, hold[23:0]}; m_tkeep <= 4'b1111; end
                    endcase
                    cnt <= 2'd0;
                    hold <= 24'd0;
                end else begin
                    hold[8*cnt +: 8] <= i_data;
                    cnt <= cnt + 2'd1;
                end
            end
        end
    end
endmodule
`default_nettype wire
