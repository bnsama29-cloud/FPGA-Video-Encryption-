# paper/data/research: research suite R1-R7 on the real clips

Where these files came from (nothing here is typed by hand):

| Folder | Produced by | Where it ran |
|---|---|---|
| `stall_profile/` (R1) | `experiments/stall_profile.py` (RTL in Icarus 12, cycle-accurate), incl. a 640x480 frame | Kaggle, CPU, 15 Oct 2026 (`run_log.json`, 28.7 min, 47/47 steps PASS) |
| `parallel_lanes/` (R2) | `experiments/parallel_lanes.py` | same run |
| `change_driven/` (R4) | `experiments/change_driven.py` (+ thresholds 2 and 8 on the open sources) | same run |
| `block_transform/` (R6) | `experiments/block_transform.py` | same run |
| `rate_control/` (R3), `size_leak/` (R7), `run_log_rerun.json` | **rerun** with `ONLY = ["r3_rate", "r7_size"]`, after the fixes of bugs #22-#24 (14.9 min, 14/14 PASS). Tears of Steel's PI and FF+PI rows show the limit cycle of bug #25 (fixed after this run) | Kaggle, CPU, 15 Oct 2026 |
| `chosen_plaintext/` (R8), `size_leak_vm/` (R7 with the deployable padding rows) | `experiments/chosen_plaintext.py`, `experiments/size_leak.py`, synthetic scene only | development VM, 15 Oct 2026 |
| `rate_control_before_fix/` (R3) | `experiments/rate_control.py` **before** the fixes of bugs #22 and #23 (unreachable set point on clips that open on black; estimator windup in FF+PI). Kept for the record, renamed `.txt` so no script reads them. | first run |

Known limits of this snapshot (docs/TESTING.md §8):

* `size_leak/` and `rate_control/` are from the rerun (after bugs #22-#24). In the first run, the
  synthetic source stamped the wall-clock time (bug #24); the clip numbers were not affected.
* Next rerun (`ONLY = ["r3_rate", "r7_size", "r8_cpa"]`): R3 after bug #25, the deployable padding
  rows of R7 and R8 on every source.

Sources: `synthetic` (fixed-camera corridor scene of `link/sources.py`), four copyrighted film clips
identified by hash in `future_work/clips_manifest.md` (numbers only, never pictures), Sintel trailer and
Tears of Steel (Blender Foundation, CC BY 3.0; the R3 plots are only from these and the synthetic scene).
The film clips contain shot cuts and camera motion; the fixed-camera case of R4 and R7 is represented
only by the synthetic scene until a static-camera clip is added.
