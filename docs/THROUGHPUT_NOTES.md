# Throughput: where we stand, and the path past 150 Mpx/s

Written 16 Oct 2026, from a competitor-datasheet check (logiJPGE, CAST JPEG-E-S/EX-S) done
against our own R1 (`experiments/stall_profile.py`) and R2 (`experiments/parallel_lanes.py`)
numbers. Nothing here is implemented yet — this is the brainstorming list Samarth asked for
before deciding what to build next. Do not start RTL changes from this file alone; turn a
chosen item into a GUIDE.md task first.

## The arithmetic

`Mpx/s = clock (MHz) x pixels per clock`.

- **Us:** 1 sample/clock, 100 MHz, 1.534 cycles/pixel (measured, 640x480, matches the
  1.5 + a/rows law from R1) -> **65 Mpx/s**.
- **CAST JPEG-E-S:** "one color sample per clock cycle", 166 MHz on Artix-7 ->
  166 / 1.5 (4:2:0) = 110 Mpx/s, or 166 / 2 (4:2:2) = 83 Mpx/s. Same samples/clock as us,
  faster clock only.
- **logiJPGE:** datasheet says "150 MPix/s when running at 150 MHz" for Zynq-7020
  (LUT 3240, FF 1969, BRAM 16, DSP48 30, Fmax 150 MHz, resource table is for 4:2:2).
  150 MHz x 1 px/clk = 150 Mpx/s only if 1 pixel = 1 sample; for 4:2:2 a pixel is 2 samples,
  so to hit exactly "150 at 150" with a 4:2:2 resource table they are most likely doing
  ~2 samples/clock (their 30 DSPs vs. CAST's 16 is consistent with that, but the datasheet
  does not say so directly -- this is inference, not confirmed).
- Conclusion: **the gap to CAST is clock only (100 -> 166 MHz). The gap to logiJPGE is
  clock plus roughly 2x samples/clock.**

## Our own projected route past 150 (R2, `parallel_lanes.py` / `fig_lanes.pdf`)

| Change                               | Cycles/px | @100 MHz | @125 MHz | @150 MHz |
|---------------------------------------|-----------|----------|----------|----------|
| Today (measured)                      | 1.53      | 65       | 82       | 98       |
| Overlap frames (no first-row wait)    | 1.50      | 67       | 83       | 100      |
| 2 lanes, 1 px/clk in                  | 1.00      | 100      | 125      | **150**  |
| 2 lanes, 2 px/clk in, overlap         | 0.75      | 133      | **166**  | **200**  |
| 4 lanes, 2 px/clk in                  | 0.50      | **200**  | 250      | 300      |

Only the "today" row is RTL-measured; the rest are the R2 event-model projections, already
charted in `fig_lanes.pdf`. Cheapest route clearly over 150: **2 lanes + 64-bit (2 px/clk)
input bus at 125 MHz** (~7,600 LUTs / 45 DSPs, projected). Widening the input bus matters as
much as adding lanes -- with 1 px/clk in, cycles/px cannot go below 1.0 no matter how many
lanes are added downstream.

## Full list of places we underperform published/commercial designs

Speed
1. Clock: 100 MHz vs. 150-166 MHz (CAST/logiJPGE). Current critical path is zig-zag/RLE,
   +0.09 ns slack at 100 MHz -- next clock sweep (run 4, 125/150 MHz) will name the new
   limiting block.
2. Samples/clock: 1 vs. ~2 (logiJPGE) vs. up to 32 (CAST JPEG-EX-F/DX-F family).
3. Input bus width: 32-bit / 1 px/clk caps cycles/px at 1.0 regardless of lane count.
4. Frame-start cost: first MCU row must fill before DCT starts (2-20% depending on frame size).
5. Resolution headroom: 1080p60 needs 124 Mpx/s; today's 65 Mpx/s is ~31 fps at 1080p.

