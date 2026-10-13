# The Vivado day: from verified RTL to paper numbers and a PYNQ-Z2 overlay in one day

**Goal for the day:**

1. XSim confirms the RTL in Vivado's own simulator.
2. Post-route resources, timing and power go into the paper.
3. The overlay (`secure_jpeg.bit` + `.hwh`) exists for the board.
4. If a board is at hand: first contact, with a bit-exact check and real fps.

Everything is scripted. You mostly run one command and check the results. Give this file to Claude
together with `docs/TEAM_CONTEXT.md` if anything fails.

**Status of the scripts:**

* `vivado/run_xsim.*` and `vivado/vivado_ooc.tcl` are straightforward; `vivado_ooc.tcl` was improved for this day.
* The block design script (`future_work/board/block_design.tcl`) has **not been run in Vivado yet**.
  Expect one or two small fixes there (step 4 says how).
* Without Vivado, everything was checked only here: the report parser (on reports in Vivado's
  format), the one-command driver (dry run) and the board script (golden-model mock).

| Time | Step | Tool time | Result |
|---|---|---|---|
| the evening before | 0. Install Vivado + board files | 1–3 h (download) | `vivado -version` works |
| 09:00 | 1. XSim | 10 min | `XSIM RESULT: PASS` |
| 09:30 | 2. Post-route numbers of the encoder (100 MHz) | 10–15 min | LUT/FF/BRAM/DSP, WNS, power |
| 10:00 | 3. Per-block numbers + fmax (optional, runs alone) | 30–45 min | Ascon share of the area, max clock |
| 11:00 | 4. Block design → bitstream | 20–30 min per run, + fixes | `overlay/secure_jpeg.bit` + `.hwh` |
| 15:00 | 5. Tables, commit, pull request | 15 min | `sim_out/vivado/vivado_tables.md` |
| 16:00 | 6. Board first contact (if you have the board) | 1–2 h | bit-exact on hardware, real fps |

Steps 1, 2, 4 and 5 can all be done by one command: `python vivado/run_vivado_day.py` (about 1 hour of tool time).

---

## 0. The evening before: install (1–3 h, mostly download)

1. **Vivado.** Use the free *Vivado ML Standard* edition from amd.com → Support → Downloads (it
   needs a free AMD account). The free edition includes the PYNQ-Z2's chip (xc7z020).
   * In the installer choose **Vivado**, then **Vivado ML Standard**.
   * Under devices, tick **only SoCs → Zynq-7000**. This keeps the install to roughly 30–40 GB instead of 100+.
   * **Version:** 2022.1 matches the PYNQ v3.0 image (check the release notes of the image on your SD
     card); any 2020.2 or newer is fine for the paper numbers.
   * No licence file is needed for this device.
   * If a college lab PC already has Vivado 2020.2+, use it and skip the install.
2. **PYNQ-Z2 board files** (exact PS settings). Download the board files from the PYNQ GitHub
   repository or TUL's PYNQ-Z2 page, and copy the `pynq-z2` folder into
   `<Vivado install>/data/boards/board_files/`. The script uses them automatically; without them it
   prints a warning and still works.
3. **The repo and Python.**
   * Keep the repo in a path **without spaces**, e.g. `C:\work\fpga-video-encryption-` or `~/fpga`.
   * Run `git pull` on `main`.
   * Create the Python environment as in `HELP_GUIDE.md` §2.
   * `pip install -r requirements.txt`.
4. **Check:** open a new terminal, then
   ```
   Windows:  C:\Xilinx\Vivado\2022.1\settings64.bat        (or open "Vivado 2022.1 Tcl Shell")
   Linux:    source /tools/Xilinx/Vivado/2022.1/settings64.sh
   vivado -version
   python vivado/run_vivado_day.py --dry-run                 (prints the plan, runs nothing)
   ```

Every step below starts in such a terminal, in the repository root, with the venv active.

---

## 1. XSim: the RTL in Vivado's simulator (10 min)

```
python vivado/run_vivado_day.py --steps xsim
```

It does three things:

1. Writes golden-model test vectors (`vivado/gen_xsim_vectors.py`).
2. Compiles all RTL plus `vivado/tb_secure_jpeg_top.v` in XSim and runs 5 frames.
3. Rebuilds the JPEGs and decrypts them with the receiver (`vivado/check_xsim_output.py`).

**Pass:** `XSIM RESULT: PASS (5 frames bit-exact with the golden model)` and `CHECK RESULT: PASS`.

