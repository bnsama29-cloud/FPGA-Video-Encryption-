# paper/data/research: research suite R1-R7 on the real clips

Where these files came from (nothing here is typed by hand):

| Folder | Produced by | Where it ran |
|---|---|---|
| `stall_profile/` (R1) | `experiments/stall_profile.py` (RTL in Icarus 12, cycle-accurate), incl. a 640x480 frame | Kaggle, CPU, 15 Oct 2026 (`run_log.json`, 28.7 min, 47/47 steps PASS) |
| `parallel_lanes/` (R2) | `experiments/parallel_lanes.py` | same run |
| `change_driven/` (R4) | `experiments/change_driven.py` (+ thresholds 2 and 8 on the open sources) | same run |
| `block_transform/` (R6) | `experiments/block_transform.py` | same run |
| `size_leak/` (R7) | `experiments/size_leak.py` | same run |
| `rate_control_before_fix/` (R3) | `experiments/rate_control.py` **before** the fixes of bugs #22 and #23 (unreachable set point on clips that open on black; estimator windup in FF+PI). Kept for the record, renamed `.txt` so no script reads them. | same run |

Known limits of this snapshot (docs/TESTING.md §8):

* The `E2 FF+PI + pad-105%` row of every `size_leak/*.json` used the FF+PI controller before the fix of
  bug #23. All other R7 rows (E0-E5, padding) do not use the controller and are valid.
* The `synthetic` source stamped the wall-clock time before the fix of bug #24, so its byte counts
  differ slightly from a rerun (it matters only for the 1 KB padding row). The clip numbers are not
  affected.
* A rerun of R3 and R7 (`kaggle_research.py` with `ONLY = ["r3_rate", "r7_size"]`) replaces
  `rate_control_before_fix/` by `rate_control/` and refreshes `size_leak/`.

Sources: `synthetic` (fixed-camera corridor scene of `link/sources.py`), four copyrighted film clips
identified by hash in `future_work/clips_manifest.md` (numbers only, never pictures), Sintel trailer and
Tears of Steel (Blender Foundation, CC BY 3.0; the R3 plots are only from these and the synthetic scene).
The film clips contain shot cuts and camera motion; the fixed-camera case of R4 and R7 is represented
only by the synthetic scene until a static-camera clip is added.
