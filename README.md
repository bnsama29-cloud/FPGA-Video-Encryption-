# Secure video transmission with hardware selective encryption

RVCE Experiential Learning (III Sem, Semiconductor Engineering), team **CMOS Crusaders**:
Aravind R, Suhas VJ, Rishab HR, Samarth BN, Vijaysurya BS. Mentor: Dr. Chetana G.

A JPEG/MJPEG encoder for the PYNQ-Z2 (Zynq-7020) that encrypts selected coefficient bits **inside
the encoder** with NIST Ascon-AEAD128 (SP 800-232) and seals every frame with a 128-bit tag:

* any standard viewer still plays the stream, but without the key the picture is scrambled;
* the key holder verifies the tag and recovers the frame bit-exactly.

Around the encoder there is:

* an authenticated feedback channel and key ratcheting;
* an attack-aware adaptive defence;
* a live web dashboard;
* the experiments behind the paper.

```
camera ─► encoder + Ascon (RTL / golden model) ─► UDP ─► channel (network + attacker) ─► receiver ─► viewer
                     ▲                                                                      │
                     └────────── authenticated feedback (heartbeats, alerts) ◄──────────────┘
                adaptive defence on the ARM: protection level E2..E5, rekey, dead-man rule
```

## Status (21 Oct 2026)

