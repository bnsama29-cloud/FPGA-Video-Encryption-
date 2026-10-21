"""Key schedule: one pre-shared master key -> per-purpose keys + forward-secure ratchet.

    K_fb        = KDF(K_master, "feedback")            feedback channel key (receiver -> sender)
    K_video[0]  = KDF(K_master, "video", 0)
    K_video[e+1]= KDF(K_video[e], "ratchet", e+1)      one-way step; old keys are erased
    session_id  = base (48 random bits) << 16 | epoch  (64-bit, goes in every nonce + APP11)

KDF(K, label, ctx) = Ascon-AEAD128 tag under K with nonce (session 0, ctx, purpose 1),
AD = label, empty message. Session id 0 is reserved for the KDF: frame session
ids always have a non-zero 48-bit base, so a KDF nonce can never equal a frame
nonce under the same key. We reuse the one primitive that is already verified in
Python (1089 KATs) and in RTL, so no second core is needed on the FPGA. The tag
of a sponge-based AEAD is a PRF under the usual assumptions. SP 800-232 also
defines Ascon-XOF128 / Ascon-CXOF128, the textbook choice for key derivation;
swapping it in (with its official test vectors) is listed as improvement B8 in
GUIDE.md.

Rekeying needs no handshake: the sender moves to epoch e+1 and the epoch is in
the authenticated session id of every frame, so the receiver ratchets forward
when it sees a valid frame from the next epoch, then erases the old key.
"""
import os

from model import ascon

KDF_SESSION = 0               # reserved: no frame ever uses session id 0
EPOCH_BITS = 16


def kdf(key, label, ctx=0):
    return ascon.mac(key, ascon.make_nonce(KDF_SESSION, ctx, 1), label.encode())


def feedback_key(master):
    return kdf(master, "feedback")


def video_key(master, epoch):
    k = kdf(master, "video", 0)
    for e in range(1, epoch + 1):
        k = kdf(k, "ratchet", e)
    return k


def session_id(base, epoch):
    if not 0 < base < (1 << 48):
        raise ValueError("session base must be 1 .. 2^48-1 (0 is reserved for the KDF)")
    return ((base & ((1 << 48) - 1)) << EPOCH_BITS) | (epoch & ((1 << EPOCH_BITS) - 1))


def split_session(sid):
    return sid >> EPOCH_BITS, sid & ((1 << EPOCH_BITS) - 1)


def random_base():
    return int.from_bytes(os.urandom(6), "big") or 1


class Ratchet:
    """Holds only the current video key; forward() is one-way."""

    def __init__(self, master, epoch=0):
        self.epoch = epoch
        self.key = video_key(master, epoch)

    def peek(self, epoch):
        """Key for a later epoch without committing (receiver checks a frame first)."""
        if epoch < self.epoch:
            return None                       # old keys are gone (forward secrecy)
        k = self.key
        for e in range(self.epoch + 1, epoch + 1):
            k = kdf(k, "ratchet", e)
        return k

    def forward(self, epoch=None):
        epoch = self.epoch + 1 if epoch is None else epoch
        self.key = self.peek(epoch)
        self.epoch = epoch
        return self.key


# ================================================================ post-quantum session key (option)
# keys.exchange = "pq" (link/kex.py): instead of using the pre-shared key K_psk directly as the master
# key, both ends run one hybrid key exchange at session start and use its result as K_master:
#
#   receiver -> sender   M1 = "SVK1" | r1 | ek (ML-KEM-768, FIPS 203) | X25519 public | HMAC(K_a, M1)
#   sender  -> receiver  M2 = "SVK2" | r2 | ct = Encaps(ek)        | X25519 public | HMAC(K_a, M1 || M2)
#   K_master = HKDF-SHA256(salt = K_psk, ikm = ss_mlkem || ss_x25519, info = "SV session" || SHA256(M1 || M2))
#   K_a      = HMAC(K_psk, "SV kex auth")          (authenticates both messages: no man in the middle)
#
# Why: a pre-shared key used for every session is the single point of failure (paper, limitations).
# With the exchange, a recorded session can only be decrypted by someone who breaks ML-KEM AND X25519
# for that session's ephemeral keys, even if K_psk leaks later (forward secrecy) and even with a
# quantum computer (ML-KEM is post-quantum; X25519 keeps the classical guarantee if ML-KEM falls).
# K_psk only authenticates. Ascon-AEAD128 in the fabric is unchanged: a 128-bit symmetric key keeps
# about 2^64 security against Grover's search. Runs on the ARM once per session (experiments/pq_kex_cost.py).
# Libraries: `cryptography` (OpenSSL, >= 46 has ML-KEM) when it has ML-KEM, else the pure-Python
# FIPS 203 implementation `kyber-py`; both are cross-checked in tests/test_pq_kex.py.
import hashlib
import hmac

KEX_MAGIC1, KEX_MAGIC2 = b"SVK1", b"SVK2"
EK_LEN, CT_LEN, X_LEN, R_LEN, MAC_LEN = 1184, 1088, 32, 16, 32
M1_LEN = 4 + R_LEN + EK_LEN + X_LEN + MAC_LEN
M2_LEN = 4 + R_LEN + CT_LEN + X_LEN + MAC_LEN


