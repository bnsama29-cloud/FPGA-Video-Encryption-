"""N17: PROLEAD robust-probing check of one masked Ascon S-box column (glitches + transitions, first order).

Design under test: hardware/rtl/neuro/nv_ascon_sbox_dom.v, one 5-bit column of nv_ascon_round_dom.v (the round is
bit-sliced: 64 identical columns between share-wise linear layers). Negative control ("textbook"): the same column
with the five ANDs of the specification form b_i = l_i ^ (~u_i & v_i), whose operand pairs share a variable; PROLEAD
must report leakage for it, otherwise the check could not see the flaw that bug #84 fixed.

Flow per variant: Yosys with PROLEAD's cell library (the flow of PROLEAD's yosys/syn/synthesize.sh), then PROLEAD
(order 1, transitional leakage, fixed-vs-random groups, 2,048,000 simulations by default). Writes
sim_out/neuro/n17/prolead.json (per variant: verdict, simulations, last probe, max -log10 p) and the logs.

Needs a PROLEAD build (https://github.com/ChairImpSec/PROLEAD) and yosys:  python experiments/neuro_prolead.py
--prolead-src <PROLEAD checkout with release/PROLEAD>.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))
import neuro_common as C  # noqa: E402

TEXTBOOK = """`default_nettype none
module nv_ascon_sbox_dom (
    input  wire       clk,
    input  wire [4:0] x_s0,
    input  wire [4:0] x_s1,
    input  wire [4:0] r,
    output wire [4:0] y_s0,
    output wire [4:0] y_s1
);
    wire a0_0 = x_s0[0] ^ x_s0[4], a0_1 = x_s1[0] ^ x_s1[4];
    wire a2_0 = x_s0[2] ^ x_s0[1], a2_1 = x_s1[2] ^ x_s1[1];
    wire a4_0 = x_s0[4] ^ x_s0[3], a4_1 = x_s1[4] ^ x_s1[3];
    wire [4:0] l0 = {a4_0, x_s0[3], a2_0, x_s0[1], a0_0};
    wire [4:0] l1 = {a4_1, x_s1[3], a2_1, x_s1[1], a0_1};
    // b_i = l_i ^ (~l_{i+1} & l_{i+2}): operands (x1, a2), (a2, x3), (x3, a4), (a4, a0), (a0, x1)
    wire [4:0] u0 = ~{l0[0], l0[4], l0[3], l0[2], l0[1]};
    wire [4:0] u1 =  {l1[0], l1[4], l1[3], l1[2], l1[1]};
    wire [4:0] v0 = {l0[1], l0[0], l0[4], l0[3], l0[2]};
    wire [4:0] v1 = {l1[1], l1[0], l1[4], l1[3], l1[2]};
    reg [4:0] p00, p01, p10, p11, q0, q1;
    always @(posedge clk) begin
        p00 <= u0 & v0; p11 <= u1 & v1;
        p01 <= (u0 & v1) ^ r; p10 <= (u1 & v0) ^ r;
        q0 <= l0; q1 <= l1;
    end
    wire [4:0] b0 = q0 ^ p00 ^ p01;
    wire [4:0] b1 = q1 ^ p11 ^ p10;
    assign y_s0 = {b0[4], b0[3] ^ b0[2], ~b0[2], b0[1] ^ b0[0], b0[0] ^ b0[4]};
    assign y_s1 = {b1[4], b1[3] ^ b1[2],  b1[2], b1[1] ^ b1[0], b1[0] ^ b1[4]};
endmodule
`default_nettype wire
"""

VARIANTS = {"independent": (ROOT / "hardware/rtl/neuro/nv_ascon_sbox_dom.v", 7), "textbook": (None, 5)}
ROW = re.compile(r"\|\s*(\d+)\s*/\s*(\d+)\s*\|\s*(\S+)\s*\|\s*([\d.einf+-]+)\s*\|\s*(OKAY|LEAKAGE)\s*\|")


def config(n_rand, sims):
    return {
        "performance": {"max_number_of_threads": "half", "minimize_probing_sets": "aggressive"},
        "simulation": {
            "groups": ["5'h$$", "5'h00"],
            "number_of_clock_cycles": 4,
            "always_random_inputs": [f"r[{n_rand - 1}:0]"],
            "output_shares": ["y_s0[4:0]", "y_s1[4:0]"],
            "expected_output": ["5'h$$", "5'h04"],          # S(0) = 0x04 (column bit i = x_i)
            "input_sequence": [{"signals": [{"name": "x_s0[4:0]", "value": "group_in0[4:0]"},
                                            {"name": "x_s1[4:0]", "value": "group_in1[4:0]"}]}],
            "number_of_simulations": sims,
            "number_of_simulations_per_step": min(sims, 128000),
        },
        "hardware": {"clock_signal_name": "clk"},
        "side_channel_analysis": {"order": 1, "transitional_leakage": True},
    }


def parse(log):
    rows = [m.groups() for m in ROW.finditer(log)]
    if not rows:
        raise RuntimeError("no PROLEAD result rows in the log")
    leak = [r for r in rows if r[4] == "LEAKAGE"]
    last = leak[0] if leak else rows[-1]
    return {"verdict": "LEAKAGE" if leak else "OKAY", "simulations": int(last[0]), "probing_sets": int(last[1]),
            "probe": last[2], "max_neg_log10_p": float(last[3]),
            "max_neg_log10_p_all_steps": max(float(r[3]) for r in rows)}


def run_variant(name, src, n_rand, sims, prolead, work):
    d = work / name
    rtl = d / "rtl"
    rtl.mkdir(parents=True, exist_ok=True)
    (rtl / "nv_ascon_sbox_dom.v").write_text(src.read_text() if src else TEXTBOOK)
    lib = prolead / "yosys" / "lib"
    script = (f"read_verilog {rtl}/nv_ascon_sbox_dom.v; read_verilog -lib {lib}/custom_cells.v; "
              f"setattr -set keep_hierarchy 1; synth -top nv_ascon_sbox_dom; "
              f"dfflibmap -liberty {lib}/custom_cells.lib; abc -liberty {lib}/custom_cells.lib; "
              f"setattr -set keep_hierarchy 0; flatten; opt_clean -purge; select nv_ascon_sbox_dom; "
              f"write_verilog -noattr -selected {d}/design.v")
    subprocess.run(["yosys", "-q", "-p", script], check=True)
    (d / "config.json").write_text(json.dumps(config(n_rand, sims), indent=2))
    res = d / "results"
    if res.exists():
        shutil.rmtree(res)
    p = subprocess.run([str(prolead / "release" / "PROLEAD"), "-l", "libs/custom.json", "-n", "custom",
                        "-d", str(d / "design.v"), "-m", "nv_ascon_sbox_dom", "-c", str(d / "config.json"),
                        "-r", str(res)], cwd=prolead, capture_output=True, text=True)
    log = p.stdout + p.stderr
    (d / "prolead.log").write_text(log)
    out = parse(log)
    out.update(fresh_bits=n_rand, netlist_cells=len(re.findall(r"^\s*\w+\s+_\d+_\s*\(", (d / "design.v").read_text(),
                                                                re.M)))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--prolead-src", required=True, help="PROLEAD checkout containing release/PROLEAD")
    ap.add_argument("--simulations", type=int, default=2_048_000)
    ap.add_argument("--variants", nargs="+", default=list(VARIANTS), choices=list(VARIANTS))
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    out = Path(a.out) if a.out else ROOT / "sim_out" / "neuro" / "n17"
    work = out / "work"
    prolead = Path(a.prolead_src).resolve()
    res = {v: run_variant(v, *VARIANTS[v], a.simulations, prolead, work) for v in a.variants}
    for v, r in res.items():
        print(f"{v:12s} {r['verdict']:8s} sims {r['simulations']:>9d}  probe {r['probe']:>14s}  "
              f"-log10 p {r['max_neg_log10_p']:.2f}  fresh bits {r['fresh_bits']}")
    data = {"results": res, "meta": C.meta(a, tool="PROLEAD", order=1, glitches=True, transitions=True,
                                           threshold_neg_log10_p=5.0)}
    out.mkdir(parents=True, exist_ok=True)
    (out / "prolead.json").write_text(json.dumps(data, indent=2))
    print(f"wrote {out / 'prolead.json'}")
    return data


if __name__ == "__main__":
    main()
