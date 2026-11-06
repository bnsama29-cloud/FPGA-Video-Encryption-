# Paper-1 crypto we can reuse for event packets (repo notes)

Read from branch `neuromorphic` (worktree `neuro_wt`), 6 Nov 2026. Sources: `software/model/ascon.py`,
`software/model/hw.py`, `software/model/selective.py`, `software/model/container.py`, `software/model/jpeg.py`,
`software/link/keys.py`, `software/link/feedback.py`, `docs/INTERFACES.md` §4/§8, and
`hardware/rtl/{ascon_aead128_core,ascon_round,keystream_gen,tag_unit,kseg_unit,skid_buf,byte_fifo}.v`.
Numbers marked *measured* come from files written by scripts; numbers marked *from RTL reading* are
cycle counts I derived from the FSMs and must be confirmed by a testbench before they go in the paper.

## 1. Python golden model (reuse as is)

### 1.1 `software/model/ascon.py` (NIST SP 800-232, checked against 1089 official KATs, `tests/test_ascon_kat.py`)

| Function | Signature | Returns / notes |
|---|---|---|
| `encrypt` | `encrypt(key: bytes16, nonce: bytes16, ad: bytes, plaintext: bytes) -> bytes` | `ciphertext || tag16`. Full AEAD; use for V4 baseline |
| `decrypt` | `decrypt(key, nonce, ad, ciphertext_with_tag) -> bytes | None` | `None` on tag failure (constant-time compare via `hmac.compare_digest`) |
| `mac` | `mac(key, nonce, data: bytes) -> bytes16` | `= encrypt(key, nonce, data, b"")`: tag over arbitrary bytes, data as AD, empty message. This is the per-frame tag primitive and the KDF primitive |
| `Keystream` | `Keystream(key, nonce)`; `.take(n) -> int`; `.next_block() -> bytes16`; counters `.blocks`, `.consumed` | streaming keystream (Ascon ciphertext of an endless zero message, empty AD). `take(n)`: bit j of the returned int = j-th bit handed out (LSB = first) |
| `keystream` | `keystream(key, nonce, nbytes) -> bytes` | first nbytes of the same stream |
| `keystream_bits` | `keystream_bits(key, nonce, nbits) -> list[int]` | bits in consumption order (testbench format) |
| `make_nonce` | `make_nonce(session_id: int<2^64, frame_ctr: int<2^63, purpose: 0|1) -> bytes16` | see 1.4 |
| `key_from_words` | `key_from_words([KEY0..KEY3]) -> bytes16` | register words -> key, KEY0 = key bytes 0..3 LE |
| `permutation` | `permutation(S: list[5 ints], rounds)` | Ascon-p in place (rounds 12 or 8 used) |
| `parse_kat` | `parse_kat(path) -> list[dict]` | KAT file reader |
| constants | `IV_AEAD128 = 0x00001000808C0001`, `RATE = 16`, `A_ROUNDS, B_ROUNDS = 12, 8`, `FRAME_CTR_BITS = 63`, `SESSION_ID_BITS = 64` | |

**Keystream bit order (contract v2, must be kept):** keystream bit *i* = bit (*i* mod 8) of keystream byte
(*i* div 8), LSB first. Keystream bytes = Ascon little-endian word output, i.e. byte 0..7 = state word x0
LE, 8..15 = x1 LE per 128-bit block. `Keystream.take(n)` and RTL `ks_bits[0]` both deliver the next unused
bit first. So for a 32-bit event word the natural mapping is `w ^= ks.take(32)` (bit 0 of the word gets
keystream bit 0) — any field-wise use must state which keystream bit goes to which field bit.

### 1.2 Tag / MAC over arbitrary bytes

* Generic: `ascon.mac(K, nonce, data)`.
* Frame tag (paper 1): `hw.frame_tag(key, mode, frame_ctr, session_id, width, height, scan, version=2) -> bytes16`
  = `ascon.mac(key, make_nonce(session_id, frame_ctr, 1), tag_prefix(...) + scan)`.
