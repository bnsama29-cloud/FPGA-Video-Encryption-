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
| Vivado run 8 (counters + D3 stage) | 30/30 steps pass; 100 MHz met by every design and both PYNQ-Z2 systems; 125 MHz still fails (v2 −0.487 ns, 2 lanes −0.914 ns) |
| 125 MHz fix (product stage P in both converters) | RTL done and bit-exact; needs Vivado run 9 |
| Board (PYNQ-Z2) | 2-lane E5 bitstream bit-exact with the model on silicon, E0–E5 (A1); first speed numbers (A2) |
| ARM side (PS) | the same encoder in C, bit-exact, for the A3 baseline and a no-bitstream camera node |
| Laptop receiver | decryption in C (`link/fastrx.py`), same results as the model, keeps up with E5 frames from the board |
| Open | A2 fabric-only time (counters), A3, A4 power, A5/A6 attacks with the board, 4-lane board image, 125 MHz |

How the work is split on the Zynq: the **programmable logic** does every per-pixel step (colour
conversion, DCT, quantiser, entropy coding, Ascon encryption and tag); the **ARM processing system**
does the per-frame and per-session work (headers, the E5 segment order, keys, network, defence policy).
See [docs/RUNBOOK.md](docs/RUNBOOK.md) §1.

## Next steps

1. **Vivado run 9** (Vivado PC, ~1.5 h): `py vivado\run_vivado_day.py --steps xsim ooc lanes bd_lanes bd_lanes4 power parse --periods 8.0`
   → 125 MHz check with the product stage, new 2-lane image, and the first **4-lane** PYNQ-Z2 image.
2. **Board, A1–A3** (~1 h): `first_contact` with `--zero-copy`, then `future_work.arm.arm_baseline`.
3. **Board, A4–A6** (~3 h): power meter, then the attack suite with the board as sender.
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
| what is left for the FPGA (125 MHz, power from simulated activity, board power), with the test that says "done" | [docs/HW_TODO.md](docs/HW_TODO.md) |
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
