# Board bring-up: from the bitstream to measured numbers on the PYNQ-Z2

> **First time with the board? Use `docs/FPGA_HANDS_ON.md`:** the same plan step by step, with wiring,
> jumpers, LEDs, which machine runs which command, expected output and a demo-day checklist. This file is
> the short task list.

This is the hardware headstart. It takes the bitstreams Vivado built (run 6: v2 + 2 lanes; **run 7: the
2-lane system with E5**, preferred) and turns them into the
numbers the paper is still missing: **bit-exact on silicon, real frames per second, ARM baseline,
power and energy per frame, and the live link with the dashboard.** GUIDE.md §4.2 lists the same work
as tasks A1–A6 with owners; this file is the how-to.

Everything here was rehearsed without a board (17 Oct 2026): the driver, the gate and the live link
were run against the golden-model emulation of the FPGA (`--mock`, `--mock-lanes 2`) for both
bitstreams, including attacks and the dashboard. What has **never** run is the real `PynqBackend`
(Overlay loading, DMA), so expect small fixes in §9.

---

## 0. What you need

| Item | Notes |
|---|---|
| PYNQ-Z2 + 12 V adapter or micro-USB power | jumper on the power source you use |
| micro-SD card, 16 GB or more | for the PYNQ image |
| Ethernet cable | board ↔ laptop directly, or both to the same router |
| The two overlays from the Vivado laptop | `future_work\board\overlay\secure_jpeg.bit` + `.hwh` (v2, 1 pixel/clock) and `secure_jpeg_lanes.bit` + `.hwh` (v3, 2 lanes, 2 pixels/clock) |
| USB power meter (optional, for A4) | inline on the board's supply; reads V, A, W |
| USB webcam (optional, for the live demo) | otherwise a video file or the synthetic scene |

---

## 1. SD card and network (30 min)

1. Download the **PYNQ-Z2 image (v3.0.x)** from pynq.io → *Boards* → PYNQ-Z2. Write it with
   balenaEtcher or Raspberry Pi Imager ("use custom image").
2. Board jumpers: **boot = SD**, power = USB or REG (adapter). Insert the card, connect Ethernet, power on.
   After ~1 min the LEDs settle.
3. Find the board:
   * **Through a router:** the router's client list shows `pynq`; or try `http://pynq:9090`.
   * **Direct cable to the laptop:** the board falls back to the static address **192.168.2.99**.
     Give the laptop's Ethernet adapter `192.168.2.1`, mask `255.255.255.0` (Windows: Settings →
     Network → Ethernet → IP assignment → Manual), then open `http://192.168.2.99:9090`.
4. Jupyter opens; the password is `xilinx`. Write down the board IP (`<BOARD>`) and the laptop's IP on
   the same network (`<LAPTOP>`, from `ipconfig`).

---

## 2. Put the repo and the overlays on the board (15 min)

From the laptop, in the repo folder (Windows 10/11 has `scp` built in):

```
scp -r model link future_work configs experiments requirements.txt xilinx@<BOARD>:/home/xilinx/fpga/
```

The password is `xilinx`. This includes `future_work/board/overlay/` with both `.bit` + `.hwh` pairs.
Each `.bit` must sit next to its `.hwh` **with the same base name**, or PYNQ cannot load it. If `scp` is a
problem, use Jupyter's *Upload* button for a zip of those folders and unzip it in a terminal.

---

## 3. The Python environment on the board (10 min)

Open **Jupyter → New → Terminal** or SSH in (`ssh xilinx@<BOARD>`). PYNQ needs root to touch the FPGA,
so run `sudo -i` first (password `xilinx`), then:

```
source /etc/profile.d/pynq_venv.sh          # PYNQ v3: the Python that has the pynq package
cd /home/xilinx/fpga
python3 -c "import pynq, numpy, cv2; print('ok', pynq.__version__)"
```

* `numpy`, `cv2` (OpenCV) and `pynq` come with the image. **Do not `pip install opencv-python` on the
  board**: there is no wheel for the 32-bit ARM, and building it takes hours. If `cv2` is really missing,
  `apt install python3-opencv`.
* `pip3 install cryptography pillow` only if a later command asks for them (the ARM baseline does).

---

## 4. Rehearse on the laptop first (5 min, no board)

The same scripts run against the golden-model emulation, so typing mistakes are found before the board:

