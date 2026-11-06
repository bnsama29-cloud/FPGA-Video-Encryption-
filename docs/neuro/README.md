# Paper 2: authenticated, format-preserving encryption of event-camera streams

**What it is.** A sensor-side encryptor for event-camera (DVS) data on the PYNQ-Z2 (xc7z020clg400-1, 100 MHz).
It cuts an EVT 2.0 word stream into 1024 µs packets, protects each packet at one of five levels and appends one
16-byte Ascon-AEAD128 tag (NIST SP 800-232) per packet. Paper 1 (the JPEG/MJPEG encoder in this repository)
provides the Ascon core, the keystream generator, the key exchange and the nonce layout; paper 2 reuses them
without editing them. Target journal: *Neuromorphic Computing and Engineering* (IOP).

| Level | Protects | Payload stays EVT 2.0 |
|---|---|---|
| V0 | tag only | yes |
| V1 | polarity (keystream XOR) | yes (hides polarity only) |
| V2 | positions: keyed mixed-radix Feistel on Z_W × Z_H, new tables every packet, fixed latency | yes |
| V3 | V2 + polarity + low 6 timestamp bits; optional dummy-event padding | yes |
| V4 | full AEAD of payload and trailer (baseline) | no |

**Status.** Design contract n1 (revision 2, 7 Nov 2026). No code yet. Branch `neuromorphic`, worktree
`neuro_wt`. Paper 1's board day takes precedence over every paper-2 step.

**Where things live** (all inside the six top-level folders; full layout in `DESIGN.md` §10):

| Path | Contents |
|---|---|
| `docs/neuro/DESIGN.md` | The contract: threat model, packet layout, keys and nonces, receiver rules, levels, padding, hardware pipeline, register map, model API, experiments N1-N11 with pass criteria |
| `docs/neuro/LITERATURE.md` | Every reference, with how it was verified; UNVERIFIED ones marked |
| `docs/neuro/notes/` | Source notes the design was built from (literature, EVT 2.0 spec, paper-1 crypto, tooling) |
| `docs/neuro/BASELINES.md` | (to write first) Du 2021 and Zhang 2024 equations from the PDFs |
| `software/neuro/` | (planned) golden model, the referee for the RTL |
| `hardware/rtl/neuro/`, `hardware/tb/neuro/`, `hardware/vectors/neuro/` | (planned) `nv_*.v`, cocotb tests, generated vectors |
| `hardware/vivado/neuro/` | (planned) N2 synthesis and power |
| `software/system/board/neuro/`, `software/system/kaggle/kaggle_neuro.py` | (planned) board replay (N10), Kaggle job (N3-N6) |
| `experiments/neuro/fpe_design_numbers.py` | design numbers behind §4.3 (writes `sim_out/neuro_fpe/`); later `experiments/neuro_*.py` |

**Order of work.** BASELINES.md → model + tests → vectors → RTL (N1) → laptop experiments (N4b, N7, N8, N9, N11)
→ Kaggle (N5 cache, N3, N6, N4) → Vivado (N2) → board (N10).
