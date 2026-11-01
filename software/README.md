# software: golden model, system layer and board software

Python packages (imported as `model`, `link`, `system`) plus helper scripts. `pip install -r
requirements.txt` installs the packages in editable mode; `make` and `pytest` find them without that; on
the board, `export PYTHONPATH=$PWD/software` from the repository root.

| Folder | Contents |
|---|---|
| `model/` | The golden model and the referee for the RTL. Ascon-AEAD128 exactly as NIST SP 800-232 (`ascon.py`, passes all 1089 known-answer tests), colour and DCT/quantiser bit-exact with the RTL, entropy coding, selective encryption, JPEG container. Two views of one contract: frame level (`jpeg.py`) and stage level (`hw.py`, used by `hardware/tb/`); `tests/test_hw_equivalence.py` keeps them identical. `gen_rtl_tables.py` writes `hardware/rtl/include/*.vh`. |
| `link/` | System layer, every node a process talking UDP: sender (digital twin of the camera), channel with the attacker, receiver (C fast path in `native/`), authenticated feedback (SRTCP-like), key schedule and forward-secure ratchet (`keys.py`), hybrid ML-KEM-768 + X25519 session key (`kex.py`), adaptive defence policy, web dashboard (`static/`). |
| `system/` | PYNQ-Z2 board software (driver, bit-exact gate, board as camera, block design, board images in `board/overlay/`), the encoder in C on the ARM, software baselines and energy table, jigsaw attacks, figure scripts, the cloud rerun script. See `system/README.md`. |
| `scripts/` | Setup check, demo key, end-to-end check against an emulated board, board helpers (results, clock), bitstream check, older model tools (`tools.py`), Yosys estimate script. |
| `configs/` | `default.toml`: every setting of the link. The key in it is a public demo key; `scripts/demo_key.py` makes a private one. |

## Commands (from the repository root)

```bash
python software/scripts/check_setup.py           # what is missing on this machine, with the fix
python -m link.run_all                           # whole link + attacker + dashboard on http://localhost:8000
python software/scripts/emulated_board_check.py --quick   # every board program against an emulated bitstream
python -m model.gen_rtl_tables                   # = make tables
```

Every script has `--help`. Interfaces and the key/nonce layout: `docs/INTERFACES.md`.
