# The project, explained from the beginning

For the whole team (CMOS Crusaders): what we are building, why, how every part works, what each folder
and program does, what is finished, and what is left. Plain words first; the details live in the files
this one points to. Status as of 17 Oct 2026.

---

## 1. The idea in one minute

A security camera sends video over a network that other people can see (Wi-Fi, a shared LAN). Two
things can go wrong: someone **watches** the video, or someone **changes** it (replays old footage,
injects fake frames, cuts the feed).

The usual fix is to encrypt the whole stream (TLS, a VPN). That works, but it has two costs: the video
becomes unplayable for every normal tool (VLC shows nothing), and a small camera's processor spends a
lot of time and energy on encryption.

**Our idea:** do the encryption *inside the video encoder*, in hardware, and encrypt only the few bits of
each JPEG frame that carry most of the picture (the signs and sizes of the important coefficients).

* The frame is still a **valid JPEG**: VLC or a browser plays it, but the picture is scrambled.
* The **key holder** gets back the exact original frame.
* A **tag** (a cryptographic checksum) on every frame proves it came from our camera, unchanged, in order.
* It costs **zero extra clock cycles** in the encoder, because the encryption happens while the
  frame is being coded anyway.
* A small **defence loop** watches for attacks and raises the protection level when it sees one.

It runs on a **PYNQ-Z2** board: a Zynq chip with an FPGA (where our encoder is) and an ARM processor
(which runs Linux, Python, the network and the defence logic).

---

## 2. Five background ideas you need

**JPEG in six steps.** A frame is cut into 16x16-pixel macroblocks (MCUs). Each step is one hardware block:

1. **Colour conversion:** RGB → Y (brightness) + Cb, Cr (colour); colour is stored at half resolution (4:2:0).
2. **DCT:** each 8x8 block becomes 64 frequency coefficients (the first, "DC", is the average brightness).
3. **Quantisation:** divide the coefficients by a table and round: most become zero. This is where JPEG loses quality.
4. **Zig-zag + run-length:** list the 64 values from low to high frequency, write runs of zeros compactly.
5. **Huffman coding:** frequent symbols get short codes. Each non-zero value is a *size* (how many bits)
   plus the *amplitude bits* (the value itself, including its sign).
6. **Packing:** bits into bytes, plus headers → a `.jpg` file. Video = a stream of these (MJPEG).

**Selective encryption.** We XOR a secret keystream onto the sign and amplitude bits *after* step 4 and
*before* step 5. The Huffman codes, and so the file structure, do not change: every decoder still opens it.

**Ascon.** The NIST standard for lightweight cryptography (SP 800-232, 2025), designed for small
devices. We use Ascon-AEAD128 twice: as a **keystream generator** (the bits we XOR) and as a **tag**
(the checksum over the frame and its header).

**Nonce, tag, replay.** Every frame has a counter. The counter feeds the keystream (so no two frames
reuse a keystream) and the tag (so an old frame replayed later is detected). A key **ratchet** changes
the key over time; old keys are erased.

