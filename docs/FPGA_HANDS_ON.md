# FPGA hands-on: from the box to measured numbers on the PYNQ-Z2

This is the step-by-step manual for the day the board is on the table. It assumes nothing: what to
plug where, what each light means, which command runs **on which machine**, and what the screen must
show when it worked. `docs/BOARD_BRINGUP.md` is the short version of the same plan with the paper's
task numbers (A1–A6); `docs/HW_TODO.md` says what is left in the hardware.

Everything below was rehearsed without a board: the driver, the bit-exact gate, the live sender and the
attack scenarios run against an emulation of the bitstream (`--mock`, `--mock-lanes 2 --mock-e5`) and
pass. What has never run is the real PYNQ path (Overlay load + AXI DMA). Expect one or two small fixes
on day 1; §11 lists the likely ones.

---

## 0. How other papers did their hardware implementation (and why we do more)

Before the steps, the context, because reviewers will compare (paper: Section II-F, Table 1):

| Work | What they did on hardware | What they reported |
|---|---|---|
| Kishore et al. (JPEG + scrambling) | Stratix II/IV, synthesis | resources; frame rate **computed** as 1 / (coding time of one frame at the clock), PSNR |
| Bağbaba & Örs (JPEG + TEA) | Virtex-6 ML605 kit | resources, PSNR/RMSE |
| Khairallah & Yadhunathan (Ascon MACs) | Artix-7, Vivado synthesis | LUT/FF, throughput from the clock, Vivado power |
| Gladis Kurian & Chen (Ascon + replay filter) | Arty A7-100T **board**; replay detection shown with **LEDs** | resources, on-chip power, latency in simulation |
| Farahmand, Homsirikamol & Gaj (Zynq crypto testbed) | ZedBoard (same Zynq-7020 as ours): **AXI DMA** between DDR and the core, **AXI timer** for time, every output compared with software, clock raised by binary search until results break | measured throughput, max working frequency, HW/SW speedup |

So most papers stop at synthesis. The strongest method (Farahmand et al.) is exactly our structure:
DMA + timing + bit-exact comparison against software. We add: a golden model as the reference for every
byte and tag, post-route timing, SAIF power, and an end-to-end live link with attacks. **The board
numbers are the last missing piece** — that is what this file produces.

---

## 1. What you need on the table

| Item | Why | Notes |
|---|---|---|
| PYNQ-Z2 board | the hardware | handle by the edges; touch a metal case first (static) |
| micro-SD card, **16 GB or more** | holds the PYNQ Linux image | class 10; you will erase it |
| micro-USB cable (data, not charge-only) | power **and** serial console | into the port labelled **PROG / UART** |
| Ethernet cable | board ↔ laptop or router | any CAT5e/6 |
| Laptop with the repo | runs the receiver, dashboard, attacker | Windows: repo at `E:\FPGA-Video-Encryption-` |
| The bitstream pair | the hardware design | `secure_jpeg_lanes.bit` **and** `secure_jpeg_lanes.hwh` (same base name!) |
| USB power meter (inline, ~₹500) | power and energy (A4) | sits between the USB supply and the board's cable |
| Optional: USB webcam | live camera demo | otherwise a video file or the synthetic scene |
| Optional: router / switch | lets a second laptop or phone watch the dashboard | the board, the laptop and the viewer on one LAN |

**Which bitstream.** The E5-capable two-lane system from Vivado run 7 (18 Oct) is on tom's PC:
`D:\FPGA-Video-Encryption-\future_work\board\overlay\secure_jpeg_lanes.bit` + `.hwh`. The run-6 pair (no
E5) is on Samarth's laptop under `E:\FPGA-Video-Encryption-\future_work\board\overlay\`. If neither is at
hand, rebuild on any PC with Vivado (about 1 h):

```
cd /d E:\FPGA-Video-Encryption-
py vivado\run_vivado_day.py --steps bd_lanes parse
```

It ends with `future_work\board\overlay\secure_jpeg_lanes.bit` and `.hwh`. Copy **both** to a USB stick.

---

## 2. Know the board (30 seconds)

