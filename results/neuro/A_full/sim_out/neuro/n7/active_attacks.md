# N7 active attacks

| attack | required status reached | rate [CP 95 %] | statuses seen |
|---|---|---|---|
| inject | 200/200 | 1.000 [0.982, 1.000] | forged |
| bitflip_payload | 200/200 | 1.000 [0.982, 1.000] | forged |
| bitflip_tag | 200/200 | 1.000 [0.982, 1.000] | forged |
| replay_in_window | 200/200 | 1.000 [0.982, 1.000] | replay |
| replay_old | 200/200 | 1.000 [0.982, 1.000] | replay |
| reorder_in_window | 200/200 | 1.000 [0.982, 1.000] | ok |
| splice | 200/200 | 1.000 [0.982, 1.000] | forged |
| downgrade | 200/200 | 1.000 [0.982, 1.000] | policy |
| epoch_jump | 200/200 | 1.000 [0.982, 1.000] | policy, kdf +0 |
| flood | 200/200 | 1.000 [0.982, 1.000] | malformed |
| delete (gap) | 200/200 | 1.000 [0.982, 1.000] | max latency 65.536 ms |
| tail truncation | 20/20 | 1.000 [0.832, 1.000] | truncated |

Forgery bound: 2^-128 per attempt (Ascon-AEAD128 tag, 128 bits). Gap bound: 64 packets = 65.536 ms.

Flood cost (µs per datagram, median): junk_header_like_us 5.2, junk_random_us 5.0, passes_header_checks_one_mac_us 1485.2

| T µs | p loss | events delivered (mean) | min |
|---|---|---|---|
| 256 | 0 | 1 | 1 |
| 256 | 0.001 | 0.9991 | 0.9945 |
| 256 | 0.01 | 0.99 | 0.9811 |
| 256 | 0.05 | 0.9484 | 0.9399 |
| 1024 | 0 | 1 | 1 |
| 1024 | 0.001 | 0.9983 | 0.9924 |
| 1024 | 0.01 | 0.989 | 0.9745 |
| 1024 | 0.05 | 0.9524 | 0.9261 |
| 4096 | 0 | 1 | 1 |
| 4096 | 0.001 | 0.9966 | 0.9743 |
| 4096 | 0.01 | 0.9833 | 0.9435 |
| 4096 | 0.05 | 0.9553 | 0.9178 |

Baselines: du2021: all manipulations accepted (no tag); zhang2024: all manipulations accepted (no tag)
