# system/: the board, the ARM side, baselines, attacks and figure scripts

Everything beyond the encoder RTL and the network layer. Run each script from the repository root as
`python -m system.<folder>.<script>`; every script has `--help`.

```
system/
├── board/                        PYNQ-Z2
│   ├── pynq_driver.py            driver for the encoder IP: register sequence, DMA, cycle counters
│   ├── first_contact.py          bit-exact gate on the board (every level vs the golden model), then timing
│   ├── board_sender.py           the board as the camera node of link/ (key exchange, policy, padding)
│   ├── fast_e5.py, native/       E5 segment order in C (falls back to the model)
│   ├── block_design.tcl          Zynq PS + AXI DMA + encoder -> .bit + .hwh (driven by vivado/run_vivado_day.py)
│   ├── sjpeg_bd_top.v, sjpeg_lanes_bd_top.v   block-design wrappers with AXI interface attributes
│   ├── axis_tamper.v, axil_buttons.v, tamper_pynq_z2.xdc   fault injector after the tag (test equipment)
│   ├── pico_tamper/              optional external trigger for the fault injector (Raspberry Pi Pico)
│   ├── bitstreams.json           the board images and their build hashes
│   └── overlay/                  the board images (.bit + .hwh) with MANIFEST.md
├── arm/
│   ├── sw_encoder.py, native/    the same encoder in C for the Cortex-A9, bit-exact with the model
│   └── arm_baseline.py           timing against libjpeg-turbo alone and with whole-file Ascon / AES-GCM
├── baselines/
│   ├── bench_software_codecs.py  software codecs and ciphers per frame on the host
│   └── energy_table.py           energy per frame from measured fps and power (or Vivado's estimate)
├── attacks/
│   ├── jigsaw_attack.py          greedy jigsaw solver against E5
│   ├── mst_jigsaw.py             minimum-spanning-tree solver with gradient compatibility
│   └── jigsaw_gate.py            check that the solvers work on unencrypted tiles before scoring E5
├── figures/
│   ├── format_compliance.py      which decoders open each level
│   ├── visual_security_grid.py   no key / eavesdropper / key holder, per level
│   └── paper_tables.py           result tables from the result files
├── kaggle/kaggle_runs.py         reruns the GPU and long-CPU experiments in one cloud session
└── clips_manifest.md             the private test clips, identified by SHA-256 (never committed)
```

**Emulated bitstream.** `SecureJpegIP(MockBackend())` answers the register map with the golden model's
bytes, so the driver, the board sender and the network side run without a board
(`python scripts/emulated_board_check.py`). Times measured on the emulation are Python, not FPGA, and
`first_contact.py` labels them so.
