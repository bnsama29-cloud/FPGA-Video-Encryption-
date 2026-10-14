@echo off
REM Run the self-checking testbench in Vivado XSim (Windows).
REM   1. Open "Vivado <version> Tcl Shell" (or call C:\Xilinx\Vivado\<version>\settings64.bat)
REM   2. cd to the repository root (no spaces in the path)
REM   3. python vivado\gen_xsim_vectors.py
REM   4. vivado\run_xsim.bat          (batch, prints XSIM RESULT: PASS/FAIL)
REM      vivado\run_xsim.bat gui      (waveform GUI)
REM   5. python vivado\check_xsim_output.py
REM no -testplusarg VEC_DIR=...: cmd treats '=' as an argument separator and xsim printed its usage
REM text (bug #19); the testbench defaults to the current folder, which is xsim_work.
cd /d "%~dp0xsim_work" || (echo run python vivado\gen_xsim_vectors.py first & exit /b 1)
call xvlog -prj xsim_abs.prj -i "%~dp0..\rtl\include" || exit /b 1
call xelab -debug typical -top tb_secure_jpeg_top -snapshot tb_snap || exit /b 1
if "%1"=="gui" (
    call xsim tb_snap -gui
) else (
    call xsim tb_snap -R
)
