# Help guide — secure video link simulation (CMOS Crusaders)

This guide is for the five of us. It explains what is in the repository now, how to
run every part, how we split the remaining simulation work evenly over 3–4 days, how our
results compare with published work, and what is still missing before the paper.

Read §1–§3 together on day 1. After that, each person mainly needs §4 (their role) and §8 (rules).

---

## 1. What changed in this pull request (and why)

The project had two code bases: the golden model (this GitHub repo) and the Verilog
simulation repo (`secure-jpeg-sim`). They now live here as one project, with one contract.

**The two had drifted apart.** Encoding the same image in E2 gave 335 of 348 different
scan bytes. The JPEG part matched; the encryption and framing did not. A board running
the old RTL would have been rejected by the old receiver. Contract v2 keeps the stronger
choice from each side. Full table with reasons: `docs/INTERFACES.md` §7.

| What | Now (v2) | Why it matters (be ready to explain this in the viva) |
|---|---|---|
| Sign encryption | invert all amplitude bits (the RTL rule) | in JPEG's ones' complement coding that is exactly v → −v. The old golden rule flipped only the top bit, which also changed the magnitude (5 → −6), so it was not sign encryption |
| Nonce | 64-bit session id ‖ 63-bit counter ‖ purpose bit | a 32-bit random session id repeats after ~65 000 sessions (birthday bound); a repeated nonce reuses the keystream |
| Tag | covers APP11 metadata + width + height + scan | the old RTL tagged only the scan, so an attacker could change the mode byte E2 → E1 and the receiver would show a wrongly decrypted frame as authentic (**real hole, now fixed and tested**) |
| DCT / quantiser | the RTL's integer arithmetic | about 6% of the old golden coefficients differed by ±1 from the RTL, so the old golden model could never have checked the hardware |

`tests/test_hw_equivalence.py` now proves that the stage-level view used by the RTL
testbenches (`model/hw.py`) and the frame-level golden model (`model/jpeg.py`) produce
**identical bytes** for 4 images × 4 qualities × 5 modes.

**Added on top:** a Vivado XSim testbench; the system simulation (one sender, one receiver,
network + attacker, authenticated feedback, key ratchet, adaptive defence, web dashboard);
a new mode E5; and experiment scripts that produce the paper's tables and figures.

---

## 2. Setup (once per laptop, ~30 min)

**Python 3.10+** (Windows: use WSL Ubuntu 22.04/24.04 and work inside `~/`, not `/mnt/c`).

```bash
git clone https://github.com/bnsama29-cloud/FPGA-Video-Encryption-.git && cd FPGA-Video-Encryption-
git switch sim-integration        # only until the pull request is merged into main
python3 -m venv .venv && source .venv/bin/activate          # every new terminal
pip install -r requirements.txt
```

**Icarus Verilog 12** (for the RTL tests). Ubuntu 24.04: `sudo apt install iverilog` gives 12.0.
Ubuntu 22.04 ships 11.0 — build 12 from source:
`git clone https://github.com/steveicarus/iverilog && cd iverilog && git checkout v12_0 && sh autoconf.sh && ./configure && make -j4 && sudo make install`
(needs `autoconf gperf flex bison g++`). Optional: `gtkwave`, `verilator` (lint).

**Vivado / Vitis 2023.2 or newer, ML Standard (free)** — on Windows is fine. Only the
person doing Role 1 needs it on day 1; everyone else can use Icarus.

**GPU (Role 5 only):** install the CUDA build of PyTorch that matches the driver
(`pip install torch --index-url https://download.pytorch.org/whl/cu124`), then
`python -c "import torch; print(torch.cuda.is_available())"` must print `True`.

**Check everything works:**

```bash
make test-model        # golden model + contract + system tests: all pass in ~5 s
make test-rtl          # 10 RTL test groups in Icarus: all pass in ~30 s
make xsim-icarus       # Vivado testbench run in Icarus: "XSIM RESULT: PASS (5 frames ...)"
python -m link.run_all # then open http://localhost:8000
```

