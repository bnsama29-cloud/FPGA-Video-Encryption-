# Vitis HLS 2024.1:  cd secure-jpeg-sim && vitis_hls -f hardware/hls/run_hls.tcl
#   (or: vitis-run --mode hls --tcl hardware/hls/run_hls.tcl)
# First: python -m model.gen_vectors   (creates hardware/vectors/dct_quant_vectors.txt)
open_project -reset hls_dct_quant
set_top dct_quant
add_files hardware/hls/dct_quant.cpp -cflags "-Ihardware/hls"
add_files -tb hardware/hls/tb_dct_quant.cpp -cflags "-Ihardware/hls"
add_files -tb hardware/vectors/dct_quant_vectors.txt
open_solution -reset sol1 -flow_target vivado
set_part xc7z020clg400-1
create_clock -period 10 -name default
csim_design -argv "dct_quant_vectors.txt"
csynth_design
cosim_design -argv "dct_quant_vectors.txt"
export_design -format ip_catalog
exit
