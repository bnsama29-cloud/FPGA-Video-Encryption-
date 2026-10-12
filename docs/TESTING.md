# How to test the design

## 1. The rule everything rests on

The Python golden model in `model/` is the **referee**. Every RTL block has one model function (named in the block's header comment) and its output must match **bit for bit**. Therefore:

1. Test the model first (`make test-model`). It is checked against outside references: the official NIST Ascon KATs and libjpeg (tables, image quality), and Pillow must decode its files.
2. Then test each block alone against the model (unit tests).
3. Then the whole chain (integration).
4. Only then synthesise, and only then go to the board, using the same vectors.

Never change the model to make an RTL test pass, unless the model is proven wrong against the JPEG standard (ITU-T T.81) or Ascon (NIST SP 800-232).

## 2. Test order (run in this order when bringing up or after big changes)

| # | Command | Checks | "Done when" (milestone) |
|---|---|---|---|
| 1 | `make test-model` | 1089 Ascon KATs, tables vs libjpeg, quality vs libjpeg, round trip all modes, tamper/replay/wrong key/session, marker-parsing regression | 14 passed (M0) |
| 2 | `make test-ascon` | RTL Ascon core vs KATs (70-vector subset covering every AD/PT length 0..33 + longest) and random vs model; `make full` runs all 1089 | all pass (M1) |
| 3 | `make test-crypto` | keystream for 4 nonces incl. early restart, random take sizes; tag for AD lengths 1,15,16,17,31,32,33,48,100 + random | all pass (M1/M5) |
| 4 | `make test-front` | colour + 4:2:0 + blocking on bars (pure R/G/B/black/white), noise, checker, 16×16 single MCU, non-square, back-to-back frames | byte-exact (M2) |
| 5 | `make test-dct` | DCT: flat 0/128/255, checkerboard, stripes, ramp, random. Quantiser: 5 quality tables, extremes ±2048, clamping, rounding of negatives | bit-exact (M2) |
| 6 | `make hls-csim` | HLS DCT+quantiser vs the same vectors (g++; Vitis via `hls/run_hls.tcl`) | 0 mismatches (M2, R1) |
| 7 | `make test-entropy` | run-length: DC-only, all-zero, ZRL, 62 zeros + last non-zero, dense, max values. Encryption: all 5 modes, keystream starvation, decrypt = re-encrypt. Huffman+packer: 4 images + every one of the 324 AC codes, 0xFF stuffing, padding | byte-exact (M3, M5) |
| 8 | `make test-top` | registers (read-back, write-only key, WSTRB, unused address); one frame per mode with receiver round trip; back-to-back frames of 4 sizes with random DMA stalls + tamper/replay/wrong key/wrong session; throughput | all pass (M4, M5) |
| 9 | `make full` | everything above with all KATs and a 320×240 frame | all pass |
| 10 | `make lint`, `make synth`, then `scripts/vivado_ooc.tcl` in Vivado | synthesizable, resource estimate, timing slack ≥ 0 at 100 MHz | WNS ≥ 0 |

Every test that uses randomness prints `random seed = N`; rerun with `SEED=N` to get the identical run.

## 3. What a good unit test contains (template for new blocks)

Look at `tb/test_dct_quant.py`; each test:

1. starts the clock and reset (`common.start`),
2. builds inputs from the model or from deliberate edge cases,
3. drives them with `drive_stream(..., p_idle=0.2)` (random gaps) and collects with `collect_stream(..., p_stall=0.3)` (random backpressure),
4. compares against the model and **reports the first mismatch with its index, input, got and expected**,
5. has a `def test_<top>(): run_sim("<top>", "<module>")` function at the bottom so pytest can run it.

Add the new top and its source files to `SOURCES` in `tb/common.py`.

Timing rule for testbench code (found the hard way, see bug log): right after `await RisingEdge(clk)`, cocotb returns the values from *before* the edge. That is correct for "did a transfer happen on this edge" checks. If your testbench must *react* to the current state (for example a keystream window), make the decision at `await FallingEdge(clk)` (plus `await ReadOnly()` to read combinational outputs that depend on what you just drove).

## 4. After you change RTL

1. `make one T=<that block's test>` until it passes.
2. `make test` (24 s). Never merge a failing block.
3. If you changed a table or formula, change the model, run `make tables`, `make vectors`, and update docs/INTERFACES.md.
4. `make lint` and, for timing-sensitive changes, the Vivado OOC run.
5. Commit the code together with a one-line note of what was verified.

## 5. Results available from simulation already

`make test-top` and `make demo` (model, bit-exact with the RTL) give early versions of the paper's tables. Example from `scripts/visual_security.py` (256×192 synthetic image, quality 75):

| Mode | Encrypted bits | % of scan | Size change | PSNR without key | Replacement attack | AC-zeroing attack |
|---|---|---|---|---|---|---|
| E1 | 10 112 | 14.4 % | −4 B | 14.5 dB | 14.2 dB | **17.5 dB = clear DC thumbnail** |
| E2 | 11 176 | 15.9 % | +8 B | 6.1 dB | 6.1 dB | 6.5 dB |
| E3 | 19 351 | 27.6 % | +1 B | 5.1 dB | 6.0 dB | 5.1 dB |
| E4 | 22 158 | 31.6 % | +3 B | 6.0 dB | 5.6 dB | 6.0 dB |

Finding for RQ1/RQ3: **E1 alone is broken** by discarding the AC coefficients (DC is in clear), which justifies E2 as the main configuration. Repeat with real photographs (`--image`) and several qualities, and add SSIM for the paper.

## 6. Known gaps and limitations (be honest about these in the report)

* **The tag covers the scan data only.** The header (quantisation tables, size) and the APP11 mode byte are not authenticated: an attacker can change them without detection (the receiver then decrypts wrongly). Fix: absorb a 16-byte header block (mode, width, height, quality ID) as associated data before the scan bytes in `tag_unit.v` and `model.ascon.mac`. Good RQ3 discussion point.
* Leakage: sizes and run lengths are never encrypted (by design, for format compliance), so block activity and outlines can leak, especially for E3/E4. Try an edge-detection or "size-map" attack.
* Verilator flow is not verified (cocotb 2.x needs Verilator ≥ 5.036; Ubuntu ships older). Use Icarus.
* Simulation cannot show real DDR/DMA speed, Ethernet/VLC behaviour, measured power or timing closure; simulated throughput assumes 100 MHz is met.
* The DCT's 8-input multiply-add is the likeliest timing-critical path; if Vivado reports negative slack, register the products (one extra pipeline stage) or lower the clock.
* No restart markers: a single bit error in transmission corrupts the rest of a frame (the tag will reject it anyway).

## 7. From simulation to the board (one block at a time)

1. `make vectors` (and `--image` for a real frame) writes `vectors/<name>/` with `pixels.txt`, `blocks.txt`, `coeffs.txt`, `qcoeffs.txt`, `symbols.txt`, `enc_symbols.txt`, `scan.bin`, `tag.hex`, `frame.jpg`, `config.txt` (the exact register values).
2. On the board, feed `pixels.txt` through the DMA with the register values from `config.txt`; the received scan must equal `scan.bin` byte for byte and TAG0..3 must equal `tag.hex`.
3. If it differs, do not guess: find the first wrong byte, then bring that stage's output out (ILA, or a debug build that stops after the stage) and compare against the matching vectors file.
4. Package `secure_jpeg_top` with Vivado's IP packager: the `s_axil_*`, `s_axis_*`, `m_axis_*` names are inferred as interfaces. `rst` is active-high (use `peripheral_reset` from Processor System Reset, not `peripheral_aresetn`).

## 8. Bug log: real bugs found while building this repository

Keep this log going; it is good material for the report and shows what the tests are for.

| # | Symptom | Root cause | Fix | Lesson |
|---|---|---|---|---|
| 1 | `Can't convert LogicArray to int: it contains non-0/1 values` in the keystream test | `cur`/`nxt` registers in `keystream_gen.v` had no reset value, so the window output was X | reset them on `rst`/`start` | X on an output = an uninitialised register; cocotb refuses to turn X into a number |
| 2 | keystream test: "first mismatch at bit 6", RTL looked right | testbench read the window right after `RisingEdge`, getting the previous cycle's value | decide at `FallingEdge` | before suspecting RTL, check *when* the testbench samples |
| 3 | `invalid Huffman code at bit 6466` in the receiver, although RTL matched the model byte for byte | model searched for `FF C0` to find SOF0; session ID 0x00C0FFEE is stored as `EE FF C0 00` inside APP11 | walk marker segments (`segments()`), regression test added | never byte-search for JPEG markers |
| 4 | planted bug: quantiser test said only "block 14 mismatch" | weak assertion message | report index, input, reciprocal, got, expected, exact quotient | the message `F=-2048, R=624, exact quotient 19.5000, got -19 expected -20` points straight at rounding |
