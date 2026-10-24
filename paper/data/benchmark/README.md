# paper/data/benchmark: SVE-Bench results

| File | Produced by | Where it ran |
|---|---|---|
| `benchmark_suite/<source>.json`, `.md` | `experiments/benchmark_suite.py` (method v2, `docs/BENCHMARK_METHOD.md`) via `system/kaggle/kaggle_runs.py (JOB = "benchmark")`, branch `claude/project-thread-yxa59j` at commit 477585a (`run_log.json`: 43.9 min, every step PASS) | Kaggle (results received 18 Oct 2026, 10:01) |
| `benchmark_suite/kodak_q50.*`, `kodak_q90.*` | same run, Kodak at quality 50 and 90 (`kodak.*` is quality 75) | Kaggle |
| `standard_metrics/<source>.json`, `.md` | `experiments/standard_metrics.py` in the same run, including E5's hardware form (`E5 (v3, hw)`) | Kaggle |

Nine sources: `synthetic`, five private clips (`17735`, `avengers`, `challenge`, `denzel`, `jailer`; numbers
only, see `system/clips_manifest.md`), Sintel trailer and Tears of Steel (CC BY 3.0) at 320x240, and the
Kodak set at 768x512. 19 scored frames per video, 23 for Kodak (175 in total); the attacker's known frame
(the loaded frame with the most detail) is not scored and is named in each file's `meta.known_frame`.

Every scheme (plain, E1-E5, Van Droogenbroeck, Kishore, Auer, Hirose RI=1/4) is scored by the same four
attacks (A1 decode, A2 replacement, A3 NZCA, A4 known plaintext); values are edge correlations with the
original luma, with 95 % bootstrap intervals. `paper/make_assets.py :: benchmark()` pools the quality-75 files
into `paper/tables/tab_bench.tex`, `tab_bench_metrics.tex` and the `\Bench*` macros (the `_q50`/`_q90` files
are not pooled). `tab_stdmetrics.tex` still reads the 14 Oct files in `../extra/<source>/standard_metrics/`.
Nothing here is typed by hand: the files are the unzipped `benchmark_results.zip`. The first run (old A4,
known frame 0) is in git history at commit 3588feb.
