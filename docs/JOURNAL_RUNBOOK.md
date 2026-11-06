# Journal runbook: the software phase, then the board phase, then the paper phase

This branch (`journal-version`) adds the programs for the journal experiments. It leaves `main` alone, so the ICCE submission is not affected. The phases run in a fixed order:

1. **Software phase.** Run everything that needs no board: laptop, Vivado and simulation. Check that the results convince before moving on.
2. **Board phase.** Run the same scripts with the PYNQ-Z2 as the camera.
3. **Paper phase.** Copy the outputs into the manuscript's data snapshot. The manuscript stays outside this repository.

Every number comes from a script that writes to `sim_out/`. Copy a finished run into `results/` unchanged (see `results/README.md`). The references behind each experiment are listed in `docs/LITERATURE.md`.

Run the setup once per terminal:
```
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e . && pip install lpips yowasp-yosys     # lpips: LPIPS column; yowasp-yosys: X12 without a yosys install
```

## 1. Software phase (laptop, about one day of machine time)

| X | Experiment | Command | Output |
|---|---|---|---|
| X6 | Standard test sequences | `python software/scripts/get_xiph.py` | `clips/xiph/*.mp4`, `manifest.md` (SHA-256 of each input) |
| X6 | Rerun the main metrics on them | `python experiments/standard_metrics.py --video clips/xiph/foreman_cif.mp4 --size 352x288 --frames 24 --stride 12 --name foreman` (repeat for each sequence) | `sim_out/standard_metrics/` |
| X7 | Size overhead per mode, with padding cost | `python experiments/size_overhead.py --source clips/xiph/foreman_cif.mp4 --size 352x288 --frames 50 --quality 50 75 90` | `sim_out/size_overhead/` |
| X17 | Privacy metrics: SSIM, LPIPS, edges, face recall | `python experiments/privacy_metrics.py --video clips/xiph/foreman_cif.mp4 --size 352x288 --frames 60 --stride 5 --face-model face_detection_yunet_2023mar.onnx --name foreman` (also akiyo, mother_daughter, hall_monitor) | `sim_out/privacy_metrics/` |
| X18 | Stronger learned attacker (GPU) | `python experiments/learned_attack.py --train-source clips/a.mp4,clips/b.mp4,clips/c.mp4 --test-source clips/xiph/foreman_cif.mp4 --frames 6000` | `sim_out/learned_attack/` |
| X19 | Benchmark against EtC and Tang | `python experiments/benchmark_suite.py` (EtC and Tang are now in the suite) | `sim_out/benchmark_suite/` |
| X16 | Faults before and after the tag | `python experiments/fault_pre_tag.py --faults 500` | `sim_out/fault_pre_tag/` |
| X20 | Decoders and containers (AVI, MKV, MOV) | `python -m system.figures.format_compliance` | `software/system/results/format_compliance.md` |
| X24 | Cost of SRTP, DTLS, ChaCha20 and Ascon next to ours | `python -m system.baselines.stream_protection` | `sim_out/stream_protection/` |
| X25 | Rekey under load | `python experiments/rekey_load.py` | `sim_out/rekey_load/sim/` |
| X22 | Several cameras on one receiver | `python experiments/multi_camera.py --cameras 1 2 4 8` | `sim_out/multi_camera/` |
| X3 | Repeated attack suite, 95 % intervals | `python experiments/repeat_runs.py --reps 5` | `sim_out/repeat_runs/full_suite/` |
| X12 | ASIC area (sky130, Nangate 45 nm) | `python experiments/asic_estimate.py` | `sim_out/asic_estimate/` |
| X8–X10, X13 | Everything in Vivado, one command (laptop, ~4–6 h): other FPGAs, clock and memory sweep, power, tamper bitstream | `python hardware/vivado/run_vivado_day.py --steps xsim ooc lanes power parts bd_tamper parse --periods 8.0 7.0 6.667 --maxw 9 10 --parallel 2` | `vivado_results_<date>.zip` |
| X13 | Tamper debounce (simulation) | `make one T=hardware/tb/test_axis_tamper.py` | — |

**On Kaggle in one run:** everything above except Vivado is `JOB = "journal"` in `software/system/kaggle/kaggle_runs.py` (GPU T4, ~6–7 h, `journal_results.zip`).

Get the YuNet face model (X17) once from `github.com/opencv/opencv_zoo`, at `models/face_detection_yunet/face_detection_yunet_2023mar.onnx`. OpenCV 5 no longer ships the Haar cascades.

**Gate before the board phase.** The software phase passes when all of the following hold:
- `make test` passes.
- E2 or higher hides faces in X17.
- The overhead in X7 stays within the claims.
- X19 places the scheme sensibly against EtC and Tang.

If any of these fails, fix it here first. A board day spent on a design that the simulation already rejects is wasted.

**X9 (142 MHz).** The quantiser change waits for the Vivado reports of the 7.0 ns run. Pipeline only the path those reports name, then check that the model and RTL equivalence tests still pass.

## 2. Board phase (PYNQ-Z2)

| X | Experiment | Command |
|---|---|---|
| X1 | Power from a USB meter, idle against encoding | read the meter during `first_contact.py --timing-frames 600`, and log the readings next to the run |
| X2 | 1080p and YUYV overlays | `python -m system.board.first_contact --sizes 1920x1080` with the `lanes4hd` and `lanes4yuyv` bitstreams |
| X3 | Repeats with the board as the camera | `python experiments/repeat_runs.py --reps 5 --external-sender <BOARD IP>` |
| X4 | ARM against the FPGA, with zero-copy | `first_contact.py --zero-copy`, then `sudo -E python3 -m system.arm.arm_baseline --pl-json sim_out/board/first_contact.json` |
| X5 | Webcam source | `python -m system.board.first_contact --source webcam:0` and `board_sender.py ... --set sender.source=webcam:0` |
| X13 | Tamper button with debounce | build the `bd_tamper` overlay again (LOCK_BITS defaults to 20, about 10 ms), then press BTN0 quickly several times: one press should tamper one frame |
| X22, X25 | Several cameras and rekey under load, board as sender | `multi_camera.py` / `rekey_load.py --external-sender <BOARD IP>` |
| X23 | Wi-Fi link | the same scenarios with the receiver on Wi-Fi; record the RSSI |

## 3. Paper phase

1. Copy each finished `sim_out/<exp>/` into `results/<board|hardware|security|simulation>/`, and name the run in that folder's README.
2. Build the manuscript's data snapshot from `results/`. Keep the manuscript outside this repository.
3. Cite only entries in `docs/LITERATURE.md` that were checked. Mark anything unchecked as `\TODO{}`.
