# Vivado: from verified RTL to paper numbers and PYNQ-Z2 bitstreams

One command runs everything: XSim, post-route numbers, both PYNQ-Z2 overlays and the paper tables.
Give this file to Claude together with `docs/TEAM_CONTEXT.md` if anything fails.

**Status (18 Oct 2026, run 7): all 27 steps pass; the lane encoders and the 2-lane PYNQ-Z2 system now
include E5 and still meet 100 MHz.** Results in `paper/data/vivado/` (the paper is built from them); the
history of runs 1-7 is in §6. E5 is only on branch `claude/project-thread-yxa59j` until PR #1 is merged:
clone or `git checkout` that branch instead of `main`.

---

## 0. Install (once)

1. **Vivado ML Standard** (free) from amd.com → Support → Downloads, with a free AMD account.
   * Choose *Vivado → Vivado ML Standard*; under devices tick **only SoCs → Zynq-7000** (about 30-40 GB).
   * We use **2026.1**, installed at `E:\FPGA\2026.1\Vivado\` on Samarth's laptop.
   * Licence (2026.1 refuses to start without one): amd.com/support → *Product Licensing*, tick
     **Vivado Basic Tier License, Node Locked** and **Vitis HLS License** (both *No Charge*), host ID =
     the Ethernet address shown by *Vivado License Manager → View Host Information*, then *Load License*.
     Do not take the 60-day trial.
2. **Vivado on the PATH in every Command Prompt** (no more "vivado is not on the PATH"): run once
   ```
   reg add "HKCU\Software\Microsoft\Command Processor" /v AutoRun /d "E:\FPGA\2026.1\Vivado\settings64.bat" /f
   ```
   (your install path). Check in a new window: `where vivado`. Linux: `source <Vivado>/settings64.sh`.
3. **PYNQ-Z2 board files** (optional, exact PS presets): copy the `pynq-z2` folder from the PYNQ
   GitHub repository into `<Vivado>/data/boards/board_files/`. Without them the script warns and works.
4. **Repo and Python:** a path without spaces (e.g. `E:\FPGA-Video-Encryption-`), `git pull` on `main`,
   `pip install -r requirements.txt`. Check: `python vivado/run_vivado_day.py --dry-run`.

Run from a normal Command Prompt, **not** with `exec python ...` in the Vivado GUI's Tcl console
(that uses Vivado's own Python, hides all output until the end and keeps the GUI's ~1 GB in memory).

---

## 1. The command

```
cd /d E:\FPGA-Video-Encryption-
git pull
rmdir /s /q sim_build future_work\board\vivado_proj future_work\board\vivado_proj_lanes
py vivado\run_vivado_day.py --steps xsim ooc lanes bd bd_lanes parse --maxw 9 10 --periods 8.0 6.667 --jobs 2
```

About 1.5 h on an 8 GB laptop (run 6: 88 min). Close other programs; use `--jobs 1` if Vivado runs out
of memory. It ends with **`vivado_results_<date>.zip`** in the repository root: send that one file.
The bitstreams stay on the laptop in `future_work\board\overlay\`.

Shorter variants:

| Command | What |
|---|---|
| `py vivado\run_vivado_day.py --steps xsim` | only the XSim check (2 min) |
| `py vivado\run_vivado_day.py --steps bd_lanes parse` | only the lane overlay |
| `py vivado\run_vivado_day.py --steps ooc --blocks --fmax` | per-block area, confirm fmax |
| `py vivado\run_vivado_day.py --steps bd --fclk 90` | overlay at another clock |
| `py vivado\run_vivado_day.py --steps xsim lanes bd_lanes power parse` | rebuild the lane encoder and overlay with E5 (17 Oct RTL) + power from simulated activity |
| `py vivado\run_vivado_day.py --steps power parse` | only the power runs (needs `routed.dcp` from an earlier `ooc` / `lanes`) |
| `py vivado\run_vivado_day.py --dry-run` | print the plan, run nothing |

The same file also holds the three helper tools the steps use (no Vivado needed for them):

| Command | What |
|---|---|
| `python vivado/run_vivado_day.py vectors [--v3]` | XSim test vectors from the golden model → `vivado/xsim_work[_v3]/` |
| `python vivado/run_vivado_day.py check [--dir ...]` | rebuild the JPEGs from an XSim/Icarus run and run the receiver |
| `python vivado/run_vivado_day.py parse [folders]` | Vivado reports → `sim_out/vivado/vivado_tables.md` + `.json` |

`make xsim-icarus` runs `vectors` + `check` with Icarus instead of XSim (Linux/WSL, and in CI).

---

## 2. What each step does and checks

| Step | What it runs | Pass means |
|---|---|---|
| `xsim` | golden-model vectors → `vivado/tb_secure_jpeg_top.v` in XSim, v2 then v3 (`M 3`) → `check` | `XSIM RESULT: PASS (5 frames bit-exact ...)` and `CHECK RESULT: PASS`, both contracts |
| `ooc` | `secure_jpeg_top` out of context at 100 MHz, at every `--periods` clock, with every `--maxw` line-buffer size | the run finished; the WNS is the result |
| `lanes` | `secure_jpeg_lanes_top`: 2 lanes at 100 MHz and every `--periods` clock, 4 lanes (1024-pixel lines) at 100 MHz | as `ooc` |
| `bd` | PYNQ-Z2 system: Zynq PS + AXI DMA (32-bit pixels) + v2 encoder → `overlay/secure_jpeg.bit` + `.hwh` | `RESULT overlay ... WNS >= 0`; if not, retried at 90 then 80 MHz |
| `bd_lanes` | the same with the 2-lane encoder and a 64-bit pixel DMA → `overlay/secure_jpeg_lanes.bit` + `.hwh`, reports in `overlay/lanes/` | as `bd` |
| `power` | after `ooc` / `lanes`: XSim records the switching activity of one 320×240 frame per mode (v2: E0, E2, E4; 2 lanes: E2, E5) into `activity.saif`, then `vivado/power_saif.tcl` reads it into `routed.dcp` and reports power → `power_saif_<run>.txt` (docs/HW_TODO.md H4) | `XSIM RESULT: PASS` and `RESULT power_saif` for every run |
| `parse` | every report → `sim_out/vivado/vivado_tables.md` / `.json` (the paper's hardware numbers) | the table has no `?` |
| collect | (always last) summary + reports → `vivado_results_<date>.zip` | |

Every step logs to `sim_build\vivado_logs\<step>.log` (Vivado's own log: `<step>_vivado.log`).
Waveforms for the report: `vivado\run_xsim.bat gui`, or `vivado -mode gui -source vivado/xsim_project.tcl`
(useful signals: `dut/u_enc`, `dut/u_ks`, `dut/u_tag`).

---

## 3. Run 6 results (17 Oct 2026; run 7 with E5 in §6)

Post-route, xc7z020clg400-1, slack at 100 MHz (full table: `paper/data/vivado/vivado_tables.md`):

| Design | LUT | BRAM36 | DSP | WNS |
|---|---|---|---|---|
| encoder (1 px/clk, contract v2), out of context | 5,037 | 24.5 | 23 | +0.554 ns |
| 2 lanes (2 px/clk, contract v3), out of context | 9,869 | 50 | 46 | +0.400 ns |
| 4 lanes, 1024-pixel lines, out of context | 16,573 | 52 | 92 | +0.440 ns |
| **PYNQ-Z2 system, v2 encoder** (`secure_jpeg.bit`) | 6,933 | 26.5 | 23 | +0.788 ns |
| **PYNQ-Z2 system, 2 lanes** (`secure_jpeg_lanes.bit`) | 11,716 | 52.5 | 46 | +0.208 ns |

At 125 MHz the colour converter is the next limit (v2: -0.875 ns). Shorter line buffers save BRAM:
512-pixel lines need 6.5 BRAM36, 1024-pixel lines 12.5.

---

## 4. First contact with the board

1. **Prepare the board:** PYNQ-Z2 image (v3.0.x from pynq.io) on a ≥ 16 GB SD card, boot jumper on SD,
   Ethernet to the laptop or router, power. Open `http://pynq:9090` (or the board's IP), password `xilinx`.
