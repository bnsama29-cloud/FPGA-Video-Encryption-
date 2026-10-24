# Project rules for Claude Code

Hardware JPEG/MJPEG encoder with in-loop selective encryption (Ascon-AEAD128, NIST SP 800-232) for a PYNQ-Z2 (xc7z020clg400-1). Explain every change so that it can be defended in review; `README.md` describes the repository.

## Ground truth
- `model/` is the golden model and the referee. RTL in `rtl/` must match it bit for bit.
  `model/jpeg.py` (frame level) and `model/hw.py` (stage level, used by `tb/`) are one
  contract (v2); `tests/test_hw_equivalence.py` must stay green.
- Do NOT change the model to make an RTL test pass. Only change it if it contradicts ITU-T T.81 (JPEG) or NIST SP 800-232 (Ascon), and say so explicitly.
- Interfaces, register map, nonce layout and arithmetic are specified in `docs/INTERFACES.md`; keep it in sync with any change.

## Commands (activate the venv first: `source .venv/bin/activate`)
- `make test` full regression (~40 s). Must pass before you say a task is done.
- `RUN_SLOW=1 python -m pytest tests/` adds the end-to-end link test; `make xsim-icarus` runs the Vivado testbench.
- System simulation: `python -m link.run_all` (dashboard on :8000). Experiments: `experiments/*.py` (README.md, "Reproducing the results").
- `make one T=tb/<file>.py::<test> SEED=<n>` one test; `make waves T=...` with FST waveforms in `sim_build/<top>/`.
- `make bundle T=...` collects a failure into `debug_bundle.md`.
- Vivado (needs Vivado on PATH): `python vivado/run_vivado_day.py` (XSim, post-route OOC, block design, tables); board test `python -m system.board.first_contact`.
- `make lint`, `make synth` (Yosys estimate), `make hls-csim`, `make tables`, `make vectors`.

## Conventions
- RTL is Verilog-2001 for Icarus 12 and Vivado: `default_nettype none`, active-high synchronous `rst`, valid/ready handshakes (hold data while `valid && !ready`).
- Never edit generated files `rtl/include/*.vh` or `hls/dct_coeffs.h`; edit the model and run `make tables`.
- Each RTL file's header names its golden-model function ("Golden model: model/... :: fn()"). Keep that line accurate.
- Tests report the first mismatch (index, input, got, expected). Keep that standard in new tests.
- In cocotb testbenches, values read right after `RisingEdge` are pre-edge; react to DUT state at `FallingEdge`.

## When fixing a failure
1. Reproduce with the reported SEED. 2. Find the first mismatch and the RTL line responsible. 3. Smallest fix. 4. Re-run that test, then `make test`. 5. Add a regression test and a row in `docs/TESTING.md` §8 (bug log). 6. Summarise root cause, fix and evidence.

## System layer (link/) and experiments
- Nodes talk UDP only; never import one node from another. Shared code lives in `link/wire.py`, `keys.py`, `feedback.py`, `defence.py`.
- Every claim in the paper must come from a script in `experiments/` that writes its numbers to `sim_out/`; never type numbers by hand.

## Paper (`paper/`)
- `paper/data/` is the result snapshot the paper is built from; `paper/make_assets.py` turns it into `paper/tables/*.tex` and `paper/figures/`. Never edit generated tables.
- Cite only references verified in `paper/refs.bib` (each entry says how it was checked). Never invent a reference, a page number or a result; mark unknowns `\TODO{}`.
- State as a result only what a script reproduces from `paper/data/`; everything else is a limitation or future work.
