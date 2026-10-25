"""Configuration shared by every node of the system simulation.

Defaults live here; configs/default.toml overrides them; command-line flags
(--set section.key=value) override the file. Every node loads the same file,
so ports and keys always agree.
"""
import argparse
import copy
from pathlib import Path

try:
    import tomllib                      # Python 3.11+
except ModuleNotFoundError:             # Python 3.10 (Ubuntu 22.04): pip install tomli
    import tomli as tomllib

ROOT = Path(__file__).resolve().parents[1]

DEFAULTS = {
    "link": {
        "host": "127.0.0.1",     # where to SEND (all on one PC: localhost)
        "bind_host": "",         # where to LISTEN; "" = same as host. Board + laptop: "0.0.0.0"
        "sender_host": "",       # where the sender runs (the board): feedback and dashboard sender commands go here; "" = host
        "video_in": 47000,       # sender -> channel
        "video_out": 47001,      # channel -> receiver
        "fb_in": 47002,          # receiver -> channel (feedback)
        "fb_out": 47003,         # channel -> sender  (feedback)
        "control": 47004,        # dashboard / experiments -> channel and sender (JSON)
        "sender_control": 47005,
        "kex": 47006,            # post-quantum key exchange (link/kex.py), receiver listens
        "bus": [47010],          # telemetry + previews -> dashboard / experiment logger; an entry is a port
                                 # (on bus_host) or "ip:port" (two laptops: telemetry to both screens)
        "bus_host": "",          # where telemetry goes; "" = host. Two-laptop attack setup: the board and
                                 # the attacker send video to the attacker but telemetry to the receiver
        "kex_rx": 0,             # channel kex relay: forward to (host, kex_rx); 0 = same port as kex
        "fragment": 1400,        # UDP payload bytes per fragment (+24 B header < 1472 = Ethernet MTU)
        "pad": "none",           # frame-size padding against the size side channel (link/wire.py
                                 # SizePadder): none | bucket:1024 | runmax | window:100
    },
    "keys": {
        # Pre-shared 128-bit master key (hex). In a product this would come from a
        # key exchange or provisioning; here both ends read it from the config.
        "master": "000102030405060708090a0b0c0d0e0f",
        "session_base": 0,       # 0 = random 48-bit base chosen by the sender at start
        "master_file": "",       # read the master key (hex) from this file instead, e.g. the session
                                 # key of link/kex.py (configs/session_key.txt); keys.master is then unused
    },
    "sender": {
        "source": "synthetic",   # synthetic | <video file> | webcam:<index>
        "width": 320,
        "height": 240,
        "fps": 10.0,
        "quality": 75,
        "mode": "E2",            # starting / base mode
        "encoder": "model",      # model (golden Python) | rtl (Icarus/XSim per frame)
        "policy": "threshold",   # fixed | threshold | bandit
        "preview_every": 1,      # send a preview to the dashboard every N frames
        "loop": True,            # loop video files
    },
    "receiver": {
        "heartbeat_s": 0.5,      # authenticated heartbeat period
        "alert_min_gap_s": 0.2,  # rate limit for immediate alerts
        "max_epoch_jump": 4,     # how far the receiver ratchets forward on its own
        "preview_every": 1,
    },
    "channel": {
        "loss": 0.0,             # benign random packet loss (0..1) per fragment
        "delay_ms": 5.0,
        "jitter_ms": 2.0,
        "reorder": 0.0,          # probability a frame is delayed by one frame time
        "attacker_view_every": 5,  # run the replacement attack on every Nth frame
        "kex_relay": False,      # also relay the post-quantum key exchange (link/kex.py): needed when the
                                 # channel runs on its own laptop between board and receiver
        "kex_tamper_s": 0.0,     # attack on the key exchange: flip one byte of every relayed kex
                                 # message during the first N seconds (each fails its HMAC; the
                                 # exchange only completes once the attacker stops)
    },
    "defence": {
        "window_s": 1.0,
        "deadman_s": 3.0,        # no valid heartbeat for this long -> maximum protection
        "hold_s": 8.0,           # threshold policy: keep escalation this long after evidence
        "rekey_min_interval_s": 10.0,
        "rekey_on_tag_fail": 5,  # tag failures in one window that trigger a rekey
        "max_mode": "E5",        # E5 = E4 + keyed MCU shuffle (model only; capped to E4 with encoder=rtl)
        "epsilon": 0.1,          # bandit exploration rate
        "alpha": 0.05,           # bandit step-size floor (sample average until 1/n < alpha)
        "seed": -1,              # bandit exploration seed; -1 = random each run (set it for repeatable studies)
        "memory_file": "sim_out/bandit_memory.json",
        # Leakage per mode = edge correlation between the original and the best
        # picture an eavesdropper reconstructs without the key (0 = nothing, 1 = all);
        # cost = fraction of payload bits encrypted. Measured on the synthetic CCTV
        # scene with experiments/measure_mode_tradeoff.py (320x240, q75). Re-measure
        # on your own videos and paste the numbers into configs/default.toml.
        "leakage": {"E0": 0.996, "E1": 0.336, "E2": 0.327, "E3": 0.352, "E4": 0.352, "E5": 0.0},
        "cost": {"E0": 0.0, "E1": 0.115, "E2": 0.135, "E3": 0.25, "E4": 0.287, "E5": 0.303},
        "w_switch": 0.02,
        "w_cost": 0.5,
    },
    "dashboard": {
        "bind_host": "127.0.0.1",  # loopback by default; set to 0.0.0.0 for trusted-LAN access
        "http_port": 8000,
    },
}


