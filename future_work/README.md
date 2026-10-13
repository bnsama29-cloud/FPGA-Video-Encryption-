# Future work and polish — making the claims stronger

This folder holds the work that goes **beyond** the five role tasks of the simulation phase
(`docs/TEAM_CONTEXT.md` §8): getting onto the board, the fair baselines a reviewer will ask
for, a stronger attacker against E5, and the paper figures. It is the companion to
`docs/ROADMAP.md`, which has the full plan and dates. Give this README to Claude together
with `docs/TEAM_CONTEXT.md` when you work on anything here.

**Status legend:**

* ✅ built **and tested here**: in CI, see `tests/test_future_work.py`;
* 🧪 built, but needs hardware or a tool we did not have (Vivado, the board) to be tested;
* 📝 plan only: the spec is below, the code is yours to write.

---

## 1. What is in this folder

```
future_work/
├── board/
│   ├── pynq_driver.py        ✅ (mock) 🧪 (board)  driver for our IP: register sequence, DMA, readout
│   ├── board_sender.py       ✅ (mock) 🧪 (board)  the camera node on the PYNQ, plugs into link/
│   ├── sjpeg_bd_top.v        ✅ compiles/lints     block-design wrapper with AXI interface attributes
│   └── block_design.tcl      🧪                    Vivado: Zynq PS + AXI DMA + our IP -> .bit + .hwh
├── baselines/
│   ├── bench_software_codecs.py  ✅  libjpeg-turbo + AES-GCM / ChaCha20 / our selective, per frame
│   ├── energy_table.py           ✅  energy per frame from measured fps and power
│   └── power_template.csv            fill with board measurements
├── attacks/
│   └── jigsaw_attack.py      ✅  a jigsaw solver that tries to un-shuffle E5
├── figures/
│   ├── visual_security_grid.py   ✅  the paper figure: no key / eavesdropper / key holder per mode
│   └── format_compliance.py      ✅  which decoders open each mode (Pillow, OpenCV, skimage, ffmpeg, Chromium)
└── results/                       generated outputs (not in git)
```

Run everything from the repository root with `python -m future_work.<folder>.<script>`.

---

## 2. Results already produced here (simulation PC, 12–13 Oct 2026)

**Format compliance** (`python -m future_work.figures.format_compliance`): every mode, **E0–E5
including the shuffled E5**, decodes in Pillow, OpenCV, scikit-image, ffmpeg (MJPEG clip, which
is what VLC uses underneath) and Chromium. This is the table for the "plays in a normal player" claim.

**Jigsaw attack on E5** (`python -m future_work.attacks.jigsaw_attack`):

| Tiles given to the solver | Neighbours restored | Edge correlation of the solved picture |
|---|---|---|
| unencrypted, shuffled (sanity check; 3 photos) | **81–100%** | up to 1.00 |
| E5 = E4 + shuffle, replacement-attack tiles (3 photos + synthetic) | **0–2%** (≈ chance) | −0.05 … 0.04 |
| E5 if the attacker knew every position (upper bound) | — | 0.35–0.40 |

**What it means:** shuffling alone would be broken easily; our solver reassembles plain tiles. E5
works because E4's sign and amplitude encryption inside each block destroys the border clues a
jigsaw solver needs. That interplay is a nice point for the paper.

**Honest caveat:** this is one greedy solver, so the result is a lower bound on what E5 leaks.
Stronger solvers (Gallagher 2012, or learned compatibilities trained on the GPU) might do better.

**Visual-security figure** (`python -m future_work.figures.visual_security_grid`):
`results/visual_security_grid.png/.pdf`. One frame, three rows:

1. what any viewer shows (E1 leaks the scene, E2/E4 scramble, E5 shows shuffled blocks);
2. the eavesdropper's best effort (edge correlation E1 0.34, E2 0.35, E4 0.35, E5 + jigsaw 0.00);
3. the key holder (all bit-exact).

**Software baselines on a server CPU** (`python -m future_work.baselines.bench_software_codecs`):

| 640×480 | ms / frame | fps | plays |
|---|---|---|---|
| libjpeg-turbo (OpenCV) | 0.90 | ~1100 | yes |
| + full AES-128-GCM | 0.91 | ~1100 | **no** |
| + full ChaCha20-Poly1305 | 0.91 | ~1090 | **no** |
| + our selective E2 in Python, after encoding | 135 | 7 | yes |
| FPGA RTL estimate (1.64 cycles/px at 100 MHz) | 5.0 | ~199 | yes |

