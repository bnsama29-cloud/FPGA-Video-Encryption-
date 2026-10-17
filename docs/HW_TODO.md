# What is left for the hardware (as of 17 Oct 2026)

All software is finished and tested: the golden model, the receiver, the board driver, the board
sender, the bit-exact gate, the XSim vector and check tools and the dashboard all already handle every
item below. Each task names the RTL files to change, what must change, and the test that says "done".
The model is the referee (CLAUDE.md): change the RTL until the test passes, never the model.

| # | Task | Why | Effort |
|---|---|---|---|
| H1 | **E5 in the lane encoder** (mode 5, contract v3 §8.6) | the strongest level exists only in software today; with H1 the board reaches E5 | ~1 week |
| H2 | Board bring-up A1–A6 (`docs/BOARD_BRINGUP.md`) | every board number in the paper | 1–2 weeks |
| H3 | 125 MHz: one more pipeline stage in the colour converter | 1 lane 82, 2 lanes ~150 Mpixel/s | 1–2 days + Vivado run |
| H4 | Power from simulated switching activity (GUIDE B37) | replaces the vectorless estimate | 1 day |

H2 does not depend on H1: run the board with today's bitstreams first, then again with the H1 bitstream.

---

## H1 — E5 in `secure_jpeg_lanes_top` (contract v3, mode 5)

**Spec:** `docs/INTERFACES.md` §8.6. **Golden model:** `model/hw.py :: encode_frame_v3(..., mode=5)`
(fabric output), `model/hw.py :: arm_shuffle` (ARM, already written: `future_work/board/fast_e5.py`).

What the fabric must do in mode 5 (CTRL[3:1] = 5):

1. **Encrypt like E4.** `selective_enc.v`: treat mode 5 exactly as mode 4 (same fields).
2. **One restart segment per MCU instead of per MCU row.** Inside a lane, end a segment after every
   MCU: `zigzag_rle` resets the DC predictors (`SEG_RESET` path, `flast` at the end of every MCU instead
   of the row), `bit_packer` pads to a byte and marks the segment's last byte (`o_slast`) per MCU.
3. **Keystream per MCU.** `encoder_lane.v`: the segment index `seg` becomes the raster MCU index
   (row × MCUs per row + column) and the keystream restarts with nonce(seg, frame_ctr, 0) under K_seg for
   every MCU. A restart costs one Ascon initialisation (12 rounds); one MCU is 384 samples, so it fits
   if it overlaps the previous MCU like the per-row restart does today. Check with the `throughput` test.
4. **Merger.** `segment_merger.v`: segments now come in groups: the `cols` segments of MCU row r all come
   from lane r mod LANES, each followed by a restart marker (except the frame's last). The lane select
   becomes (s / cols) mod LANES. The segment counter `s` and `segs` must hold the MCU count
   (16 bits: 1200 MCUs at 640×480; today 8 bits for MCU rows).
5. **Tag.** Unchanged: `tag_unit` absorbs the merged scan as produced (raster order) after the 26-byte
   prefix with mode byte 5.
6. **VERSION.** Set bit 7: `0x5EC00380 + LANES`. The driver (`future_work/board/pynq_driver.py`) only
   uses mode 5 when this bit is set; the board sender then lets the policy reach E5.

Nothing else changes: no frame buffer, no new Ascon core. The ARM does the permutation.

**Done when:**
* `make one T=tb/test_lanes_top.py::test_secure_jpeg_lanes_top` runs the `e5_one_segment_per_mcu` test for
  1, 2 and 4 lanes and it passes (today it logs "E5 not implemented in this RTL" and returns). The test
  compares scan and tag byte for byte with the model, under random stalls, then runs the ARM shuffle and
  the receiver.
* `make test` stays green (modes 0–4 must not change by a single byte).
* `python vivado/run_vivado_day.py vectors --v3 --modes 2 5` then XSim then `... check --dir vivado/xsim_work_v3`
  prints `CHECK RESULT: PASS` (the vectors already contain two E5 frames and expect VERSION bit 7).
* Vivado: `--steps lanes bd_lanes parse` still meets 100 MHz.
* Board (after H2): `python3 -m future_work.board.first_contact --bitfile .../secure_jpeg_lanes.bit` checks
  E0–E5 (it adds E5 automatically when VERSION bit 7 is set). Rehearse today with `--mock-lanes 2 --mock-e5`.

Cost to expect: +8–23 % bytes for E5 over E4 at 320×240 (restart marker, padding and restarted DC
prediction per MCU; `experiments/restart_interval.py`), the same as the model's E5.

---

## H3 — 125 MHz

Vivado run 6: at 125 MHz the colour converter fails by 0.875 ns (v2). Add one register stage in
`rgb2ycbcr_block.v` / `rgb2ycbcr_2px.v` behind the existing valid/ready handshake (the same technique as
bugs #17, #20, #27 in `docs/TESTING.md`). Done when every RTL test is still bit-exact and
`py vivado\run_vivado_day.py --steps ooc lanes --periods 8.0` shows WNS ≥ 0 at 8 ns.

## H4 — Power with switching activity

`vivado/tb_secure_jpeg_top.v` already runs real frames in XSim. Add `open_saif` / `log_saif` around the
frame loop, then `read_saif` before `report_power` in the implementation step, and report the matched
net percentage next to the power. Done when `vivado_tables.md` shows both the vectorless and the
SAIF-based power for the encoder and both overlays.

## Rehearsing without a board

```
python -m future_work.board.first_contact --mock-lanes 2 --mock-e5 --sizes 64x48 --frames 2 --timing-frames 2
py -m link.run_all --no-sender            # window 1
py -m future_work.board.board_sender --mock-lanes 2 --mock-e5 --set sender.policy=fixed --set sender.mode=E5   # window 2
```
