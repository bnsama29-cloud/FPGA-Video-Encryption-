# Post-quantum session key on `pynq` (armv7l, Python 3.10.4)

Hybrid ML-KEM-768 + X25519, authenticated by the pre-shared key; median of 20 runs. Wire: M1 1268 B, M2 1172 B, confirm 20 B (one datagram each).

| ML-KEM implementation | receiver M1 (ms) | sender answer (ms) | receiver finish (ms) | total (ms) |
|---|---|---|---|---|
| kyber-py | 112.85 | 153.71 | 183.17 | 449.73 |
