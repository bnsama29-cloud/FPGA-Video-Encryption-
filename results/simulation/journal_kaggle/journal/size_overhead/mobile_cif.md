# Bytes per protection level: mobile_cif, 352x288, 50 frames

Overhead relative to the plain JPEG of the same frame (no key, no secure segment), mean over frames.
`payload equal` = share of frames whose coded payload (bits before byte stuffing) has exactly the length
of the same frame unencrypted in the same container (plain JPEG for v2, v3 E0 for v3); the scan in bytes
may still differ by stuffed 0x00 bytes. E5 reorders restart segments, which adds markers in v2.

## Quality 50

| Stream | frame bytes | scan bytes | frame overhead | scan overhead | payload equal |
|---|---|---|---|---|---|
| plain | 24975 | 24366 | +0 B (+0.00 %) | +0.00 % | 100 % |
| v2 E0 | 25017 | 24366 | +42 B (+0.17 %) | +0.00 % | 100 % |
| v2 E1 | 25015 | 24364 | +40 B (+0.16 %) | -0.01 % | 100 % |
| v2 E2 | 25017 | 24366 | +42 B (+0.17 %) | +0.00 % | 100 % |
| v2 E3 | 25024 | 24373 | +49 B (+0.20 %) | +0.03 % | 100 % |
| v2 E4 | 25026 | 24375 | +51 B (+0.20 %) | +0.04 % | 100 % |
| v2 E5 | 26152 | 25495 | +1177 B (+4.72 %) | +4.64 % | 0 % |
| v3 E0 | 25059 | 24402 | +84 B (+0.34 %) | +0.15 % | 100 % |
| v3 E1 | 25058 | 24401 | +83 B (+0.33 %) | +0.14 % | 100 % |
| v3 E2 | 25059 | 24402 | +84 B (+0.34 %) | +0.15 % | 100 % |
| v3 E3 | 25068 | 24411 | +93 B (+0.37 %) | +0.18 % | 100 % |
| v3 E4 | 25067 | 24410 | +92 B (+0.37 %) | +0.18 % | 100 % |
| v3 E5 | 26153 | 25496 | +1178 B (+4.72 %) | +4.64 % | 0 % |

Link padding on the v3 E5 stream (frame-size hiding, `link.pad`):

| Policy | mean bytes | overhead | distinct sizes |
|---|---|---|---|
| none | 26153 | +0.0 % | 50 |
| bucket:1024 | 26747 | +2.3 % | 3 |
| window:100 | 26414 | +1.0 % | 8 |
| runmax | 26414 | +1.0 % | 8 |

## Quality 75

| Stream | frame bytes | scan bytes | frame overhead | scan overhead | payload equal |
|---|---|---|---|---|---|
| plain | 35978 | 35369 | +0 B (+0.00 %) | +0.00 % | 100 % |
| v2 E0 | 36020 | 35369 | +42 B (+0.12 %) | +0.00 % | 100 % |
| v2 E1 | 36021 | 35370 | +43 B (+0.12 %) | +0.00 % | 100 % |
| v2 E2 | 36021 | 35370 | +43 B (+0.12 %) | +0.00 % | 100 % |
| v2 E3 | 36035 | 35384 | +57 B (+0.16 %) | +0.04 % | 100 % |
| v2 E4 | 36033 | 35382 | +55 B (+0.15 %) | +0.04 % | 100 % |
| v2 E5 | 37199 | 36542 | +1221 B (+3.40 %) | +3.32 % | 0 % |
| v3 E0 | 36066 | 35409 | +88 B (+0.25 %) | +0.11 % | 100 % |
| v3 E1 | 36065 | 35408 | +87 B (+0.24 %) | +0.11 % | 100 % |
| v3 E2 | 36065 | 35408 | +87 B (+0.24 %) | +0.11 % | 100 % |
| v3 E3 | 36077 | 35420 | +100 B (+0.28 %) | +0.15 % | 100 % |
| v3 E4 | 36078 | 35421 | +101 B (+0.28 %) | +0.15 % | 100 % |
| v3 E5 | 37199 | 36542 | +1221 B (+3.40 %) | +3.32 % | 0 % |

Link padding on the v3 E5 stream (frame-size hiding, `link.pad`):

| Policy | mean bytes | overhead | distinct sizes |
|---|---|---|---|
| none | 37199 | +0.0 % | 50 |
| bucket:1024 | 37745 | +1.5 % | 4 |
| window:100 | 37443 | +0.7 % | 11 |
| runmax | 37443 | +0.7 % | 11 |

## Quality 90

| Stream | frame bytes | scan bytes | frame overhead | scan overhead | payload equal |
|---|---|---|---|---|---|
| plain | 57250 | 56641 | +0 B (+0.00 %) | +0.00 % | 100 % |
| v2 E0 | 57292 | 56641 | +42 B (+0.07 %) | +0.00 % | 100 % |
| v2 E1 | 57292 | 56641 | +42 B (+0.07 %) | +0.00 % | 100 % |
| v2 E2 | 57289 | 56638 | +40 B (+0.07 %) | -0.00 % | 100 % |
| v2 E3 | 57307 | 56656 | +57 B (+0.10 %) | +0.03 % | 100 % |
| v2 E4 | 57311 | 56660 | +61 B (+0.11 %) | +0.03 % | 100 % |
| v2 E5 | 58512 | 57855 | +1262 B (+2.21 %) | +2.15 % | 0 % |
| v3 E0 | 57334 | 56678 | +85 B (+0.15 %) | +0.06 % | 100 % |
| v3 E1 | 57334 | 56677 | +84 B (+0.15 %) | +0.06 % | 100 % |
| v3 E2 | 57332 | 56675 | +82 B (+0.14 %) | +0.06 % | 100 % |
| v3 E3 | 57349 | 56692 | +99 B (+0.17 %) | +0.09 % | 100 % |
| v3 E4 | 57348 | 56691 | +98 B (+0.17 %) | +0.09 % | 100 % |
| v3 E5 | 58511 | 57854 | +1261 B (+2.21 %) | +2.14 % | 0 % |

Link padding on the v3 E5 stream (frame-size hiding, `link.pad`):

| Policy | mean bytes | overhead | distinct sizes |
|---|---|---|---|
| none | 58511 | +0.0 % | 50 |
| bucket:1024 | 59126 | +1.1 % | 6 |
| window:100 | 58783 | +0.5 % | 16 |
| runmax | 58783 | +0.5 % | 16 |
