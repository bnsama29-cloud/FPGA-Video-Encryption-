"""Is this machine ready to run the project? Prints one line per check, with the fix for anything missing.

    py scripts\\check_setup.py                 laptop (simulation, dashboard, receiver, experiments, paper)
    python3 scripts/check_setup.py --board     on the PYNQ-Z2 (as root, in the PYNQ venv)
    py scripts\\check_setup.py --vivado        the PC that builds the bitstreams

FAIL = the project will not run until it is fixed (exit code 1). WARN = one part is slower or unavailable.
See HOW_TO_RUN.md for the whole sequence.
"""
import argparse
import importlib
import os
import platform
import shutil
import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
WIN = os.name == "nt"
PIP = "py -m pip" if WIN else "python3 -m pip"

# (module, pip name, what needs it)
CORE = [("numpy", "numpy", "everything"), ("PIL", "pillow", "golden model"),
        ("skimage", "scikit-image", "experiments"), ("scipy", "scipy", "experiments"),
        ("cv2", "opencv-python", "video sources, dashboard"), ("matplotlib", "matplotlib", "paper figures"),
        ("cryptography", "cryptography", "key exchange, baselines"), ("pytest", "pytest", "tests")]
RTL = [("cocotb", "cocotb==2.1.0"), ("cocotbext.axi", "cocotbext-axi==0.1.28")]
TCP_PORTS = [8000]
UDP_PORTS = [47000, 47001, 47002, 47003, 47004, 47005, 47006, 47010]

RESULTS = []


def res(level, name, detail="", fix=""):
    RESULTS.append((level, name, detail, fix))
    print(f"  {level:<4}  {name}" + (f": {detail}" if detail else "") + (f"\n        fix: {fix}" if fix else ""))


def has(mod):
    try:
        importlib.import_module(mod)
        return True
    except Exception:                                   # noqa: BLE001 -- any import failure means "missing"
        return False


def python_ok():
    v = sys.version_info
    if v < (3, 10):
        res("FAIL", "Python", platform.python_version(), "install Python 3.10 or newer (3.12 recommended)")
    else:
        res("ok", "Python", f"{platform.python_version()} ({sys.executable})")
    if sys.prefix == sys.base_prefix and not os.environ.get("VIRTUAL_ENV"):
        res("WARN", "virtual environment", "not active",
            ".venv\\Scripts\\activate" if WIN else "source .venv/bin/activate")


def packages(board=False):
    need = CORE if not board else [c for c in CORE if c[0] in ("numpy", "PIL", "cryptography")]
    miss = [p for m, p, _ in need if not has(m)]
    if miss:
        res("FAIL", "Python packages", "missing " + ", ".join(miss), f"{PIP} install -r requirements.txt")
    else:
        res("ok", "Python packages", ", ".join(m for m, _, _ in need))
    if not has("tomllib") and not has("tomli"):
        res("FAIL", "TOML reader", "Python 3.10 needs tomli", f"{PIP} install tomli")
    try:
        from link import keys
        name = keys.mlkem_backend()[0]
        res("ok", "post-quantum key exchange (--pq-kex)", f"ML-KEM-768 from {name}")
    except Exception as e:                              # noqa: BLE001
        res("WARN", "post-quantum key exchange (--pq-kex)", str(e).splitlines()[0], f"{PIP} install kyber-py")


def compiler():
    from link import fastrx
    cc = fastrx._cc()
    if not shutil.which(cc):
        res("WARN", "C compiler", f"'{cc}' not found: the receiver decrypts in Python (E5 at 10 fps lags), "
            "no ARM C baseline", "Windows: install MinGW-w64 gcc (admin: choco install mingw), "
            "open a new window; Linux: sudo apt install gcc")
    elif fastrx.available():
        res("ok", "C compiler", f"{shutil.which(cc)}; fast receiver (link/fastrx.py) builds and loads")
    else:
        err = fastrx.load_error() or "unknown error"
        fix = ("install a 64-bit gcc (admin: choco install mingw), open a new window, check `gcc -dumpmachine` "
               "says x86_64-w64-mingw32 (or set CC=<full path of that gcc.exe>)" if "32-bit" in err
               else f"read the error; try: {cc} -O2 -shared -fPIC -o x.so link/native/sjpeg_rx.c")
        res("WARN", "C compiler", f"{cc} found but link/native/sjpeg_rx.c did not build or load: {err}", fix)


def rtl_tools():
    miss = [p for m, p in RTL if not has(m)]
    res("ok" if not miss else "WARN", "cocotb (RTL tests)", "missing " + ", ".join(miss) if miss else "installed",
        f"{PIP} install -r requirements.txt" if miss else "")
    iv = shutil.which("iverilog")
    if not iv:
        res("WARN", "Icarus Verilog 12 (RTL tests, make test)", "not found: only tests/ runs, not tb/",
            "Linux/WSL: sudo apt install iverilog (Ubuntu 24.04 has 12.0); Windows: run the RTL tests in WSL")
        return
    out = subprocess.run([iv, "-V"], capture_output=True, text=True).stdout.splitlines()
    ver = out[0] if out else "?"
    res("ok" if "version 12" in ver else "WARN", "Icarus Verilog", ver,
        "" if "version 12" in ver else "the testbenches are verified with Icarus 12.0")