class KexError(ValueError):
    """A key-exchange message was malformed or not authentic (wrong PSK or tampered)."""


def mlkem_backend(prefer=None):
    """('cryptography' | 'kyber-py', keygen, encaps, decaps) for ML-KEM-768."""
    order = [prefer] if prefer else ["cryptography", "kyber-py"]
    for name in order:
        if name == "cryptography":
            try:
                from cryptography.hazmat.primitives import serialization as S
                from cryptography.hazmat.primitives.asymmetric import mlkem
            except ImportError:
                continue

            def keygen():
                dk = mlkem.MLKEM768PrivateKey.generate()
                return dk.public_key().public_bytes(S.Encoding.Raw, S.PublicFormat.Raw), dk

            def encaps(ek):
                ss, ct = mlkem.MLKEM768PublicKey.from_public_bytes(ek).encapsulate()
                return ss, ct

            return name, keygen, encaps, lambda dk, ct: dk.decapsulate(ct)
        if name == "kyber-py":
            try:
                from kyber_py.ml_kem import ML_KEM_768 as K
            except ImportError:
                continue
            return name, (lambda: K.keygen()), (lambda ek: K.encaps(ek)), (lambda dk, ct: K.decaps(dk, ct))
    raise RuntimeError("no ML-KEM implementation: pip install 'cryptography>=46' or kyber-py")


def _x25519():
    from cryptography.hazmat.primitives import serialization as S
    from cryptography.hazmat.primitives.asymmetric import x25519
    priv = x25519.X25519PrivateKey.generate()
    return priv, priv.public_key().public_bytes(S.Encoding.Raw, S.PublicFormat.Raw)


def _x25519_shared(priv, peer):
    from cryptography.hazmat.primitives.asymmetric import x25519
    try:
        return priv.exchange(x25519.X25519PublicKey.from_public_bytes(peer))
    except ValueError as e:                      # all-zero shared secret (small-order point)
        raise KexError(f"bad X25519 public key: {e}") from None


def _auth_key(psk):
    return hmac.new(psk, b"SV kex auth", hashlib.sha256).digest()


def _session_key(psk, ss_k, ss_x, m1, m2):
    prk = hmac.new(psk, ss_k + ss_x, hashlib.sha256).digest()                       # HKDF-Extract
    info = b"SV session" + hashlib.sha256(m1 + m2).digest()
    return hmac.new(prk, info + b"\x01", hashlib.sha256).digest()[:16]              # HKDF-Expand, 16 bytes


def kex_init(psk, backend=None):
    """Receiver side, step 1: (state, M1)."""
    name, keygen, _, _ = mlkem_backend(backend)
    ek, dk = keygen()
    xpriv, xpub = _x25519()
    body = KEX_MAGIC1 + os.urandom(R_LEN) + ek + xpub
    m1 = body + hmac.new(_auth_key(psk), body, hashlib.sha256).digest()
    return dict(dk=dk, xpriv=xpriv, m1=m1, backend=name), m1


def kex_respond(psk, m1, backend=None):
    """Sender side: checks M1, returns (K_master, M2)."""
    if len(m1) != M1_LEN or m1[:4] != KEX_MAGIC1:
        raise KexError("M1 malformed")
    ka = _auth_key(psk)
    if not hmac.compare_digest(m1[-MAC_LEN:], hmac.new(ka, m1[:-MAC_LEN], hashlib.sha256).digest()):
        raise KexError("M1 not authentic (wrong pre-shared key or tampered)")
    o = 4 + R_LEN
    ek, xpeer = m1[o:o + EK_LEN], m1[o + EK_LEN:o + EK_LEN + X_LEN]
    _, _, encaps, _ = mlkem_backend(backend)
    ss_k, ct = encaps(ek)
    xpriv, xpub = _x25519()
    ss_x = _x25519_shared(xpriv, xpeer)
    body = KEX_MAGIC2 + os.urandom(R_LEN) + ct + xpub
    m2 = body + hmac.new(ka, m1 + body, hashlib.sha256).digest()
    return _session_key(psk, ss_k, ss_x, m1, m2), m2


def kex_finish(psk, state, m2):
    """Receiver side, step 2: checks M2, returns K_master."""
    m1 = state["m1"]
    if len(m2) != M2_LEN or m2[:4] != KEX_MAGIC2:
        raise KexError("M2 malformed")
    if not hmac.compare_digest(m2[-MAC_LEN:], hmac.new(_auth_key(psk), m1 + m2[:-MAC_LEN], hashlib.sha256).digest()):
        raise KexError("M2 not authentic (wrong pre-shared key, tampered, or an answer to another M1)")
    o = 4 + R_LEN
    ct, xpeer = m2[o:o + CT_LEN], m2[o + CT_LEN:o + CT_LEN + X_LEN]
    _, _, _, decaps = mlkem_backend(state["backend"])
    ss_k = decaps(state["dk"], ct)
    ss_x = _x25519_shared(state["xpriv"], xpeer)
    return _session_key(psk, ss_k, ss_x, m1, m2)


def key_confirm(k_master, m1, m2, role):
    """16-byte proof that the peer derived the same key (sent after the exchange)."""
    return hmac.new(k_master, b"SV confirm " + role.encode() + hashlib.sha256(m1 + m2).digest(),
                    hashlib.sha256).digest()[:16]
