"""Every RTL signal is declared before its first use (Verilog-2001; XSim's xvlog rejects the rest, TESTING bug #79).

Icarus and Vivado synthesis accepted nv_axil_regs.v reading en_q 30 lines above its declaration; XSim did not
(22 Nov 2026, the N2 power run). Function bodies are skipped: their arguments are local names.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = sorted((ROOT / "hardware/rtl/neuro").glob("*.v")) + [ROOT / "hardware/tb/neuro/tb_nv_power.v"] + \
    [ROOT / "hardware/rtl" / f for f in ("ascon_round.v", "ascon_aead128_core.v", "keystream_gen.v", "skid_buf.v")]
DECL = re.compile(r"^\s*(?:reg|wire|integer|genvar)\b(?:\s+signed)?\s*(?:\[[^\]]*\])?\s*([^;=]+)")


def used_before_declared(text):
    """[(line, name, declared at)] for module-level names read above their declaration."""
    code, in_fn = [], False
    for line in text.split("\n"):
        line = re.sub(r"//.*", "", line)
        if re.match(r"^\s*function\b", line):
            in_fn = True
        code.append("" if in_fn else line)
        if re.match(r"^\s*endfunction\b", line):
            in_fn = False
    declared = {}
    for i, line in enumerate(code):
        m = DECL.match(line)
        if m:
            for name in re.findall(r"\b([A-Za-z_]\w*)\b(?:\s*\[[^\]]*\])?\s*(?:,|$)", m.group(1)):
                declared.setdefault(name, i)
    out = []
    for name, di in declared.items():
        pat = re.compile(r"\b" + re.escape(name) + r"\b")
        for i in range(di):
            if pat.search(code[i]) and not re.match(r"^\s*(input|output|inout)\b", code[i]):
                out.append((i + 1, name, di + 1))
                break
    return out


def test_no_signal_used_before_declaration():
    bad = [(f.relative_to(ROOT).as_posix(), *b) for f in FILES for b in used_before_declared(f.read_text())]
    assert not bad, f"first: {bad[0][0]}:{bad[0][1]} reads '{bad[0][2]}', declared at line {bad[0][3]} ({len(bad)} total)"


def test_checker_sees_the_bug_79_pattern():
    src = "module m;\n  always @* x = en_q;\n  reg en_q;\nendmodule\n"
    assert used_before_declared(src) == [(2, "en_q", 3)]
