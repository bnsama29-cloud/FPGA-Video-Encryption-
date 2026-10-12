"""Selective encryption stage (sits between run-length and Huffman, as in the hardware).

Each non-zero symbol carries a `size`-bit amplitude field (see entropy.py).
Encryption XORs keystream bits onto that field; the size never changes.

    sign only : field ^= (k << (size-1))        consumes 1 keystream bit
    all bits  : field ^= k[size-1:0]            consumes `size` keystream bits

Modes (value sets from section 6.1 of the project document):
    E0 : nothing encrypted (plain JPEG, tag only)
    E1 : AC signs
    E2 : AC signs + DC-difference signs                  (main configuration)
    E3 : E2 + all AC amplitude bits
    E4 : E3 + all DC-difference amplitude bits

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


MODES = {
    "E0": ModeCfg(False, False, False, False),
    "E1": ModeCfg(True, False, False, False),
    "E2": ModeCfg(True, True, False, False),
    "E3": ModeCfg(True, True, True, False),
    "E4": ModeCfg(True, True, True, True),
}
MODE_ID = {name: i for i, name in enumerate(MODES)}       # E0 -> 0 ... E4 -> 4
MODE_NAME = {i: name for name, i in MODE_ID.items()}


def apply_keystream(symbols, ks, mode):
    """XOR keystream onto the selected amplitude bits.

    Returns (new symbol list, number of encrypted bits).
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
            mask = ks.bits(size)
            n += size
        elif sign:
            mask = ks.bits(1) << (size - 1)
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

    * AC sign encrypted only  -> take |amp| (magnitude is still correct)
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
