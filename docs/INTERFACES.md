# Interface specification (contract v2, and contract v3 for the lane encoder)

Every interface the team agreed in week 1 (project document §13.2), as actually implemented. If you change one, change the RTL, the model and this file in the same commit.

There is **one** contract. `model/jpeg.py` (frame-level golden model, used by the system simulation and the receiver) and `model/hw.py` (stage-level view, used by the RTL testbenches) are proven byte-identical by `tests/test_hw_equivalence.py`. Section 7 lists what changed from v1 and why.

## 1. Handshake convention (all internal streams)

`valid`/`ready`, data transferred on a rising edge where both are 1. Once `valid` is high, the sender must hold data stable until the transfer happens (AXI rule). `ready` may depend on `valid` and data; `valid` must never depend on `ready`. Every unit test applies random idle cycles on the input and random backpressure on the output to prove this.

## 2. Streams

| Interface | Width / fields | Order and framing |
|---|---|---|
| Pixels in (`s_axis_*`, DMA → `rgb2ycbcr_block`) | 32-bit: `[7:0]` R, `[15:8]` G, `[23:16]` B, `[31:24]` unused | raster order; frame start = `CTRL.START`; `TLAST` ignored |
| Samples (`rgb2ycbcr_block` → `dct8x8`) | 8-bit unsigned + `comp[1:0]` + `blast` + `flast` | 64 per block row-major; per MCU: Y0 Y1 Y2 Y3 Cb Cr; `flast` on last sample of the frame |
| Coefficients (`dct8x8` → `quantiser` → `zigzag_rle`) | 16-bit signed + `comp`, `blast`, `flast` | 64 per block, natural row-major order |
| Symbols (`zigzag_rle` → `selective_enc` → `huffman_enc`) | `is_dc`(1) `run`(4) `size`(4) `amp`(11) `eob`(1) `comp`(2) `flast`(1) | `amp` = the bits written to the file (negatives in ones' complement); ZRL = run 15 size 0; EOB = `eob` 1 |
| Keystream (`keystream_gen` → `selective_enc`) | `ks_bits[15:0]`, `ks_avail[4:0]`, `ks_take`, `ks_n[4:0]` | `ks_bits[0]` = next unused bit; consumer takes `ks_n ≤ ks_avail` bits per clock; restarts with the new nonce on START |
| Chunks (`huffman_enc` → `bit_packer`) | `bits[26:0]`, `len[4:0]`, `flast` | right-aligned, `bits[len-1]` first; code followed by amplitude bits |
| Scan bytes (`bit_packer` → `tag_unit` + `scan_word_packer`) | 8-bit + `last` | after 0xFF→0xFF 0x00 stuffing; final byte padded with 1s |
| Scan out (`m_axis_*` → DMA) | 32-bit + `TKEEP[3:0]` + `TLAST` | little-endian: first byte in `[7:0]`; `TLAST` on the final word; byte count in `OUT_BYTES` |

Frame size: width and height multiples of 16, width ≤ 2048 (parameter `LOG_MAXW`).

## 3. Registers (AXI4-Lite, 32-bit, `rtl/axil_regs.v`)

| Offset | Name | Access | Bits |
|---|---|---|---|
| 0x00 | CTRL | RW | `[0]` START (write 1, self-clearing), `[3:1]` MODE: 0 off, 1 E1, 2 E2, 3 E3, 4 E4 |
| 0x04 | STATUS | RO | `[0]` DONE, `[1]` BUSY, `[2]` TAG_VALID |
| 0x08 | VERSION | RO | 0x5EC00200 (contract v2, `secure_jpeg_top`); 0x5EC003LL (contract v3, `secure_jpeg_lanes_top`, LL = lanes) |
| 0x10 | WIDTH | RW | pixels |
| 0x14 | HEIGHT | RW | pixels |
| 0x18 | FRAME_CTR | RW | frame counter bits [31:0]; the 63-bit counter must strictly increase |
| 0x1C | SESSION_ID | RW | session id bits [31:0]; 64-bit, random per session |
| 0x20–0x2C | KEY0–KEY3 | WO (read 0) | KEY0 = key bytes 0..3, little-endian |
| 0x30 | OUT_BYTES | RO | scan bytes of the last frame |
| 0x34–0x40 | TAG0–TAG3 | RO | TAG0 = tag bytes 0..3, little-endian |
| 0x44 | QT_ADDR | RW | `[6]` table (0 luma, 1 chroma), `[5:0]` index (natural order) |
| 0x48 | QT_DATA | WO | 17-bit reciprocal `round(65536/Q)`, written at QT_ADDR, then QT_ADDR++ |
| 0x4C | SESSION_ID_HI | RW | session id bits [63:32] |
| 0x50 | FRAME_CTR_HI | RW | frame counter bits [62:32] (register bit 31 reads 0) |

`WSTRB` is honoured; writes to unused addresses are ignored with an OKAY response.

Per-frame sequence (identical in `tb/test_top.py::Encoder` and the future PYNQ driver):
once per session write KEY0..3, SESSION_ID, SESSION_ID_HI and the 128 QT_DATA values (QT_ADDR=0 first); per frame write WIDTH, HEIGHT, FRAME_CTR, FRAME_CTR_HI, then `CTRL = 1 | mode << 1`, start both DMA channels (receive first), wait for STATUS.DONE, read OUT_BYTES and TAG0..3.

## 4. Cryptography

* Cipher: Ascon-AEAD128, NIST SP 800-232 (little-endian word loading), 1 round per clock. Checked against the official KAT file `vectors/LWC_AEAD_KAT_128_128.txt` (1089 vectors) in Python and in RTL.
* Nonce (128-bit): bytes 0..7 = `session_id` (64-bit, little-endian), bytes 8..15 = `frame_ctr << 1 | purpose` (little-endian). So the Ascon state words are simply x3 = `session_id`, x4 = `{frame_ctr[62:0], purpose}`. Purpose 0 = keystream nonce N_enc, 1 = tag nonce N_mac. Model: `model/ascon.py :: make_nonce(session_id, frame_ctr, purpose)`.
* A (key, nonce) pair must never repeat: never reuse a frame counter in a session, and use a fresh random 64-bit session id (or a new key) for every session. With 64 random bits a collision is expected only after ~2^32 sessions.
* Keystream = Ascon-AEAD128 ciphertext of an all-zero message under (K, N_enc), no associated data. Bit *i* = bit (*i* mod 8) of byte (*i* div 8), i.e. LSB first.
* Tag = Ascon-AEAD128 tag under (K, N_mac) with an empty message and associated data = **26-byte prefix || scan bytes (after stuffing)**. The prefix is the APP11 metadata plus the frame size (section 5); the RTL builds it from the registers at START (`rtl/secure_jpeg_top.v`, `tag_prefix`) and `tag_unit.v` absorbs it before the first scan byte.
* Selective encryption per symbol of size *s* > 0, when selected by the mode: keystream bit 0 = sign (if 1, invert all *s* amplitude bits, which in JPEG's ones' complement coding is exactly v → −v); keystream bits 1..*s*−1 XOR the low *s*−1 amplitude bits (bit *k* → field bit *k*−1; E3 for AC, E4 for DC). Sizes and runs never change, so Huffman code lengths are unchanged. A sign-only symbol consumes 1 keystream bit, an all-bits symbol *s* bits.

| Mode | AC sign | DC sign | AC low bits | DC low bits |
|---|---|---|---|---|
| E1 | ✓ | | | |
| E2 | ✓ | ✓ | | |
| E3 | ✓ | ✓ | ✓ | |
| E4 | ✓ | ✓ | ✓ | ✓ |

## 5. JPEG file layout (built by the ARM)

`SOI, APP0 (JFIF), APP11, DQT (2 tables, zig-zag order), SOF0 (3 comps, Y 2×2, Cb/Cr 1×1), DHT ×4 (Annex K), SOS, scan data, EOI`

APP11 (marker 0xFFEB) payload, 38 bytes, ignored by normal viewers:

| Bytes | Field | Encoding |
|---|---|---|
| 0..3 | `"SJV1"` | ASCII identifier |
| 4 | version | 2 (contract v2) or 3 (contract v3, section 8); any other value is rejected |
| 5 | mode | 0..4 = E0..E4 |
| 6..13 | session_id | 64-bit big-endian |
| 14..21 | frame_ctr | 64-bit big-endian (top bit 0) |
| 22..37 | tag | 16 bytes, Ascon-AEAD128 tag |

Tag AD prefix (26 bytes) = APP11 bytes 0..21 || width (2 B big-endian) || height (2 B big-endian). Model: `model/container.py :: secure_meta(), auth_data()`, `model/hw.py :: tag_prefix()`. Always parse headers by walking segments (`model.container.parse_jpeg`), never by searching for marker bytes: 0xFF 0xC0 can occur inside APP11 (see TESTING.md, bug log).

## 6. Arithmetic definitions (bit-exact contract)

* Colour: `Y = (77R + 150G + 29B + 128) >> 8`, `Cb = (−43R − 85G + 128B + 32896) >> 8`, `Cr = (128R − 107G − 21B + 32896) >> 8`, clamped 0..255; chroma = `(a + b + c + d + 2) >> 2` over each 2×2.
* DCT: `C[u][x] = round(2^13 · c(u)/2 · cos((2x+1)uπ/16))`; pass 1 on rows of (sample − 128) with `(Σ + 2^10) >> 11`, output transposed; pass 2 identical with `(Σ + 2^14) >> 15`.
* Quantiser: `q = sign(F) · ((|F|·R + 2^15) >> 16)`; DC clamped to −1024..1023, AC to −1023..1023.

## 7. Changes from contract v1 (12 Oct 2026) and why

The GitHub golden model and the RTL repo had drifted apart: the JPEG part was the same, but on one 64×64 test image 335 of 348 scan bytes differed in mode E2. A board running the old RTL would have been rejected by the old receiver. Contract v2 takes the stronger choice from each side:

| Item | Golden model v1 | RTL v1 | v2 (now) | Why |
|---|---|---|---|---|
| Sign encryption | flip the field MSB | invert all field bits | invert all bits (RTL) | Flipping only the MSB also changes the magnitude (5 → −6), so it was not sign encryption; inverting all bits is exactly v → −v in ones' complement coding |
| Keystream bit order | MSB first | LSB first | LSB first (RTL) | Matches Ascon's little-endian byte order, no RTL change |
| Nonce | session 64 b + counter 63 b, big-endian | 32-bit words, session and counter 32 b | 64 b + 63 b, little-endian | 32-bit random session ids collide after ~65k sessions (nonce reuse = keystream reuse). LE layout maps straight onto Ascon state words |
| Tag AD | meta + size + scan | scan only | meta + size + scan | v1 RTL did not authenticate the mode byte: an attacker could change E2 → E1 and the receiver would show a wrongly decrypted frame as authentic |
| APP11 | `SJV1`, big-endian, 38 B | `SJPG`, little-endian | `SJV1`, version 2 | Golden layout; version bumped so old frames are rejected, not misread |
| DCT | one pass, 12-bit matrix | two passes, 13-bit | two passes (RTL) | ~6% of v1 golden coefficients differed by ±1 from the RTL; v2 accuracy is still within 1 of the exact DCT |
| Quantiser | division | reciprocal multiply + clamp | reciprocal (RTL) | One DSP, no divider; the golden model now does the same |
| KAT file | 00..0F nonces | official SP 800-232 file | official file | Both pass; the official file is the one to cite |

## 8. Contract v3: parallel lanes over restart segments (16 Oct 2026)

Encoder `rtl/secure_jpeg_lanes_top.v` (parameter `LANES` = 1, 2 or 4); model
`model/hw.py :: encode_frame_v3()` = `model/jpeg.py :: encode_frame(..., segmented=True)` (proven equal
by `tests/test_hw_equivalence.py`). Contract v2 and `secure_jpeg_top.v` are unchanged and remain the
default; a receiver accepts both and tells them apart by the APP11 version byte.

Why: one v2 pipeline consumes one sample per clock, and 4:2:0 has 1.5 samples per pixel, so it can
never do better than 1.5 clocks per pixel (65 Mpx/s at 100 MHz). A JPEG restart marker resets the DC
predictors and byte-aligns the stream, so the data between two markers can be coded with no knowledge
of the rest. v3 makes every MCU row a restart segment and gives every segment its own keystream, so
`LANES` copies of the pipeline can code segments at the same time; a merger writes them back in order.
The bytes do not depend on `LANES` (checked on the RTL for 1, 2 and 4 lanes by `tb/test_lanes_top.py`).

| Item | Contract v3 |
|---|---|
| Segments | segment *s* = MCU row *s*; restart interval = width/16 MCUs; the ARM writes a DRI segment (0xFFDD) with that value |
| Scan | seg0 ‖ RST0 ‖ seg1 ‖ RST1 ‖ … ‖ seg(n−1), markers 0xFFD0 + (s mod 8), none after the last; each segment padded to a byte with 1s and stuffed on its own |
| DC prediction | all three predictors reset to 0 at the start of every segment (T.81 F.1.2.3) |
| Segment key | K_seg = Ascon-AEAD128 tag under (K, N_enc), AD = the 5 ASCII bytes `lanes`, empty message (`rtl/kseg_unit.v`, `segment_key()`). In v3, N_enc is used only for this derivation |
| Segment keystream | keystream of (K_seg, nonce(s, frame_ctr, 0)), i.e. Ascon x3 = s, x4 = {frame_ctr, 0}; restarts at every segment, same bit order and selection rules as section 4 |
| Nonce uniqueness | K_seg is unique per (K, session_id, frame_ctr), and under one K_seg the segment index *s* is unique, so no (key, nonce) pair repeats. A session uses one contract version for all its frames |
| Tag | as v2 (section 4), but the 26-byte prefix carries version 3, and the AD scan bytes include the RST markers |
| APP11 | version byte 3 |
| Modes | E0–E4. E5 (keyed MCU shuffle) stays a contract-v2 model feature |
| Pixel stream | `s_axis_tdata` 64 bits = 2 pixels per beat: `[31:0]` = left pixel `{pad, B, G, R}`, `[63:32]` = right pixel. The byte stream in memory is the same as v2's 32-bit words, so the DMA buffer does not change; only the DMA's MM2S width is 64 bits |
| Dealer | MCU row *r* (16 lines) goes to lane *r* mod LANES; LANES is a power of two |
| Lane | `rtl/encoder_lane.v`: `rgb2ycbcr_2px` (2 pixels per clock in, 1 sample per clock out) → the v2 DCT, quantiser, `zigzag_rle` (SEG_RESET = 1), `selective_enc` + `keystream_gen` (restarted per segment), `huffman_enc`, `bit_packer` (flushes at each segment end) → `byte_fifo` (2^LOG_FIFO bytes) |
| Merger | `rtl/segment_merger.v`: copies segment *s* from lane *s* mod LANES, then writes 0xFF, 0xD0 + (s mod 8) |
| Receiver | decodes and decrypts each segment on its own and re-codes the clear frame without restart markers, so the clear output is byte-identical to the v2 plain JPEG |

Cost: about 0.3 % more bytes (one 2-byte marker and up to 7 padding bits per MCU row; measured
by `experiments/parallel_lanes.py`), one extra Ascon core per lane (keystream) plus `kseg_unit`, and
per-lane line buffers.
