# Roadmap — what is left, the board plan, the paper, and future work

Companion to `docs/TEAM_CONTEXT.md` (give both files to Claude). Status as of 12 Oct 2026.
Roles: 1 Hardware & Vivado · 2 Cryptography & protocol · 3 Network & attacker ·
4 Receiver, dashboard & demo · 5 Defence, ML & visual security (RTX 4060).

**Code for the board phase and for the paper-strengthening items now lives in `future_work/`**;
its README (`future_work/README.md`) is the step-by-step guide, with status per item and a
claim-to-evidence checklist.

**Next:** `docs/VIVADO_ONE_DAY.md` (Vivado numbers + overlay + board first contact in one day), then
`docs/REMAINING_WORK.md` (board, polish, paper, with owners and dates). Those two supersede the dates below.

---

## 1. Where we are

| Part | Done | What "done" means / what is missing |
|---|---|---|
| Design + verified RTL (E0–E4) | ~95% | bit-exact with the model, all 1089 KATs in RTL; missing: Vivado run, E5 restart markers |
| System and security design | ~90% | contract v2, ratchet, authenticated feedback, dead-man rule, defence policies; missing: threat model doc, XOF-based KDF |
| Simulation results | ~85% after the 3–4 simulation days | missing: real video, repeated runs, learned attack |
| Real hardware on the PYNQ-Z2 | ~10% | only Vivado numbers after the simulation days; the board work is §3 |
| Paper | ~30% after the simulation days | section drafts; final numbers need the board |

**Overall:** about 60–65% of the project and 40–50% of the paper once the simulation days are over.
The board is the big remaining block. Without it we have a good simulation paper but not a
measured hardware paper.

---

## 2. Phase A — finish the simulation (13–16 Oct)

Detailed steps per role: `docs/TEAM_CONTEXT.md` §8. Checklist:

| # | Task | Role | Output | Done when |
|---|---|---|---|---|
| A1 | Everyone: setup, `make test`, `make xsim-icarus`, dashboard | all | — | all green on every laptop |
| A2 | Vivado XSim (batch + GUI) on the real tool | 1 | log + waveform screenshot | `XSIM RESULT: PASS` in Vivado |
| A3 | Out-of-context synthesis + implementation | 1 | utilization / timing / power for top, Ascon core, keystream, tag | WNS ≥ 0 at 100 MHz (or the critical path explained) |
| A4 | Threat model + nonce-uniqueness argument | 2 | `docs/THREAT_MODEL.md` | reviewed by one teammate |
| A5 | KDF on Ascon-XOF128 (only with official vectors) | 2 | code + test, or a documented plan | tests green |
| A6 | Repeated full-suite and benign runs (3–5 each), aggregate script | 3 | mean ± std attack table, false-alarm vs loss plot | table filled |
| A7 | Two new attacks (freeze/loop, targeted region) | 3 | code + tests + dashboard buttons | in `full_suite.json` |
| A8 | Record 3–4 real CCTV-like clips (different places) | 4 | `clips/` shared on Drive | shared by end of day 1 |
| A9 | Latency report per mode and under attack; freeze indicator | 4 | latency figure | figure in `sim_out/` |
| A10 | Multi-receiver design document | 4 | `docs/MULTI_RECEIVER.md` | reviewed |
| A11 | Leakage/cost on real clips | 5 | table (mean ± std over clips) | `[defence]` values updated if needed |
| A12 | Learned (GPU) attack, train and test on different clips | 5 | `sim_out/learned_attack/results.md` + examples | table filled |
| A13 | E5 restart-interval study (N = 1, 2, 4, 8) | 5 | leakage vs overhead plot | tests green |
| A14 | Learning scenario × 3 (fresh memory) | 5 | rounds plot with mean ± std | figure in `sim_out/` |
| A15 | Demo video (2 min) + dashboard screenshots | 4 | video | shown to mentor |

---

## 3. Phase B — the FPGA board (17 Oct – 12 Nov)

**Role 1 leads, but everyone has a part.** It is too much for one person in 3 weeks.

