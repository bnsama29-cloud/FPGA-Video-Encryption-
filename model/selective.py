"""Selective encryption stage (sits between run-length and Huffman, as in the hardware).

Each non-zero symbol carries a `size`-bit amplitude field (see entropy.py):
positive v -> v, negative v -> v + 2^size - 1 (ones' complement). Encryption
XORs keystream bits onto that field; the size never changes, so Huffman code
lengths and the file layout are unchanged (format compliant).

Contract v2 (identical to rtl/selective_enc.v):
    keystream bit 0          -> sign: if 1, invert ALL `size` bits of the field.
                                In JPEG's ones' complement coding that is exactly
                                v -> -v, so sign-only modes keep the magnitude.
    keystream bits 1..size-1 -> XOR onto the low size-1 field bits (bit k -> field
                                bit k-1), only in the "all bits" modes.
    A sign-only symbol consumes 1 keystream bit, an all-bits symbol `size` bits.

(Contract v1 flipped only the field MSB for "sign" encryption. That changes the
magnitude as well as the sign (e.g. 5 -> -6), so it was not sign encryption.)

Modes (value sets from section 6.1 of the project document):
    E0 : nothing encrypted (plain JPEG, tag only)
    E1 : AC signs
    E2 : AC signs + DC-difference signs                  (main configuration)
    E3 : E2 + all AC amplitude bits
    E4 : E3 + all DC-difference amplitude bits
    E5 : E4 + keyed shuffle of the MCUs (restart interval = 1 MCU; Hirose et al.
         2024). Amplitude/sign encryption never hides WHICH coefficients are
         non-zero, so E1-E4 all leak an edge sketch; E5 also moves every 16x16
         MCU to a secret position. Model only for now: the RTL does not emit
         restart markers yet.

Keystream bits are consumed strictly in coding order, only for selected fields.
Symbols with size 0 (EOB, ZRL, DC diff of 0) consume nothing.
Because XOR is an involution, the same function decrypts.
"""
from dataclasses import dataclass

from .entropy import Symbol, category


@dataclass(frozen=True)
class ModeCfg:
    ac_sign: bool
    dc_sign: bool
    ac_all: bool
    dc_all: bool
    shuffle: bool = False


MODES = {
    "E0": ModeCfg(False, False, False, False),
    "E1": ModeCfg(True, False, False, False),
    "E2": ModeCfg(True, True, False, False),
    "E3": ModeCfg(True, True, True, False),
    "E4": ModeCfg(True, True, True, True),
    "E5": ModeCfg(True, True, True, True, True),
}
MODE_ID = {name: i for i, name in enumerate(MODES)}       # E0 -> 0 ... E5 -> 5
MODE_NAME = {i: name for name, i in MODE_ID.items()}


def symbol_mask(size, ks_bits, all_bits):
    """XOR mask for one amplitude field from the keystream bits it consumed.

    ks_bits: int, bit j = j-th keystream bit for this symbol (LSB first)."""
    full = (1 << size) - 1
    mask = full if (ks_bits & 1) else 0
    if all_bits:
        mask ^= (ks_bits >> 1) & (full >> 1)
    return mask


def apply_keystream(symbols, ks, mode):
    """XOR keystream onto the selected amplitude bits.

    ks: an object with take(n) -> int (ascon.Keystream). Returns
    (new symbol list, number of encrypted bits).
    """
    cfg = MODES[mode]
    out = []
    app = out.append
    n = 0
    for s in symbols:
        size = s.size
        if size == 0:
            app(s)
            continue
        if s.is_dc:
            all_bits, sign = cfg.dc_all, cfg.dc_sign
        else:
            all_bits, sign = cfg.ac_all, cfg.ac_sign
        if all_bits:
            mask = symbol_mask(size, ks.take(size), True)
            n += size
        elif sign:
            mask = symbol_mask(size, ks.take(1), False)
            n += 1
        else:
            app(s)
            continue
        if mask == 0:
            app(s)
            continue
        a = s.amp
        b = (a if a >= 0 else a + (1 << size) - 1) ^ mask
        app(s._replace(amp=b if (b >> (size - 1)) else b - (1 << size) + 1))
    return out, n


def replacement_attack(symbols, mode):
    """Attacker without the key replaces encrypted values with fixed guesses.

    * AC sign encrypted only  -> take |amp| (magnitude is exact in contract v2)
    * AC amplitude encrypted  -> smallest positive value of the same size category
    * DC encrypted (any)      -> DC difference = 0 (flat grey blocks)
    The attacker re-encodes a valid JPEG from the result.
    """
    cfg = MODES[mode]
    out = []
    for s in symbols:
        if s.is_dc and (cfg.dc_sign or cfg.dc_all):
            out.append(Symbol(1, 0, 0, 0, 0, s.comp))
        elif not s.is_dc and s.size and cfg.ac_all:
            out.append(s._replace(amp=1 << (s.size - 1)))
        elif not s.is_dc and s.size and cfg.ac_sign:
            out.append(s._replace(amp=abs(s.amp)))
        else:
            out.append(s)
    return [s._replace(size=category(s.amp)) if (s.is_dc or s.size) else s for s in out]


def shuffle_order(n, ks):
    """Keyed uniform permutation of range(n) (Fisher-Yates, rejection sampling).

    ks: object with take(bits) -> int. Output position i carries MCU order[i]."""
    order = list(range(n))
    for i in range(n - 1, 0, -1):
        bits = i.bit_length()
        while True:
            j = ks.take(bits)
            if j <= i:
                break
        order[i], order[j] = order[j], order[i]
    return order
