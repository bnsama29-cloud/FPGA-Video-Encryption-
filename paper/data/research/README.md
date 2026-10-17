# paper/data/research: research suite R1-R7 on the real clips

Where these files came from (nothing here is typed by hand):

| Folder | Produced by | Where it ran |
|---|---|---|
| `stall_profile/` (R1) | `experiments/stall_profile.py` (RTL in Icarus 12, cycle-accurate), incl. a 640x480 frame | Kaggle, CPU, 15 Oct 2026 (`run_log.json`, 28.7 min, 47/47 steps PASS) |
| `parallel_lanes/` (R2) | `experiments/parallel_lanes.py` | same run |
| `change_driven/` (R4) | `experiments/change_driven.py` (+ thresholds 2 and 8 on the open sources) | same run |
| `block_transform/` (R6) | `experiments/block_transform.py` | same run |
| `run_log_rerun.json` | 1st **rerun** with `ONLY = ["r3_rate", "r7_size"]`, after the fixes of bugs #22-#24 (14.9 min, 14/14 PASS). Tears of Steel's PI and FF+PI rows show the limit cycle of bug #25 (fixed after this run) | Kaggle, CPU, 15 Oct 2026 |
| `rate_control/`, `size_leak/`, `run_log_rerun3.json` | **3rd rerun**, `ONLY = ["r3_rate", "r7_size"]`, after bug #26 (19.0 min, 19/19 PASS, 8 sources) | Kaggle, CPU, 15 Oct 2026 |
| `chosen_plaintext/` (R8), `run_log_rerun2.json` | **2nd rerun**, `ONLY = ["r3_rate", "r7_size", "r8_cpa"]`, after bug #25 (19.3 min, 27/27 PASS), 8 sources incl. `17735` (user clip, not labelled yet, so `make_assets.py` skips it). PI/FF+PI rows predate the fix of bug #26; Tears of Steel's R3 rows show that oscillation and are left out of the paper | Kaggle, CPU, 15 Oct 2026 |
| `rate_control_before_fix/` (R3) | **removed 17 Oct 2026**: the run before the fixes of bugs #22 and #23, in git history at commit 327e237 | |

Known limits of this snapshot (docs/TESTING.md §8):

* `size_leak/` and `rate_control/` are from the 3rd rerun, after every fix (bugs #22-#26).
* Tears of Steel's R3 rows include the transient after a cut from black (the controller raises quality
  on black frames that cannot reach the budget); all controllers settle within +-5 % afterwards.

Sources: `synthetic` (fixed-camera corridor scene of `link/sources.py`), four copyrighted film clips
identified by hash in `future_work/clips_manifest.md` (numbers only, never pictures), Sintel trailer and
Tears of Steel (Blender Foundation, CC BY 3.0; the R3 plots are only from these and the synthetic scene).
The film clips contain shot cuts and camera motion; the fixed-camera case of R4 and R7 is represented
only by the synthetic scene until a static-camera clip is added.
