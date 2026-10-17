"""The camera node running on the PYNQ-Z2: the link sender with the FPGA doing the encode.

On the board (PYNQ image, repo copied to the board):
    python3 -m future_work.board.board_sender --bitfile secure_jpeg.bit \\
        --set link.host=<laptop IP> --set link.bind_host=0.0.0.0 --set sender.source=webcam:0

On the laptop (channel + receiver + dashboard, listening on the network):
    python -m link.run_all --no-sender --set link.bind_host=0.0.0.0 --set link.sender_host=<board IP>
    (or start link.channel, link.receiver, link.dashboard separately with the same --set flags)

Without a board (development / tests): --mock uses the golden-model emulation of the IP
(--mock-lanes 2 emulates the lane bitstream secure_jpeg_lanes.bit), so everything except the
FPGA itself can be exercised on a laptop.

Everything else (keys, ratchet, feedback, defence policy, dashboard telemetry) is the
unchanged link/sender.py. The ARM keeps the policy loop; the fabric does the encoding.
E5 needs a lane bitstream that reports it (VERSION bit 7, docs/INTERFACES.md §8.6); with any other
bitstream max_mode is capped at E4. --mock-lanes 2 --mock-e5 emulates such a bitstream.
"""
import argparse

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

    def encode(self, rgb, key, session_id, frame_ctr, mode):
        if (key, session_id) != (self.key, self.sid):      # new session or rekey -> reload registers
            self.ip.setup_session(key, session_id, self.quality)
            self.key, self.sid = key, session_id
        m = MODE_ID[mode]
        scan, tag = self.ip.encode(rgb, m, frame_ctr)
        jpeg = self.ip.build_jpeg(rgb.shape[1], rgb.shape[0], m, frame_ctr, scan, tag)
        # the fabric does not report how many bits it encrypted, so the dashboard's
        # "encrypted bits" reads 0 for the board (cost per mode comes from measure_mode_tradeoff.py)
        return EncodedOut(jpeg, payload_bits=8 * len(scan), enc_bits=0, scan_bytes=len(scan))


def make_board_sender(cfg, bitfile=None, mock=False, mock_lanes=None, mock_e5=False):
    cfg["sender"]["encoder"] = "model"                     # placeholder, replaced below
    if mock_lanes:
        backend = MockBackend(contract=3, lanes=mock_lanes, e5=mock_e5)
    else:
        backend = MockBackend() if mock else PynqBackend(bitfile)
    ip = SecureJpegIP(backend)
    if cfg["defence"]["max_mode"] == "E5" and not ip.e5:
        cfg["defence"]["max_mode"] = "E4"
    s = Sender(cfg)
    s.encoder = BoardEncoder(ip, cfg["sender"]["quality"])
    return s


def main():
    ap = config.add_args(argparse.ArgumentParser(description=__doc__,
                                                 formatter_class=argparse.RawDescriptionHelpFormatter))
    ap.add_argument("--bitfile", default="secure_jpeg.bit")
    ap.add_argument("--mock", action="store_true", help="emulate the IP with the golden model (no board)")
    ap.add_argument("--mock-lanes", type=int, choices=[1, 2, 4],
                    help="emulate the lane bitstream (contract v3) with this many lanes (no board)")
    ap.add_argument("--mock-e5", action="store_true", help="with --mock-lanes: the emulated bitstream has E5")
    a = ap.parse_args()
    cfg = config.load(a.config, a.set)
    make_board_sender(cfg, a.bitfile, a.mock, a.mock_lanes, a.mock_e5).run()


if __name__ == "__main__":
    main()

