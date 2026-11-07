# Several cameras on one machine

Scenario calm.json, 8 CPU cores.

| Cameras | frames verified per camera | latency median (ms) | worst p95 (ms) | false alarms | CPU load |
|---|---|---|---|---|---|
| 1 | 533 | 12 | 2189 | 2/58 | - |
| 2 | 386 | 12.0 | 119 | 0/116 | - |
| 4 | 348 | 12.0 | 135 | 0/232 | - |
| 8 | 229 | 14.0 | 244 | 0/461 | - |
