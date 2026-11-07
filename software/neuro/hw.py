"""Stage view of the sender for the RTL testbenches (DESIGN §6, §7.1). Must match the packet view.

The packet view (neuro.packet, neuro.sender) works on whole packets as bytes. The hardware sees one 32-bit word
per clock, so the testbenches need the same packet split into the words and blocks each RTL stage handles:

    header_words(hdr)              the 12 AXI words of the 48-byte header (nv_packetizer output)
    trailer_words(tr)              bitmap words then n_words, n_cd, rsvd (nv_trailer output at EOP)
    table_fill_entries(...)        (table, index, value) in nv_table_gen write order
    feistel_round(x, y, j, t)      one round of nv_feistel
    xor_word(w, k, b)              nv_xor on one CD word with its 1 + b keystream bits
    tag_blocks(...)                the exact Ascon block sequence nv_tag32 hands to the core
    tag_input(...)                 the bytes the tag covers (header || payload || trailer)
    out_words(packet)              the AXI output words of one packet (nv_out_mux), tlast on the last
    commit_ok(...)                 the §6.7 commit rule (same function as the sender's)

AXI word j of a byte string carries bytes 4j..4j+3 with byte 4j in bits [7:0] (DESIGN §3.3), so an EVT word
in the payload appears on AXI as itself, and the big-endian header fields appear byte-swapped.
`tests/test_neuro_equivalence.py` checks that this view and the packet view agree.
"""
import numpy as np

from model import ascon

from . import sender
from .feistel import make_tables
from .keys import nonce
from .packet import HEADER_LEN, Packet, PacketHeader, Trailer

RATE = 16
AD, PT = 0, 1
MAC, ENC = 0, 1
KIND_HDR, KIND_PAY, KIND_TRL = 0, 1, 2


def words_of(b):
    """AXI words of a byte string whose length is a multiple of 4."""
    b = bytes(b)
    if len(b) % 4:
        raise ValueError(f"length {len(b)} is not a multiple of 4")
    return np.frombuffer(b, dtype="<u4").astype(np.uint32).tolist()


def bytes_of(words):
    return np.asarray(words, dtype="<u4").tobytes()


def header_words(hdr: PacketHeader):
    return words_of(hdr.pack())


def trailer_words(tr: Trailer):
    return words_of(tr.pack())


def table_fill_entries(k_perm, sid, ctr, W, H):
    """[(j, i, value)] in fill order: table 0 first, then index order (nv_table_gen write order)."""
    t = make_tables(k_perm, sid, ctr, W, H)
    return [(j, i, int(v)) for j in range(t.r) for i, v in enumerate(t.t[j].tolist())]


def feistel_round(x, y, j, tables):
    """Round j of P_ctr on one point (nv_feistel round j: add, then one compare-and-subtract)."""
    if j % 2 == 0:
        s = x + int(tables.t[j][y])
        return (s - tables.W if s >= tables.W else s), y
    s = y + int(tables.t[j][x])
    return x, (s - tables.H if s >= tables.H else s)


def xor_word(w, k, b):
    """nv_xor on one real CD word: k holds the 1 + b keystream bits, bit 0 first."""
    return (int(w) ^ ((k & 1) << 28) ^ (((k >> 1) & ((1 << b) - 1)) << 22)) & 0xFFFFFFFF


def _blocks(data, typ):
    """Full blocks with blk_last = 0, then one final block with blk_bytes < 16 and blk_last = 1."""
    out = []
    n_full = len(data) // RATE
    for i in range(n_full):
        out.append((data[RATE * i:RATE * (i + 1)], RATE, 0, typ))
    rest = data[RATE * n_full:]
    out.append((rest + bytes(RATE - len(rest)), len(rest), 1, typ))
    return out


def tag_blocks(header, payload, trailer, mode=MAC):
    """Exact block sequence handed to the Ascon core by nv_tag32: [(16 data bytes, blk_bytes, blk_last, type)].

    MAC (V0-V3): AD = header || payload || trailer, then one empty final PT block (finalisation, tag).
    ENC (V4):    AD = header, PT = payload || trailer.
    The core needs blk_bytes < 16 on the last block of each type, so a length that is a multiple of 16 ends
    with an empty block (`ascon_aead128_core.v` header).
    """
    h = bytes(header)
    body = bytes_of(payload) + bytes(trailer)
    if mode == MAC:
        return _blocks(h + body, AD) + [(bytes(RATE), 0, 1, PT)]
    return _blocks(h, AD) + _blocks(body, PT)


def tag_input(header, payload, trailer):
    """Bytes covered by the V0-V3 tag (DESIGN §3.3)."""
    return bytes(header) + bytes_of(payload) + bytes(trailer)


def run_blocks(key, nonce_b, blocks):
    """Feed a tag_blocks sequence to the reference Ascon (model.ascon) the way the core absorbs it.

    Returns (ciphertext, tag). Used by the equivalence test to show the block sequence is the packet's tag.
    """
    ad = b"".join(d[:n] for d, n, _, t in blocks if t == AD)
    pt = b"".join(d[:n] for d, n, _, t in blocks if t == PT)
    ct = ascon.encrypt(key, nonce_b, ad, pt)
    return ct[:-16], ct[-16:]


def out_words(packet: Packet):
    """[(word, tlast)] of one packet on the AXI output (tlast on the last tag word)."""
    w = packet.to_words().tolist()
    return [(int(v), int(i == len(w) - 1)) for i, v in enumerate(w)]


def packet_words_kinds(packet: Packet):
    """[(word, kind)] of the ordered stream before the tag (kind 0 header, 1 payload, 2 trailer)."""
    h = header_words(packet.header)
    if packet.header.level == 4:
        body = words_of(packet.body)
        n_pay = len(packet.payload)
        return [(w, KIND_HDR) for w in h] + [(w, KIND_PAY if i < n_pay else KIND_TRL) for i, w in enumerate(body)]
    return ([(w, KIND_HDR) for w in h] + [(int(w), KIND_PAY) for w in packet.payload]
            + [(w, KIND_TRL) for w in trailer_words(packet.trailer)])


def check_packet(packet: Packet, sk):
    """Recompute the tag of a sealed packet from its stage-view blocks; True if equal (equivalence test)."""
    h = packet.header
    sid, ctr = h.session_id, h.packet_ctr
    if h.level == 4:
        blocks = tag_blocks(h.pack(), packet.payload, packet.trailer.pack(), ENC)
        ct, tag = run_blocks(sk.aead, nonce(sid, ctr, 0), blocks)
        return ct == packet.body and tag == packet.tag
    blocks = tag_blocks(h.pack(), packet.payload, packet.trailer.pack(), MAC)
    _, tag = run_blocks(sk.tag, nonce(sid, ctr, 1), blocks)
    return tag == packet.tag


commit_ok = sender.commit_ok
HEADER_WORDS = HEADER_LEN // 4
