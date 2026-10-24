# Playable but Private: in-encoder selective encryption with Ascon-AEAD128 for MJPEG video on an FPGA SoC

Companion repository of the paper of the same name (Aravind R, Suhas V J, Rishab H R, Samarth B N,
Vijaysurya B S, Chetana G; Department of Electronics and Communication Engineering, RV College of
Engineering, Bengaluru). It contains the hardware design, the golden model it is verified against, the
system and attack experiments, the board software for the PYNQ-Z2, and every result and script behind the
numbers in the paper.

## In one paragraph

A JPEG/MJPEG encoder for the Zynq-7020 FPGA SoC encrypts the sign and amplitude bits of selected DCT
coefficients **inside the entropy coder**, with a keystream from Ascon-AEAD128 (NIST SP 800-232). Huffman code
lengths never change, so every protection level is a valid JPEG that standard players and recorders accept;
only the key holder sees the picture. A 128-bit Ascon tag over the frame metadata and the coded scan rejects
modified, replayed and forged frames. The strongest level, E5, hides block positions with a keyed per-frame
permutation of restart segments that needs no frame buffer: the fabric codes and authenticates one segment
per macroblock, and the ARM core only reorders them. An authenticated feedback channel raises the protection
level when the receiver reports an attack.

```
            PYNQ-Z2 (Zynq-7020)
  ┌───────────────────────────────────────────────┐
  │ PL: colour 4:2:0, DCT, quantiser, zig-zag/RLE, │       UDP        ┌──────────────────────────────┐
  │     selective XOR, Huffman, Ascon keystream    │ ───────────────► │ receiver: replay window,     │
  │     + tag (1, 2 or 4 lanes)                    │   (attacker on   │ undo E5 order, verify tag,   │
  │ PS: headers, E5 order, key exchange + ratchet, │    the network)  │ decrypt, display             │
  │     adaptive policy                            │ ◄─────────────── │                              │
  └───────────────────────────────────────────────┘  authenticated   └──────────────────────────────┘
                                                      heartbeats, alerts
```

## Protection levels

| Level | Encrypted | Keystream bits |
|---|---|---|
| E0 | nothing (tag only) | 0 |
| E1 | AC sign bits | 1 per non-zero AC coefficient |
| E2 | + DC-difference sign bits (default) | |
| E3 | + AC amplitude bits | up to 11 per coefficient |
| E4 | + DC amplitude bits | |
| E5 | E4 + keyed per-frame permutation of all macroblocks (restart interval 1) | + the permutation |

Sign and amplitude encryption cannot hide which coefficients are non-zero, so E1–E4 leak an outline of the
scene; E5 removes it. The paper measures what each level leaks.

## Repository layout

| Folder | Contents |
|---|---|
| `model/` | Golden model in Python: Ascon-AEAD128 (passes all 1089 official known-answer tests), JPEG, selective encryption, E5, receiver. The referee for every RTL block. |
| `rtl/` | The encoder in Verilog-2001: single pipeline (`secure_jpeg_top.v`) and lane encoder for 1, 2 or 4 lanes with E5 (`secure_jpeg_lanes_top.v`). |
| `tb/` | cocotb testbenches for every RTL block and both top levels (Icarus Verilog 12), bit-exact against the model. |
| `vivado/` | Vivado 2026.1 flow: XSim testbench, out-of-context place and route, PYNQ-Z2 block designs, power with simulated activity, report parser. |
| `hls/` | Vitis HLS version of the DCT and quantiser (C simulation against the same tables). |
| `link/` | System layer: sender, network channel with attacker, receiver (with a C fast path), feedback, key exchange, defence policy, web dashboard. All nodes talk UDP. |
| `experiments/` | One script per result in the paper; each writes its numbers to `sim_out/`. |
| `system/` | Board software for the PYNQ-Z2 (`board/`: driver, bit-exact gate, camera node, block design, board images), the encoder in C on the ARM (`arm/`), software baselines and energy table (`baselines/`), jigsaw attacks (`attacks/`), figure scripts (`figures/`), and the script that reruns the GPU experiments in one cloud session (`kaggle/`). |
| `paper/` | Both manuscripts (6-page conference version and full-length IEEE Access version), the result snapshot they are built from (`paper/data/`), and the generator that turns it into every table, figure and number (`paper/make_assets.py`). |
| `docs/` | Interface specification, verification method and bug log, benchmark method, research notes. |
| `scripts/` | Setup check, demo key, end-to-end check with an emulated board, board-image check, board helpers. |
| `tests/` | Python tests: model, contract equivalence between the model's two views, system layer, experiments, paper assets. |

## Requirements

* Python 3.10 or newer: `pip install -r requirements.txt` (GPU experiments: `requirements-gpu.txt`).
* For the RTL tests: Icarus Verilog 12.
* For the hardware build: Vivado 2026.1 (any recent version should work).
* For the board: a PYNQ-Z2 with the PYNQ 3.1.1 image.
* A C compiler (gcc) is optional; with it, the receiver and the ARM baseline use their C paths.

