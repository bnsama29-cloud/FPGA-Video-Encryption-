# Out-of-context synthesis + implementation of the paper-2 encryptor (nv_top or one nv_* block), DESIGN §8.2 N2.
# Run from the repository root (or let hardware/vivado/neuro/run_vivado_neuro.py do it):
#   vivado -mode batch -source hardware/vivado/neuro/vivado_ooc_neuro.tcl -tclargs nv_top 10.0 U 2
#   vivado -mode batch -source hardware/vivado/neuro/vivado_ooc_neuro.tcl -tclargs nv_top 10.0 U 4 MAXW 346 MAXH 260
#   vivado -mode batch -source hardware/vivado/neuro/vivado_ooc_neuro.tcl -tclargs nv_ascon_core_u 10.0 U 4
# Arguments: top, clock period in ns, then parameter/value pairs (two arguments each; Windows cmd splits at '=').
# Reads the four reused paper-1 files and hardware/rtl/neuro/*.v; paper-1's vivado_ooc.tcl is not edited.
# Reports in sim_build/vivado_neuro_<top>[_<period>ns][_<param><value>...]/: utilization.txt,
# utilization_hier.txt (per nv_sdp_ram instance: RAMB18 count), timing.txt, power.txt (vectorless unless a SAIF
# is given in NV_SAIF), routed.dcp.
set top    [expr {[llength $argv] > 0 ? [lindex $argv 0] : "nv_top"}]
set period [expr {[llength $argv] > 1 ? [lindex $argv 1] : "10.0"}]
set part xc7z020clg400-1
set gens {}
for {set i 2} {$i + 1 < [llength $argv]} {incr i 2} {
    lappend gens "[lindex $argv $i]=[lindex $argv [expr {$i + 1}]]"
}
set out sim_build/vivado_neuro_$top
if {$period != 10.0} { set out ${out}_${period}ns }
foreach g $gens { set out ${out}_[string tolower [string map {= ""} $g]] }
file mkdir $out

read_verilog [list hardware/rtl/ascon_round.v hardware/rtl/ascon_aead128_core.v hardware/rtl/keystream_gen.v \
                   hardware/rtl/skid_buf.v]
read_verilog [glob hardware/rtl/neuro/*.v]

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
set sargs [list -top $top -part $part -mode out_of_context -flatten_hierarchy rebuilt {*}$gopt]
if {[catch {synth_design {*}$sargs -global_retiming on} err]} {
    puts "WARNING: synth_design -global_retiming not accepted ($err); synthesising without retiming"
    synth_design {*}$sargs
}
report_utilization -file $out/utilization_synth.txt
opt_design -directive Explore
place_design -directive ExtraTimingOpt
phys_opt_design -directive Explore
route_design -directive AggressiveExplore
# No post-route phys_opt_design -directive AggressiveExplore: Vivado 2026.1 crashed there on nv_top
# (EXCEPTION_ACCESS_VIOLATION, 7 Nov 2026), as on paper 1's lane encoder (TESTING bug #38).
report_utilization    -file $out/utilization.txt
report_utilization    -hierarchical -hierarchical_depth 4 -file $out/utilization_hier.txt
report_timing_summary -max_paths 10 -file $out/timing.txt
if {[info exists ::env(NV_SAIF)] && [file exists $::env(NV_SAIF)]} {
    read_saif $::env(NV_SAIF)
    report_power -file $out/power_saif.txt
}
report_power -file $out/power.txt
set wns [get_property SLACK [get_timing_paths -max_paths 1 -nworst 1 -setup]]
puts "RESULT top=$top period=${period}ns $gens WNS=${wns}ns -> reports in $out/"
file delete -force $out/routed.dcp
if {[catch {write_checkpoint -force $out/routed.dcp} err]} {
    puts "WARNING: checkpoint not written ($err)"
}