If any of these fails on a clean checkout, stop and fix that first (§8, "When something fails").

---

## 3. The system in 5 minutes

```
                       camera twin (link/sender.py)                       laptop (link/receiver.py)
 synthetic CCTV /  ──► encoder + selective encryption + tag ──► UDP ──► verify tag, check counter, ──► dashboard
 video / webcam        (golden model, or the real Verilog)        │       decrypt bit-exactly            (link/dashboard.py)
                                  ▲                               │                │
                                  │                     channel + attacker         │
                                  │                     (link/channel.py)          │
                                  └──── authenticated feedback (heartbeats, alerts) ◄┘
           adaptive defence (link/defence.py): chooses E2..E5, rekeys, dead-man rule
```

Four separate processes talk real UDP on localhost, exactly as the board and the laptop
will. Later, the PYNQ board replaces `link/sender.py` and nothing else has to change.

**Run it:** `python -m link.run_all` and open http://localhost:8000. The page shows:

* **Camera → On the wire → Receiver**: the plain input, the real bytes on the network (what
  VLC or an eavesdropper sees) and the verified, decrypted output.
* **Eavesdropper's best guess**: what someone without the key reconstructs from the intercepted bytes.
* **Protection**: current mode (E2 is the floor), attack evidence, encrypted-bit share, heartbeat age.
* **Attack the link**: 11 attacks on the video and feedback paths; **Defence and network**:
  policy, manual mode, rekey, packet loss and delay.
* VLC: *Media → Open Network Stream →* `http://localhost:8000/stream/wire.mjpg` plays the
  real scrambled stream. That is the "plays but unreadable" demo.

**Useful variations:**

```bash
python -m link.run_all --set sender.policy=bandit            # learning policy
python -m link.run_all --set sender.source=clip.mp4          # your own video (resized to 320x240)
python -m link.run_all --set sender.source=webcam:0          # live webcam
python -m link.run_all --set channel.loss=0.03               # benign packet loss from the start
python -m link.run_all --set sender.encoder=rtl --set sender.width=128 --set sender.height=96 --set sender.fps=0.25
                                                             # every frame encoded by the real Verilog (Icarus)
```

Each node can also run in its own terminal (`python -m link.channel`, `link.receiver`,
`link.dashboard`, `link.sender`), which is how you debug one part.

**Key schedule** (`link/keys.py`): one pre-shared master key → feedback key and video keys.
`K_video[e+1] = KDF(K_video[e])` is one-way; the receiver follows a rekey automatically,
because the epoch is inside the authenticated session id, and erases the old key (forward
secrecy). Frames from an erased epoch are rejected as `stale-epoch`.

**Feedback** (`link/feedback.py`): every message is Ascon-AEAD128 encrypted and authenticated
under its own key, with a 64-entry replay window (as SRTCP, RFC 3711). Heartbeat every
0.5 s plus rate-limited alerts. If no valid heartbeat arrives for 3 s, the **dead-man rule**
switches the sender to maximum protection and rekeys, so dropping the alerts does not help an attacker.

**Defence** (`link/defence.py`): a passive eavesdropper sends nothing, so nobody can "see how
it steals". That is why there is a **floor** (E2) that never drops. What the sender sees is
evidence of active attacks: tag failures, replays, missing frames, forged or replayed
feedback, silence. Three policies:

* **fixed**: no reaction (the baseline);
* **threshold**: hand-written rules;
* **bandit**: a contextual bandit that learns which mode to use in which situation and
  remembers it across runs (`sim_out/bandit_memory.json`).

---

## 4. Who does what (3–4 days, equal work)

Each role has the same shape: **run and verify** your part, **extend** it (2–3 tasks), **produce**
one table or figure for the paper, and **write** one paper subsection (~0.75 page) plus its
slide. Fill in the names; whoever has the RTX 4060 laptop takes Role 5.