```
                         PYNQ-Z2, seen from above
   ┌──────────────────────────────────────────────────────────────────┐
   │  [Power switch]   [Power jumper: USB | REG]   [Boot jumper: SD]  │
   │                                                                  │
   │  (PROG / UART micro-USB)  ← power + serial console               │
   │  (12 V barrel jack)       ← only if Power jumper = REG           │
   │  (RJ45 Ethernet)          ← laptop or router                     │
   │                                                                  │
   │  LEDs: red = power   DONE (green/yellow) = FPGA configured       │
   │        4 green + 2 blue user LEDs = boot progress                │
   │  micro-SD slot: on the underside                                 │
   └──────────────────────────────────────────────────────────────────┘
```

Set **two jumpers** before the first power-on:

1. **Boot jumper → SD** (boot Linux from the card).
2. **Power jumper → USB** (power from the PROG/UART micro-USB). Use **REG** only with a 12 V adapter in the
   barrel jack; check the TUL PYNQ-Z2 manual for the jack's polarity before you plug in any adapter that
   did not come with the board. For power measurements (§8) USB power is the easier choice, because the
   inline USB meter then sees everything the board draws.

---

## 3. Prepare the SD card (laptop, 20 min, once)

1. Download the **PYNQ-Z2** image from <https://www.pynq.io> → *Boards* → PYNQ-Z2 (version 3.0.x).
2. Write it with **balenaEtcher** (or Raspberry Pi Imager → *Use custom*). This erases the card.
3. Eject the card safely, insert it into the board's slot (underside, contacts facing the board).

---

## 4. First power-on and what the lights mean

1. Plug the micro-USB into **PROG / UART** and the laptop (or a 5 V / 2 A USB adapter).
2. Plug the Ethernet cable (§5 says where to).
3. Slide the **power switch ON**.

| What you see | Meaning |
|---|---|
| red LED on at once | board has power |
| DONE LED (green/yellow) after a few seconds | the Zynq is running |
| after ~1 min the 4 green + 2 blue LEDs flash together | Linux is booting |
| blue LEDs turn on and off, green ones stay on | **booted and ready** |
| only the red LED, nothing else after 2 min | SD card not written correctly or Boot jumper not on SD |

**Serial console (optional but the surest way to see what happens).** Windows: Device Manager → *Ports
(COM & LPT)* → note the *USB Serial Port (COMx)*. Open PuTTY → *Serial*, line `COMx`, speed **115200**
(8 data bits, 1 stop bit, no parity, no flow control) → Open → press Enter. You get a login prompt
(`xilinx` / `xilinx`). `ip -4 addr show eth0` prints the board's IP address.

---

## 5. Network: put the board and the laptop on one network

**Option A — through a router (best for the demo).** Board and laptop both on the same router (board by
cable, laptop by cable or Wi-Fi). The board gets an address by DHCP. Find it in the router's client list
(name `pynq`), or with the serial console (§4), or try `http://pynq:9090` in a browser.

**Option B — cable directly into the laptop.** Without a DHCP server the board falls back to
**192.168.2.99**. Give the laptop's Ethernet adapter a fixed address in the same network:
Windows Settings → Network → Ethernet → *IP assignment: Manual* → IPv4 **192.168.2.1**, mask
**255.255.255.0**, no gateway. (Undo it after the session.)

Check: `ping 192.168.2.99` (or the DHCP address) from the laptop must answer.

Write these two down; every command below uses them:

```
<BOARD>  = the board's IP     (e.g. 192.168.2.99 or 192.168.1.37)
<LAPTOP> = the laptop's IP on the same network   (ipconfig → the Ethernet/Wi-Fi adapter in use)
```

---

## 6. Copy the project and the bitstream to the board (10 min)

**Where things run:** from now on every block says **[laptop]** or **[board]**.

**[laptop]** (Command Prompt, in the repo folder; Windows 10/11 has `scp` built in; password `xilinx`):

```
cd /d E:\FPGA-Video-Encryption-
ssh xilinx@<BOARD> "mkdir -p /home/xilinx/fpga"
scp -r model link future_work configs experiments scripts requirements.txt xilinx@<BOARD>:/home/xilinx/fpga/
```

`future_work/board/overlay/` must contain `secure_jpeg_lanes.bit` **and** `secure_jpeg_lanes.hwh`.
If the bitstream came on a USB stick, copy both files into that folder first, or send them separately:

