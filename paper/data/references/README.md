# Attacks from the reference papers (Kaggle JOB = "references", 17 Oct 2026, 74 min, 12/12 steps PASS)

* `sign_recovery/` — B35, `experiments/sign_recovery.py`: Lin et al.'s LP sign recovery, 128x96 luma, q75.
  Kodak 12 images, scikit-image 7 photos, 2 frames of each video (Sintel, Tears of Steel, five private clips).
  Two video frames are blank (no AC coefficient, sign share undefined) and are left out by make_assets.
* `video_fingerprint/` — B36, `experiments/video_fingerprint.py`: video identification from frame sizes,
  7 videos (2 open + 5 private), 600 frames at stride 3, 320x240, 300 queries per window.
Private clips contribute numbers only; no frame was saved.
