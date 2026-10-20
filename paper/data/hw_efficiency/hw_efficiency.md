# Hardware figures of merit (throughput: paper/data/lanes_rtl/results.json, sim_out/lanes_rtl/results.json; area/power: paper/data/vivado/vivado_results.json)

| Design | Mode | Frame | LUT | BRAM | DSP | MHz | Mpx/s | fps 1080p | Mpx/s per kLUT | Gbit/s in | Power (W) | nJ/pixel |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ours, contract v2 (1 pipeline) | E2 | 640x480 | 5,037 | 24.5 | 23 | 100 | 65.2 | 31.4 | 12.94 | 1.56 | 0.210 SAIF (Medium) | 3.22 |
| ours, 2 lanes | E2 | 640x480 | 10,069 | 50.0 | 46 | 100 | 122.3 | 59.0 | 12.15 | 2.94 | 0.319 SAIF (Medium) | 2.61 |
| ours, 4 lanes | E2 | 640x480 | 16,893 | 52.0 | 92 | 100 | 175.7 | 84.7 | 10.40 | 4.22 | 0.555 vectorless (Medium) | 3.16 |

Published (copied from each source, paper/data/related/compare.json; different devices and functions):

| Work | Device | Function | LUT (Stratix: ALUT) | DSP (Stratix: 18-bit mult.) | MHz | Mpx/s | Mpx/s per kLUT | Crypto |
|---|---|---|---|---|---|---|---|---|
| logiJPGE [logijpge] | Zynq-7020 | JPEG enc. | 3,240 | 30 | 150 | 150.0 | 46.30 | none |
| CAST JPEG-E-S [castjpeg] | Artix-7 | JPEG enc. | 3,069 | 16 | 166 | - | - | none |
| Khairallah [khairallah2023] | Artix-7 | Ascon-PRF MAC | 1,031 | 0 | 200 | - | - | MAC |
| Kurian [kurian2025] | Artix-7 | Ascon AEAD + replay | 5,335 | 0 | 100 | - | - | AEAD |
| Kishore [kishore2015] | Stratix IV | JPEG enc. + scrambling (grey) | 2,250 | 47 | 100 | 11.1 | 4.93 | scrambling |
| Bağbaba [bagbaba2015] | Virtex-6 | JPEG enc. + TEA | 2,130 | 9 | 87 | - | - | TEA |

Throughput: RTL simulation, no DMA stalls. Power: as labelled (vectorless = estimate). E5 rows use the area of the Vivado run named above; a run older than the E5 RTL has no E5 logic in it.
