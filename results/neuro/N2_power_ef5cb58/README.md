# N2_power_ef5cb58

Laptop, Vivado 2026.1, 22 Nov 2026, commit `ef5cb58` (bug #79): `run_vivado_neuro.py --steps power parse --power-npy
ibmGestureTest/user24_fluorescent/0.npy`. For each workload, `tb_nv_power.v` replayed the stimulus of
`experiments/neuro_power_vectors.py` in XSim bit-exact against the model (`power_run.log`), the SAIF was read into the
routed `nv_top` U = 2, 1280 x 720 checkpoint (`hardware/vivado/power_saif.tcl`), and `neuro_hw_tables.py` computed
energy per event. Copied unchanged: `sim_out/neuro/n2/hw_tables.{md,json}` (supersedes `N2_vivado_169f7e3`'s table:
same builds plus the power section), `power/power_saif_*.txt`, `power/nv_power_*/{vectors,sim_result}.json`.
Hashes: `MANIFEST.md`.
