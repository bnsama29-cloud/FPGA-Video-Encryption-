# Benchmark plan: every metric against the published designs (21 Oct 2026)

Goal: a design and an evaluation that later papers have to compare against. That means two things:
win every metric where a win is physically possible on the xc7z020, and for the rest report the
fair metric honestly instead of hiding it (a reviewer finds a hidden weakness in five minutes).

Published numbers: `paper/data/related/compare.json` (each row checked against its source).
Ours: `paper/data/vivado/` (post-route), `paper/data/lanes_rtl/` (cycle-accurate RTL), `paper/data/board/`.

## 1. Where we stand

| Metric | Best published (source) | Ours today | Status | What closes it |
|---|---|---|---|---|
| Clock (MHz) | 150 logiJPGE (Zynq-7020), 166 CAST (Artix-7), 200 Ascon core alone | **125 met** (v2 +0.060 ns, 2 lanes +0.213 ns, run 9); 100 for 4 lanes and every PYNQ-Z2 system | behind | run 10: skid buffers + keystream ring + packer + zig-zag flag (bug #36), timing-driven flow; targets 150 and 166 MHz |
| Throughput (Mpixel/s) | 150 logiJPGE at 150 MHz, no cipher | 4 lanes: 175.7 (RGB) at 100 MHz; **208 with YUYV input** (320×240, 4 px/beat) | **ahead** (RTL simulation) | 4 lanes × 150 MHz ≈ 260 (RGB) / 310+ (YUYV); board measurement A2 |
| 1080p frames/s | — | 84.7 (4 lanes, 100 MHz, RGB) | ahead | 4 lanes 1080p image (`bd_lanes4hd`, NBUF = 1) |
| LUT | 3,069–3,240 (commercial, no cipher) | 4,752 (v2, with 2 Ascon cores + tag + registers) | behind on raw LUT | fair metric: JPEG datapath alone (fewer LUTs than both, Table "compare"); crypto adds ~45 % — no published secure encoder is smaller AND authenticated |
| Mpixel/s per kLUT | 46.3 logiJPGE | 12.9 (v2), 10.4 (4 lanes) at 100 MHz | behind | ×1.5 at 150 MHz; YUYV drops the colour converter (−300…1,000 LUT per lane); one Ascon core shared by the lanes (−~2,700 LUT for 4) is the remaining big item (docs/RESEARCH.md, item 8) |
| BRAM36 | 16 logiJPGE (4:2:2, 2048 px), 2 CAST (block-order input) | 25.5 (v2, 4:2:0, 2048 px), 56 (4 lanes, 1024 px) | behind | NBUF = 1 halves the 4-lane line buffers (2–5 % throughput); 4:2:0 needs 16 lines where 4:2:2 needs 8, so per line we are already at parity; block-order input (CAST) would need a 2-D DMA — future work |
| Power / energy | not published for the commercial cores | 0.206 W SAIF (v2), 0.32 W (2 lanes); 2.6–3.2 nJ/pixel | first to report | A4 board measurement; nJ/pixel falls with the clock (static power is shared) |
| Security | scrambling or TEA, no authentication (Kishore, Bağbaba) | Ascon-AEAD128 per frame, format compliant, E5 removes outlines, replay window, adaptive defence | **ahead** | — |
| Side channels | not evaluated | size channel measured (R7), **padding shipped** (`link.pad`) | ahead | — |
| Key management | static keys | per-frame nonces, ratchet; **post-quantum session key** (ML-KEM-768 + X25519, `link/kex.py`) | ahead | board timing of the exchange (experiments/pq_kex_cost.py on the A9) |
| Verification | not described | golden model referee, 1,089 KATs, every block bit-exact, XSim of 1/2/4 lanes | ahead | — |
| Silicon | Kishore: FPGA board | bit-exact E0–E5 on the PYNQ-Z2 | parity | A2–A6 |

So: clock is the one headline number we still lose, LUT/BRAM efficiency against cipher-free cores is
the one we cannot fully win (and say so), and everything else is ahead or first.

## 2. What changed in the RTL for this plan (all bit-exact, `make test`)

| Change | Metric | Evidence |
|---|---|---|
| Product stage P in both colour converters | clock | run 9: 125 MHz met |
| `rtl/skid_buf.v` at the encryption stage and the bit packer (in + out) | clock | bug #36; run 10 |
| Keystream slots as a ring, registered `ks_avail` | clock (removes the 128-bit fan-out-133 copy) | run 10 |
| Bit packer shifts by its registered fill level | clock | run 10 |
| Zig-zag non-zero flags in flip-flops | clock | run 10 |
| `NBUF = 1` option | BRAM, 1080p with 4 lanes | `--nbuf 1`: 0.613 / 0.601 clk/px vs 0.603 / 0.569 |
| `PIXFMT = 1` (YUYV input, `rtl/yuyv_4px.v`) | throughput, DDR bytes (2 instead of 4 per pixel), LUT (no multipliers), ARM load | 0.480 clk/px for 4 lanes at 320×240 = 208 Mpx/s at 100 MHz |
| Timing-driven Vivado flow (`SJPEG_IMPL=perf`) | clock | run 10 (the old flow stays: `SJPEG_IMPL=default`) |

## 3. The ideas from other fields: what each one became

| Idea | Principle | What it is here | Status |
|---|---|---|---|
| Retina: parallel pathways merged later | many slow channels instead of one fast one | the lanes (restart segments = independent receptive fields) | done (1/2/4 lanes) |
| Compound eye (insects): facets that each work alone | independence | restart segments: each decodes alone → lanes and the E5 permutation | done |
| Frog / fly motion detectors, event cameras | spend effort on change only | change-driven coding (R4) | measured; useful only for fixed cameras (paper §further) |
| Jumping spider: cheap wide-field eyes trigger the sharp principal eyes | cheap detection gates expensive processing | the adaptive defence: cheap evidence (tag failures, loss) raises the protection level | done |
| Human fovea / eagle's double fovea | resolution where it matters | region-of-interest protection | not built: a detector on the camera is itself a target (paper, inspirations) |
| Camera ISP / iPhone pipeline | sensors give YCbCr, ISPs never convert back to RGB; several pixels per clock | YUYV input, 4 pixels per beat, no colour multipliers | done (`PIXFMT = 1`) |
| Phone secure enclave | keys never leave the secure part | key registers are write-only in the PL; the session key comes from the exchange on the PS | done |
| BJT/MOSFET at high frequency: delay = R·C, Miller load | load and wire length set the speed | fan-out and long routes are 70 % of our path delay (run 9 reports): register slices, replicated enables, no 128-bit copies | done for the known paths (run 10) |
| Repeaters on long on-chip wires | cut a long RC line into short ones | pipeline registers between modules (skid buffers) | done |
| Multiphase (interleaved) buck converters | N phases at f/N each, outputs summed | the lanes are interleaved phases: lane l takes MCU rows l, l+L, …; the merger sums them | done |
| Power electronics: switching loss ∝ f·C·V² | do not switch what does not change | registers load only on a handshake (the DCT/quantiser pipelines freeze when stalled); measured with SAIF | done; board power A4 |
| Soft switching (ZVS) | switch when it costs nothing | nothing comparable in synchronous logic (clock gating of idle lanes would be the analogue; the xc7z020 has BUFGCE) | future |
| Quantum computing | Grover halves the bits of a symmetric key; Shor breaks X25519/RSA | Ascon-128 keeps ~2^64 against Grover; the session key now comes from ML-KEM-768 (FIPS 203) + X25519, so a recorded session is safe against a future quantum computer | done (`link/kex.py`) |
| "A pixel as an electromagnet" | — | a pixel is a number in this pipeline; field equations give no speed-up for DCT or Ascon. The physically real version is the FPGA's own electromagnetic emission: an EM probe over the chip can see the Ascon registers switch (a side channel on the key). Not evaluated yet: a simulated leakage test (Hamming distance of the Ascon state from the XSim activity) and masking are future work; Ascon was designed to be cheap to mask | open |

## 4. Next measurements (in order)

1. Vivado run 10 (RUNBOOK §3): 150 / 166 MHz for 1, 2, 4 lanes; 4 lanes NBUF = 1, 1080p, YUYV; 4-lane system at 142 MHz.
2. Board A1–A3 with the 4-lane image (and the YUYV one with a USB camera in YUYV mode).
3. Board A4 power; A5/A6 attacks with `--pq-kex` and `link.pad=runmax`.
4. Only then the remaining area item: one Ascon core shared by the lanes (docs/RESEARCH.md, item 8).
