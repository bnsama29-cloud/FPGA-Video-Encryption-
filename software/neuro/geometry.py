"""Sensor geometries (DESIGN §2.3).

EVT 2.0 carries x and y in 11-bit fields, so 1 <= W, H <= 2048. The permutation levels V2/V3 need
W >= MIN_PERM_DIM and H >= MIN_PERM_DIM (§2.3); that check lives where the tables are made
(neuro.feistel) and at commit (neuro.sender), not here.

`eventreid` is not in SENSORS: its geometry is read from the dataset files (§2.3), not assumed.
"""
from dataclasses import dataclass

MIN_PERM_DIM = 16
MAX_DIM = 1 << 11            # x, y are 11-bit fields in an EVT 2.0 CD word


@dataclass(frozen=True)
class Geometry:
    name: str
    W: int
    H: int

    def __post_init__(self):
        for f in ("W", "H"):
            v = getattr(self, f)
            if not isinstance(v, int) or not 1 <= v <= MAX_DIM:
                raise ValueError(f"Geometry {self.name!r}: {f} = {v!r} outside 1..{MAX_DIM}")

    @property
    def perm_ok(self):
        """True if V2/V3 are allowed at this geometry (W, H >= 16, §2.3)."""
        return self.W >= MIN_PERM_DIM and self.H >= MIN_PERM_DIM


SENSORS = {g.name: g for g in (
    Geometry("imx636", 1280, 720),
    Geometry("davis346", 346, 260),
    Geometry("cif", 352, 288),
    Geometry("dvsgesture", 128, 128),
    Geometry("nmnist", 34, 34),
    Geometry("vga", 640, 480),
)}


def by_size(W, H):
    """The named sensor with this size, else an unnamed Geometry 'WxH'."""
    for g in SENSORS.values():
        if (g.W, g.H) == (W, H):
            return g
    return Geometry(f"{W}x{H}", W, H)
