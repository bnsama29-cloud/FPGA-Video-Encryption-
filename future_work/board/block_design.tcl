# block_design.tcl -- PYNQ-Z2 overlay: Zynq PS + AXI DMA + secure JPEG IP -> bitstream + .hwh
#
#   vivado -mode batch -source future_work/board/block_design.tcl          (from the repo root)
#   vivado -mode gui   -source future_work/board/block_design.tcl          (to inspect the diagram)
#
# Output: future_work/board/overlay/secure_jpeg.bit and secure_jpeg.hwh -> copy both to
# the board (same folder, same base name) and use them with pynq_driver.PynqBackend.
#
# STATUS: written as a starting point and NOT yet run in Vivado (no Vivado in the
# environment it was written in). Expect to fix small things (IP versions, pin
# names) on the first run -- paste the first error into Claude together with
# docs/TEAM_CONTEXT.md. Tested with nothing; reviewed against Vivado 2023.x syntax.
#
# What it builds:
#   ps7 (DDR + FIXED_IO, FCLK0 = 100 MHz, M_AXI_GP0 master, S_AXI_HP0 slave, IRQ_F2P)
#   axi_dma (simple mode, 32-bit streams): MM2S -> sjpeg/s_axis (pixels),
#                                           sjpeg/m_axis -> S2MM (scan bytes)
#   sjpeg = sjpeg_bd_top (RTL module reference around rtl/secure_jpeg_top.v)
#   AXI-Lite: ps7 GP0 -> {dma control, sjpeg registers}; interrupts -> IRQ_F2P

set root    [file normalize [file join [file dirname [info script]] .. ..]]
set projdir [file join $root future_work board vivado_proj]
set outdir  [file join $root future_work board overlay]
set part    xc7z020clg400-1

create_project pynq_secure_jpeg $projdir -part $part -force
# Board files make the PS presets exact. If the PYNQ-Z2 board files are installed
# (https://github.com/Xilinx/PYNQ -> boards/Pynq-Z2), uncomment:
# set_property board_part tul.com.tw:pynq-z2:part0:1.0 [current_project]

add_files [glob [file join $root rtl *.v]]
add_files [file join $root future_work board sjpeg_bd_top.v]
set_property include_dirs [file join $root rtl include] [get_filesets sources_1]
update_compile_order -fileset sources_1

create_bd_design system

# ---- Zynq processing system
set ps7 [create_bd_cell -type ip -vlnv xilinx.com:ip:processing_system7 ps7]
apply_bd_automation -rule xilinx.com:bd_rule:processing_system7 \
    -config {make_external "FIXED_IO, DDR" apply_board_preset "1" Master "Disable" Slave "Disable"} $ps7
set_property -dict [list \
    CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ {100} \
    CONFIG.PCW_USE_M_AXI_GP0 {1} \
    CONFIG.PCW_USE_S_AXI_HP0 {1} \
    CONFIG.PCW_S_AXI_HP0_DATA_WIDTH {64} \
    CONFIG.PCW_USE_FABRIC_INTERRUPT {1} \
    CONFIG.PCW_IRQ_F2P_INTR {1}] $ps7

# ---- our IP (RTL module reference, no packaging step needed)
set sjpeg [create_bd_cell -type module -reference sjpeg_bd_top sjpeg]

# ---- AXI DMA, simple (register) mode
set dma [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_dma dma]
set_property -dict [list \
    CONFIG.c_include_sg {0} \
    CONFIG.c_sg_length_width {23} \
    CONFIG.c_m_axi_mm2s_data_width {32} \
    CONFIG.c_m_axis_mm2s_tdata_width {32} \
    CONFIG.c_m_axi_s2mm_data_width {32} \
    CONFIG.c_mm2s_burst_size {16} \
    CONFIG.c_s2mm_burst_size {16}] $dma

