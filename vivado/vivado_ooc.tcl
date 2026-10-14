# Out-of-context synthesis + implementation in Vivado (no board needed).
# Gives the real LUT/FF/BRAM/DSP use, timing slack and a power estimate for the paper.
# Run from the repository root (or let vivado/run_vivado_day.py do it):
#   vivado -mode batch -source vivado/vivado_ooc.tcl                              (whole design, 100 MHz)
#   vivado -mode batch -source vivado/vivado_ooc.tcl -tclargs ascon_aead128_core  (one block)
#   vivado -mode batch -source vivado/vivado_ooc.tcl -tclargs secure_jpeg_top 8.0 (try 125 MHz)
#   vivado -mode batch -source vivado/vivado_ooc.tcl -tclargs secure_jpeg_top 10.0 LOG_MAXW=10
#                                                     (1024-pixel line buffers: memory sweep)
# Reports in sim_build/vivado_<top>[_<period>ns]/: utilization.txt, utilization_hier.txt,
# timing.txt (WNS), power.txt (vectorless estimate). python vivado/parse_reports.py turns
# them into the paper table.
#
# The clock is declared in an XDC that is read BEFORE synthesis, so synthesis is
# timing-driven (declaring it only after synth_design would leave synthesis blind).
set top    [expr {[llength $argv] > 0 ? [lindex $argv 0] : "secure_jpeg_top"}]
set period [expr {[llength $argv] > 1 ? [lindex $argv 1] : "10.0"}]
# optional third argument: a top-level parameter, e.g. LOG_MAXW=10 (memory sweep, GUIDE B19)
set gen    [expr {[llength $argv] > 2 ? [lindex $argv 2] : ""}]
set out    sim_build/vivado_$top
if {$period != 10.0} { set out ${out}_${period}ns }
if {$gen ne ""} { set out ${out}_[string tolower [string map {= ""} $gen]] }
file mkdir $out

read_verilog [glob rtl/*.v]
set_property include_dirs rtl/include [current_fileset]

# I/O delays (bug #20): without them the ports are unconstrained and Vivado does not time any
# path that starts at an input or ends at an output. The first overlay then failed by 3.1 ns on
# a path from the DMA register into the colour conversion that this run had reported as met.
# 20 % of the period stands for the neighbouring block's clock-to-out and routing.
set io [expr {0.2 * $period}]
set xdc [file join $out clock.xdc]
set f [open $xdc w]
puts $f "create_clock -name clk -period $period \[get_ports clk\]"
puts $f "set_input_delay  -clock clk $io \[get_ports -filter {DIRECTION == IN && NAME != clk}\]"
puts $f "set_output_delay -clock clk $io \[get_ports -filter {DIRECTION == OUT}\]"
close $f
read_xdc -mode out_of_context $xdc

set gopt {}
if {$gen ne ""} { set gopt [list -generic $gen] }
synth_design -top $top -part xc7z020clg400-1 -mode out_of_context -flatten_hierarchy rebuilt \
             -include_dirs rtl/include {*}$gopt
report_utilization -file $out/utilization_synth.txt
opt_design
place_design
phys_opt_design
route_design
report_utilization    -file $out/utilization.txt
report_utilization    -hierarchical -hierarchical_depth 3 -file $out/utilization_hier.txt
report_timing_summary -max_paths 10 -file $out/timing.txt
report_power          -file $out/power.txt
write_checkpoint -force $out/routed.dcp
set wns [get_property SLACK [get_timing_paths -max_paths 1 -nworst 1 -setup]]
puts "RESULT top=$top period=${period}ns $gen WNS=${wns}ns -> reports in $out/"
puts "WNS >= 0 means the design meets ${period} ns. Estimated fmax = 1000 / (period - WNS) MHz."
