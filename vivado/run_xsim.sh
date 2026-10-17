#!/usr/bin/env bash
# Run the self-checking testbench in Vivado XSim (Linux / WSL).
#   source /tools/Xilinx/Vivado/<version>/settings64.sh      (once per terminal)
#   python vivado/run_vivado_day.py vectors                        (vectors from the golden model)
#   bash vivado/run_xsim.sh            # batch: prints XSIM RESULT: PASS/FAIL
#   bash vivado/run_xsim.sh gui        # opens the XSim waveform GUI
#   bash vivado/run_xsim.sh batch xsim_work_v3   # contract-v3 vectors (run_vivado_day.py vectors --v3)
#   python vivado/run_vivado_day.py check # rebuild JPEGs, run the receiver, save images
set -e
cd "$(dirname "$0")/${2:-xsim_work}" || { echo "run python vivado/run_vivado_day.py vectors first"; exit 1; }
xvlog -prj xsim_abs.prj -i "$(cd ../../rtl/include && pwd)"
xelab -debug typical -top tb_secure_jpeg_top -snapshot tb_snap
if [ "$1" = "gui" ]; then
    xsim tb_snap -gui
else
    xsim tb_snap -R | tee xsim_run.log
    grep -q "XSIM RESULT: PASS" xsim_run.log
fi