**Read this carefully before writing the paper.** A desktop CPU with libjpeg-turbo is about 5×
faster than our FPGA design, and full AES on it is practically free. The paper therefore must
**not** claim "faster than software". The fair comparison is on the **same board**:

* the PYNQ's 650 MHz Cortex-A9, which has no AES instructions and is much weaker than this CPU, vs
* our FPGA path;

measuring fps and **energy per frame** (§3.3). The Python selective row is also unfair: a C
implementation is planned (§4.1).

---

## 3. Getting onto the board

### 3.1 Build the overlay (🧪, Role 1 leads)

```bash
vivado -mode batch -source future_work/board/block_design.tcl      # from the repo root
```

It builds:

* the Zynq PS (DDR, FCLK0 = 100 MHz, GP0 master, HP0 slave, fabric interrupts);
* an **AXI DMA** in simple mode (MM2S → our `s_axis` pixels, our `m_axis` scan bytes → S2MM);
* our IP through `sjpeg_bd_top.v`, a wrapper that only adds interface attributes. The verified RTL is unchanged.

Output: `future_work/board/overlay/secure_jpeg.bit` + `.hwh`, plus utilization, timing and power reports.

The script has **not been run in Vivado yet**. Expect to fix small things on the first run (IP
versions, a pin name). Paste the first error into Claude with this README.

**If timing fails at 100 MHz:** set `CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ {50}` and report the
achieved clock honestly.

**If the PYNQ-Z2 board files are installed:** uncomment the `board_part` line; it gives exact PS presets.

### 3.2 First contact with the board

1. Copy `secure_jpeg.bit` and `secure_jpeg.hwh` (same base name) and this repo to the PYNQ
   (Jupyter upload or `scp`).
2. On the board:
   ```python
   from future_work.board.pynq_driver import PynqBackend, SecureJpegIP
   ip = SecureJpegIP(PynqBackend("secure_jpeg.bit"))    # checks VERSION == 0x5EC00200
   ```
   If the IP or DMA names differ, print `Overlay("secure_jpeg.bit").ip_dict.keys()` and pass
   `ip_name=` / `dma_name=`.
3. Encode one frame, rebuild the JPEG, and **compare it with the golden model byte for byte**:
   ```python
   ip.setup_session(key, session_id, 75)
   scan, tag = ip.encode(rgb, 2, 1)
   assert ip.build_jpeg(w, h, 2, 1, scan, tag) == hw.encode_frame(rgb, 75, 2, key, 1, session_id)["jpeg"]
   ```
   Do this for ≥ 50 frames and every mode 0–4 before anything else. If it differs, the board is
   wrong, not the model: check the clock, reset polarity, DMA sizes and the pixel word order
   `{pad, B, G, R}`.

**Develop without the board:** `SecureJpegIP(MockBackend())` behaves like the IP (bit-exact with
the RTL), so the driver, the sender and the network side can be finished before the bitstream exists.

### 3.3 Run the real link

**On the board** (the camera node: policy, keys and feedback on the ARM, encoding in the fabric):

```bash
python3 -m future_work.board.board_sender --bitfile secure_jpeg.bit \
    --set link.host=<laptop IP> --set link.bind_host=0.0.0.0 --set sender.source=webcam:0
```

**On the laptop** (channel/attacker, receiver, dashboard):

```bash
python -m link.run_all --no-sender --set link.bind_host=0.0.0.0 --set link.sender_host=<board IP>
```

`link.bind_host` (where to listen) and `link.sender_host` (where the channel sends feedback) are new
config keys. With the defaults everything still runs on one PC as before.

Try it without a board: `python -m future_work.board.board_sender --mock`, plus `python -m link.run_all --no-sender`.

Then rerun `experiments/scenarios/full_suite.json` and `benign.json` with the board as the sender.
Same attacks, now against real hardware.

### 3.4 Measure (the most valuable numbers in the paper)

1. **Software on the ARM.** On the PYNQ:
   `python3 -m future_work.baselines.bench_software_codecs --sizes 320x240 640x480 --frames 30`.
2. **FPGA fps.** Time a loop of `ip.encode` over 100 frames at each size and mode. Report the encoder
   alone and the full sender (headers + UDP).
