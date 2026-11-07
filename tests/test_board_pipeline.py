"""Journal board phase: the driver's split encode (encode_start / encode_finish) and the pipelined loop in
first_contact --pipeline. The board itself is checked by first_contact's bit-exact gate; these tests pin
the order of the DMA and START operations and that overlapping the ARM with the fabric changes no byte."""
import numpy as np

from system.board import first_contact as fc
from system.board.pynq_driver import CTRL, MockBackend, PynqBackend, SecureJpegIP
from model import hw
from model.testimage import make_image

KEY = bytes(range(16))
SID = 0x1234_5678_9ABC


class _Channel:
    def __init__(self, name, log):
        self.name, self.log, self.idle = name, log, True

    def transfer(self, buf):
        self.log.append(self.name)

    def wait(self):
        pass


class _Dma:
    def __init__(self, log):
        self.recvchannel = _Channel("arm S2MM (scan out)", log)
        self.sendchannel = _Channel("arm MM2S (pixels in)", log)


def test_start_run_arms_receive_then_start_then_send():
    """S2MM before START (the output only waits on it); MM2S after START, because the lane dealer takes
    pixels whenever a lane is ready and START resets its position (secure_jpeg_lanes_top.v)."""
    log = []
    b = PynqBackend.__new__(PynqBackend)              # no pynq here: only the DMA ordering is under test
    b.dma, b.inbuf, b.outbuf = _Dma(log), np.zeros(16, np.uint32), np.zeros(16, np.uint32)
    b.start_run(8, lambda: log.append("CTRL.START"))
    expected = ["arm S2MM (scan out)", "CTRL.START", "arm MM2S (pixels in)"]
    assert log == expected, f"first difference: got {log}, expected {expected}"


def test_encode_writes_start_once_after_the_frame_registers():
    ip = SecureJpegIP(MockBackend(contract=3, lanes=2, e5=True))
    ip.setup_session(KEY, SID, 75)
    n0 = len(ip.b.writes)
    ip.encode(make_image(64, 48, "scene"), 5, 7)
    starts = [i for i, (a, v) in enumerate(ip.b.writes[n0:]) if a == CTRL and v & 1]
    assert starts == [4], f"CTRL.START at write {starts}, expected [4] (after WIDTH, HEIGHT, FRAME_CTR, _HI)"


def test_split_encode_equals_encode_and_the_model():
    ip = SecureJpegIP(MockBackend(contract=3, lanes=2, e5=True))
    ip.setup_session(KEY, SID, 75)
    img = make_image(64, 48, "scene")
    for mode in range(6):
        a = ip.encode(img, mode, 100 + mode)
        b = ip.encode_finish(ip.encode_start(img, mode, 100 + mode))
        assert a == b, f"mode E{mode}: split encode differs from encode"
        want = hw.encode_frame_v3(img, 75, mode, KEY, 100 + mode, SID)["jpeg"]
        if mode == hw.MODE_E5:                         # the ARM permutes the segments (INTERFACES.md §8.6)
            want = hw.arm_shuffle(want, KEY, SID, 100 + mode)
        got = ip.build_jpeg(64, 48, mode, 100 + mode, *b)
        if got != want:
            i = next(k for k in range(min(len(got), len(want))) if got[k] != want[k])
            raise AssertionError(f"mode E{mode}: first mismatch at byte {i}: got {got[i]:#04x}, "
                                 f"expected {want[i]:#04x}")


def test_pipelined_loop_gives_the_same_jpegs_as_one_by_one():
    ip = SecureJpegIP(MockBackend(contract=3, lanes=4, e5=True))
    ip.setup_session(KEY, SID, 75)
    imgs = [make_image(64, 64, "scene"), make_image(64, 64, "noise"), make_image(64, 64, "bars")]
    for mode in (0, 4, 5):
        one = [ip.build_jpeg(64, 64, mode, 50_000 + i, *ip.encode(x, mode, 50_000 + i))
               for i, x in enumerate(imgs)]
        for zero_copy in (False, True):
            sec, same = fc.pipelined(ip, imgs, 64, 64, mode, zero_copy, one)
            assert same, f"mode E{mode}, zero_copy={zero_copy}: pipelined JPEGs differ from one-by-one"
            assert sec > 0
        assert not fc.pipelined(ip, imgs, 64, 64, mode, False, one[::-1])[1], "a wrong reference must fail"


def test_first_contact_pipeline_flag_on_mock(tmp_path):
    try:
        fc.main(["--mock-lanes", "2", "--mock-e5", "--sizes", "64x48", "--frames", "1", "--timing-frames", "2",
                 "--pipeline", "--out", str(tmp_path)])
    except SystemExit as e:
        assert e.code == 0, "first_contact --pipeline failed on the emulated board"
    import json
    res = json.loads((tmp_path / "first_contact.json").read_text())
    assert res["all_bit_exact"] and all(r["pipe_same_bytes"] for r in res["speed"])
    assert "Pipelined" in (tmp_path / "first_contact.md").read_text()
