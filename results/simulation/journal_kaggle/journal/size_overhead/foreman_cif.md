# Bytes per protection level: foreman_cif, 352x288, 50 frames

Overhead relative to the plain JPEG of the same frame (no key, no secure segment), mean over frames.
`payload equal` = share of frames whose coded payload (bits before byte stuffing) has exactly the length
of the same frame unencrypted in the same container (plain JPEG for v2, v3 E0 for v3); the scan in bytes
may still differ by stuffed 0x00 bytes. E5 reorders restart segments, which adds markers in v2.

## Quality 50

| Stream | frame bytes | scan bytes | frame overhead | scan overhead | payload equal |
|---|---|---|---|---|---|
| plain | 11784 | 11175 | +0 B (+0.00 %) | +0.00 % | 100 % |
| v2 E0 | 11826 | 11175 | +42 B (+0.36 %) | +0.00 % | 100 % |
| v2 E1 | 11825 | 11174 | +42 B (+0.36 %) | -0.00 % | 100 % |
| v2 E2 | 11825 | 11174 | +41 B (+0.36 %) | -0.01 % | 100 % |
| v2 E3 | 11831 | 11180 | +47 B (+0.40 %) | +0.04 % | 100 % |
| v2 E4 | 11830 | 11179 | +46 B (+0.40 %) | +0.04 % | 100 % |
| v2 E5 | 13082 | 12425 | +1299 B (+11.21 %) | +11.41 % | 0 % |
| v3 E0 | 11863 | 11206 | +79 B (+0.68 %) | +0.28 % | 100 % |
| v3 E1 | 11863 | 11206 | +79 B (+0.68 %) | +0.28 % | 100 % |
| v3 E2 | 11862 | 11205 | +78 B (+0.67 %) | +0.27 % | 100 % |
| v3 E3 | 11865 | 11208 | +82 B (+0.70 %) | +0.31 % | 100 % |
| v3 E4 | 11867 | 11210 | +84 B (+0.72 %) | +0.32 % | 100 % |
| v3 E5 | 13082 | 12425 | +1299 B (+11.21 %) | +11.41 % | 0 % |

Link padding on the v3 E5 stream (frame-size hiding, `link.pad`):

| Policy | mean bytes | overhead | distinct sizes |
|---|---|---|---|
| none | 13082 | +0.0 % | 50 |
| bucket:1024 | 13558 | +3.6 % | 8 |
| window:100 | 14193 | +8.5 % | 10 |
| runmax | 14193 | +8.5 % | 10 |

## Quality 75

| Stream | frame bytes | scan bytes | frame overhead | scan overhead | payload equal |
|---|---|---|---|---|---|
| plain | 17540 | 16930 | +0 B (+0.00 %) | +0.00 % | 100 % |
| v2 E0 | 17582 | 16930 | +42 B (+0.24 %) | +0.00 % | 100 % |
| v2 E1 | 17581 | 16930 | +42 B (+0.24 %) | +0.00 % | 100 % |
| v2 E2 | 17581 | 16930 | +41 B (+0.24 %) | -0.00 % | 100 % |
| v2 E3 | 17589 | 16938 | +49 B (+0.29 %) | +0.05 % | 100 % |
| v2 E4 | 17588 | 16937 | +48 B (+0.28 %) | +0.04 % | 100 % |
| v2 E5 | 18950 | 18293 | +1410 B (+8.20 %) | +8.21 % | 0 % |
| v3 E0 | 17619 | 16962 | +80 B (+0.46 %) | +0.19 % | 100 % |
| v3 E1 | 17617 | 16960 | +77 B (+0.45 %) | +0.18 % | 100 % |
| v3 E2 | 17618 | 16961 | +79 B (+0.46 %) | +0.19 % | 100 % |
| v3 E3 | 17625 | 16968 | +86 B (+0.50 %) | +0.23 % | 100 % |
| v3 E4 | 17625 | 16968 | +86 B (+0.50 %) | +0.23 % | 100 % |
| v3 E5 | 18950 | 18293 | +1410 B (+8.20 %) | +8.21 % | 0 % |

Link padding on the v3 E5 stream (frame-size hiding, `link.pad`):

| Policy | mean bytes | overhead | distinct sizes |
|---|---|---|---|
| none | 18950 | +0.0 % | 50 |
| bucket:1024 | 19517 | +3.0 % | 11 |
| window:100 | 20577 | +8.6 % | 12 |
| runmax | 20577 | +8.6 % | 12 |

## Quality 90

| Stream | frame bytes | scan bytes | frame overhead | scan overhead | payload equal |
|---|---|---|---|---|---|
| plain | 29901 | 29292 | +0 B (+0.00 %) | +0.00 % | 100 % |
| v2 E0 | 29943 | 29292 | +42 B (+0.14 %) | +0.00 % | 100 % |
| v2 E1 | 29941 | 29290 | +40 B (+0.14 %) | -0.01 % | 100 % |
| v2 E2 | 29943 | 29292 | +42 B (+0.14 %) | +0.00 % | 100 % |
| v2 E3 | 29953 | 29302 | +52 B (+0.18 %) | +0.03 % | 100 % |
| v2 E4 | 29953 | 29302 | +52 B (+0.18 %) | +0.03 % | 100 % |
| v2 E5 | 31452 | 30795 | +1551 B (+5.28 %) | +5.23 % | 0 % |
| v3 E0 | 29978 | 29321 | +77 B (+0.26 %) | +0.10 % | 100 % |
| v3 E1 | 29980 | 29323 | +79 B (+0.27 %) | +0.11 % | 100 % |
| v3 E2 | 29978 | 29321 | +77 B (+0.26 %) | +0.10 % | 100 % |
| v3 E3 | 29987 | 29330 | +86 B (+0.29 %) | +0.13 % | 100 % |
| v3 E4 | 29988 | 29331 | +87 B (+0.30 %) | +0.13 % | 100 % |
| v3 E5 | 31451 | 30794 | +1550 B (+5.28 %) | +5.23 % | 0 % |

Link padding on the v3 E5 stream (frame-size hiding, `link.pad`):

| Policy | mean bytes | overhead | distinct sizes |
|---|---|---|---|
| none | 31451 | +0.0 % | 50 |
| bucket:1024 | 31949 | +1.6 % | 15 |
| window:100 | 33889 | +7.8 % | 13 |
| runmax | 33889 | +7.8 % | 13 |
