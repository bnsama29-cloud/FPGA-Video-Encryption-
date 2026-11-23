# N16 simulated first-order TVLA (fixed vs random), register-level leakage model

Simulation, not a measurement: Hamming weight and Hamming distance per 64-bit register, Gaussian noise 2.0 bits, no glitches. Threshold |t| = 4.5.

| design | traces | samples | max |t| | samples over 4.5 |
|---|---|---|---|---|
| unmasked round (nv_ascon_round_reg) | 200000 | 20 | 389.1 | 15 |
| DOM round (nv_ascon_round_dom) | 200000 | 76 | 3.1 | 0 |
