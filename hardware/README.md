# hardware: the encoder RTL, its testbenches and the build flow

The JPEG/MJPEG encoder with in-loop Ascon-AEAD128 selective encryption for the Zynq-7020 (PYNQ-Z2).
Every block is bit-exact with the golden model in `software/model/`.

| Folder | Contents |
|---|---|
| `rtl/` | The encoder in Verilog-2001: single pipeline (`secure_jpeg_top.v`, contract v2) and the lane encoder for 1, 2 or 4 lanes with E5 (`secure_jpeg_lanes_top.v`, contract v3). Ascon core, keystream generator, tag unit, colour conversion, DCT, quantiser, zig-zag/RLE, selective encryption, Huffman, packer, AXI4-Lite registers. `include/*.vh` are generated from the model (`make tables`); never edit them. |
| `tb/` | cocotb testbenches (Icarus Verilog 12) for every block and both top levels, with random back-pressure; each reports the first mismatch against the model. `common.py` holds the source lists. |
| `vivado/` | Vivado 2026.1 flow driven by `run_vivado_day.py`: XSim testbench (`tb_secure_jpeg_top.v`, `xsim.prj`), out-of-context place and route (`vivado_ooc.tcl`), power with simulated activity (`power_saif.tcl`), PYNQ-Z2 board images (via `software/system/board/block_design.tcl`), report parser. |
| `hls/` | Vitis HLS version of the DCT and quantiser, C simulation against the same tables (`dct_coeffs.h` is generated). |
| `vectors/` | The official NIST Ascon-AEAD128 known-answer file; per-stage golden vectors are written here by `make vectors` (git-ignored). |

## Commands (from the repository root)

```bash
make test-rtl                                   # every block + both top levels in Icarus (~5 min)
make one T=hardware/tb/test_dct_quant.py::test_dct8x8 SEED=1     # one test, full log
make xsim-icarus                                # the Vivado testbench, run in Icarus
python hardware/vivado/run_vivado_day.py --steps xsim ooc lanes parse        # with Vivado on the PATH
python hardware/vivado/run_vivado_day.py --steps bd_lanes bd_lanes4 parse    # PYNQ-Z2 board images
```

Interfaces, register map, nonce layout and arithmetic: `docs/INTERFACES.md`. Verification method and bug
log: `docs/TESTING.md`. Post-route and RTL-simulation results: `results/hardware/`.
