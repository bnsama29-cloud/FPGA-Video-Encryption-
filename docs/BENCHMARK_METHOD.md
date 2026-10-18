# How we measure E5 against published work (method note, 18 Oct 2026)

This note says how the security and hardware numbers for E5 are produced, so a reviewer can line them up
with the papers we compare against. Every number comes from a script in `experiments/` that writes to
`sim_out/`. The paper only states rows that are ✅ in GUIDE.md §5.

## 1. What changed on 18 Oct 2026, and why

| Before | Now | Why |
|---|---|---|
| A4 "cross-frame" was **handed** the true permutation of frame 0 | A4 is a **known-plaintext attacker**: from one clear frame and its ciphertext it recovers the permutation *and* the keystream bits, then uses both on the following frames | Papers attack with a known or chosen plaintext (Li et al. [li2025shuffle] use one designed frame); a handed permutation is not an attack a reviewer recognises, and it ignored keystream reuse |
| Security tables reported only edge correlation | Each scheme also gets PSNR, SSIM, entropy, adjacent-pixel correlation (h/v/d) and NPCR/UACI (key and one-pixel) | These are what selective-encryption papers print (Hirose et al. [hirose2024]: PSNR/SSIM, key sensitivity, histograms; Kishore et al. [kishore2015], Auer et al. [auer2013]: PSNR and visual) |
| Means over frames only | Every mean has a 95 % percentile-bootstrap interval over frames | Lets a reader see whether two schemes differ |
| One quality factor (75), 320x240 for every source | `--quality 50 75 90` sweep, and `--size native` / `768x512` for Kodak | Image papers report Kodak at its own size and several quality factors |
| Standard metrics measured E5 only in the model's v2 form | They also measure **E5 (v3, hw)**, the form the lane-encoder RTL produces | The paper's claims are about the hardware |
| Hardware compared by raw LUT and Mpixel/s | `experiments/hw_efficiency.py` adds Mpixel/s per kLUT, input Gbit/s and nJ per pixel, per mode (E5 has its own rows) | Hardware papers compare throughput per area and energy per unit of work |

E5 itself is unchanged: the RTL, the model and contract v3 are exactly as in commit b41c733. Only the
way it is measured changed. The SVE-Bench numbers in `paper/data/benchmark/` were made with the old A4
and without the new metrics, so they must be re-run (Kaggle `JOB = "benchmark"`) before the new columns
can go into the paper.

## 2. Threat model of each attack (SVE-Bench, `experiments/benchmark_suite.py`)

The attacker knows every scheme (Kerckhoffs) and sees only the bytes on the network.

| Attack | The attacker has | It does | Score |
|---|---|---|---|
| A1 decode | the stream | opens it in a normal viewer | edge correlation of the picture with the original |
| A2 replacement | the stream | replaces every encrypted field with a fixed guess and decodes | same |
| A3 NZCA | the stream | counts non-zero AC coefficients per luma block (sketch attack) | correlation with the original block edge energy |
| A4 known plaintext | the stream **and one frame in clear** (the loaded frame with the most detail) | matches received segments/blocks to clear ones by structure (run, size, EOB, and amplitudes that are not encrypted) to recover the permutation; XORs clear and received fields to recover the keystream bits; on every other frame it undoes the permutation and decrypts with those bits (and, for permuting schemes, also tries replacement and NZCA) | best of those |

**Max leak** is the strongest of A1-A4 (means over the scored frames, i.e. all but the known one, with the interval of that attack).
The share of the known frame's permutation recovered exactly is printed next to A4; structurally identical segments
(e.g. flat sky) can be swapped without changing any attack's result.

What to expect, and why:

* **Fixed key material falls.** Van Droogenbroeck (one stream for the whole video), Kishore (fixed seed) and
  Hirose (fixed K1, K2) reuse the same keystream or permutation in every frame, so one known frame breaks
  every later frame. On the synthetic scene (320x240, 5 scored frames, quality 75) A4 reaches 0.99 for
  Van Droogenbroeck, 0.74 / 0.95 for Hirose RI = 1 / 4 and 0.71 for Kishore, against 0.01 for E5 in both
  forms (quality 50 and 90 give the same picture).
* **Per-frame keys hold.** E1-E5 draw a fresh keystream (and E5 a fresh permutation) from the frame counter,
  so what A4 learns from the known frame is useless on any other frame. E1-E4 still leak through A3 (NZCA) because they do not
  permute; that is a known, stated weakness (GUIDE §5).
