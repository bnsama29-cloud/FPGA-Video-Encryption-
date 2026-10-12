# Secure video transmission with hardware selective encryption

RVCE Experiential Learning (III Sem, Semiconductor Engineering), team CMOS Crusaders.

A JPEG/MJPEG encoder for the PYNQ-Z2 (Zynq-7020) that encrypts selected coefficient
bits **inside the encoder** with NIST Ascon-AEAD128 (SP 800-232) and seals every frame
with a 128-bit tag. VLC still plays the stream, but without the key the picture is
scrambled; the key holder verifies the tag and recovers the frame bit-exactly. Around
it: an authenticated feedback channel, key ratcheting, an attack-aware adaptive
defence, a live web dashboard, and the experiments for the paper.

**New to the repo? Start with [HELP_GUIDE.md](HELP_GUIDE.md)** — setup, how to run every
part, who does what, benchmarks, and what is left to do.

```
camera ──► encoder + Ascon (RTL / golden model) ──► UDP ──► channel (network + attacker) ──► receiver ──► viewer
                      ▲                                                                        │
                      └──────────── authenticated feedback (heartbeats, alerts) ◄──────────────┘
                 adaptive defence on the ARM: mode E2..E5, rekey, dead-man rule
```

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt

make test-model                 # golden model + contract + system tests        (~5 s)
make test-rtl                   # every Verilog block + top level in Icarus 12  (~30 s)
make xsim-icarus                # the Vivado XSim testbench, run in Icarus      (~10 s)

python -m link.run_all          # whole link + dashboard -> http://localhost:8000
```

In Vivado: `python vivado/gen_xsim_vectors.py`, then `bash vivado/run_xsim.sh` (Linux/WSL),
`vivado\run_xsim.bat` (Windows) or `vivado -mode gui -source vivado/xsim_project.tcl`.

## What is in here

| Folder | What | Main entry points |
|---|---|---|
| `model/` | Golden model = the referee. Frame level (`jpeg.py`) and the RTL's stage-level view (`hw.py`), proven byte-identical | `model.jpeg.encode_frame / receive_frame` |
| `rtl/` | Synthesizable Verilog-2001: colour, DCT, quantiser, RLE, selective encryption, Huffman, Ascon keystream + tag, AXI | `secure_jpeg_top.v` |
| `tb/` | cocotb testbenches, every block vs the model under random stalls | `make test-rtl` |
| `vivado/` | XSim self-checking testbench, run scripts, GUI project, out-of-context synthesis | `run_xsim.sh/.bat`, `vivado_ooc.tcl` |
| `hls/` | Vitis HLS DCT + quantiser (same arithmetic as the RTL) | `make hls-csim` |
| `link/` | System simulation: sender, channel/attacker, receiver, feedback, keys, defence, dashboard | `python -m link.run_all` |
| `experiments/` | Paper numbers: mode trade-off, attack scenarios, policy comparison, crypto benchmark, learned (GPU) attack | see HELP_GUIDE.md §6 |
| `scripts/` | Golden-model tools: image/video evaluation, MJPEG server + receiver, vector export | `scripts/run_video_eval.py` |
| `docs/` | Interface contract v2 (registers, nonce, tag, file format), testing guide | `docs/INTERFACES.md` |
| `configs/` | Settings shared by every node | `configs/default.toml` |

## Encryption modes

| Mode | Encrypted | In RTL |
|---|---|---|
| E0 | nothing (tag only) | yes |
| E1 | AC signs | yes |
| E2 | + DC-difference signs (default floor) | yes |
| E3 | + AC amplitude bits | yes |
| E4 | + DC amplitude bits | yes |
| E5 | E4 + keyed shuffle of the 16×16 MCUs (restart interval 1) | model only (RTL task) |

Sign and amplitude encryption never hides which coefficients are non-zero, so E1–E4
all leak an edge sketch to an eavesdropper; E5 removes it (measured: edge correlation
0.33–0.35 → 0.00). Details and numbers: HELP_GUIDE.md §7.

## Golden-model tools (unchanged usage)

```bash
python scripts/encode_image.py my_photo.jpg --out out_image         # every mode on one image
python scripts/make_test_video.py --out test_video.mp4 --frames 90
python scripts/run_video_eval.py --video test_video.mp4 --out results   # metrics, plots, videos
python scripts/mjpeg_server.py --video test_video.mp4 --mode E2 --tamper 7   # simple HTTP MJPEG demo
python scripts/receiver.py --url http://localhost:8080/stream.mjpg
python scripts/export_vectors.py --sample astronaut --size 64x64 --out vectors/astro64
```

`results/` holds outputs of an earlier run made with contract v1; re-run
`scripts/run_video_eval.py` before using any of those numbers.

## The contract (summary — full text in docs/INTERFACES.md)

* Ascon-AEAD128 per SP 800-232, checked against all 1089 official KATs in Python and RTL.
* Nonce = session_id (64 bit, LE) ‖ frame_ctr (63 bit) ‖ purpose bit; keystream bits LSB-first.
* Sign encryption inverts all amplitude bits of a coefficient (= exact sign flip).
* Tag over the 26-byte APP11 metadata + frame size **and** the scan, so mode, counter,
  session and size cannot be changed undetected.
* DCT / quantiser: the RTL's integer arithmetic (two-pass 13-bit DCT, reciprocal quantiser).
