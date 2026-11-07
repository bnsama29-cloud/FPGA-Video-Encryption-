"""nv_tag32 + nv_word_fifo + nv_out_mux against software/neuro/sender.py (packet bytes) and
software/neuro/hw.py :: out_words(): V0-V4, with and without padding (bitmap), payload lengths 0..3 mod 4,
random output backpressure, U in {1, 2, 4}. Also checks nv_ascon_core_u against model.ascon through the tags."""
import os

import cocotb
from cocotb.triggers import FallingEdge, Timer
import numpy as np

from common_nv import le, run_sim_nv
from common import rng_for, start
from model import ascon
from neuro import evt2, hw, keys
from neuro.geometry import SENSORS
from neuro.keys import nonce
from neuro.packet import HEADER_LEN, PacketHeader, Trailer
from neuro.pad import FLOOR, PadPolicy
from neuro.sender import Config, encrypt_stream

MASTER = bytes(range(16))
SID = keys.session_id(3, 5, 0)
SK = keys.subkeys(MASTER, 3, 5, 0)


def body_words(raw, level):
    """Pre-tag ordered stream of one sealed packet (plaintext at V4): [(word, last)]."""
    h = PacketHeader.unpack(raw)
    if level == 4:
        pt = ascon.decrypt(SK.aead, nonce(h.session_id, h.packet_ctr, 0), h.pack(), raw[HEADER_LEN:])
        body = hw.words_of(h.pack() + pt)
    else:
        body = hw.words_of(raw[:-16])
    return [(w, int(i == len(body) - 1)) for i, w in enumerate(body)]


def make_packets(rng):
    geom = SENSORS["dvsgesture"]
    out = []
    cases = [(0, 0, None), (1, 0, None), (2, 0, None), (3, 6, None), (4, 0, None), (3, 6, PadPolicy(FLOOR, 2)),
             (4, 0, PadPolicy(FLOOR, 1))]
    for (level, b, pad) in cases:
        n = rng.randrange(5, 60)
        ev = np.zeros(n, dtype=evt2.EVENT_DTYPE)
        ev["t"] = sorted(rng.randrange(640, 640 + 4 * 128) for _ in range(n))
        ev["x"] = [rng.randrange(geom.W) for _ in range(n)]
        ev["y"] = [rng.randrange(geom.H) for _ in range(n)]
        ev["p"] = [rng.randrange(2) for _ in range(n)]
        pk, _ = encrypt_stream(evt2.encode(ev, 128), SK, SID, Config(level, b, 128, geom, pad))
        out += [(level, raw) for raw in pk]
    return out


@cocotb.test()
async def tag_chain_matches_model(dut):
    rng = rng_for(dut)
    dut.w_en.value = 0
    dut.m_tready.value = 1
    dut.key_tag.value = le(SK.tag)
    dut.key_aead.value = le(SK.aead)
    await start(dut)
    pkts = make_packets(rng)
    lens = sorted({len(body_words(r, l)) % 4 for l, r in pkts})
    assert lens == [0, 1, 2, 3], f"payload length classes covered: {lens}"
    feed = [wl for level, raw in pkts for wl in body_words(raw, level)]
    exp = [(w, l) for level, raw in pkts for (w, l) in hw.out_words(hw_packet(raw, level))]
    got, i, cyc = [], 0, 0
    while len(got) < len(exp):
        await FallingEdge(dut.clk)
        cyc += 1
        assert cyc < 200 * len(exp), f"stuck after {len(got)} of {len(exp)} output words"
        dut.m_tready.value = int(rng.random() < 0.6)
        if i < len(feed) and int(dut.count.value) < 500 and rng.random() < 0.9:
            dut.w_en.value, dut.w_word.value, dut.w_last.value = 1, feed[i][0], feed[i][1]
            i += 1
        else:
            dut.w_en.value = 0
        await Timer(1, "ns")
        if int(dut.m_tvalid.value) and int(dut.m_tready.value):
            got.append((int(dut.m_tdata.value), int(dut.m_tlast.value)))
    assert not int(dut.overflow.value)
    for k, (g, e) in enumerate(zip(got, exp)):
        assert g == e, (f"first mismatch at output word {k}: got {g[0]:08x} last={g[1]}, "
                        f"expected {e[0]:08x} last={e[1]}")
    dut._log.info("U=%s: %d packets, %d words in %d clk", os.getenv("NV_U", "1"), len(pkts), len(exp), cyc)


def hw_packet(raw, level):
    from neuro.packet import Packet, from_bytes
    if level != 4:
        return from_bytes(raw)
    h = PacketHeader.unpack(raw)
    return Packet(h, np.zeros(0, np.uint32), Trailer(0, 0), raw[-16:], raw[HEADER_LEN:-16])


def test_nv_tag32():
    for u in (1, 2, 4):
        os.environ["NV_U"] = str(u)
        run_sim_nv("tb_nv_tag_chain", "test_nv_tag32", parameters={"U": u}, build_tag=f"_u{u}")
