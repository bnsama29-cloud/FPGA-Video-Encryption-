# Golden model — Secure JPEG/MJPEG video link (PYNQ-Z2, Ascon-AEAD128)

A complete Python implementation of the transmitter and receiver from the project
document. It is (1) the reference that defines "correct" for every hardware block,
(2) the source of test vectors for cocotb/HLS testbenches, and (3) the key-holder
receiver that verifies and decrypts the stream on the laptop.

## 1. Setup (once)

Needs Python 3.10 or newer.

```bash
cd golden_model
python -m venv venv
# Linux / macOS:
source venv/bin/activate
# Windows (PowerShell):
venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Optional but recommended: VLC (to play the scrambled stream) and FFmpeg (to remux files).

## 2. Prove the model is correct (milestone M0)

```bash
python -m pytest
```

All 35 tests must pass. They check: all 1089 official Ascon-AEAD128 known-answer
vectors (NIST SP 800-232), colour extremes, DCT accuracy, quantiser rounding of
negatives, every amplitude size 1–11, run-length edge cases (all zeros, ZRL, last
coefficient non-zero), 0xFF stuffing and 1-padding, Huffman round trip, closeness to
libjpeg, bit-exact decryption for E0–E4, zero size change before stuffing, software
path = in-encoder path byte-for-byte, tamper/replay/reorder/drop detection.

## 3. Quick check on one image

```bash
python scripts/encode_image.py                      # built-in sample photo
python scripts/encode_image.py my_photo.jpg --out out_image
```

Open `out_image/scrambled_E2.jpg` in any image viewer: it opens, but scrambled.

## 4. Run on an actual video and get metrics

No video handy? Make one:

```bash
python scripts/make_test_video.py --out test_video.mp4 --frames 90
```

Run the evaluation (any .mp4/.avi/.mov that OpenCV can read, or a webcam index):

```bash
python scripts/run_video_eval.py --video test_video.mp4 --out results
python scripts/run_video_eval.py --video my_clip.mp4 --out results --max-frames 60 --quality 50 75 90
python scripts/run_video_eval.py --video 0 --out results_webcam --max-frames 20
```

Useful options:

| Option | Default | Meaning |
|---|---|---|
| `--size 640x480` | 640x480 | resize frames (Level 1 resolution); `none` keeps original |
| `--max-frames N` | 30 | how many frames to process |
| `--stride N` | 1 | use every Nth frame (spread samples over a long clip) |
| `--quality 50 75 90` | 75 | one or more JPEG quality settings |
| `--modes E1 E2 E3 E4` | all four | value sets to evaluate |
| `--main-mode E2` | E2 | mode used for output videos and integrity tests |
| `--deep-every N` | 10 | key-sensitivity / statistics on every Nth frame |
| `--tamper-frames N` | 10 | frames used for tamper/replay tests |

Speed: about 7 s per frame per quality at 640x480 on a typical laptop (it does
every mode, decryption, attacks and metrics). Use `--size 320x240` or `--stride` for
quick runs. These are PC timings of pure Python, so use them only for relative
comparisons; real fps, latency and energy numbers must come from the board.

### What you get in `results/`

| File | Contents |
|---|---|
| `frames.csv` | one row per frame × quality × mode, every metric |
| `summary.csv`, `summary.json` | mean and std per quality × mode → paper tables |
| `integrity.csv` | detection rate for each tamper/sequence attack (RQ3) |
| `plots/rq1_security_vs_cost.png` | encrypted-bit % vs SSIM under attack (RQ1) |
| `plots/visual_security_*.png` | PSNR/SSIM an attacker sees, no key and under attack |
| `plots/size_overhead.png`, `plots/timing_pc.png` | overhead and relative timing |
| `samples/` | first frame: original, plain, scrambled, decrypted, attack images |
| `scrambled_E*.mjpeg` | exactly the bytes VLC would receive |
| `decrypted_E2.mjpeg` | what the key holder recovers |
| `comparison_E2.mp4` | original / no-key view / receiver output side by side |
| `modes_grid.mp4` | original plus the no-key view of every mode |

### What each metric means

| Column | Meaning | What you want |
|---|---|---|
| `psnr_vs_orig`, `ssim_vs_orig` (PLAIN rows) | compression quality without encryption | ~33–38 dB at Q75 |
| `psnr_nokey`, `ssim_nokey` | what VLC / an attacker without the key sees | low (PSNR < 10 dB, SSIM < 0.2) |
| `psnr_attack`, `ssim_attack` | replacement attack: encrypted values set to fixed guesses | low; shows leakage |
| `enc_bits_pct` | encryption space: % of scan payload bits encrypted | cost side of RQ1 |
| `overhead_bytes` | scan size change vs plain (only 0xFF stuffing can change it) | ~0 |
| `bit_exact` | receiver output == plain encoder output, byte for byte | 1 (100%) |
| `compliant` | Pillow and OpenCV/libjpeg both decode the encrypted frame | 1 (100%) |
| `sw_equals_hw` | software post-hoc encryption == in-encoder encryption | 1 (100%) |
| `npcr_keychange`, `uaci_keychange` | no-key images under K vs K with 1 bit flipped | high NPCR |
| `psnr_wrongkey` | decrypting with a key off by one bit | as low as no key |
| `entropy_*`, `corr_*` | histogram entropy, adjacent-pixel correlation | correlation drops |
| `t_*_ms` | PC Python timing (relative only) | — |

What the first run shows (and is worth discussing in the paper): E1 alone leaves the
picture recognisable, because unencrypted DC values give a blocky thumbnail; E2–E4
are unrecognisable. Under the replacement attack every mode still leaks edge outlines,
because size categories (code lengths) are never encrypted — this is the leakage
noted in section 6.1, now measurable.

### Watching the videos

```bash
ffplay -f mjpeg results/scrambled_E2.mjpeg
# or make an AVI with the exact same JPEG bytes (no re-encoding) for VLC:
ffmpeg -f mjpeg -framerate 30 -i results/scrambled_E2.mjpeg -c copy results/scrambled_E2.avi
```

`comparison_E2.mp4` and `modes_grid.mp4` play in any player.

## 5. Live stream demo (mirrors the board)

Terminal 1 — the "board":

```bash
python scripts/mjpeg_server.py --video test_video.mp4 --mode E2 --tamper 7
```

Then either open VLC → Media → Open Network Stream → `http://localhost:8080/stream.mjpg`
(scrambled video), and/or in terminal 2 run the key holder:

