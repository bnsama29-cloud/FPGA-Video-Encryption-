# experiments: one script per result

Each script writes its numbers to `sim_out/` (git-ignored); the snapshot of each finished run is in
`results/`. No number is typed by hand. Run from the repository root, e.g.
`python experiments/scenario.py --help`.

| Script | Result |
|---|---|
| `scenario.py` (`scenarios/*.json`) | Scripted attack scenario against the live link: detection, reaction, false alarms; `--external-sender` with the board as camera |
| `compare_policies.py`, `policy_seeds.py` | Defence policies compared, one run and over seeds |
| `hw_tamper.py` | Bits flipped inside the board after the tag: every tampered frame rejected |
| `measure_mode_tradeoff.py` | Leakage against cost for every protection level (feeds the policy) |
| `benchmark_suite.py` | SVE-Bench: our levels against four published schemes under four attacks (method: `docs/BENCHMARK_METHOD.md`) |
| `standard_metrics.py` | PSNR, SSIM, entropy, adjacent correlation, NPCR/UACI per level |
| `learned_attack.py`, `recognition.py` | Trained U-Net attacker (GPU); person detection on the eavesdropper's picture |
| `sign_recovery.py`, `video_fingerprint.py` | Attacks from the literature: LP sign-bit recovery; video identification from frame sizes |
| `restart_interval.py`, `chosen_plaintext.py` | E5 restart interval and non-zero counting; chosen-plaintext attack on the shuffle |
| `stall_profile.py`, `lanes_rtl_throughput.py`, `parallel_lanes.py` | Cycles per pixel and lane throughput in RTL simulation; lane projection |
| `hw_efficiency.py`, `benchmark_crypto.py`, `pq_kex_cost.py` | Hardware figures of merit; cost per protected frame; cost of the post-quantum key |
| `rate_control.py`, `change_driven.py`, `block_transform.py`, `size_leak.py` | Research suite R3, R4, R6, R7 (`docs/RESEARCH.md`) |

Journal-version experiments (plan and commands: `docs/JOURNAL_RUNBOOK.md`; references: `docs/LITERATURE.md`):

| Script | Result |
|---|---|
| `repeat_runs.py` | X3: the attack suite repeated, 95 % interval per attack (also summarises board runs) |
| `size_overhead.py` | X7: bytes added per level and container, and what padding against the size side channel costs |
| `asic_estimate.py` | X12: ASIC area in gate equivalents (Yosys, sky130 and Nangate 45 nm) |
| `fault_pre_tag.py` | X16: faults before the tag (coefficient, ciphertext) and after it |
| `privacy_metrics.py` | X17: SSIM, LPIPS, edge correlation and face recall in the attacker's pictures |
| `multi_camera.py` (`scenarios/calm.json`) | X22: several cameras on one machine: frames, latency, CPU load |
| `rekey_load.py` (`scenarios/rekey_load.json`) | X25: rekeys while the video runs, with and without loss |
| `benchmark_suite.py` | X19: now also the EtC (Kurihara 2015) and Tang (1996) schemes |

Which folder of `results/` holds each result: `README.md` in the repository root, "Reproducing the results".
