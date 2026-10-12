// dct_quant.h -- Vitis HLS 8x8 DCT + quantiser (alternative to rtl/dct8x8.v + rtl/quantiser.v).
#pragma once
#include <stdint.h>
#include <hls_stream.h>

// One sample / coefficient per stream beat. For a Vivado block design with
// AXI DMA you will want hls::axis<> types (real TLAST); these plain structs
// keep the C testbench portable. The arithmetic is what must not change.
struct pix_t  { uint8_t data; uint8_t comp; bool last; };   // last = end of block
struct coef_t { int16_t data; uint8_t comp; bool last; };

// Processes one 8x8 block per call: 64 samples in, 64 quantised coefficients out.
// rtab: 128 reciprocals R = round(65536/Q), [0..63] luma, [64..127] chroma, natural order.
void dct_quant(hls::stream<pix_t> &in, hls::stream<coef_t> &out, const uint32_t rtab[128]);