connect_bd_intf_net [get_bd_intf_pins dma/M_AXIS_MM2S] [get_bd_intf_pins sjpeg/s_axis]
connect_bd_intf_net [get_bd_intf_pins sjpeg/m_axis]     [get_bd_intf_pins dma/S_AXIS_S2MM]

# ---- AXI-Lite control from the PS, memory access to DDR through HP0
apply_bd_automation -rule xilinx.com:bd_rule:axi4 \
    -config {Master "/ps7/M_AXI_GP0" Clk "/ps7/FCLK_CLK0 (100 MHz)"} [get_bd_intf_pins dma/S_AXI_LITE]
apply_bd_automation -rule xilinx.com:bd_rule:axi4 \
    -config {Master "/ps7/M_AXI_GP0" Clk "/ps7/FCLK_CLK0 (100 MHz)"} [get_bd_intf_pins sjpeg/s_axil]
apply_bd_automation -rule xilinx.com:bd_rule:axi4 \
    -config {Slave "/ps7/S_AXI_HP0" Clk "/ps7/FCLK_CLK0 (100 MHz)"} [get_bd_intf_pins dma/M_AXI_MM2S]
apply_bd_automation -rule xilinx.com:bd_rule:axi4 \
    -config {Slave "/ps7/S_AXI_HP0" Clk "/ps7/FCLK_CLK0 (100 MHz)"} [get_bd_intf_pins dma/M_AXI_S2MM]

# ---- clock and reset for our IP (active-high, synchronous, from the automation's reset block)
connect_bd_net [get_bd_pins ps7/FCLK_CLK0] [get_bd_pins sjpeg/clk]
set rstblk [lindex [get_bd_cells -filter {VLNV =~ "*proc_sys_reset*"}] 0]
connect_bd_net [get_bd_pins $rstblk/peripheral_reset] [get_bd_pins sjpeg/rst]

# ---- interrupts: our DONE + both DMA channels -> IRQ_F2P
set cc [create_bd_cell -type ip -vlnv xilinx.com:ip:xlconcat irq_concat]
set_property CONFIG.NUM_PORTS {3} $cc
connect_bd_net [get_bd_pins sjpeg/irq_done]         [get_bd_pins irq_concat/In0]
connect_bd_net [get_bd_pins dma/mm2s_introut]       [get_bd_pins irq_concat/In1]
connect_bd_net [get_bd_pins dma/s2mm_introut]       [get_bd_pins irq_concat/In2]
connect_bd_net [get_bd_pins irq_concat/dout]        [get_bd_pins ps7/IRQ_F2P]

assign_bd_address
validate_bd_design
save_bd_design

# ---- wrapper, synthesis, implementation, bitstream
set bd [get_files system.bd]
make_wrapper -files $bd -top
add_files -norecurse [file join $projdir pynq_secure_jpeg.gen sources_1 bd system hdl system_wrapper.v]
set_property top system_wrapper [current_fileset]
update_compile_order -fileset sources_1
launch_runs impl_1 -to_step write_bitstream -jobs 4
wait_on_run impl_1

file mkdir $outdir
set bit [glob -nocomplain [file join $projdir pynq_secure_jpeg.runs impl_1 *.bit]]
set hwh [glob -nocomplain [file join $projdir pynq_secure_jpeg.gen sources_1 bd system hw_handoff system.hwh]]
if {$bit eq "" || $hwh eq ""} {
    error "bitstream or .hwh not found -- open the project and check the impl_1 log"
}
file copy -force [lindex $bit 0] [file join $outdir secure_jpeg.bit]
file copy -force [lindex $hwh 0] [file join $outdir secure_jpeg.hwh]
open_run impl_1
report_utilization    -file [file join $outdir utilization.txt]
report_timing_summary -file [file join $outdir timing.txt]
report_power          -file [file join $outdir power.txt]
puts "Overlay in $outdir (secure_jpeg.bit + secure_jpeg.hwh). Check WNS >= 0 in timing.txt."
