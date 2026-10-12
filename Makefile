# Secure JPEG/MJPEG encoder -- simulation flow.   Run `make help`.
# Variables: SIM=icarus|verilator  WAVES=1  SEED=<n>  FULL=1  T=<pytest node id>
PY      ?= python3
PYTEST  ?= $(PY) -m pytest
RTL_ALL  = ascon_round.v ascon_aead128_core.v keystream_gen.v tag_unit.v rgb2ycbcr_block.v \
           dct_stage.v dct8x8.v quantiser.v zigzag_rle.v selective_enc.v huffman_enc.v \
           bit_packer.v scan_word_packer.v axil_regs.v secure_jpeg_top.v
LINT_WAIVE = -Wno-UNUSEDSIGNAL -Wno-WIDTHEXPAND -Wno-WIDTHTRUNC

.PHONY: help setup tables vectors test test-model test-ascon test-crypto test-front \
        test-dct test-entropy test-top full one waves lint lint-strict synth hls-csim \
        bundle demo clean

help:
	@echo "make setup        install Python packages (inside your venv)"
	@echo "make tables       regenerate ROM include files from the model"
	@echo "make vectors      write per-stage golden vectors to vectors/"
	@echo "make test         full regression (model + every block + top)   ~1 min"
	@echo "make test-model | test-ascon | test-crypto | test-front | test-dct | test-entropy | test-top"
	@echo "make full         long run: all 1089 Ascon KATs, 320x240 frames"
	@echo "make one T=tb/test_dct_quant.py::test_dct8x8 [SEED=n]   one test, full log"
	@echo "make waves T=...  same with waveforms -> gtkwave sim_build/<top>/*.fst"
	@echo "make bundle T=... [SEED=n]   debug_bundle.md to paste into Claude"
	@echo "make lint | lint-strict | synth | hls-csim | demo | clean"

setup:
	$(PY) -m pip install -r requirements.txt

tables:
	$(PY) -m model.gen_rtl_tables

vectors:
	$(PY) -m model.gen_vectors

test:
	$(PYTEST) -q tb/

test-model:   ; $(PYTEST) -q tb/test_model.py
test-ascon:   ; $(PYTEST) -q tb/test_ascon_core.py
test-crypto:  ; $(PYTEST) -q tb/test_crypto_units.py
test-front:   ; $(PYTEST) -q tb/test_rgb2ycbcr_block.py
test-dct:     ; $(PYTEST) -q tb/test_dct_quant.py
test-entropy: ; $(PYTEST) -q tb/test_entropy.py
test-top:     ; $(PYTEST) -q -s tb/test_top.py

full:
	FULL=1 $(PYTEST) -q tb/

one:
	$(PYTEST) -x -s -q $(T)

waves:
	WAVES=1 $(PYTEST) -x -s -q $(T)

lint:
	cd rtl && verilator --lint-only -Wall $(LINT_WAIVE) -Iinclude --top-module secure_jpeg_top $(RTL_ALL)
	@echo "lint clean (waived: unused bits, intentional width changes -- see 'make lint-strict')"

lint-strict:
	cd rtl && verilator --lint-only -Wall -Iinclude --top-module secure_jpeg_top $(RTL_ALL) || true

synth:
	mkdir -p sim_build && yosys -q -s scripts/yosys_synth.ys > sim_build/yosys.log
	@grep -E "LUT[1-6]|FD[RSCP]E|DSP48|RAMB|RAM64M|CARRY4" sim_build/yosys_utilisation.txt

hls-csim: vectors
	mkdir -p sim_build && g++ -std=c++14 -O2 -Wno-unknown-pragmas -Wno-unused-label \
	  -Ihls -Ihls/shim hls/dct_quant.cpp hls/tb_dct_quant.cpp -o sim_build/hls_csim
	./sim_build/hls_csim vectors/dct_quant_vectors.txt

bundle:
	$(PY) scripts/debug_bundle.py $(T) $(if $(SEED),--seed $(SEED))

demo:
	$(PY) scripts/visual_security.py

clean:
	rm -rf sim_build sim_out results.xml tb/*.result.xml debug_bundle.md hls_dct_quant .pytest_cache \
	       tb/__pycache__ model/__pycache__ tb/sim_build