* AD prefix: `hw.tag_prefix(mode, frame_ctr, session_id, width, height, version=2) -> bytes26` =
  `container.auth_data(container.secure_meta(mode, session_id, frame_ctr, version), width, height, b"")`:
  `"SJV1" | version | mode | session_id (8 B BE) | frame_ctr (8 B BE) | width (2 B BE) | height (2 B BE)`.
  (Note: inside the AD the integers are **big-endian**; inside the nonce they are **little-endian**.)
* Encrypt-then-MAC: the tag covers the bytes **after** selective encryption; the receiver checks the tag
  before decrypting (`jpeg.receive_frame`).

### 1.3 Key derivation and ratchet — `software/link/keys.py` (imports `model.ascon`)

| Function | Signature | Definition |
|---|---|---|
| `kdf` | `kdf(key, label: str, ctx: int = 0) -> bytes16` | `ascon.mac(key, make_nonce(0, ctx, 1), label.encode())`; session id 0 (`KDF_SESSION`) is reserved for the KDF |
| `feedback_key` | `feedback_key(master)` | `kdf(master, "feedback")` |
| `video_key` | `video_key(master, epoch)` | `K[0] = kdf(master, "video", 0)`, `K[e] = kdf(K[e-1], "ratchet", e)` |
| `session_id` | `session_id(base: 1..2^48-1, epoch) -> int` | `base << 16 | epoch` (`EPOCH_BITS = 16`); base 0 rejected |
| `split_session` | `split_session(sid) -> (base, epoch)` | |
| `random_base` | `random_base() -> int` | 48 random bits, never 0 |
| `Ratchet` | `Ratchet(master, epoch=0)`; `.key`, `.epoch`, `.peek(epoch) -> key | None`, `.forward(epoch=None) -> key` | one-way; `peek` refuses old epochs |
| `kex_init / kex_respond / kex_finish / key_confirm` | hybrid ML-KEM-768 + X25519 session key (INTERFACES §9) | optional, ARM side only |

Other derived keys already in the model (same pattern "MAC under K with a label"):
`hw.segment_key(key, session_id, frame_ctr)` = `mac(K, nonce(sid, ctr, 0), b"lanes")` (RTL `kseg_unit.v`);
`hw.shuffle_key(key)` = `mac(K, nonce(0, 0, 0), b"E5 MCU shuffle")`.

Keyed permutation already in the model: `selective.shuffle_order(n, ks)` / `hw.e5_order(key, sid, ctr, n)` —
Fisher–Yates with rejection sampling on `Keystream.take(bit_length(i))`. Software only (ARM); rejection sampling
has the same variable-latency problem as cycle walking.

Replay checks: `jpeg.ReplayGuard().check(session_id, ctr) -> "ok" | "gap" | "replay"` (strictly increasing);
`feedback.ReplayWindow(size=64).check(ctr) -> bool` (RFC 3711 sliding window, tolerates UDP reordering —
better fit for packets over UDP).

### 1.4 Nonce packing (contract v2, `make_nonce`)

`nonce = session_id.to_bytes(8, "little") || (ctr << 1 | purpose).to_bytes(8, "little")`, hence Ascon state
x3 = `session_id`, x4 = `{ctr[62:0], purpose}`. Purpose 0 = N_enc (keystream), 1 = N_mac (tag). Reserved uses:
session 0 = KDF (`kdf`), nonce(0,0,0) = E5 shuffle key, nonce(s, ctr, 0) under K_seg = v3 segment keystreams.
For events: `session_id = keys.session_id(base, epoch)` (camera/stream base 48 b + epoch 16 b) and
`ctr = packet counter` (63 b) fit unchanged. A camera id would have to live inside the 48-bit base (or in the
AD prefix); the nonce has no free bits.

### 1.5 Selective-encryption helpers (JPEG-specific, pattern only)

