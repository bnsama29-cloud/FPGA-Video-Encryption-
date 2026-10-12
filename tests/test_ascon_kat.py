"""Milestone M0: Ascon-AEAD128 must pass all 1089 NIST SP 800-232 known-answer vectors.

vectors/LWC_AEAD_KAT_128_128.txt is the official SP 800-232 KAT file
(Key 00..0F, Nonce 10..1F, AD/PT lengths 0..32), as published with the
reference implementations (ascon-c / pyascon genkat, Ascon-AEAD128).
The same file is used later to test the RTL core in cocotb and on the board.
"""
import os
from pathlib import Path

from model import ascon

KAT = Path(__file__).resolve().parents[1] / "vectors" / "LWC_AEAD_KAT_128_128.txt"


def load_kats():
    cases, cur = [], {}
    for line in KAT.read_text().splitlines():
        line = line.strip()
        if not line:
            if cur:
                cases.append(cur)
                cur = {}
            continue
        k, _, v = line.partition("=")
        cur[k.strip()] = v.strip()
    if cur:
        cases.append(cur)
    return cases


def test_all_known_answer_vectors():
    cases = load_kats()
    assert len(cases) == 1089
    for i, c in enumerate(cases, 1):
        key, nonce = bytes.fromhex(c["Key"]), bytes.fromhex(c["Nonce"])
        pt, ad, ct = bytes.fromhex(c["PT"]), bytes.fromhex(c["AD"]), bytes.fromhex(c["CT"])
        assert ascon.encrypt(key, nonce, ad, pt) == ct, f"vector {i}"
        assert ascon.decrypt(key, nonce, ad, ct) == pt, f"vector {i}"


def test_tampered_ciphertext_rejected():
    key, nonce = os.urandom(16), os.urandom(16)
    ct = ascon.encrypt(key, nonce, b"header", b"secret frame data")
    for i in range(len(ct)):
        bad = bytearray(ct)
        bad[i] ^= 0x01
        assert ascon.decrypt(key, nonce, b"header", bytes(bad)) is None


def test_keystream_equals_zero_message_encryption():
    key, nonce = os.urandom(16), os.urandom(16)
    ks = ascon.Keystream(key, nonce)
    first = ks.take(3) | ks.take(997) << 3              # odd-sized requests, LSB first
    ref = ascon.encrypt(key, nonce, b"", bytes(125))[:125]
    assert first.to_bytes(125, "little") == ref
    assert ascon.keystream_bits(key, nonce, 1000) == [(first >> i) & 1 for i in range(1000)]


def test_different_nonces_give_different_keystreams():
    key = os.urandom(16)
    a = ascon.Keystream(key, ascon.make_nonce(1, 5, 0)).take(256)
    b = ascon.Keystream(key, ascon.make_nonce(1, 6, 0)).take(256)
    c = ascon.Keystream(key, ascon.make_nonce(1, 5, 1)).take(256)
    assert len({a, b, c}) == 3


def test_nonce_layout_contract_v2():
    """x3 = session_id, x4 = frame_ctr << 1 | purpose (both loaded little-endian)."""
    sid, ctr = 0x0123456789ABCDEF, (1 << 62) + 5
    for purpose in (0, 1):
        n = ascon.make_nonce(sid, ctr, purpose)
        assert int.from_bytes(n[:8], "little") == sid
        assert int.from_bytes(n[8:], "little") == (ctr << 1) | purpose
    for bad in ((1 << 64, 0), (0, 1 << 63), (-1, 0)):
        try:
            ascon.make_nonce(*bad, 0)
        except ValueError:
            continue
        raise AssertionError(f"out-of-range nonce fields accepted: {bad}")