```
python -m future_work.board.first_contact --mock --sizes 64x48 --frames 2 --timing-frames 2
python -m future_work.board.first_contact --mock-lanes 2 --sizes 64x48 --frames 2 --timing-frames 2
```

Both must print `Bit-exact ... **yes**`. Mock times are Python, not the FPGA; never report them.

---

## 5. A1 + A2: the bit-exact gate and real speed (30 min) — the milestone

On the board, for **each** bitstream (separate output folders, so the second does not overwrite the first):

```
python3 -m future_work.board.first_contact --bitfile future_work/board/overlay/secure_jpeg.bit       --sizes 320x240 640x480 --frames 10 --out sim_out/board/v2
python3 -m future_work.board.first_contact --bitfile future_work/board/overlay/secure_jpeg_lanes.bit --sizes 320x240 640x480 --frames 10 --out sim_out/board/lanes
```

What happens:

1. The FPGA is programmed and the driver reads the `VERSION` register: `0x5EC00200` (v2) or `0x5EC00382`
   (lanes; bit 7 = E5 in the RTL). It prints `contract v2` or `contract v3, 2 lanes`.
2. **Part 1, the gate:** for every size and mode E0–E4, 10 frames are encoded on the FPGA and compared
   **byte for byte** with the golden model (v2 or v3 bytes, from the VERSION register), then decrypted by
   the receiver. Any difference stops the run and names the frame and byte offset.
3. **Part 2, speed** (only if the gate passed): `ip.encode` alone (registers + DMA + fabric) and the full
   frame (+ JPEG headers on the ARM), over 50 frames per size and mode → ms/frame and fps.

Output: `sim_out/board/<v2|lanes>/first_contact.md` and `.json`. **When the gate passes, the hardware is
verified on silicon: that sentence goes in the paper.**

What the fps will look like: the fabric alone needs 1.52 (v2) or 0.82 (2 lanes) clocks per pixel at
100 MHz, so about 4.7 ms or 2.5 ms for a 640x480 frame. The script measures more, because the ARM copies
the pixels into the DMA buffer and polls registers. Report both numbers honestly: "encode only" is the
hardware, "incl. headers" is what the system delivers today. If the ARM copy dominates, that is a
software limit (the next step would be a camera straight into the fabric), not the encoder's.

---

## 6. A3: the ARM baseline on the same board (20 min)

The fair comparison is software on the **same** chip's ARM core, which has no AES instructions:

```
pip3 install cryptography            # if missing
python3 -m future_work.baselines.bench_software_codecs --sizes 320x240 640x480 --frames 30
```

It times libjpeg-turbo (through OpenCV), + full AES-128-GCM, + ChaCha20-Poly1305 and + our selective
encryption in Python → `future_work/results/baselines_<host>.md`.

---

## 7. A4: power and energy per frame (1-2 h, needs the USB meter)

1. Meter inline on the board's supply. Record **idle** (booted, nothing running) for 30 s, average W.
2. For each row of `future_work/baselines/power_template.csv`: run that workload continuously (ARM: the
   baseline script with a large `--frames`; FPGA: `first_contact` with a large `--timing-frames`), read
   the meter's 30 s average, and fill in `fps`, `power_w`, `idle_power_w`.
3. On the laptop: `python -m future_work.baselines.energy_table future_work/baselines/power_template.csv`
   → energy per frame (total and dynamic) and the ratio to software.

Rule from GUIDE.md: report what you measure, even if the FPGA path is not better on some metric.

---

## 8. A5: the live link with the dashboard (30 min)

The board becomes the camera: it encodes on the FPGA, encrypts, signs and streams over Ethernet. The
laptop runs the network channel (with the attacker), the receiver and the dashboard.

```
           PYNQ-Z2 (board_sender.py)                         laptop (link.run_all --no-sender)
  camera → FPGA encoder + Ascon → ARM: headers ─UDP→ channel/attacker ─→ receiver ─→ dashboard :8000
             ↑ policy loop (ARM) ←──── authenticated heartbeats ←─────────────┘
```

**Laptop first** (repo root):

```
py -m link.run_all --no-sender --set link.bind_host=0.0.0.0 --set link.sender_host=<BOARD>
```

**Then the board:**

```
python3 -m future_work.board.board_sender --bitfile future_work/board/overlay/secure_jpeg_lanes.bit --set link.host=<LAPTOP> --set link.bind_host=0.0.0.0 --set sender.source=synthetic
```

