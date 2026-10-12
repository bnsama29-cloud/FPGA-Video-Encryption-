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
swapping it in (with its official test vectors) is listed as an improvement in
HELP_GUIDE.md.

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
