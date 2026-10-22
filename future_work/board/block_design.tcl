# block_design.tcl -- PYNQ-Z2 overlay: Zynq PS + AXI DMA + secure JPEG IP -> bitstream + .hwh
#
#   vivado -mode batch -source future_work/board/block_design.tcl          (from the repo root)
#   vivado -mode gui   -source future_work/board/block_design.tcl          (to inspect the diagram)
#   vivado -mode batch -source future_work/board/block_design.tcl -tclargs 50   (FCLK0 = 50 MHz
#                                                         if timing fails at 100 MHz)
#   ... -tclargs 100 4                                   (FCLK0 = 100 MHz, 4 parallel jobs)
#   ... -tclargs 100 2 lanes                             (contract-v3 lane encoder, 2 lanes,
#                                                         64-bit pixel DMA; own project + overlay
#                                                         secure_jpeg_lanes.bit/.hwh)
#   ... -tclargs 100 2 lanes4                            (the same with 4 lanes, lines up to 1024
#                                                         pixels: secure_jpeg_lanes4.bit/.hwh,
#                                                         reports in overlay/lanes4/)
#   ... -tclargs 100 2 lanes4hd   (4 lanes, 1080p lines, NBUF = 1: secure_jpeg_lanes4hd.bit)
#   ... -tclargs 100 2 lanes4yuyv (4 lanes, YUYV camera input: secure_jpeg_lanes4yuyv.bit)
#   ... -tclargs 100 2 lanestamper (2 lanes as "lanes" + the hardware tamper injector between the encoder and
#                                   the receive DMA, driven by SW0/SW1, BTN0 and PMOD A pin 1, LEDs show its
#                                   state: secure_jpeg_lanes_tamper.bit, attack demonstration only)
#
# Output: future_work/board/overlay/secure_jpeg.bit and secure_jpeg.hwh -> copy both to
# the board (same folder, same base name) and use them with pynq_driver.PynqBackend.
#
# STATUS: first run in Vivado 2026.1 on 14 Oct 2026 stopped at create_bd_cell (header file
# not in the project, fixed above); the steps after it have still never run. Expect to fix
# small things (an IP version, a pin name). Guide: docs/VIVADO_ONE_DAY.md §5. Paste the FIRST
# "ERROR:" line of vivado.log into Claude together with docs/TEAM_CONTEXT.md.
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
set fclk    [expr {[llength $argv] > 0 ? [lindex $argv 0] : 100}]
# parallel jobs for the IP/out-of-context synthesis runs: each needs ~2 GB for the xc7z020,
# so 2 suits an 8 GB laptop (second argument; run_vivado_day.py --jobs passes it)
set jobs    [expr {[llength $argv] > 1 ? [lindex $argv 1] : 2}]
# third argument: "v2" (default, secure_jpeg_top, 32-bit pixel stream) or "lanes" (contract v3,
# secure_jpeg_lanes_top with 2 lanes, 64-bit pixel stream = 2 pixels per DMA beat)
set design  [expr {[llength $argv] > 2 ? [lindex $argv 2] : "v2"}]
if {$design eq "lanes"} {
    set projdir [file join $root future_work board vivado_proj_lanes]
    set outname secure_jpeg_lanes
    set bdtop   sjpeg_lanes_bd_top
    set pxbits  64
} elseif {$design eq "lanestamper"} {
    # the 2-lane image unchanged + future_work/board/axis_tamper.v on the scan stream (board day, attack demo)
    set projdir [file join $root future_work board vivado_proj_lanestamper]
    set outname secure_jpeg_lanes_tamper
    set bdtop   sjpeg_lanes_bd_top
    set pxbits  64
} elseif {$design in {lanes4 lanes4hd lanes4yuyv}} {
    # 4 lanes, same wrapper. lanes4: lines up to 1024 pixels (VGA); lanes4hd: 2048-pixel lines (1080p) with
    # one line-buffer set per lane (NBUF = 1, otherwise the BRAM would double); lanes4yuyv: camera-native
    # YUYV input, four pixels per 64-bit beat (rtl/yuyv_4px.v), lines up to 1024 pixels
    set projdir [file join $root future_work board vivado_proj_$design]
    set outname [string map {lanes4 secure_jpeg_lanes4} $design]
    set bdtop   sjpeg_lanes_bd_top
    set pxbits  64
} else {
    set outname secure_jpeg
    set bdtop   sjpeg_bd_top
    set pxbits  32
}