(`--set sender.source=webcam:0` with a USB webcam, or a video file copied to the board.)

Open `http://localhost:8000` on the laptop. What changes with the board:

* The log says `Sender started ... board encoder`; the Camera tile says *Input to the FPGA encoder*.
* **Encode time** is the FPGA + DMA time per frame; **Encrypted bits** reads *not reported by the FPGA*
  (the fabric does not count them).
* The top protection level is **E5** with the run-7 lane bitstream (VERSION bit 7 set) and **E4** with the
  run-6 bitstreams; the driver decides from the VERSION register. Rehearse E5 with `--mock-lanes 2 --mock-e5`.
* **Key:** both commands need the same `--set keys.master=<KEY>`; make a fresh one with `py scripts\demo_key.py`
  (the key in `configs/default.toml` is public).
* Everything else is the same as the laptop demo: attack buttons, rejections, protection rising,
  rekeying, the eavesdropper view (for both bitstreams).

**Windows firewall:** the first time, Windows asks whether Python may use the network: allow it on
*Private* networks. If nothing arrives, allow the link's UDP ports once (admin Command Prompt):

```
netsh advfirewall firewall add rule name="secure-link" dir=in action=allow protocol=UDP localport=47000-47010
```

To rehearse this exact setup on one laptop: start the laptop command without `--set` flags, then
`py -m future_work.board.board_sender --mock-lanes 2` in a second window.

### A6: the attack scenarios against the board (10 min per run)

The same scripted attacks as the paper's protocol table, with the FPGA as the sender. On the laptop:

```
py experiments\scenario.py --scenario experiments\scenarios\full_suite.json --external-sender <BOARD> --out sim_out\runs\board_full_suite_rep1
```

It starts the channel and receiver, prints the exact `board_sender` command for these ports (replace
`<LAPTOP IP>`), and starts the scenario clock when the board's first report arrives. Run `full_suite`
and `benign` three times each (`_rep1`..`_rep3`). With the run-6 bitstreams the top protection level is E4, so the
analysis counts an attack as mitigated when E4 is reached; with a lane bitstream rebuilt from the current
RTL (E5 in hardware) add `--board-max-mode E5`. Rehearsed with `--mock-lanes 2` on one laptop
(17 Oct 2026, quick scenario): 4/4 attacks mitigated, 0 false alarms. Expect one difference from the
laptop runs: E4 hides the outline no better than E2 (leakage under attack about 0.35, against about 0 with
E5), which is why E5 in hardware (GUIDE.md B6) is the next security step.

---

## 9. When something goes wrong

| Symptom | Likely cause and fix |
|---|---|
| `Overlay(...)` fails to load | `.bit` and `.hwh` not side by side with the same base name; or run as root (§3) |
| `VERSION register reads ...` | the IP or DMA was not found by name: `python3 -c "from pynq import Overlay; print(Overlay('future_work/board/overlay/secure_jpeg.bit').ip_dict.keys())"`, then pass `--ip-name` / `--dma-name` to `first_contact` |
| `TimeoutError: STATUS.DONE never set` | DMA lengths, FCLK0 not running, reset polarity, `tlast`. Try 64x48 first (`--sizes 64x48`) |
| Bytes differ at a small offset | header or registers: quality tables, the HI words of session id / frame counter |
| Bytes differ deep in the scan | pixel word order `{pad, B, G, R}`, or a real data-path difference: rerun XSim on the same frame |
| Gate passes for v2, fails for lanes | the 64-bit DMA: check the frame width is a multiple of 16 and the DMA's MM2S width is 64 in the block design |
| Board slow (< 30 fps at 640x480) | the ARM copying pixels, not the fabric: compare "encode only" with "incl. headers" |
| Dashboard shows nothing in §8 | firewall (§8), wrong IPs, or the laptop command started after the board: restart the board command |

Paste the first error and this file into Claude with `docs/TEAM_CONTEXT.md`.

---

## 10. What to bring back

From the board: `sim_out/board/v2/`, `sim_out/board/lanes/`, `future_work/results/baselines_*.md`, the
filled `power_template.csv`, and a phone video or screen recording of §8 with one attack. Copy them back
(`scp -r xilinx@<BOARD>:/home/xilinx/fpga/sim_out/board .`), commit on a branch, open a pull request.
The paper's placeholders that these fill: §VI board results, the ARM-baseline TODO in the protocol
section, and the "⏳ board" rows of GUIDE.md §5.