Area / memory
6. BRAM: 24.5 blocks vs. 16 (logiJPGE) vs. 2 (CAST) -- ours are full double MCU-row buffers
   sized for 2048px lines.
7. DSPs: 23, between CAST's 16 and logiJPGE's ~30 (each extra lane: ~+22).
8. Two separate Ascon cores running -- GUIDE B7 (sharing one core) still open.

Features others have that we don't
9. Chroma formats: only 4:2:0. CAST does 4:2:0/4:2:2/4:4:4/grayscale/12-bit; logiJPGE does
   4:2:0 and 4:2:2.
10. Huffman tables: fixed in RTL; CAST's are programmable. Rate control exists only in
    the Python model, not in hardware.
11. Latency (first pixel in -> first byte out): never measured in RTL. Easy to add to the
    cocotb testbench.

Evidence gaps vs. published crypto/hardware papers
12. No board measurements yet (real fps, power, energy/frame) -- power is a vectorless
    estimate only. Biggest gap for the paper's credibility.
13. Ascon throughput never reported in Gbps or Gbps/LUT, the metric comparable NIST
    LWC hardware papers (Kurian, Khairallah, Mozaffari-Kermani et al.) use.
14. No software (ARM/PS-side) baseline for comparison (GUIDE B1).
15. No side-channel resistance -- no masking against power analysis; physical attacks are
    explicitly out of scope, but recent Ascon hardware papers address this.
16. E5 (our strongest security result) exists only in the Python model, not in RTL.
17. Frame-size padding exists only in `experiments/size_leak.py`, not in `link/sender.py`
    or hardware.

Security weak spots (to state honestly in the paper, not to hide)
18. E1 is broken by a trained reconstruction network (learned_attack.py results).
19. Every protection level leaks motion through frame sizes (R7).
20. Restart intervals with N > 1 are not safe against the jigsaw/MST solver.

## Where this leads

Items 1-3 are most of the throughput story; a 2-lane, 2px/clk, 125 MHz design is the
cheapest change that clears 150 Mpx/s on our own model. Items 12 and 16 matter most for how
strong the paper's claims look, independent of throughput.

Pick from this list and bring back the idea -- check it against the event model
(`experiments/parallel_lanes.py`) before touching RTL.

## Status, 16 Oct 2026 (evening): items 2 and 3 built

The lane encoder is in RTL: `rtl/secure_jpeg_lanes_top.v` (contract v3, `docs/INTERFACES.md` §8).
Ideas behind it, and where each one came from:

| Idea | Inspiration | What it became |
|---|---|---|
| Parallel channels, each seeing part of the image, merged later | retina: parallel ganglion-cell pathways | LANES copies of the verified pipeline, MCU row r → lane r mod LANES |
| Several pixels per clock on a wide stream | camera ISPs and video IP (CAST JPEG-EX-F: 1-32 samples/cycle) | 64-bit pixel stream, `rgb2ycbcr_2px.v` |
| Independent units that can be decoded alone | JPEG restart markers (already used by E5) | one restart segment per MCU row, DC reset, byte flush |
| Seekable cipher stream | counter-mode style keystreams | K_seg per frame, nonce = segment index |

Measured (Icarus, cycle-accurate, `experiments/lanes_rtl_throughput.py`, 640x480, 100 MHz):
1 lane 1.519 clk/px = 65.8 Mpx/s · 2 lanes 0.817 = 122.3 Mpx/s · 4 lanes 0.569 = 175.7 Mpx/s.
Post-route (Vivado run 6, 17 Oct): 2 lanes 9,869 LUT / 50 BRAM / 46 DSP and 4 lanes 16,573 / 52 / 92 meet
100 MHz; the 2-lane PYNQ-Z2 overlay meets 100 MHz (WNS +0.208 ns). Next clock limit: the colour converter
(v2 at 125 MHz: -0.875 ns). Items still open from the list above: 1 (clock), 6 (BRAM: lanes multiply
the line buffers), 9-11, 12-17.
