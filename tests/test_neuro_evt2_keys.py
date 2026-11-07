"""Paper 2 model: EVT 2.0 words (DESIGN §2) and the key schedule (§3.4)."""
import numpy as np
import pytest

from neuro import evt2, keys
from neuro.geometry import SENSORS, Geometry
from neuro_helpers import MASTER, events


def test_encode_decode_roundtrip_and_heartbeat():
    ev = events(500)
    w = evt2.encode(ev, 1024)
    got, extras = evt2.decode(w)
    assert len(extras) == 0
    d = evt2.first_difference(evt2.encode(got, 1024), w)
    assert d is None, f"first mismatch {d}"
    th = (w >> 28) == evt2.TIME_HIGH
    vals = (w[th] & evt2.TH_MASK).astype(int)
    # a TIME_HIGH at every packet boundary up to and after the last event
    bounds = set(range(vals[0] + 16, (int(ev["t"][-1]) >> 6) + 17, 16))
    assert bounds <= set(vals.tolist())


def test_cd_word_layout_matches_spec():
    w = evt2.cd_word(x=0x5A5, y=0x3C3, p=1, ts6=0x2A)
    assert w >> 28 == evt2.CD_ON and (w >> 22) & 63 == 0x2A and (w >> 11) & 0x7FF == 0x5A5 and w & 0x7FF == 0x3C3


def test_input_filter_rules():
    g = Geometry("t", 16, 16)
    w = np.array([evt2.cd_word(1, 1, 0, 0),             # before first TIME_HIGH
                  evt2.time_high(10), evt2.cd_word(20, 1, 0, 0),   # x out of range
                  evt2.time_high(9),                       # backwards
                  evt2.time_high(10), evt2.cd_word(2, 2, 1, 5)], dtype=np.uint32)
    kept, c = evt2.input_filter(w, g)
    assert c == {"ERR_PRE_TH": 1, "ERR_ORDER": 1, "ERR_RANGE": 1}
    assert kept.tolist() == [w[1], w[4], w[5]]


def test_raw_file_roundtrip(tmp_path):
    w = evt2.encode(events(50), 1024)
    p = tmp_path / "a.raw"
    evt2.write_raw(p, w, SENSORS["dvsgesture"])
    w2, g = evt2.read_raw(p)
    assert np.array_equal(w2, w) and (g.W, g.H) == (128, 128)


def test_kdf_ctx_distinct_and_subkeys_differ():
    s0, s1 = keys.subkeys(MASTER, 3, 5, 0), keys.subkeys(MASTER, 3, 5, 1)
    vals0 = [s0.tag, s0.pol, s0.perm, s0.dum, s0.aead]
    assert len(set(vals0)) == 5
    assert not set(vals0) & {s1.tag, s1.pol, s1.perm, s1.dum, s1.aead}
    assert keys.subkeys(MASTER, 3, 6, 0).tag != s0.tag
    assert len({1 << 62 | i for i in keys.LABELS.values()}) == 5


def test_ratchet_bounds_and_epoch_last():
    r = keys.EventRatchet(MASTER, 3, 5, 0)
    assert r.peek(keys.E_MAX) is not None and r.peek(keys.E_MAX + 1) is None
    r.forward(1)
    assert r.peek(0) is None
    assert r.key == keys.epoch_key(MASTER, 3, 5, 1)
    last = keys.EventRatchet.from_key(b"x" * 16, 3, 5, keys.EPOCH_LAST)
    assert last.peek(keys.EPOCH_LAST + 1) is None
    with pytest.raises(ValueError):
        keys.session_id(3, 5, keys.EPOCH_LAST + 1)
    with pytest.raises(ValueError):
        keys.base(0, 5)
    assert keys.split_session(keys.session_id(7, 9, 4)) == (7, 9, 4)
