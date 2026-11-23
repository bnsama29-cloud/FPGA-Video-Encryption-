# N2b (model): cycle walking on a binary domain vs the mixed-radix Feistel

All W*H addresses walked for 16 packet keys per row. Mixed-radix Feistel: 1 pass, 1 word/clk.
RTL model: K = 4 unrolled passes, 16 clk per extra pass + 1 clk side-unit overhead.

| sensor | W x H | domain | binary | ratio | mean passes | p99 | max | frac > 4 | dense words/clk | table entries walk / mixed |
|---|---|---|---|---|---|---|---|---|---|---|
| nmnist | 34x34 | pow2 | 64x64 | 3.543 | 3.542 | 14 | 29 | 0.2671 | 0.061 | 512 / 272 |
| nmnist | 34x34 | balanced | 64x64 | 3.543 | 3.542 | 14 | 29 | 0.2671 | 0.061 | 512 / 272 |
| dvsgesture | 128x128 | pow2 | 128x128 | 1 | 1 | 1 | 1 | 0 | 1 | 1024 / 1024 |
| dvsgesture | 128x128 | balanced | 128x128 | 1 | 1 | 1 | 1 | 0 | 1 | 1024 / 1024 |
| davis346 | 346x260 | pow2 | 512x512 | 2.914 | 2.914 | 11 | 33 | 0.1858 | 0.101 | 4096 / 2424 |
| davis346 | 346x260 | balanced | 512x512 | 2.914 | 2.914 | 11 | 33 | 0.1858 | 0.101 | 4096 / 2424 |
| cif | 352x288 | pow2 | 512x512 | 2.586 | 2.586 | 10 | 28 | 0.1411 | 0.143 | 4096 / 2560 |
| cif | 352x288 | balanced | 512x512 | 2.586 | 2.586 | 10 | 28 | 0.1411 | 0.143 | 4096 / 2560 |
| vga | 640x480 | pow2 | 1024x512 | 1.707 | 1.707 | 6 | 18 | 0.0293 | 0.546 | 6144 / 4480 |
| vga | 640x480 | balanced | 1024x1024 | 3.413 | 3.413 | 14 | 42 | 0.25 | 0.067 | 8192 / 4480 |
| imx636 | 1280x720 | pow2 | 2048x1024 | 2.276 | 2.276 | 8 | 30 | 0.0987 | 0.213 | 12288 / 8000 |
| imx636 | 1280x720 | balanced | 2048x2048 | 4.551 | 4.551 | 19 | 64 | 0.3707 | 0.035 | 16384 / 8000 |
