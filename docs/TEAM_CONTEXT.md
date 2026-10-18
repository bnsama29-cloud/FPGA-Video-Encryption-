# Team context for Claude — Secure Video Transmission Using Hardware Selective Encryption

> **How to use this file (for us humans).**
>
> 1. Open a new Claude chat and attach this file plus `GUIDE.md`, or in Claude Code inside the repo
>    say *"Read docs/TEAM_CONTEXT.md and GUIDE.md"*.
> 2. Then say who you are and which task you are doing, e.g. *"I'm Rishab, Role 3, task A6 of GUIDE.md."*
> 3. Paste error messages, logs and results as you go; Claude cannot see your laptop.

---

## 0. Instructions for Claude (the assistant reading this)

You are helping one member of a 5-person undergraduate team (RVCE Bangalore, ECE, III semester,
Experiential Learning). The project state is below; the remaining tasks, their owners and their
step-by-step specs are in **`GUIDE.md` §4**. Work like this:

- **Ask which task (GUIDE.md §4: A1–A8, B1–B12, or the paper) and which OS** the person has, if they
  did not say. Then help them through that task one step at a time.
- **Explain the reasoning** behind fixes and design choices, not just the fix. The team must defend
  everything in a viva and at a conference.
- **The golden model in `model/` is the referee.** Never change it to make an RTL test pass, unless
  it contradicts ITU-T T.81 (JPEG) or NIST SP 800-232 (Ascon); then say so explicitly.
- **Never invent numbers or references.** Results come from scripts (`experiments/`, `future_work/`)
  that write files. Paper tables are generated from `paper/data/`. References must be in
  `paper/refs.bib`, which was checked source by source.
- **Every code change needs a test**, and `make test` must pass before a pull request.
- **Don't over-claim:** §5 lists the honest limitations, and GUIDE.md §5 is the claim–evidence checklist.
- When debugging, ask for the exact command, the full error and the `random seed = N` line;
  `make bundle T=<test>` writes `debug_bundle.md` to paste.

---

## 1. The project in one page

| | |
|---|---|
| Title | Secure Video Transmission Using Hardware Selective Encryption (Semiconductor Engineering theme) |
| Team | CMOS Crusaders: Aravind R, Suhas VJ, Rishab HR, Samarth BN, Vijaysurya BS |
| Mentor / evaluator | Dr. Chetana G (mentor), Dr. Deepika P (evaluator), Dept. of ECE, RVCE |
| Board | PYNQ-Z2 (Zynq-7020, xc7z020clg400-1): ARM Cortex-A9 + FPGA fabric, 100 MHz target clock |
| Repo | https://github.com/bnsama29-cloud/FPGA-Video-Encryption- (branch `main`) |
| Deadlines | simulation done (14 Oct 2026); working hardware by **12 Nov 2026**; conference paper by **15 Dec 2026** |

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

**Key references** (verified; the full, checked list is `paper/refs.bib`):

- [1] Van Droogenbroeck & Benedett, ACIVS 2002 (JPEG selective encryption of appended bits).
- [2] Puech & Rodrigues, EUSIPCO 2005 (AES on selected DCT coefficients, medical images).
- [3] Hirose, Imaizumi & Kiya, *Electronics* 13(11), Art. no. 2016, 2024 (JPEG bitstream encryption + restart-marker block shuffling).
- [4] Bağbaba & Örs, ELECO 2015 (FPGA JPEG + TEA cipher).
- [5] Gladis Kurian & Chen, *Electronics* 14(13) 2668, 2025 (Ascon-AEAD128 on Artix-7 with Bloom-filter replay protection). The first author's surname is "Gladis Kurian".
- [6] Turan et al., NIST SP 800-232, Aug 2025.
- [7] Boyadjis et al., IEEE TCSVT 27(4) 2017 (H.264/HEVC selective encryption).

Also important: Kishore, Kumar & Patil, *J. Real-Time Image Processing* 2015 ("FPGA based simple and fast JPEG encryptor", the closest prior FPGA work), and Lin et al., *JVCIR* 2024 (recovering DCT sign bits, an attack on sign-only encryption).

---

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
| Modes | E0 tag only · E1 AC signs · E2 + DC-difference signs (**default floor**) · E3 + AC amplitudes · E4 + DC amplitudes · E5 = E4 + keyed MCU shuffle (restart interval 1 MCU, Fisher–Yates under a separately derived key; **in the model and, since 17 Oct, in the lane-encoder RTL as contract v3 mode 5; not yet on the board**) |
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

---

## 4. Status and results (14 Oct 2026)

**Done and verified.**

- **Golden model + contract v2.** All 1089 Ascon KATs pass in Python and RTL.
- **RTL (E0–E4).** Bit-exact with the model under random stalls (cocotb + Icarus 12), with 0 extra
  cycles for encryption. **E5** in the contract-v3 lane encoder (17 Oct): bit-exact for 1, 2, 4 lanes.