2. **Copy the repo onto the board**, including `future_work/board/overlay/` (both `.bit` + `.hwh` pairs,
   same base names): Jupyter upload, or `scp -r` to `/home/xilinx/fpga`.
3. **In a board terminal** (Jupyter *New → Terminal*):
   ```
   cd /home/xilinx/fpga
   sudo -E pip3 install numpy pillow opencv-python
   sudo -E python3 -m future_work.board.first_contact --sizes 320x240 640x480 --frames 10
   sudo -E python3 -m future_work.board.first_contact --bitfile future_work/board/overlay/secure_jpeg_lanes.bit --sizes 320x240 640x480 --frames 10
   ```
4. **The bit-exact gate comes first:** for every size and mode E0-E4 the FPGA's JPEG must equal the golden
   model's byte for byte (contract v2 or v3, read from the VERSION register) and the receiver must decrypt
   it. Only then does it time the encoder → `sim_out/board/first_contact.md`. Rehearse on the laptop with
   `python -m future_work.board.first_contact --mock` (or `--mock-lanes 2`).

| Problem | Likely cause |
|---|---|
| `VERSION register reads ...` | wrong IP picked: `print(Overlay(...).ip_dict.keys())`, pass `--ip-name` / `--dma-name` |
| `TimeoutError: STATUS.DONE never set` | DMA lengths, the clock not running (FCLK0), reset polarity, or `tlast` |
| Bytes differ at a small offset | headers or registers: quality tables, session id / frame counter HI words |
| Bytes differ deep in the scan | pixel word order `{pad, B, G, R}`, or a data-path difference: compare with XSim |
| Slow (< 30 fps at 640x480) | the Python on the ARM (copying pixels), not the fabric: time `ip.encode` alone |

