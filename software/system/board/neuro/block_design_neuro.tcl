# block_design_neuro.tcl -- PYNQ-Z2 overlay for paper 2: Zynq PS + AXI DMA + nv_top -> nv.bit + nv.hwh (DESIGN §8.2 N10)
#
#   vivado -mode batch -source software/system/board/neuro/block_design_neuro.tcl                 (repo root)
#   vivado -mode batch -source software/system/board/neuro/block_design_neuro.tcl -tclargs 100 2 2
#                                                     (FCLK0 MHz, parallel jobs, U = Ascon rounds per clock)
# Output: software/system/board/overlay/neuro/nv.bit and nv.hwh; copy both to the board and use them with
# software/system/board/neuro/nv_driver.py (PynqBackend). Paper 1's block_design.tcl is not edited.
#
#   ps7 (FCLK0, M_AXI_GP0, S_AXI_HP0 64-bit, IRQ_F2P)
#   axi_dma (simple mode, 32-bit streams): MM2S -> nv/s_axis (EVT 2.0 words), nv/m_axis -> S2MM (packets; tlast ends
#                                          each S2MM transfer, one packet per transfer)
#   nv = nv_bd_top (module reference around hardware/rtl/neuro/nv_top.v, PAD = 1, MAX_CD = 131072, 1280 x 720)
#   AXI-Lite: ps7 GP0 -> {dma control, nv registers}; DMA interrupts -> IRQ_F2P
set root    [file normalize [file join [file dirname [info script]] .. .. .. ..]]
set projdir [file join $root software system board vivado_proj_neuro]
set outdir  [file join $root software system board overlay neuro]
set part    xc7z020clg400-1
set fclk    [expr {[llength $argv] > 0 ? [lindex $argv 0] : 100}]
set jobs    [expr {[llength $argv] > 1 ? [lindex $argv 1] : 2}]
set U       [expr {[llength $argv] > 2 ? [lindex $argv 2] : 2}]
file mkdir $outdir

create_project pynq_neuro $projdir -part $part -force
set bp [lindex [lsort [get_board_parts -quiet *pynq-z2*]] end]
if {$bp ne ""} { set_property board_part $bp [current_project] }

add_files [list [file join $root hardware rtl ascon_round.v] [file join $root hardware rtl ascon_aead128_core.v] \
                [file join $root hardware rtl keystream_gen.v] [file join $root hardware rtl skid_buf.v]]
add_files [glob [file join $root hardware rtl neuro *.v]]
add_files [file join $root software system board neuro nv_bd_top.v]
update_compile_order -fileset sources_1

create_bd_design system
set ps7 [create_bd_cell -type ip -vlnv xilinx.com:ip:processing_system7 ps7]
apply_bd_automation -rule xilinx.com:bd_rule:processing_system7 \
    -config {make_external "FIXED_IO, DDR" apply_board_preset "1" Master "Disable" Slave "Disable"} $ps7
set_property -dict [list CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ $fclk CONFIG.PCW_USE_M_AXI_GP0 {1} \
    CONFIG.PCW_USE_S_AXI_HP0 {1} CONFIG.PCW_S_AXI_HP0_DATA_WIDTH {64} CONFIG.PCW_USE_FABRIC_INTERRUPT {1} \
    CONFIG.PCW_IRQ_F2P_INTR {1}] $ps7

set nv [create_bd_cell -type module -reference nv_bd_top nv]
set_property -dict [list CONFIG.U $U] $nv

set dma [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_dma dma]
set_property -dict [list CONFIG.c_include_sg {0} CONFIG.c_sg_length_width {23} \
    CONFIG.c_m_axi_mm2s_data_width {32} CONFIG.c_m_axis_mm2s_tdata_width {32} CONFIG.c_m_axi_s2mm_data_width {32} \
    CONFIG.c_mm2s_burst_size {16} CONFIG.c_s2mm_burst_size {16}] $dma

connect_bd_net [get_bd_pins ps7/FCLK_CLK0] [get_bd_pins nv/clk]
connect_bd_intf_net [get_bd_intf_pins dma/M_AXIS_MM2S] [get_bd_intf_pins nv/s_axis]
connect_bd_intf_net [get_bd_intf_pins nv/m_axis] [get_bd_intf_pins dma/S_AXIS_S2MM]

proc axi_auto {master slave target} {
    apply_bd_automation -rule xilinx.com:bd_rule:axi4 -config [list \
        Clk_master {Auto} Clk_slave {Auto} Clk_xbar {Auto} Master $master Slave $slave \
        ddr_seg {Auto} intc_ip {Auto} master_apm {0}] [get_bd_intf_pins $target]
}
axi_auto /ps7/M_AXI_GP0  /dma/S_AXI_LITE dma/S_AXI_LITE
axi_auto /ps7/M_AXI_GP0  /nv/s_axil      nv/s_axil
# the second master must be the automation target (paper 1 bug #32)
axi_auto /dma/M_AXI_MM2S /ps7/S_AXI_HP0  ps7/S_AXI_HP0
axi_auto /dma/M_AXI_S2MM /ps7/S_AXI_HP0  dma/M_AXI_S2MM

proc unconnected {pin} { expr {[llength [get_bd_nets -quiet -of_objects [get_bd_pins $pin]]] == 0} }
set rstblk [lindex [get_bd_cells -filter {VLNV =~ "*proc_sys_reset*"}] 0]
if {[unconnected nv/rst]} { connect_bd_net [get_bd_pins $rstblk/peripheral_reset] [get_bd_pins nv/rst] }

set cc [create_bd_cell -type ip -vlnv xilinx.com:ip:xlconcat irq_concat]
set_property CONFIG.NUM_PORTS {2} $cc
connect_bd_net [get_bd_pins dma/mm2s_introut] [get_bd_pins irq_concat/In0]
connect_bd_net [get_bd_pins dma/s2mm_introut] [get_bd_pins irq_concat/In1]
connect_bd_net [get_bd_pins irq_concat/dout]  [get_bd_pins ps7/IRQ_F2P]

assign_bd_address
# both DMA masters must reach DDR (paper-1 bug #32: an S2MM left without a segment wrote nothing on the board)
foreach seg {Data_MM2S Data_S2MM} {
    if {[llength [get_bd_addr_segs -quiet -of_objects [get_bd_addr_spaces dma/$seg]]] == 0} {
        error "dma/$seg has no address segment: the DMA cannot reach DDR"
    }
}
validate_bd_design
save_bd_design
make_wrapper -files [get_files system.bd] -top
add_files -norecurse [glob [file join $projdir pynq_neuro.gen sources_1 bd system hdl system_wrapper.v]]
set_property top system_wrapper [current_fileset]
update_compile_order -fileset sources_1

launch_runs impl_1 -to_step write_bitstream -jobs $jobs
wait_on_run impl_1
set impl [get_runs impl_1]
if {[get_property PROGRESS $impl] ne "100%"} { error "implementation did not finish: [get_property STATUS $impl]" }
open_run impl_1
report_utilization    -file [file join $outdir utilization.txt]
report_timing_summary -file [file join $outdir timing.txt]
report_power          -file [file join $outdir power.txt]
set bit [glob [file join $projdir pynq_neuro.runs impl_1 *.bit]]
file copy -force $bit [file join $outdir nv.bit]
set hwh [glob -nocomplain [file join $projdir pynq_neuro.gen sources_1 bd system hw_handoff system.hwh]]
if {$hwh ne ""} { file copy -force [lindex $hwh 0] [file join $outdir nv.hwh] }
puts "OVERLAY written to $outdir (nv.bit, nv.hwh) U=$U FCLK0=$fclk MHz"
