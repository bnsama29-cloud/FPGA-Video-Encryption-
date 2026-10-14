Source: /kaggle/working/opendata/kodak, 6 frames, 320x240

| Variant | Overhead vs E4 (%) | Edge corr. replacement attack | NZCA corr. (block level) | Jigsaw neighbours | Edge corr. jigsaw | Raster solver: segments in place | Raster solver: true successors (chance) | Edge corr. raster solver | Permutation key space (bits) |
|---|---|---|---|---|---|---|---|---|---|
| E4 | 0.0 | 0.33 | 0.79 | – | – | – | – | – | – |
| E5 N=1 | 8.3 | -0.00 | 0.01 | 0.01 | -0.00 | 0.00 | 0.01 (0.00) | -0.01 | 2041 |
| E5 N=2 | 4.1 | 0.00 | 0.01 | 0.02 | -0.00 | 0.00 | 0.03 (0.01) | 0.01 | 873 |
| E5 N=4 | 2.0 | 0.00 | -0.01 | 0.04 | 0.02 | 0.03 | 0.03 (0.01) | 0.03 | 363 |
| E5 N=5 | 1.6 | 0.03 | 0.06 | 0.06 | 0.03 | 0.02 | 0.03 (0.02) | 0.01 | 272 |
| E5 N=8 | 1.1 | 0.02 | 0.05 | – | – | 0.05 | 0.03 (0.03) | 0.02 | 149 |
| E5 N=10 | 0.8 | 0.02 | 0.02 | 0.07 | 0.05 | 0.09 | 0.09 (0.03) | 0.06 | 108 |
| E5 N=32 | 0.3 | 0.02 | 0.00 | – | – | 0.23 | 0.31 (0.11) | 0.02 | 22 |
