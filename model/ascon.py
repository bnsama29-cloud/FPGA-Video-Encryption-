"""Ascon-AEAD128 exactly as specified in NIST SP 800-232 (Aug 2025).

Pure Python, written for clarity so it can be read side by side with the RTL.
Verified against the official known-answer vectors (vectors/LWC_AEAD_KAT_128_128.txt).

Conventions (the hardware must match these):
  * Bytes are loaded into 64-bit state words little-endian (SP 800-232).
  * Keystream = Ascon-AEAD128 ciphertext of an all-zero plaintext, empty AD,
    under (K, N_enc). Keystream bit i = bit (i mod 8) of keystream byte (i div 8),
    i.e. LSB-first within each byte (contract v2, matches rtl/keystream_gen.v).
  * Nonce (contract v2) = session_id (8 bytes LE) || (frame_ctr << 1 | purpose)
    (8 bytes LE), so state word x3 = session_id and x4 = {frame_ctr, purpose}.
  * Frame tag = Ascon-AEAD128 with an empty plaintext and the frame's
    authenticated data as AD, under (K, N_mac). Output = 16-byte tag.
"""
import hmac

MASK = (1 << 64) - 1
IV_AEAD128 = 0x00001000808C0001          # SP 800-232 Ascon-AEAD128 IV
RATE = 16                                # bytes
A_ROUNDS, B_ROUNDS = 12, 8


def _rotr(x, n):
    return ((x >> n) | (x << (64 - n))) & MASK


def permutation(S, rounds):
    """Ascon-p[rounds] on state S (list of five 64-bit ints), in place."""
    for r in range(12 - rounds, 12):
        S[2] ^= ((0xF - r) << 4) | r                     # round constant
        # substitution layer (bitsliced 5-bit S-box)
        S[0] ^= S[4]; S[4] ^= S[3]; S[2] ^= S[1]
        T = [(S[i] ^ MASK) & S[(i + 1) % 5] for i in range(5)]
        for i in range(5):
            S[i] ^= T[(i + 1) % 5]
        S[1] ^= S[0]; S[0] ^= S[4]; S[3] ^= S[2]; S[2] ^= MASK
        # linear diffusion layer
        S[0] ^= _rotr(S[0], 19) ^ _rotr(S[0], 28)
        S[1] ^= _rotr(S[1], 61) ^ _rotr(S[1], 39)
        S[2] ^= _rotr(S[2], 1) ^ _rotr(S[2], 6)
        S[3] ^= _rotr(S[3], 10) ^ _rotr(S[3], 17)
        S[4] ^= _rotr(S[4], 7) ^ _rotr(S[4], 41)


def _le(b):
    return int.from_bytes(b, "little")


def _to_le(x, n=8):
    return (x & MASK).to_bytes(8, "little")[:n]


def _initialize(key, nonce):
    if len(key) != 16 or len(nonce) != 16:
        raise ValueError("Ascon-AEAD128 needs a 16-byte key and a 16-byte nonce")
    k0, k1 = _le(key[:8]), _le(key[8:])
    S = [IV_AEAD128, k0, k1, _le(nonce[:8]), _le(nonce[8:])]
    permutation(S, A_ROUNDS)
    S[3] ^= k0
    S[4] ^= k1
    return S


def _absorb_ad(S, ad):
    if len(ad) > 0:
        padded = ad + b"\x01" + b"\x00" * (RATE - (len(ad) % RATE) - 1)
        for i in range(0, len(padded), RATE):
            S[0] ^= _le(padded[i:i + 8])
            S[1] ^= _le(padded[i + 8:i + 16])
            permutation(S, B_ROUNDS)
    S[4] ^= 1 << 63                                     # domain separation


def _finalize(S, key):
    k0, k1 = _le(key[:8]), _le(key[8:])
    S[2] ^= k0
    S[3] ^= k1
    permutation(S, A_ROUNDS)
    return _to_le(S[3] ^ k0) + _to_le(S[4] ^ k1)


def encrypt(key, nonce, ad, plaintext):
    """Returns ciphertext || 16-byte tag."""
    S = _initialize(key, nonce)
    _absorb_ad(S, ad)
    plen = len(plaintext)
    padded = plaintext + b"\x01" + b"\x00" * (RATE - (plen % RATE) - 1)
    ct = bytearray()
    for i in range(0, len(padded) - RATE, RATE):
        S[0] ^= _le(padded[i:i + 8])
        S[1] ^= _le(padded[i + 8:i + 16])
        ct += _to_le(S[0]) + _to_le(S[1])
        permutation(S, B_ROUNDS)
    i = len(padded) - RATE
    S[0] ^= _le(padded[i:i + 8])
    S[1] ^= _le(padded[i + 8:i + 16])
    last = plen % RATE
    ct += _to_le(S[0], min(8, last)) + (_to_le(S[1], last - 8) if last > 8 else b"")
    return bytes(ct) + _finalize(S, key)