def _merge(base, over):
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _merge(base[k], v)
        else:
            base[k] = v
    return base


def _parse_value(text):
    try:
        return tomllib.loads(f"v = {text}")["v"]
    except tomllib.TOMLDecodeError:
        return text


def load(path=None, overrides=()):
    """Returns the merged configuration dict."""
    cfg = copy.deepcopy(DEFAULTS)
    path = Path(path) if path else ROOT / "configs" / "default.toml"
    if path.exists():
        _merge(cfg, tomllib.loads(path.read_text()))
    for item in overrides:
        key, _, value = item.partition("=")
        sec, _, name = key.partition(".")
        cfg.setdefault(sec, {})[name] = _parse_value(value)
    if isinstance(cfg["link"]["bus"], int):
        cfg["link"]["bus"] = [cfg["link"]["bus"]]
    mf = cfg["keys"].get("master_file")
    if mf:
        f = Path(mf) if Path(mf).is_absolute() else ROOT / mf
        k = f.read_text().strip()
        if len(bytes.fromhex(k)) != 16:
            raise ValueError(f"{f}: expected 32 hex digits (a 128-bit key)")
        cfg["keys"]["master"] = k
    return cfg


def bind_host(cfg):
    return cfg["link"].get("bind_host") or cfg["link"]["host"]


def sender_host(cfg):
    return cfg["link"].get("sender_host") or cfg["link"]["host"]


def bus_addrs(cfg):
    """Telemetry destinations: a port goes to bus_host (or host), "ip:port" goes where it says."""
    host = cfg["link"].get("bus_host") or cfg["link"]["host"]
    out = []
    for b in cfg["link"]["bus"]:
        if isinstance(b, str) and ":" in b:
            h, _, p = b.rpartition(":")
            out.append((h, int(p)))
        else:
            out.append((host, int(b)))
    return out


def add_args(ap):
    ap.add_argument("--config", help="TOML file (default configs/default.toml)")
    ap.add_argument("--set", action="append", default=[], metavar="SECTION.KEY=VALUE",
                    help="override one setting, e.g. --set sender.mode=E4 (repeatable)")
    return ap


def from_args(description):
    ap = add_args(argparse.ArgumentParser(description=description))
    a = ap.parse_args()
    return load(a.config, a.set), a


def policy_seed(cfg):
    """Bandit seed from defence.seed; None (random) when it is negative or missing."""
    s = cfg["defence"].get("seed", -1)
    return None if s is None or int(s) < 0 else int(s)