| Role | Who | Owns (folders) | Paper subsection |
|---|---|---|---|
| 1 Hardware & Vivado | _____ | `rtl/`, `tb/`, `vivado/`, `hls/` | Hardware implementation + resource/timing/power table |
| 2 Cryptography & protocol | _____ | `model/ascon.py`, `link/keys.py`, `link/feedback.py`, `docs/INTERFACES.md` | Security design + threat model |
| 3 Network & attacker | _____ | `link/channel.py`, `link/sender.py`, `experiments/scenarios/` | Integrity and attack-detection evaluation |
| 4 Receiver, dashboard & demo | _____ | `link/receiver.py`, `link/dashboard.py`, `link/static/` | System overview figure, demo, latency |
| 5 Defence, ML & visual security | _____ | `link/defence.py`, `experiments/` (measure, compare, learned_attack) | Visual security + adaptive defence results |

### Role 1 — Hardware & Vivado

Run and verify:
1. `make test-rtl`, then `make full` (all 1089 KATs in RTL + a 320×240 frame).
2. In Vivado: `python vivado/gen_xsim_vectors.py`, then `vivado\run_xsim.bat` (or
   `bash vivado/run_xsim.sh`) → `XSIM RESULT: PASS`. Then `python vivado/check_xsim_output.py`
   and open the `frame*_scrambled.jpg` / `_decrypted.jpg` files in `vivado/xsim_work/`.
3. GUI: `vivado -mode gui -source vivado/xsim_project.tcl`; add `dut/u_tag` (state, `pleft`,
   `pref`), `dut/u_enc` and `dut/u_ks` to the wave window; take a screenshot of one frame's
   tag-prefix absorption for the paper.

Extend:
1. Out-of-context synthesis + implementation: `vivado -mode batch -source vivado/vivado_ooc.tcl`
   for `secure_jpeg_top`, `ascon_aead128_core`, `keystream_gen`, `tag_unit`. Record LUT/FF/BRAM/DSP,
   WNS at 100 MHz and power. If WNS < 0, report the critical path and try 80 MHz.
2. Run a real-image vector set: `python vivado/gen_xsim_vectors.py --image photo.jpg --size 320x240 --modes 2 4`.
3. *(Stretch, needed for E5 on the board)* restart-marker support: after every MCU, byte-align
   with 1-padding, emit `FF D0+n` and reset the DC predictors. Add a `RESTART` bit to `CTRL`.
   The model is already there (`model/entropy.py :: encode_segments / join_restart`). The MCU
   shuffle itself can stay on the ARM (it only reorders segments in DDR).

Produce: resource / timing / power table + one waveform figure.
Note: encryption adds **0 cycles** in every mode (`experiments/benchmark_crypto.py --rtl`) — the
cost is area. Report the Ascon cores' share of the LUTs.

### Role 2 — Cryptography & protocol

Run and verify:
1. `python -m pytest -q tests/test_ascon_kat.py tests/test_link.py`.
2. Read `docs/INTERFACES.md` §4–§7 and `link/keys.py`; be able to explain every nonce on a whiteboard.

Extend:
1. Write `docs/THREAT_MODEL.md`: attacker capabilities (passive eavesdropper, active MITM on
   video and feedback, replay, DoS, no physical access), assets, what is and is not protected.
   Include the honest limits in §7.4.
2. Swap the KDF to **Ascon-XOF128 / CXOF128** (SP 800-232): implement it in `model/ascon.py`
   and test it against the **official** XOF test vectors before using it in `link/keys.py`.
   Keep the old KDF if you cannot get the official vectors — never ship unverified crypto.
3. Nonce-uniqueness argument: one paragraph showing that no two (key, nonce) uses collide —
   frames (purpose 0/1), the E5 shuffle key, KDF (session 0) and feedback (separate key).

Produce: key-schedule / protocol figure (who holds which key, what each message carries) +
threat-model table.

### Role 3 — Network & attacker

Run and verify:
1. `python experiments/scenario.py --scenario experiments/scenarios/quick.json --policy threshold`.
2. `python experiments/scenario.py --scenario experiments/scenarios/full_suite.json --policy threshold`
   (every attack once, ~5 min) and `... benign.json` (no attacks — every escalation is a false alarm).

