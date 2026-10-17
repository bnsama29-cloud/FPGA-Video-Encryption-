# future_work/: code for the board, the baselines, the extra attacks and the paper figures

This folder is code only. **What to do with it, in which order and by whom is in [`GUIDE.md`](../GUIDE.md) §4.**

Run everything from the repository root as `python -m future_work.<folder>.<script>`; every script has
`--help` with examples.

Status key:

* ✅ tested here (in CI: `tests/test_future_work.py`);
* 🧪 needs Vivado or the board to be tested;
* 📝 specified in GUIDE.md, not written yet.

```
future_work/
├── board/
│   ├── pynq_driver.py        ✅ mock / 🧪 board   driver for our IP: register sequence, DMA, readout
│   ├── first_contact.py      ✅ mock / 🧪 board   bit-exact gate on the PYNQ-Z2, then fps   (GUIDE A1-A2)
│   ├── board_sender.py       ✅ mock / 🧪 board   the camera node on the PYNQ, plugs into link/ (GUIDE A5)
│   ├── sjpeg_bd_top.v        ✅ compiles + lints  block-design wrapper with AXI interface attributes
│   └── block_design.tcl      🧪                   Zynq PS + AXI DMA + our IP -> .bit + .hwh (docs/VIVADO_ONE_DAY.md)
├── baselines/
│   ├── bench_software_codecs.py  ✅  libjpeg-turbo, AES-GCM, ChaCha20, selective (Python) per frame (GUIDE A3)
│   ├── energy_table.py           ✅  energy per frame from measured fps and power                  (GUIDE A4)
│   ├── power_template.csv            fill in with board measurements
│   └── c_selective/              📝  selective encryption in C, the fair ARM baseline                (GUIDE B1)
├── attacks/
│   └── jigsaw_attack.py      ✅  greedy jigsaw solver against E5 (stronger solver: GUIDE B9)
├── figures/
│   ├── visual_security_grid.py   ✅  no key / eavesdropper / key holder per mode
│   ├── format_compliance.py      ✅  which decoders open each mode
│   └── paper_tables.py           ✅  every result table from the result files (paper/data/paper_tables.md)
├── kaggle/
│   └── kaggle_runs.py            ✅  every Kaggle run in one cell; JOB = "complete" (whole simulation,
│                                     10 seeds, real video), "remaining" (open clips, Kodak, metrics,
│                                     restart interval, learned attack), "research" (R1-R8), "final"
├── clips_manifest.md             test clips by hash (the clips themselves are never committed)
└── results/                      generated outputs (not in git)
```

**Mock vs board.** `SecureJpegIP(MockBackend())` behaves like the FPGA IP, bit-exact with the RTL, so
the driver, the board sender and the network side work before the bitstream exists. Times measured on
the mock are Python, not FPGA: `first_contact.py` labels them so.

**Untested parts.** `block_design.tcl` and `PynqBackend` have never run on real tools or hardware. The
first errors to expect, and their fixes, are in `docs/VIVADO_ONE_DAY.md` §4 and §5.
