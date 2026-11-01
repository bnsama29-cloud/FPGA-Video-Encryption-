Source: /kaggle/working/opendata/tearsofsteel.mov, 6 frames, 320x240

| Variant | Overhead vs E4 (%) | Edge corr. replacement attack | NZCA corr. (block level) | Jigsaw neighbours | Edge corr. jigsaw | Raster solver: segments in place | Raster solver: true successors (chance) | Edge corr. raster solver | Permutation key space (bits) |
|---|---|---|---|---|---|---|---|---|---|
| E4 | 0.0 | 0.43 | 0.84 | – | – | – | – | – | – |
| E5 N=1 | 13.8 | -0.01 | -0.03 | 0.01 | -0.02 | 0.00 | 0.01 (0.00) | 0.07 | 2041 |
| E5 N=2 | 6.9 | -0.01 | -0.01 | 0.02 | -0.01 | 0.01 | 0.02 (0.01) | 0.05 | 873 |
| E5 N=4 | 3.5 | -0.01 | -0.01 | 0.05 | 0.03 | 0.01 | 0.04 (0.01) | 0.02 | 363 |
| E5 N=5 | 2.8 | -0.01 | -0.03 | 0.05 | -0.05 | 0.04 | 0.06 (0.02) | 0.06 | 272 |
| E5 N=8 | 1.8 | 0.02 | 0.04 | – | – | 0.07 | 0.03 (0.03) | 0.02 | 149 |
| E5 N=10 | 1.4 | 0.02 | 0.04 | 0.09 | 0.03 | 0.03 | 0.05 (0.03) | -0.00 | 108 |
| E5 N=32 | 0.5 | 0.03 | 0.04 | – | – | 0.22 | 0.17 (0.11) | 0.01 | 22 |