Extend:
1. Two more attacks in `link/channel.py`: a **freeze/loop attack** (keep re-sending the same
   valid frame — what does the receiver say?) and a **targeted region attack** (flip bits only
   in the first MCU rows). Add each to `ATTACKS`, the dashboard list and `full_suite.json`.
2. Run `benign.json` at loss 1/3/6/10% and tune `defence.hold_s` and the loss levels so that
   false alarms stay low without slowing detection. Report the trade-off.
3. Repeat each scenario 3 times and report mean ± std (timing varies run to run).

Produce: the attack-detection table (attack → receiver verdict, first rejection, sender
aware, mitigated, rekeys) for all attacks.

### Role 4 — Receiver, dashboard & demo

Run and verify:
1. `python -m link.run_all`; try every attack button; check the VLC stream `/stream/wire.mjpg`.
2. `python -m pytest -q tests/test_link.py` and `RUN_SLOW=1 python -m pytest -q tests/test_link.py`.

Extend:
1. Record 3–4 short **CCTV-like clips** on a phone (corridor, gate, lab; 30–60 s each, different
   places). Everyone needs real video: Role 5 trains on them and the demo uses them.
2. Measure end-to-end latency: `latency_ms` is already reported per frame; add a plot of the
   latency distribution per mode (E2 vs E5) and under the replay/flood attacks.
3. Write `docs/MULTI_RECEIVER.md`: the design for later (encrypt once, one tag per receiver,
   join/leave, revocation by rekey; see §9). Design only — no code yet.

Produce: system overview figure (the §3 diagram, drawn properly), dashboard screenshots, a
2-minute demo video (calm → attack → detection → recovery).

### Role 5 — Defence, ML & visual security (RTX 4060)

Run and verify:
1. `python experiments/measure_mode_tradeoff.py --save-images` (synthetic), then on Role 4's clips:
   `--video clips/gate.mp4 --frames 30`. Paste the printed `[defence.leakage]` / `[defence.cost]`
   into `configs/default.toml` if they differ a lot.
2. `python experiments/compare_policies.py` (quick, ~6 min) and
   `python experiments/compare_policies.py --scenario experiments/scenarios/learning.json --policies threshold bandit` (~16 min).

Extend:
1. **Learned attack on the GPU**: `python experiments/learned_attack.py --train-source clips/A.mp4 --test-source clips/B.mp4 --modes E1 E2 E4 E5 --size 160x128 --frames 3000 --epochs 25`
   (train and test on *different* clips). This is the strongest attacker in the paper.
2. **E5 restart-interval study**: interval 1 MCU costs 13–21% bitrate. Add a `restart_interval`
   parameter (now fixed at 1: `run_length_encode(restart=...)`, `mcu_segments`, the DRI value
   in `package_frame` / `receive_frame`), keep the tests green, then try 2, 4, 8 MCUs and plot
   leakage vs overhead.
3. Repeat the learning scenario with 3 different seeds / fresh memories and report mean ± std.

Produce: the visual-security figure (original | E1 | E2 | E4 | E5 attacker views) + the
leakage/cost table, and the policy comparison table + `rounds.png`.

### Day plan

| Day | Everyone | Goal at the end of the day |
|---|---|---|
| 1 | Morning: setup (§2) together, all checks green. Afternoon: each role's "run and verify" | everyone can demo their part |
| 2 | Extend tasks 1–2 | new code merged through PRs, CI green |
| 3 | Extend task 3 + final experiment runs; figures and tables into `sim_out/` | every number in the paper comes from a script |
| 4 (buffer) | Integration demo rehearsal; paper subsections; review each other's sections | draft paper + demo video |

---

## 5. Command reference

