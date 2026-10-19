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

## Start here

| You want to… | Read |
|---|---|
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
make test                       # golden model + system + every RTL block in Icarus 12 (~1 min)
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
| `link/` | system simulation |
| `experiments/` | every paper number |
| `future_work/` | board kit, baselines, attacks, figures, the Kaggle script |
| `paper/` | the IEEE draft and the data it is built from |
| `docs/` | contract, testing, Vivado guide |
