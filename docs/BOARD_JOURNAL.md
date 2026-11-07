# Journal board phase on the PYNQ-Z2, step by step

This is the board part of `docs/JOURNAL_RUNBOOK.md` (section 2), written as a list of commands to type. It
assumes the board was set up once before (PYNQ 3.1.1 image, direct Ethernet cable, the board day of 24 Oct
2026) and a Windows laptop with this repository and its `.venv`.

Order: **0** get the branch, **1** checks without the board, **2** (optional) rebuild the tamper image, **3**
start the board, **4** the experiments, **5** save the results to git, **6** shut down. Part 1 must pass
before part 3. A board day spent on a design that the simulation already rejects is wasted.

| Machine | Address | Window |
|---|---|---|
| Board (PYNQ-Z2) | `192.168.2.99` | **Board window**: ssh; the line starts with `root@pynq:/home/xilinx/fpga_journal#` |
| Laptop | `192.168.2.1` | **Laptop window**: Command Prompt in `D:\FPGA-journal`; the line starts with `(.venv)` |

Board commands (`python3`, `sudo`, `export`) only work in the board window. Laptop commands (`py`, `git`,
`scp`) only work in the laptop window.

### What is new on this branch for the board

* `first_contact --pipeline`: the ARM builds the JPEG of frame t (headers, APP11, E5 shuffle) while the
  fabric already encodes frame t+1 (`SecureJpegIP.encode_start` / `encode_finish` in
  `software/system/board/pynq_driver.py`). The pipelined JPEGs must be byte-identical to the one-by-one
  JPEGs, or the run is marked not bit-exact. Journal item "faster driver"; results in the `pipe_ms` /
  `pipe_fps` columns.
* The driver now arms the receive DMA channel before START (`docs/INTERFACES.md` §3), so the pixels start
  one pynq `transfer()` call earlier. Compare `in_wait` with the 24 Oct numbers (about 0.64 ms per frame).
  The send channel still starts after START. This change affects every image, so the bit-exact gate (4.1)
  is run first.

---

## 0. A separate copy for the journal work (laptop window, once)

The journal work lives in its own folder, with its own `.venv` and `sim_out`, on the laptop and on the board.
The folder you present from (the non-journal version) is never switched to this branch, and nothing
here changes it.

| | Presentation version | Journal version |
|---|---|---|
| Laptop folder | your existing clone | `D:\FPGA-journal` |
| Git branch | `main` | `journal-version` |
| Board folder | `/home/xilinx/fpga` | `/home/xilinx/fpga_journal` |

```
cd /d D:\
git clone -b journal-version https://github.com/vij-ship-it/FPGA-Video-Encryption- FPGA-journal
cd FPGA-journal
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
py software\scripts\check_setup.py
```
**Expect:** 0 FAIL. Each folder needs its own `.venv`: `requirements.txt` installs the packages in editable
mode, so one `.venv` always runs the code of the folder it was installed from. Always activate the `.venv` of
the folder you are in.