| Command | What it does |
|---|---|
| `make test` | model + system + RTL tests (must pass before any merge) |
| `make test-model` / `make test-rtl` | only `tests/` / only `tb/` |
| `RUN_SLOW=1 python -m pytest tests/` | adds the 20-s end-to-end link test |
| `make xsim-icarus` | Vivado testbench in Icarus + receiver check |
| `make full` | long run: all KATs in RTL, 320×240 frame |
| `make one T=tb/test_top.py SEED=n` / `make waves T=...` | one test, reproducible / with waveforms |
| `make bundle T=...` | failure report `debug_bundle.md` to paste into Claude |
| `make hls-csim`, `make lint`, `make synth`, `make tables`, `make vectors` | HLS C-sim, Verilator lint, Yosys estimate, ROM regeneration, stage vectors |
| `python -m link.run_all` | the whole link + dashboard |
| `python experiments/scenario.py --scenario ... --policy ...` | one attack scenario → `sim_out/runs/` |
| `python experiments/compare_policies.py ...` | policies side by side → `sim_out/compare/` |
| `python experiments/measure_mode_tradeoff.py` | leakage vs cost per mode → `sim_out/mode_tradeoff.json` |
| `python experiments/benchmark_crypto.py --rtl` | cost of each protection method → `sim_out/benchmark/` |
| `python experiments/learned_attack.py ...` | neural attack (GPU) → `sim_out/learned_attack/` |

---

## 6. Repository map

```
model/        golden model (the referee): ascon, colour, DCT/quant, entropy, selective, container,
              jpeg (frame level), hw (stage level for tb/), metrics, tables, testimage, generators
rtl/          Verilog-2001 datapath + AXI (secure_jpeg_top.v); include/ = generated ROMs
tb/           cocotb testbenches (one per block family + top level)
vivado/       tb_secure_jpeg_top.v, gen_xsim_vectors.py, check_xsim_output.py, run_xsim.sh/.bat,
              xsim_project.tcl, xsim.prj, vivado_ooc.tcl
hls/          Vitis HLS DCT + quantiser
link/         system simulation (sender, channel, receiver, dashboard, keys, feedback, defence, wire)
experiments/  scenario runner, scenarios/, compare_policies, measure_mode_tradeoff, benchmark_crypto,
              learned_attack
scripts/      golden-model tools (run_video_eval, encode_image, mjpeg_server, receiver, export_vectors)
tests/        pytest: Ascon KATs, pipeline, contract equivalence, system layer
docs/         INTERFACES.md (contract v2), TESTING.md (+ bug log), DEBUGGING_WITH_CLAUDE.md
configs/      default.toml (shared by every node)
sim_out/      everything generated (not in git)
```

---

## 7. Results so far, comparison with published work, and how to make it IEEE-ready

All numbers below were produced by the scripts in this repo on a laptop-class CPU (Python
model, Icarus). Re-run them on your machines; board numbers come later.

### 7.1 Measured so far

**Hardware (RTL, Icarus, 100 MHz):**

* Every RTL block is bit-exact with the model under random stalls; all 1089 Ascon KATs pass in RTL.
* Throughput is **1.64 cycles/pixel → ≈199 fps at 640×480**, ≈66 fps at 720p, if timing closes at 100 MHz.
* **Encryption adds 0 cycles in every mode**: E0–E4 take the same cycles, because the keystream
  is pre-fetched and the tag is computed in parallel.
* Earlier Yosys estimate: ~5.3 K LUT, ~10% of the Zynq-7020. The real numbers come from Vivado (Role 1).

**Visual security** (synthetic CCTV scene, 320×240, q75; `measure_mode_tradeoff.py`):

| Mode | Leakage, edge correlation (0 = nothing) | SSIM of attacker image | Encrypted bits | File size vs plain |
|---|---|---|---|---|
| E0 | 0.996 | 0.95 | 0% | +0.6% (APP11) |
| E1 | 0.336 | 0.62 | 11.5% | ~+0.6% |
| E2 | 0.327 | 0.53 | 13.5% | ~+0.6% |
| E3 | 0.352 | 0.55 | 25.0% | ~+0.7% |
| E4 | 0.352 | 0.55 | 28.7% | ~+0.7% |
| E5 | **0.000** | 0.43 | 30.3% | **+13% (320×240), +21% (640×480)** |

