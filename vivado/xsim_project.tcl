# Creates a Vivado project with every RTL source and the XSim testbench, then
# launches the behavioural simulation (waveforms in the GUI).
#   python vivado/run_vivado_day.py vectors                 (first, from the repo root)
#   vivado -mode gui -source vivado/xsim_project.tcl  (from the repo root; no spaces in the path)
# Project goes to vivado/proj/ (not in git). Re-running recreates it.
set root [file normalize [file join [file dirname [info script]] ..]]
set vec  [file join $root vivado xsim_work]
if {![file exists [file join $vec commands.txt]]} {
    error "No vectors in $vec -- run: python vivado/run_vivado_day.py vectors"
}
create_project secure_jpeg_sim [file join $root vivado proj] -part xc7z020clg400-1 -force
add_files [glob [file join $root rtl *.v]]
set_property include_dirs [file join $root rtl include] [get_filesets sources_1]
set_property top secure_jpeg_top [get_filesets sources_1]
add_files -fileset sim_1 [file join $root vivado tb_secure_jpeg_top.v]
set_property include_dirs [file join $root rtl include] [get_filesets sim_1]
set_property top tb_secure_jpeg_top [get_filesets sim_1]
set_property top_lib xil_defaultlib [get_filesets sim_1]
set_property -name {xsim.simulate.runtime} -value {all} -objects [get_filesets sim_1]
set_property -name {xsim.simulate.xsim.more_options} -value "-testplusarg VEC_DIR=$vec" -objects [get_filesets sim_1]
update_compile_order -fileset sources_1
update_compile_order -fileset sim_1
launch_simulation
puts "Look for 'XSIM RESULT: PASS' in the Tcl console. Useful signals: dut/u_enc (selective_enc),"
puts "dut/u_ks (keystream_gen), dut/u_tag (tag_unit: state, pref, pleft), dut/u_regs."
