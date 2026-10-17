# What is left for the hardware (as of 17 Oct 2026, H1 done)

All software is finished and tested: the golden model, the receiver, the board driver, the board
sender, the bit-exact gate, the XSim vector and check tools and the dashboard all already handle every
item below. Each task names the RTL files to change, what must change, and the test that says "done".
The model is the referee (CLAUDE.md): change the RTL until the test passes, never the model.

| # | Task | Why | Effort |
|---|---|---|---|
| H1 | ✅ **E5 in the lane encoder** (mode 5, contract v3 §8.6) | done 17 Oct: bit-exact for 1, 2, 4 lanes and in the XSim testbench; the lane bitstream must be rebuilt in Vivado to include it | done |
| H2 | Board bring-up A1–A6 (`docs/BOARD_BRINGUP.md`) | every board number in the paper | 1–2 weeks |
| H3 | 125 MHz: one more pipeline stage in the colour converter | 1 lane 82, 2 lanes ~150 Mpixel/s | 1–2 days + Vivado run |
| H4 | Power from simulated switching activity (GUIDE B37) | replaces the vectorless estimate | flow built (`--steps power`); ⏳ run it in Vivado |

H2 does not depend on H1: run the board with today's bitstreams first, then again with a lane bitstream
rebuilt from the current RTL (`py vivado\run_vivado_day.py --steps xsim lanes bd_lanes power parse`).

---

## H1 — E5 in `secure_jpeg_lanes_top` (contract v3, mode 5) ✅ done 17 Oct 2026

**Result.** All six "done when" checks below that run without a board pass: `tb/test_lanes_top.py` runs
`e5_one_segment_per_mcu` for 1, 2 and 4 lanes (scan and tag byte-exact under random stalls, then the ARM
shuffle and the receiver); `make test` is green with modes 0–4 unchanged; `make xsim-icarus` passes the two
E5 frames and reads VERSION 0x5EC00382. Measured cost: 0.7–3.6 % fewer pixels per second than E2 at 320×240 (1, 2, 4 lanes: 62.7 / 115.3 / 164.8 Mpx/s at 100 MHz, `experiments/lanes_rtl_throughput.py --modes 2 5`);
Yosys (2 lanes): +50 LUT, +1 DSP. Still to do in Vivado: the `lanes` / `bd_lanes` run on the new RTL.
The plan as it was written:

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

## H4 — Power with switching activity (flow built 17 Oct 2026; ⏳ run in Vivado)

`py vivado\run_vivado_day.py --steps ooc lanes power parse` (or `--steps power parse` after an earlier
`ooc lanes` run, which left `routed.dcp` in `sim_build\vivado_*\`). For each routed out-of-context design
and mode (v2 encoder: E0, E2, E4; 2-lane encoder: E2, E5) it:

1. writes vectors for one 320×240 scene frame (`vectors --scene 320x240`, size set by `--power-size`);
2. runs the XSim testbench with `+SAIF` and `saif.tcl` (`open_saif` / `log_saif` on the encoder /
   `run all` / `close_saif`) → `vivado\xsim_power_<v2|v3>_E<m>\activity.saif`. The frame is still checked
   bit-exact (`XSIM RESULT: PASS`);
3. runs `vivado/power_saif.tcl`: opens `routed.dcp`, `read_saif -strip_path tb_secure_jpeg_top/dut[3]`,
   `report_power` → `power_saif_<v2|v3>_E<m>.txt` next to `power.txt`.

`parse` adds a table "Power with simulated switching activity" with the vectorless number beside each
run and the confidence Vivado gives the activity ("Internal nodes activity"). The SAIF comes from RTL
simulation, so only nets whose names survive synthesis are matched; read the `read_saif` summary in
`sim_build\vivado_logs\power_report_*_vivado.log`. Tested here: the Python side (`tests/test_vivado_reports.py`)
and the `+SAIF` testbench path in Icarus; the Vivado commands themselves need a Vivado machine.
The overlays are not covered (the block-design testbench would need the Zynq PS model).

**Measured** power remains a board task: USB meter, idle / ARM / FPGA per mode (GUIDE A4,
`future_work/baselines/power_template.csv` → `python -m future_work.baselines.energy_table`).

## Rehearsing without a board

```
python -m future_work.board.first_contact --mock-lanes 2 --mock-e5 --sizes 64x48 --frames 2 --timing-frames 2
py -m link.run_all --no-sender            # window 1
py -m future_work.board.board_sender --mock-lanes 2 --mock-e5 --set sender.policy=fixed --set sender.mode=E5   # window 2
```