## Quick start (no hardware)

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python scripts/check_setup.py          # one line per check, with the fix if something is missing
make test                              # golden model, system layer and every RTL block in Icarus
python -m link.run_all                 # the whole link with the attacker and the dashboard: http://localhost:8000
python scripts/emulated_board_check.py --quick   # every board program against an emulation of the bitstream
```

## Reproducing the results

Every number in both papers comes from a script that writes it to `sim_out/`; the snapshot used for the papers
is in `paper/data/` (each folder has a README saying which run produced it), and
`python paper/make_assets.py` regenerates every table, figure and number from it.
`tests/test_paper_assets.py` fails if a table in the manuscripts no longer matches the data.

| Result in the paper | Script | Data in `paper/data/` |
|---|---|---|
| Format compliance in four decoders | `system/figures/format_compliance.py` | `future_work_results/` |
| Outline leakage per level, 95 % intervals | `experiments/measure_mode_tradeoff.py` | `final/`, `extra/` |
| Benchmark against four published schemes (SVE-Bench) | `experiments/benchmark_suite.py` (method: `docs/BENCHMARK_METHOD.md`) | `benchmark/` |
| Jigsaw solvers, chosen-plaintext attack | `system/attacks/jigsaw_attack.py`, `experiments/chosen_plaintext.py` | `final/`, `research/` |
| Sign-bit recovery (linear program), video identification from frame sizes | `experiments/sign_recovery.py`, `experiments/video_fingerprint.py` | `references/` |
| Trained U-Net attacker, person recognition | `experiments/learned_attack.py`, `experiments/recognition.py` | `final/`, `extra/` |
| Attack suite and benign impairments (system simulation) | `experiments/scenario.py` | `simulation/` |
| Cycles per pixel, lane throughput (RTL simulation) | `experiments/stall_profile.py`, `experiments/lanes_rtl_throughput.py` | `research/`, `lanes_rtl*/` |
| Post-route resources, timing, power | `vivado/run_vivado_day.py` | `vivado/` |
| Hardware figures of merit | `experiments/hw_efficiency.py` | `hw_efficiency/` |
| Board: bit-exact gate and timing; ARM baseline; energy | `system/board/first_contact.py`, `system/arm/arm_baseline.py`, `system/baselines/energy_table.py` | `board/` |
| Board as the sender: attack suite, fault injection after the tag | `experiments/scenario.py --external-sender`, `experiments/hw_tamper.py` | `board/board_day_24oct/runs/` |

The GPU and long-CPU experiments (learned attacker, benchmark, recognition) rerun in one cloud session with
`system/kaggle/kaggle_runs.py`.

## Hardware

**Verification.** The golden model is the referee: every RTL block has a cocotb testbench with random
back-pressure that reports the first mismatch, the encoders are byte-exact with the model in Icarus and in
Vivado XSim for one, two and four lanes and every level, and a test proves the model's frame-level and
stage-level views byte-identical. `docs/TESTING.md` describes the method and keeps a log of every defect
found, with its root cause and regression test.

**Build.** With Vivado on the PATH:

```bash
python vivado/run_vivado_day.py --steps xsim ooc lanes parse          # XSim + out-of-context place and route
python vivado/run_vivado_day.py --steps bd_lanes bd_lanes4 parse      # PYNQ-Z2 board images (.bit + .hwh)
```

The board images used in the paper are in `system/board/overlay/`; `MANIFEST.md` lists the SHA-256 of each,
and `python scripts/publish_bitstreams.py --check` verifies a copy.

**Board.** Copy the repository to the PYNQ-Z2 and run, as root in the PYNQ Python environment:

```bash
python3 -m system.board.first_contact --bitfile system/board/overlay/secure_jpeg_lanes4.bit \
        --sizes 320x240 640x480 --frames 3 --timing-frames 50 --zero-copy      # bit-exact gate + timing
python3 -m system.board.board_sender --bitfile system/board/overlay/secure_jpeg_lanes.bit \
        --pq-kex --set link.host=<receiver IP> --set link.bind_host=0.0.0.0    # the board as the camera
```

and on the receiving machine `python -m link.run_all --no-sender --pq-kex --set link.sender_host=<board IP>`.
Every script has `--help`.

## Interfaces

`docs/INTERFACES.md` specifies the handshake convention, the AXI4-Lite register map, the nonce layout, the
tag, the keystream order and the JPEG container (contract v2 for the single pipeline, v3 for the lane
encoder).

## Data and privacy

The open sources (the Blender Foundation films and the Kodak images) can be downloaded and rerun. The four
private clips are copyrighted and are not distributed; they are identified by SHA-256 in
`system/clips_manifest.md`, and no frame of them is stored or shown. The key in `configs/default.toml` is a
public demo key; a deployment generates its own (`python scripts/demo_key.py`).
