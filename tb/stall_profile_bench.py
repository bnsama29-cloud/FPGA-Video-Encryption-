"""Stall profile of the encoder pipeline (research R1).

Not a pass/fail test of the design: it measures WHERE the cycles go. The encoder needs about
1.64 cycles per pixel; 4:2:0 sampling sets a floor of 1.5 (one DCT sample per clock, 1.5 samples
per pixel). This monitor watches every internal valid/ready link of secure_jpeg_top during whole
frames and counts, per link, the cycles with a transfer (valid & ready), a stall (valid & !ready:
the consumer is the bottleneck) and a starve (!valid: the producer has nothing). Not collected by pytest (no test_ prefix):
run it through experiments/stall_profile.py, which writes sim_out/stall_profile/.

Signals are read right after RisingEdge, i.e. the values the edge samples (CLAUDE.md).
"""
import json
import os

import cocotb
import numpy as np
from cocotb.triggers import RisingEdge

from common import ROOT
from model.testimage import make_image
from test_top import Encoder, init

# (name, valid, ready) in pipeline order; names as in rtl/secure_jpeg_top.v
LINKS = [("pixels in (s_axis)", "s_axis_tvalid", "s_axis_tready"),
         ("colour conv -> DCT", "c_valid", "c_ready"),
         ("DCT -> quantiser", "d_valid", "d_ready"),
         ("quantiser -> zig-zag/RLE", "q_valid", "q_ready"),
         ("RLE -> selective enc", "r_valid", "r_ready"),
         ("selective enc -> Huffman", "e_valid", "e_ready"),
         ("Huffman -> bit packer", "h_valid", "h_ready"),
         ("bit packer -> word packer", "b_valid", "b_ready"),
         ("scan out (m_axis)", "m_axis_tvalid", "m_axis_tready")]


class Monitor:
    def __init__(self, dut):
        self.sig = [(n, getattr(dut, v), getattr(dut, r)) for n, v, r in LINKS]
        self.clk = dut.clk
        self.on = False
        self.reset()

    def reset(self):
        self.cnt = {n: [0, 0, 0] for n, *_ in LINKS}      # transfer, stall, starve
        self.cycles = 0

    async def run(self):
        while True:
            await RisingEdge(self.clk)
            if not self.on:
                continue
            self.cycles += 1
            for n, v, r in self.sig:
                vv, rr = int(v.value), int(r.value)
                c = self.cnt[n]
                if vv and rr:
                    c[0] += 1
                elif vv:
                    c[1] += 1
                else:
                    c[2] += 1


@cocotb.test()
async def profile(dut):
    enc = await init(dut)
    dut.m_axis_tready.value = 1
    await enc.setup_session(bytes(16), 1, 75)
    mon = Monitor(dut)
    cocotb.start_soon(mon.run())
    w, h = [int(x) for x in os.getenv("PROFILE_SIZE", "128x96").split("x")]
    images = os.getenv("PROFILE_IMAGES", "scene,noise,bars").split(",")
    modes = [int(m) for m in os.getenv("PROFILE_MODES", "0,2,4").split(",")]
    out, ctr = [], 1
    for kind in images:
        img = make_image(w, h, kind, seed=1)
        await enc.encode(img, 2, ctr)                   # warm-up (first frame after setup)
        ctr += 1
        for mode in modes:
            mon.reset()
            mon.on = True
            scan, tag, cycles = await enc.encode(img, mode, ctr)
            mon.on = False
            ctr += 1
            out.append(dict(image=kind, mode=mode, width=w, height=h, pixels=w * h,
                            cycles=mon.cycles, cycles_per_pixel=mon.cycles / (w * h),
                            scan_bytes=len(scan),
                            links={n: dict(transfer=c[0], stall=c[1], starve=c[2]) for n, c in mon.cnt.items()}))
            dut._log.info("%s E%d: %d cycles, %.3f cycles/pixel, %d scan bytes",
                          kind, mode, mon.cycles, mon.cycles / (w * h), len(scan))
    dest = ROOT / "sim_out" / "stall_profile"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "raw.json").write_text(json.dumps(out, indent=1))