3. **Power.** Use a USB power meter on the board's supply:
   * idle (booted, nothing running);
   * ARM-only encoding;
   * FPGA encoding, per mode.

   Wait for the reading to settle and average over 30 s.
4. Fill `baselines/power_template.csv`, then run `python -m future_work.baselines.energy_table future_work/baselines/power_template.csv`.
   That gives energy per frame (total and dynamic) and the ratio vs the ARM.

**Claim policy:** report what you measure. If the FPGA path uses less energy per frame than the
ARM, that is the headline. If it does not, report it; the playability and authentication claims stand anyway.

---

## 4. Polish work still to do (📝 specs; pick by priority)

Priority: **P1** = the paper is weak without it · **P2** = clearly stronger · **P3** = nice to have / future work section.

| # | Item | Priority | Who | Est. | Strengthens which claim |
|---|---|---|---|---|---|
| 4.1 | Selective encryption in **C** (fair software baseline) | P1 | 2 or 5 | 1–2 days | "in-encoder vs software selective" |
| 4.2 | Board measurements (§3.4) | P1 | 1 + 5 | 3–4 days after the bitstream | fps, energy, latency on real hardware |
| 4.3 | E5 restart markers in RTL | P2 | 1 | 3–5 days | E5 in hardware, not only in Python |
| 4.4 | E5 restart-interval study (N = 1, 2, 4, 8) | P2 | 5 | 1 day | overhead vs leakage trade-off |
| 4.5 | Stronger jigsaw attacker (Gallagher MST solver, or learned compatibility on the GPU) | P2 | 5 | 2–3 days | E5's security against a strong attacker |
| 4.6 | One shared Ascon core vs two (ablation) | P2 | 1 | 2 days | area vs throughput |
| 4.7 | Ascon-XOF128 KDF with official vectors | P2 | 2 | 1 day | standards-conformant key derivation |
| 4.8 | Multi-receiver prototype (per-receiver tags) | P3 | 4 + 3 | 3 days | scalability |
| 4.9 | Masked (side-channel protected) Ascon | P3 | 1 | future | physical-attack resistance |
| 4.10 | ROI encryption (faces / number plates stronger) | P3 | 5 | future | privacy-aware protection |
| 4.11 | H.264 / HEVC version | P3 | — | future | modern codecs |

### 4.1 Selective encryption in C (P1)

The Python baseline (135 ms/frame) is unfair. Write `future_work/baselines/c_selective/selective.c`:

* parse a baseline JPEG with standard tables;
* Huffman-decode;
* XOR the keystream onto sign and amplitude bits with the contract-v2 rule;
* re-encode the result;
* get the keystream from the official Ascon C reference (ascon-c, `asconaead128/ref` or `opt32`).

Expose it as a CLI (`selective in.jpg out.jpg key nonce mode`) or with ctypes.

Must produce **byte-identical** output to `model.jpeg.selective_encrypt_jpeg` (test it against 100
frames). Then add a row to `bench_software_codecs.py`. On the ARM this is the honest comparison
with our FPGA path.

### 4.3 E5 in RTL (P2)

1. `zigzag_rle.v`: reset `pred[0..2]` at each MCU start when `CTRL[4]` (new RESTART bit) is set.
2. `bit_packer.v`: at each MCU end, pad with 1-bits to a byte, then emit `FF D0+n` (n = MCU mod 8,
   none after the last MCU) without stuffing.
3. The keyed shuffle stays on the ARM. It only reorders the segments (find them by scanning for
   `FF D0..D7`, which cannot occur in stuffed data) before the tag is computed.

   Note: the tag covers the **shuffled** scan, so either the ARM computes the tag (Ascon on the ARM,
   as in fallback 3 of `docs/ROADMAP.md`), or a reorder buffer in BRAM shuffles in fabric before the tag unit.

Golden references: `model/entropy.py :: run_length_encode(restart=True), encode_segments,
join_restart`, `model/jpeg.py :: package_frame`. Add a mode-5 path to `model/hw.py` first, then
the cocotb test, then the RTL.

### 4.4 Restart-interval study (P2)

Add a `restart_interval` parameter (now fixed at 1) in:

* `run_length_encode` (reset every N MCUs);
* `mcu_segments` (N MCUs per segment);
* `package_frame` / `receive_frame` / `replacement_attack_jpeg` (DRI = N, `ceil(n_mcu / N)` segments,
  last one shorter).

