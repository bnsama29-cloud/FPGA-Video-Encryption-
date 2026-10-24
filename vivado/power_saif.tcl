# Post-route power with SIMULATED switching activity .
#
# report_power without activity data guesses a 12.5 % toggle rate for every internal net (the
# "vectorless" estimate in power.txt). This script reads the activity the XSim testbench recorded
# while it encoded real frames (activity.saif) and reports power again, so the number reflects
# what the encoder actually does in a given mode.
#
# Run by python vivado/run_vivado_day.py --steps power (after ooc / lanes). By hand, from the
# repository root:
#   vivado -mode batch -source vivado/power_saif.tcl -tclargs \
#       sim_build/vivado_secure_jpeg_top/routed.dcp vivado/xsim_power_v2_E2/activity.saif \
#       tb_secure_jpeg_top/dut sim_build/vivado_secure_jpeg_top/power_saif_v2_E2.txt
#
# Arguments: <routed checkpoint> <SAIF file> <testbench path of the DUT> <output report>
# The SAIF comes from RTL simulation, so only nets whose names survive synthesis (registers,
# ports, most named wires) are matched; Vivado keeps its default activity for the rest. The
# "Internal nodes activity" confidence line and the matched-net summary printed by read_saif
# say how much was matched; run_vivado_day.py parse puts both next to the number.
if {[llength $argv] < 4} {
    error "usage: power_saif.tcl <routed.dcp> <activity.saif> <strip path> <out report>"
}
lassign $argv dcp saif strip out
open_checkpoint $dcp
read_saif -strip_path $strip $saif
report_power -file $out
puts "RESULT power_saif report=$out"
