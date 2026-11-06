# Paper 1 experiment code that paper 2 (event-camera encryption) can reuse

Working notes, not a result. Read on branch `neuromorphic` from `experiments/privacy_metrics.py`,
`experiments/learned_attack.py`, `experiments/benchmark_suite.py` (structure only), `experiments/repeat_runs.py`,
`software/scripts/get_xiph.py`, `software/system/kaggle/kaggle_runs.py` (journal job, setup part),
`experiments/README.md`, `results/README.md`, `requirements*.txt`, `pyproject.toml`.
Paper 2 experiment ids (N1-N10) are the draft plan's.

## 1. Output convention: every number from a script

- Each script writes to `sim_out/<experiment>/` (git-ignored). The default output folder is a module constant
  `OUT = ROOT / "sim_out" / "<exp>"`, and an `--out` flag overrides it. The files are `<name>.json`, which keeps
  the full data plus a `meta`/`source` block (input, frames, size, quality, CI method), and `<name>.md`, the
  table the paper uses, which the script also prints. `benchmark_suite.py` names sweeps `<name>_q<Q>.json`.
  `repeat_runs.py` also writes `table.csv` and `runs.json`.
- A finished run is copied unchanged into `results/<area>/` (board, hardware, security, simulation), and the
  folder README names the script, commit and machine. `experiments/README.md` maps each script to its result.
  For paper 2, add rows there, or keep a separate `experiments/neuro/README.md` if the scripts live in their
  own folder.
- Header convention: the docstring starts with the question and the usage lines, then gives the method and
  the controls, and ends with "Writes sim_out/...". The `argparse` setup uses `description=__doc__` and
  `RawDescriptionHelpFormatter`. Paths are set with `ROOT = Path(__file__).resolve().parents[1]` and
  `sys.path[:0] = [str(ROOT), str(ROOT / "software")]`.

### 95 % intervals: two helpers, copied by hand (there is no shared module)
- `bootstrap_ci(values, n=2000, seed=0)` is a 95 % percentile bootstrap of the mean. It is defined in
  `experiments/learned_attack.py:142`, `experiments/benchmark_suite.py:613` (returns `[mean, mean]` when there
  are fewer than 2 values) and `experiments/standard_metrics.py:175`. It is used for per-frame metrics
  (SSIM, edge corr.).
- `mean_ci(v)` in `experiments/repeat_runs.py:36` returns (mean, half-width) from a Student t interval, using
  the `T95` table for df 1..29 and 1.96 beyond. It drops None and NaN and returns `(None, None)` for an empty
  list and `(v, None)` for a single value. It is used for repeated runs (time to detect or mitigate). `fmt(m, h)`
  prints `m ± h`.
- Paper 2 plan: put both helpers in one shared module (e.g. `software/neuro/stats.py` or
  `experiments/neuro/common.py`) and do not copy them a fourth time. Use the bootstrap for per-window or
  per-sample metrics and the t interval for repeated runs (N7 active attacks, N10 replay).

## 2. Image-quality and privacy helpers (for E2VID/FireNet reconstructions, N3/N4)

They live in `experiments/privacy_metrics.py` and are also duplicated in `learned_attack.py` and
`benchmark_suite.py`.
- `luma(rgb)` uses BT.601 weights in float64. `learned_attack.py` uses `cv2.cvtColor(..., RGB2GRAY)` instead.
- `ssim(a, b)` is `skimage.metrics.structural_similarity(luma(a), luma(b), data_range=255.0)`.
- `edge_corr(a, b)` is the Pearson correlation of the Sobel gradient magnitudes (`cv2.Sobel` dx, dy,
  `np.hypot`). It returns 0.0 if either picture has no edges.
- `scores(pred, target)` in `learned_attack.py:134` returns `{psnr, ssim, edge_corr}`.
- `lpips_metric()` returns `(a, b) -> LPIPS` (AlexNet, `lpips.LPIPS(net="alex")`), or None when
  `lpips`/`torch` are missing. Inputs are scaled to [-1, 1] as NCHW. **Needs torch: Kaggle only.**
- `face_detector(model)` returns `rgb -> [(x1, y1, x2, y2)]`, or None.
  - With YuNet: `cv2.FaceDetectorYN.create(path, "", (320, 320), 0.7)` (score threshold 0.7). Before each
    `detect`, call `setInputSize((w, h))`. The input is BGR. Boxes are taken from `faces[:, :4]`, as x, y, w, h.
  - Where to get the model: `face_detection_yunet_2023mar.onnx` from github.com/opencv/opencv_zoo at
    `models/face_detection_yunet/`. The Kaggle job downloads it from
    `https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx`
    with its `fetch()` (`kaggle_runs.py:1324`). Cite it as `yunet2023` in `docs/LITERATURE.md`.
  - It works with OpenCV 4.8+ and 5, so it runs on the laptop (OpenCV 5). The Haar-cascade fallback is
    OpenCV 4 only, because OpenCV 5 no longer bundles the cascades. On the laptop, always pass `--face-model <yunet.onnx>`.