- **Vivado testbench.** Passes in Icarus.
- **System simulation.** Feedback, ratchet, defence, 11 attacks and the dashboard.
- **The complete simulation result set.** One Kaggle run on 14 Oct (`future_work/kaggle/kaggle_runs.py (JOB = "complete")`):
  3 repeats of every attack suite, 10 seeds of the policy study, 4 real clips, and a learned attack
  on a GPU. The snapshot is in `paper/data/`; every table is in **`paper/data/paper_tables.md`**.
- **The open-data run** (14 Oct, `future_work/kaggle/kaggle_runs.py (JOB = "remaining")`, 39/39 steps): Sintel trailer,
  Tears of Steel (CC BY 3.0) and Kodak; standard image-encryption metrics; E5 restart interval
  N = 1–32 with the non-zero counting attack; U-Net trained on 3 clips and tested on 3 others; the
  attack suite with an open clip. Snapshot in `paper/data/extra/` (its README gives the provenance).
  A rerun (same day) added the fixed restart interval on the open sources and the learned-attack control.

**Not done yet.**

- Vivado rebuild of the lane encoder/overlay with E5, and power from simulated activity (`--steps lanes bd_lanes power parse`, `docs/VIVADO_ONE_DAY.md`).
- Everything on the board (GUIDE A1–A8).
- The P1 polish items (GUIDE B1, B3, B20–B22) and the rest of GUIDE §4.3.
- Finishing the paper (`paper/`, first full draft exists).

**Where to find what.**

| Topic | Source |
|---|---|
| Throughput and cycle cost | `paper/data/paper_tables.md` §Hardware (RTL simulation) |
| Resources (until Vivado) | Yosys estimate, `paper/data/yosys/` |
| Attack reaction, false alarms, latency | §Reaction (3 runs each) |
| Bandit vs threshold | §Bandit vs threshold over seeds (10 seeds) |
| Leakage per mode, jigsaw, learned attack | §Leakage, §E5 against the jigsaw solver, §Learned; open data in `paper/data/extra/` |
| Standard metrics, restart interval, NZCA | `paper/data/extra/<source>/standard_metrics/`, `.../restart_interval/`; tables via `paper/make_assets.py` |
| Decoders that open the stream | §Format compliance |

**Bugs found and fixed:** `docs/TESTING.md` §8 (bug log). It makes good report material.

---

## 5. Honest limitations and claims to avoid (the paper must respect these)

- **The sketch leak.** Sign and amplitude encryption never hides *which* coefficients are non-zero, so E1–E4 all leak an edge sketch, and E3/E4 don't reduce it. E5 hides block positions; a greedy jigsaw solver and a trained U-Net both fail to restore the outline (edge correlation ≤ 0.044), but a stronger solver is still to be tried (GUIDE B9). E5 also defeats the non-zero counting attack (NZCA).
- **E5 overhead.** E5 costs 12–21% bitrate at restart interval 1 (10–23% per clip at 320×240); in RTL (lane encoder, since 17 Oct) it also costs 0.7–3.6% throughput. Longer intervals are cheap (0.5% at N = 32) but **not** safe: a beam-search solver re-chains 15–41% of the 10 segments (chance 11%). Keep N = 1.
- **Passive eavesdroppers are invisible.** The defence reacts only to *active* attacks; a passive eavesdropper is handled only by the floor mode (E2).
- **Loss vs jamming.** The receiver can't tell benign loss from partial jamming. Only near-total suppression (≥90% frame loss) escalates.
- **Reaction time.** It is bounded by the 1 s decision window plus the 0.5 s heartbeat.
- **Learned attacker.** A U-Net **breaks E1** (edge corr. 0.69, SSIM 0.79 on unseen clips). It recovers coarse brightness and colour from E2–E5 (SSIM up to ~0.43; E5 0.36 in the 3→3 setup) but no outline under E5 (edge ≤ 0.044). Against a no-ciphertext control (the median training frame) the E5 edge correlation is equal (0.037 vs 0.036: no outline from the stream), but SSIM is 0.11 higher in the 3→3 setup — probably frame-level brightness/colour (GUIDE B25). Say exactly that, not "nothing leaks".
- **Standard metrics.** Key sensitivity is good, but adjacent-pixel correlation (0.88–0.92) and entropy stay far from full-cipher values: format-compliant encryption keeps 8×8 structure. Report them for comparability, never as proof of security.
- **Bandit.** Over 10 seeds it encrypts fewer bits but reacts slower and leaks more under attack: a trade-off, not an improvement.
- **Test clips.** The four private clips are copyrighted trailers / talking-head videos: numbers only, never frames. Pictures in the paper come only from the open films (Sintel, Tears of Steel) or the synthetic scene.
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

---

## 6. Glossary

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