```
scp secure_jpeg_lanes.bit secure_jpeg_lanes.hwh xilinx@<BOARD>:/home/xilinx/fpga/future_work/board/overlay/
```

No `scp`? Open `\\<BOARD>\xilinx` in Windows Explorer (user `xilinx`, password `xilinx`), or Jupyter's
*Upload* button at `http://<BOARD>:9090` with a zip, then unzip in a Jupyter terminal.

---

## 7. Log in and prepare Python on the board (5 min)

**[laptop]** `ssh xilinx@<BOARD>` (password `xilinx`), or Jupyter → *New* → *Terminal*. Then **[board]**:

```
sudo -i                                   # the FPGA and the DMA need root (password xilinx)
source /etc/profile.d/pynq_venv.sh        # PYNQ v3 keeps its Python in this environment
cd /home/xilinx/fpga
python3 -c "import pynq, numpy, cv2; print('ok', pynq.__version__)"
```

It must print `ok 3.x`. Do **not** `pip install opencv-python` on the board (no wheel for the 32-bit ARM;
building takes hours); if `cv2` is missing: `apt install python3-opencv`.

---

## 8. The milestone: bit-exact on silicon (A1) and real speed (A2), 30 min

**[laptop] first, the rehearsal (1 min, no board):** proves the command is right.

```
py -m future_work.board.first_contact --mock-lanes 2 --mock-e5 --sizes 64x48 --frames 1 --timing-frames 2
```

It prints `VERSION ok: contract v3, 2 lanes, E5 in hardware`, six lines `64x48 E0 … E5: bit-exact`, and a
table. Mock timings are Python, never report them.

**[board] the real run:**

```
python3 -m future_work.board.first_contact --bitfile future_work/board/overlay/secure_jpeg_lanes.bit --sizes 64x48 --frames 1 --timing-frames 2 --out sim_out/board/smoke
python3 -m future_work.board.first_contact --bitfile future_work/board/overlay/secure_jpeg_lanes.bit --sizes 320x240 640x480 --frames 10 --out sim_out/board/lanes
```

The first line is a 10-second smoke test; the second is the measurement. What happens and what you
must see:

1. The FPGA is programmed with the bitstream and the driver reads the `VERSION` register:
   **`0x5EC00382`** = contract v3, 2 lanes, bit 7 set = E5 in hardware. The line reads
   `IP found (…secure_jpeg_lanes.bit), VERSION ok: contract v3, 2 lanes, E5 in hardware.`
   (`0x5EC00302` = 2 lanes without E5, an older bitstream: E0–E4 only; `0x5EC00200` = the single-pipeline
   bitstream `secure_jpeg.bit`.)
2. **Part 1, the gate.** For every size and level, 10 frames are encoded **on the FPGA** and compared byte
   for byte (scan and tag) with the golden model, then decrypted by the receiver. Every line must say
   `bit-exact`; any `MISMATCH` stops the run and names the frame and the first wrong byte.
3. **Part 2, speed** (only if Part 1 passed): ms per frame for "encode only" (registers + DMA + fabric)
   and "with headers" (plus the ARM's JPEG headers), per size and level.
4. Result files: `sim_out/board/lanes/first_contact.md` and `.json`. The last line says
   `Bit-exact with the golden model in every size and mode: **yes**` — **that sentence goes into the
   paper** (Section VIII-D).

**How to read the speed.** The fabric alone needs 0.82 clock cycles per pixel with 2 lanes at 100 MHz,
about 2.5 ms for 640x480. The measured time will be larger because the ARM copies pixels into the DMA
buffer and polls registers. Report both numbers honestly; if the ARM copy dominates, that is a software
limit (next step: camera straight into the fabric), not the encoder's.

---

## 9. ARM baseline (A3) and power (A4)

**A3 [board]** The fair comparison is the **same function** on the **same chip's** processing system (PS: two
Cortex-A9 cores, no AES instructions). `future_work/arm/` holds our whole encoder in C
(`native/sjpeg_sw.c`), bit-exact with the golden model and therefore with the fabric, plus the standard
software alternatives:

```
pip3 install cryptography            # if missing (for the AES-GCM row)
# after first_contact (A1/A2) has written sim_out/board/first_contact.json:
CFLAGS="-mcpu=cortex-a9 -mfpu=neon" python3 -m future_work.arm.arm_baseline --sizes 320x240 640x480 --frames 30
```