| Part | State |
|---|---|
| Golden model, RTL (single pipeline + 1/2/4 lanes, E0–E5), cocotb + XSim | done, every RTL test bit-exact with the model |
| Vivado run 9 (product stage P) | 30/30 steps; **125 MHz met** (single pipeline +0.060 ns, 2 lanes +0.213 ns); every PYNQ-Z2 system meets 100 MHz, **including 4 lanes** (18,683 LUT, WNS +0.461 ns) |
| 150 / 166 MHz (the commercial cores' clocks) | RTL done, bit-exact: register slices on the stall chains, keystream ring, packer and zig-zag fixes, timing-driven flow; needs Vivado run 10 |
| Camera-native YUYV input (4 pixels per beat) | RTL + model + driver done, bit-exact for 2 and 4 lanes: 4 lanes 208 Mpixel/s at 100 MHz in simulation, half the DDR bytes |
| 4 lanes with 1080p lines | option done (one line-buffer set per lane: half the BRAM, 2–5 % slower) |
| Board (PYNQ-Z2) | 2-lane E5 bitstream bit-exact with the model on silicon, E0–E5 (A1); first speed numbers (A2) |
| ARM side (PS) | the same encoder in C, bit-exact (A3 baseline, no-bitstream camera node); post-quantum session key (ML-KEM-768 + X25519) |
| Link | decryption in C on the laptop; frame-size padding against the size side channel (`link.pad`) |
| Open | Vivado run 10; on the board: 4-lane image, A2 fabric-only time, A3, A4 power, A5/A6 attacks |

Where we beat the published designs and where we do not yet: **[docs/BENCHMARK_PLAN.md](docs/BENCHMARK_PLAN.md)**.

How the work is split on the Zynq: the **programmable logic** does every per-pixel step (colour
conversion, DCT, quantiser, entropy coding, Ascon encryption and tag); the **ARM processing system**
does the per-frame and per-session work (headers, the E5 segment order, keys and the key exchange,
network, defence policy). See [docs/RUNBOOK.md](docs/RUNBOOK.md) §1.

## Next steps

1. **Vivado run 10** (Vivado PC, overnight, ~5 h): `git pull`, then
   `py vivado\run_vivado_day.py --steps xsim ooc lanes bd_lanes4 power parse --periods 6.667 6.0 --fclk 142 --parallel 2 --jobs 2`
   → 150 / 166 MHz for 1, 2 and 4 lanes, the YUYV and 1080p variants, the 4-lane system at 142.9 MHz. Send the zip.
2. **Board, A1–A3** (~1.5 h): 4-lane smoke test, `first_contact` with 2 and 4 lanes (`--zero-copy`), `arm_baseline`, `pq_kex_cost`.
3. **Board, A4–A6** (~3 h): power meter, then the attack suite with the board as sender (`--pq-kex`, `link.pad=runmax`).
4. **Paper**: copy the results to `paper/data/`, `python paper/make_assets.py`, `make -C paper`, replace the red TODOs.

Exact commands and order: [docs/RUNBOOK.md](docs/RUNBOOK.md) §3.

## Start here

| You want to… | Read |
|---|---|
| every program, which machine it runs on, and the order for the hardware days | **[docs/RUNBOOK.md](docs/RUNBOOK.md)** |
| understand the whole project from the basics, every folder and program, and its status | **[docs/PROJECT_EXPLAINED.md](docs/PROJECT_EXPLAINED.md)** |
| know what is done, what is left, and how to do each remaining task | **[GUIDE.md](GUIDE.md)** |
| run the Vivado flow (XSim, post-route numbers, PYNQ overlay) | [docs/VIVADO_ONE_DAY.md](docs/VIVADO_ONE_DAY.md) |
| bring up the PYNQ-Z2: bit-exact on silicon, fps, power, live link with the dashboard | [docs/BOARD_BRINGUP.md](docs/BOARD_BRINGUP.md) |
| demonstrate the dashboard and MJPEG streams on a LAN / VLC | [docs/DASHBOARD_LAN_DEMO.md](docs/DASHBOARD_LAN_DEMO.md) |
| what is left for the FPGA (150 MHz, YUYV and 1080p images, board power), with the test that says "done" | [docs/HW_TODO.md](docs/HW_TODO.md) |
| every metric against the published designs, and what each idea from other fields became | [docs/BENCHMARK_PLAN.md](docs/BENCHMARK_PLAN.md) |
| read or build the conference paper | [paper/README.md](paper/README.md) |
| see every result table | [paper/data/paper_tables.md](paper/data/paper_tables.md) |
| see the open-data, standard-metric and restart-interval results | [paper/data/extra/README.md](paper/data/extra/README.md) |
| understand the contract (registers, nonce, tag, file format) | [docs/INTERFACES.md](docs/INTERFACES.md) |
| give Claude the project context | [docs/TEAM_CONTEXT.md](docs/TEAM_CONTEXT.md) + GUIDE.md |

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
make test                       # golden model + system + every RTL block in Icarus 12 (~6 min)
make xsim-icarus                # the Vivado testbench, run in Icarus
python -m link.run_all          # whole link + dashboard -> http://localhost:8000
```

## Protection levels

| Mode | Encrypted | In RTL |
|---|---|---|
| E0 | nothing (tag only) | yes |
| E1 | AC sign bits | yes |
| E2 | + DC-difference sign bits (default floor) | yes |
| E3 | + AC amplitude bits | yes |
| E4 | + DC amplitude bits | yes |
| E5 | E4 + keyed shuffle of the 16×16 MCUs (restart interval 1) | yes, lane encoder (contract v3 mode 5: the fabric codes one segment per MCU, the ARM shuffles) |

Sign and amplitude encryption cannot hide *which* coefficients are non-zero, so E1–E4 leak an
outline sketch to an eavesdropper; E5 removes it. The measured numbers are in `paper/data/paper_tables.md`.

## Repository map

See GUIDE.md §3. In short:

| Folder | Contents |
|---|---|
| `model/` | the golden model (the referee) |
| `rtl/` | the Verilog encoder |
| `tb/` | cocotb tests |
| `vivado/` | Vivado flow |
| `link/` | system simulation (sender, channel, receiver with C fast path, dashboard) |
| `experiments/` | every paper number |
| `future_work/` | board kit (`board/`), the encoder on the ARM in C (`arm/`), baselines, attacks, figures, the Kaggle script |
| `paper/` | the IEEE draft and the data it is built from |
| `docs/` | contract, testing, Vivado guide |
