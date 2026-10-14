# paper/data/extra: open-data, standard-metric, restart-interval and stronger learned-attack results

Where these files came from (nothing here is typed by hand):

| Folder | Produced by | Where it ran |
|---|---|---|
| `<source>/mode_tradeoff.json`, `<source>/jigsaw/`, `<source>/standard_metrics/` | `future_work/kaggle/kaggle_remaining.py` (`run_log.json`, 74.5 min, every step PASS) | Kaggle, GPU T4, 14 Oct 2026 |
| `sintel_trailer/grid/`, `tearsofsteel/grid/` | same run, `future_work/figures/visual_security_grid.py` | Kaggle |
| `scenario_open/` | same run: the 11-attack suite with Tears of Steel as the video source | Kaggle |
| `learned_L1_open/`, `learned_L2_all/` | same run, `experiments/learned_attack.py` (before the no-ciphertext control was added) | Kaggle T4 |
| `synthetic|avengers|challenge|denzel|jailer/restart_interval/` | `experiments/restart_interval.py` **after the fix of bug #16** (same frames and arguments as the Kaggle run) | development VM |
| `kodak|sintel_trailer|tearsofsteel/restart_interval/*.prefix16.*.txt` | the Kaggle run, **before** the fix of bug #16 (overhead measured against a file with the APP11 segment; no raster solver). Kept for the record, renamed so no script reads them. Rerun with `kaggle_remaining.py` (GUIDE.md B20). | Kaggle |

Sources: `synthetic` (the model's synthetic scene), four copyrighted clips identified by hash in
`future_work/clips_manifest.md` (numbers only, never pictures), and three openly licensed sources:
Sintel trailer and Tears of Steel (Blender Foundation, CC BY 3.0) and the Kodak image set. Pictures in
this folder come only from the synthetic scene and the open sources.

The private-clip numbers of `mode_tradeoff.json` and `jigsaw.json` are identical to the earlier
Kaggle run in `../simulation/real/` (checked to 1e-15): the pipeline is deterministic across machines.

`paper_tables_kaggle.md` is the table file the Kaggle run wrote; `paper/make_assets.py` reads the
JSON files directly.
