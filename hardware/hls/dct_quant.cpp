// dct_quant.cpp -- bit-exact with model/jpeg.py :: dct2d() + quantise()
// and with rtl/dct8x8.v + rtl/quantiser.v.
#include "dct_quant.h"
#include "dct_coeffs.h"

static int16_t clamp16(int32_t v, int32_t lo, int32_t hi) {
    return (int16_t)(v < lo ? lo : (v > hi ? hi : v));
}

void dct_quant(hls::stream<pix_t> &in, hls::stream<coef_t> &out, const uint32_t rtab[128]) {
#pragma HLS INTERFACE axis port=in
#pragma HLS INTERFACE axis port=out
#pragma HLS INTERFACE s_axilite port=rtab
#pragma HLS INTERFACE s_axilite port=return
    int16_t blk[64], tmp[64], f[64];
#pragma HLS ARRAY_PARTITION variable=blk cyclic factor=8
#pragma HLS ARRAY_PARTITION variable=tmp cyclic factor=8
    uint8_t comp = 0;

read_block:
    for (int i = 0; i < 64; i++) {
#pragma HLS PIPELINE II=1
        pix_t p = in.read();
        blk[i] = (int16_t)p.data - 128;           // level shift
        comp = p.comp;
    }
// stage 1: rows, output transposed: tmp[u*8+y] = (sum_x C[u][x]*blk[y*8+x] + 2^10) >> 11
stage1:
    for (int o = 0; o < 64; o++) {
#pragma HLS PIPELINE II=1
        int u = o >> 3, y = o & 7;
        int32_t acc = 0;
        for (int x = 0; x < 8; x++) acc += (int32_t)DCT_C[u][x] * blk[y * 8 + x];
        tmp[o] = (int16_t)((acc + (1 << 10)) >> 11);
    }
// stage 2: same on the transposed data: f[v*8+u] = (sum_y C[v][y]*tmp[u*8+y] + 2^14) >> 15
stage2:
    for (int o = 0; o < 64; o++) {
#pragma HLS PIPELINE II=1
        int v = o >> 3, u = o & 7;
        int32_t acc = 0;
        for (int y = 0; y < 8; y++) acc += (int32_t)DCT_C[v][y] * tmp[u * 8 + y];
        f[o] = (int16_t)((acc + (1 << 14)) >> 15);
    }
// quantiser: q = sign(F) * ((|F| * R + 2^15) >> 16), DC -1024..1023, AC -1023..1023
quant:
    for (int i = 0; i < 64; i++) {
#pragma HLS PIPELINE II=1
        int32_t F = f[i];
        uint32_t mag = ((uint32_t)(F < 0 ? -F : F) * rtab[(comp ? 64 : 0) + i] + 32768u) >> 16;
        int32_t q = F < 0 ? -(int32_t)mag : (int32_t)mag;
        coef_t c;
        c.data = (i == 0) ? clamp16(q, -1024, 1023) : clamp16(q, -1023, 1023);
        c.comp = comp;
        c.last = (i == 63);
        out.write(c);
    }
}