**Key finding:** E3/E4 cost twice the encrypted bits of E2 but **do not** reduce the outline
leak. Amplitude and sign encryption never hides *which* coefficients are non-zero, and those
positions are the edges. Only E5's keyed MCU shuffle removes the sketch, at a bitrate cost.
This "sketch attack" weakness matches the literature (Li et al., IET SP 2020 survey) and is
exactly why Hirose et al. (our reference [3]) use restart-interval shuffling.

**Integrity and reaction**: `full_suite.json`, threshold policy, one run, every attack for 6 s, 25 s apart.

| Attack | What the receiver says | First rejection | Sender aware | Max protection | Rekey |
|---|---|---|---|---|---|
| Bit flip in scan | tag-mismatch | 0.0 s | 0.3 s | 0.3 s | yes (≥5 tag failures) |
| Mode downgrade E2 → E0 | tag-mismatch | 0.0 s | 0.3 s | 0.3 s | yes |
| Splice (old picture, new header) | tag-mismatch | 0.0 s | 0.3 s | 0.3 s | yes |
| Inject forged frames | tag-mismatch | 0.1 s | 0.3 s | 0.3 s | yes |
| Replay captured frames | replay / stale-epoch | 0.0 s | 0.3 s | 0.3 s | — |
| Hold back and release late | late / replay + gaps | 4.1 s (on release) | 1.3 s | 1.3 s | — |
| Jamming (all frames dropped) | (nothing arrives) | — | 1.3 s | 1.3 s | — |
| Flood of junk datagrams | junk counted, video fine | — | 0.3 s | 0.3 s | — |
| Feedback silenced | — | — | 3.3 s (dead-man) | 3.3 s | yes |
| Forged feedback | — | — | 0.3 s (tag fails at sender) | 0.3 s | — |
| Replayed feedback | — | — | 0.3 s (replay window) | 0.3 s | — |

Summary: 11/11 attacks mitigated, mean 0.72 s, **0 false alarms in 125 calm windows**.
`benign.json` (1–6% packet loss, 60–120 ms delay, jitter, 5% reordering, no attacks):
**0 false alarms in 149 windows**. Reordered frames are reported as `late`, not `replay`.
A degraded link is reported but does not raise encryption, because more encryption does not
help against loss. Reaction times vary between 0.3 s and 1.3 s with the 1-s window alignment,
so always report mean ± std over repeated runs (Role 3).

**Adaptive defence, learning scenario**: 5 rounds each of bit-flip and replay, 40 s calm in
between, final code (`compare_policies.py --scenario experiments/scenarios/learning.json --policies threshold bandit`).

| Policy | Mitigated | Mean time to max protection | Leakage while attacked | Mean cost | False alarms (calm windows) |
|---|---|---|---|---|---|
| threshold | 10/10 | 1.26 s | 0.042 | 0.189 | 0/301 |
| bandit (fresh memory) | 10/10 | 1.30 s | 0.054 | **0.164 (−13%)** | 0/301 |

The bandit's time to max protection per round:

* bit-flip: 4.3 → 1.3 → 1.3 → 0.3 → 1.3 s (the last is an exploration step);
* replay: 3.3 → 0.3 → 0.3 → 0.3 → 0.3 s.

After its first encounter with each attack it reacts as fast as the hand-written rules, at
13% lower cost; the rules stay slightly better on leakage. That is an honest trade-off, not
a win on every axis.

Reaction time for any policy is bounded by the decision window (1 s) plus the heartbeat
(0.5 s). Depending on where an attack starts within the window, the same policy measured
0.3 s in one run and 1.3–1.4 s in another, so report mean ± std over repeated runs.

**Cost of protection** (`benchmark_crypto.py`, 640×480, PC):