If the gate passes and time is left: the ARM baseline
(`python3 -m future_work.baselines.bench_software_codecs --sizes 320x240 640x480`) and power with a USB
power meter (idle, ARM encoding, FPGA encoding; GUIDE.md §4.2, A4).

---

## 5. If something fails

Read the first `ERROR:` line in `sim_build\vivado_logs\<step>_vivado.log`, or paste it into Claude with
`docs/TEAM_CONTEXT.md`. Errors met so far (bug numbers in `docs/TESTING.md` §8):

| Error | Fix |
|---|---|
| `vivado is not on the PATH` | §0 step 2 (AutoRun), or run `settings64.bat` in that window |
| `[filemgmt 56-591] ... dct_coeffs.vh needs to be added to the project` | fixed in `block_design.tcl` (#18) |
| `[BD 41-758] ... /clk_wiz/clk_in1` on a 90/80 MHz retry | fixed (#28): the wrappers no longer fix the clock at 100 MHz |
| XSim cannot find the sources on Windows | fixed (#18): `vectors` writes an absolute-path `xsim_abs.prj` |
| Out of memory / laptop freezes in the block design | `--jobs 1`, close the browser |
| `apply_bd_automation ... invalid -config` | do the connection automation in the GUI (`vivado future_work/board/vivado_proj/pynq_secure_jpeg.xpr`), copy the journal's command into `block_design.tcl` |
| `IP ... is locked / version` | Tools → Report IP Status → Upgrade, re-run |
| Timing fails | the worst-path table in `vivado_tables.md` names the block; pipeline it behind its handshake and keep every RTL test bit-exact (#17, #20, #27) |

Commit what the team needs: `future_work/board/overlay/*.bit`, `*.hwh` and reports, and any fix to
`block_design.tcl`. Never `sim_build/`, `vivado_proj*/`, `.Xil/` (git-ignored).

---

## 6. History of the runs

| Run | Date | What changed | Result |
|---|---|---|---|
| 1 | 14 Oct | first run in Vivado 2026.1 | encoder only 47 MHz: DCT summed a row in one clock, quantiser -1.2 ns (#17); XSim paths and block-design include fixed (#18) |
| 2-3 | 14 Oct | pipelined DCT and quantiser, 2-stage converter writes (#20) | encoder +0.045 ns out of context; overlay -0.24 ns |
| 4 | 15 Oct | one more converter stage; clock and memory sweeps | superseded by run 5 (which includes it): v2 overlay +0.014 ns, encoder +0.020 ns |
| 5 | 16-17 Oct | + contract-v3 lane encoder and its overlay | lanes -0.13 ns (zig-zag stage, #27); 90/80 MHz retries stopped on a clock wizard (#28) |
| 6 | 17 Oct | zig-zag stage split in two, byte-FIFO flag registered, wrapper clock fixed | **20/20 steps pass, everything meets 100 MHz** |
| 7 | 18 Oct | E5 in the lane encoder (H1); `--steps xsim ooc lanes bd_lanes power parse`, tom's PC, 61 min | **27/27 pass**: 2 lanes 10,069 LUT (+200) +0.359 ns, 4 lanes 16,893 (+320) +0.293 ns, 2-lane system 11,913 (+197) +0.228 ns; E5 bit-exact in XSim; SAIF power 2 lanes 0.318 W (E5) / 0.319 W (E2) |
