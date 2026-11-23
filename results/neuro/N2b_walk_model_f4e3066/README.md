# N2b_walk_model_f4e3066

Cloud workspace, 23 Nov 2026, commit `f4e3066`: `python experiments/neuro_walk_ablation.py --keys 16`. Every address of
every sensor geometry walked through the eight-round binary table Feistel (pow2 and balanced domains) for 16 packet
keys; walk length statistics and the dense-input throughput of the K = 4 RTL ablation `nv_feistel_walk`, whose stall
model (1 + 16 (calls - K) frozen clocks per long walk) is checked by `hardware/tb/neuro/test_nv_feistel_walk.py`.
Copied unchanged: `sim_out/neuro/n2b/walk_stats.{json,md}`.
