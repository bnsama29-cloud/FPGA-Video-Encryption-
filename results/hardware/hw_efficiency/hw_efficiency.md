# Hardware figures of merit (throughput: results/hardware/lanes_rtl/results.json; area/power: results/hardware/vivado/vivado_results.json)

| Design | Mode | Frame | LUT | BRAM | DSP | MHz | Mpx/s | fps 1080p | Mpx/s per kLUT | Gbit/s in | Power (W) | nJ/pixel |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ours, contract v2 (1 pipeline) | E2 | 640x480 | 5,043 | 25.5 | 23 | 100 | 65.2 | 31.4 | 12.92 | 1.56 | 0.230 SAIF (Medium) | 3.53 |
| ours, 2 lanes | E2 | 640x480 | 10,099 | 52.0 | 46 | 100 | 126.1 | 60.8 | 12.48 | 3.03 | 0.345 SAIF (Medium) | 2.74 |
| ours, 4 lanes | E2 | 640x480 | 17,515 | 56.0 | 92 | 100 | 181.6 | 87.6 | 10.37 | 4.36 | 0.606 vectorless (Medium) | 3.34 |

Published (copied from each source, results/hardware/related/compare.json; different devices and functions):

| Work | Device | Function | LUT (Stratix: ALUT) | DSP (Stratix: 18-bit mult.) | MHz | Mpx/s | Mpx/s per kLUT | Crypto |
|---|---|---|---|---|---|---|---|---|
| logiJPGE [logijpge] | Zynq-7020 | JPEG enc. | 3,240 | 30 | 150 | 150.0 | 46.30 | none |
| CAST JPEG-E-S [castjpeg] | Artix-7 | JPEG enc. | 3,069 | 16 | 166 | - | - | none |
| Khairallah [khairallah2023] | Artix-7 | Ascon-PRF MAC | 1,031 | 0 | 200 | - | - | MAC |
| Kurian [kurian2025] | Artix-7 | Ascon AEAD + replay | 5,335 | 0 | 100 | - | - | AEAD |
| Kishore [kishore2015] | Stratix IV | JPEG enc. + scrambling (grey) | 2,250 | 47 | 100 | 11.1 | 4.93 | scrambling |
| Bağbaba [bagbaba2015] | Virtex-6 | JPEG enc. + TEA | 2,130 | 9 | 87 | - | - | TEA |

Throughput: RTL simulation, no DMA stalls. Power: as labelled (vectorless = estimate). E5 rows use the area of the Vivado run named above; a run older than the E5 RTL has no E5 logic in it.
