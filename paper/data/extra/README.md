# paper/data/extra: open-data, standard-metric, restart-interval and stronger learned-attack results

Where these files came from (nothing here is typed by hand):

| Folder | Produced by | Where it ran |
|---|---|---|
| `<source>/mode_tradeoff.json`, `<source>/jigsaw/`, `<source>/standard_metrics/` | `future_work/kaggle/kaggle_runs.py (JOB = "remaining")` (`run_log.json`, 74.5 min, every step PASS) | Kaggle, GPU T4, 14 Oct 2026 |
| `sintel_trailer/grid/`, `tearsofsteel/grid/` | same run, `future_work/figures/visual_security_grid.py` | Kaggle |
| `scenario_open/` | same run: the 11-attack suite with Tears of Steel as the video source | Kaggle |
| `learned_L1_open/`, `learned_L2_all/` | **rerun** (`kaggle_runs.py (JOB = "remaining")`, `RERUN = True`, 56 min, `run_log_rerun.json`) with the no-ciphertext control and the bootstrap interval | Kaggle T4, 14 Oct |
| `learned_*_v1/` | **removed 17 Oct 2026** (superseded first run without the control; in git history at commit 327e237) | |
| `synthetic|avengers|challenge|denzel|jailer/restart_interval/` | `experiments/restart_interval.py` **after the fix of bug #16** (same frames and arguments as the Kaggle run) | development VM |
| `kodak|sintel_trailer|tearsofsteel/restart_interval/<name>.json` and pictures, `sintel_trailer|tearsofsteel/grid/` (paper size) | the rerun, after the fix of bug #16 | Kaggle T4, 14 Oct |
| `<source>/restart_interval/*.prefix16.*.txt` | **removed 17 Oct 2026** (first run before the fix of bug #16; in git history at commit 327e237) | |

Sources: `synthetic` (the model's synthetic scene), four copyrighted clips identified by hash in
`future_work/clips_manifest.md` (numbers only, never pictures), and three openly licensed sources:
Sintel trailer and Tears of Steel (Blender Foundation, CC BY 3.0) and the Kodak image set. Pictures in
this folder come only from the synthetic scene and the open sources.

The private-clip numbers of `mode_tradeoff.json` and `jigsaw.json` are identical to the earlier
Kaggle run in `../simulation/real/` (checked to 1e-15): the pipeline is deterministic across machines.

`paper_tables_kaggle.md` is the table file the Kaggle run wrote; `paper/make_assets.py` reads the
JSON files directly.
