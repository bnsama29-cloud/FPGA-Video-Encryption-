"""Bug #44: the 100 MHz board images ran at 62.5 MHz on the PYNQ-Z2. PYNQ copies the .hwh's FCLK0 dividers
(4 x 4), which assume the 1600 MHz IO PLL of the Vivado project; the board boots with a 1000 MHz IO PLL.
PynqBackend now sets FCLK0 to the clock the image was built for (PCW_ACT_FPGA0_PERIPHERAL_FREQMHZ)."""
import sys
import types
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from system.board import pynq_driver as pd       # noqa: E402

OVERLAY = ROOT / "system" / "board" / "overlay"


@pytest.mark.parametrize("image, mhz", [("secure_jpeg.bit", 100), ("secure_jpeg_lanes.bit", 100),
                                        ("secure_jpeg_lanes_tamper.bit", 100), ("secure_jpeg_lanes4.bit", 125),
                                        ("secure_jpeg_lanes4hd.bit", 125), ("secure_jpeg_lanes4yuyv.bit", 125)])
def test_built_clock_is_read_from_the_hwh(image, mhz):
    if not (OVERLAY / image).with_suffix(".hwh").exists():
        pytest.skip("board images not in this checkout")
    got = pd.built_fclk_mhz(OVERLAY / image)
    assert got == mhz, f"{image}: built clock {got}, expected {mhz}"


def test_built_clock_missing_hwh(tmp_path):
    assert pd.built_fclk_mhz(tmp_path / "none.bit") is None


def test_choose_fclk():
    cases = [  # (built, now, requested) -> target
        ((100, 62.5, None), 100),        # bug #44: put back to the built clock
        ((125, 125.0, None), None),      # already right: leave it
        ((125, 125.0, 100), 100),        # --fclk 100 lowers a 125 MHz image
        ((100, 62.5, 50), 50),
        ((None, 62.5, None), None),      # no .hwh: nothing to go by
    ]
    for (built, now, req), want in cases:
        got = pd.choose_fclk(built, now, req)[0]
        assert got == want, f"built={built}, now={now}, --fclk={req}: got {got}, expected {want}"
    with pytest.raises(ValueError, match="above the 100 MHz"):
        pd.choose_fclk(100, 62.5, 125)


class _Buf(np.ndarray):
    def flush(self):
        pass

    def invalidate(self):
        pass


def _fake_pynq(io_pll_mhz):
    """A pynq module whose Clocks behave like the board: loading copies the .hwh dividers onto this IO PLL,
    and setting fclk0_mhz picks dividers for the requested clock (as pynq.Clocks does)."""
    m = types.ModuleType("pynq")
    state = {}

    class Clocks:
        pass

    def get(_):
        return state["mhz"]

    def put(_, v):
        div = round(io_pll_mhz / v)
        state["mhz"] = io_pll_mhz / div
    Clocks.fclk0_mhz = property(get, put)
    clocks = Clocks()

    class Overlay:
        def __init__(self, bitfile):
            text = Path(bitfile).with_suffix(".hwh").read_text(errors="ignore")
            d0 = int(text.split('NAME="PCW_FCLK0_PERIPHERAL_DIVISOR0" VALUE="')[1].split('"')[0])
            d1 = int(text.split('NAME="PCW_FCLK0_PERIPHERAL_DIVISOR1" VALUE="')[1].split('"')[0])
            state["mhz"] = io_pll_mhz / (d0 * d1)
            self.ip_dict = {"sjpeg_0": {}, "axi_dma_0": {}}
            self.sjpeg_0 = types.SimpleNamespace(read=lambda a: pd.V3_VERSION_BASE + 2 + pd.E5_CAP)
            self.axi_dma_0 = object()

    m.Overlay, m.Clocks = Overlay, clocks
    m.allocate = lambda shape, dtype: np.zeros(shape, dtype).view(_Buf)
    return m, state


@pytest.mark.parametrize("image, mhz", [("secure_jpeg_lanes.bit", 100), ("secure_jpeg_lanes4.bit", 125)])
def test_backend_runs_each_image_at_its_built_clock(monkeypatch, capsys, image, mhz):
    if not (OVERLAY / image).with_suffix(".hwh").exists():
        pytest.skip("board images not in this checkout")
    fake, state = _fake_pynq(io_pll_mhz=1000.0)                # the PYNQ-Z2's IO PLL
    monkeypatch.setitem(sys.modules, "pynq", fake)
    b = pd.PynqBackend(str(OVERLAY / image), max_pixels=64)
    assert state["mhz"] == mhz and b.fabric_hz == mhz * 1e6, \
        f"{image}: FCLK0 {state['mhz']} MHz, fabric_hz {b.fabric_hz}, expected {mhz} MHz"
    if mhz == 100:
        assert "came up at 62.5 MHz" in capsys.readouterr().out
    b = pd.PynqBackend(str(OVERLAY / image), max_pixels=64, fclk_mhz=50)
    assert state["mhz"] == 50 and b.fabric_hz == 50e6