It first checks that the PS encoder is bit-exact with the model (every mode, 1 and 2 threads), then
times: our encoder on 1 and 2 ARM cores (E0, E2, E4, E5, incl. headers and the E5 order), libjpeg-turbo
alone, libjpeg-turbo + Ascon-AEAD128 over the whole file (C), libjpeg-turbo + AES-128-GCM (OpenSSL), and
puts the fabric's round trip and fabric-only time (CYCLES) from `first_contact.json` next to them →
`sim_out/board/arm_baseline.md`. Copy it with first_contact.json to `paper/data/board/<run>/`.
The older `future_work.baselines.bench_software_codecs` (selective encryption in Python) is kept for
reference only: Python is not a fair baseline.

The same C encoder also runs the camera node without a bitstream (PS only):
`python3 -m future_work.board.board_sender --software 2 ...` (same bytes, the receiver cannot tell).

**A4 power with the USB meter.** Wiring: USB supply → **meter** → micro-USB cable → PROG/UART port.

1. Board booted, nothing running: read the meter's average over 30 s → **idle W**.
2. For each row of `future_work/baselines/power_template.csv`, start that workload in a loop
   (FPGA: `first_contact … --timing-frames 2000`; ARM: the baseline with `--frames 2000`), read the 30 s
   average → fill `power_w`, `fps`, `idle_power_w`.
3. **[laptop]** `py -m future_work.baselines.energy_table future_work\baselines\power_template.csv` → energy
   per frame (total and dynamic) and the ratio to software.

Take a photo of the meter during each reading (evidence for the paper and the viva).

---

## 10. The live demo: board as camera, laptop as receiver (A5) and attacks (A6)

```
  PYNQ-Z2 (board_sender)                      laptop (link.run_all --no-sender)              viewer
  camera/file → FPGA encode+encrypt+tag → ARM headers, E5 order ─UDP→ channel/attacker → receiver → dashboard :8000 ← browser / VLC
                 ↑ policy (ARM) ←──────── authenticated heartbeats ←──────────────────────┘
```

**Key.** `configs/default.toml` holds a public example key. For a demo make a fresh one **[laptop]**:

```
py scripts\demo_key.py
```

It prints the key and the exact laptop and board commands with `--set keys.master=<key>` filled in
(the file `configs\demo_key.txt` is git-ignored). Type the same key on the board. The key never travels
over the network or the dashboard: that is the "pre-shared" assumption of the paper.

**[laptop] first**, then **[board]** (replace the IPs and the key; `demo_key.py` prints these lines):

```
py -m link.run_all --no-sender --set keys.master=<KEY> --set link.bind_host=0.0.0.0 --set link.sender_host=<BOARD> --set dashboard.bind_host=0.0.0.0
```
```
python3 -m future_work.board.board_sender --bitfile future_work/board/overlay/secure_jpeg_lanes.bit --set keys.master=<KEY> --set link.host=<LAPTOP> --set link.bind_host=0.0.0.0 --set sender.source=synthetic
```

(`--set sender.source=webcam:0` with a USB webcam on the board, or a video file copied to the board.)

**Check the output:**

| Where | What you must see |
|---|---|
| laptop browser `http://localhost:8000` | log line `Sender started … board encoder`; Camera tile *Input to the FPGA encoder*; Receiver view playing; counters **verified** rising, **rejected 0** |
| second laptop / phone `http://<LAPTOP>:8000` | the same dashboard (guide: `docs/DASHBOARD_LAN_DEMO.md`) |
| VLC → *Media → Open Network Stream* → `http://<LAPTOP>:8000/stream/wire.mjpg` | the **scrambled** wire stream: what any viewer without the key sees |
| dashboard top bar | protection level E2 when calm; E5 when attacked (VERSION bit 7 set) |

**Attack live:** press *bit flip* on the dashboard → the receiver rejects the first tampered frame
(red counter), shows the last good frame instead of garbage, the board's policy jumps to **E5**, and
after the attack it returns to E2. Then the scripted suite **[laptop]**:

```
py experiments\scenario.py --scenario experiments\scenarios\full_suite.json --external-sender <BOARD> --board-max-mode E5 --set keys.master=<KEY> --out sim_out\runs\board_full_suite_rep1
```