Keep `make test-model` green. Measure leakage (`experiments/measure_mode_tradeoff.py` + `jigsaw_attack.py`)
and overhead for N = 1, 2, 4, 8, and plot both.

### 4.5 Stronger jigsaw attacker (P2)

Implement a Gallagher-style solver (minimum spanning tree over Mahalanobis gradient compatibility)
in `attacks/`, or train a small network on the GPU to score tile pairs, using **unencrypted** training
tiles from other videos. Reuse the sanity check in `tests/test_future_work.py`: it must beat the
greedy solver on plain tiles before its E5 numbers count.

### 4.6 Shared Ascon core (P2)

Today `keystream_gen` and `tag_unit` each have an Ascon core (~2.7K of ~5.3K LUTs, Yosys estimate).

* Build a variant with one core, time-shared by an arbiter.
* Measure LUTs (Vivado OOC) and cycles/pixel (`experiments/benchmark_crypto.py --rtl`) for both.
* Report it as an ablation: area vs throughput.

### 4.7–4.11

See `docs/TEAM_CONTEXT.md` (Role 2, step 4) for the XOF KDF, `docs/MULTI_RECEIVER.md` (Role 4 writes it; not yet in
the repo) for the multi-receiver design, and `docs/ROADMAP.md` §6 for the rest.

---

## 5. Which claim is backed by what (checklist for the paper)

| Claim in the paper | Evidence | Status |
|---|---|---|
| Output stays a valid, playable JPEG/MJPEG in every mode | `figures/format_compliance.py` (5 decoders × 6 modes) | ✅ |
| Key holder recovers the frame bit-exactly | tests + `visual_security_grid.py` row 3 | ✅ |
| E1–E4 leak an edge sketch; E5 removes it, even against a jigsaw solver | `measure_mode_tradeoff.py`, `jigsaw_attack.py` | ✅ synthetic + 3 photos; real clips: Role 5 |
| Learned (neural) attacker | `experiments/learned_attack.py` | 📝 needs GPU + clips (Role 5) |
| Every tampered / replayed / forged frame or feedback is rejected; reaction ≤ ~1.5 s | `experiments/scenario.py` suites | ✅ simulation; board run 📝 |
| Encryption adds 0 cycles to the encoder | `experiments/benchmark_crypto.py --rtl` | ✅ RTL simulation |
| Resource use and timing on the Zynq-7020 | `vivado/vivado_ooc.tcl`, `board/block_design.tcl` | 🧪 Role 1 |
| Faster / lower energy than software on the same board | §3.4 + `energy_table.py` | 📝 board |
| Fair software baseline | §4.1 (C selective) + libjpeg-turbo | 📝 |

---

## 6. Rules (same as the rest of the repo)

* Every script writes its numbers to `future_work/results/` or `sim_out/`. **Never type numbers by hand.**
* New code comes with a test in `tests/` (the board-only parts: a mock test).
* `make test` and `RUN_SLOW=1 python -m pytest tests/` must be green before a pull request.
* Claims follow the evidence table above: if a row is not ✅, the paper says "planned" or leaves it out.

---

## 7. Whole-system test record (13 Oct 2026, before this pull request)

| Check | Command | Result |
|---|---|---|
| Model + system unit tests | `make test` (model part) | 91 passed, 1 skipped (the slow end-to-end test) |
| RTL vs model (cocotb + Icarus, random stalls) | `make test` (RTL part) | 10 passed |
| Everything incl. end-to-end link and `test_future_work.py` | `RUN_SLOW=1 python -m pytest tests/` | 92 passed |
| Vivado testbench in Icarus | `make xsim-icarus` | CHECK RESULT: PASS |
| Lint | `make lint` | clean |
| Attack scenario | `python experiments/scenario.py --scenario experiments/scenarios/quick.json` | 4/4 attacks mitigated, mean 1.48 s, 0/45 false alarms |
| Board path without a board | `python -m link.run_all --no-sender --set link.bind_host=0.0.0.0 ...` + `python -m future_work.board.board_sender --mock ...` | 46/46 frames received OK, encoder = board, 0 tag failures |

Not testable here (needs Vivado or the PYNQ-Z2): `board/block_design.tcl` and `PynqBackend`.
They are marked 🧪 above; Role 1 confirms them on the first board day (§3.1–3.2).
