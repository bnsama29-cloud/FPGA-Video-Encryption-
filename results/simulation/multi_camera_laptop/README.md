# Several cameras on one receiver, team laptop (8 cores), 7 Nov 2026

Unchanged output of `python experiments/multi_camera.py --cameras 1 2 4 8` (branch `journal-version`, scenario
`calm.json`). The 1-camera row (worst p95 2189 ms, 2 false alarms in 58 windows) is the first run after start-up
and disagrees with the Kaggle run (`../journal_kaggle/journal/multi_camera/`, 65 ms, 0 alarms); rerun
`--cameras 1` before using it. CPU load is empty because psutil was not installed.