- `evaluate(frames, detect, lp, levels)` scores, per frame and level, the attacker picture that reveals the
  most (highest SSIM, lowest LPIPS, highest edge corr.). Face recall is the share of faces in the original
  that are found again with IoU >= 0.3. It uses `IOU = 0.3` and `iou()` from `experiments/recognition.py`.
  Face false alarms are counted only on frames without faces.
- `experiments/recognition.py` has the stronger person detector: torchvision Faster R-CNN ResNet-50 FPN v2
  with COCO weights, score 0.5. **torch/torchvision: Kaggle only.**
- How paper 2 can reuse them: rebuild an intensity frame from the events, with E2VID/FireNet for the real
  attack or with event accumulation or time surfaces as a cheap proxy. Then call `ssim`, `edge_corr`,
  `lpips_metric` and `face_detector` on the reconstructions from the original and from the encrypted events,
  exactly as here. Paper 1's "most revealing picture per frame" rule carries over: take the best of the
  attacker's reconstructions.

## 3. Learned attacker (`experiments/learned_attack.py`, GPU) and the controls to copy

- Data: `make_pairs` returns X uint8 `[n, H, W, 6]`, made of the no-key decode and the replacement picture,
  and Y uint8 `[n, H, W, 3]`. Each frame gets a fresh `os.urandom(16)` key. The data is cached as `.npz` in
  `OUT`, and the cache name contains the source's SHA-1 (bug log #13: without it, a second run with other
  videos silently reused the first run's frames). `make_pairs_multi` splits n frames over sources
  separated by commas and skips sources that are too short. The script refuses to run if the train and test
  sources overlap, because the network would memorise the scene.
- Network: `build_unet(torch, nn, base=32)` is a 3-level U-Net with Conv-BN-ReLU blocks repeated twice,
  max-pooling and ConvTranspose up-sampling. Its output is a residual: `x[:, 3:6] + out(d1)`, a correction
  added to the replacement picture. With `--adv W`, a PatchGAN `build_disc` on 9 channels adds an LSGAN loss.
- Training loop: AdamW (lr 2e-3, wd 1e-4), CosineAnnealingLR over the epochs, L1 loss, AMP fp16 with
  GradScaler on CUDA, and horizontal flips (they keep the 8x8 grid aligned). `torch.manual_seed(0)` and a
  per-epoch numpy RNG make the permutation reproducible. The default is batch 16 for 25 epochs, and
  `state_dict` is saved to `OUT/unet_<mode>.pt`. If there is no CUDA device it prints a warning and trains on
  the CPU (only for a 2-epoch smoke test).
- Evaluation, all on the test set, with these controls:
  - (a) the replacement attack without learning;
  - (b) the network;
  - (c) the per-pixel median of the training targets, a prior that uses no ciphertext;
  - (d) the flat true mean colour;
  - (e) (c) recoloured to the true frame statistics;
  - (f) (c) recoloured to the frame statistics the stream reveals.

  The script reports bootstrap CIs on the learned SSIM and edge corr. and on the oracle SSIM, and saves
  `examples_<mode>.png` (original | attack | network). The results are merged into `results.json` per
  mode, so modes can run in separate sessions, and `results.md` is rebuilt every time.
- For paper 2 (N4), copy the structure: the same (c)-(f) controls, the residual output and the train/test
  overlap guard. Change the input to an event tensor, e.g. a voxel grid with B time bins x 2 polarities
  built from the *encrypted* events, and set the target to the clean-event reconstruction or the APS frame.
  The learned-attacker baseline for V2/V3 is "the network on encrypted events vs the prior (c)".

## 4. Datasets and download pattern (`software/scripts/get_xiph.py`)

- The script downloads Xiph derf `.y4m` files from `https://media.xiph.org/video/derf/y4m/` into
  `clips/xiph/`, via a `.part` temp file and a rename. If `ffmpeg` is on PATH it converts to MP4 with libx264
  crf 0, yuv420p, and an optional `--frames N`. It writes `clips/xiph/manifest.md` with the
  sha256 (first 16 hex digits) of each `.y4m`, so that results can name their exact inputs. `--list` shows
  the 8 known sequences, and the default set is the 6 CIF sequences.
