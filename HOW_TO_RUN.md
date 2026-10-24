# How to run the project

From a fresh clone to the full system: the simulation on one laptop, then the PYNQ-Z2 board as the camera
with the laptop as receiver, dashboard and attacker. Commands are for a Windows Command Prompt (`py`);
on Linux or WSL use `python` and `/` instead of `\`.

| Machine | Runs | Needs |
|---|---|---|
| **Laptop** (receiver) | dashboard, receiver, attacker, experiments, tests, papers | Python 3.10+, `requirements.txt`, gcc (recommended) |
| **PYNQ-Z2** (sender) | encoder + Ascon + tag in the FPGA; headers, E5 shuffle, network and key exchange on its ARM | PYNQ 3.1 SD image, the `.bit` + `.hwh` files |
| **Vivado PC** (only to rebuild the FPGA images) | `vivado/run_vivado_day.py` | Vivado 2026.1, a Windows checkout without spaces in the path |

Each step says what you should see. Steps 1–3 need no board.

---

## 1. Set up the laptop (once)

```
git clone https://github.com/vij-ship-it/FPGA-Video-Encryption-.git
cd FPGA-Video-Encryption-
git checkout claude/project-thread-yxa59j
py -m venv .venv
.venv\Scripts\activate
py -m pip install -r requirements.txt
py scripts\check_setup.py
```

(The team repository is `bnsama29-cloud/FPGA-Video-Encryption-`, branch `main`; it gets the same files
through a pull request.)

`check_setup` prints one line per check, each with its fix. `FAIL` must be fixed; `WARN` means one part is
slower or missing:

* **C compiler.** Without gcc the receiver decrypts in Python, which falls behind the board's E5 frames at
  10 fps. On Windows:
  `choco install mingw` (admin), then open a new window. On Linux: `sudo apt install gcc`.
* **Icarus Verilog 12.** Only for the RTL tests. Use WSL Ubuntu 24.04 (`sudo apt install iverilog`).
* **Board images.** See step 4.

Every new window needs `.venv\Scripts\activate` first.

## 2. Run the whole system with no hardware

```
py -m link.run_all
```

Open **http://localhost:8000**. Sender, network and attacker, receiver and dashboard all run on this laptop;
the encoder is the golden model (the same bytes as the FPGA). On the dashboard:

* the four tiles are the camera, the wire (what an eavesdropper sees), the receiver, and the attacker's best
  picture without the key;
* "Attack the link" has 11 attacks: 8 on the video (flip a bit, downgrade, splice, inject, replay, hold back,
  jam, flood) and 3 on the feedback (silence, forge, replay). Each one makes the receiver reject frames or
  raise an alarm, and the defence moves the level up to E5, then back to E2 once it is calm;
* "Protection" fixes a level (E0–E5) or leaves it automatic. The wire tile shows what each level hides.

Options (add any of them; all settings: `link/config.py`):

| What | Add |
|---|---|
| your own video or a webcam | `--set sender.source=clip.mp4` or `--set sender.source=webcam:0` |
| a key nobody else has | `py scripts\demo_key.py` once, then `--set keys.master=<KEY>` (on both ends) |
| post-quantum session key (ML-KEM-768 + X25519) | `--pq-kex` |
| other devices on the LAN (phone, second laptop) | `--set dashboard.bind_host=0.0.0.0`, then open `http://<laptop IP>:8000` |
| VLC | Media → Open Network Stream → `http://localhost:8000/stream/wire.mjpg` (scrambled: VLC has no key) |