**Protection levels** (the dashboard's ladder):

| Level | What is encrypted | What an eavesdropper sees |
|---|---|---|
| E0 | nothing (tag only) | the picture, but tampering is detected |
| E1 | signs of the AC coefficients | an outline (and a trained neural network can undo E1) |
| E2 | + DC signs | outline sketch, no brightness |
| E3 | + AC amplitude bits | outline sketch |
| E4 | + all amplitude bits | outline sketch |
| E5 | E4 + the 16x16 blocks shuffled with a key | noise, no outline (golden model and lane-encoder RTL) |

The key holder recovers the exact original at every level.

---

## 3. How the whole system works

```
  camera ──► FPGA: colour → DCT → quantise → zig-zag ──► XOR keystream ──► Huffman → bytes ──┐
                                                  ▲ Ascon keystream            Ascon tag ◄───┤
                                                                                              ▼
  ARM: adds JPEG headers + our APP11 segment (level, session, counter, tag) ──► UDP over Ethernet
                                                                                              │
  laptop: receiver checks the tag → decrypts → shows the frame; anything wrong is rejected ◄──┘
          receiver ──► authenticated heartbeats ("I got 10 good frames, 2 bad") ──► ARM
  ARM: defence policy reads the heartbeats → raises the protection level / rekeys when attacked
```

In the simulation everything runs as separate programs on one PC that talk over UDP exactly as the
real devices will. A **channel** program sits in the middle and plays the network *and* the attacker.

**Two hardware versions** of the encoder exist:

* **Contract v2** (`rtl/secure_jpeg_top.v`): one pipeline, 1 pixel per clock in, about 1.5 clocks per
  pixel (4:2:0 has 1.5 samples per pixel). 65 Mpixel/s at 100 MHz.
* **Contract v3, "lanes"** (`rtl/secure_jpeg_lanes_top.v`): 2 or 4 copies of the pipeline, 2 pixels per
  clock in. Each row of 16x16 blocks becomes an independent JPEG *restart segment*, coded by its own
  lane with its own keystream, and the segments are joined back in order. 122 Mpixel/s (2 lanes) and
  176 Mpixel/s (4 lanes) at 100 MHz. The idea came from the retina (parallel channels, each seeing part
  of the image) and from camera chips (several pixels per clock).

A "contract" is a precise definition of the bytes the encoder must produce; `docs/INTERFACES.md` has both.

---

## 4. The rule everything rests on: the golden model

`model/` is a Python version of the whole encoder and receiver, written straight from the two standards
(ITU-T T.81 for JPEG, NIST SP 800-232 for Ascon). It is the **referee**:

* every Verilog block is tested against it, bit for bit, with random inputs and random stalls;
* the whole encoder's output bytes must equal the model's, in Icarus and in Vivado's simulator;
* the model is never changed to make a hardware test pass (only if it contradicts a standard).

When a test fails, the hardware is wrong until proven otherwise. 142 model/system tests and 16 RTL
testbenches run with `make test`; every real bug found is logged in `docs/TESTING.md` §8 (29 so far).

---

## 5. The repository, folder by folder

### Top level

| File | What it is |
|---|---|
| `README.md` | front page: what the project is, how to start |
| `GUIDE.md` | the team's work plan: every task with owner, steps, and the claim → evidence checklist (§5) |
| `CLAUDE.md` | rules for Claude Code when it works in this repo |
| `Makefile` | short commands: `make test`, `make xsim-icarus`, `make bundle`, `make tables` ... |
| `requirements.txt` | Python packages |

### `model/` — the golden model (Python)

| File | In simple words |
|---|---|
| `ascon.py` | the Ascon cipher, checked against all 1089 official test vectors |
| `color.py` | RGB → YCbCr, 4:2:0, cutting into 8x8 blocks |
| `dct_quant.py` | the DCT and quantiser, with exactly the hardware's integer arithmetic |
| `entropy.py` | zig-zag, run-length, Huffman, packing bits into bytes, restart segments |
| `selective.py` | which bits each level encrypts; the eavesdropper's "replacement attack" |
| `container.py` | building and reading the JPEG file, incl. our APP11 security segment |
| `jpeg.py` | the whole sender and receiver: `encode_frame`, `receive_frame` (v2 and v3) |
| `hw.py` | the same encoder split stage by stage like the hardware (the RTL tests use it) |
| `tables.py`, `testimage.py`, `metrics.py` | JPEG tables, synthetic test images, PSNR/SSIM/edge metrics |
| `gen_rtl_tables.py`, `gen_vectors.py` | generate ROM tables for the Verilog, and test vectors |

### `rtl/` — the hardware (Verilog-2001)

| File | In simple words |
|---|---|
| `secure_jpeg_top.v` | the v2 encoder: all blocks below chained together, plus the registers and streams |
| `rgb2ycbcr_block.v` | colour conversion + line buffers (holds 16 lines to form blocks) |
| `dct_stage.v`, `dct8x8.v` | the DCT, pipelined over five stages |
| `quantiser.v` | quantisation by multiplying with reciprocals (no divider) |
| `zigzag_rle.v` | zig-zag order, DC difference, run-length symbols (two stages since 17 Oct) |
| `selective_enc.v` | XORs the keystream onto the chosen bits |
| `huffman_enc.v`, `bit_packer.v`, `scan_word_packer.v` | Huffman codes → bytes (with 0xFF stuffing) → 32-bit words |
| `ascon_round.v`, `ascon_aead128_core.v` | the Ascon permutation and the AEAD core (one round per clock) |
| `keystream_gen.v`, `tag_unit.v` | the keystream and the per-frame tag, each with its own Ascon core |
| `axil_regs.v` | the registers the ARM writes (key, size, mode, counter) and reads (tag, length) |
| `secure_jpeg_lanes_top.v` | the v3 encoder: dealer → lanes → merger → tag |
| `encoder_lane.v`, `rgb2ycbcr_2px.v` | one lane (2 pixels per clock front end + the same pipeline) |
| `kseg_unit.v`, `segment_merger.v`, `byte_fifo.v` | per-frame segment key, joining segments in order, lane buffers |
| `huffman_packer.v` | small wrapper used only by a testbench |
| `include/*.vh` | generated tables (never edit by hand; `make tables`) |

### `tb/` — hardware tests (cocotb + Icarus Verilog)

One test file per group of blocks (`test_crypto_units.py`, `test_dct_quant.py`, `test_entropy.py`,
`test_rgb2ycbcr_block.py`, `test_top.py`, `test_lanes_top.py`, `test_ascon_core.py`). Each drives random
inputs with random stalls and compares every output with `model/`. `common.py` holds the shared setup.

### `vivado/` — the FPGA tool flow

| File | In simple words |
|---|---|
| `run_vivado_day.py` | **one command for all of Vivado**: simulation, synthesis + place & route, both PYNQ bitstreams, report tables. Also has the `vectors`, `check`, `parse` helper commands |
| `tb_secure_jpeg_top.v` | the self-checking testbench for Vivado's simulator (XSim), both encoders |
| `vivado_ooc.tcl` | synthesis + place & route of one design on its own ("out of context") → area, timing, power |
| `run_xsim.bat` / `.sh`, `xsim.prj`, `xsim_project.tcl` | run XSim in batch or GUI |

### `link/` — the system simulation (the network, the receiver, the defence)

| File | In simple words |
|---|---|
| `run_all.py` | starts everything: channel, receiver, dashboard, sender |
| `sender.py` | the camera node (a "digital twin" of the board): encodes, sends, runs the defence |
| `channel.py` | the network + the attacker: loss, delay, and 11 attacks (bit flip, replay, jamming ...) |
| `receiver.py` | the key holder: checks tags, rejects replays, decrypts, sends heartbeats back |
| `defence.py` | the protection policies: fixed, threshold rules, and a learning (bandit) policy |
| `feedback.py`, `keys.py` | authenticated heartbeats; the key schedule and ratchet |
| `wire.py`, `config.py`, `buslog.py`, `sources.py`, `backends.py` | UDP fragments, settings, event logging, video sources, encoder choice (model / RTL) |
| `dashboard.py`, `static/dashboard.html` | the web dashboard on http://localhost:8000 |

### `experiments/` — every number in the paper comes from one of these

| Script | Question it answers |
|---|---|
| `measure_mode_tradeoff.py` | how much does each level leak, and what does it cost? |
| `scenario.py` (+ `scenarios/*.json`) | scripted attacks against the live link: detection and reaction times; `--external-sender` uses the real board |
| `compare_policies.py`, `policy_seeds.py` | threshold rule vs learning policy, over 10 seeds |
| `learned_attack.py` | can a neural network (U-Net) undo the encryption? |
| `recognition.py` | can a person detector find people in the eavesdropper's picture? |
| `restart_interval.py`, `chosen_plaintext.py`, `block_transform.py` | attacks on E5's block shuffle |
| `standard_metrics.py` | the usual image-encryption metrics (NPCR, UACI, entropy ...), for E1-E5 and E5's hardware form |
| `benchmark_suite.py` | SVE-Bench: ours and four published schemes under the same attacks, incl. a known-plaintext attacker, plus the metrics those papers print (`docs/BENCHMARK_METHOD.md`) |
| `hw_efficiency.py` | Mpixel/s per kLUT and nJ per pixel per design and mode, next to published FPGA designs |
| `size_leak.py` | do frame sizes reveal motion? (yes, at every level) |
| `stall_profile.py`, `parallel_lanes.py`, `lanes_rtl_throughput.py` | where the cycles go; the lanes, projected and measured |
| `rate_control.py`, `change_driven.py` | bitrate control like a motor drive; retina-style change-driven coding |
| `benchmark_crypto.py` | cost of hardware vs software encryption per frame |

### `future_work/` — the board, baselines, extra attacks

| Folder / file | In simple words |
|---|---|
| `board/block_design.tcl` | builds the PYNQ-Z2 system in Vivado (ARM + DMA + our encoder) → bitstream |
| `board/pynq_driver.py` | Python driver for our encoder on the board (and a mock that emulates it) |
| `board/first_contact.py` | **the first board test**: bit-exact check, then speed |
| `board/board_sender.py` | the camera node on the board, with the FPGA doing the encoding |
| `board/sjpeg_bd_top.v`, `sjpeg_lanes_bd_top.v` | thin wrappers that let Vivado put our encoder into the block design |
| `baselines/` | software baselines (libjpeg-turbo, AES-GCM) and the power / energy tables |
| `attacks/` | jigsaw-puzzle solvers against E5 |
| `figures/` | the visual-security grid, format compliance, all result tables |
| `kaggle/kaggle_runs.py` | every Kaggle (GPU) run in one file; pick `JOB = "..."` |

### `paper/`, `docs/`, `tests/`, `scripts/`, `hls/`

| Folder | In simple words |
|---|---|
| `paper/conference.tex`, `paper/access.tex` | the 6-page conference paper and the full IEEE Access paper (sections in `paper/sections/`) |
| `paper/data/` | the frozen results the paper is built from (never edit by hand) |
| `paper/make_assets.py` | turns `paper/data/` into every table, figure and number in the paper |
| `docs/INTERFACES.md` | the exact byte formats, register map, nonce layout (contracts v2, v3) |
| `docs/TESTING.md` | how we test, the bug log (§8), debugging with Claude (§9) |
| `docs/VIVADO_ONE_DAY.md` | the Vivado guide and the history of the six runs |
| `docs/BOARD_BRINGUP.md` | **the board guide**: from the SD card to every hardware number |
| `docs/RESEARCH.md` | the research experiments R1–R8 and the throughput notes |
| `docs/TEAM_CONTEXT.md` | a summary to give Claude in a new chat |
| `tests/` | pytest for the model, the link, the experiments, the paper build |
| `scripts/tools.py` | older demo tools (VLC stream server, receiver window, test vectors, `make bundle`) |
| `hls/` | an alternative DCT + quantiser in Vitis HLS (same arithmetic); the bitstreams use the Verilog `rtl/dct8x8.v` |

---

## 6. What is done (with the evidence)

| Area | Result | Where it comes from |
|---|---|---|
| Golden model | Ascon passes all 1089 official vectors; encoder round-trips bit-exact | `tests/` |
| Hardware correctness | both encoders bit-exact with the model, all levels, random stalls; also in Vivado's XSim | `tb/`, `vivado/` |
| Format compliance | all six levels open in Pillow, OpenCV, scikit-image and FFmpeg | `future_work/figures/format_compliance.py` |
| Encryption cost | 0 extra cycles (E0–E4 differ by at most 2 cycles per frame, handshake noise) | `benchmark_crypto.py --rtl` |
| Throughput (RTL, 640x480, 100 MHz) | 65 Mpixel/s (1 pipeline), 122 (2 lanes), 176 (4 lanes) | `stall_profile.py`, `lanes_rtl_throughput.py` |
| Area + timing (Vivado runs 6-7) | encoder 5,037 LUT / 24.5 BRAM / 23 DSP; 2 lanes with E5 10,069 LUT; 4 lanes with E5 16,893 LUT; **all meet 100 MHz**; both PYNQ-Z2 systems meet 100 MHz (the 2-lane one with E5) | `paper/data/vivado/` |
| Visual security | E1–E4: eavesdropper sees an outline (edge correlation 0.28–0.56); E5: none (jigsaw solvers at chance) | `measure_mode_tradeoff.py`, `future_work/attacks/` |
| Learned attacker | a U-Net breaks E1 (edge correlation 0.69); adds little on E2/E4; nothing on E5 | `learned_attack.py` |
| Person detection | 68–100 % of people found in plain frames, ≤ 3 % under E2/E4, 0 % under E5 | `recognition.py` |
| Active attacks | all 11 attacks mitigated in all 3 runs, 0.91 ± 0.02 s on average, 0/375 false alarms | `scenario.py full_suite` |
| Bad network, no attack | 0/447 false alarms with up to 6 % loss, delay, jitter, reordering | `scenario.py benign` |
| Frame-size leak | every level leaks motion through frame sizes; padding fixes it cheaply only for fixed cameras | `size_leak.py` |
| Policies | the learning policy encrypts 14 % less but reacts later; threshold rule stays default | `policy_seeds.py` |
| Board path (emulated) | driver, bit-exact gate, live link, dashboard and attack scenarios all run against the golden-model emulation of both bitstreams | `docs/BOARD_BRINGUP.md` |
| Paper | 6-page conference draft and 12–13-page IEEE Access draft, every number generated | `paper/` |

---

## 7. What is left

**Deadlines:** working hardware by **12 Nov 2026**, paper by **15 Dec 2026**.

| # | Task | Owner (GUIDE.md role) | Guide |
|---|---|---|---|
| A1–A2 | **Bit-exact gate and real fps on the PYNQ-Z2** (both bitstreams) — the milestone | 1 | `docs/BOARD_BRINGUP.md` §5 |
| A3 | ARM software baseline on the same board | 2 | §6 |
| A4 | Power and energy per frame (USB meter optional; Vivado estimate without it) | 1 + 5 | §7 |
| A5 | Live link board → laptop with the dashboard | 3 + 4 | §8 |
| A6 | Attack scenarios with the board as sender (3 runs each) | 3 | §8, A6 |
| A7–A8 | Webcam on the board; 2-minute demo video | 4 | GUIDE.md §4.2 |
| B1 | Selective encryption in C on the ARM (the fair software baseline) | 2 | GUIDE.md §4.3 |
| B3, B22 | One page of threat model + nonce argument; E1's status after the U-Net result | 2 (+5) | GUIDE.md §4.3 |
| B6 | E5 in hardware: ✅ RTL done (H1); rebuild the lane bitstream in Vivado | 1 | `docs/HW_TODO.md` |
| — | Commit the two `.bit` + `.hwh` pairs so everyone can use the board | 1 | — |
| — | Paper: author e-mails, order, bios, funding line, AI-assistance statement; the board-results section after A1–A4 | all | `paper/conference.tex`, `paper/access.tex` (red `TODO`s) |

Nice-to-have (paper future work): a shared Ascon core (B7), Ascon-XOF key derivation (B8), the colour
converter pipelined for 125 MHz, multiple receivers (B11), masking against power analysis.

---

## 8. How to run the main things

| Goal | Command (from the repo root) |
|---|---|
| Everything still correct? | `make test` (≈ 4 min) |
| The live demo | `py -m link.run_all --set sender.source=clips/denzel.mp4`, open http://localhost:8000 |
| A scripted attack run | `py experiments\scenario.py --scenario experiments\scenarios\quick.json` |
| Vivado (everything) | `py vivado\run_vivado_day.py --steps xsim ooc lanes bd bd_lanes parse --maxw 9 10 --periods 8.0 6.667 --jobs 2` |
| Rebuild the paper | `python paper/make_assets.py`, then `make -C paper all` |
| Board, without a board | `py -m future_work.board.first_contact --mock-lanes 2 --sizes 64x48 --frames 2 --timing-frames 2` |
| A failing test, for Claude | `make bundle T=tb/<file>.py::<test>` → paste `debug_bundle.md` |

---

## 9. Words you will hear

| Word | Meaning |
|---|---|
| RTL | the hardware description (our Verilog) |
| bit-exact | the hardware's output bytes equal the model's, every single one |
| cocotb, Icarus | Python test framework for Verilog; a free Verilog simulator |
| XSim, Vivado | AMD's simulator; AMD's FPGA tool that turns Verilog into a bitstream |
| out of context (OOC) | synthesising one design alone, to measure its own area and timing |
| WNS | worst negative slack: positive = the design meets the clock, negative = too slow |
| LUT, FF, BRAM, DSP | the FPGA's logic cells, flip-flops, memory blocks and multipliers |
| bitstream (`.bit`) + `.hwh` | the FPGA configuration file and its description for PYNQ |
| AXI-Lite, AXI-Stream, DMA | register bus (ARM → our registers); data stream; the engine that moves frames between memory and our encoder |
| MCU, restart segment | a 16x16 macroblock; an independently decodable part of a JPEG scan |
| keystream, tag, nonce | the secret bits we XOR; the frame's checksum; the never-repeating frame number |
| replay, dead-man rule | re-sending old frames; "no heartbeat for 3 s → assume attack" |
| edge correlation | how much of the scene's outline an eavesdropper recovers (0 = none, 1 = all) |
