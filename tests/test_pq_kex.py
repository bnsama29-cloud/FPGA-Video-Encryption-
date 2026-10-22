"""Post-quantum session key (link/keys.py kex_*, link/kex.py): hybrid ML-KEM-768 (FIPS 203) + X25519,
authenticated by the pre-shared key.

Checks: both ML-KEM implementations agree with each other (OpenSSL through `cryptography`, and the
pure-Python kyber-py: an encapsulation by one is decapsulated by the other), both ends derive the same
16-byte key, fresh keys every run, and every forged, tampered or replayed message is rejected."""
import threading

import pytest

from link import config, kex, keys

PSK = bytes(range(16))


def backends():
    out = []
    for b in ("cryptography", "kyber-py"):
        try:
            keys.mlkem_backend(b)
            out.append(b)
        except RuntimeError:
            pass
    return out


@pytest.mark.parametrize("rx", backends())
@pytest.mark.parametrize("tx", backends())
def test_both_ends_agree(rx, tx):
    st, m1 = keys.kex_init(PSK, rx)
    k_tx, m2 = keys.kex_respond(PSK, m1, tx)
    k_rx = keys.kex_finish(PSK, st, m2)
    assert k_tx == k_rx and len(k_tx) == 16, f"{rx} -> {tx}: keys differ"
    assert len(m1) == keys.M1_LEN and len(m2) == keys.M2_LEN
    assert keys.key_confirm(k_rx, m1, m2, "receiver") == keys.key_confirm(k_tx, m1, m2, "receiver")


def test_fresh_keys():
    ks = set()
    for _ in range(4):
        st, m1 = keys.kex_init(PSK)
        k, m2 = keys.kex_respond(PSK, m1)
        assert keys.kex_finish(PSK, st, m2) == k
        ks.add(k)
    assert len(ks) == 4 and PSK not in ks


def test_wrong_psk_and_tampering_rejected():
    st, m1 = keys.kex_init(PSK)
    with pytest.raises(keys.KexError):
        keys.kex_respond(bytes(16), m1)                     # sender with another PSK
    for pos in (5, 100, 4 + 16 + 1184 + 3, len(m1) - 1):     # nonce, ML-KEM key, X25519 share, MAC
        bad = bytearray(m1); bad[pos] ^= 1
        with pytest.raises(keys.KexError):
            keys.kex_respond(PSK, bytes(bad))
    k, m2 = keys.kex_respond(PSK, m1)
    for pos in (5, 500, len(m2) - 40, len(m2) - 1):
        bad = bytearray(m2); bad[pos] ^= 1
        with pytest.raises(keys.KexError):
            keys.kex_finish(PSK, st, bytes(bad))
    with pytest.raises(keys.KexError):
        keys.kex_finish(PSK, st, m2[:-1])


def test_replayed_answer_rejected():
    st_old, m1_old = keys.kex_init(PSK)
    _, m2_old = keys.kex_respond(PSK, m1_old)
    st, _ = keys.kex_init(PSK)                              # a new session
    with pytest.raises(keys.KexError):
        keys.kex_finish(PSK, st, m2_old)                    # an old M2 does not answer the new M1


def test_over_udp(tmp_path):
    cfg = config.load(None, [f"keys.master={PSK.hex()}", "link.host=127.0.0.1", "link.kex=47096"])
    got = {}
    rx = threading.Thread(target=lambda: got.update(rx=kex.run_receiver(cfg, 20, tmp_path / "rx.txt", log=lambda *_: None)))
    rx.start()
    got["tx"] = kex.run_sender(cfg, 20, tmp_path / "tx.txt", log=lambda *_: None)
    rx.join(10)
    assert got["rx"] == got["tx"]
    assert (tmp_path / "rx.txt").read_text().strip() == got["rx"].hex() == (tmp_path / "tx.txt").read_text().strip()
    c2 = config.load(None, [f"keys.master_file={tmp_path / 'rx.txt'}"])
    assert c2["keys"]["master"] == got["rx"].hex()


def test_over_udp_slow_first_keygen(tmp_path, monkeypatch):
    """Bug #39: the receiver's first kex_init took longer than the sender's 0.5 s resend (0.87 s cold on
    Windows, longer on the A9), so two SVK0 queued, the receiver re-initialised for the second one and
    rejected the M2 that answered the first M1 forever. A repeated SVK0 must get the same M1 again."""
    real, calls = keys.kex_init, []

    def slow_init(psk):
        calls.append(1)
        if len(calls) == 1:
            import time
            time.sleep(1.2)
        return real(psk)
    monkeypatch.setattr(keys, "kex_init", slow_init)
    cfg = config.load(None, [f"keys.master={PSK.hex()}", "link.host=127.0.0.1", "link.kex=47097"])
    got = {}
    rx = threading.Thread(target=lambda: got.update(rx=kex.run_receiver(cfg, 10, tmp_path / "rx.txt", log=lambda *_: None)))
    rx.start()
    got["tx"] = kex.run_sender(cfg, 10, tmp_path / "tx.txt", log=lambda *_: None)
    rx.join(10)
    assert got.get("rx") == got["tx"], f"keys differ: receiver {got.get('rx')}, sender {got['tx']}"
    assert len(calls) == 1, f"the receiver started {len(calls)} exchanges for one sender"