**Waveforms** (for the report, optional): `bash vivado/run_xsim.sh gui` / `vivado\run_xsim.bat gui`,
or `vivado -mode gui -source vivado/xsim_project.tcl`. Useful signals: `dut/u_enc`, `dut/u_ks`,
`dut/u_tag`. Take one screenshot of a frame passing through.

**If it fails:**

1. Run `make xsim-icarus` on Linux/WSL (it passes in CI). If Icarus passes and XSim fails, it is a
   simulator difference (usually an uninitialised register).
2. Paste the log `sim_build/vivado_logs/xsim_run.log` into Claude.

---

## 2. Post-route numbers of the encoder (10–15 min)

```
python vivado/run_vivado_day.py --steps ooc parse
```

It runs `vivado/vivado_ooc.tcl`: out-of-context synthesis, then place and route of `secure_jpeg_top`
on xc7z020 with a 100 MHz clock (the clock is declared before synthesis, so synthesis is timing-driven).
Then `vivado/parse_reports.py` writes the paper table to `sim_out/vivado/vivado_tables.md`.

**Read three numbers:**

* **WNS** (worst negative slack) in `sim_build/vivado_secure_jpeg_top/timing.txt`. **WNS ≥ 0** means
  100 MHz is met, and only then are the 199 fps (640×480) from the RTL simulation a hardware claim.
  The table also gives *est. fmax = 1000 / (10 − WNS)*.
* **LUT / FF / BRAM / DSP** and % of the chip. The Yosys estimate was ~5.3 K LUTs (~10 %); Vivado's
  number is the one to report.
* **Power** (`power.txt`): Vivado's *vectorless estimate*. Report it as an estimate; real power comes
  from the board (REMAINING_WORK.md, A4).

**If WNS < 0:**

1. Open `timing.txt` and look at the worst path (its start and end registers).
2. Paste the first path into Claude. Usually one extra register stage in that block fixes it, and the
   cocotb tests tell you whether the fix broke anything.
3. If there is no time, report the achieved clock honestly. Use `--fmax` (step 3) to measure it, and
   run the block design at 50 MHz (`--fclk 50`).

---

## 3. Per-block numbers and fmax (optional, 30–45 min, run it over lunch)

```
python vivado/run_vivado_day.py --steps ooc parse --blocks --fmax
```

* **`--blocks`** implements the Ascon core, keystream, tag unit, DCT, quantiser, Huffman and selective
  encryption stage on their own. This gives the paper's breakdown: how much of the area is the
  cryptography (the cost of "in-encoder encryption").
* The hierarchical report of step 2 (`utilization_hier.txt`) gives a breakdown too. The table prints both.
* **`--fmax`** re-runs the top at the clock the first run's slack suggests (5 % margin, 0.5 ns steps),
  so the fmax you report is a measured run, not an extrapolation.

---

## 4. Block design → bitstream (20–30 min per run, budget the afternoon)

1. **Run it:**
   ```
   python vivado/run_vivado_day.py --steps bd parse
   ```
2. **What it builds:**
   * the Zynq PS: DDR, FCLK0 = 100 MHz, a GP0 master and an HP0 slave;
   * an AXI DMA in simple mode: pixels → our `s_axis`, our `m_axis` → scan bytes;
   * our IP through `future_work/board/sjpeg_bd_top.v` (the verified RTL, unchanged);
   * AXI-Lite control, and our interrupts into the PS.
3. **Output:** `future_work/board/overlay/secure_jpeg.bit` + `secure_jpeg.hwh`, plus reports. The
   project is in `future_work/board/vivado_proj/`.
4. **This script has never run in Vivado, so plan for a fix or two:**
   1. Read the first `ERROR:` in `sim_build/vivado_logs/block_design_vivado.log`.
   2. Open the half-built design: `vivado future_work/board/vivado_proj/pynq_secure_jpeg.xpr`, then
      *Open Block Design*.
   3. Fix it by hand in the GUI. *Run Connection Automation* is usually all that is missing.
   4. Copy the Tcl that Vivado printed for your clicks (Tcl console, or `vivado.jou`) into
      `block_design.tcl`, so the script works for the next person.
   5. Or paste the error into Claude.