For the LAN, run from Windows, not WSL (WSL's network is private), and allow Python on private networks.
Full LAN guide: `docs/DASHBOARD_LAN_DEMO.md`.

**Scripted attacks and results.**

```
py experiments\scenario.py --scenario experiments\scenarios\full_suite.json
```

This runs the 11 attacks. Each run writes a summary to `sim_out\runs\`; the paper's result is 11/11
mitigated with 0 false alarms. The other experiments are in `experiments\` (GUIDE.md §2).

## 3. Tests and the board-day rehearsal

```
make test
py scripts\rehearse_board_day.py --quick
```

* **`make test`** runs the full regression (golden model, system, every RTL block in Icarus). Run it in
  WSL or Linux; on Windows without make, use `py -m pytest tests`.
* **`rehearse_board_day.py`** runs every board-day command against an emulated board and prints PASS or FAIL
  per check. `--quick` skips the two 5-minute runs and the full test suite; without it the run takes about
  20 minutes. Step 8 fails until the board images are on the laptop (step 4). Windows: `set CC=gcc` first.

## 4. Get the FPGA images (bitstreams)

The board needs each `.bit` with its `.hwh` in `future_work\board\overlay\`. They are built in Vivado and
were not in git before. **Once**, on the PC that has them (run 12 + the run-13 tamper image):

```
git checkout claude/project-thread-yxa59j
git pull
py scripts\publish_bitstreams.py
git commit -m "Board images: run 12 + tamper image of run 13"
git push
```

The script checks that every image has its `.hwh` and the recorded run-12 and run-13 hashes. It then writes
`overlay\MANIFEST.md` and stages only the images, about 4 MB each. After that, every `git pull` brings them.

To check a copy, run `py scripts\publish_bitstreams.py --check` (also works on the board).

To rebuild them, run this on the Vivado PC (1–1.5 h, guide `docs/VIVADO_ONE_DAY.md`):
`py vivado\run_vivado_day.py --steps bd_lanes bd_lanes4 bd_tamper parse --jobs 2`.

| Image | Use |
|---|---|
| `secure_jpeg_lanes.bit` | 2 lanes + E5, 100 MHz: the main demo image |
| `secure_jpeg_lanes4.bit` | 4 lanes + E5, 125 MHz: the speed numbers (use `--fclk 100` if 125 fails) |
| `secure_jpeg_lanes_tamper.bit` | 2 lanes + tamper injector (SW0, SW1, BTN0) + level buttons (BTN1–BTN3) |
| `secure_jpeg.bit`, `..._lanes4hd.bit`, `..._lanes4yuyv.bit` | single pipeline; 1080p lines; YUYV camera input |

## 5. Run on the board

Follow **`docs/BOARD_DAY.html`** (open it in a browser and tick the steps). The short version:

**Board setup**

1. Write the PYNQ-Z2 3.1.1 image to the SD card. Set the jumpers Boot → SD and Power → USB, then connect
   Ethernet to a router or straight to the laptop. With a direct cable the board is 192.168.2.99; set the
   laptop's Ethernet adapter to 192.168.2.1.
2. Copy the project to the board:
   ```
   ssh xilinx@<BOARD> "mkdir -p /home/xilinx/fpga"
   scp -r model link future_work configs experiments scripts requirements.txt xilinx@<BOARD>:/home/xilinx/fpga/
   ```
   The password is `xilinx`.
3. On the board:
   ```
   sudo -i
   source /etc/profile.d/pynq_venv.sh
   cd /home/xilinx/fpga
   python3 scripts/check_setup.py --board
   ```

**Board alone**

4. Bit-exact check and speed (A1, A2):
   ```
   python3 -m future_work.board.first_contact --bitfile future_work/board/overlay/secure_jpeg_lanes4.bit --sizes 320x240 640x480 --frames 10 --timing-frames 50 --zero-copy --out sim_out/board/lanes4_final
   ```
   You should see `Bit-exact … **yes**`. Every level E0–E5 is byte-identical with the golden model running
   on the board.
5. The same encoder in C on the ARM (A3):
   ```
   CFLAGS="-mcpu=cortex-a9 -mfpu=neon" python3 -m future_work.arm.arm_baseline --sizes 320x240 640x480 --frames 30 --pl-json sim_out/board/lanes4_final/first_contact.json --out sim_out/board/arm_final
   ```

**Board with the laptop**

6. The complete system (A5): the board is the camera, the laptop is the receiver and dashboard. Start the
   laptop first:
   ```
   py -m link.run_all --no-sender --pq-kex --set keys.master=<KEY> --set link.bind_host=0.0.0.0 --set link.sender_host=<BOARD> --set dashboard.bind_host=0.0.0.0
   ```
   Then the board:
   ```
   python3 -m future_work.board.board_sender --bitfile future_work/board/overlay/secure_jpeg_lanes.bit --pq-kex --set keys.master=<KEY> --set link.host=<LAPTOP> --set link.bind_host=0.0.0.0 --set link.pad=runmax
   ```
   Both print `kex: session key established`. The dashboard plays the board's stream with 0 rejected
   frames, and the attack buttons work as in step 2.
7. The attack suite on hardware (A6). On the laptop:
   ```
   py experiments\scenario.py --scenario experiments\scenarios\full_suite.json --external-sender <BOARD> --board-max-mode E5 --pq-kex --set keys.master=<KEY> --out sim_out\runs\board_full_suite_rep1
   ```
   Then run the board command it prints. To put the attacker on a second laptop, add `--attacker <IP>`.
8. Tampering inside the FPGA: run `py experiments\hw_tamper.py --external-sender <BOARD> --trigger manual ...`
   with the tamper image, set SW1 up, and press BTN0. Each press should cost exactly one rejected frame.
   See BOARD_DAY phase 12.

**Windows firewall** (admin cmd, once on each laptop):
`netsh advfirewall firewall add rule name="secure-link" dir=in action=allow protocol=UDP localport=47000-47010,47200-47215`

## 6. Power and energy per frame (the USB meter is optional)

Without a meter, nothing extra runs on the board. Copy the results back (BOARD_DAY phase 13), then on the
laptop:

```
py -m future_work.baselines.energy_table future_work\baselines\power_template.csv --no-meter --fpga-json sim_out\board\lanes4_final\first_contact.json --arm-json sim_out\board\arm_final\arm_baseline.json
```

Energy per frame = power ÷ fps:

* the fps are always measured on the board;
* without a meter, the power is Vivado's post-route estimate of the same bitstream (about 2.2 W for the
  4-lane image). Each row names its power source, so report these as estimates;
* the ARM rows show fps only, because Vivado has no model of the ARM's load.

With a meter, put it between the USB supply and the board. Write the 30-second averages into the `power_w`
and `idle_power_w` columns of `power_template.csv`, then run the same command without `--no-meter`.
BOARD_DAY phase 9 has the 2000-frame runs to measure under.

## 7. Results into the papers

Send `board_results.zip` (BOARD_DAY phase 13) to Claude, or copy the folders into `paper/data/board/`.
Then rebuild:

```
py paper\make_assets.py
make -C paper
```

`make -C paper` needs LaTeX; otherwise upload `paper/` to Overleaf. The conference paper must stay at
6 pages.

## When something goes wrong

| Symptom | Fix |
|---|---|
| `check_setup` FAIL on packages | `.venv\Scripts\activate`, then `py -m pip install -r requirements.txt` |
| dashboard does not open | another `run_all` is still running (Ctrl+C it); `check_setup` lists busy ports |
| every frame **rejected (tag)** | the two ends have different keys: the same `--set keys.master=` on both |
| receiver falls behind at E5 | no C compiler: install gcc (step 1), restart `run_all` |
| phone or second laptop cannot connect | `--set dashboard.bind_host=0.0.0.0`, run from Windows not WSL, firewall rule above |
| `Overlay(...)` fails on the board | the `.bit` and `.hwh` must be side by side with the same name: `publish_bitstreams.py --check` |
| `ModuleNotFoundError: pynq` | `sudo -i` and `source /etc/profile.d/pynq_venv.sh` first |
| anything else on the board | BOARD_DAY.html, "When something goes wrong"; send Claude the first error line and the command |

More detail: `docs/RUNBOOK.md` (every program, where it runs, the order) and `GUIDE.md` (status and the
remaining tasks).