`selective.symbol_mask(size, ks_bits, all_bits)`, `selective.apply_keystream(symbols, ks, mode) -> (symbols, nbits)`,
`hw.bits_needed(sym, mode)`, `hw.encrypt_symbol(sym, mode, ks_list)`, `hw.selective_encrypt(syms, mode, key, nonce) -> (syms, total_bits)`.
Rule worth copying: keystream bits are consumed strictly in stream order, only for selected fields, and XOR is
an involution, so one function encrypts and decrypts.

## 2. RTL modules (Verilog-2001, `default_nettype none`, sync active-high `rst`)

Handshake everywhere: valid/ready, transfer on a rising edge with both high, data held while `valid && !ready`.

### 2.1 `ascon_aead128_core` (Golden model: `ascon.py :: encrypt()`), no parameters

| Port | Dir | Width | Meaning |
|---|---|---|---|
| clk, rst | in | 1 | |
| init | in | 1 | pulse: load `{nonce[127:64], nonce[63:0], key[127:64], key[63:0], IV}`, run p12 (has priority over everything) |
| key, nonce | in | 128 | byte i = bits [8i+7:8i] (LE, same as the model's bytes) |
| blk_valid / blk_ready | in / out | 1 | `blk_ready = (state == S_READY)` (registered state; does not depend on valid) |
| blk_data | in | 128 | byte i = `blk_data[8i+7:8i]` |
| blk_bytes | in | 5 | 0..16 valid bytes; the core masks and pads (0x01 at byte `blk_bytes` when `blk_last`) |
| blk_type | in | 1 | 0 = AD, 1 = plaintext |
| blk_last | in | 1 | last block of its type; **the last block of each type must have `blk_bytes < 16`** (send an empty one if the length is a multiple of 16). No AD -> send no AD block (DSEP is applied with the first PT block) |
| ct_valid, ct_data | out | 1, 128 | pulse one clock after a PT block is accepted; bytes beyond `blk_bytes` masked to 0 |
| tag_valid, tag | out | 1, 128 | pulse when finalisation ends; tag byte i = bits [8i+7:8i] |

Timing (1 round per clock): init -> first block accepted after **13 clocks**, then **9 clocks per 128-bit block**
(1 accept + p8) — *measured*, `results/simulation/ascon_rate/ascon_rate.json` (`hardware/tb/test_ascon_core.py`).
= 14.2 keystream bits per clock (1.42 Gbit/s at 100 MHz). Final PT block -> p12 -> tag: about 13 clocks
*from RTL reading*. Size (post-route, `results/hardware/vivado/vivado_tables.md`, secure_jpeg_top_log_maxw9):
860–969 LUT, 458–585 FF, 0 BRAM, 0 DSP per instance.

### 2.2 `ascon_round` (combinational, Golden model: `ascon.py :: permutation()` one round)
Ports: `s_in[319:0]`, `rc[7:0]`, `s_out[319:0]`; packing `s = {x4, x3, x2, x1, x0}`, x0 = `s[63:0]`.
Core drives `rc = {~rnd, rnd}` (round r of 12; p8 starts at rnd = 4).

### 2.3 `keystream_gen` (Golden model: `ascon.py :: keystream_bits()`), no parameters

| Port | Dir | Width | Meaning |
|---|---|---|---|
| clk, rst | in | 1 | |
| start | in | 1 | pulse: re-init with (key, nonce), clears both slots; `ks_avail` = 0 until the first block (~15 clocks *from RTL reading*: 13 to accept + 1 ct register + 1 slot write) |
| key, nonce | in | 128 | sampled at `start` (by the core's `init`) |
| ks_bits | out | 16 | look-ahead window; `ks_bits[0]` = next unused bit (LSB-first order of 1.1) |
| ks_avail | out | 5 | valid bits in the window, 0..16, a register |
| ks_take | in | 1 | consume `ks_n` bits this clock |
| ks_n | in | 5 | bits to consume, must be `<= ks_avail`; header says 1..12 for JPEG, the logic accepts up to 16. Should come from a register (timing fix, bug #38) |

Internals: two 128-bit slots used as a ring + one block in flight; refill is automatic (plaintext = 0, never
finalised). Sustained supply = 128 bits / 9 clocks; burst up to 16 bits per clock while slots are full.
Size 949 LUT / 851 FF incl. its core (same table).

### 2.4 `tag_unit` (Golden model: `hw.py :: frame_tag()`), parameter `PREFIX_BYTES = 26` (legal 1..63)

| Port | Dir | Width | Meaning |
|---|---|---|---|
| clk, rst | in | 1 | |
| start | in | 1 | pulse: core init with (key, nonce = N_mac), latch `ad_prefix`, clear `tag_valid` |
| key, nonce | in | 128 | |
| ad_prefix | in | 8·PREFIX_BYTES | byte i = bits [8i+7:8i]; latched at `start`, so it must be known **before** the first stream byte |
| ad_valid / ad_ready | in / out | 1 | `ad_ready = (state == S_COLLECT) && !pend`, i.e. low while the prefix is absorbed |
| ad_data | in | 8 | one stream byte per handshake |
| ad_last | in | 1 | marks the final stream byte |
| tag_valid, tag | out | 1, 128 | `tag_valid` stays high until the next `start` |

How it absorbs prefix + stream: after `start` the FSM is in `S_PREFIX` and feeds the latched prefix one byte per
clock (`pref >> 8`), no handshake, into a 16-byte buffer; then `S_COLLECT` takes stream bytes. Whenever 16 bytes
are collected a full AD block is handed to the core (`pend`); `ad_last` closes a partial last block
(`blk_last`, padded by the core) or, if the AD length is a multiple of 16, an extra empty last AD block
(`S_ADEMPTY`); then an empty plaintext block (`S_PT`) triggers p12 and `S_WAIT` latches the tag. So
AD = prefix ‖ stream bytes, P = empty, exactly `ascon.mac(K, N_mac, prefix + stream)`.

Throughput *from RTL reading*: 1 stream byte per clock with one bubble per 16-byte block (≈16/17 B/clk) — the
byte-wide collector, not the core (16 B / 9 clk), is the limit. Per packet overhead *from RTL reading*:
PREFIX_BYTES clocks before `ad_ready` rises, and roughly 25 clocks from `ad_last` to `tag_valid`
(last AD block p8 + empty PT accept + p12 + latch). Size 1344 LUT / 1072 FF incl. core (same table).

Instantiation in `secure_jpeg_top.v`: nonce `n_mac`, prefix built from registers with `bswap64` (BE fields),
and the scan stream forked to `tag_unit` and `scan_word_packer` with
`ad_valid = b_valid && w_ready`, `b_ready = t_ready && w_ready`.

### 2.5 `kseg_unit` (Golden model: `hw.py :: segment_key()`), no parameters
Ports: `clk, rst, start, key[127:0], nonce[127:0]` (N_enc of the frame) in; `kseg_valid` (high until next
start), `kseg[127:0]` out. Computes `mac(K, N_enc, "lanes")`: init p12, one 5-byte AD block p8, empty PT p12,
"about 35 clocks" (header comment). Template for any fixed-label per-packet key derivation in hardware:
only the `AD` localparam (bytes, LE) and `blk_bytes` change.

### 2.6 Plumbing (no golden model)
* `skid_buf #(W = 8)`: `i_valid, i_ready, i_data[W-1:0]` -> `o_valid, o_ready, o_data[W-1:0]`; 2-entry, full
  rate, `i_ready` and outputs straight from flip-flops, +1 clock latency. Use to cut ready chains.
* `byte_fifo #(LOG_DEPTH = 11)`: `i_valid, i_ready, i_data[8:0]` (8 data + 1 flag) -> `o_valid, o_ready,
  o_data[8:0]`; BRAM-mapped, show-ahead output register, `full` registered. Width is fixed at 9 bits: a
  32-bit event FIFO needs a copy with a width parameter.

## 3. What has to change to authenticate event packets instead of JPEG scans

1. **Tag stream width.** `tag_unit` takes 8 bits per clock (≈0.94 B/clk *from RTL reading*); EVT 2.0 words are
   32 bits, so it would cap at about 0.24 words per clock. A word-wide collector (4 bytes per handshake, block
   every 4 words) is limited by the core at 16 B / 9 clk = 0.44 words per clock (*from the measured 9 clk/block*).
   One event per clock (4 B/clk) needs more than one round per clock (an unrolled core: 2 rounds/clk gives
   1 + 4 = 5 clk per block = 3.2 B/clk, still short; 4 rounds/clk gives 3 clk per block = 5.3 B/clk; timing at
   100 MHz unknown until Vivado) or several tag lanes combined by a defined rule — the latter changes the
   golden-model tag definition and must be specified in the model first.
2. **Prefix must be fixed-length and known at `start`.** Anything only known at packet end (event count, last
   timestamp) cannot go in the prefix; either put it in a trailer word inside the stream (it is then
   authenticated) or rely on the AD itself (a fixed-length prefix + Ascon padding makes the AD unambiguous, so
   insertion/deletion/truncation of words already changes the tag). `PREFIX_BYTES` must stay ≤ 63 (6-bit counter).
3. **Empty packets.** `tag_unit` forces `in_last = 0` during the prefix, so the stream must carry ≥ 1 byte with
   `ad_last`, otherwise the tag never finishes. A 1 ms packet with no events must still send one word
   (e.g. a time-high/trailer word). Specify this in the packet format.
4. **Back-to-back packets.** A new `start` restarts the core and aborts an unfinished tag, and `ad_ready` is low
   for PREFIX_BYTES clocks after `start`. For packets every 1 ms (100 000 clocks at 100 MHz) the ~50-clock gap is
   small, but the event stream must be buffered (FIFO) across it, or two `tag_unit`s used in ping-pong.
5. **New prefix layout.** `tag_prefix`/`secure_meta` are JPEG-specific (`"SJV1"`, mode 0..5, width/height).
   Events need their own identifier/version (must not collide with `"SJV1"` v2/v3 so a JPEG receiver rejects it),
   level V0–V4, session id, packet counter, W, H, packet start time — new model function + new RTL prefix wiring.
6. **Keystream per packet.** `keystream_gen` restarts on `start` with a new nonce: ~15 clocks with
   `ks_avail = 0` per packet (pre-start the next packet's generator or use two in ping-pong). Supply is 14.2 bits
   per clock sustained: V1 (1 bit/event) is fine at one event per clock; V3 (polarity + k timestamp bits) needs
   1 + k ≤ 14 bits per event per clock on average.
7. **More than two nonce purposes.** The nonce has 1 purpose bit (enc / mac) and no free bits. V2's permutation
   key (Feistel round keys) needs a third stream: derive it like contract v3 (`kseg_unit`, `segment_key`):
   `K_pkt = mac(K, nonce(sid, ctr, 0), label)` with N_enc used only for derivation, then sub-streams
   `Keystream(K_pkt, nonce(i, ctr, 0))` for i = 0, 1, … (polarity/timestamps, round keys). Do **not** use the
   same (K, nonce) both as a keystream and as a MAC with AD.
8. **Variable latency.** Cycle walking (V2) and rejection sampling (`shuffle_order`) both take a variable number
   of clocks; the existing keystream port (`ks_take`/`ks_n`) can feed a variable-rate consumer, but the
   permutation datapath itself needs a fixed-latency design or a FIFO + skid buffers. Nothing in the repo solves
   this yet.
9. **Replay window.** Packets over UDP can reorder; `feedback.ReplayWindow` (64-entry sliding window) fits better
   than `jpeg.ReplayGuard` (strictly increasing).
10. **Width-parameterised FIFO.** `byte_fifo` is hard-wired to 9 bits; event words need a `W` parameter (new
    module or a parameterised copy; do not change the paper-1 file while its Vivado run uses it).
11. **KDF reuse is free.** `keys.kdf / video_key / Ratchet / session_id` work unchanged for an event stream
    (labels e.g. `"events"`), provided the 48-bit base is non-zero.
