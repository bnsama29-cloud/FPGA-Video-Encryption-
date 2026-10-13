# Team context for Claude — Secure Video Transmission Using Hardware Selective Encryption

> **How to use this file (for us humans)**
> 1. Open a new Claude chat (claude.ai) and attach or paste this whole file, or in Claude Code
>    inside the repo say: *"Read docs/TEAM_CONTEXT.md"*.
> 2. Then say who you are and which role you have, e.g.
>    *"I'm Rishab, I'm doing Role 3. I have finished step 1. Help me with step 2."*
> 3. Paste error messages, logs and your results into the chat as you go. Claude cannot see your laptop.
> 4. For the board phase, the paper plan and future work, also give Claude `docs/ROADMAP.md`.
>
> The file is long on purpose: it holds everything a fresh chat needs. Each role's section
> (§8) also works on its own.

---

## 0. Instructions for Claude (the assistant reading this)

You are helping one member of a 5-person undergraduate team (RVCE Bangalore, ECE, III semester,
Experiential Learning). The project and its current state are described below. Work like this:

- **Ask which role (1–5) the person has, if they did not say**, and their OS (Windows + WSL,
  Linux, or Mac). Then help them through their role's tasks in §8, **in order**, one step at a time.
- **Explain the reasoning** behind fixes and design choices, not just the fix. The team must
  defend everything in a viva and in an IEEE paper, and they prefer learning-oriented explanations.
- **The golden model in `model/` is the referee.** Never suggest changing it to make an RTL test
  pass, unless it contradicts ITU-T T.81 (JPEG) or NIST SP 800-232 (Ascon). In that case say so explicitly.
- **Never invent numbers.** Every result in the paper must come from a script in `experiments/`
  that writes to `sim_out/`. If the person reports a number, ask which command produced it.
- **Every code change needs a test**, and `make test` must pass before they open a pull request.
  Work on a branch per task, open a PR, and let a teammate review it.
- Stay inside the person's role (§8, "Owns"). If a change touches another role's files, tell them
  to coordinate with that teammate.
- Don't over-claim. §6 lists the honest limitations and the claims the paper must not make.
- You only see what they paste. When debugging, ask for the exact command, the full error and the
  `random seed = N` line. In the repo, `make bundle T=<test>` writes `debug_bundle.md` to paste.

---

## 1. The project in one page

| | |
|---|---|
| Title | Secure Video Transmission Using Hardware Selective Encryption (Semiconductor Engineering theme) |
| Team | CMOS Crusaders: Aravind R, Suhas VJ, Rishab HR, Samarth BN, Vijaysurya BS |
| Mentor / evaluator | Dr. Chetana G (mentor), Dr. Deepika P (evaluator), Dept. of ECE, RVCE |
| Board | PYNQ-Z2 (Zynq-7020, xc7z020clg400-1): ARM Cortex-A9 + FPGA fabric, 100 MHz target clock |
| Repo | https://github.com/bnsama29-cloud/FPGA-Video-Encryption- (branch `main`) |
| Deadlines | simulation done by ~16 Oct 2026; working project by ~12 Nov 2026; IEEE paper ready by **15 Dec 2026** |

**Idea.** A JPEG/MJPEG video encoder in the FPGA encrypts *selected* coefficient bits (signs and
amplitudes) **inside the encoder**, before Huffman coding, using NIST Ascon-AEAD128 (SP 800-232, Aug 2025).

- Code lengths don't change, so the output is still a valid JPEG: **VLC plays it, but the picture
  is scrambled**.
- Every frame carries a 128-bit authentication tag, so the receiver detects tampering, replay and
  injection, and the key holder recovers the frame **bit-exactly**.

**Added in phase 2** (all built, in simulation):

- an authenticated feedback channel from receiver to sender;
- a forward-secure key ratchet;
- an attack-aware adaptive defence (rule-based and a learning "bandit");
- a live web dashboard;
- a 6th mode E5 (keyed block shuffle);
- experiment scripts for the paper.

**Phase-1 references** (verified):

- [1] Van Droogenbroeck & Benedett, ACIVS 2002 (JPEG selective encryption of appended bits).
- [2] Puech & Rodrigues, EUSIPCO 2005 (AES on selected DCT coefficients, medical images).
- [3] Hirose, Imaizumi & Kiya, *Electronics* 13(11), Art. no. 2016, 2024 (JPEG bitstream encryption + restart-marker block shuffling).
- [4] Bağbaba & Örs, ELECO 2015 (FPGA JPEG + TEA cipher).
- [5] Gladis Kurian & Chen, *Electronics* 14(13) 2668, 2025 (Ascon-AEAD128 on Artix-7 with Bloom-filter replay protection). The first author's surname is "Gladis Kurian".
- [6] Turan et al., NIST SP 800-232, Aug 2025.
- [7] Boyadjis et al., IEEE TCSVT 27(4) 2017 (H.264/HEVC selective encryption).

Also important: Kishore, Kumar & Patil, *J. Real-Time Image Processing* 2015 ("FPGA based simple and fast JPEG encryptor", the closest prior FPGA work), and Lin et al., *JVCIR* 2024 (recovering DCT sign bits, an attack on sign-only encryption).

---

## 2. Architecture

```
 camera / video ─► [ FPGA: RGB→YCbCr 4:2:0 → 8x8 DCT → quantiser → zig-zag + run-length
                     → SELECTIVE ENCRYPTION (XOR Ascon keystream onto sign/amplitude bits)
                     → Huffman → bit packer ]  ─► scan bytes ─► ARM adds JPEG headers + APP11 (tag)
                     [ Ascon tag unit absorbs 26-byte header prefix + scan → 128-bit tag ]
                                                         │ UDP (Ethernet)
                                                         ▼
                     network / attacker  ─►  receiver (laptop): verify tag, check counter,
                                                 decrypt, show; sends authenticated feedback
                                                         │
 sender's ARM runs the adaptive defence ◄────────────────┘  (heartbeats + alerts)
 (mode E2..E5, rekey, dead-man rule)
```

