# Out-of-context synthesis + implementation in Vivado (no board needed).
# Gives the real LUT/FF/BRAM/DSP use, timing slack and a power estimate for the paper.
# Run from the repository root (or let vivado/run_vivado_day.py do it):
#   vivado -mode batch -source vivado/vivado_ooc.tcl                              (whole design, 100 MHz)
#   vivado -mode batch -source vivado/vivado_ooc.tcl -tclargs ascon_aead128_core  (one block)
#   vivado -mode batch -source vivado/vivado_ooc.tcl -tclargs secure_jpeg_top 8.0 (try 125 MHz)
# Reports in sim_build/vivado_<top>[_<period>ns]/: utilization.txt, utilization_hier.txt,
# timing.txt (WNS), power.txt (vectorless estimate). python vivado/parse_reports.py turns
# them into the paper table.
#
# The clock is declared in an XDC that is read BEFORE synthesis, so synthesis is
# timing-driven (declaring it only after synth_design would leave synthesis blind).
set top    [expr {[llength $argv] > 0 ? [lindex $argv 0] : "secure_jpeg_top"}]
set period [expr {[llength $argv] > 1 ? [lindex $argv 1] : "10.0"}]
set out    sim_build/vivado_$top
if {$period != 10.0} { set out ${out}_${period}ns }
file mkdir $out

read_verilog [glob rtl/*.v]
set_property include_dirs rtl/include [current_fileset]

set xdc [file join $out clock.xdc]
set f [open $xdc w]
puts $f "create_clock -name clk -period $period \[get_ports clk\]"
close $f
read_xdc -mode out_of_context $xdc

synth_design -top $top -part xc7z020clg400-1 -mode out_of_context -flatten_hierarchy rebuilt \
             -include_dirs rtl/include
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
puts "RESULT top=$top period=${period}ns WNS=${wns}ns -> reports in $out/"
puts "WNS >= 0 means the design meets ${period} ns. Estimated fmax = 1000 / (period - WNS) MHz."
