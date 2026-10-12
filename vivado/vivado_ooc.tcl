# Out-of-context synthesis + implementation in Vivado (no board needed).
# Gives the real LUT/FF/BRAM/DSP use, timing slack at 100 MHz and a power
# estimate for the paper (walkthrough step 9).
#   cd secure-jpeg-sim
#   vivado -mode batch -source scripts/vivado_ooc.tcl            (whole design)
#   vivado -mode batch -source scripts/vivado_ooc.tcl -tclargs ascon_aead128_core
set top [expr {[llength $argv] > 0 ? [lindex $argv 0] : "secure_jpeg_top"}]
set out sim_build/vivado_$top
file mkdir $out
read_verilog [glob rtl/*.v]

synth_design -top $top -part xc7z020clg400-1 -mode out_of_context -flatten_hierarchy rebuilt -include_dirs rtl/include
create_clock -name clk -period 10.000 [get_ports clk]
opt_design
place_design
route_design
report_utilization    -file $out/utilization.txt
report_utilization    -hierarchical -file $out/utilization_hier.txt
report_timing_summary -file $out/timing.txt
report_power          -file $out/power.txt
puts "Reports in $out/ -- check WNS >= 0 in timing.txt before trusting any result."
