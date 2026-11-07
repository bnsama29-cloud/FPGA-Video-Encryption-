# Baselines for paper 2: Du 2021 and Zhang 2024 (read from the PDFs, 7 Nov 2026)

This file is the contract for `software/neuro/baselines/du2021.py` and `zhang2024.py` (DESIGN §8.3). Everything
below was read from the two PDFs supplied by the authors of this repository (not committed: copyrighted). Page and
section numbers refer to the published versions. Where a paper leaves a detail open or is internally inconsistent,
the choice we made is marked **[choice]** with the reason; the paper's text is summarised, not quoted at length.

The attacker knows the scheme and not the key (Kerckhoffs), as for our levels.

---

## 1. Du et al. 2021 [`du2021sensors`]

Du, Li, Yang, Wang, Zhang et al., "Event Encryption for Neuromorphic Vision Sensors: Framework, Algorithm, and
Evaluation", *Sensors* 21(13):4320, 2021, doi 10.3390/s21134320. The construction is in **§4 (pp. 6-10)**, not §3
as DESIGN §8.3 first said (§3 is the threat model); DESIGN is corrected.

### 1.1 Pseudo-random sequences (§4.1, eqs. 4-7)

- 2D Sine ICMIC modulation map (2D-SIMM), eq. 6:
  `x_{i+1} = a sin(π y_i) sin(b / x_i)`, `y_{i+1} = a sin(π x_{i+1}) sin(b / y_i)`, with **a = 1, b = 5**
  ("hyperchaotic in this setting", p. 7).
- Key (p. 7 and §5.3, p. 14): x0 (52 bits), y0 (52 bits), H (52 bits) and one G (25 bits) per sequence; six
  sequences, so 3·52 + 6·25 = **306 bits**, matching the 2^306 key space of §5.3.
- Initial state for sequence k, eq. 7: `x0^G = (x0 + G H) mod 1`, `y0^G = (y0 + G H) mod 1`.
- Six sequences r1..r6, "lengths N, M, N, M, 2N and 2M" (p. 7), with M x N the width x height ("Given that the
  width and height of the NVS resolution are M and N").

**[choice] Indexing.** Algorithm 1 (p. 9) indexes r1 by x (x < M) and reduces mod N, r2 by y and reduces mod M,
r3 by x', r4 by y', r5 by p·N + y (length 2N), r6 by p·M + x (length 2M). So r1 and r3 must have length M
(width) and r2, r4 length N (height); the stated "N, M, N, M" contradicts the algorithm for M ≠ N. We follow
Algorithm 1 (lengths M, N, M, N, 2N, 2M). Eq. 8 (p. 7, "mod M" on y) is the same inconsistency; Algorithm 1 and
Algorithm 2 (p. 9) agree with each other and are used.

**[choice] Real to integer.** The paper does not say how a chaotic value becomes an integer shift (it refers to
[35], the image-encryption paper it extends). We use `r = floor(|v| · 10^14) mod modulus`, the common rule in
2D-SIMM image ciphers; r5 and r6 are used as real values (they are only sorted).

**[choice] Which component.** Each iterate gives (x_i, y_i); we use x_i for the sequence value, iterates i = 1, 2, ...

### 1.2 Encryption and decryption (§4.2, Algorithms 1 and 2, pp. 7-9)

For one event (t, x, y, p), W = M, H = N:

```
1  y' = (y  + r1[x ]) mod N          position round 1 (eq. 8)
2  x' = (x  + r2[y']) mod M          (eq. 9)
3  y' = (y' + r3[x']) mod N          position round 2
4  x' = (x' + r4[y']) mod M
5-8   S5 = rank of each element of r5 in sorted order; v = S5[p·N + y'];  p_t = v div N;  y' = v mod N
9-12  S6 = rank of each element of r6;               u = S6[p_t·M + x'];  p'  = u div M;  x' = u mod M
```

Timestamps are unchanged. Decryption (Algorithm 2) applies the inverse ranks and subtracts in reverse order.
Lines 1-4 of Algorithm 1 print `y` and `x` on the right-hand side of lines 3 and 4; Algorithm 2 (lines 9-12) only
inverts them if they are the values after the previous line, so **[choice]** we read them as y' and x'.

### 1.3 Updating (§4.3, eq. 12, p. 10)

- Updating score `= log10( L / (N × M) × K )`, L = events processed since the last update, N × M the resolution,
  K the platform's processing speed (Table 3: K = 36 694 061 on the Raspberry Pi 4B; Table 4: 253 725 220 desktop;
  Table 5: 152 031 121 cloud). The sequences are updated "when a new event occurs" and the score exceeds a
  threshold (Fig. 4). Tables 3-5 use scores 7.2 to 8.8.
- **[choice] Default** threshold 8.4 with the Raspberry-Pi K (the setting the paper quotes as 0.20 µs/event on the
  Pi, p. 15); then an update happens every ceil(10^8.4 · N · M / K) events (about 112 000 events at 128 x 128).
- **[choice] New sequences** continue the chaotic iteration of each sequence (the paper does not say how new
  sequences are formed); update u uses iterates u·len+1 .. (u+1)·len of each sequence.

### 1.4 Numbers to use as anchors

