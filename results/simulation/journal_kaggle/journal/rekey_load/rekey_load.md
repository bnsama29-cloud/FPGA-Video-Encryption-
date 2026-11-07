# Rekeys while the video runs

8 rekeys; the receiver adopted 8 new epochs. In the 2 s after each rekey: 0 frames rejected (0 of them from the old epoch), 12 missing by counter (all causes, including channel loss).
First verified frame of the new epoch: median 123.0 ms, worst 456.8 ms after the rekey.

| Rekey | epoch | adopted | first new-epoch frame (ms) | rejected | stale epoch | missing | shown / expected |
|---|---|---|---|---|---|---|---|
| 1 | 1 | yes | 114.5 | 0 | 0 | 0 | 20 / 20 |
| 2 | 2 | yes | 131.4 | 0 | 0 | 0 | 20 / 20 |
| 3 | 3 | yes | 113.2 | 0 | 0 | 0 | 20 / 20 |
| 4 | 4 | yes | 139.8 | 0 | 0 | 0 | 20 / 20 |
| 5 | 5 | yes | 110.8 | 0 | 0 | 1 | 19 / 17 |
| 6 | 6 | yes | 231.9 | 0 | 0 | 3 | 16 / 16 |
| 7 | 7 | yes | 456.8 | 0 | 0 | 2 | 14 / 15 |
| 8 | 8 | yes | 111.9 | 0 | 0 | 6 | 14 / 15 |
