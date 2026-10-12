// tb_dct_quant.cpp -- C testbench: reads vectors/dct_quant_vectors.txt (from
// `python -m model.gen_vectors`) and checks every block bit-exactly.
// Used for both C simulation and C/RTL co-simulation in Vitis HLS.
#include <cstdio>
#include <cstring>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>
#include "dct_quant.h"

int main(int argc, char **argv) {
    const char *path = argc > 1 ? argv[1] : "vectors/dct_quant_vectors.txt";
    std::ifstream f(path);
    if (!f) { std::printf("cannot open %s (run: python -m model.gen_vectors)\n", path); return 1; }
    uint32_t rtab[128];
    std::string line, tok;
    int blocks = 0, errors = 0;
    while (std::getline(f, line)) {
        std::istringstream s(line);
        s >> tok;
        if (tok == "RECIP") {
            for (int i = 0; i < 128; i++) s >> rtab[i];
            continue;
        }
        int comp, v;
        s >> comp;
        hls::stream<pix_t> in;
        hls::stream<coef_t> out;
        for (int i = 0; i < 64; i++) {
            s >> v;
            pix_t p; p.data = (uint8_t)v; p.comp = (uint8_t)comp; p.last = (i == 63);
            in.write(p);
        }
        s >> tok;                                   // "Q"
        dct_quant(in, out, rtab);
        for (int i = 0; i < 64; i++) {
            s >> v;
            coef_t c = out.read();
            if (c.data != v || c.comp != comp || c.last != (i == 63)) {
                if (errors < 10)
                    std::printf("block %d index %d: got %d expected %d\n", blocks, i, c.data, v);
                errors++;
            }
        }
        blocks++;
    }
    std::printf("%d blocks checked, %d mismatches -> %s\n", blocks, errors, errors ? "FAIL" : "PASS");
    return errors ? 1 : 0;   // non-zero return makes Vitis HLS csim/cosim fail
}
