"""Keys, nonces and domain separation for event packets (DESIGN §3.4).

    C62       = 1 << 62
    base      = cam_id << 32 | boot_id                           48 bits; cam_id != 0, so base != 0
    K_ev[0]   = kdf(master_boot, "nv1-events",  C62 | base)
    K_ev[e]   = kdf(K_ev[e-1],   "nv1-ratchet", e)               e = 1 .. 0xFFFF, one-way
    K_x       = kdf(K_ev[e],     "nv1-" + x,    C62 | i_x)       x: tag=1, pol=2, perm=3, dum=4, aead=5
    sid       = base << 16 | e                                    = link.keys.session_id(base, e)

kdf is paper 1's link.keys.kdf unchanged (Ascon-AEAD128 tag under nonce (sid 0, ctx, purpose 1), AD = label).
Under every key each KDF call has its own ctx: the master sees ctx = C62|base here (paper 1 uses ctx 0); K_ev[e]
sees the ratchet ctx e+1 <= 0xFFFF and the subkey ctx C62|1..5. Packet nonces are ascon.make_nonce(sid, ctr, p)
with sid != 0, so they never meet a KDF nonce.
"""
import hashlib
from dataclasses import dataclass

from link import keys as _lk
from model import ascon

C62 = 1 << 62
LABELS = {"tag": 1, "pol": 2, "perm": 3, "dum": 4, "aead": 5}
E_MAX = 2                 # receiver looks at most E_MAX epochs ahead (§3.5 step 2)
EPOCH_LAST = 0xFFFF       # last epoch of a boot (§3.4)
ROOT_LABEL = "nv1-events"
RATCHET_LABEL = "nv1-ratchet"


@dataclass(frozen=True)
class SubKeys:
    tag: bytes
    pol: bytes
    perm: bytes
    dum: bytes
    aead: bytes


def _check_epoch(epoch):
    if not (isinstance(epoch, int) and 0 <= epoch <= EPOCH_LAST):
        raise ValueError(f"epoch {epoch!r} outside 0..{EPOCH_LAST:#x}")


def base(cam_id, boot_id):
    """48-bit session base cam_id[15:0] << 32 | boot_id[31:0]; cam_id must be nonzero."""
    if not (isinstance(cam_id, int) and 0 < cam_id < (1 << 16)):
        raise ValueError(f"cam_id {cam_id!r} must be 1 .. 0xFFFF")
    if not (isinstance(boot_id, int) and 0 <= boot_id < (1 << 32)):
        raise ValueError(f"boot_id {boot_id!r} must be 0 .. 2^32-1")
    return (cam_id << 32) | boot_id


def root_key(master, cam_id, boot_id):
    """K_ev[0] = kdf(master, 'nv1-events', C62 | base)."""
    return _lk.kdf(master, ROOT_LABEL, C62 | base(cam_id, boot_id))


def ratchet_step(k_prev, epoch):
    """K_ev[epoch] from K_ev[epoch-1]."""
    _check_epoch(epoch)
    if epoch == 0:
        raise ValueError("epoch 0 is the root key, not a ratchet step")
    return _lk.kdf(k_prev, RATCHET_LABEL, epoch)


def epoch_key(master, cam_id, boot_id, epoch):
    """K_ev[epoch] (epoch + 1 KDF calls)."""
    _check_epoch(epoch)
    k = root_key(master, cam_id, boot_id)
    for e in range(1, epoch + 1):
        k = ratchet_step(k, e)
    return k


def subkeys_of(k_ev):
    """The five packet subkeys of one epoch key."""
    return SubKeys(**{x: _lk.kdf(k_ev, "nv1-" + x, C62 | i) for x, i in LABELS.items()})


def subkeys(master, cam_id, boot_id, epoch):
    return subkeys_of(epoch_key(master, cam_id, boot_id, epoch))


def session_id(cam_id, boot_id, epoch):
    """sid = base << 16 | epoch (link.keys.session_id)."""
    _check_epoch(epoch)
    return _lk.session_id(base(cam_id, boot_id), epoch)


def split_session(sid):
    """(cam_id, boot_id, epoch) of a session id."""
    if not 0 <= sid < (1 << 64):
        raise ValueError(f"session id {sid!r} outside 64 bits")
    b, e = _lk.split_session(sid)
    return b >> 32, b & 0xFFFFFFFF, e


def nonce(sid, ctr, purpose):
    """Packet nonce (paper 1's make_nonce); sid 0 is the KDF's and is refused here."""
    if sid == 0:
        raise ValueError("session id 0 is reserved for the KDF")
    return ascon.make_nonce(sid, ctr, purpose)


def boot_id_from_kex(m1, m2):
    """kex profile: first 4 bytes, big-endian, of SHA-256(M1 || M2)."""
    return int.from_bytes(hashlib.sha256(bytes(m1) + bytes(m2)).digest()[:4], "big")


class EventRatchet:
    """Holds only the current epoch key K_ev[epoch] of one boot; forward() is one-way.

    peek(e) returns K_ev[e] without committing, or None if e is older than the current epoch, more than E_MAX
    ahead, or past EPOCH_LAST (so a junk header costs at most E_MAX KDF calls, §3.5 step 2).
    """

    def __init__(self, master, cam_id, boot_id, epoch=0):
        self.cam_id, self.boot_id = cam_id, boot_id
        self.epoch = epoch
        self.key = epoch_key(master, cam_id, boot_id, epoch)

    @classmethod
    def from_key(cls, k_ev, cam_id, boot_id, epoch):
        """Ratchet that starts from a known K_ev[epoch] (no master needed)."""
        _check_epoch(epoch)
        base(cam_id, boot_id)
        r = cls.__new__(cls)
        r.cam_id, r.boot_id, r.epoch, r.key = cam_id, boot_id, epoch, k_ev
        return r

    @property
    def sid(self):
        return session_id(self.cam_id, self.boot_id, self.epoch)

    def subkeys(self):
        return subkeys_of(self.key)

    def peek(self, epoch):
        if not isinstance(epoch, int) or epoch < self.epoch or epoch > self.epoch + E_MAX or epoch > EPOCH_LAST:
            return None
        k = self.key
        for e in range(self.epoch + 1, epoch + 1):
            k = ratchet_step(k, e)
        return k

    def forward(self, epoch=None):
        epoch = self.epoch + 1 if epoch is None else epoch
        k = self.peek(epoch)
        if k is None:
            raise ValueError(f"cannot move the ratchet from epoch {self.epoch} to {epoch} "
                             f"(older, more than E_MAX={E_MAX} ahead, or past EPOCH_LAST)")
        self.key, self.epoch = k, epoch
        return k
