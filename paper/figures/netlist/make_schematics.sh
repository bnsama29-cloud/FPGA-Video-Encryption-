#!/bin/sh
# Schematics generated from Verilog (no hand drawing). Yosys elaborates each slice and maps every
# operator to one gate WITHOUT logic optimisation, so the drawing shows the RTL's structure; netlistsvg
# lays it out. Needs: pip install yowasp-yosys cairosvg; npm install netlistsvg.
#   sh paper/figures/netlist/make_schematics.sh      (from the repo root)
set -e
cd "$(dirname "$0")"
YOSYS=${YOSYS:-yowasp-yosys}
NETLISTSVG=${NETLISTSVG:-netlistsvg}
# Ascon S-box slice: 1-bit operators -> exactly one gate each (11 XOR, 5 AND, 6 NOT)
$YOSYS -q -p "read_verilog ascon_sbox_slice.v; hierarchy -top ascon_sbox_slice; proc; techmap; opt_clean -purge; write_json ascon_sbox_slice.json"
# encryption bit slice: keep the RTL operators (>=, ?:, |size, &, ^) as cells, as Vivado's RTL schematic does
$YOSYS -q -p "read_verilog selective_enc_bitslice.v; hierarchy -top selective_enc_bitslice; proc; opt_clean -purge; write_json selective_enc_bitslice.json"
for top in selective_enc_bitslice ascon_sbox_slice; do
  $NETLISTSVG $top.json -o $top.svg
  python3 -c "import cairosvg; cairosvg.svg2pdf(url='$top.svg', write_to='../fig_$top.pdf')"
done
