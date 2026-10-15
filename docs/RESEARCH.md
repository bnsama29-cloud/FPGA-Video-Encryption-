# Research suite: speed, regulation and change-driven coding (R1-R5)

Started 14 Oct 2026 on branch `research-suite`. None of this touches the board baseline: the RTL used
for the PYNQ-Z2 is unchanged by R2-R4 (they are model-level studies), and R1 only observes the RTL.
Rules as everywhere: every number comes from a script that writes `sim_out/`; the golden model is the
referee; every failure gets a bug-log row and a new approach, not a workaround.

**Run everything at once:** `future_work/kaggle/kaggle_research.py` (one Kaggle cell, ~1.5 h, CPU only)
and, on the laptop with Vivado, `python vivado\run_vivado_day.py --steps ooc parse --periods 8.0 6.667`
(R5). Status: the sections R1-R7 below were written from the development VM (synthetic scene, RTL in
Icarus). The Kaggle run of 15 Oct 2026 (7 sources, 47/47 steps PASS, snapshot in
`paper/data/research/`) tested them on four film clips and the two open Blender films; the next
section says what held and what did not. In the paper: R1 (measured VGA throughput) and R7 (frame-size
leak, E0-E5 and padding rows).

## What the real clips changed (Kaggle, 15 Oct 2026)

An extra clip `17735` (added by the user in the 2nd rerun, content not yet described) is kept out of the paper until it is labelled and hashed in `future_work/clips_manifest.md`: its frame sizes barely vary (12-16 kB) and no level leaks motion through them (0.50), so it is not the fixed camera with people walking that R7 needs.

Important for reading the numbers: the six clips are **edited films** (shot cuts, camera motion). The
threat model of R4 and R7 is a **fixed camera**; only the synthetic scene is one so far. A short clip
from a phone on a stand (a room, people walking in and out) is the most useful next input.

