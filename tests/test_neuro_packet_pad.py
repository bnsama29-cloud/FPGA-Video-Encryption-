"""Paper 2 model: packet framing and packetizer (DESIGN §3), padding (§5)."""
import numpy as np
import pytest

from neuro import evt2, pad, packet
from neuro.geometry import SENSORS, Geometry
from neuro_helpers import sid, sk, stream

G = SENSORS["dvsgesture"]


def test_header_pack_unpack_and_size():
    h = packet.PacketHeader(level=3, flags=packet.F_FIRST, ts_bits=6, session_id=sid(), packet_ctr=9,
                            t_start=4096, W=128, H=128, T_us=1024, pad_policy=0, link=packet.LINK_NONE)
    b = h.pack()
    assert len(b) == 48 and b[:4] == b"NVE1"
    assert packet.PacketHeader.unpack(b) == h


def test_trailer_parse_is_unique_with_trailer_like_payload():
    rng = np.random.default_rng(3)
    for _ in range(50):
        n = int(rng.integers(0, 40))
        payload = rng.integers(0, 2**32, n, dtype=np.uint64).astype(np.uint32)
        if n >= 3:                                   # plant a fake trailer inside the payload
            payload[n - 3:] = np.array([n, 1, 0], dtype=">u4").view("<u4")
        n_cd = int(rng.integers(0, 70))
        tr = packet.Trailer(n, n_cd, bytes(packet.bitmap_len(n_cd)))
        body = payload.astype("<u4").tobytes() + tr.pack()
        got = packet.Trailer.unpack(body, pad=True)
        assert (got.n_words, got.n_cd, got.bitmap) == (n, n_cd, tr.bitmap)


def test_packetizer_grid_empty_packets_and_closing():
    w = np.array([evt2.time_high(100), evt2.cd_word(1, 1, 0, 0),
                  evt2.time_high(116),                  # closes packet 0 (T = 1024 = 16 buckets), opens 1
                  evt2.time_high(164), evt2.cd_word(2, 2, 1, 0),   # closes 1, packets 2, 3 empty, opens 4
                  evt2.time_high(180)], dtype=np.uint32)          # closes 4
    ps = packet.packetize(w, G, 1024)
    assert [p.ctr for p in ps] == [0, 1, 2, 3, 4]
    assert [len(p.words) for p in ps] == [2, 1, 0, 0, 2]
    assert [p.needs_tables for p in ps] == [True, True, False, False, True]
    assert [p.t_start for p in ps] == [6400 + 1024 * k for k in range(5)]


def test_time_jump_drop_and_halt():
    far = 100 + (1_000_000 // 64) + 50
    w = np.array([evt2.time_high(100), evt2.cd_word(1, 1, 0, 0), evt2.time_high(far), evt2.cd_word(2, 2, 0, 0),
                  evt2.time_high(101), evt2.cd_word(3, 3, 0, 0)], dtype=np.uint32)
    pz = packet.Packetizer(128, 128, 1024, jump_mode=0)
    pz.feed(w)
    assert pz.err["ERR_JUMP"] == 2 and pz.open[-1] == w[-1]
    pz = packet.Packetizer(128, 128, 1024, jump_mode=1)
    out = pz.feed(w)
    assert pz.halted and out[-1].flags & packet.F_FINAL and len(out[-1].words) == 0
    assert pz.held[0] == w[2]
    pz.resume(ctr0=0)
    assert pz.started and pz.t_origin == 64 * far


@pytest.mark.parametrize("policy", [pad.PadPolicy(pad.FLOOR, 8), pad.PadPolicy(pad.LADDER, 4, 64)])
def test_pad_roundtrip_conformance_and_empty_packet(policy):
    ps = packet.packetize(stream(300), G, 1024)
    for p in ps + [packet.RawPacket(99, ps[-1].t_start + 1024, np.zeros(0, np.uint32))]:
        w, bm, nd, dm = pad.pad_packet(p.words, policy, sk().dum, sid(), p.ctr, G, p.t_start, 1024)
        assert nd == 0 and len(bm) == packet.bitmap_len(int(evt2.is_cd(w).sum()))
        real, dm2 = pad.strip(w, bm, sk().dum, sid(), p.ctr, G, policy, p.t_start, 1024)
        assert evt2.event_equal(real, p.words) or (len(p.words) == 0 and not evt2.is_cd(real).any())
        assert np.array_equal(dm, dm2)
        assert ((w >> 28) == evt2.TIME_HIGH).sum() >= 16       # every bucket has a TIME_HIGH


def test_pad_detects_tampered_dummy_and_overflow_counts():
    policy = pad.PadPolicy(pad.FLOOR, 8)
    p = packet.packetize(stream(300), G, 1024)[0]
    w, bm, _, dm = pad.pad_packet(p.words, policy, sk().dum, sid(), p.ctr, G, p.t_start, 1024)
    i = int(np.nonzero(dm)[0][0])
    w2 = w.copy()
    w2[i] ^= 1
    with pytest.raises(pad.StripError):
        pad.strip(w2, bm, sk().dum, sid(), p.ctr, G, policy, p.t_start, 1024)
    small = pad.PadPolicy(pad.FLOOR, 8, max_cd=10)
    w3, _, nd, dm3 = pad.pad_packet(p.words, small, sk().dum, sid(), p.ctr, G, p.t_start, 1024)
    cd3 = evt2.is_cd(w3)
    assert cd3.sum() == 10                                    # dummies count towards MAX_CD_PAD too
    assert nd + int((cd3 & ~dm3).sum()) == int(evt2.is_cd(p.words).sum())


def test_padding_only_where_allowed():
    pad.check_allowed(3, 6)
    pad.check_allowed(4, 0)
    for lvl, b in [(0, 0), (1, 0), (2, 0), (3, 5)]:
        with pytest.raises(pad.PadError):
            pad.check_allowed(lvl, b)
