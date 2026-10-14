Source: /kaggle/working/opendata/sintel_trailer.mp4, 6 frames, 320x240

| Variant | Overhead vs E4 (%) | Edge corr. replacement attack | NZCA corr. (block level) | Jigsaw neighbours | Edge corr. jigsaw | Raster solver: segments in place | Raster solver: true successors (chance) | Edge corr. raster solver | Permutation key space (bits) |
|---|---|---|---|---|---|---|---|---|---|
| E4 | 0.0 | 0.33 | 0.72 | – | – | – | – | – | – |
| E5 N=1 | 15.1 | -0.01 | -0.00 | 0.02 | -0.03 | 0.01 | 0.03 (0.00) | -0.02 | 2041 |
| E5 N=2 | 7.4 | -0.01 | 0.02 | 0.02 | -0.02 | 0.01 | 0.03 (0.01) | -0.01 | 873 |
| E5 N=4 | 3.7 | -0.02 | -0.01 | 0.06 | -0.04 | 0.02 | 0.03 (0.01) | 0.02 | 363 |
| E5 N=5 | 2.9 | 0.00 | -0.01 | 0.06 | -0.01 | 0.03 | 0.08 (0.02) | 0.02 | 272 |
| E5 N=8 | 1.9 | 0.01 | 0.05 | – | – | 0.04 | 0.04 (0.03) | 0.01 | 149 |
| E5 N=10 | 1.4 | 0.01 | 0.03 | 0.09 | 0.01 | 0.01 | 0.05 (0.03) | -0.01 | 108 |
| E5 N=32 | 0.5 | -0.02 | 0.00 | – | – | 0.13 | 0.19 (0.11) | -0.02 | 22 |