* Software selective encryption of a finished JPEG takes ~117–222 ms per frame in Python.
* Full-stream AES-128-GCM through OpenSSL takes **< 0.01 ms** and produces an unplayable file.
* On a laptop, full-stream AES is effectively free. So our argument must **not** be "faster
  than AES on a CPU". It is:
  1. the output stays a **playable, standard JPEG** (privacy-preserving preview, legacy viewers);
  2. encryption **inside the encoder costs 0 extra cycles**, with no extra buffering or latency;
  3. per-frame authentication of header + content;
  4. the target ARM Cortex-A9 has **no AES instructions**, so measure the board before claiming
     any energy advantage.

### 7.2 Where we stand against published work

| Work | Codec / platform | Cipher | Integrity | Plays in a normal player | Adaptive / feedback |
|---|---|---|---|---|---|
| Van Droogenbroeck & Benedett 2002 | JPEG, software, after encoding | DES/IDEA | no | yes | no |
| Kishore, Kumar & Patil 2015 (JRTIP) | JPEG in FPGA encoder (Stratix) | PN scrambling | no | yes | no |
| Bağbaba & Örs 2015 (ELECO) | JPEG in FPGA | TEA | no | not shown | no |
| Sbiaa et al. 2016 | H.264 in-encoder (VHDL) | stream cipher | no | yes | no |
| Rezk et al. 2021 (IEEE Access) | DWT + AES on Virtex-5 | AES-CBC + chaos | no | no | no |
| Hirose, Imaizumi & Kiya 2024 | JPEG bitstream, software | keyed XOR + block shuffle | no | yes | no |
| Sheng et al. 2025 (IEEE TMM) | HEVC, software | chaotic | no | yes | content-adaptive (not threat) |
| Gladis Kurian & Chen 2025 | Ascon on Artix-7, generic data | Ascon-AEAD128 | yes + replay (Bloom) | n/a | no |
| **This work** | JPEG/MJPEG in Zynq-7020 encoder | **Ascon-AEAD128 (NIST)** | **per-frame tag over header + scan, replay window, authenticated feedback** | **yes** | **threat-adaptive (rules + bandit), dead-man, ratchet** |

Defensible novelty statement (use this wording, not a stronger one):
> To our knowledge, this is the first FPGA-SoC MJPEG encoder that embeds NIST SP 800-232
> Ascon-AEAD128 keystream encryption of coefficient sign and amplitude bits at the entropy-coding
> stage, keeps the stream playable, and authenticates every frame. It adds an authenticated
> feedback loop that adapts the protection level to observed attacks. We measure the
> visual-security, bitrate, throughput, area and reaction-time trade-offs.

Do **not** claim: "first JPEG selective encryption" (2002), "first FPGA JPEG encryption"
(2015), "post-quantum secure" (Ascon is a symmetric 128-bit scheme), or "secure against all
attacks" (§7.4).

### 7.3 What makes it IEEE-publishable (checklist)

- [x] One verified contract; RTL bit-exact with the model; official KATs; CI on every PR.
- [x] Integrity: tamper, splice, inject, downgrade, replay, stale-key, feedback forgery and replay all rejected.
- [x] Honest visual-security evaluation, including the sketch leak, plus a fix (E5).
- [ ] Vivado post-route resources, WNS and power (Role 1). **Required**: Yosys estimates are not accepted as results.
- [ ] Real videos, not only the synthetic scene: several clips, mean ± std (Roles 4, 5).
- [ ] Learned attack per mode on held-out video (Role 5). This is the strongest security evidence.
- [ ] Repeated runs with mean ± std for every timing table (Roles 3, 5).
- [ ] Threat model + nonce-uniqueness argument (Role 2).
- [ ] (Strongly recommended) board measurement: fps, latency, and energy with a USB power meter.
- [ ] Reproducibility statement: every figure comes from a script in `experiments/`.

### 7.4 Limitations to state in the paper (reviewers reward this)

* Sign and amplitude encryption is *perceptual* protection: run lengths and size categories
  stay visible, so E1–E4 leak an edge sketch. E5 hides positions, but a jigsaw-solving attacker
  may partly re-order MCUs (not evaluated yet).
