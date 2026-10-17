@echo off
REM Run the self-checking testbench in Vivado XSim (Windows).
REM   1. Open "Vivado <version> Tcl Shell" (or call C:\Xilinx\Vivado\<version>\settings64.bat)
REM   2. cd to the repository root (no spaces in the path)
REM   3. python vivado\run_vivado_day.py vectors
REM   4. vivado\run_xsim.bat          (batch, prints XSIM RESULT: PASS/FAIL)
REM      vivado\run_xsim.bat gui      (waveform GUI)
REM      vivado\run_xsim.bat batch xsim_work_v3   (contract-v3 vectors: run_vivado_day.py vectors --v3)
REM   5. python vivado\run_vivado_day.py check
REM no -testplusarg VEC_DIR=...: cmd treats '=' as an argument separator and xsim printed its usage
REM text (bug #19); the testbench defaults to the current folder, which is xsim_work.
set WORK=xsim_work
if not "%2"=="" set WORK=%2
cd /d "%~dp0%WORK%" || (echo run python vivado\run_vivado_day.py vectors first & exit /b 1)
call xvlog -prj xsim_abs.prj -i "%~dp0..\rtl\include" || exit /b 1
call xelab -debug typical -top tb_secure_jpeg_top -snapshot tb_snap || exit /b 1
if "%1"=="gui" (
    call xsim tb_snap -gui
) else (
    call xsim tb_snap -R
)
