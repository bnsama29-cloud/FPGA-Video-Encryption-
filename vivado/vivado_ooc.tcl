# Out-of-context synthesis + implementation in Vivado (no board needed).
# Gives the real LUT/FF/BRAM/DSP use, timing slack and a power estimate for the paper.
# Run from the repository root (or let vivado/run_vivado_day.py do it):
#   vivado -mode batch -source vivado/vivado_ooc.tcl                              (whole design, 100 MHz)
#   vivado -mode batch -source vivado/vivado_ooc.tcl -tclargs ascon_aead128_core  (one block)
#   vivado -mode batch -source vivado/vivado_ooc.tcl -tclargs secure_jpeg_top 8.0 (try 125 MHz)
#   vivado -mode batch -source vivado/vivado_ooc.tcl -tclargs secure_jpeg_top 10.0 LOG_MAXW 10
#                                                     (1024-pixel line buffers: memory sweep)
#   vivado -mode batch -source vivado/vivado_ooc.tcl -tclargs secure_jpeg_lanes_top 8.0 LANES 2 LOG_L 1
#                                                     (contract-v3 lane encoder, any number of
#                                                      parameter/value pairs after the period)
# Reports in sim_build/vivado_<top>[_<period>ns]/: utilization.txt, utilization_hier.txt,
# timing.txt (WNS), power.txt (vectorless estimate). python vivado/run_vivado_day.py parse turns
# them into the paper table.
#
# The clock is declared in an XDC that is read BEFORE synthesis, so synthesis is
# timing-driven (declaring it only after synth_design would leave synthesis blind).
set top    [expr {[llength $argv] > 0 ? [lindex $argv 0] : "secure_jpeg_top"}]
set period [expr {[llength $argv] > 1 ? [lindex $argv 1] : "10.0"}]
# optional 3rd + 4th arguments: a top-level parameter and its value, e.g. LOG_MAXW 10 (memory sweep,
# GUIDE B19). Two arguments, not LOG_MAXW=10: Windows cmd splits arguments at '=' (bug #19).
# More pairs may follow (LANES 2 LOG_L 1 ...).
set gens {}
for {set i 2} {$i + 1 < [llength $argv]} {incr i 2} {
    lappend gens "[lindex $argv $i]=[lindex $argv [expr {$i + 1}]]"
}
set gen [join $gens " "]
set out    sim_build/vivado_$top
if {$period != 10.0} { set out ${out}_${period}ns }
foreach g $gens { set out ${out}_[string tolower [string map {= ""} $g]] }
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
foreach g $gens { lappend gopt -generic $g }
# Implementation strategy (run 10). "perf" (default): register retiming in synthesis and the
# timing-driven directives of every implementation step, plus a post-route physical optimisation
# when the slack is negative. "default" = the flow of runs 1-9 (SJPEG_IMPL=default to reproduce them).
# "safe" = "perf" without the AggressiveExplore physical optimisation: in run 10 Vivado 2026.1 crashed
# (EXCEPTION_ACCESS_VIOLATION) inside phys_opt_design on the 4-lane encoder at 150 and 166 MHz, twice
# each (TESTING bug #38). run_vivado_day.py retries a job that crashed with SJPEG_IMPL=safe.
set impl [expr {[info exists ::env(SJPEG_IMPL)] ? $::env(SJPEG_IMPL) : "perf"}]
set sargs [list -top $top -part xc7z020clg400-1 -mode out_of_context -flatten_hierarchy rebuilt \
           -include_dirs rtl/include {*}$gopt]
if {$impl eq "perf" || $impl eq "safe"} {
    if {[catch {synth_design {*}$sargs -retiming} err]} {
        puts "WARNING: synth_design -retiming not accepted ($err); synthesising without retiming"
        synth_design {*}$sargs
    }
} else {
    synth_design {*}$sargs
}
report_utilization -file $out/utilization_synth.txt
if {$impl eq "perf"} {
    opt_design -directive Explore
    place_design -directive ExtraTimingOpt
    phys_opt_design -directive AggressiveExplore
    route_design -directive AggressiveExplore
    if {[get_property SLACK [get_timing_paths -max_paths 1 -nworst 1 -setup]] < 0} {
        phys_opt_design -directive AggressiveExplore
    }
} elseif {$impl eq "safe"} {
    opt_design -directive Explore
    place_design -directive ExtraTimingOpt
    phys_opt_design -directive Explore
    route_design -directive AggressiveExplore
} else {
    opt_design
    place_design
    phys_opt_design
    route_design
}
report_utilization    -file $out/utilization.txt
report_utilization    -hierarchical -hierarchical_depth 3 -file $out/utilization_hier.txt
report_timing_summary -max_paths 10 -file $out/timing.txt
report_power          -file $out/power.txt
set wns [get_property SLACK [get_timing_paths -max_paths 1 -nworst 1 -setup]]
puts "RESULT top=$top period=${period}ns $gen WNS=${wns}ns impl=$impl -> reports in $out/"
puts "WNS >= 0 means the design meets ${period} ns. Estimated fmax = 1000 / (period - WNS) MHz."
# The checkpoint is only needed by the power step. Written last and inside catch (run 10: Vivado died
# silently in write_checkpoint while a second run was routing, and the finished result was lost).
# A stale checkpoint of an older run is deleted first, so the power step can never use the wrong netlist.
file delete -force $out/routed.dcp
if {[catch {write_checkpoint -force $out/routed.dcp} err]} {
    puts "WARNING: checkpoint not written ($err): the power step will skip this design"
}
puts "CHECKPOINT written $out/routed.dcp"