create_project pynq_secure_jpeg $projdir -part $part -force
# PYNQ-Z2 board files give the exact PS presets (DDR, MIO). They are used automatically
# when installed: copy the "pynq-z2" folder from https://github.com/Xilinx/PYNQ
# (boards/Pynq-Z2/board_files) or the TUL website into <Vivado>/data/boards/board_files/.
set bp [lindex [lsort [get_board_parts -quiet *pynq-z2*]] end]
if {$bp ne ""} {
    set_property board_part $bp [current_project]
    puts "INFO: using board part $bp"
} else {
    puts "WARNING: PYNQ-Z2 board files not installed: using the bare part $part. The overlay still"
    puts "WARNING: loads on PYNQ (the PYNQ image configures DDR at boot), but install them for exact presets."
}

add_files [glob [file join $root rtl *.v]]
add_files [file join $root future_work board ${bdtop}.v]
if {$design eq "lanestamper"} {
    add_files [file join $root future_work board axis_tamper.v]
    add_files -fileset constrs_1 [file join $root future_work board tamper_pynq_z2.xdc]
}
# The RTL `include`s generated headers (dct_coeffs.vh, ...). A module reference
# (create_bd_cell -type module) only accepts them when they are project files of type
# "Verilog Header" (first Vivado run: ERROR [filemgmt 56-591], bug #18).
set vh [glob -nocomplain [file join $root rtl include *.vh]]
if {[llength $vh] > 0} {
    add_files -norecurse $vh
    set_property file_type {Verilog Header} [get_files $vh]
}
set_property include_dirs [file join $root rtl include] [get_filesets sources_1]
update_compile_order -fileset sources_1

create_bd_design system

# ---- Zynq processing system
set ps7 [create_bd_cell -type ip -vlnv xilinx.com:ip:processing_system7 ps7]
apply_bd_automation -rule xilinx.com:bd_rule:processing_system7 \
    -config {make_external "FIXED_IO, DDR" apply_board_preset "1" Master "Disable" Slave "Disable"} $ps7
set_property -dict [list \
    CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ $fclk \
    CONFIG.PCW_USE_M_AXI_GP0 {1} \
    CONFIG.PCW_USE_S_AXI_HP0 {1} \
    CONFIG.PCW_S_AXI_HP0_DATA_WIDTH {64} \
    CONFIG.PCW_USE_FABRIC_INTERRUPT {1} \
    CONFIG.PCW_IRQ_F2P_INTR {1}] $ps7

# ---- our IP (RTL module reference, no packaging step needed)
set sjpeg [create_bd_cell -type module -reference $bdtop sjpeg]
if {$design eq "lanes4"} {
    set_property -dict [list CONFIG.LANES {4} CONFIG.LOG_L {2} CONFIG.LOG_MAXW {10}] $sjpeg
} elseif {$design eq "lanes4hd"} {
    set_property -dict [list CONFIG.LANES {4} CONFIG.LOG_L {2} CONFIG.LOG_MAXW {11} CONFIG.NBUF {1}] $sjpeg
} elseif {$design eq "lanes4yuyv"} {
    set_property -dict [list CONFIG.LANES {4} CONFIG.LOG_L {2} CONFIG.LOG_MAXW {10} CONFIG.PIXFMT {1}] $sjpeg
}

# ---- AXI DMA, simple (register) mode
set dma [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_dma dma]
set_property -dict [list \
    CONFIG.c_include_sg {0} \
    CONFIG.c_sg_length_width {23} \
    CONFIG.c_m_axi_mm2s_data_width $pxbits \
    CONFIG.c_m_axis_mm2s_tdata_width $pxbits \
    CONFIG.c_m_axi_s2mm_data_width {32} \
    CONFIG.c_mm2s_burst_size {16} \
    CONFIG.c_s2mm_burst_size {16}] $dma