It prints the exact `board_sender` command for its ports, including your `--set keys.master` (start it on
the board), waits for the board's
first report, then runs the 11 attacks 25 s apart. Run `full_suite` and `benign` three times each
(`_rep1`…`_rep3`): that is the "on hardware" row next to the simulation's 11/11.

**Windows firewall:** allow Python on *Private* networks when asked. If nothing arrives (admin prompt):
`netsh advfirewall firewall add rule name="secure-link" dir=in action=allow protocol=UDP localport=47000-47010`

**Shut down cleanly** before switching off **[board]**: `sudo shutdown -h now`, wait for the LEDs to stop,
then the power switch. Pulling power while Linux writes can corrupt the SD card.

---

## 11. When something goes wrong

| Symptom | Likely cause → fix |
|---|---|
| only the red LED | SD card not written, or Boot jumper not on SD → rewrite with Etcher, check jumper |
| `ping` fails | wrong IP / laptop not in 192.168.2.x (option B) / Wi-Fi isolation on the router → use the serial console to read the IP; try option B |
| `ModuleNotFoundError: pynq` | forgot `source /etc/profile.d/pynq_venv.sh` (and `sudo -i` before it) |
| `Overlay(...)` fails / `.hwh` not found | `.bit` and `.hwh` not side by side with the **same base name** |
| `VERSION register reads 0x…` or IP not found | names in the block design differ: `python3 -c "from pynq import Overlay; print(Overlay('future_work/board/overlay/secure_jpeg_lanes.bit').ip_dict.keys())"`, then pass `--ip-name` / `--dma-name` |
| `TimeoutError: DMA receive (S2MM, scan out) not finished` (older drivers: hangs in `recvchannel.wait()`) | a bitstream built before bug #32 (20 Oct 2026): the DMA's write master was not connected to DDR. Rebuild the overlay with the current `block_design.tcl` (`py vivado\run_vivado_day.py --steps bd_lanes --jobs 2`) |
| `RuntimeError: No Devices Found` / `is the XRT environment sourced?` | root without a login shell (`sudo bash -c ...`): use `sudo -i` (or `source /etc/profile.d/xrt_setup.sh` as well as `pynq_venv.sh`) |
| `TimeoutError: STATUS.DONE never set` | DMA lengths, `tlast`, clock or reset → try `--sizes 64x48` first; paste the first error into Claude with `docs/TEAM_CONTEXT.md` |
| bytes differ at a small offset | header or registers: quality tables, the HI words of session id / frame counter |
| bytes differ deep in the scan | pixel word order `{pad, B, G, R}` or a real datapath difference → rerun XSim on the same frame (`docs/VIVADO_ONE_DAY.md`) |
| gate passes E0–E4, E5 missing | old bitstream (VERSION without bit 7) → use the run-7 pair |
| dashboard empty in §10 | firewall, wrong IPs, laptop started after the board → restart the board command |
| every frame **rejected (tag)** | the two ends use different keys → same `--set keys.master=` on both |
| board slow (< 30 fps at 640x480) | the ARM copy, not the fabric → compare "encode only" with "with headers" |

---

## 12. What to bring back (and where it goes)

**[laptop]** `scp -r xilinx@<BOARD>:/home/xilinx/fpga/sim_out/board .` and
`scp xilinx@<BOARD>:/home/xilinx/fpga/future_work/results/baselines_*.md future_work/results/`, plus
the filled `power_template.csv`, the meter photos, and a phone video of §10 with one attack. Commit on
a branch, open a pull request. In the papers they fill: `sections/access_08_hwresults.tex` (Section
VIII-D, the red TODO), Table 1's "Ours" row, and the limitation sentence of `conference.tex`.

## 13. A demo-day checklist

- [ ] jumpers: Boot = SD, Power = USB (or REG with the right adapter)
- [ ] `ping <BOARD>` answers; `ssh` works
- [ ] `first_contact` smoke test passes (64x48) on the board
- [ ] fresh key made with `scripts\demo_key.py`, same key on both ends
- [ ] laptop dashboard shows verified frames; second device opens `http://<LAPTOP>:8000`; VLC shows the wire stream
- [ ] one live bit-flip: rejection, E5, recovery
- [ ] `sudo shutdown -h now` before switching off
