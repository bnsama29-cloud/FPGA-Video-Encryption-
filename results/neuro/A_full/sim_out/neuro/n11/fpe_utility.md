# N11 FPE utility

(a) Bytes (sum over samples):

| payload | lzma | zlib | zstd-19 | raw |
|---|---|---|---|---|
| plain | 22193888 | 27751802 | 26065913 | 33742368 |
| V1 | 22448404 | 27895012 | 26263431 | 33742368 |
| V2 | 29231648 | 31066134 | 30795292 | 33742368 |
| V3 | 29659320 | 31064124 | 30785369 | 33742368 |
| V4 | 35161568 | 34950188 | 34789714 | 35970004 |

(b) Activity detection AUC from what a packet shows without the key:

| view | AUC |
|---|---|
| plain | 0.9983 |
| V1 | 0.9983 |
| V2 | 0.9983 |
| V3 | 0.9983 |
| V4 | 0.9986 |
| V3 + pad floor 8 | 0.8731 |
| V3 + pad ladder 2..64 | 0.9931 |
| V4 + pad floor 8 | 0.8731 |
| V4 + pad ladder 2..64 | 0.9931 |

Criterion: kept by ['V1', 'V2', 'V3']; lost by V4 + padding: ['V4 + pad floor 8'] -> FPE worth it.

EVT 3.0: not run here: needs expelliarmus (Kaggle job)