# Clock our IP from FCLK0 BEFORE the AXI automation, so "Auto" reuses this clock. The wrapper's clock
# pin no longer declares FREQ_HZ 100000000: with that fixed value, a 90 or 80 MHz retry made the
# automation insert a clk_wiz with an unconnected input (run 5: ERROR [BD 41-758] /clk_wiz/clk_in1).
connect_bd_net [get_bd_pins ps7/FCLK_CLK0] [get_bd_pins sjpeg/clk]

connect_bd_intf_net [get_bd_intf_pins dma/M_AXIS_MM2S] [get_bd_intf_pins sjpeg/s_axis]
if {$design eq "lanestamper"} {
    # encoder -> tamper injector -> receive DMA; the board's buttons, switches, LEDs and PMOD A pin 1
    set tamper [create_bd_cell -type module -reference axis_tamper tamper]
    connect_bd_net [get_bd_pins ps7/FCLK_CLK0] [get_bd_pins tamper/clk]
    connect_bd_intf_net [get_bd_intf_pins sjpeg/m_axis]  [get_bd_intf_pins tamper/s_axis]
    connect_bd_intf_net [get_bd_intf_pins tamper/m_axis] [get_bd_intf_pins dma/S_AXIS_S2MM]
    create_bd_port -dir I -from 3 -to 0 btn
    create_bd_port -dir I -from 1 -to 0 sw
    create_bd_port -dir I pmod_trig
    create_bd_port -dir O -from 3 -to 0 led
    connect_bd_net [get_bd_ports btn]       [get_bd_pins tamper/btn]
    connect_bd_net [get_bd_ports sw]        [get_bd_pins tamper/sw]
    connect_bd_net [get_bd_ports pmod_trig] [get_bd_pins tamper/pmod_trig]
    connect_bd_net [get_bd_ports led]       [get_bd_pins tamper/led]
} else {
    connect_bd_intf_net [get_bd_intf_pins sjpeg/m_axis] [get_bd_intf_pins dma/S_AXIS_S2MM]
}

# ---- AXI-Lite control from the PS, memory access to DDR through HP0
# (same -config form that Vivado 2019.2+ records in its journal; clocks "Auto" = FCLK_CLK0,
# the only clock in the design)
proc axi_auto {master slave target} {
    apply_bd_automation -rule xilinx.com:bd_rule:axi4 -config [list \
        Clk_master {Auto} Clk_slave {Auto} Clk_xbar {Auto} Master $master Slave $slave \
        ddr_seg {Auto} intc_ip {Auto} master_apm {0}] [get_bd_intf_pins $target]
}
axi_auto /ps7/M_AXI_GP0  /dma/S_AXI_LITE   dma/S_AXI_LITE
axi_auto /ps7/M_AXI_GP0  /sjpeg/s_axil     sjpeg/s_axil
# The second master must be the automation TARGET (bug #32): the first call connects HP0; a call that
# targets ps7/S_AXI_HP0 again finds it already connected and does nothing, which left M_AXI_S2MM
# unconnected with no address (on the board the receive DMA never wrote a byte and hung).
axi_auto /dma/M_AXI_MM2S /ps7/S_AXI_HP0    ps7/S_AXI_HP0
axi_auto /dma/M_AXI_S2MM /ps7/S_AXI_HP0    dma/M_AXI_S2MM

# ---- clock and reset for our IP (active-high, synchronous, from the automation's reset block)
# (the AXI automation above may already have wired them: only connect what is still open)
proc unconnected {pin} { expr {[llength [get_bd_nets -quiet -of_objects [get_bd_pins $pin]]] == 0} }
# (sjpeg/clk was connected to FCLK0 above)
set rstblk [lindex [get_bd_cells -filter {VLNV =~ "*proc_sys_reset*"}] 0]
if {[unconnected sjpeg/rst]} { connect_bd_net [get_bd_pins $rstblk/peripheral_reset] [get_bd_pins sjpeg/rst] }
if {$design eq "lanestamper" && [unconnected tamper/rst]} {
    connect_bd_net [get_bd_pins $rstblk/peripheral_reset] [get_bd_pins tamper/rst]
}