5. **Then check:**
   * `RESULT overlay fclk=100MHz WNS=...` in the log, with **WNS ≥ 0**. Otherwise use `--fclk 50`
     and say so in the paper.
   * In the block diagram, our IP's `s_axil` has an address. Its offset is in the Address Editor
     (PYNQ reads it from the .hwh).
   * Both `.bit` and `.hwh` exist **with the same base name**.

| First-run error (typical) | Fix |
|---|---|
| `module reference ... could not find include file` | Settings → General → Verilog include directories: add `rtl/include`, then re-run |
| `apply_bd_automation ... invalid -config` | Do the connection automation in the GUI and copy the journal's command into the script |
| `[BD 41-...] pin already connected` | Delete the duplicate `connect_bd_net` line (the automation already wired it) |
| `IP ... is locked / version` | Tools → Report IP Status → Upgrade, then re-run |
| Timing fails only in the full design | `--fclk 50`, or run step 3 and fix the slow block |

---

## 5. Tables, commit and pull request (15 min)

```
python vivado/run_vivado_day.py --steps parse
git checkout -b vivado-results
git add future_work/board/overlay future_work/board/block_design.tcl vivado/ docs/
git commit -m "Vivado: post-route results and PYNQ-Z2 overlay (Vivado <version>)"
git push -u origin vivado-results        (then open a pull request on GitHub)
```

* **Commit the overlay** (`.bit` ~4 MB + `.hwh` + reports), so teammates without Vivado can use the board.
* **Also commit** any fixes you made to `block_design.tcl`.
* **Do not commit** `sim_build/`, `vivado_proj/` or `.Xil/` (they are git-ignored).
* Send `sim_out/vivado/vivado_tables.md` to the team: it is the paper's hardware table, and
  `python -m future_work.figures.paper_tables --root sim_out` puts it next to all the simulation tables.

---

## 6. First contact with the board (1–2 h, if the board is there)

1. **Prepare the board.**
   * Write the PYNQ-Z2 image (v3.0.x from pynq.io) to a ≥ 16 GB SD card.
   * Set the boot jumper to SD.
   * Connect Ethernet to the laptop or router, and power the board over USB or an adapter.
   * Open `http://pynq:9090` (or the board's IP); the password is `xilinx`.
2. **Copy the repo onto the board**, including `future_work/board/overlay/`. Use the Jupyter
   upload or `scp -r` to `/home/xilinx/fpga`.
3. **Start a terminal on the board:** in Jupyter *New → Terminal*, then
   ```
   cd /home/xilinx/fpga
   sudo -E pip3 install -r requirements.txt     (skip packages that fail; the board needs numpy,
                                                  pillow, opencv; no cocotb, no torch)
   sudo -E python3 -m future_work.board.first_contact --sizes 320x240 640x480 --frames 10
   ```
4. **The bit-exact gate** comes first. For every size and mode E0–E4, it checks that the FPGA's JPEG
   equals the golden model's byte for byte, and that the receiver decrypts it. Only if all pass does
   it time the encoder (`sim_out/board/first_contact.md`).

**The gate passing is the milestone of the day: the hardware is verified on silicon.**

| Problem | Likely cause |
|---|---|
| `VERSION register reads ...` | wrong IP picked: `print(Overlay(...).ip_dict.keys())`, pass `--ip-name` / `--dma-name` |
| `TimeoutError: STATUS.DONE never set` | DMA lengths, the clock not running (FCLK0), reset polarity, or `tlast` |
| Bytes differ at a small offset | header or registers: quality tables, session id / frame counter HI words |
| Bytes differ deep in the scan | pixel word order `{pad, B, G, R}`, or a data path difference; compare with XSim |
| Encode is slow (< 30 fps at 640×480) | the Python on the ARM (copying pixels), not the fabric; time `ip.encode` alone |

If the gate passes and time is left:

* **ARM baseline:** `python3 -m future_work.baselines.bench_software_codecs --sizes 320x240 640x480`.
* **Power:** with a USB power meter, measure idle, ARM encoding and FPGA encoding (see REMAINING_WORK.md, A4).

---

## What you have at the end of the day

| Paper item | File |
|---|---|
| Resources, timing, power of the encoder (+ per-block breakdown, fmax) | `sim_out/vivado/vivado_tables.md` |
| XSim confirmation (+ waveform screenshot) | `sim_build/vivado_logs/xsim_run.log` |
| Overlay for the board | `future_work/board/overlay/` |
| Bit-exact on hardware, real fps (if board) | `sim_out/board/first_contact.md` |

What comes after this day is in **`docs/REMAINING_WORK.md`**.
