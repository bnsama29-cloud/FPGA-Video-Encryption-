"""Paper 2 model: receiver checks (DESIGN §3.5) against every attack of §1.4, and the sender commit rules (§6.7)."""
import numpy as np
import pytest

from neuro import attacks, evt2, keys, pad, sender
from neuro.packet import F_FINAL, F_FIRST, LINK_NONE, PacketHeader
from neuro_helpers import BOOT, CAM, MASTER, SENSORS, decryptor, seal, sid, sk, stream

G = SENSORS["dvsgesture"]


def run(pkts, **kw):
    d = decryptor(**kw)
    res = [d.accept(p, now=i * 0.001) for i, p in enumerate(pkts)]
    return d, res


@pytest.mark.parametrize("level,b,policy", [(0, 0, None), (1, 0, None), (2, 0, None), (3, 6, None), (4, 0, None),
                                            (3, 6, pad.PadPolicy(1, 8)), (4, 0, pad.PadPolicy(2, 4, 64))])
def test_roundtrip_every_level(level, b, policy):
    w = stream(500)
    pk, enc = seal(w, level, b, pad=policy)
    d, res = run(pk, level=level, b=b, pad=policy)
    assert {r.status for r in res} == {"ok"}
    dec = np.concatenate([r.words for r in res])
    diff = evt2.first_difference(dec, w)
    assert diff is None, f"first mismatch {diff}"
    assert d.close() == []
    assert PacketHeader.unpack(pk[0]).first and PacketHeader.unpack(pk[-1]).final


def test_each_active_attack_gets_its_status():
    pk, _ = seal(stream(500))
    cases = {
        "bitflip": (pk[:2] + [attacks.flip_bit(pk[2], 60)], "forged"),
        "downgrade": (pk[:2] + [attacks.downgrade(pk[2], 3)[:0] + attacks.set_header_field(pk[2], ts_bits=5)],
                      "policy"),
        "splice": (pk[:2] + [attacks.splice(pk[2], pk[3])], None),
        "replay": (pk[:3] + [pk[1]], "replay"),
        "inject_junk": (pk[:2] + attacks.flood(1), None),
        "epoch_jump": (pk[:2] + [attacks.epoch_jump(pk[2], 0xFFFF)], "policy"),   # DESIGN §7.3
        "epoch_far": (pk[:2] + [attacks.epoch_jump(pk[2], 3)], "policy"),
        "wrong_t_start": (pk[:2] + [attacks.set_header_field(pk[2], t_start=PacketHeader.unpack(pk[2]).t_start + 64)],
                          "policy"),
    }
    for name, (seq, want) in cases.items():
        _, res = run(seq)
        last = res[-1].status
        assert last != "ok", f"{name}: attack accepted"
        if want:
            assert last == want, f"{name}: got {last}, expected {want}"


def test_downgrade_level_is_refused_by_exact_profile():
    pk, _ = seal(stream(300))
    _, res = run([attacks.downgrade(pk[0], 0)])
    assert res[0].status == "policy"


def test_forged_huge_counter_does_not_move_state():
    pk, _ = seal(stream(500))
    h = PacketHeader.unpack(pk[1])
    forged = attacks.set_header_field(pk[1], packet_ctr=h.packet_ctr + (1 << 40),
                                      t_start=h.t_start + (1 << 40) * 1024 % (1 << 34))
    d = decryptor()
    assert d.accept(pk[0]).status == "ok"
    assert d.accept(forged).status in ("forged", "policy")
    assert d.accept(pk[1]).status == "ok"


def test_epoch_far_ahead_costs_no_kdf():
    pk, _ = seal(stream(300))
    d = decryptor()
    d.accept(pk[0])
    before = d.kdf_calls
    assert d.accept(attacks.epoch_jump(pk[1], 65535 - 0)).status in ("stale", "policy")
    assert d.accept(attacks.epoch_jump(pk[1], 100)).status == "policy"
    assert d.kdf_calls == before


def test_deletion_gives_gap_and_tail_truncation_gives_truncated():
    pk, _ = seal(stream(800, t1=40000))
    d, res = run(attacks.delete(pk, 3))
    notes = d.close()
    assert ("gap", (3, 3)) in [(n.kind, n.ctrs) for n in notes]
    d, res = run(attacks.delete_tail(pk, 1))
    assert "truncated" in [n.kind for n in d.close()]


