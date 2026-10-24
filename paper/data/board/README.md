# paper/data/board: results measured on the PYNQ-Z2

| Folder / file | Produced by | Run |
|---|---|---|
| `smoke/` | `python3 -m future_work.board.first_contact --bitfile future_work/board/overlay/secure_jpeg_lanes.bit --sizes 64x48 --frames 1 --timing-frames 2` | 20 Oct 2026 |
| `lanes_320x240/` (console output in `run_log.txt`) | same, `--sizes 320x240 --frames 10` (timing over 50 frames) | 20 Oct 2026 |
| `lanes_640x480/` (console output in `run_log.txt`) | same, `--sizes 640x480 --frames 3` (timing over 50 frames) | 20 Oct 2026 |

Board: PYNQ-Z2 (xc7z020), PYNQ image 3.1.1, run as root in a login shell on the board's ARM. Bitstream:
the 2-lane lane encoder with E5 (contract v3, VERSION 0x5EC00382), FCLK0 = 100 MHz, rebuilt on 20 Oct 2026
from commit da21bfd with `py vivado\run_vivado_day.py --steps bd_lanes --jobs 2` (Vivado 2026.1, tom's PC,
WNS +0.123 ns). The bitstream is not in git:

| File | Bytes | SHA-256 |
|---|---|---|
| `secure_jpeg_lanes.bit` | 4,045,769 | `0a5c50e4aee000eee2ce318924d42bc408979763bcbfd45a19e5fab8e1e91230` |
| `secure_jpeg_lanes.hwh` | 319,563 | `1c1ff1afdcf41c550a6395b3f44a07f7abb3abc246dc43713d49687186556258` |

The run-7 bitstreams (18 Oct) loaded but hung: the block design had left the DMA's write master
unconnected (docs/TESTING.md bug #32). Every result here is from the rebuilt bitstream.

How to read the numbers:

* **Bit-exact**: every frame was encoded on the FPGA, read back by DMA and compared byte for byte (scan and
  tag) with the golden model (`model/hw.py :: encode_frame_v3`) running on the same board, then decrypted by
  the receiver. Source: the synthetic scene, quality 75.
* **Encode only / Incl. headers**: medians of the Python round trip on the ARM (pixel conversion, copy into
  the DMA buffer, cache flush, register writes, DMA both ways, polling), then the JPEG headers (and for E5 the
  MCU shuffle) on the ARM. They are the same in every level, so the encryption costs no time; they are
  **not** the fabric's speed (RTL simulation: 0.82 cycles/pixel, about 2.5 ms for 640x480), which has not
  been measured on the board yet.

The files were copied from `sim_out/board/` on tom's PC (the `.json` / `.md` exactly as the script wrote them).

## Board day, 24 Oct 2026 (`board_day_24oct/`)

Copied by `scripts/save_board_day.py` (see its `MANIFEST.md` for every file and hash). The final board images of
Vivado runs 12 and 13, each at the clock it was built for: `lanes4_final` (4 lanes, 125 MHz, 3 frames per level
and size), `lanes2_final` (2 lanes, 100 MHz) and `v2_final` (single pipeline, 100 MHz), all bit-exact; the ARM
baseline (`arm_final`), the post-quantum key on the A9 (`pq_kex`), the energy table without a meter (`energy`,
Vivado estimate) and, with the board as sender, the attack suite, the benign run and the tamper run (`runs/`).
`paper/make_assets.py :: board_day()` turns them into `tab_board.tex`, the `\Bd...` macros, the column "Board"
of `tab_attacks.tex` and `fig_board_fps.pdf` / `fig_board_cycles.pdf`.

How to read the fabric time: CYCLES counts START to DONE; IN_WAIT counts the clocks in which the encoder could
take a pixel but the DMA had none. The driver (`pynq_driver.encode`) writes START before it starts the pixel DMA,
so IN_WAIT is almost the same for every image (about 0.62 ms per frame); CYCLES minus IN_WAIT equals the RTL
simulation's cycle count to within 1 %. `lanes2_final_62mhz` is an extra run of the 2-lane image at 62.5 MHz
(not used in the papers). In the tamper run 9 of 25 button presses cost two rejected frames: BTN0 is not
debounced in `axis_tamper.v`.
