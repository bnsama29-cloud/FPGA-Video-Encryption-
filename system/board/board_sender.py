"""The camera node running on the PYNQ-Z2: the link sender with the FPGA doing the encode.

On the board (PYNQ image, repo copied to the board):
    python3 -m system.board.board_sender --bitfile secure_jpeg.bit \\
        --set link.host=<laptop IP> --set link.bind_host=0.0.0.0 --set sender.source=webcam:0

On the laptop (channel + receiver + dashboard, listening on the network):
    python -m link.run_all --no-sender --set link.bind_host=0.0.0.0 --set link.sender_host=<board IP>
    (or start link.channel, link.receiver, link.dashboard separately with the same --set flags)

Without a board (development / tests): --mock uses the golden-model emulation of the IP
(--mock-lanes 2 emulates the lane bitstream secure_jpeg_lanes.bit), so everything except the
FPGA itself can be exercised on a laptop. --software 2 runs the same encoder (bit-exact, C) on the two
ARM cores of the processing system instead of the fabric: the PS-only configuration and the A3 baseline.

Everything else (keys, ratchet, feedback, defence policy, dashboard telemetry) is the
unchanged link/sender.py. The ARM keeps the policy loop; the fabric does the encoding.
E5 needs a lane bitstream that reports it (VERSION bit 7, docs/INTERFACES.md §8.6); with any other
bitstream max_mode is capped at E4. --mock-lanes 2 --mock-e5 emulates such a bitstream.
"""
import argparse
import random

from link import config
from link.backends import EncodedOut
from link.sender import Sender
from model.selective import MODE_ID

from .pynq_driver import MockBackend, PynqBackend, SecureJpegIP


class BoardEncoder:
    """Same interface as link/backends.py encoders: encode(rgb, key, sid, ctr, mode) -> EncodedOut."""
    name = "board"

    def __init__(self, ip, quality):
        self.ip, self.quality = ip, quality
        self.key = self.sid = None
        self.tamper = None

    def encode(self, rgb, key, session_id, frame_ctr, mode):
        if (key, session_id) != (self.key, self.sid):      # new session or rekey -> reload registers
            self.ip.setup_session(key, session_id, self.quality)
            self.key, self.sid = key, session_id
        m = MODE_ID[mode]
        scan, tag = self.ip.encode(rgb, m, frame_ctr)
        if self.tamper is not None:
            scan = self.tamper.apply(scan)
        jpeg = self.ip.build_jpeg(rgb.shape[1], rgb.shape[0], m, frame_ctr, scan, tag)
        # the fabric does not report how many bits it encrypted, so the dashboard's
        # "encrypted bits" reads 0 for the board (cost per mode comes from measure_mode_tradeoff.py)
        return EncodedOut(jpeg, payload_bits=8 * len(scan), enc_bits=0, scan_bytes=len(scan))


class MockTamper:
    """Laptop rehearsal of the tamper injector (system/board/axis_tamper.v, secure_jpeg_lanes_tamper.bit):
    a "tamper_shot" command on the sender's control port flips one bit of the next frame's scan, after the
    tag, never in a marker byte (same rule as the RTL). Real hardware: the Pico or BTN0, not this."""

    def __init__(self, seed=None):
        self.pending = 0
        self.applied = 0
        self.rng = random.Random(seed)

    def shot(self, _cmd=None):
        self.pending = 1

    def apply(self, scan):
        if not self.pending:
            return scan
        mask = 1 << self.rng.randrange(8)
        ok = [i for i in range(4, len(scan), 4)
              if scan[i] != 0xFF and scan[i - 1] != 0xFF and scan[i] ^ mask != 0xFF]
        if not ok:
            return scan                                    # no safe byte: wait for the next frame
        i = self.rng.choice(ok[:16])
        self.pending = 0
        self.applied += 1
        return scan[:i] + bytes([scan[i] ^ mask]) + scan[i + 1:]


MODES = ["E0", "E1", "E2", "E3", "E4", "E5"]


class ButtonLevels:
    """BTN1..BTN3 of secure_jpeg_lanes_tamper.bit (system/board/axil_buttons.v) -> the sender's existing
    "mode" command, the same one the dashboard sends: BTN1 one level down, BTN2 one level up (up to what the
    bitstream offers), BTN3 back to the automatic policy. The level still goes through the sender (MODE
    register + authenticated APP11 header) and takes effect at the next defence window (defence.window_s).
    read_count() returns the COUNT register: 8-bit press counters of BTN1, BTN2, BTN3 in bits 0, 8, 16."""

    def __init__(self, sender, read_count, top="E5", log=print):
        self.sender, self.read_count, self.top, self.log = sender, read_count, top, log
        self.last = read_count()                       # presses before the start do not count

    def poll(self):
        c = self.read_count()
        for b in range(3):
            n = ((c >> 8 * b) - (self.last >> 8 * b)) & 0xFF
            for _ in range(n):
                self.press(b + 1)
        self.last = c

    def press(self, b):
        s = self.sender
        cur = MODES.index(s.manual_mode or s.mode)
        if b == 1:
            new = MODES[max(0, cur - 1)]
        elif b == 2:
            new = MODES[min(MODES.index(self.top), cur + 1)]
        else:
            new = None
        s.handle_control({"cmd": "mode", "mode": new, "source": f"BTN{b}"})
        self.log(f"buttons: BTN{b} -> " + (f"manual {new}" if new else "automatic policy"), flush=True)