* E5 costs 13–21% bitrate at restart interval 1, and the RTL does not support it yet.
* The defence reacts only to *active* attacks; a passive eavesdropper is handled by the floor mode alone.
* Packet loss and jamming cannot be told apart from the receiver's side; the dead-man rule is conservative.
* The KDF uses Ascon-AEAD128 as a PRF instead of Ascon-XOF128 (Role 2 task).
* No side-channel protection of the Ascon cores (future work).
* All timings so far are from simulation and Python; board numbers are pending.

---

## 8. Rules for working with AI tools ("vibe coding" safely)

1. **The model is the referee.** Never change `model/` to make an RTL test pass, unless the model
   is wrong against T.81 or SP 800-232, and then say so in the PR. `CLAUDE.md` tells Claude the same.
2. **Every change comes with a test**, and `make test` must be green before you open a PR.
   CI (`.github/workflows/tests.yml`) runs everything on GitHub.
3. **Numbers only from scripts.** A number in the paper must be in a file under `sim_out/` produced
   by a script in `experiments/`. Commit the script and its command line, not the number.
4. **When something fails:** reproduce with the printed `SEED`, run `make bundle T=<test>` and paste
   `debug_bundle.md` into Claude (`docs/DEBUGGING_WITH_CLAUDE.md`). Add a row to the bug log in
   `docs/TESTING.md` §8 — rows 5–11 are from this PR and make good material for the report.
5. **Git:** `main` stays green. Work on a branch per task (`git switch -c role3-freeze-attack`),
   open a PR, and let another team member review it. Do not commit `sim_out/`, videos or `.pt` files.

---

## 9. Later (after the simulation is done)

**Multiple receivers.** The encoder encrypts each frame once. Each receiver gets its own tag key,
so one receiver cannot forge frames for another; that is a few microseconds of extra Ascon work
per receiver per frame. Removing a receiver = rekey everyone else. Optionally, use tiered access
(two keystreams: a "guard" key for signs only, an "admin" key for everything). Simulation:
`link/receiver.py` already takes its own ports, so N receivers = N processes plus a fan-out in the channel.

**Board bring-up.**

1. Vivado block design: Zynq PS + AXI DMA + `secure_jpeg_top`; bitstream; PYNQ overlay.
2. `board/sender.py` = `link/sender.py` with `encoder=board`, doing the register sequence of
   `tb/test_top.py::Encoder`, which is already the driver template.
3. Point the board at the laptop's channel or receiver IP and run the same dashboard.
4. Measure fps, latency and power; re-run `benchmark_crypto.py` on the ARM for the CPU baselines.

**Application requirements** (targets for the paper's requirements table):

| Requirement | Target | Status |
|---|---|---|
| Format compliance | 100% of frames open in VLC / ffmpeg / Pillow / OpenCV | met (tests) |
| Confidentiality (floor E2) | attacker image SSIM < 0.6, PSNR < 15 dB; edge leak reported honestly | E2: SSIM 0.53, 13.9 dB; E5 removes edges |
| Integrity | 100% of modified / injected / replayed / downgraded frames rejected | met in simulation |
| Exact recovery (medical) | key holder recovers the encoder's JPEG bit-exactly | met (all modes) |
| Throughput | ≥ 640×480 @ 30 fps; target 720p30 | RTL ≈199 fps @ 640×480 if 100 MHz closes |
| Encode latency (CCTV, drones) | < 33 ms per frame; end-to-end < 100 ms | RTL ≈5 ms/frame at 640×480 (1.64 cycles/px, 100 MHz); simulation p95 ≈ 110 ms (Python encoder) |
| Bitrate overhead | < 1% + 42 B/frame (E0–E4); E5 reported separately | E0–E4 met; E5 +13–21% |
| Alert time | operator warned within 1–2 s; dead-man 3 s | 0.3 s typical, 3.3 s dead-man |
| Hardware budget | < 25% of Zynq-7020 LUTs, timing met at 100 MHz | estimate ~10%; Vivado pending |
| Key management | no nonce reuse; rekey without downtime; old keys erased | met (64-bit session, ratchet) |
| Privacy law | CCTV and health video are personal data under India's DPDP Act 2023 | discuss in the paper |
