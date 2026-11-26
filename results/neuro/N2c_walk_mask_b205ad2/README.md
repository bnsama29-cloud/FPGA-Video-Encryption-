# N2c_walk_mask_b205ad2

Vivado 2026.1 on the laptop (xc7z020clg400-1, post-route OOC at 100 MHz), 27 Nov 2026, commit `b205ad2`:
`python hardware/vivado/neuro/run_vivado_neuro.py --steps walk mask parse --jobs 1 --resume`. Builds: N2b cycle-walking
baseline `nv_feistel_walk` (1280 x 720 on the 2048 x 1024 binary domain, K = 4 and 8 unrolled passes) and the masking
ablation (`nv_ascon_round_dom`, seven-AND DOM round after bug #84, against `nv_ascon_round_reg`). All four meet timing.
Copied unchanged: `sim_out/neuro/n2/hw_tables.{md,json}` and, per build, `builds/<build>/{utilization,timing,power,impl,...}.txt`.
The hw_tables row "No post-route reports: nv_top_u2_maxw34_maxh34" is an older unfinished folder on the laptop, not part
of this run; the N2 nv_top and nv_feistel numbers are in `N2_vivado_169f7e3`.