```bash
python scripts/receiver.py --url http://localhost:8080/stream.mjpg
```

The receiver window shows the VLC view on the left and the verified, decrypted frame on
the right; `--tamper 7` corrupts every 7th frame and you will see `REJECTED: tag-mismatch`.
A `GAP` verdict means a counter was skipped (a dropped frame — by the network, a slow
client or an attacker). The receiver also reads recorded files:

```bash
python scripts/receiver.py --file results/scrambled_E2.mjpeg --save-dir rx_frames
```

When the board is ready, point the same receiver at the board's IP. Because the model
defines the format, a board stream that this receiver accepts is a correct stream.

## 6. Test vectors for the hardware (R1, R2, R3)

```bash
python scripts/export_vectors.py --sample astronaut --size 64x64 --out vectors/astro64
python scripts/export_vectors.py --video test_video.mp4 --frame 10 --size 640x480 --out vectors/v640
```

Each stage is written as one hex value per line (`$readmemh`/cocotb friendly) plus
`stages.npz` for Python testbenches. See the docstring in `scripts/export_vectors.py`
for every file and the packed symbol format. The cocotb example in section 15 of the
project document works unchanged: `from model.jpeg import quantise, Q_LUMA`.
`vectors/LWC_AEAD_KAT_128_128.txt` holds the official Ascon vectors for the RTL core.

## 7. Bit-exact contracts the hardware must follow

These were left open in the project document; the model fixes them. Add them to the
interface-contract table (section 13.2).

1. **Colour conversion** (`model/color.py`): integer BT.601 with the exact constants and
   rounding in the docstring; 4:2:0 = `(a+b+c+d+2)>>2`; edge-replicate to multiples of 16.
2. **DCT** (`model/dct_quant.py`): level shift −128, 12-bit fixed-point matrix `T_INT`,
   exact integer product, round half away from zero at 2^24. Within ±1 of the exact DCT,
   and simple to reproduce bit-exactly in Vitis HLS with `ap_int<40>` accumulators.
3. **Quantiser**: `sign(F) * ((|F| + Q/2) // Q)`.
4. **Selective encryption** (`model/selective.py`): XOR on the raw amplitude field;
   sign = MSB of the field. Keystream bits are consumed in coding order, only for
   selected fields, MSB-first within each keystream byte.
5. **Keystream**: Ascon-AEAD128 encryption of an all-zero message, empty AD, under N_enc.
6. **Nonces**: `session_id (64 bits) || frame_ctr (63 bits) || purpose bit`
   (0 = encryption, 1 = tag).
7. **Tag AD** — one deliberate addition to the document: the tag covers
   `APP11 metadata (22 bytes: 'SJV1', version, mode, session, counter) || width || height || scan data`,
   not the scan data alone. Without this, an attacker could change the mode byte and the
   receiver would decrypt wrongly while the tag still verified. In hardware the tag engine
   simply absorbs these words from registers before the scan bytes.
8. **Packing**: MSB-first bit packer, last byte padded with 1s, then 0xFF → 0xFF 0x00.
9. **Pixel word**: R in bits [7:0], G [15:8], B [23:16], pad [31:24].

## 8. File map

```
model/ascon.py       Ascon-AEAD128 (SP 800-232), keystream generator, MAC, nonces
model/color.py       RGB→YCbCr, 4:2:0, MCU blocking
model/dct_quant.py   fixed-point DCT, quantisation tables, quantiser
model/entropy.py     zig-zag, run-length symbols, Huffman encode/decode, stuffing
model/selective.py   modes E0–E4, keystream XOR, replacement attack
model/container.py   JPEG headers, APP11 secure segment, parser, MJPEG splitter
model/jpeg.py        encode_frame / receive_frame / software baselines / ReplayGuard
model/metrics.py     PSNR, SSIM, NPCR/UACI, correlation, entropy
scripts/             evaluation, streaming, receiver, vector export, demos
tests/               pytest suite (run before every merge)
```
