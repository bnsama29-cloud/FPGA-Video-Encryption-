# Post-quantum session key on `DESKTOP-I60PED0` (AMD64, Python 3.14.5)

Hybrid ML-KEM-768 + X25519, authenticated by the pre-shared key; median of 3 runs. Wire: M1 1268 B, M2 1172 B, confirm 20 B (one datagram each).

| ML-KEM implementation | receiver M1 (ms) | sender answer (ms) | receiver finish (ms) | total (ms) |
|---|---|---|---|---|
| cryptography | 0.17 | 0.11 | 0.08 | 0.37 |
| kyber-py | 2.27 | 2.70 | 3.52 | 8.48 |