def ports():
    busy = []
    for p in TCP_PORTS:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.bind(("127.0.0.1", p))
        except OSError:
            busy.append(f"TCP {p}")
        finally:
            s.close()
    for p in UDP_PORTS:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.bind(("0.0.0.0", p))
        except OSError:
            busy.append(f"UDP {p}")
        finally:
            s.close()
    if busy:
        res("WARN", "network ports", "in use: " + ", ".join(busy),
            "stop the running link.run_all / board_sender (Ctrl+C) or the program holding them")
    else:
        res("ok", "network ports", "TCP 8000 and UDP 47000-47006, 47010 free")
    if WIN:
        res("info", "firewall (LAN or board only)", "allow Python on Private networks once",
            'admin cmd: netsh advfirewall firewall add rule name="secure-link" dir=in action=allow protocol=UDP '
            'localport=47000-47010,47200-47215')


def wsl():
    try:
        if "microsoft" in Path("/proc/version").read_text().lower():
            res("info", "WSL", "fine for simulation and tests; for the board, a phone or a second laptop run from "
                "Windows (WSL's network is private)")
    except OSError:
        pass


def bitstreams(required):
    from scripts import publish_bitstreams as pb
    rows = pb.check(use_manifest=True)
    ok = [r["file"] for r in rows if r["status"] == "ok"]
    bad = [f"{r['file']} ({r['problem']})" for r in rows if r["status"] == "error"]
    level = "ok" if not bad else ("FAIL" if required else "WARN")
    detail = f"{len(ok)} of {len(rows)} present and checked" + ("; " + "; ".join(bad) if bad else "")
    fix = ("on the Vivado PC: py scripts\\publish_bitstreams.py, commit, push; then git pull here "
           "(or copy future_work/board/overlay/ by hand)") if bad else ""
    res(level, "board images (future_work/board/overlay)", detail, fix if required or bad else "")


def key():
    if (ROOT / "configs" / "demo_key.txt").exists():
        res("ok", "demo key", "configs/demo_key.txt (never committed); give the same key to both ends")
    else:
        res("info", "demo key", "none yet: the built-in key is used. For a demo with the board: "
            + ("py scripts\\demo_key.py" if WIN else "python scripts/demo_key.py"))


def board():
    if not has("pynq"):
        res("FAIL", "PYNQ", "pynq not importable", "sudo -i; source /etc/profile.d/pynq_venv.sh  (PYNQ image 3.x)")
    else:
        import pynq
        res("ok", "PYNQ", getattr(pynq, "__version__", "?"))
    if hasattr(os, "geteuid") and os.geteuid() != 0:
        res("FAIL", "root", "loading a bitstream needs root", "sudo -i; source /etc/profile.d/pynq_venv.sh")
    if not str(ROOT).startswith("/home/xilinx"):
        res("info", "repo location", f"{ROOT} (the docs use /home/xilinx/fpga)")


def vivado():
    v = shutil.which("vivado") or shutil.which("vivado.bat")
    if not v:
        res("FAIL", "Vivado", "not on the PATH", 'Windows cmd: call "<Vivado dir>\\settings64.bat" '
            '(e.g. D:\\Program_Files\\AMDDesignTools\\2026.1\\Vivado\\settings64.bat), not in WSL')
    else:
        res("ok", "Vivado", v)
    miss = [p for m, p in (("numpy", "numpy"), ("PIL", "pillow")) if not has(m)]
    if miss:
        res("FAIL", "Python for the XSim step", "missing " + ", ".join(miss), f"{PIP} install numpy pillow")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--board", action="store_true", help="checks for the PYNQ-Z2")
    g.add_argument("--vivado", action="store_true", help="checks for the PC that builds the bitstreams")
    a = ap.parse_args(argv)
    role = "board" if a.board else "vivado" if a.vivado else "laptop"
    print(f"Setup check ({role}), repo {ROOT}")
    python_ok()
    if role == "board":
        packages(board=True)
        board()
        compiler()
        bitstreams(required=True)
    elif role == "vivado":
        vivado()
        bitstreams(required=False)
    else:
        packages()
        compiler()
        rtl_tools()
        ports()
        wsl()
        key()
        bitstreams(required=False)
    fails = [r for r in RESULTS if r[0] == "FAIL"]
    warns = [r for r in RESULTS if r[0] == "WARN"]
    print(f"\n{len(fails)} FAIL, {len(warns)} WARN. " +
          ("Ready: see HOW_TO_RUN.md." if not fails else "Fix the FAIL lines first."))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