**In simulation today:**

- **Sender:** the golden Python model, or the real Verilog per frame in Icarus.
- **Network and attacker:** simulated (`link/channel.py`).
- **Receiver and dashboard:** run on one PC.

Every part is a separate process talking real UDP, so later the PYNQ board replaces only the sender.

---

## 3. The contract (v2): facts every role must know

The full specification is in `docs/INTERFACES.md`. Section 7 there explains why each choice was made.

| Item | Definition |
|---|---|
| Cipher | Ascon-AEAD128 per SP 800-232; 64-bit words loaded little-endian; RTL does 1 round per clock. All 1089 official KAT vectors (`vectors/LWC_AEAD_KAT_128_128.txt`) pass in Python **and** RTL |
| Nonce (128 bit) | bytes 0–7 = `session_id` (64-bit, LE); bytes 8–15 = `frame_ctr << 1 | purpose` (LE). So Ascon state x3 = session_id, x4 = {frame_ctr[62:0], purpose}. purpose 0 = keystream, 1 = tag. Function: `model/ascon.py :: make_nonce(session_id, frame_ctr, purpose)` |
| Keystream | Ascon-AEAD128 ciphertext of an all-zero message, no AD, under (K, N_enc). Bit i = bit (i mod 8) of byte (i div 8), i.e. **LSB first** |
| Sign encryption | if keystream bit 0 is 1, **invert all `size` bits** of the amplitude field. In JPEG's ones' complement coding that is exactly v → −v |
| Amplitude encryption | keystream bits 1..size−1 XOR the low size−1 field bits (modes E3 for AC, E4 for DC) |
| Tag | Ascon-AEAD128 tag under (K, N_mac), empty message, AD = **26-byte prefix ‖ scan bytes (after 0xFF stuffing)** |
| 26-byte prefix | `'SJV1'`, version 2, mode, session_id (8 B big-endian), frame_ctr (8 B BE), width (2 B BE), height (2 B BE). Model: `model/hw.py :: tag_prefix()` |
| APP11 segment (0xFFEB, 38 B) | the first 22 prefix bytes + the 16-byte tag. Normal viewers ignore it. Always parse JPEGs by walking segments, never by searching for 0xFF 0xC0 (that byte pair can occur inside APP11) |
| Modes | E0 tag only · E1 AC signs · E2 + DC-difference signs (**default floor**) · E3 + AC amplitudes · E4 + DC amplitudes · E5 = E4 + keyed MCU shuffle (restart interval 1 MCU, Fisher–Yates under a separately derived key; **Python model only, not in RTL yet**) |
| DCT | two passes of 8-tap 13-bit integer DCT (`rtl/dct_stage.v`), rounding shifts 11 and 15 |
| Quantiser | multiply by the 17-bit reciprocal `R = (131072 + Q) // (2Q)`, then `(abs(F)·R + 2^15) >> 16`; DC clamped to −1024..1023, AC to ±1023 |
| Colour | `Y = (77R + 150G + 29B + 128) >> 8` etc., 4:2:0 average `(a+b+c+d+2) >> 2`; frame width and height must be multiples of 16 for the RTL |
| Registers (AXI-Lite) | CTRL 0x00 (bit 0 START, bits 3:1 MODE) · STATUS 0x04 · VERSION 0x08 = 0x5EC00200 · WIDTH 0x10 · HEIGHT 0x14 · FRAME_CTR 0x18 (low 32) · SESSION_ID 0x1C (low 32) · KEY0–3 0x20–0x2C (write-only) · OUT_BYTES 0x30 · TAG0–3 0x34–0x40 · QT_ADDR 0x44 · QT_DATA 0x48 · SESSION_ID_HI 0x4C · FRAME_CTR_HI 0x50 |
| Two model views | `model/jpeg.py` = frame level (used by the receiver, system and experiments); `model/hw.py` = stage level (used by the RTL testbenches). `tests/test_hw_equivalence.py` proves they produce identical bytes |

**Key schedule** (`link/keys.py`):

- `K_fb = KDF(master, "feedback")` is the feedback key.
- `K_video[0] = KDF(master, "video")`, and each rekey steps `K_video[e+1] = KDF(K_video[e], "ratchet", e+1)`. The step is one-way, so old keys are erased (forward secrecy).
- `session_id = 48-bit random base << 16 | epoch`.
- The KDF is an Ascon-AEAD128 tag under nonce (session 0, ctx, 1). Session id 0 is reserved for the KDF.

**Feedback** (`link/feedback.py`):

- Every message is Ascon-AEAD128 encrypted and authenticated under `K_fb`, with a 64-entry replay window, the same idea as SRTCP (RFC 3711).
- The receiver sends a heartbeat every 0.5 s plus rate-limited alerts.
- **Dead-man rule:** if no valid heartbeat arrives for 3 s, the sender goes to maximum mode and rekeys.

---

## 4. What has been done and verified (as of 12 Oct 2026)

**Merged in PR #1. CI (GitHub Actions) runs every test on every PR.**

