# paper/data/benchmark: SVE-Bench results

| File | Produced by | Where it ran |
|---|---|---|
| `benchmark_suite/<source>.json`, `.md` | `experiments/benchmark_suite.py` via `future_work/kaggle/kaggle_runs.py (JOB = "benchmark")`, branch `e5-hardware` (`run_log.json`: 4.1 min, every step PASS) | Kaggle (results received 18 Oct 2026) |

Nine sources at 320x240: `synthetic`, five private clips (`17735`, `avengers`, `challenge`, `denzel`,
`jailer`; numbers only, see `future_work/clips_manifest.md`), Sintel trailer and Tears of Steel (CC BY 3.0)
and the Kodak set. 19 scored frames per video, 23 for Kodak (175 in total).

Every scheme (plain, E1-E5, Van Droogenbroeck, Kishore, Auer, Hirose RI=1/4) is scored by the same four
attacks (A1 decode, A2 replacement, A3 NZCA, A4 cross-frame); values are edge correlations with the
original luma. `paper/make_assets.py :: benchmark()` pools them into `paper/tables/tab_bench.tex` and the
`\Bench*` macros. Nothing here is typed by hand: the files are the unzipped `benchmark_results.zip`.