class MockButtons:
    """Laptop rehearsal of axil_buttons.v: {"cmd":"button","n":1..3} on the sender's control port counts as a
    press of BTN<n>. Real hardware: the board's buttons, not this."""

    def __init__(self):
        self.n = [0, 0, 0]

    def press(self, cmd):
        b = int(cmd.get("n", 0))
        if 1 <= b <= 3:
            self.n[b - 1] = (self.n[b - 1] + 1) & 0xFF

    def read_count(self):
        return self.n[0] | self.n[1] << 8 | self.n[2] << 16


def hw_buttons(backend):
    """read_count for the overlay's "buttons" IP, or None when the bitstream has none (every image but the
    tamper image)."""
    ol = getattr(backend, "ol", None)
    if ol is None or "buttons" not in ol.ip_dict:
        return None
    from pynq import MMIO                              # only available on the board
    d = ol.ip_dict["buttons"]
    mm = MMIO(d["phys_addr"], d.get("addr_range", 16))
    if mm.read(0x0) != 0xB7750001:
        print(f"buttons: ID 0x{mm.read(0x0):08x} is not axil_buttons; BTN1..BTN3 not used", flush=True)
        return None
    return lambda: mm.read(0x8)


def start_buttons(sender, read_count, top):
    import threading
    import time
    bl = ButtonLevels(sender, read_count, top)

    def loop():
        while True:
            time.sleep(0.05)
            bl.poll()
    threading.Thread(target=loop, daemon=True).start()
    print(f"buttons: BTN1 level down, BTN2 level up (max {top}), BTN3 automatic policy", flush=True)
    return bl


def make_board_sender(cfg, bitfile=None, mock=False, mock_lanes=None, mock_e5=False, software=0, mock_tamper=False,
                      mock_buttons=False):
    cfg["sender"]["encoder"] = "model"                     # placeholder, replaced below
    if software:                                           # PS only: the C encoder on the A9's cores
        from system.arm.sw_encoder import SoftwareBackend
        backend = SoftwareBackend(contract=3, lanes=2, e5=True, threads=software)
    elif mock_lanes:
        backend = MockBackend(contract=3, lanes=mock_lanes, e5=mock_e5)
    else:
        backend = MockBackend() if mock else PynqBackend(bitfile)
    ip = SecureJpegIP(backend)
    if cfg["defence"]["max_mode"] == "E5" and not ip.e5:
        cfg["defence"]["max_mode"] = "E4"
    s = Sender(cfg)
    s.encoder = BoardEncoder(ip, cfg["sender"]["quality"])
    if mock_tamper:
        s.encoder.tamper = MockTamper()
        s.extra_control["tamper_shot"] = s.encoder.tamper.shot
    read_count = None
    if mock_buttons:
        mb = MockButtons()
        s.extra_control["button"] = mb.press
        read_count = mb.read_count
    elif not (software or mock or mock_lanes):
        read_count = hw_buttons(backend)
    if read_count is not None:
        start_buttons(s, read_count, cfg["defence"]["max_mode"])
    return s


def main():
    ap = config.add_args(argparse.ArgumentParser(description=__doc__,
                                                 formatter_class=argparse.RawDescriptionHelpFormatter))
    ap.add_argument("--bitfile", default="secure_jpeg.bit")
    ap.add_argument("--mock", action="store_true", help="emulate the IP with the golden model (no board)")
    ap.add_argument("--mock-lanes", type=int, choices=[1, 2, 4],
                    help="emulate the lane bitstream (contract v3) with this many lanes (no board)")
    ap.add_argument("--mock-e5", action="store_true", help="with --mock-lanes: the emulated bitstream has E5")
    ap.add_argument("--software", type=int, metavar="THREADS", default=0,
                    help="no bitstream: run the encoder on the ARM cores (system/arm/sw_encoder.py, same bytes)")
    ap.add_argument("--mock-tamper", action="store_true",
                    help="rehearsal without the board: emulate the tamper injector, fired by experiments/hw_tamper.py "
                         "--trigger udp:<this IP> (the real one is secure_jpeg_lanes_tamper.bit + the Pico or BTN0)")
    ap.add_argument("--mock-buttons", action="store_true",
                    help="rehearsal without the board: {\"cmd\":\"button\",\"n\":1..3} on the control port presses "
                         "BTN<n> (the real ones are read from secure_jpeg_lanes_tamper.bit automatically)")
    ap.add_argument("--pq-kex", action="store_true",
                    help="first run the post-quantum key exchange with the laptop (link/kex.py, start the laptop "
                         "with run_all --pq-kex) and encrypt with its session key")
    a = ap.parse_args()
    cfg = config.load(a.config, a.set)
    if a.pq_kex:
        from link import kex
        cfg["keys"]["master"] = kex.run_sender(cfg).hex()
    make_board_sender(cfg, a.bitfile, a.mock, a.mock_lanes, a.mock_e5, a.software, a.mock_tamper,
                      a.mock_buttons).run()


if __name__ == "__main__":
    main()