- **One contract.** The original golden repo and the Verilog repo had drifted apart: 335 of 348 scan bytes differed in E2. Both were unified on contract v2.
- **Security hole fixed.** The old RTL tag did not cover the mode byte, so an E2 → E1 downgrade was undetectable. Now fixed and tested.
- **RTL fully verified.** Every block is bit-exact with the model under random stalls (cocotb + Icarus 12). The top level is bit-exact for E0–E4 with 64-bit session ids and counters above 2³².
- **Vivado testbench** `vivado/tb_secure_jpeg_top.v`, in plain Verilog-2001. It has been run in **Icarus only**: 5 frames pass, and it correctly fails when expectations are corrupted. **Nobody has run it in Vivado yet.**
- **System simulation** (`link/`), with tests including a 20-second end-to-end UDP run.
- **Experiments** (`experiments/`) and **CI** (`.github/workflows/tests.yml`).

**Measured numbers** (simulation, single runs, synthetic CCTV scene unless stated):

| Result | Value | Produced by |
|---|---|---|
| RTL throughput | 1.64 cycles/pixel → ≈199 fps at 640×480 and ≈66 fps at 720p, **if** 100 MHz timing closes | `experiments/benchmark_crypto.py --rtl` |
| Extra cycles for encryption | **0** in every mode (E0–E4 take identical cycles) | same |
| Resources (estimate only) | ~5.3K LUT, ~10% of Zynq-7020 (Yosys estimate, **not** Vivado) | `make synth` (old) |
| Leakage = edge correlation of the eavesdropper's best image (0 = nothing) | E0 0.996 · E1 0.336 · E2 0.327 · E3 0.352 · E4 0.352 · **E5 0.000** | `experiments/measure_mode_tradeoff.py` |
| Encrypted share of payload bits | E1 11.5% · E2 13.5% · E3 25% · E4 28.7% · E5 30.3% | same |
| E5 file-size overhead | +13% (320×240), +21% (640×480): 2 marker bytes + padding per 16×16 block | `benchmark_crypto.py` |
| Attack suite (11 attacks, threshold policy) | 11/11 detected and mitigated, mean 0.72 s, **0/125** false alarms | `scenario.py --scenario experiments/scenarios/full_suite.json` |
| Benign network (1–6% loss, delay, jitter, reorder) | **0/149** false alarms | `scenarios/benign.json` |
| Learning scenario (5 rounds × bit-flip + replay) | threshold: 1.26 s mean, cost 0.189 · bandit: 1.30 s, cost 0.164 (−13%). Bandit per round: bit-flip 4.3 → 1.3 → 1.3 → 0.3 → 1.3 s; replay 3.3 → 0.3 s from round 2 | `compare_policies.py --scenario .../learning.json --policies threshold bandit` |
| PC cost (640×480) | software selective encryption 117–222 ms/frame (Python); full-stream AES-GCM (OpenSSL) **< 0.01 ms** | `benchmark_crypto.py` |
| End-to-end latency (Python sender) | median ~70 ms, p95 ~110 ms at 320×240, 10 fps | scenario summaries |

**Bugs found and fixed:** see `docs/TESTING.md` §8, rows 5–11. They make good report material.

---

## 5. What is NOT done yet (the work for the next days and weeks)

| Missing | Why it matters | Role |
|---|---|---|
| Vivado XSim run + post-route resources, WNS, power | Reviewers do not accept Yosys estimates. This is the main hardware result | 1 |
| Restart-marker support in RTL (for E5 on the board) | E5 exists only in Python | 1 (stretch) |
| Threat model, nonce-uniqueness argument, KDF on Ascon-XOF128 | the security section of the paper | 2 |
| Repeated runs (mean ± std), 2 new attacks, tuning on benign loss | reaction times vary 0.3–1.4 s with window alignment | 3 |
| Real video clips, latency analysis, multi-receiver design, demo video | only a synthetic scene so far | 4 |
| Learned (GPU) attack on real video, E5 restart-interval study, repeated learning runs | the strongest security evidence | 5 |
| Board bring-up (Vivado block design, PYNQ driver, real fps, latency, power) | needed to claim any energy or speed advantage | all, after simulation |
| Multiple receivers | designed only (Role 4 writes the design doc) | later |

**Update 13 Oct:** the simulation is complete (Kaggle: `future_work/kaggle/kaggle_complete.py`). The Vivado step is
scripted for one day in `docs/VIVADO_ONE_DAY.md`; everything after it, with owners and dates, is in
`docs/REMAINING_WORK.md`. Read those two first.

Much of this has a head start in `future_work/` (PYNQ driver tested on a mock, Vivado block design script,
board sender, software baselines, energy table, jigsaw attack on E5, visual-security figure, format
compliance). Read `future_work/README.md` before starting any board or paper-polish task: it says what is
tested, what is untested until the board exists, and which claim each script supports.

---

## 6. Honest limitations and claims to avoid (the paper must respect these)

- **The sketch leak.** Sign and amplitude encryption never hides *which* coefficients are non-zero, so E1–E4 all leak an edge sketch, and E3/E4 don't reduce it. E5 hides block positions, but a jigsaw-solving attacker might partly reorder blocks (not evaluated).
- **E5 overhead.** E5 costs 13–21% bitrate at restart interval 1, and the RTL doesn't support it yet.
- **Passive eavesdroppers are invisible.** The defence reacts only to *active* attacks; a passive eavesdropper is handled only by the floor mode (E2).
- **Loss vs jamming.** The receiver can't tell benign loss from partial jamming. Only near-total suppression (≥90% frame loss) escalates.
- **Reaction time.** It is bounded by the 1 s decision window plus the 0.5 s heartbeat.
- **KDF.** It uses Ascon-AEAD128 as a PRF instead of Ascon-XOF128.
- **No side-channel protection** of the Ascon cores.
- **Speed argument.** On a PC, full-stream AES-GCM is almost free. So the argument must be:
  - playability (a standard JPEG);
  - **0 added hardware cycles**, no buffering;
  - per-frame authentication of header + content;
  - the board's Cortex-A9 has no AES instructions, which must be **measured** before any energy claim.