def test_window_reports_old_missing_counters():
    pk, _ = seal(stream(2000, t1=200000))
    assert len(pk) > 80
    d = decryptor()
    gaps = []
    for i, p in enumerate(pk):
        if i == 5:
            continue
        gaps += [n.ctrs for n in d.accept(p).notices if n.kind == "gap"]
    assert (5, 5) in gaps


def test_reorder_inside_window_is_accepted():
    pk, _ = seal(stream(500))
    _, res = run(attacks.reorder(pk, 1, 2))
    assert [r.status for r in res] == ["ok"] * len(pk)


def test_stall_notice():
    pk, _ = seal(stream(300))
    d = decryptor()
    d.accept(pk[0], now=0.0)
    assert d.tick(0.05) == []
    assert [n.kind for n in d.tick(0.5)] == ["stall"]


def test_epoch_change_first_link_and_old_epoch_gap():
    w = stream(1500, t1=30000)
    cfg = sender.Config(3, 6, 1024, G)
    enc = sender.Encryptor(sk(0), sid(0), cfg)
    out = enc.push(w[:200])
    open_ctr = enc.pz.open_ctr
    enc.commit(open_ctr + 2, subkeys=sk(1), sid=sid(1), ctr0=0)
    out += enc.push(w[200:]) + enc.flush()
    hs = [PacketHeader.unpack(p) for p in out]
    idx = next(i for i, h in enumerate(hs) if h.session_id == sid(1))
    assert hs[idx - 1].final and hs[idx].first and hs[idx].link == hs[idx - 1].packet_ctr and hs[idx].packet_ctr == 0
    d = decryptor()
    seq = out[:idx - 2] + out[idx:]                     # drop two packets of epoch 0, incl. its FINAL
    res = [d.accept(p) for p in seq]
    assert {r.status for r in res} == {"ok"}
    notes = [(n.kind, n.sid) for r in res for n in r.notices]
    assert ("truncated", sid(0)) in notes and ("gap", sid(0)) in notes


def test_commit_rules_late_and_rewind():
    cfg = sender.Config(3, 6, 1024, G)
    enc = sender.Encryptor(sk(0), sid(0), cfg)
    enc.push(stream(300))
    oc = enc.pz.open_ctr
    with pytest.raises(sender.ConfigError) as e:
        enc.commit(oc + 1, cfg)
    assert e.value.code == sender.CFG_LATE
    enc.commit(oc + 2, subkeys=sk(1), sid=sid(1))
    enc.push(stream(800, t0=7000, t1=20000))
    with pytest.raises(sender.ConfigError) as e:     # back to epoch 0 under the same base
        enc.commit(enc.pz.open_ctr + 2, subkeys=sk(0), sid=sid(0))
    assert e.value.code == sender.CFG_REWIND
    assert enc.counters["ERR_CFG"] == 2
    with pytest.raises(sender.ConfigError) as e:
        sender.Encryptor(sk(), sid(), sender.Config(2, 0, 1024, sender.Geometry("thin", 128, 8)))
    assert e.value.code == sender.CFG_GEOM
    with pytest.raises(sender.ConfigError) as e:
        sender.Encryptor(sk(), sid(), sender.Config(2, 0, 1024, G, pad.PadPolicy(1, 4)))
    assert e.value.code == sender.CFG_LEVEL


def test_psk_lower_boot_is_stale(tmp_path):
    pk, _ = seal(stream(200))
    from neuro import receiver
    prof = receiver.Profile(frozenset({(3, 6, None, None)}), G, 1024)
    st = tmp_path / "state.json"
    d = receiver.Decryptor({(CAM, BOOT): MASTER, (CAM, BOOT - 1): MASTER}, prof, st)
    assert d.accept(pk[0]).status == "ok"
    d2 = receiver.Decryptor({(CAM, BOOT - 1): MASTER, (CAM, BOOT): MASTER}, prof, st)
    old = sender.encrypt_stream(stream(200), keys.subkeys(MASTER, CAM, BOOT - 1, 0),
                                keys.session_id(CAM, BOOT - 1, 0), sender.Config(3, 6, 1024, G))[0]
    assert d2.accept(old[0]).status == "stale"
