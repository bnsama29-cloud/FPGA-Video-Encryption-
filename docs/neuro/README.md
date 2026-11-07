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

**Status (7 Nov 2026).** Contract n1, revision 2. Model, RTL and all experiment programs are written; the RTL
top level (`nv_top`) is bit-exact against the model on every `neuro.vectors` case. No paper number exists yet:
the Kaggle (N3-N6), Vivado (N2) and board (N10) runs are still to be made. Branch `neuromorphic`, worktree
`neuro_wt`. Paper 1's board day takes precedence over every paper-2 step.

**Where things live** (all inside the six top-level folders; full layout in `DESIGN.md` §10):

| Path | Contents |
|---|---|
| `docs/neuro/DESIGN.md` | The contract: threat model, packet layout, keys and nonces, receiver rules, levels, padding, hardware pipeline, register map, model API, experiments N1-N11 with pass criteria |
| `docs/neuro/BASELINES.md` | Du 2021 and Zhang 2024 read from the PDFs, with every choice we had to make marked |
| `docs/neuro/LITERATURE.md` | Every reference, with how it was verified; UNVERIFIED ones marked |
| `docs/neuro/notes/` | Source notes the design was built from (literature, EVT 2.0 spec, paper-1 crypto, tooling) |
| `software/neuro/` | Golden model (sender, receiver, packets, keys, levels, Feistel, padding), stage view `hw.py`, test cases and vectors `vectors.py`, `stats.py`, `cycle_model.py`, datasets, `baselines/` (Du, Zhang) |
| `hardware/rtl/neuro/` | `nv_top` and its blocks (packetizer, trailer, XOR, Feistel, table generator, FIFO, tag, output mux, registers, U-round Ascon core) |
| `hardware/tb/neuro/` | cocotb tests per block and `test_nv_top.py` (every vector case, random backpressure; `FULL=1` for all 32) |
| `hardware/vivado/neuro/` | N2: `vivado_ooc_neuro.tcl`, `run_vivado_neuro.py` |
| `software/system/board/neuro/` | N10: block-design wrapper and TCL, driver (`MockBackend` = model), first contact, replay |
| `software/system/kaggle/kaggle_neuro.py`, `software/scripts/get_events.py` | Kaggle job (data, N5 cache, N3, N6, N4 and the CPU experiments on real data); dataset download with manifests |
| `experiments/neuro_*.py` | One script per experiment (table in `experiments/README.md`); `experiments/neuro/fpe_design_numbers.py` gives the §4.3 design numbers |

**Order of work.** BASELINES.md → model + tests → vectors → RTL (N1) → laptop experiments (N4b, N7, N8, N9, N11)
→ Kaggle (N5 cache, N3, N6, N4) → Vivado (N2) → board (N10).