- **Claims to avoid:**
  - "first JPEG selective encryption" — false since 2002;
  - "first FPGA JPEG encryption" — false since 2015;
  - "post-quantum secure" — Ascon is symmetric;
  - "secure against all attacks";
  - any number not produced by a script.
- **Defensible novelty:**

  > To our knowledge, the first FPGA-SoC MJPEG encoder that embeds NIST SP 800-232 Ascon-AEAD128
  > keystream encryption of coefficient sign and amplitude bits at the entropy-coding stage, keeps
  > the stream playable, and authenticates every frame. It adds an authenticated feedback loop
  > that adapts the protection level to observed attacks, and we measure the visual-security,
  > bitrate, throughput, area and reaction-time trade-offs.

---

## 7. Repo, environment, commands, rules

**Layout**

```
model/        golden model: ascon.py, color.py, dct_quant.py, entropy.py, selective.py, container.py,
              jpeg.py (frame level), hw.py (stage level), metrics.py, tables.py, testimage.py
rtl/          Verilog-2001: secure_jpeg_top.v + 14 blocks; include/*.vh are GENERATED (make tables)
tb/           cocotb testbenches (common.py, test_*.py)
vivado/       tb_secure_jpeg_top.v, gen_xsim_vectors.py, check_xsim_output.py, run_xsim.sh/.bat,
              xsim_project.tcl, xsim.prj, vivado_ooc.tcl
hls/          Vitis HLS DCT + quantiser
link/         sender, channel, receiver, dashboard (+ static/dashboard.html), keys, feedback,
              defence, wire, sources, backends, config, run_all, buslog
experiments/  scenario.py, scenarios/*.json, compare_policies.py, measure_mode_tradeoff.py,
              benchmark_crypto.py, learned_attack.py
tests/        test_ascon_kat.py, test_pipeline.py, test_hw_equivalence.py, test_link.py
docs/         INTERFACES.md, TESTING.md (bug log §8), DEBUGGING_WITH_CLAUDE.md, TEAM_CONTEXT.md (this)
configs/      default.toml (shared by all nodes; override with --set section.key=value)
sim_out/      generated results (not in git)
```

**Environment**

- **Windows:** use WSL Ubuntu and keep the repo inside `~/`, not `/mnt/c`.
- **Python** 3.10+ (3.10 needs `tomli`, which `requirements.txt` installs automatically).
- **Icarus Verilog 12** is required for the RTL tests. Ubuntu 24.04: `sudo apt install iverilog`. Ubuntu 22.04 ships 11, so build 12 from source.
- **Vivado / Vitis 2023.2+ ML Standard (free)** runs on Windows; only Role 1 needs it.
- **GPU (Role 5):** the CUDA build of PyTorch (`requirements-gpu.txt`).

**Setup**

```bash
git clone https://github.com/bnsama29-cloud/FPGA-Video-Encryption-.git && cd FPGA-Video-Encryption-
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
make test-model      # ~5 s, all pass
make test-rtl        # ~30 s, 10 RTL test groups pass (needs Icarus 12)
make xsim-icarus     # "XSIM RESULT: PASS (5 frames ...)" + "CHECK RESULT: PASS"
python -m link.run_all   # dashboard at http://localhost:8000
```

**Commands everyone uses:** `make test` (before every PR) · `RUN_SLOW=1 python -m pytest tests/`
(adds the end-to-end link test) · `make one T=tb/test_top.py SEED=n` · `make waves T=...` ·
`make bundle T=...` · `python -m link.run_all --set sender.policy=bandit --set sender.source=clip.mp4`.

**Team rules**

1. The golden model is the referee.
2. A test comes with every change, and `make test` must be green.
3. Numbers only come from scripts.
4. One branch per task, then a PR with a teammate's review.
5. Never commit `sim_out/`, videos or `.pt` files.
6. Add every real bug to `docs/TESTING.md` §8.
7. Keep `docs/INTERFACES.md` in sync with any interface change.

---

## 8. Role briefs

Each role has the same shape: **run and verify** → **extend** → **produce** one table or figure → **write** one
paper subsection (~0.75 page) + its slide → help with the demo. The work is meant to be equal.
Day plan (§9): day 1 setup + verify, day 2 extend, day 3 final runs + figures, day 4 buffer +
paper drafts.

---

### Role 1 — Hardware & Vivado

**Mission:** turn the verified RTL into real hardware numbers (resources, timing, power) and
Vivado-based evidence, and prepare E5 support in hardware.

**Owns:** `rtl/`, `tb/`, `vivado/`, `hls/`, `Makefile` targets for them.

**Background to understand first:**

- the valid/ready handshake used by every block (`docs/INTERFACES.md` §1);
- the datapath order (§2 above);
- how `tag_unit.v` absorbs the 26-byte prefix latched at START, then the scan bytes;
- how `keystream_gen.v` gives a 16-bit look-ahead window so one symbol is encrypted per clock.

Read the header comment of each RTL file; it names its golden-model function.

**Steps**

1. **Verify locally.**
   - `make test-rtl`, then `make full`: all 1089 KATs in RTL plus a 320×240 frame, ~2 min.
   - *Done when:* everything passes.
