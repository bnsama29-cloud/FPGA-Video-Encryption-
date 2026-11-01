# Project rules for Claude Code

Hardware JPEG/MJPEG encoder with in-loop selective encryption (Ascon-AEAD128, NIST SP 800-232) for a PYNQ-Z2 (xc7z020clg400-1). Explain every change so that it can be defended in review; `README.md` describes the repository.

Six top-level folders: `hardware/`, `software/`, `experiments/`, `results/`, `tests/`, `docs/`. The Python packages `model`, `link`, `system` live in `software/` and keep their import names (pytest.ini, Makefile and conftest.py put `software/` on the path; `pip install -e .` for everything else). Each folder's README lists its contents; keep it in sync when adding files.

## Ground truth
- `software/model/` is the golden model and the referee. RTL in `hardware/rtl/` must match it bit for bit.
  `software/model/jpeg.py` (frame level) and `software/model/hw.py` (stage level, used by `hardware/tb/`) are one
  contract (v2); `tests/test_hw_equivalence.py` must stay green.
- Do NOT change the model to make an RTL test pass. Only change it if it contradicts ITU-T T.81 (JPEG) or NIST SP 800-232 (Ascon), and say so explicitly.
- Interfaces, register map, nonce layout and arithmetic are specified in `docs/INTERFACES.md`; keep it in sync with any change.

## Commands (activate the venv first: `source .venv/bin/activate`)
- `make test` full regression (~40 s). Must pass before you say a task is done.
- `RUN_SLOW=1 python -m pytest tests/` adds the end-to-end link test; `make xsim-icarus` runs the Vivado testbench.
- System simulation: `python -m link.run_all` (dashboard on :8000). Experiments: `experiments/*.py` (README.md, "Reproducing the results").
- `make one T=hardware/tb/<file>.py::<test> SEED=<n>` one test; `make waves T=...` with FST waveforms in `sim_build/<top>/`.
- `make bundle T=...` collects a failure into `debug_bundle.md`.
- Vivado (needs Vivado on PATH): `python hardware/vivado/run_vivado_day.py` (XSim, post-route OOC, block design, tables); board test `python -m system.board.first_contact`.
- `make lint`, `make synth` (Yosys estimate), `make hls-csim`, `make tables`, `make vectors`.

## Conventions
- RTL is Verilog-2001 for Icarus 12 and Vivado: `default_nettype none`, active-high synchronous `rst`, valid/ready handshakes (hold data while `valid && !ready`).
- Never edit generated files `hardware/rtl/include/*.vh` or `hardware/hls/dct_coeffs.h`; edit the model and run `make tables`.
- Each RTL file's header names its golden-model function ("Golden model: software/model/... :: fn()"). Keep that line accurate.
- Tests report the first mismatch (index, input, got, expected). Keep that standard in new tests.
- In cocotb testbenches, values read right after `RisingEdge` are pre-edge; react to DUT state at `FallingEdge`.

## When fixing a failure
1. Reproduce with the reported SEED. 2. Find the first mismatch and the RTL line responsible. 3. Smallest fix. 4. Re-run that test, then `make test`. 5. Add a regression test and a row in `docs/TESTING.md` §8 (bug log). 6. Summarise root cause, fix and evidence.

## System layer (software/link/) and experiments
- Nodes talk UDP only; never import one node from another. Shared code lives in `software/link/wire.py`, `keys.py`, `feedback.py`, `defence.py`.
- Every result must come from a script in `experiments/` (or `software/system/`, `hardware/vivado/`) that writes its numbers to `sim_out/`; never type numbers by hand.

## Results (`results/`: board, hardware, security, simulation)
- Snapshots of finished runs, exactly as the scripts wrote them; each folder's README names the run. Never edit a result file by hand; rerun the script and copy the output (`software/scripts/save_board_day.py` for board days).
- Manuscripts are not kept in this repository.