# ---- interrupts: our DONE + both DMA channels -> IRQ_F2P
set cc [create_bd_cell -type ip -vlnv xilinx.com:ip:xlconcat irq_concat]
set_property CONFIG.NUM_PORTS {3} $cc
connect_bd_net [get_bd_pins sjpeg/irq_done]         [get_bd_pins irq_concat/In0]
connect_bd_net [get_bd_pins dma/mm2s_introut]       [get_bd_pins irq_concat/In1]
connect_bd_net [get_bd_pins dma/s2mm_introut]       [get_bd_pins irq_concat/In2]
connect_bd_net [get_bd_pins irq_concat/dout]        [get_bd_pins ps7/IRQ_F2P]

assign_bd_address
# Every DMA master must reach DDR through HP0, or the overlay loads but the DMA hangs on the board (bug #32).
foreach space {dma/Data_MM2S dma/Data_S2MM} {
    if {[llength [get_bd_addr_segs -quiet -of_objects [get_bd_addr_spaces $space]]] == 0} {
        error "$space has no address segment: the DMA master is not connected to ps7/S_AXI_HP0"
    }
}
if {[llength [get_bd_cells -quiet -filter {VLNV =~ "*clk_wiz*"}]] > 0} {
    error "the AXI automation added a clk_wiz: every block must run on ps7/FCLK_CLK0 (see the comment at sjpeg/clk)"
}
validate_bd_design
save_bd_design

# ---- wrapper, synthesis, implementation, bitstream
set bd [get_files system.bd]
# make_wrapper returns the path of the wrapper (.gen/ in Vivado 2020.2+, .srcs/ before)
add_files -norecurse [make_wrapper -files $bd -top]
set_property top system_wrapper [current_fileset]
update_compile_order -fileset sources_1
# Implementation strategy (run 10): timing-driven unless SJPEG_IMPL=default (the flow of runs 1-9)
if {![info exists ::env(SJPEG_IMPL)] || $::env(SJPEG_IMPL) ne "default"} {
    if {[catch {set_property strategy Flow_PerfOptimized_high [get_runs synth_1]} err]} { puts "WARNING: $err" }
    if {[catch {set_property strategy Performance_ExplorePostRoutePhysOpt [get_runs impl_1]} err]} { puts "WARNING: $err" }
}
launch_runs impl_1 -to_step write_bitstream -jobs $jobs
wait_on_run impl_1

file mkdir $outdir
if {[get_property PROGRESS [get_runs impl_1]] ne "100%"} {
    error "implementation did not finish -- open $projdir in the GUI and read the impl_1 / synth_1 logs"
}
set bit [glob -nocomplain [file join $projdir pynq_secure_jpeg.runs impl_1 *.bit]]
set hwh [concat [glob -nocomplain [file join $projdir pynq_secure_jpeg.gen sources_1 bd system hw_handoff system.hwh]] \
                [glob -nocomplain [file join $projdir pynq_secure_jpeg.srcs sources_1 bd system hw_handoff system.hwh]]]
if {$bit eq "" || $hwh eq ""} {
    error "bitstream or .hwh not found -- open the project and check the impl_1 log"
}
file copy -force [lindex $bit 0] [file join $outdir ${outname}.bit]
file copy -force [lindex $hwh 0] [file join $outdir ${outname}.hwh]
open_run impl_1
# reports: overlay/ for v2 (as before), overlay/lanes/ for the lane encoder
set rptdir [expr {$design eq "v2" ? $outdir : [file join $outdir $design]}]
file mkdir $rptdir
report_utilization    -file [file join $rptdir utilization.txt]
report_utilization    -hierarchical -hierarchical_depth 3 -file [file join $rptdir utilization_hier.txt]
report_timing_summary -max_paths 10 -file [file join $rptdir timing.txt]
report_power          -file [file join $rptdir power.txt]
set wns [get_property SLACK [get_timing_paths -max_paths 1 -nworst 1 -setup]]
puts "RESULT overlay design=$design fclk=${fclk}MHz WNS=${wns}ns"
puts "Overlay in $outdir (${outname}.bit + ${outname}.hwh). WNS must be >= 0 before using it."