- Paper 2 needs a `get_events.py` built the same way, with a SHA-256 manifest for each dataset: DVS Gesture,
  N-MNIST and an event dataset with APS/intensity ground truth for E2VID, all to be confirmed and cited from
  their papers. Event datasets are large, so download them on Kaggle and store the manifest in `results/`.
- `link.sources.open_source(path, w, h, loop=False).read()` gives RGB frames (video, image folder or
  "synthetic"). It is frame-based and has no event reader, so paper 2 needs its own EVT 2.0 / AEDAT reader
  in the new package.

## 5. Structure of `benchmark_suite.py` (pattern for N7 scheme comparison)

`SCHEMES` dict name -> function(an, ctr, key) re-implementing published schemes (with the citation key in
the docstring and the method in `docs/BENCHMARK_METHOD.md`). `ATTACKS` tuple (decode, replacement, NZCA,
known-plaintext). `evaluate(name, ...)` is applied to each scheme and gives a row of metrics, and `max_leak`
is the best attack. `tables()` gives the md. The `meta` block records the CI method. The same frames go to
every scheme, the attacker knows the scheme but not the key (Kerckhoffs), and the competing schemes get our
Ascon keystream ("only helps them"). Paper 2 can reuse this shape for the Du 2021 / Zhang 2024 baselines
under inject/replay/delete/splice. Their exact bibliographic data must be checked before they are cited.

## 6. Dependencies

| Package | Declared (`requirements.txt`) | Laptop (given) | Kaggle journal job installs |
|---|---|---|---|
| Python | `requires-python >=3.10` (pyproject) | 3.14 | Kaggle image default |
| numpy | >=1.24 | 2.5 | numpy |
| opencv | `opencv-python>=4.8` | 5 | `opencv-python-headless` |
| scikit-image | >=0.21 | 0.26 | scikit-image |
| scipy | >=1.10 | (installed in venv) | scipy |
| pillow, matplotlib | >=10.0, >=3.7 | venv | yes |
| cryptography | >=42 | venv | yes |
| kyber-py | >=1.0 | venv | yes |
| cocotb / cocotbext-axi | ==2.1.0 / ==0.1.28 | cocotb 2.1, Icarus 12 | other jobs only (`cocotb==2.1.0 cocotbext-axi==0.1.28`, plus `verilator` in one job) |
| torch | `requirements-gpu.txt`: torch>=2.3 (CUDA build) | **not installed** | Kaggle image (T4) |
| lpips | not declared, `pip install lpips` | **not installed** (needs torch) | yes |
| torchvision | not declared | **not installed** | Kaggle image / one job pip |
| Yosys | `make synth`; `yowasp-yosys` on Kaggle | **not installed** | `yowasp-yosys` |
| Verilator | - | **not installed** | pip `verilator` (one job) |

`pyproject.toml`: the package `secure-mjpeg-ascon` 1.0.0, setuptools, with packages `model*`, `link*`,
`system*` found under `software/`. It ships `*.v`, `*.json` and other files as package data. A paper 2
package, e.g. `software/neuro/`, must be added to `include` or it will not be importable after
`pip install -e .`.

## 7. Where each part can run

GPU or Kaggle only, because the laptop has no torch:
- learned attacker training (N4);
- E2VID/FireNet inference (N3);
- LPIPS;
- the torchvision person detector;
- any SNN training or evaluation (N6, unless it is done in numpy);
- DVS Gesture / N-MNIST classifiers (N6);
- the Yosys and Verilator steps (no binaries on the laptop; Kaggle has `yowasp-yosys`).

Laptop (CPU, light):
- the golden model, i.e. the EVT 2.0 codec, the V0-V4 levels, Ascon, the Feistel and cycle walking;
- cocotb + Icarus RTL tests (N1);
- SSIM and edge corr.;
- YuNet faces (OpenCV 5 `FaceDetectorYN`);
- leakage statistics (N5);
- active-attack tests (N7);
- overhead (N8).

Vivado (N2) runs on the laptop when the PC is free.

Kaggle job pattern (`kaggle_runs.py`, JOB "journal"):
- Steps: clone the branch, then `pip install -q -e . ... lpips yowasp-yosys`, then check
  `torch.cuda.is_available()` (no GPU means the GPU steps are skipped with a message), then fetch the data.
- The CPU steps run first and the GPU step last.
- `checkpoint()` rewrites `journal_results.zip` after every step, so whatever finished before a crash or
  the 12 h limit is kept.
- `QUICK = True` is a smoke test of about 20 min.
- Paper 2 should add its own JOB that clones `neuromorphic`, built the same way.
