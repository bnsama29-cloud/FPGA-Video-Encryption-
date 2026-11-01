# results: every measured result

Snapshots of finished runs, as the scripts wrote them (no number typed by hand). Every folder with a README
says which script, commit and machine produced it. `README.md` in the repository root maps each result to
its script.

| Folder | Contents | Script |
|---|---|---|
| `board/` | Measured on the PYNQ-Z2: bit-exact gate and timing of the 1-, 2- and 4-lane board images, ARM baseline, post-quantum key exchange on the A9, energy, and the live-link runs with the board as the sender (attack suite, benign run, fault injection after the tag) | `software/system/board/first_contact.py`, `software/system/arm/arm_baseline.py`, `experiments/scenario.py --external-sender`, `experiments/hw_tamper.py` |
| `hardware/vivado/` | Post-route resources, timing and power (Vivado 2026.1), every board image | `hardware/vivado/run_vivado_day.py` |
| `hardware/lanes_rtl/`, `lanes_rtl_nbuf1/`, `lanes_rtl_yuyv/` | Lane-encoder throughput in cycle-accurate RTL simulation (1, 2, 4 lanes) | `experiments/lanes_rtl_throughput.py` |
| `hardware/hw_efficiency/` | Figures of merit (Mpixel/s per kLUT, Gbit/s, nJ/pixel) from `vivado/` and `lanes_rtl/` | `experiments/hw_efficiency.py` |
| `hardware/netlist/` | Gate-level one-bit slices of the Ascon S-box and the encryption stage, with schematics | `hardware/netlist/make_schematics.sh`; checked by `tests/test_netlist_slices.py` |
| `hardware/related/` | Published FPGA designs, numbers copied from each cited source | each row names its source |
| `hardware/yosys/` | Early Yosys resource estimate (superseded by `vivado/`) | `make synth` |
| `security/final/`, `security/extra/` | Outline leakage per level (95 % intervals), jigsaw solvers, learned attacker, standard metrics, restart interval | `experiments/measure_mode_tradeoff.py`, `software/system/attacks/jigsaw_attack.py`, `experiments/learned_attack.py` |
| `security/benchmark/` | SVE-Bench: our levels against four published schemes under four attacks | `experiments/benchmark_suite.py` (method: `docs/BENCHMARK_METHOD.md`) |
| `security/references/` | Attacks from the literature: LP sign-bit recovery, video identification from frame sizes | `experiments/sign_recovery.py`, `experiments/video_fingerprint.py` |
| `security/research/` | Research suite R1-R8 (cycles per pixel, lanes, rate control, size side channel, chosen plaintext) | see `docs/RESEARCH.md` |
| `security/first_runs/` | Format compliance in standard decoders, software codec baselines, first jigsaw run, visual-security grid | `software/system/figures/format_compliance.py`, `software/system/baselines/bench_software_codecs.py` |
| `simulation/` | System simulation of the link (attack suite, benign impairments, policy comparison and seeds), model benchmark and RTL cycles, Ascon rate, leakage on the synthetic scene and the real clips; `run_log_kaggle.json` is the log of the cloud run | `experiments/scenario.py`, `experiments/compare_policies.py`, `software/system/kaggle/kaggle_runs.py` |
| `results_tables.md` | All tables collected into one file | `python -m system.figures.results_tables` |