* **A4 is not a full attack on a per-frame scheme.** For E5 it recovers the known frame's own permutation (91 % of
  positions on the synthetic scene; the rest are identical segments), but this does not help on other frames.

**Which frame is known (fixed 18 Oct 2026 after the first Kaggle run of this method).** The first run used
frame 0. Four sources (Denzel, Jailer, Sintel, Tears of Steel) open on a black frame, which has no structure to
match and no encrypted AC bits, so A4 recovered nothing there and the published schemes' A4 dropped to about 0
on those sources (pooled: Hirose RI = 1 0.50, Kishore 0.42). The attacker now uses the loaded frame with the most
non-zero AC coefficients, the realistic worst case for the defender. E5's result does not depend on the choice.

## 3. Metrics that papers report (computed on the no-key picture)

| Metric | How | Ideal for a full-image cipher | Comment for a format-compliant scheme |
|---|---|---|---|
| PSNR, SSIM | luma of the no-key picture vs the original frame | low (PSNR around 8-10 dB, SSIM near 0) | comparable with Hirose et al.'s PSNR/SSIM tables |
| Entropy | Shannon entropy of the luma histogram | 8 bits | a decodable JPEG is smooth inside each 8x8 block, so values stay below 8 |
| Adjacent correlation | correlation of every pixel with its right, lower, lower-right neighbour | 0 | stays high **by design**: the decoder smooths each block; report, don't claim |
| NPCR / UACI (key) | no-key pictures of one frame under two keys one bit apart | 99.6 % / 33.5 % | E5 reaches 99.4 % NPCR on the synthetic scene |
| NPCR / UACI (1 pixel) | no-key pictures of two frames one pixel apart, same key and counter | 99.6 % / 33.5 % | no diffusion step. In contract v2 a size change shifts every later keystream bit, so the rest of the frame changes; in contract v3 (E5 hardware form) each segment has its own keystream, so only that segment changes (0.3 % NPCR on the synthetic scene, 53 % in v2). This is by design (the nonce never repeats, so two real frames never share a keystream), and must be explained, not hidden |

`experiments/standard_metrics.py` reports the same family per level, now including **E5 (v3, hw)**, plus the
wrong-key decryption (SSIM to the original, share of pixels that differ). GUIDE §5 already says standard
metrics are "for comparability only": they assume full-image ciphers.

## 4. Hardware figures of merit (`experiments/hw_efficiency.py`)

Joins measured throughput (`experiments/lanes_rtl_throughput.py --modes 2 5`, R1 for the contract-v2
encoder) with the post-route Vivado results and the published rows of `paper/data/related/compare.json`:

* **Mpixel/s per kLUT**: the efficiency number hardware papers compare. Kishore et al. report 11.1 Mpixel/s
  on 2250 Stratix IV ALUTs; ALUTs and 7-series LUTs are not the same unit, so the table says so.
* **nJ per pixel** = total on-chip power / throughput. Power is the SAIF-annotated report for that mode
  when `run_vivado_day.py --steps power` has been run (GUIDE B37), else Vivado's vectorless estimate,
  labelled as such. Board measurement (GUIDE A4) replaces both.
* **Input Gbit/s** = Mpixel/s x 24 bit, the data the design consumes, for comparison with cipher cores.

Limits: throughput is RTL simulation without DMA stalls. Vivado run 6 (17 Oct) predates the E5 RTL, so E5
rows pair E5's throughput with the pre-E5 area (Yosys: about +50 LUT and +1 DSP for 2 lanes) until the lane
bitstream is rebuilt.

## 5. How to reproduce

```
source .venv/bin/activate
python experiments/benchmark_suite.py                                        # synthetic, quick
python experiments/benchmark_suite.py --video data/kodak --frames 24 --stride 1 --size 768x512 \
       --quality 50 75 90 --name kodak                                       # Kodak, native size, sweep
python experiments/standard_metrics.py --video data/kodak --frames 24 --stride 1 --size 768x512 --name kodak
python experiments/lanes_rtl_throughput.py --sizes 320x240 640x480 --modes 2 5
python experiments/hw_efficiency.py
```

The full set of sources runs on Kaggle with `JOB = "benchmark"` in `future_work/kaggle/kaggle_runs.py`
(it now also runs `standard_metrics.py` on every source and packs both into `benchmark_results.zip`).
`paper/make_assets.py` reads either the old (`cross_frame`) or the new (`known_plaintext`) format; with new
data it also writes `tab_bench_metrics.tex`.
