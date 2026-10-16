# paper/data/final: the last Kaggle run (16 Oct 2026)

Produced by `future_work/kaggle/kaggle_final.py` (Kaggle, GPU T4, 180.9 min, 32/32 steps PASS,
`run_log.json`), branch `kaggle-final`. Nothing here is typed by hand.

| Folder / file | Task | Script |
|---|---|---|
| `<source>/mode_tradeoff.json` | B24: leakage per level, 60 frames per video source (Sintel 25, Kodak 24), 95 % bootstrap intervals | `experiments/measure_mode_tradeoff.py` |
| `<source>/jigsaw_mst/` | B9: MST jigsaw solver (Gallagher-style MGC) on E5, 8 frames | `future_work/attacks/jigsaw_attack.py --solver mst` |
| `<source>/recognition/` | B23: Faster R-CNN person detection in the attacker's pictures, 40 frames (Kodak 24) | `experiments/recognition.py` |
| `learned_L1_open/`, `learned_L2_all/` | B25: P3 and P4 again, with the frame-statistics controls. **P4's split changed**: with the new clip `17735` the private clips are 5, so P4 is 4 sources -> 3 (17735, Talk B, Trailer B, Sintel -> Trailer A, Talk A, Tears of Steel), not 3 -> 3 as in `../extra/` | `experiments/learned_attack.py` |
| `learned_P5_corpus_gan/` | B17: P5, trained on Elephants Dream + Tears of Steel (CC BY) with a PatchGAN loss (weight 0.01), tested on Sintel and the five private clips | `experiments/learned_attack.py --adv 0.01` |
| `jigsaw_gate.json/.md` | B9 gate: greedy vs MST on unencrypted tiles of six scikit-image photos | `future_work/attacks/jigsaw_gate.py` (development VM) |

Sources: as in `../research/README.md`, plus `17735` = **Phone A** (handheld portrait phone video of an
outdoor crowd, identifiable people: numbers only; hash in `future_work/clips_manifest.md`). Big Buck
Bunny was not found in Blender's directory listing, so P5's corpus is Elephants Dream and Tears of Steel.
`learned_L1_open/examples_*.png` show frames of the open Tears of Steel test clip only.