- Efficiency, Tables 3-5 (pp. 15-16): 0.20 µs/event on a Raspberry Pi 4B at score 8.4, 0.04 µs on the desktop and
  cloud servers. Quoted separately with citation, never mixed into our timing table (DESIGN §8.2 N9).
- Visualization attack (§5.1, Tables 1-2): PSNR below 6.5 dB against the plaintext E2VID reconstruction, on DAVIS
  and DDD17 (not our datasets).
- The Event-ReId anchor (Du at 75 % encryption, SSIM 0.451) is from Ahmad 2023 Table 3, **not** from this paper;
  it is still to be read from the Ahmad PDF before N3 uses it.

### 1.5 Variant used only in N7/N9

`ascon_keyed=True` replaces the chaotic sequences by Ascon keystream values (r = keystream mod modulus, r5/r6 as
uniform 32-bit integers), labelled "Ascon-keyed Du". It isolates the effect of the permutation structure from the
chaotic generator.

---

## 2. Zhang, Zhu, Lam 2024 [`zhang2024nce`]

"Event encryption: rethinking privacy exposure for neuromorphic imaging", *Neuromorph. Comput. Eng.* 4(1):014002,
2024, doi 10.1088/2634-4386/ad207b. Construction in **§3.2 (Algorithm 1, eqs. 4-7, pp. 3-4)**, settings in **§4.1
(p. 4)**.

### 2.1 Construction

- Ex = the set of pixels where events occur. Mask M = pixels where noise may be synthesised; §4.1 sets
  **M = S \ Ex** (S = the whole sensor), so noise fills every pixel without events.
- Algorithm 1, for each position x_i in Ex (Ex grows during the loop, line 9):
  R = θ(x_i, M) = {x ∈ M : f_x(x, x_i) < T_x} (eq. 4); if R is empty, continue; E_c = events at x_i;
  N = φ(R, E_c); add N; Ex = Ex ∪ R; M = M \ R; stop when M is empty.
- φ (eq. 5): for each x ∈ R, |N| = |E_c| noise events (p. 4, "|N| = |Ec|"), each with p random in {−1, +1} and
  `t = t_i (1 + σ f_x(x, x_i))` under |t − t_i| < T_t.
- Settings (§4.1): f_x, f_t, f_p are L1 distances; **T_x = 1; σ = 0.05**; T_t "varies with the attributes of the
  events".
- Polarity mapping λ (eq. 6), applied to all events at the end: `p = p ⊕ (szudzik(x) mod 2)`, szudzik the
  Szudzik pairing of the two coordinates.
- Key (eq. 7): `key = ρ(szudzik(Ex))`, ρ "any well-established encryption method"; the receiver keeps the events
  at pixels in Ex and undoes eq. 6. Lossless.

**[choice] Neighbourhood.** With L1 distance and the strict `< T_x = 1`, R would contain only x_i itself (which is
not in M), so no noise would ever be made. Fig. 2 (p. 4) shows the four horizontally/vertically adjacent pixels,
i.e. L1 distance 1. We use `≤ 1` (4-neighbourhood), as in the figure.

**[choice] Timestamps.** `t_i (1 + σ)` scales absolute time, so a 5 % shift of a timestamp of 10^6 µs is 50 ms. We
apply it to time relative to the first event of the sample, `t = t0 + (t_i − t0)(1 + σ f_x)`, and enforce no T_t
(the paper gives no value). Noise events at depth d of the recursion therefore sit at (t_i − t0)·1.05^d after t0.

**[choice] Randomness and ρ.** The random noise polarities and ρ are not specified; we draw the polarities from
an Ascon keystream under the experiment key and use Ascon-AEAD128 as ρ (labelled as such: Zhang leaves ρ open, so
there is no "own" generator to use).

**[choice] Processing order.** Ex is traversed in order of first occurrence of each pixel in the stream, then in
the order pixels are appended (breadth first), R in the order (x+1, y), (x−1, y), (x, y+1), (x, y−1).

### 2.2 Numbers to use as anchors

Table 1 (p. 6), top-1 recognition accuracy on N-MNIST, columns raw / raw + 50 % random noise / Du [3] / Zhang:

| Method | raw | +50 % noise | Du | Zhang |
|---|---|---|---|---|
| Rebecq et al. [29] | 0.93 | 0.71 | 0.17 | 0.14 |
| Gehrig et al. [13] | 0.97 | 0.74 | 0.11 | 0.09 |
| Li et al. [32] | 0.95 | 0.77 | 0.15 | 0.06 |
| Wang et al. [33] | 0.94 | 0.68 | 0.19 | 0.12 |

Random guess 0.1. Our anchor (DESIGN §8.3): our Zhang reimplementation with a frame CNN trained on Zhang
ciphertext must land within ±3 pp of the 0.06-0.14 range for the frame-based rows (N6, row (ii)). The paper's
§5 states the algorithm is at least quadratic in time with non-deterministic runtime; we report our runtime in N9.

---

## 3. What is not reproduced

- Du's E2VID/EV-Gait numbers on DAVIS, DDD17 and EV-Gait (other datasets than ours).
- Zhang's detection results (Table 2) and denoiser study (Fig. 4); N3 uses Tonic `Denoise` and the NNf of eq. 3
  as denoise-then-reconstruct attacks.