The demo key is not in git. Copy it from the presentation folder, using that folder's path:
`copy <presentation folder>\software\configs\demo_key.txt software\configs\` (older layouts keep it in
`configs\demo_key.txt`). You can also make a new key with `py software\scripts\demo_key.py`.

Every command below runs in `D:\FPGA-journal`, with its `.venv` active.

## 1. Checks without the board (laptop window)

1. Tests (about 1 min; the RTL tests need Icarus and run in WSL with `make test`):
   ```
   py -m pytest -q tests
   ```
   **Expect:** all passed, a few skipped (337 passed, 7 skipped on this branch on 7 Nov 2026).
2. The board programs against an emulated board (about 20 min, `--quick` about 5 min):
   ```
   py software\scripts\emulated_board_check.py --quick
   ```
   **Expect:** every step PASS.
3. The new pipelined loop on the emulated 4-lane image (seconds):
   ```
   cd software
   py -m system.board.first_contact --mock-lanes 4 --mock-e5 --sizes 64x48 --frames 2 --timing-frames 3 --zero-copy --pipeline --out ..\sim_out\mock_pipeline
   cd ..
   ```
   **Expect:** `Same bytes` = yes in every row. The times are the Python emulation: never report them.
4. **Gate:** the software-phase results pass the four checks in `docs/JOURNAL_RUNBOOK.md` ("Gate before
   the board phase"). They are already in git: `results/simulation/journal_kaggle/` (Kaggle, 6 Nov, 27 of 27
   steps), `results/hardware/vivado_journal/` (Vivado, 7 Nov) and `results/simulation/multi_camera_laptop/`.
   Part 5.2 is only for later reruns.

## 2. Tamper image with the BTN0 debounce (done)

Samarth rebuilt it in the 7 Nov Vivado run (`bd_tamper`, X13). It is
`software/system/board/overlay/secure_jpeg_lanes_tamper.bit`, recorded in `bitstreams.json` as
"journal X13 (7 Nov 2026)" (SHA-256 `3d3154be762c0e1b...`). It replaces run 13, which had no debounce.
Nothing to do here.

## 3. Start the board (about 10 min)

### 3.1 Board on
1. Jumpers: **Boot → SD**, **Power → REG** with a 12 V supply (USB power is not enough for a webcam).
2. Micro-USB into **PROG/UART**, Ethernet cable from the board to the laptop. Switch on and wait about
   1 min, until the green LEDs stay on.
3. Laptop: Settings → Network → Ethernet → IP assignment → **Manual**, IPv4 `192.168.2.1`, mask
   `255.255.255.0`, gateway empty. Then `ping 192.168.2.99`.

### 3.2 Copy this branch to a NEW folder on the board (laptop window, password `xilinx`)
Use a new folder. The old `/home/xilinx/fpga` has top-level `model/`, `link/` and `system/` from before the
six-folder layout, and Python would load those instead of the new ones in `software/`.
```
ssh xilinx@192.168.2.99 "mkdir -p /home/xilinx/fpga_journal"
scp -r software experiments pyproject.toml requirements.txt xilinx@192.168.2.99:/home/xilinx/fpga_journal/
```
Repeat the `scp` after every `git pull` that changes code. It does not touch results on the board.

### 3.3 Board window (a second Command Prompt; one line at a time)
```
ssh xilinx@192.168.2.99
sudo -i
source /etc/profile.d/pynq_venv.sh
cd /home/xilinx/fpga_journal
export PYTHONPATH=$PWD/software
python3 software/scripts/check_setup.py --board
python3 software/scripts/publish_bitstreams.py --check
```
**Expect:** 0 FAIL, and every image ok. Run `export PYTHONPATH=...` again in every new board window.

### 3.4 Clock (laptop window, password `xilinx` twice)
The board has no battery clock. Run this after every power-up, and again right before every timed run
in 4.6–4.9 (the clocks drift about 30 ms per 15 min):
```
py software\scripts\set_board_clock.py
```
**Expect:** `difference left` under 1 ms.

### 3.5 Key
Laptop window:
```
set /p KEY=<software\configs\demo_key.txt
echo %KEY%
```
Board window, type the key that `echo` printed:
```
KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```
The commands below use `%KEY%` on the laptop and `$KEY` on the board. Never type `<KEY>` literally.

---

## 4. The experiments

Run them in this order. 4.1 is the gate: if it does not print `Bit-exact ... yes`, stop and send the output.
Every board command writes to `sim_out/` in `/home/xilinx/fpga_journal`. Part 5 copies everything to the
laptop. `--resume` continues a stopped `first_contact` run.

### 4.1 Bit-exact gate and speed, 4 lanes, with the pipelined loop (X4, about 15 min)
Board window:
```
python3 -m system.board.first_contact --bitfile software/system/board/overlay/secure_jpeg_lanes4.bit --sizes 320x240 640x480 --frames 3 --timing-frames 100 --zero-copy --pipeline --out sim_out/board/j_lanes4
```
**Expect:** `Bit-exact ... yes`, `Same bytes` yes in every pipelined row, and a `Pipelined` column
faster than `Complete frame, one by one`. 24 Oct for comparison: 640x480 zero-copy 5.9 ms (169 fps), E5
119 fps.

### 4.2 Same on the 2-lane image (about 10 min)
```
python3 -m system.board.first_contact --bitfile software/system/board/overlay/secure_jpeg_lanes.bit --sizes 320x240 640x480 --frames 3 --timing-frames 100 --zero-copy --pipeline --out sim_out/board/j_lanes2
```
Check the printed `fabric clock`: it must be 100 MHz (bug #44: 62.5 MHz means the driver did not set it).

### 4.3 ARM against the FPGA (X4, about 10 min)
```
python3 -m system.arm.arm_baseline --pl-json sim_out/board/j_lanes4/first_contact.json --out sim_out/board/j_arm
```

### 4.4 HD: 720p and 1080p (X2, about 20 min)
Sizes must be multiples of 16, so 1080p is coded as 1920x1088.
```
python3 -m system.board.first_contact --bitfile software/system/board/overlay/secure_jpeg_lanes4hd.bit --sizes 1280x720 1920x1088 --frames 2 --timing-frames 30 --zero-copy --pipeline --out sim_out/board/j_hd
```
This image has never run on the board. If it times out, add `--fclk 100` and run it again.

### 4.5 Camera-native YUYV image (X2, about 10 min)
Lines up to 1024 pixels.
```
python3 -m system.board.first_contact --bitfile software/system/board/overlay/secure_jpeg_lanes4yuyv.bit --sizes 640x480 1024x768 --frames 3 --timing-frames 100 --zero-copy --pipeline --out sim_out/board/j_yuyv
```
This image has never run on the board either: same `--fclk 100` fallback.

### 4.6 Webcam as the source (X5, about 5 min)
Plug the USB webcam into the board (12 V supply). 320x240 is the size that runs live. 640x480 runs under
10 fps, because the ARM copies each frame.
```
python3 -m system.board.first_contact --bitfile software/system/board/overlay/secure_jpeg_lanes4.bit --source webcam:0 --sizes 320x240 640x480 --frames 3 --timing-frames 100 --pipeline --out sim_out/board/j_webcam
```
Then the live link with the webcam (stop with Ctrl+C on the board first, then on the laptop):
Laptop window:
```
py -m link.run_all --no-sender --pq-kex --set keys.master=%KEY% --set link.bind_host=0.0.0.0 --set link.sender_host=192.168.2.99 --set dashboard.bind_host=0.0.0.0
```
Board window, within 2 minutes:
```
python3 -m system.board.board_sender --bitfile software/system/board/overlay/secure_jpeg_lanes4.bit --pq-kex --set keys.master=$KEY --set link.host=192.168.2.1 --set link.bind_host=0.0.0.0 --set link.pad=runmax --set sender.source=webcam:0 --set sender.width=320 --set sender.height=240
```
Open http://localhost:8000. Film a running stopwatch with the webcam and photograph it next to the
dashboard's picture to get the glass-to-glass latency. Take 10 photos and write the times next to the run.

### 4.7 The attack suite 5 times with the board as camera (X3, about 30 min)
Sync the clock (3.4) first. Laptop window:
```
py experiments\repeat_runs.py --reps 5 --external-sender 192.168.2.99 --board-max-mode E5 --set keys.master=%KEY% --out sim_out\runs\board_repeat_runs
```
Every repetition needs a NEW board sender. When the laptop prints `=== repetition N ===` and a board
command (it starts with `sudo -E env PYTHONPATH=software`):
1. Board window: **Ctrl+C** first, if a sender from the last repetition is still running.
2. Board window: paste the command with `<LAPTOP IP>` replaced by `192.168.2.1` (from repetition 2 on,
   up arrow + Enter gives the same command).
3. Leave both windows alone until the next `=== repetition ... ===` (or the table after the last one).

The laptop waits for the new sender before it starts the clock. If it prints `a board sender from an
earlier run is still streaming`, do steps 1 and 2. (On 7 Nov an old sender started the clock and the
first attacks of three repetitions hit a link with no video: bug #50, fixed.)
**Expect** (24 Oct, one run): 11/11 mitigated, 0 false alarms.

### 4.8 Rekey under load (X25, about 5 min)
```
py experiments\rekey_load.py --external-sender 192.168.2.99 --board-max-mode E5 --set keys.master=%KEY% --out sim_out\runs\board_rekey_load
```
Paste the printed board command as in 4.7.

### 4.9 Tamper button with debounce (X13)
On the board, set **SW1 up** and **SW0 down**, and Ctrl+C any sender still running. LD0 shows SW1 only
while the tamper image is loaded, so it stays dark until the board command below has started. Laptop window:
```
py experiments\hw_tamper.py --external-sender 192.168.2.99 --trigger manual --set keys.master=%KEY% --out sim_out\runs\hw_tamper_journal
```
Paste the printed board command. Once it has loaded the tamper image, **LD0 must be on**; if it is off,
flip SW1. At each beep, give BTN0 **one** tap. The debounce ignores the contact
bounce for about 10 ms after a press, so every shot must now give exactly one rejected frame. On 24 Oct,
without the debounce, 9 of 25 shots gave 2 frames. It does not merge deliberate presses: two taps are
two shots.

### 4.10 Optional
* **X23 Wi-Fi:** connect the laptop to a Wi-Fi router and the board to the same router by cable. Then run
  4.7 once with the board's new address. Note the RSSI (`netsh wlan show interfaces`, "Signal").
* **X1 power:** only with a USB power meter. Read it while 4.1 runs with `--timing-frames 600`, and note
  idle and encoding power next to the run. Without a meter, the paper keeps the Vivado estimate and says so.
* **X22 several cameras** has no board mode. It stays a simulation result.

---

## 5. Save the results to git (laptop window)

### 5.1 Board results
```
py software\scripts\pull_board_results.py --remote /home/xilinx/fpga_journal
py software\scripts\save_board_day.py --name journal_<date>
git add results/board/journal_<date>
git commit -m "Journal board day <date>: first_contact (pipelined), HD, YUYV, webcam, ARM, repeats"
git pull --rebase origin journal-version
git push origin journal-version
```
Use a date like `15nov`. `save_board_day` also copies the laptop's runs in `sim_out\runs` whose names
start with `board_` or `hw_tamper` (4.7–4.9 use such names, so keep them). It stops if a
file holds your key: delete that line and run it again. Write the webcam latency photos' times and any
power readings into `results/board/journal_<date>/README.md` with the date, the bitstream and the clock.

### 5.2 Software results from your teammates (Kaggle `journal_results.zip`)
1. Unzip it into `sim_out\` (each experiment keeps its own folder: `sim_out\privacy_metrics\`,
   `sim_out\size_overhead\`, ...).
2. Copy each finished folder unchanged into `results\security\journal\` or `results\simulation\journal\`.
   Use `security` for privacy, learned attacker, SVE-Bench, faults and sizes. Use `simulation` for repeats,
   rekey, multi-camera and stream protection.
3. Add a `README.md` there that names the run: Kaggle version, commit, date and `QUICK = False`. Never edit
   a number by hand.
4. `git add results` → commit → `git push origin journal-version`.

## 6. Shut down
1. Board window: `shutdown -h now`. Wait until the LEDs stop blinking, then switch the board off.
2. Laptop: set the Ethernet IP assignment back to **Automatic**.

## Problems seen before, and the fix

| You see | Cause and fix |
|---|---|
| `ModuleNotFoundError: system` or old behaviour on the board | `export PYTHONPATH=$PWD/software` missing, or the command was run in the old `/home/xilinx/fpga` (3.2, 3.3) |
| `width and height must be multiples of 16` | Use 1920x1088, not 1920x1080 (4.4) |
| `FCLK0 came up at 62.5 MHz ... setting it to ...` | Normal: the driver fixes the clock (bug #44) |
| `DMA ... not finished after 2 s` on the HD or YUYV image | Add `--fclk 100`. If it still fails, send the printed STATUS / MM2S_SR / S2MM_SR line |
| `Same bytes: NO` in a pipelined row | The pipelined driver differs from the one-by-one driver on this board. Do not use the pipelined numbers; send the output |
| `The system cannot find the file specified` | `<KEY>` typed literally. Use `%KEY%` / `$KEY` (3.5) |
| `kex: no answer from the receiver` | The board started more than 2 min after the laptop. Ctrl+C both, start the laptop, then the board |
| Latency 0 ms, negative or huge | Board clock drifted. Run 3.4 again right before the run |
| Tamper run: 0 of 25 detected | SW1 is the wrong way round (LD0 off) |
| LD0 off before the tamper run | Normal until the board command has loaded the tamper image (4.9) |