| # | Task | Owner | Details | Done when |
|---|---|---|---|---|
| B1 | Vivado block design | 1 | Zynq PS7 (DDR, FCLK0 = 100 MHz, GP0 master, HP0 slave) + **AXI DMA** (MM2S pixels → `s_axis`, S2MM `m_axis` → DDR, simple mode) + AXI interconnect + `secure_jpeg_top` packaged as IP (or as an RTL module reference) + `irq_done` to the PS. Constraints: only the clock. Generate the bitstream. | `.bit` + `.hwh` build without timing errors |
| B2 | PYNQ overlay smoke test | 1 | copy `.bit` / `.hwh` to the board; `Overlay(...)`; read `VERSION` = 0x5EC00200 over MMIO | register read works |
| B3 | Board driver `board/sender.py` | 2 + 1 | follows `tb/test_top.py::Encoder` exactly: key + session (+ `_HI`) + 128 QT reciprocals once; per frame WIDTH, HEIGHT, FRAME_CTR(+`_HI`), CTRL = 1 \| mode<<1; start DMA receive then send; wait for STATUS.DONE; read OUT_BYTES + TAG0–3; build the JPEG with `model/container.py` (or `model/hw.py :: build_frame`); send over UDP with `link/wire.py`. Reuse `link/keys.py` and `link/feedback.py` unchanged | first frame accepted by the laptop's receiver |
| B4 | Board-in-the-loop check | 1 | the same frames encoded on the board and by `model/hw.py` must be byte-identical (frames from SD card) | 100% identical over ≥ 50 frames |
| B5 | Video input | 4 | step 1: frames from the SD card / a video file decoded on the ARM; step 2: USB webcam (OpenCV on PYNQ); HDMI-in is future work | live camera through the board |
| B6 | Network and attacks against real hardware | 3 | board → laptop running `link.channel` + `link.receiver` + dashboard; rerun `full_suite` and `benign` with the board as sender | attack table on hardware |
| B7 | Defence on the board's ARM | 5 + 2 | run `link/defence.py` inside `board/sender.py` (feedback listener + policy); check the CPU load on the Cortex-A9 | dead-man + escalation work on the board |
| B8 | Measurements | 5 + 1 | fps and latency per mode and resolution; **power** per mode (USB power meter on the supply, or idle vs active difference) → energy per frame; `experiments/benchmark_crypto.py` **on the ARM** (software selective, AES-GCM, ChaCha20, Ascon in Python and ideally in C) | measured table on the board |
| B9 | Demo on hardware | 4 | camera → board → laptop dashboard, attack buttons, VLC playing the scrambled stream from the board | rehearsed in front of the mentor |

**Fallback ladder.** Decide at the end of each week; don't wait until the deadline.

1. DMA trouble → stream small frames through AXI-Lite or a simple AXI-Stream FIFO written by the ARM. Slow, but the hardware path still runs.
2. Timing not met at 100 MHz → 80 or 50 MHz clock. Report it honestly.
3. Tag unit problems → compute the tag on the ARM from the scan bytes (keystream XOR stays in the fabric).
4. 640×480 too slow end to end → 320×240.
5. Webcam trouble → frames from the SD card. The measurements are still real.

**Risks to watch.**

- **Python on the ARM is slow.** Building headers and UDP sending may limit fps; move that to C or numpy if needed.
- **DMA buffer setup.** Use PYNQ's `allocate()` and call `flush` / `invalidate` correctly.
- **Pixel byte order.** The DUT expects `{pad, B, G, R}`, with R in bits [7:0].
- **Frame size.** Width and height must be multiples of 16.

---

## 4. Phase C — paper (13 Nov – 15 Dec)

| # | Task | Owner | When |
|---|---|---|---|
| C1 | Final experiment runs on the board + simulation (scripts only, mean ± std) | all | 13–22 Nov |
| C2 | Section drafts (see `TEAM_CONTEXT.md` §10 for who writes what) | all | 23 Nov – 2 Dec |
| C3 | Figures: architecture, waveform, visual-security grid, learned-attack examples, attack table, rounds plot, latency, resources, power | owners of each result | with C2 |
| C4 | Related-work table vs prior FPGA / selective-encryption work, normalised (device named) | 2 + team lead | with C2 |
| C5 | Internal review, mentor review, plagiarism check, IEEE template + PDF eXpress | all | 3–12 Dec |
| C6 | Submission-ready PDF | team lead | **15 Dec** |
| C7 | Choose the venue; check deadlines and page limits on the official sites | team lead | early Nov |

