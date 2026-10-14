# Research suite: speed, regulation and change-driven coding (R1-R5)

Started 14 Oct 2026 on branch `research-suite`. None of this touches the board baseline: the RTL used
for the PYNQ-Z2 is unchanged by R2-R4 (they are model-level studies), and R1 only observes the RTL.
Rules as everywhere: every number comes from a script that writes `sim_out/`; the golden model is the
referee; every failure gets a bug-log row and a new approach, not a workaround.

**Run everything at once:** `future_work/kaggle/kaggle_research.py` (one Kaggle cell, ~1 h, CPU only)
and, on the laptop with Vivado, `python vivado\run_vivado_day.py --steps ooc parse --periods 8.0 6.667`
(R5). Status: the numbers below are from the development VM on the synthetic scene and the RTL in
Icarus; the Kaggle run adds the real and open clips. Nothing here is in the paper yet.

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

## Ideas considered and not pursued

* "Chemistry-inspired" and generic "physics-inspired" methods: no mechanism that maps onto pixel
  throughput; Vivado's placer already uses annealing-style optimisation.
* Fast DCT (Loeffler/AAN): does not raise throughput by itself (the DCT already takes one sample per
  clock); worth it only to cut DSPs per lane once R2 is built.
