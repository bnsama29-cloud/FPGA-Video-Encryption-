# Interface specification

Every interface the team agreed in week 1 (project document §13.2), as actually implemented. If you change one, change the RTL, the model and this file in the same commit.

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
| 0x08 | VERSION | RO | 0x5EC00100 |
| 0x10 | WIDTH | RW | pixels |
| 0x14 | HEIGHT | RW | pixels |
| 0x18 | FRAME_CTR | RW | frame counter, must strictly increase |
| 0x1C | SESSION_ID | RW | random per session |
| 0x20–0x2C | KEY0–KEY3 | WO (read 0) | KEY0 = key bytes 0..3, little-endian |
| 0x30 | OUT_BYTES | RO | scan bytes of the last frame |
| 0x34–0x40 | TAG0–TAG3 | RO | TAG0 = tag bytes 0..3, little-endian |
| 0x44 | QT_ADDR | RW | `[6]` table (0 luma, 1 chroma), `[5:0]` index (natural order) |
| 0x48 | QT_DATA | WO | 17-bit reciprocal `round(65536/Q)`, written at QT_ADDR, then QT_ADDR++ |

`WSTRB` is honoured; writes to unused addresses are ignored with an OKAY response.

Per-frame sequence (identical in `tb/test_top.py::Encoder` and the future PYNQ driver):
once per session write KEY0..3, SESSION_ID and the 128 QT_DATA values (QT_ADDR=0 first); per frame write WIDTH, HEIGHT, FRAME_CTR, then `CTRL = 1 | mode << 1`, start both DMA channels (receive first), wait for STATUS.DONE, read OUT_BYTES and TAG0..3.

## 4. Cryptography

* Cipher: Ascon-AEAD128, NIST SP 800-232 (little-endian word loading), 1 round per clock.
* Nonces (128-bit, four 32-bit little-endian words): `[FRAME_CTR, 0, SESSION_ID, purpose]`, purpose 0 = keystream N_enc, 1 = MAC N_mac.
* Keystream = Ascon-AEAD128 ciphertext of an all-zero message under (K, N_enc), no associated data. Bit *i* = bit (*i* mod 8) of byte (*i* div 8).
* Tag = Ascon-AEAD128 tag under (K, N_mac) with associated data = scan bytes (after stuffing) and an empty message.
* Selective encryption per symbol of size *s* > 0, when selected by the mode: keystream bit 0 = sign (if 1, invert all *s* amplitude bits); keystream bits 1..*s*−1 XOR the low *s*−1 amplitude bits (E3 for AC, E4 for DC). Sizes and runs never change, so Huffman code lengths are unchanged.

| Mode | AC sign | DC sign | AC low bits | DC low bits |
|---|---|---|---|---|
| E1 | ✓ | | | |
| E2 | ✓ | ✓ | | |
| E3 | ✓ | ✓ | ✓ | |
| E4 | ✓ | ✓ | ✓ | ✓ |

## 5. JPEG file layout (built by the ARM)

`SOI, APP0 (JFIF), APP11, DQT (2 tables, zig-zag order), SOF0 (3 comps, Y 2×2, Cb/Cr 1×1), DHT ×4 (Annex K), SOS, scan data, EOI`

APP11 payload: `"SJPG"`, version (1), mode (1), FRAME_CTR (4, LE), SESSION_ID (4, LE), tag (16). Viewers ignore it. Always parse headers by walking segments (`model.jpeg.segments`), never by searching for marker bytes: 0xFF 0xC0 can occur inside APP11 (see TESTING.md, bug log).

## 6. Arithmetic definitions (bit-exact contract)

* Colour: `Y = (77R + 150G + 29B + 128) >> 8`, `Cb = (−43R − 85G + 128B + 32896) >> 8`, `Cr = (128R − 107G − 21B + 32896) >> 8`, clamped 0..255; chroma = `(a + b + c + d + 2) >> 2` over each 2×2.
* DCT: `C[u][x] = round(2^13 · c(u)/2 · cos((2x+1)uπ/16))`; pass 1 on rows of (sample − 128) with `(Σ + 2^10) >> 11`, output transposed; pass 2 identical with `(Σ + 2^14) >> 15`.
* Quantiser: `q = sign(F) · ((|F|·R + 2^15) >> 16)`; DC clamped to −1024..1023, AC to −1023..1023.
