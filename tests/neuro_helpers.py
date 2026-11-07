"""Shared fixtures for the paper-2 model tests (not a test module)."""
import numpy as np

from neuro import evt2, keys, receiver, sender
from neuro.geometry import SENSORS, Geometry

MASTER = bytes(range(16))
CAM, BOOT = 3, 5


def events(n=400, W=128, H=128, t0=1000, t1=6000, seed=0):
    rng = np.random.default_rng(seed)
    ev = np.zeros(n, dtype=evt2.EVENT_DTYPE)
    ev["t"] = np.sort(rng.integers(t0, t1, n))
    ev["x"] = rng.integers(0, W, n)
    ev["y"] = rng.integers(0, H, n)
    ev["p"] = rng.integers(0, 2, n)
    return ev


def stream(n=400, geom=SENSORS["dvsgesture"], T=1024, seed=0, **kw):
    return evt2.encode(events(n, geom.W, geom.H, seed=seed, **kw), T)


def sk(epoch=0):
    return keys.subkeys(MASTER, CAM, BOOT, epoch)


def sid(epoch=0):
    return keys.session_id(CAM, BOOT, epoch)


def seal(words, level=3, b=6, geom=SENSORS["dvsgesture"], T=1024, pad=None, flush=True, ctr0=0):
    cfg = sender.Config(level, b, T, geom, pad)
    return sender.encrypt_stream(words, sk(), sid(), cfg, ctr0=ctr0, flush=flush)


def decryptor(level=3, b=6, geom=SENSORS["dvsgesture"], T=1024, pad=None, **kw):
    prof = receiver.Profile(frozenset({(level, b, None, None)}), geom, T, pad=pad, **kw)
    return receiver.Decryptor({(CAM, BOOT): MASTER}, prof)


__all__ = ["MASTER", "CAM", "BOOT", "events", "stream", "sk", "sid", "seal", "decryptor", "Geometry", "SENSORS"]
