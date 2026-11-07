# Bytes per protection level: akiyo_cif, 352x288, 50 frames

Overhead relative to the plain JPEG of the same frame (no key, no secure segment), mean over frames.
`payload equal` = share of frames whose coded payload (bits before byte stuffing) has exactly the length
of the same frame unencrypted in the same container (plain JPEG for v2, v3 E0 for v3); the scan in bytes
may still differ by stuffed 0x00 bytes. E5 reorders restart segments, which adds markers in v2.

## Quality 50

| Stream | frame bytes | scan bytes | frame overhead | scan overhead | payload equal |
|---|---|---|---|---|---|
| plain | 8364 | 7755 | +0 B (+0.00 %) | +0.00 % | 100 % |
| v2 E0 | 8406 | 7755 | +42 B (+0.50 %) | +0.00 % | 100 % |
| v2 E1 | 8404 | 7753 | +40 B (+0.48 %) | -0.02 % | 100 % |
| v2 E2 | 8404 | 7753 | +40 B (+0.48 %) | -0.02 % | 100 % |
| v2 E3 | 8406 | 7755 | +42 B (+0.50 %) | -0.00 % | 100 % |
| v2 E4 | 8406 | 7755 | +42 B (+0.50 %) | +0.00 % | 100 % |
| v2 E5 | 9703 | 9046 | +1339 B (+16.01 %) | +16.65 % | 0 % |
| v3 E0 | 8456 | 7799 | +92 B (+1.10 %) | +0.57 % | 100 % |
| v3 E1 | 8454 | 7797 | +90 B (+1.07 %) | +0.54 % | 100 % |
| v3 E2 | 8452 | 7795 | +88 B (+1.05 %) | +0.51 % | 100 % |
| v3 E3 | 8453 | 7796 | +89 B (+1.06 %) | +0.53 % | 100 % |
| v3 E4 | 8455 | 7798 | +91 B (+1.08 %) | +0.55 % | 100 % |
| v3 E5 | 9705 | 9048 | +1341 B (+16.04 %) | +16.68 % | 0 % |

Link padding on the v3 E5 stream (frame-size hiding, `link.pad`):

| Policy | mean bytes | overhead | distinct sizes |
|---|---|---|---|
| none | 9705 | +0.0 % | 45 |
| bucket:1024 | 10240 | +5.5 % | 1 |
| window:100 | 9984 | +2.9 % | 1 |
| runmax | 9984 | +2.9 % | 1 |

## Quality 75

| Stream | frame bytes | scan bytes | frame overhead | scan overhead | payload equal |
|---|---|---|---|---|---|
| plain | 12217 | 11608 | +0 B (+0.00 %) | +0.00 % | 100 % |
| v2 E0 | 12259 | 11608 | +42 B (+0.34 %) | +0.00 % | 100 % |
| v2 E1 | 12260 | 11609 | +43 B (+0.35 %) | +0.01 % | 100 % |
| v2 E2 | 12261 | 11610 | +44 B (+0.36 %) | +0.01 % | 100 % |
| v2 E3 | 12264 | 11613 | +47 B (+0.38 %) | +0.04 % | 100 % |
| v2 E4 | 12264 | 11613 | +47 B (+0.38 %) | +0.04 % | 100 % |
| v2 E5 | 13637 | 12980 | +1420 B (+11.62 %) | +11.82 % | 0 % |
| v3 E0 | 12311 | 11654 | +93 B (+0.77 %) | +0.39 % | 100 % |
| v3 E1 | 12312 | 11655 | +94 B (+0.77 %) | +0.40 % | 100 % |
| v3 E2 | 12312 | 11655 | +94 B (+0.77 %) | +0.40 % | 100 % |
| v3 E3 | 12315 | 11658 | +97 B (+0.80 %) | +0.42 % | 100 % |
| v3 E4 | 12317 | 11660 | +100 B (+0.82 %) | +0.45 % | 100 % |
| v3 E5 | 13637 | 12980 | +1420 B (+11.62 %) | +11.82 % | 0 % |

Link padding on the v3 E5 stream (frame-size hiding, `link.pad`):

| Policy | mean bytes | overhead | distinct sizes |
|---|---|---|---|
| none | 13637 | +0.0 % | 47 |
| bucket:1024 | 14336 | +5.1 % | 1 |
| window:100 | 13834 | +1.4 % | 2 |
| runmax | 13834 | +1.4 % | 2 |

## Quality 90

| Stream | frame bytes | scan bytes | frame overhead | scan overhead | payload equal |
|---|---|---|---|---|---|
| plain | 21677 | 21068 | +0 B (+0.00 %) | +0.00 % | 100 % |
| v2 E0 | 21719 | 21068 | +42 B (+0.19 %) | +0.00 % | 100 % |
| v2 E1 | 21718 | 21067 | +41 B (+0.19 %) | -0.01 % | 100 % |
| v2 E2 | 21717 | 21066 | +40 B (+0.19 %) | -0.01 % | 100 % |
| v2 E3 | 21723 | 21072 | +46 B (+0.21 %) | +0.02 % | 100 % |
| v2 E4 | 21722 | 21071 | +45 B (+0.21 %) | +0.01 % | 100 % |
| v2 E5 | 23221 | 22564 | +1544 B (+7.12 %) | +7.10 % | 0 % |
| v3 E0 | 21769 | 21112 | +92 B (+0.42 %) | +0.21 % | 100 % |
| v3 E1 | 21767 | 21110 | +90 B (+0.42 %) | +0.20 % | 100 % |
| v3 E2 | 21766 | 21109 | +89 B (+0.41 %) | +0.20 % | 100 % |
| v3 E3 | 21772 | 21115 | +95 B (+0.44 %) | +0.22 % | 100 % |
| v3 E4 | 21772 | 21115 | +95 B (+0.44 %) | +0.22 % | 100 % |
| v3 E5 | 23222 | 22565 | +1545 B (+7.13 %) | +7.11 % | 0 % |

Link padding on the v3 E5 stream (frame-size hiding, `link.pad`):

| Policy | mean bytes | overhead | distinct sizes |
|---|---|---|---|
| none | 23222 | +0.0 % | 48 |
| bucket:1024 | 23552 | +1.4 % | 1 |
| window:100 | 23542 | +1.4 % | 2 |
| runmax | 23542 | +1.4 % | 2 |
