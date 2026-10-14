#!/usr/bin/env bash
# Run the self-checking testbench in Vivado XSim (Linux / WSL).
#   source /tools/Xilinx/Vivado/<version>/settings64.sh      (once per terminal)
#   python vivado/gen_xsim_vectors.py                        (vectors from the golden model)
#   bash vivado/run_xsim.sh            # batch: prints XSIM RESULT: PASS/FAIL
#   bash vivado/run_xsim.sh gui        # opens the XSim waveform GUI
#   python vivado/check_xsim_output.py # rebuild JPEGs, run the receiver, save images
set -e
cd "$(dirname "$0")/xsim_work" || { echo "run python vivado/gen_xsim_vectors.py first"; exit 1; }
xvlog -prj xsim_abs.prj -i "$(cd ../../rtl/include && pwd)"
xelab -debug typical -top tb_secure_jpeg_top -snapshot tb_snap
if [ "$1" = "gui" ]; then
    xsim tb_snap -gui -testplusarg VEC_DIR=.
else
    xsim tb_snap -R -testplusarg VEC_DIR=. | tee xsim_run.log
    grep -q "XSIM RESULT: PASS" xsim_run.log
fi
