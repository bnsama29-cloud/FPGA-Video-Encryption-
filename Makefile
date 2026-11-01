# Secure JPEG/MJPEG encoder -- simulation flow.   Run `make help`.
# Variables: SIM=icarus|verilator  WAVES=1  SEED=<n>  FULL=1  T=<pytest node id>
PY      ?= python3
# the Python packages (model, link, system) are in software/
export PYTHONPATH := $(CURDIR)/software:$(CURDIR)$(if $(PYTHONPATH),:$(PYTHONPATH))
PYTEST  ?= $(PY) -m pytest
RTL_ALL  = skid_buf.v ascon_round.v ascon_aead128_core.v keystream_gen.v tag_unit.v rgb2ycbcr_block.v \
           dct_stage.v dct8x8.v quantiser.v zigzag_rle.v selective_enc.v huffman_enc.v \
           bit_packer.v scan_word_packer.v axil_regs.v secure_jpeg_top.v \
           kseg_unit.v rgb2ycbcr_2px.v yuyv_4px.v byte_fifo.v encoder_lane.v segment_merger.v secure_jpeg_lanes_top.v
LINT_WAIVE = -Wno-UNUSEDSIGNAL -Wno-WIDTHEXPAND -Wno-WIDTHTRUNC

.PHONY: xsim-vectors xsim-icarus help setup tables vectors test test-model test-rtl test-ascon test-crypto test-front \
        test-dct test-entropy test-top full one waves lint lint-strict synth hls-csim \
        bundle demo clean

help:
	@echo "make setup        install Python packages (inside your venv)"
	@echo "make tables       regenerate ROM include files from the model"
	@echo "make vectors      write per-stage golden vectors to hardware/vectors/"
	@echo "make test         full regression (model + every RTL block + top)   ~1 min"
	@echo "make test-model   golden model + contract equivalence (tests/)       ~5 s"
	@echo "make test-rtl     every RTL block + top level in Icarus (hardware/tb/)        ~30 s"
	@echo "make test-ascon | test-crypto | test-front | test-dct | test-entropy | test-top"
	@echo "make full         long run: all 1089 Ascon KATs, 320x240 frames"
	@echo "make one T=hardware/tb/test_dct_quant.py::test_dct8x8 [SEED=n]   one test, full log"
	@echo "make waves T=...  same with waveforms -> gtkwave sim_build/<top>/*.fst"
	@echo "make bundle T=... [SEED=n]   debug_bundle.md for a bug report"
	@echo "make xsim-icarus  Vivado testbench (hardware/vivado/tb_secure_jpeg_top.v) run in Icarus"
	@echo "                  (in Vivado: bash hardware/vivado/run_xsim.sh  or  hardware\\vivado\\run_xsim.bat)"
	@echo "make lint | lint-strict | synth | hls-csim | demo | clean"

setup:
	$(PY) -m pip install -r requirements.txt

tables:
	$(PY) -m model.gen_rtl_tables

vectors:
	$(PY) -m model.gen_vectors

test: test-model test-rtl

test-model:   ; $(PYTEST) -q tests/
test-rtl:     ; $(PYTEST) -q hardware/tb/
test-ascon:   ; $(PYTEST) -q hardware/tb/test_ascon_core.py
test-crypto:  ; $(PYTEST) -q hardware/tb/test_crypto_units.py
test-front:   ; $(PYTEST) -q hardware/tb/test_rgb2ycbcr_block.py
test-dct:     ; $(PYTEST) -q hardware/tb/test_dct_quant.py
test-entropy: ; $(PYTEST) -q hardware/tb/test_entropy.py
test-top:     ; $(PYTEST) -q -s hardware/tb/test_top.py

full:
	FULL=1 $(PYTEST) -q tests/ hardware/tb/

one:
	$(PYTEST) -x -s -q $(T)

waves:
	WAVES=1 $(PYTEST) -x -s -q $(T)

lint:
	cd hardware/rtl && verilator --lint-only -Wall $(LINT_WAIVE) -Iinclude --top-module secure_jpeg_top $(RTL_ALL)
	cd hardware/rtl && verilator --lint-only -Wall $(LINT_WAIVE) -Iinclude --top-module secure_jpeg_lanes_top $(RTL_ALL)
	@echo "lint clean (waived: unused bits, intentional width changes -- see 'make lint-strict')"

lint-strict:
	cd hardware/rtl && verilator --lint-only -Wall -Iinclude --top-module secure_jpeg_top $(RTL_ALL) || true

synth:
	mkdir -p sim_build && yosys -q -s software/scripts/yosys_synth.ys > sim_build/yosys.log
	@grep -E "LUT[1-6]|FD[RSCP]E|DSP48|RAMB|RAM64M|CARRY4" sim_build/yosys_utilisation.txt

hls-csim: vectors
	mkdir -p sim_build && g++ -std=c++14 -O2 -Wno-unknown-pragmas -Wno-unused-label \
	  -Ihardware/hls -Ihardware/hls/shim hardware/hls/dct_quant.cpp hardware/hls/tb_dct_quant.cpp -o sim_build/hls_csim
	./sim_build/hls_csim hardware/vectors/dct_quant_vectors.txt

# ---- Vivado XSim testbench (hardware/vivado/): same files run in Icarus here and in XSim
XSIM_SRC = $(shell grep '^verilog' hardware/vivado/xsim.prj | awk '{print $$3}' | sed 's#^../../#hardware/#; s#^../#hardware/vivado/#')
xsim-vectors:
	$(PY) hardware/vivado/run_vivado_day.py vectors $(ARGS)

xsim-icarus: xsim-vectors
	mkdir -p sim_build && iverilog -g2005 -o sim_build/tb_xsim.vvp -Ihardware/rtl/include $(XSIM_SRC)
	vvp -n sim_build/tb_xsim.vvp +VEC_DIR=hardware/vivado/xsim_work | tee sim_build/xsim_icarus.log | grep -E "^frame|RESULT|ERROR"
	$(PY) hardware/vivado/run_vivado_day.py check
	$(PY) hardware/vivado/run_vivado_day.py vectors --v3 --modes 2 5
	vvp -n sim_build/tb_xsim.vvp +VEC_DIR=hardware/vivado/xsim_work_v3 | tee sim_build/xsim_icarus_v3.log | grep -E "^frame|RESULT|ERROR"
	$(PY) hardware/vivado/run_vivado_day.py check --dir hardware/vivado/xsim_work_v3
	$(PY) hardware/vivado/run_vivado_day.py vectors --v3 --lanes 4 --modes 2 5
	vvp -n sim_build/tb_xsim.vvp +VEC_DIR=hardware/vivado/xsim_work_v3l4 | tee sim_build/xsim_icarus_v3l4.log | grep -E "^frame|RESULT|ERROR"
	$(PY) hardware/vivado/run_vivado_day.py check --dir hardware/vivado/xsim_work_v3l4

bundle:
	$(PY) software/scripts/tools.py bundle $(T) $(if $(SEED),--seed $(SEED))

demo:
	$(PY) software/scripts/tools.py encode-image --out sim_out/demo

clean:
	rm -rf sim_build sim_out results.xml hardware/tb/*.result.xml debug_bundle.md hls_dct_quant .pytest_cache \
	       hardware/tb/__pycache__ software/model/__pycache__ hardware/tb/sim_build
