# Rekeys while the video runs

8 rekeys; the receiver adopted 8 new epochs. In the 2 s after each rekey: 0 frames rejected (0 of them from the old epoch), 16 missing by counter (all causes, including channel loss).
First verified frame of the new epoch: median 41.0 ms, worst 153.6 ms after the rekey.

| Rekey | epoch | adopted | first new-epoch frame (ms) | rejected | stale epoch | missing | shown / expected |
|---|---|---|---|---|---|---|---|
| 1 | 1 | yes | 47.9 | 0 | 0 | 0 | 20 / 20 |
| 2 | 2 | yes | 16.0 | 0 | 0 | 0 | 20 / 20 |
| 3 | 3 | yes | 26.2 | 0 | 0 | 0 | 20 / 20 |
| 4 | 4 | yes | 66.5 | 0 | 0 | 0 | 20 / 20 |
| 5 | 5 | yes | 53.7 | 0 | 0 | 5 | 15 / 17 |
| 6 | 6 | yes | 153.6 | 0 | 0 | 1 | 18 / 16 |
| 7 | 7 | yes | 31.3 | 0 | 0 | 5 | 15 / 17 |
| 8 | 8 | yes | 34.1 | 0 | 0 | 5 | 15 / 14 |