---

## 5. What strengthens the paper (in order of impact)

1. **Measured board numbers.** fps, latency and power per mode on the PYNQ-Z2. This is the single biggest upgrade; simulation-only hardware papers are weak.
2. **A fair comparison on the same board.**
   - Compare in-encoder encryption vs software selective vs full-stream AES-GCM / ChaCha20 / Ascon on the Cortex-A9.
   - Report energy per frame.
   - This turns "0 extra cycles" into a real system advantage, or honestly shows where it isn't one.
3. **The learned (GPU) attack on real video.** The strongest evidence of how much each mode really protects.
4. **Statistics.** Several real clips and repeated runs; mean ± std on every table.
5. **The E5 restart-interval trade-off curve.** Leakage vs bitrate is a clean, original result.
6. **A one-page security argument.** Threat model + nonce uniqueness + what is and is not protected.
7. **A visual-security figure.** Original | E1 | E2 | E4 | E5 as the attacker sees them | decrypted.
8. **A comparison table with prior FPGA work.** LUTs, fps, cipher, integrity and playability vs Kishore 2015, Bağbaba & Örs 2015, Gladis Kurian & Chen 2025 and Ascon FPGA cores, with each device named.
9. **Ablations.**
   - One shared Ascon core vs two (area vs throughput).
   - Reaction time vs `window_s` / heartbeat period.
   - Bandit vs threshold under a mixed attack schedule.
10. **Format compliance evidence.** Frames open in VLC, ffmpeg, Pillow, OpenCV and a browser (a small table).

1–4 make a solid IEEE conference paper; 5–10 make it strong and give it a shot at a journal later.

---

## 6. Future work (for the paper's last section, not for the deadline)

**Hardware**
- E5 in RTL: restart markers in `zigzag_rle.v` / `bit_packer.v`, the shuffle on the ARM or in a BRAM reorder buffer.
- Live HDMI or camera input at 720p30 or 1080p30 (mjpegZero-class performance).
- Share one Ascon core between keystream and tag (smaller), or unroll rounds (faster).
- Side-channel-protected (masked) Ascon cores.
- Attack detection and the defence policy in hardware instead of on the ARM.
- An ASIC estimate (synthesis to a standard-cell library).

**Security and protocol**
- Ascon-XOF128 / CXOF128-based KDF (if not done in Phase A) and a key-exchange or provisioning step instead of a pre-shared master key.
- A jigsaw-solver attack against E5, and stronger shuffles (per-component, multi-level).
- Region-of-interest encryption: protect faces and number plates more than the background.
- Multiple receivers with per-receiver tags, revocation and tiered access (guard sees a preview, admin sees everything).

**Codec and system**
- The same in-encoder idea for H.264 / HEVC (CABAC / CAVLC-compliant selective encryption).
- A learning defence beyond the bandit (contextual Thompson sampling or a small RL agent) and evaluation under adaptive attackers.
- A real wireless link (drone or Wi-Fi), with loss and latency measured in the field.
- Long-run tests (hours) for stability, counter wrap and rekey behaviour.
- A privacy and compliance discussion (India's DPDP Act 2023) for CCTV and medical deployments.

---

## 7. Dates at a glance

| Date | Milestone |
|---|---|
| 16 Oct | simulation phase done (Phase A), all PRs merged, CI green |
| 24 Oct | B1–B2: bitstream + register access on the board |
| 31 Oct | B3–B4: board frames byte-identical with the model, received by the laptop |
| 7 Nov | B5–B8: live input, attacks against the board, measurements |
| 12 Nov | B9: hardware demo; project complete |
| 22 Nov | final numbers (C1) |
| 2 Dec | full paper draft |
| 15 Dec | submission-ready paper |