2. **Vivado XSim, batch.** On the Vivado machine:
   - `python vivado/gen_xsim_vectors.py`, then `vivado\run_xsim.bat` (Windows; run it in the "Vivado Tcl Shell" or after `settings64.bat`), or `bash vivado/run_xsim.sh` (Linux).
   - *Done when:* it prints `XSIM RESULT: PASS (5 frames bit-exact with the golden model)`.
   - Then `python vivado/check_xsim_output.py` → `CHECK RESULT: PASS`. Open `vivado/xsim_work/frame*_scrambled.jpg` / `_decrypted.jpg`.
   - *Pitfalls:*
     - the repo path must have no spaces;
     - the vectors must exist before running;
     - if xvlog complains, paste the exact message.
3. **Vivado GUI.** Run `vivado -mode gui -source vivado/xsim_project.tcl` from the repo root.
   - Add `dut/u_tag` (`state`, `pleft`, `pref`, `tag_valid`), `dut/u_enc` and `dut/u_ks` (`ks_avail`, `ks_take`) to the wave window.
   - Screenshot one frame: the prefix absorption and the tag becoming valid. This is a paper figure.
4. **Out-of-context synthesis + implementation.**
   - Run `vivado -mode batch -source vivado/vivado_ooc.tcl` (whole design), then again with `-tclargs ascon_aead128_core`, `-tclargs keystream_gen` and `-tclargs tag_unit`.
   - Reports land in `sim_build/vivado_<top>/` (utilization, timing, power).
   - Record LUT / FF / BRAM / DSP, **WNS at 100 MHz** (must be ≥ 0) and total/dynamic power.
   - If WNS < 0, open `timing.txt`, find the critical path, report it, and try 80 MHz (`create_clock -period 12.5` in the tcl). Ask Claude to help analyse the path.
5. **Real-image vectors.**
   - `python vivado/gen_xsim_vectors.py --image photo.jpg --size 320x240 --modes 2 4`, then rerun XSim (step 2).
6. **Stretch: restart markers for E5 in RTL.** In order:
   1. Add `CTRL[4] = RESTART`.
   2. In `zigzag_rle.v`, reset the three DC predictors (`pred[0..2]`, now reset only on `start`) at the start of every MCU (every 6 blocks).
   3. In `bit_packer.v`, at each MCU end, pad to a byte with 1-bits (the same logic as the final flush), then emit `0xFF 0xD0+n` (n = MCU index mod 8, no marker after the last MCU), **without** 0xFF00 stuffing on the marker.
   4. The keyed MCU shuffle stays on the ARM: it only reorders segments in DDR.
   5. Golden reference: `model/entropy.py :: run_length_encode(restart=True)`, `encode_segments`, `join_restart`. First extend `model/hw.py` with a mode-5 stage view **without** the shuffle (plain restart coding), then write the cocotb test, then the RTL.
   6. Check that resources and cycles barely change.

**Produce:** resource / timing / power table (whole design + Ascon core + keystream + tag), one waveform figure, and the RTL cycle table from `python experiments/benchmark_crypto.py --rtl`.

**Paper subsection: Hardware implementation.**

