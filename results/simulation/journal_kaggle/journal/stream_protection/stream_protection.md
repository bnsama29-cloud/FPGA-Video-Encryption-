# Stream protection per frame on `x86_64`

Protection only (the JPEG frame is already encoded); median over frames.

## 352x288 (mean frame 17621 bytes)

| Method | ms / frame | frames/s (protection only) | bytes added | plays without key | authenticated |
|---|---|---|---|---|---|
| SRTP, AES-128-GCM (RFC 7714) | 0.032 | 31216 | 245 | no | yes |
| DTLS 1.2 records, AES-128-GCM | 0.009 | 110884 | 74 | no | yes |
| RTP packets, ChaCha20-Poly1305 | 0.042 | 23532 | 245 | no | yes |
| Ascon-AEAD128, whole frame (C) | 0.078 | 12795 | 16 | no | yes |
| ours E2, C encoder on this CPU (extra over E0) | 0.346 | 2886 | 76 | yes | yes |
| ours E5, C encoder on this CPU (extra over E0) | 0.534 | 1871 | 1437 | yes | yes |

Ours in hardware adds no time (the encryption is in the encoder's pipeline: results/board/); the C rows give its cost when the same coder runs in software.

