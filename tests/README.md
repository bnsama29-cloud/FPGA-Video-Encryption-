# tests: Python test suite

`make test` runs these (`make test-model`, ~1 min) and the RTL testbenches in `hardware/tb/`. Every test
reports the first mismatch (index, input, got, expected). `RUN_SLOW=1` adds the end-to-end link runs.

| Area | Tests |
|---|---|
| Golden model | `test_ascon_kat.py` (all 1089 NIST known-answer vectors), `test_pipeline.py`, `test_hw_equivalence.py` (frame-level and stage-level views byte-identical) |
| Gate level | `test_netlist_slices.py` (the drawn one-bit slices simulated exhaustively against the model) |
| System layer | `test_link.py`, `test_pq_kex.py`, `test_padding.py`, `test_fastrx.py`, `test_dashboard.py`, `test_two_laptop.py`, `test_demo_key.py` |
| Board software | `test_system.py`, `test_arm_software.py`, `test_board_buttons.py`, `test_board_checkpoint.py`, `test_board_clock.py`, `test_board_clock_sync.py`, `test_hw_tamper.py` |
| Experiments | `test_research.py`, `test_new_experiments.py`, `test_policy_seeds.py`, `test_video_to_frames.py`, `test_vivado_reports.py` |
| Results and setup | `test_board_results.py` (every listed board file present), `test_save_board_day.py`, `test_run_setup.py` |