- block diagram;
- one symbol per clock;
- encryption in the pipeline costs 0 extra cycles (the cost is area: report the Ascon cores' share of LUTs);
- resource and timing table vs the Zynq-7020 (53,200 LUT, 106,400 FF, 140 BRAM, 220 DSP);
- power;
- comparison with Ascon FPGA cores in the literature (1–3K LUT range).

**Hand-offs:** your numbers go into §7 of HELP_GUIDE.md and the paper's tables; Role 5 needs the cycle table.

---

### Role 2 — Cryptography & protocol

**Mission:** make the security design airtight and explainable: threat model, nonce/key
argument, KDF on the standard XOF, review of the feedback protocol.

**Owns:** `model/ascon.py`, `link/keys.py`, `link/feedback.py`, `docs/INTERFACES.md`, new `docs/THREAT_MODEL.md`.

**Background to understand first:**

- what AEAD, nonce, tag and keystream mean;
- why a repeated (key, nonce) pair is catastrophic: the same keystream XORed onto two frames leaks their XOR, and tags can be forged;
- the five uses of Ascon in this system:
  1. keystream (purpose 0);
  2. frame tag (purpose 1);
  3. E5 shuffle key: `ascon.mac(K, nonce(0,0,0), b"E5 MCU shuffle")`, then a keystream under `nonce(session, ctr, 0)` with that derived key;
  4. KDF: tag under `nonce(0, ctx, 1)`;
  5. feedback: separate key `K_fb`, `nonce(fb_session, fb_ctr, 0)`.
- SRTP/SRTCP replay windows (RFC 3711 §3.3.2).

**Steps**

1. **Verify.**
   - `python -m pytest -q tests/test_ascon_kat.py tests/test_link.py`.
   - Read `docs/INTERFACES.md` §4–§7 and `link/keys.py` until you can draw every nonce on a whiteboard.
2. **`docs/THREAT_MODEL.md`.**
   - Assets: video confidentiality, integrity, freshness, availability.
   - Attacker capabilities:
     - passive eavesdropper on the network;
     - active man-in-the-middle on video **and** feedback (modify, inject, replay, drop, delay, flood);
     - no physical access, no key extraction;
     - knows the algorithm (Kerckhoffs).
   - For each attack: what detects it (tag, counter window, epoch, dead-man) and what stays unprotected (§6 limits).
   - Trust assumptions: pre-shared master key, sender and receiver not compromised.
3. **Nonce-uniqueness argument (one page).**
   - Show that no two uses of Ascon ever share (key, nonce): distinct keys (master, K_fb, K_video[e], K_shuffle), the purpose bit, session 0 reserved for the KDF, the 63-bit counter strictly increasing per session, and a fresh 48-bit base per sender start.
   - State the conditions under which it would break: counter reset with the same session id, or the same base chosen twice, a probability of about n²/2⁴⁹.
   - Recommend what the board firmware must guarantee.
4. **KDF on Ascon-XOF128** (SP 800-232 also defines Ascon-Hash256, Ascon-XOF128 and Ascon-CXOF128).
   - Implement XOF128 in `model/ascon.py`, reusing `permutation()` and the SP 800-232 IV and padding rules.
   - **Verify against the official XOF KAT file** from the reference implementation (github.com/ascon/ascon-c, the `asconxof128` / CXOF directories). The `ascon` package on PyPI (pyascon) is another cross-check.
   - Only then switch `link/keys.py :: kdf()` to XOF128 or CXOF128 with the label as customisation string, update the docstring, and run `make test`.
   - **If you can't get official vectors, don't ship it:** document the plan instead.
5. **Protocol review.** Read `link/feedback.py` and `link/receiver.py`. Then check, and add tests for:
   - Can an attacker make the sender rekey forever? Rekeys are rate-limited by `defence.rekey_min_interval_s`.
   - Can forged alerts cause harm? They fail the tag.
   - What happens if the receiver restarts? It gets a new fb_session and a new replay window.
   - What if the sender restarts? It gets a new base, and the receiver refuses bases it has seen before.
6. **Optional:** a key-confirmation / session-start message so the receiver knows the sender's base before the first frame.

**Produce:** a key-schedule / protocol figure (who holds which key; what each message carries and protects) and the threat-model table (attack → mechanism → result → residual risk).

**Paper subsection: Security design and threat model.**

- the construction is encrypt-then-MAC from one primitive, with domain-separated nonces;
- **never** call the frame "AEAD-encrypted": it is selective XOR plus a separate tag;
- ratchet, feedback, dead-man rule, limitations.

**Hand-offs:** any change to nonces or keys must update `docs/INTERFACES.md`. Tell Role 1 if the RTL is affected; changing the KDF is not, since it runs on the ARM.

---

### Role 3 — Network & attacker

**Mission:** prove the integrity and detection claims with solid statistics, and extend the attack library.

**Owns:** `link/channel.py`, `link/sender.py` (sending side), `experiments/scenario.py`, `experiments/scenarios/*.json`.

**Background to understand first:**

- how frames are split into ~1400-byte UDP fragments (`link/wire.py`). One lost fragment loses the whole frame, so 3% packet loss is about 30% frame loss;
- what each receiver verdict means: `ok`, `tag-mismatch`, `replay`, `late` (benign reordering), `stale-epoch` (frame under an erased key), `malformed`;
- how the sender turns feedback into evidence (`link/defence.py :: Window.features`, `threat_score`);
- the 11 attacks listed in the `link/channel.py` docstring.

**Steps**

1. **Verify.**
   - `python experiments/scenario.py --scenario experiments/scenarios/quick.json --policy threshold` (~2 min).
   - Then the full suite (~5 min) and `benign.json` (~2.5 min).
   - *Done when:* full suite 11/11 mitigated, benign 0 false alarms (as in §4). If yours differ, paste the summary to Claude.
2. **Repeat runs.**
   - Run `full_suite` and `benign` **3–5 times each**. Use `--out sim_out/runs/full_suite_threshold_r1` etc., and a different `--base-port` (47200, 47240, …) for each.
   - Write a small script `experiments/aggregate_runs.py` that reads the `summary.json` files and outputs mean ± std per attack: first rejection, sender aware, time to mitigate, rekeys.
3. **Two new attacks** in `link/channel.py`. For each: add it to `ATTACKS`, to the dashboard list (`link/static/dashboard.html`, the `ATTACKS` array), to `full_suite.json`, and add a unit or end-to-end test.
   - **Freeze/loop:** re-send copies of the same valid frame. *Expected:* the receiver rejects duplicates as `replay` (the counter is authenticated), so a "frozen camera" cannot be faked. Then try "drop new frames only": the video freezes on the last good frame. That is detected as suppression; check how fast.
   - **Targeted region:** flip bits only in the first MCU rows, as if hiding a person entering. *Expected:* `tag-mismatch` like any modification.
4. **Tuning.**
   - Run `benign.json` with loss 1 / 3 / 6 / 10% (edit the impair steps or add `--set channel.loss=...`).
   - Measure false alarms vs detection speed for `defence.hold_s` ∈ {4, 8, 12} and `defence.window_s` ∈ {0.5, 1.0}.
   - Report the trade-off; propose defaults with a reason.
5. **Optional:** a bad-key attacker (forged frames carrying a correct-looking APP11 from another session).

**Produce:** the attack-detection table (each attack → verdict seen, first rejection, sender aware, time to max protection, rekey, mean ± std) and the false-alarm vs loss plot.

**Paper subsection: Integrity and attack-detection evaluation.**

- setup (sender, channel, receiver over UDP; attack injection);
- metrics;
- the table;
- benign-loss false alarms;
- the reaction-time bound (1 s window + 0.5 s heartbeat).

**Hand-offs:** tuned defaults go into `configs/default.toml` (agree with Role 5); new attacks need Role 4's dashboard check.

---

### Role 4 — Receiver, dashboard & demo

**Mission:** own the user-facing side: real video, the receiver's correctness and latency,
the dashboard, the demo, and the multi-receiver design.

**Owns:** `link/receiver.py`, `link/dashboard.py`, `link/static/dashboard.html`, `link/sources.py`, demo material, new `docs/MULTI_RECEIVER.md`.

**Background to understand first:**

- the receiver's decision order in `handle_frame`: parse APP11 → session/epoch → old counter? (cheap reject or `late`) → tag check + decrypt (`model/jpeg.py :: receive_frame`) → counter gap → show;
- why decryption is bit-exact: XOR twice gives back the same bits;
- the dashboard: Server-Sent Events at `/events`, MJPEG streams at `/stream/<camera|wire|receiver|attacker>.mjpg`, commands via `POST /api/channel` and `/api/sender`.

**Steps**

1. **Verify.**
   - `python -m link.run_all`, open http://localhost:8000, press every attack button and watch the log, ladder and receiver badge.
   - In VLC: *Media → Open Network Stream* → `http://localhost:8000/stream/wire.mjpg`. It plays, scrambled.
   - Run `RUN_SLOW=1 python -m pytest -q tests/test_link.py`.
2. **Record real clips.** 3–4 CCTV-like clips, 30–60 s each, **different places** (corridor, gate, lab, parking), steady phone on a wall or shelf. Put them in `clips/` (not in git; share via Drive).
   - Run the link on them: `--set sender.source=clips/gate.mp4`.
   - Check the frames look right at 320×240. Every role needs these clips, especially Role 5.
3. **Latency.**
   - Each verified frame's `latency_ms` is in the events (`sim_out/runs/*/events.jsonl`, `kind == "frame"`).
   - Write `experiments/latency_report.py`: latency distribution (median, p95) per mode (`--set sender.mode=E2` vs `E5`, policy fixed) and under the replay and flood attacks. Make one figure.
   - Explain what dominates: the Python encoder takes ~50–90 ms per frame, while the RTL would take ~5 ms at 640×480.
4. **Freeze indicator.** Show "no new verified frame for X s" on the receiver tile. Today the last frame just stays.
5. **`docs/MULTI_RECEIVER.md`** (design only):
   - encrypt once, one tag per receiver, so a receiver cannot forge frames for others;
   - join and leave;
   - revocation by rekeying the rest;
   - optional tiered access: a "guard" key that decrypts signs only vs an "admin" key for everything;
   - how the channel would fan out;
   - what the receiver code must change (ports, per-receiver key).
6. **Demo.** A 2-minute screen recording: calm → bit-flip attack → rejection + escalation + rekey → recovery → E5 view → VLC playing the scrambled stream. Also a dashboard screenshot for the paper.
7. **Polish (optional):** a mode-specific note on the "eavesdropper" tile; an export button that saves the current four tiles as one image.

**Produce:** system overview figure (§2 diagram, drawn neatly), dashboard screenshot, latency figure, demo video.

**Paper subsection: System overview and demonstrator.**

- the end-to-end pipeline;
- the dashboard as the evaluation tool;
- the latency results;
- format compliance (plays in VLC / ffmpeg / Pillow).

**Hand-offs:** clips to Role 5 by end of day 1. Check Role 3's new attacks show correctly.

---

### Role 5 — Defence, ML & visual security (the RTX 4060 laptop)

**Mission:** produce the security-strength evidence (what an attacker can recover per mode,
including a neural attack) and the adaptive-defence results.

**Owns:** `link/defence.py`, `experiments/measure_mode_tradeoff.py`, `experiments/compare_policies.py`, `experiments/learned_attack.py`, the `[defence]` section of `configs/default.toml`.

**Background to understand first:**

- the replacement attack (`model/selective.py :: replacement_attack`, `model/jpeg.py :: replacement_attack_jpeg`): an attacker without the key replaces encrypted values with fixed guesses;
- why E1–E4 leak edges: the positions of non-zero coefficients stay in clear;
- why E5 helps: block positions are shuffled;
- the bandit (`link/defence.py :: BanditPolicy`):
  - context = which evidence is present;
  - actions = modes from the E2 floor up to E5;
  - reward = −(evidence × leakage[mode] + 0.5 × cost[mode] + switching penalty);
  - optimistic initial values, sample-average updates;
  - memory saved to `sim_out/bandit_memory.json`;
- leakage values = measured edge correlation; cost = encrypted bit share.

**Steps**

1. **Verify.**
   - `python experiments/measure_mode_tradeoff.py --save-images` should give the §4 table.
   - `python experiments/compare_policies.py` (~6 min) should give the table + `timeline.png` + `tradeoff.png`.
2. **Real video.**
   - With Role 4's clips: `python experiments/measure_mode_tradeoff.py --video clips/X.mp4 --frames 30 --save-images` for each clip.
   - Report mean ± std across clips.
   - If the numbers differ a lot from synthetic, update `[defence.leakage]` / `[defence.cost]` in `configs/default.toml` and say why.
3. **GPU learned attack** (the key experiment). It trains a small U-Net to reconstruct the original from what an eavesdropper sees.
   - Install CUDA PyTorch (`requirements-gpu.txt`); `python -c "import torch; print(torch.cuda.is_available())"` must print True.
   - Run: `python experiments/learned_attack.py --train-source clips/A.mp4 --test-source clips/B.mp4 --modes E1 E2 E4 E5 --size 160x128 --frames 3000 --epochs 25`.
   - **Train and test on different clips/places**, otherwise the network memorises the background and the result is meaningless. The script refuses the same file.
   - If one clip is too short, concatenate several training clips with ffmpeg.
   - Outputs: `sim_out/learned_attack/results.md`, `examples_<mode>.png` (original | replacement attack | network).
   - Report PSNR / SSIM / edge correlation, replacement vs learned, per mode.
   - *Expected (to check, not to assume):* the network recovers more from E1/E2 than from E4, and little from E5. Whatever it shows is the result.
   - Out of GPU memory: `--batch 8` or `--width 24`.
4. **E5 restart-interval study.** Interval 1 MCU costs 13–21% bitrate.
   - Add a `restart_interval` parameter (now fixed at 1) in these places:
     - `model/entropy.py :: run_length_encode` — reset predictors every N MCUs;
     - `mcu_segments` — group N MCUs per segment;
     - `model/jpeg.py :: package_frame / receive_frame / replacement_attack_jpeg` — DRI value N; segment count `ceil(n_mcu / N)`; the receiver decodes `huffman_decode(seg, N)`, and the last segment may be shorter.
   - Keep `make test-model` green and add a test.
   - Measure leakage vs overhead for N = 1, 2, 4, 8 and plot it.
   - Discuss the trade-off: bigger N gives less overhead but coarser shuffling, so more sketch leaks.
5. **Repeated learning runs.**
   - `python experiments/compare_policies.py --scenario experiments/scenarios/learning.json --policies threshold bandit`, 3 times with fresh memory (each run uses its own folder; use `--out sim_out/compare/learning_r1` etc.).
   - Report time-to-mitigate per round as mean ± std (the `rounds.png` style). ~16 min per run: start it and do something else.
6. **Optional:** a bandit variant that also chooses the rekey action, or a UCB/Thompson-sampling comparison.

**Produce:**

- the visual-security figure: original | E1 | E2 | E4 | E5 attacker images, from `sim_out/attacker_E*.png` or the learned-attack examples;
- the leakage/cost table;
- the learned-attack table;
- the restart-interval plot;
- the policy comparison table + `rounds.png`.

**Paper subsection: Visual security and adaptive defence.**

- leakage metrics, and why edge correlation rather than only SSIM: a flat grey image still scores ~0.4 SSIM;
- the sketch leak, and E5 as the fix with its cost;
- the learned attack;
- the bandit vs rules trade-off: same speed after learning, 13% cheaper, slightly more leakage.

**Hand-offs:** agree defaults with Role 3. Role 1 needs the E5 decision (which N to support in RTL).

---

## 9. Timeline and dependencies

| When | Everyone | Notes |
|---|---|---|
| Day 1 | setup + all checks green (§7); each role's step 1 | Role 4 records and shares clips by evening |
| Day 2 | steps 2–3 | Role 1 has Vivado numbers; Role 2 has the threat model draft |
| Day 3 | steps 4–5, final runs, figures into `sim_out/` | every number from a script |
| Day 4 | buffer, demo rehearsal, paper subsections, review each other | PRs merged, CI green |
| until 12 Nov | board bring-up: Vivado block design (Zynq PS + AXI DMA + `secure_jpeg_top`), PYNQ overlay, `board/sender.py` doing the register sequence of `tb/test_top.py::Encoder`, real fps / latency / power | Role 1 leads; all help |
| until 15 Dec | paper: experiments on the board, writing, internal review, IEEE format | see §10 |

**Dependencies**

- Role 4's clips → Role 5 (and the demo).
- Role 1's numbers → paper tables.
- Role 2's interface changes → Role 1 (only if the RTL is affected).
- Roles 3 and 5 agree the defence defaults.

---

## 10. Paper plan (IEEE conference format, ~6 pages)

1. **Introduction** (team lead): CCTV / drone / medical motivation; contributions list.
2. **Related work**: one comparison table. Columns: codec, where encryption happens, cipher (standard?), integrity, platform, plays in a normal player, adaptive. Rows: refs [1]–[7] + Kishore 2015, Sbiaa 2016, Rezk 2021, Sheng 2025, Lin 2024.
3. **Threat model** (Role 2).
4. **Architecture and security design** (Roles 1 + 2).
5. **Feedback and adaptive defence** (Roles 2 + 5).
6. **Implementation** (Role 1): resources, timing, power, 0 extra cycles.
7. **Evaluation**: visual security + learned attack (Role 5), integrity and detection (Role 3), latency and demo (Role 4), cost vs full-stream AES (Role 1, the benchmark).
8. **Limitations** (§6).
9. **Conclusion.**

**Venues:** check deadlines yourself; dates change. Options: IEEE CONECCT (Bangalore), IEEE INDICON 2027, IEEE TENCON 2027, IEEE ISVLSI / SOCC / MWSCAS 2027, IEEE Access or IEEE Embedded Systems Letters (rolling), MDPI Electronics / Cryptography.

---

## 11. Glossary

| Term | Meaning |
|---|---|
| MCU | 16×16 pixel unit = 4 Y blocks + 1 Cb + 1 Cr (4:2:0) |
| DC / AC | the first (average) DCT coefficient of a block / the other 63 |
| Size category | number of bits needed for a coefficient's amplitude; Huffman-coded, **not** encrypted |
| Restart marker (RST, DRI) | JPEG marker `FF D0..D7` that makes segments independently decodable; DRI sets the interval |
| AEAD | authenticated encryption with associated data (Ascon-AEAD128) |
| KAT | known-answer test vectors (official expected outputs) |
| Keystream | pseudo-random bits XORed onto data; must never repeat under one key |
| Ratchet | one-way key update; old keys cannot be recomputed from new ones |
| Dead-man rule | silence on the feedback channel is itself treated as an attack signal |
| Bandit | a learning policy that tries actions and keeps the ones with the best reward per situation |
| OOC | out-of-context synthesis: synthesise a module without the full board design |
| WNS | worst negative slack: ≥ 0 means timing is met at the target clock |
| cocotb / Icarus / XSim | Python testbench framework / free Verilog simulator / Vivado's simulator |
| Edge correlation | correlation between the edge maps of the original and an attacker's image (0 = no outline leaked) |
