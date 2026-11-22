"""PynqBackend (paper-2 board driver) against a fake of pynq: Overlay, AXI DMA channels and cacheable buffers.

The fake keeps a separate "device memory" behind every buffer: the DMA reads input from it and writes packets into
it, and the ARM side only sees them through flush() / invalidate(), as on the Zynq. The encryptor behind the fake
DMA is MockBackend (the golden model). So a driver that forgets a cache operation, loses a packet, stops the receive
channel mid-transfer or re-arms a busy channel fails here before the first board run.
"""
import sys
import types

import numpy as np
import pytest

from neuro import vectors as V
from system.board.neuro import nv_driver as D
from system.board.neuro import nv_first_contact as FC


class Buf(np.ndarray):
    """A cacheable PYNQ buffer: CPU view (this array) and device memory (root._dev) differ until flush/invalidate."""

    def __array_finalize__(self, obj):
        self._root = getattr(obj, "_root", None)

    def _off(self):
        return (self.__array_interface__["data"][0] - self._root.__array_interface__["data"][0]) // self.itemsize

    def flush(self):
        o = self._off()
        self._root._dev[o:o + len(self)] = np.asarray(self)

    def invalidate(self):
        o = self._off()
        np.copyto(np.asarray(self), self._root._dev[o:o + len(self)])


def allocate(shape, dtype):
    b = np.zeros(shape, dtype).view(Buf)
    b._root = b
    b._dev = np.full(shape, 0xDEADBEEF, dtype)          # device memory starts different from the CPU view
    return b


class Chan:
    def __init__(self, dev, send):
        self.dev, self.send, self.busy, self.buf = dev, send, False, None

    def transfer(self, buf):
        if self.busy:
            raise RuntimeError("DMA channel not idle")      # what pynq raises on a busy channel
        if self.send:
            o = buf._off()
            words = buf._root._dev[o:o + len(buf)].copy()    # the DMA reads memory, not the CPU cache
            self.dev.m.out += self.dev.m.enc.push(words)
        else:
            self.busy, self.buf = True, buf

    @property
    def idle(self):
        if self.send:
            return True
        if self.busy and self.dev.m.out:                    # a packet is ready: the transfer completes (tlast)
            p = np.frombuffer(self.dev.m.out.pop(0), dtype="<u4")
            o = self.buf._off()
            self.buf._root._dev[o:o + len(p)] = p
            self.dev.length = 4 * len(p)
            self.busy = False
        return not self.busy

    def wait(self):
        if not self.idle:
            raise AssertionError("wait() on a busy channel: pynq would block forever (paper-1 bug #32)")

    def stop(self):
        raise AssertionError("receive channel stopped mid-transfer")


class Dev:
    def __init__(self):
        self.m = D.MockBackend()
        self.length = 0
        dev = self

        class Mmio:
            def read(self, a):
                return dev.length if a == 0x58 else 0
        self.dma = types.SimpleNamespace(sendchannel=Chan(self, True), recvchannel=Chan(self, False), mmio=Mmio())
        self.nv = types.SimpleNamespace(read=self.m.read, write=self.m.write)


def fake_module():
    """A fresh pynq stand-in: every Overlay() is a freshly loaded bitstream (a new device)."""
    mod = types.ModuleType("pynq")

    def overlay(path):
        dev = Dev()
        return types.SimpleNamespace(nv=dev.nv, dma=dev.dma)
    mod.Overlay = overlay
    mod.allocate = allocate
    mod.Clocks = types.SimpleNamespace(fclk0_mhz=100.0)
    return mod


@pytest.fixture
def fake_pynq(monkeypatch):
    monkeypatch.setitem(sys.modules, "pynq", fake_module())


@pytest.mark.parametrize("case", V.cases(), ids=lambda c: c.name)
def test_every_first_contact_case_is_bit_exact_through_the_pynq_backend(fake_pynq, tmp_path, case):
    ip = D.NvIP(D.PynqBackend(tmp_path / "nv.bit", max_words=64, max_packet_bytes=4096, quiet_s=0.0))
    ok, msg = FC.run_case(ip, case)
    assert ok, f"{case.name}: {msg}"


def test_missing_cache_operations_are_caught(fake_pynq, tmp_path):
    """The fake must fail a driver without flush / invalidate, or the test above proves nothing."""
    case = next(c for c in V.cases() if c.name == "dvsgesture_v3")
    for method in ("flush", "invalidate"):
        orig = getattr(Buf, method)
        setattr(Buf, method, lambda self: None)
        try:
            ip = D.NvIP(D.PynqBackend(tmp_path / "nv.bit", max_words=64, max_packet_bytes=4096, quiet_s=0.0))
            ok, msg = FC.run_case(ip, case)
        finally:
            setattr(Buf, method, orig)
        assert not ok, f"no {method}: still bit-exact ({msg})"


def test_pl_busy_rate_excludes_input_gaps():
    from system.board.neuro.nv_replay import pl_busy_rate
    c = {"WORDS_IN": 800, "CYCLES": 2000, "IN_WAIT": 1000}
    assert pl_busy_rate(c, 100.0) == pytest.approx(800 * 100e6 / 1000)       # 0.8 words/clk at 100 MHz
    assert pl_busy_rate({**c, "IN_WAIT": 0xFFFFFFFF}, 100.0) is None           # saturated: not reported
    assert pl_busy_rate({**c, "CYCLES": 0}, 100.0) is None


def test_push_does_not_wait_for_quiet(fake_pynq, tmp_path, monkeypatch):
    """A fixed quiet wait per push capped the replay at one chunk per quiet_s; push must not call _collect."""
    b = D.PynqBackend(tmp_path / "nv.bit", max_words=64, max_packet_bytes=4096, quiet_s=10.0)
    ip = D.NvIP(b)
    case = next(c for c in V.cases() if c.name == "dvsgesture_v3")
    ref = V.run_model(case)
    s0 = ref["initial"]
    ip.configure(V.subkeys_for(s0["epoch"]), s0["sid"], FC.cfg_of(s0), s0["ctr0"])
    monkeypatch.setattr(b, "_collect", lambda out: (_ for _ in ()).throw(AssertionError("push waited")))
    ip.push(np.array(ref["steps"][0]["words"], np.uint32))
