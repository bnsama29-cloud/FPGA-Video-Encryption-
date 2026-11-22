# N2_vivado_169f7e3

Vivado 2026.1 on the laptop (xc7z020clg400-1), 22 Nov 2026: `hardware/vivado/neuro/run_vivado_neuro.py --steps blocks bd parse
--jobs 1 --resume` (RTL stamp 044527473a90; the `ooc`/`usweep` builds of 16-17 Nov reused, verified from the same
RTL), then `experiments/neuro_hw_tables.py` at commit `169f7e3` (bug #78). Copied unchanged:
`sim_out/neuro/n2/hw_tables.{md,json}` and the PYNQ-Z2 overlay reports (`overlay/`, from
`software/system/board/overlay/neuro/`; bd log: `RESULT overlay fclk=100MHz U=2 WNS=0.382ns`). Hashes: `MANIFEST.md`.
