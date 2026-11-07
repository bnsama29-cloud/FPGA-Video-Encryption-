# Several cameras on one machine

Scenario calm.json, 4 CPU cores.

| Cameras | frames verified per camera | latency median (ms) | worst p95 (ms) | false alarms | CPU load |
|---|---|---|---|---|---|
| 1 | 595 | 11 | 65 | 0/59 | 26 % |
| 2 | 588 | 12.0 | 116 | 0/118 | 63 % |
| 4 | 310 | 14.0 | 217 | 0/232 | 100 % |