def decrypt(key, nonce, ad, ciphertext):
    """Returns plaintext, or None if the tag does not verify."""
    if len(ciphertext) < 16:
        return None
    ct, tag = ciphertext[:-16], ciphertext[-16:]
    S = _initialize(key, nonce)
    _absorb_ad(S, ad)
    clen = len(ct)
    full = clen - (clen % RATE)
    pt = bytearray()
    for i in range(0, full, RATE):
        c0, c1 = _le(ct[i:i + 8]), _le(ct[i + 8:i + 16])
        pt += _to_le(S[0] ^ c0) + _to_le(S[1] ^ c1)
        S[0], S[1] = c0, c1
        permutation(S, B_ROUNDS)
    last = clen - full
    tail = ct[full:] + b"\x00" * (RATE - last)
    p = _to_le(S[0] ^ _le(tail[:8])) + _to_le(S[1] ^ _le(tail[8:]))
    pt += p[:last]
    pad = p[:last] + b"\x01" + b"\x00" * (RATE - last - 1)
    S[0] ^= _le(pad[:8])
    S[1] ^= _le(pad[8:])
    good = _finalize(S, key)
    return bytes(pt) if hmac.compare_digest(good, tag) else None


def mac(key, nonce, data):
    """128-bit tag over `data` (Ascon-AEAD128, empty message, data as AD)."""
    return encrypt(key, nonce, data, b"")


class Keystream:
    """Streaming keystream: Ascon-AEAD128 encryption of an endless zero message.

    take(n) returns the next n keystream bits as an int whose bit j is the j-th
    bit handed out (LSB = first bit). Bit order inside the keystream: bit i =
    bit (i mod 8) of byte (i div 8). Same as the hardware window port
    (rtl/keystream_gen.v: ks_bits[0] = next unused bit).
    """

    def __init__(self, key, nonce):
        self.S = _initialize(key, nonce)
        self.S[4] ^= 1 << 63          # empty AD -> only the domain-separation bit
        self._buf = 0
        self._nbits = 0
        self.blocks = 0               # 128-bit blocks generated (cost statistics)
        self.consumed = 0             # keystream bits handed out

    def next_block(self):
        S = self.S
        out = _to_le(S[0]) + _to_le(S[1])
        permutation(S, B_ROUNDS)
        self.blocks += 1
        return out

    def take(self, n):
        while self._nbits < n:
            self._buf |= int.from_bytes(self.next_block(), "little") << self._nbits
            self._nbits += 128
        v = self._buf & ((1 << n) - 1)
        self._buf >>= n
        self._nbits -= n
        self.consumed += n
        return v


def keystream(key, nonce, nbytes):
    """First nbytes of the keystream (= ciphertext of nbytes zero bytes, no AD)."""
    return encrypt(key, nonce, b"", bytes(nbytes))[:nbytes]


def keystream_bits(key, nonce, nbits):
    """Keystream as a list of bits in consumption order (used by the testbenches)."""
    ks = keystream(key, nonce, (nbits + 7) // 8)
    return [(ks[i >> 3] >> (i & 7)) & 1 for i in range(nbits)]


FRAME_CTR_BITS = 63
SESSION_ID_BITS = 64


def make_nonce(session_id, frame_ctr, purpose):
    """Contract v2 nonce: session_id (64 bit) || frame_ctr (63 bit) || purpose (1 bit).

    Byte layout: session_id as 8 little-endian bytes, then (frame_ctr << 1 | purpose)
    as 8 little-endian bytes. Ascon loads words little-endian, so in hardware the
    state words are simply x3 = session_id and x4 = {frame_ctr, purpose}.
    purpose 0 = encryption keystream (N_enc), 1 = frame tag (N_mac).
    A nonce must never repeat under one key: never reuse a (session_id, frame_ctr)
    pair, and pick a fresh random 64-bit session_id (or a new key) per session.
    """
    if not 0 <= frame_ctr < (1 << FRAME_CTR_BITS):
        raise ValueError("frame counter out of range")
    if not 0 <= session_id < (1 << SESSION_ID_BITS):
        raise ValueError("session id out of range")
    return session_id.to_bytes(8, "little") + ((frame_ctr << 1) | (purpose & 1)).to_bytes(8, "little")


def key_from_words(words):
    """KEY0..KEY3 register values -> 16-byte key (KEY0 = key bytes 0..3, LE)."""
    return b"".join((w & 0xFFFFFFFF).to_bytes(4, "little") for w in words)


def parse_kat(path):
    """Parse an LWC_AEAD_KAT file into a list of dicts (values as bytes)."""
    vecs, cur = [], {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                if cur:
                    vecs.append(cur)
                    cur = {}
                continue
            k, _, v = line.partition("=")
            k, v = k.strip(), v.strip()
            cur[k] = int(v) if k == "Count" else bytes.fromhex(v)
    if cur:
        vecs.append(cur)
    return vecs
