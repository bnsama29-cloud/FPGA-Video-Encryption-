"""Re-run one failing test and package everything Claude needs into one file.

Usage:
    python scripts/debug_bundle.py tb/test_dct_quant.py::test_dct8x8
    python scripts/debug_bundle.py tb/test_top.py::test_secure_jpeg_top --seed 1234

Writes debug_bundle.md: environment, the exact command, seed, the failure
message (first mismatch), the log tail, the RTL under test, the matching
golden-model functions and the testbench. Paste or attach it to Claude
together with one sentence on what you changed last.
"""
import argparse
import datetime
import importlib
import inspect
import os
import platform
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tb"))

TEST_TO_TOP = {
    "test_ascon_core": "ascon_aead128_core", "test_keystream_gen": "keystream_gen",
    "test_tag_unit": "tag_unit", "test_rgb2ycbcr_block": "rgb2ycbcr_block",
    "test_dct8x8": "dct8x8", "test_quantiser": "quantiser",
    "test_zigzag_rle": "zigzag_rle", "test_selective_enc": "selective_enc",
    "test_huffman_packer": "huffman_packer", "test_secure_jpeg_top": "secure_jpeg_top",
}
SHARED = {"ascon_round.v", "ascon_aead128_core.v"}
MAX_FILE_LINES = 400

PROMPT = """\
I'm building a hardware JPEG encoder with in-loop selective encryption (Ascon-AEAD128)
for a PYNQ-Z2, verified with cocotb against a Python golden model (the model is
the referee; RTL must match it bit for bit). The test below fails.
What I changed last: <ONE SENTENCE>
Please (1) explain the most likely root cause, pointing at the exact RTL line,
(2) propose the smallest fix, and (3) say how to confirm it (which signal at
which cycle in the waveform). Don't change the golden model unless it disagrees
with the JPEG (ITU-T T.81) or Ascon (NIST SP 800-232) standard.
"""


def sh(cmd):
    try:
        return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30).stdout.strip()
    except Exception as e:                      # noqa: BLE001
        return f"(failed: {e})"


def model_refs(rtl_text):
    """Golden-model functions named in an RTL header: 'Golden model: model/x.py :: f(), g()'."""
    out = []
    for m in re.finditer(r"Golden model:\s*model/(\w+)\.py\s*::\s*([^\n]+)", rtl_text):
        mod = importlib.import_module("model." + m.group(1))
        for name in re.findall(r"(\w+)\(\)", m.group(2)):
            if hasattr(mod, name):
                out.append((f"model/{m.group(1)}.py", name, inspect.getsource(getattr(mod, name))))
    return out


def fenced(lang, text):
    lines = text.splitlines()
    if len(lines) > MAX_FILE_LINES:
        lines = lines[:MAX_FILE_LINES] + [f"... ({len(lines) - MAX_FILE_LINES} more lines cut)"]
    return f"```{lang}\n" + "\n".join(lines) + "\n```\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("test", help="pytest node id, e.g. tb/test_dct_quant.py::test_dct8x8")
    ap.add_argument("--seed", help="reproduce a specific random seed")
    ap.add_argument("--out", default="debug_bundle.md")
    a = ap.parse_args()

    env = dict(os.environ)
    if a.seed:
        env["SEED"] = a.seed
    cmd = [sys.executable, "-m", "pytest", "-x", "-s", "-q", a.test]
    print("running:", " ".join(cmd))
    res = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True)
    log = res.stdout + res.stderr
    (ROOT / "sim_build").mkdir(exist_ok=True)
    (ROOT / "sim_build" / "last_test.log").write_text(log)

    seeds = sorted(set(re.findall(r"re-run with SEED=(\d+)", log)))
    failure = [l for l in log.splitlines()
               if re.search(r"Error|assert|mismatch|differ|FAIL|Timeout|expected|got ", l)]
    func = a.test.split("::")[-1]
    top = TEST_TO_TOP.get(func)

    parts = ["# Debug bundle\n", f"_Generated {datetime.datetime.now():%Y-%m-%d %H:%M}_\n\n",
             "## Prompt (edit the first line)\n\n", PROMPT, "\n## Environment\n\n",
             fenced("text", "\n".join([
                 f"OS: {platform.platform()}", f"Python: {sys.version.split()[0]}",
                 f"cocotb: {sh(sys.executable + ' -c \"import cocotb;print(cocotb.__version__)\"')}",
                 f"simulator: {os.getenv('SIM', 'icarus')} / {sh('iverilog -V 2>&1 | head -1')}",
                 f"git: {sh('git -C ' + str(ROOT) + ' log -1 --oneline 2>/dev/null') or '(not a git repo)'}",
                 f"uncommitted changes: {sh('git -C ' + str(ROOT) + ' status --short 2>/dev/null') or '(none / no git)'}"])),
             "\n## Command\n\n", fenced("bash", ("SEED=" + a.seed + " " if a.seed else "") + " ".join(cmd[1:])),
             f"\nResult: {'PASSED' if res.returncode == 0 else 'FAILED'}; random seed(s): {', '.join(seeds) or 'n/a'}\n",
             "\n## Failure lines\n\n", fenced("text", "\n".join(failure[:40]) or "(none found)"),
             "\n## Log tail\n\n", fenced("text", "\n".join(log.splitlines()[-60:]))]

    if top:
        import common
        files = common.SOURCES[top]
        if top == "secure_jpeg_top":
            files = ["secure_jpeg_top.v"]
            parts.append("\n> Full-system test: localise the failing stage first "
                         "(compare against vectors/ from `python -m model.gen_vectors`), "
                         "then make a bundle for that block's unit test.\n")
        elif top not in ("ascon_aead128_core", "keystream_gen", "tag_unit"):
            files = [f for f in files if f not in SHARED]
        parts.append("\n## RTL under test\n")
        refs = []
        for f in files:
            text = (ROOT / "rtl" / f).read_text()
            parts += [f"\n### rtl/{f}\n\n", fenced("verilog", text)]
            refs += model_refs(text)
        if refs:
            parts.append("\n## Golden model (the referee)\n")
            seen = set()
            for path, name, src in refs:
                if name not in seen:
                    seen.add(name)
                    parts += [f"\n### {path} :: {name}()\n\n", fenced("python", src)]
    test_file = ROOT / a.test.split("::")[0]
    if test_file.exists():
        parts += [f"\n## Testbench {test_file.relative_to(ROOT)}\n\n", fenced("python", test_file.read_text())]

    out = ROOT / a.out
    out.write_text("".join(parts))
    print(f"{'PASSED' if res.returncode == 0 else 'FAILED'} -> wrote {out.relative_to(ROOT)} "
          f"({out.stat().st_size // 1024} KB). Attach it to Claude; full log in sim_build/last_test.log")


if __name__ == "__main__":
    main()
