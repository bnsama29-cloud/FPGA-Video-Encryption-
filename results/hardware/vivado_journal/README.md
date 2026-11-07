# Vivado journal sweep (X8-X10, X13), 7 Nov 2026

Unchanged contents of `vivado_results_20261107_0510.zip`, written by
`python hardware/vivado/run_vivado_day.py --steps xsim ooc lanes power parts bd_tamper parse --periods 8.0 7.0 6.667 --maxw 9 10 --parallel 1`
on the team laptop (Vivado 2026.1), branch `journal-version` at commit b45a23f (working tree marked dirty in `sim_out/vivado/run_info.json`).
Tables: `sim_out/vivado/vivado_tables.md`. Missing builds: Spartan-7 50 and ZU3EG (device not installed,
"Invalid -part"), 4 lanes on the Zynq-7010 (17 974 LUT > 17 600 available).

Only xc7z020clg400-1 (the PYNQ-Z2 part) is kept. The builds for other parts were removed from this folder on
7 Nov; their rows in `sim_out/vivado/vivado_tables.md` and `vivado_results.json` are not used.
