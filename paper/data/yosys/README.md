# Yosys resource estimate (until the Vivado numbers exist)

* `yosys_secure_jpeg_top.txt`: `yowasp-yosys -s scripts/yosys_synth.ys` (= `make synth`), the whole
  encoder flattened, `synth_xilinx -family xc7`.
* `yosys_keystream_gen.txt`, `yosys_tag_unit.txt`: the same flow with `-top keystream_gen` /
  `-top tag_unit` (`block.ys`, with the top name replaced). Each block contains its own Ascon core.

This is an **estimate** (no place and route, no timing). The paper labels it so, and
`paper/make_assets.py` switches to the Vivado post-route numbers automatically once
`paper/data/vivado/vivado_results.json` exists (GUIDE.md §4.1). Yosys 0.70 (yowasp build); the
hierarchical (non-flattened) run and the `selective_enc` block crash in ABC9 under this build.