| | Synthetic (fixed camera) | Six film clips | Verdict |
|---|---|---|---|
| R1 cycles/px at 640x480 (RTL) | predicted 1.541 | measured **1.534** = 65.2 Mpx/s at 100 MHz | law confirmed; in the paper |
| R2 lanes exact | all checks OK | all checks OK on every clip | holds |
| R2 restart cost per MCU row | 0.7 % | 0.6-2.2 % mean, up to 4.7 % on a frame | higher than estimated; still small |
| R3 rate control (2nd rerun) | FF+PI 1.3 % error after settling (after bug #26) | 5 clips: fixed quality 33-62 %, I 5-17 %, FF+PI 6-21 %; Tears of Steel still oscillated between q 5 and 20 (bug #26: plant gain grows at low quality), fixed by controlling ln(quantiser scale); needs one more R3 run | regulation works; I best in steady state |
| R4 change-driven bytes | 22 % of full | 41-78 % | a fixed-camera technique; modest on films |
| R4 count leak (hidden map) | 0.95 | 0.63-0.87 | the count still leaks everywhere |
| R4 constant 25 % + padding | 46 % bytes, SSIM 0.945 | 57-95 % bytes, SSIM 0.76-0.93 | worth it only for fixed cameras |
| R6 block transforms | adds nothing | adds nothing on all 7 (jigsaw at chance for both; oracle SSIM within 0.01; size within 0.5 %) | negative result confirmed |
| R6 SSIM if positions were solved | 0.55 | 0.05-0.38 | real content reveals less than the synthetic scene |
| R7 leak, E0 ... E5 | 0.94-0.96 | 0.50-0.95 (one clip at chance) | **identical across levels on every source** (within 0.02) |
| R7 constant-size padding | closes it, +3 % bytes | closes it, +31 ... +179 % bytes | the cost depends on how much sizes vary |
| R7 rate control + pad to 105 % of budget | 0.51, 2 % frames over | 0.51-0.73, 13-36 % of frames over the cap | **does not hide motion on real footage**: scene cuts beat the controller |
| R7 deployable padding (running max) | 0.54 for +3 % | 0.54-0.78 for +4 ... +71 % | the practical defence for a fixed camera; partial on edited clips |
| R8 chosen-plaintext on the E5 shuffle | learned permutation places 0.4 % of next frame's tiles (chance) | same on all 6 clips; edge corr. <= 0.02 vs 0.28-0.47 for a key-only shuffle | per-frame permutation defeats the attack of Li et al. |
| R7 padding to 1 KB steps | 0.50 (0.75 in a rerun, bug #24) | 0.52-0.94 | unreliable: depends on where sizes fall |

Conclusions:
1. **The protection level does not change the size channel at all** (E0 = E5 within 0.02 on every
   source); content does. A fixed camera with a person walking is the worst case (0.95).
2. Constant-size frames are the only defence that worked on every source. For a fixed camera it is
   almost free; for footage whose size swings it costs up to 2.8x the bytes. Rate control that keeps
   the quality slow-moving plus padding to a cap is the candidate for the middle ground (R3/R7 rerun).
3. Change-driven coding is attractive only for fixed cameras; on films it saves 22-59 % at a visible
   quality loss.

## Why the encoder makes ~61-65 Mpx/s

4:2:0 sampling gives 1.5 samples per pixel and the DCT takes one sample per clock, so this design
can never go below **1.5 cycles/pixel**. Everything else is overhead on top of that floor.

## R1 -- where the cycles go (`experiments/stall_profile.py`, RTL, cycle-accurate)

* Cycles/pixel are **identical for every image and protection level** (scene, noise, colour bars;
  E0/E2/E4). The entropy path (RLE, encryption, Huffman, packer) is never the bottleneck; it is idle
  ~83 % of the time.
* The excess over 1.5 is a per-frame cost: the DCT waits while the first 16-line MCU-row buffer fills.
  Fit over four frame sizes: **cycles/pixel = 1.5 + 1.225 / (MCU rows)** (measured 1.924, 1.689, 1.639,
  1.570 at 64x48 ... 320x240).
* Consequence for the paper: the 1.64 cycles/pixel of the 160x128 benchmark is pessimistic for real
  frames. Predicted: 1.541 at 640x480 (65 Mpx/s at 100 MHz), 1.527 at 1280x720. The Kaggle run measures
  640x480 to test the prediction before the paper uses it.
* New idea from this: let the next frame fill while the previous one drains (no reset of the row
  buffers between frames) -> 1.5 at any size (+3 % at VGA).

## R2 -- parallel lanes over restart segments (`experiments/parallel_lanes.py`, model + event model)

* Restart markers (E5 uses them for security) reset the DC prediction, so segments can be coded by
  independent lanes and merged in order. Checked byte-exact for N = 1, one MCU row and four rows,
  L = 2, 3, 4 lanes; the restart-row file decodes to the same pixels as the standard file.
* **Design finding:** today's keystream is one Ascon stream per frame, so a segment's keystream bits
  depend on all earlier segments: lanes could not encrypt independently
  (`test_sequential_keystream_is_not_lane_safe`). Proposed fix (contract-v3 candidate, model only):
  K_seg = Ascon-MAC(K, N_enc(session, frame), "lanes") once per frame, segment s uses nonce (s, frame)
  under K_seg. Unique per frame, so no (key, nonce) pair repeats; verified to decrypt and to merge exactly.
* Cost: one restart segment per MCU row adds **0.6 %** bitrate.
* Throughput (event model, validated against the RTL: 1.631 vs 1.639 and 1.570 vs 1.570 cycles/pixel):

  | Configuration (640x480) | Cycles/px | Mpx/s @100 MHz | @150 MHz | LUT (proj.) | DSP | BRAM36 |
  |---|---|---|---|---|---|---|
  | today: 1 lane, 32-bit input | 1.535 | 65 | 98 | 5,039 | 23 | 24.5 |
  | 2 lanes, 32-bit input | 1.050 | 95 | 143 | 7,584 | 45 | 36.5 |
  | 2 lanes, 64-bit input, frame overlap | 0.751 | 133 | 200 | 7,584 | 45 | 36.5 |
  | 4 lanes, 64-bit input, frame overlap | 0.500 | 200 | 300 | 12,674 | 89 | 60.5 |

  With one pixel per clock at the input, two lanes already hit the input limit (1.0 cycles/px).
  Lanes > 1 are projections, not RTL measurements.

## R3 -- bitrate regulation like a motor drive (`experiments/rate_control.py`, model)

Set point: bytes per protected frame (E2), following the link's bandwidth (100 % -> 60 % -> 120 %);
actuator: JPEG quality. Gains set on the synthetic scene only (the clips are the test).

**Kaggle run, 15 Oct: two failures, two fixes.** (1) The nominal budget was the median of the first 5
frames; Sintel and Tears of Steel open on black (1,853 bytes, headers only), so the set point was a
black frame and every controller sat at quality 5 (bug #22). Now: median size at quality 75 over the
clip, and frames whose budget lies below their size at quality 5 are reported as infeasible. (2) With
the quality pinned, FF+PI's online model got no information, its covariance grew 1.25x per frame and
the feed-forward slammed q between 5 and 95 (estimator windup, bug #23). Now: the model learns only
when q moved, the slope stays in [0.005, 0.08], the jump is bounded. Synthetic scene after both fixes
(150 frames): FF+PI 1.4 % error after settling, settles in 1 frame, 0 % of frames >10 % over; the
table below is the earlier VM run. The real clips need a rerun.

| Controller | Error after settling | Frames >10 % over budget | Settling after the drop | Overshoot |
|---|---|---|---|---|
| fixed quality 75 (today) | 32 % | 33 % | never | +81 % |
| bang-bang | 5.5 % | 9 % | 8 frames | +49 % |
| I (incremental) | 1.5 % | 4 % | 4 | +21 % |
| PI (velocity form) | 2.5 % | 8 % | 7 | +26 % |
| **FF+PI** (online model + PI) | **1.5 %** | **1 %** | **3** | **+4 %** |

Lesson recorded: the "P" controller that adds Kp*error to the quality every frame is an integral
controller; the positional PI with a slow integral was the slowest. Velocity-form PI is the drive form.

## R4 -- retina-inspired change-driven coding (`experiments/change_driven.py`, model)

Only changed 16x16 blocks are coded (each a restart segment), compared with the source pixels sent
last time (conditional replenishment). Synthetic corridor scene, 60 frames:

| Policy | Bytes vs full | Blocks coded | PSNR | Count leak | Size leak |
|---|---|---|---|---|---|
| full MJPEG (today) | 100 % | 100 % | 35.9 | -- | **0.93** |
| full + size padding | 103 % | 100 % | 35.9 | -- | 0.00 |
| changed blocks, visible map | 22 % | 7 % | 33.6 | 0.96 (mask 0.88) | 0.96 |
| changed blocks, hidden map | 22 % | 7 % | 33.6 | **0.96** | 0.96 |
| constant 25 % with useful chaff | 38 % | 25 % | 34.8 | **0.00** | 0.44 |
| **constant 25 % + size padding** | **48 %** | 25 % | 34.8 | **0.00** | **0.00** |

* Hiding the change map is useless: the block COUNT per frame correlates 0.96 with the true motion.
* Constant-rate coding with "useful chaff" (unchanged blocks refreshed oldest-first instead of dummy
  blocks) removes the count channel, and padding every frame to a fixed size removes the size channel,
  at about half the bytes of full MJPEG and -1.1 dB.
* **Finding that applies to today's design:** plain MJPEG frame sizes already track motion (0.93 on
  this scene), whatever the protection level. A size-padding option belongs in the threat-model
  discussion of the paper (to be confirmed on the real clips).
* Speed: the encoder core does 25 % of the work, so with one pixel per clock at the input the core is
  no longer the limit (1.0 cycles/px, input-bound); a change-reporting camera would remove that bound.

## R5 -- what limits the clock (`vivado/run_vivado_day.py --periods 8.0 6.667`)

Runs the encoder at 125 and 150 MHz and lists, for the worst paths, the block they start and end in
(`parse_reports.py`, "Worst setup paths"). From run 3 at 100 MHz, after the colour converter (fixed in
run 4) the next block is `u_rle` (zig-zag/RLE, slack +0.091 ns).

## R8 -- chosen-plaintext attack on the E5 shuffle (`experiments/chosen_plaintext.py`)

Li et al. (J. Shanghai Jiaotong Univ. (Sci.), 2025) recover images encrypted with JPEG block-position
shuffling by a chosen-plaintext attack: show the camera a designed picture, read where each block went
(non-zero counts survive), and reuse that permutation. It works when the permutation depends on the
key only. E5's permutation also depends on the frame nonce. Best case for the attacker (exact
permutation of frame t), applied to frame t+1 (synthetic scene, 6 pairs, 300 tiles):

| Attacker's picture of frame t+1 | Tiles in place | Edge corr. | SSIM |
|---|---|---|---|
| as seen | 0.4 % | 0.009 | 0.434 |
| key-only shuffle (what the attack needs) | 100 % | 0.347 | 0.549 |
| **E5, per-frame permutation** | **0.4 %** (chance) | -0.003 | 0.435 |

## R6 -- E5 hardened with keyed DCT-domain block transforms (`experiments/block_transform.py`) -- negative result

Motivation: plain block scrambling falls to jigsaw solvers, independent per-block keyed transforms
stop them (Chuman and Kiya, arXiv:2207.08109). For the DCT-II, mirroring a block is negating its odd
coefficients and transposing it is transposing them, so all 8 symmetries are exact, format-compliant
operations on the quantised coefficients (DC unchanged; tested).

Result (synthetic scene): **the transform adds almost nothing**, and the reason is instructive. A flip
in the DCT domain *is* a pattern of sign changes, and E4/E5 already encrypt every sign (the attacker's
replacement view drops signs anyway). Only transposition is left: with oracle tile positions, SSIM
0.555 for E5 against 0.545 for E5+T; our jigsaw solver is at chance for both (~1 % neighbours).
**Consequence:** E5's protection rests entirely on the block *positions* staying unsolved; an attacker
who recovered them would see SSIM ~0.55. Stronger solvers are the threat to watch (GUIDE B9).

## R7 -- the frame-size side channel of every level (`experiments/size_leak.py`)

Encryption hides content, not length. Wampler et al. (IEEE 2015) detected events in encrypted
IP-camera traffic from sizes and timing. Synthetic scene, 90 frames; the attacker only sees sizes:

| Stream | Size-motion corr. | Event detection (separability, 0.5 = chance) | Bytes vs E2 |
|---|---|---|---|
| E0 ... E4 | 0.91-0.92 | **0.93-0.94** | 100 % |
| E5 | 0.91 | 0.93 | 111 % |
| E2, padded to multiples of 1 KB | 0.68 | 0.72 | 105 % |
| **E2, constant size** (padded to the largest frame) | **0.00** | **0.50** | **103 %** |
| E5, constant size | 0.00 | 0.50 | 114 % |
| E2, FF+PI rate control + pad to 105 % of budget | -0.22 | 0.51 | 106 % (1 % frames over) |

* **Every protection level, including E5, tells an eavesdropper when something moves.** The event
  detector needs no training: frame size minus the smallest size of the last 30 frames.
* Constant-size frames close the channel; on this scene for +3 % bytes. The cost on real clips (whose
  sizes vary more) is what the Kaggle run measures.
* Hypothesis confirmed: rate control alone does not close it -- it **moves the leak into the quality
  factor**, which the quantisation table in the JPEG header shows in clear (separability 0.69-0.76).
  So: fixed quality + constant-size padding, or rate control that changes quality only slowly.
* Method note: the first detector (|size - median of the last 10|) looked for size *changes* and gave
  AUC < 0.5, i.e. it measured the wrong thing; a person *present* makes every frame larger. The
  background-subtraction detector and the separability max(AUC, 1-AUC) are what an attacker would use.

## Ideas considered and not pursued

* "Chemistry-inspired" and generic "physics-inspired" methods: no mechanism that maps onto pixel
  throughput; Vivado's placer already uses annealing-style optimisation.
* Fast DCT (Loeffler/AAN): does not raise throughput by itself (the DCT already takes one sample per
  clock); worth it only to cut DSPs per lane once R2 is built.
