"""The generated gate-level figures (paper/figures/netlist/*.v -> fig_*.pdf) must show the real logic:
each one-bit slice is simulated exhaustively in Icarus Verilog and compared with the golden model.
  * ascon_sbox_slice.v, applied to all 64 bit slices and followed by the linear layer, must reproduce
    one round of model/ascon.py :: permutation (which passes the 1089 official KATs);
  * selective_enc_bitslice.v must reproduce bit k of model/hw.py :: encrypt_symbol for every mode,
    DC/AC, size and keystream."""
import random
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from model import ascon, hw  # noqa: E402

NET = ROOT / "paper" / "figures" / "netlist"
pytestmark = pytest.mark.skipif(shutil.which("iverilog") is None, reason="needs Icarus Verilog")


def truth_table(tmp, module, inputs, outputs, sources=None):
    """Simulate `module` for every input combination; returns {input tuple: output tuple}."""
    n = len(inputs)
    tb = tmp / "tb.v"
    regs = "\n".join(f"  reg {i};" for i in inputs)
    wires = "\n".join(f"  wire {o};" for o in outputs)
    conns = ", ".join(f".{p}({p})" for p in inputs + outputs)
    assign = "\n".join(f"      {inp} = v[{n - 1 - k}];" for k, inp in enumerate(inputs))
    shows = " ".join("%b" for _ in outputs)
    tb.write_text(f"""`timescale 1ns/1ps
module tb;
{regs}
{wires}
  integer v;
  {module} dut ({conns});
  initial begin
    for (v = 0; v < {1 << n}; v = v + 1) begin
{assign}
      #1 $display("%0d {shows}", v, {", ".join(outputs)});
    end
    $finish;
  end
endmodule
""")
    exe = tmp / "sim.vvp"
    srcs = [str(x) for x in (sources or [NET / f"{module}.v"])]
    subprocess.run(["iverilog", "-g2005", "-o", str(exe), str(tb), *srcs], check=True)
    out = subprocess.run(["vvp", "-n", str(exe)], check=True, capture_output=True, text=True).stdout
    table = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) == len(outputs) + 1 and parts[0].isdigit():
            v = int(parts[0])
            table[tuple((v >> (n - 1 - k)) & 1 for k in range(n))] = tuple(int(b) for b in parts[1:])
    assert len(table) == 1 << n
    return table


def test_ascon_slice_figure_is_one_round_of_the_model(tmp_path):
    ins = ["x0", "x1", "x2", "x3", "x4", "rc_j"]
    tt = truth_table(tmp_path, "ascon_sbox_slice", ins, ["c0", "c1", "c2", "c3", "c4"])
    rng = random.Random(1)
    rotations = [(19, 28), (61, 39), (1, 6), (10, 17), (7, 41)]
    for trial in range(50):
        S = [rng.getrandbits(64) for _ in range(5)]
        rc = ((0xF - 11) << 4) | 11            # permutation(S, 1) runs round 11 only
        C = [0] * 5
        for j in range(64):
            bits = tuple((S[i] >> j) & 1 for i in range(5)) + (((rc >> j) & 1),)
            for i, b in enumerate(tt[bits]):
                C[i] |= b << j
        R = [c ^ ascon._rotr(c, r1) ^ ascon._rotr(c, r2) for c, (r1, r2) in zip(C, rotations)]
        ref = list(S)
        ascon.permutation(ref, 1)
        assert R == ref, f"trial {trial}: slice + linear layer differs from model/ascon.py round 11, state {S}"


def test_selective_enc_slice_figure_matches_encrypt_symbol(tmp_path):
    ins = ["mode2", "mode1", "mode0", "is_dc", "size3", "size2", "size1", "size0",
           "ks0", "ks_k1", "m_k", "m_k1", "amp_k"]
    wrap = tmp_path / "wrap.v"          # scalar ports, so the testbench can drive every bit
    wrap.write_text("""module wrap(input mode2, mode1, mode0, is_dc, size3, size2, size1, size0,
            ks0, ks_k1, m_k, m_k1, amp_k, output amp_out_k);
  selective_enc_bitslice u(.mode({mode2, mode1, mode0}), .is_dc(is_dc), .size({size3, size2, size1, size0}),
      .ks0(ks0), .ks_k1(ks_k1), .m_k(m_k), .m_k1(m_k1), .amp_k(amp_k), .amp_out_k(amp_out_k));
endmodule
""")
    tt = truth_table(tmp_path, "wrap", ins, ["amp_out_k"], [wrap, NET / "selective_enc_bitslice.v"])
    rng = random.Random(2)
    checked = 0
    for mode in range(6):
        for is_dc in (False, True):
            for size in range(1, 12 if is_dc else 11):
                for _ in range(20):
                    amp = rng.getrandbits(size)
                    sym = hw.Sym(is_dc=is_dc, run=0, size=size, amp=amp, eob=False, comp=0)
                    ks = [rng.getrandbits(1) for _ in range(12)]
                    exp = hw.encrypt_symbol(sym, mode, ks[:hw.bits_needed(sym, mode)]).amp
                    for k in range(size):
                        # the RTL's 16-bit window: bit 0 = ks[0], bit k+1 = ks[k+1]; masks from the size
                        key = ((mode >> 2) & 1, (mode >> 1) & 1, mode & 1, int(is_dc),
                               (size >> 3) & 1, (size >> 2) & 1, (size >> 1) & 1, size & 1,
                               ks[0], ks[k + 1], int(k < size), int(k + 1 < size), (amp >> k) & 1)
                        got = tt[key][0]
                        assert got == (exp >> k) & 1, (f"E{mode} dc={is_dc} size={size} amp={amp:b} ks={ks} "
                                                      f"bit {k}: slice {got}, model {(exp >> k) & 1}")
                        checked += 1
    assert checked > 5000
