# Keyed, format-preserving permutation of DVS pixel addresses at one event per clock

These are working notes for paper 2 (event-camera encryption, level V2/V3). They are not a result.
Every number below comes from `experiments/neuro/fpe_design_numbers.py`, which writes
`sim_out/neuro_fpe/fpe_design_numbers.{json,md}`. Rerun it, don't retype the numbers. The script does pure
arithmetic in under a second. BRAM counts are rough estimates from 7-series RAMB18 aspect ratios, not synthesis
results.

Source status (checked 2026-11-06): **[full]** means I read the full text, **[abs]** only the abstract or landing
page, **[meta]** only bibliographic metadata (OpenAlex), and any claim taken from such a source is marked
UNVERIFIED. The reference list is in §11.

---

## 0. Recommendation

1. **Drop binary-domain cycle walking. Use a mixed-radix Feistel on Z_W x Z_H** (Black-Rogaway 2002, "Method 3"
   with a = W, b = H, so Delta = ab - k = 0 [full]). In each round one coordinate is updated by modular addition
   of a table lookup on the other: `x <- (x + F_j(y)) mod W`, then `y <- (y + F_{j+1}(x)) mod H`. That is exactly
   BR's `fe[r,a,b]` with an even r, written without the swap. It is a permutation of exactly W x H, so it never
   walks, has a fixed latency, takes one event per clock and needs no stall path. The receiver inverts it with
   modular subtraction and the same tables. It works for every sensor here (34x34, 128x128, 346x260, 640x480,
   1280x720). When W and H are powers of two it is a plain binary Feistel.
2. **Use r = 8 rounds** of random per-packet lookup tables (FF1 uses 10 [full, SP 800-38G r1 2pd §Fig.1 note]).
   4 rounds is not enough, because a known-plaintext attack recovers every table from 9-28 % of one packet's
   codebook (§4). 6 rounds would hold against every published generic attack, but 8 leaves a margin for an
   area cost of 2 more BRAM tables.
3. **Fill the tables from Ascon** at the start of each packet, with double buffering. Draw 16-bit words and
   reduce them by multiply-shift, `(r*W) >> 16`. The worst bias is a total variation of 3.1e-3, for W = 1280.
   For 1280x720 with 8 rounds the fill takes **9 012 clk = 90 us = 9.0 % of a 1 ms packet** and about
   **24 RAMB18** double-buffered (xc7z020 has 280). Use a **separate nonce purpose (domain separation)** for the
   table stream, distinct from the tag and polarity keystreams.
4. **Small sensors (34x34, 128x128) can use a truly random per-packet permutation instead** (a Knuth shuffle into
   a table, the spirit of BR "Method 1"). It costs 4 and 28 RAMB18 and fills in 2.2 % and 34.6 % of a 1 ms packet.
   It is impossible for 346x260 and larger: 176 to 2 250 RAMB18 and 2-23 packet times. Treat it as an optional
   ablation, not the main design.
5. **Timestamp XOR (V3) is decoder-safe only inside the 6-bit EVT 2.0 low field.** It buys almost no privacy
   (§9). Either keep V3 as "polarity + <=6 low ts bits", sold as weak, or drop the timestamp part.
6. **Claims to make in the paper.** Under the PRF assumption on the Ascon keystream, each packet's permutation is
   an independent draw from the 8-round table-Feistel distribution, with nothing linking it to any other packet.
   Within a packet, provable bounds are vacuous at this domain size, as they are for FF1. Security there rests
   on the cryptanalysis in §4, as NIST's own FF1 argument does. V2 is a *confidentiality-of-layout* measure, not
   IND-CPA: within a packet it leaks event count, per-pixel multiplicity and timing (§10).

---

## 1. What the literature says about Feistel round counts vs queries

- **Luby-Rackoff 1988** [meta, UNVERIFIED content]: 3 rounds of random functions give a PRP and 4 rounds a
  strong PRP, up to about 2^{n/2} queries on a 2n-bit block. I could not open the SIAM paper. The 3-round
  generalised analysis that BR 2002 adapt from it ("an adaptation of Luby's analysis") I did read [full].
- **Patarin** [abs/meta]. ePrint 2010/293 [abs] claims security for 4, 5 and 6 rounds of random balanced Feistel
  "very near the information bound (in O(2^n/n))". CRYPTO 2003 and CRYPTO 2004 [meta; the round counts come
  from a search summary, UNVERIFIED]: 2^{n(1-eps)} security with 4 rounds against KPA, 7 against CPA and 10
  against CPCA (2003), improved to 5 and 6 rounds (2004).
- **Black-Rogaway 2002, Theorem 2** [full], the 3-round generalised Feistel on Z_a x Z_b:
  Adv <= (q+Delta)^2 / 2^{n+1} * (ceil(2^n/a) + ceil(2^n/b)). For Delta = 0 the advantage reaches 1/2 at
  **q = 4.0 (34x34), 8.0 (128x128), 11.3 (346x260), 14.3 (640x480), 20.2 (1280x720)** queries.
- **What follows for us:** with n = 10-11 bits per half, even the best "beyond-birthday" bounds (q << 2^n, about
  10^3) are below the number of distinct pixels a busy 1 ms packet can touch. As for FF1, **no provable bound
  covers our operating point.** The argument has to rest on the best known attacks (§4) plus per-packet
  freshness (§5). NIST argues the same way for FF1 (§2).

## 2. NIST SP 800-38G and its revision status

- SP 800-38G (2016) [abs: CSRC page]: the March 2016 version was withdrawn and superseded by the 4 Aug 2016
  update. It specified FF1 and FF3.
- **SP 800-38G Rev. 1, second public draft (2pd), February 2025** [full PDF], authors Dworkin and Mouha. Comments
  closed 4 Apr 2025. **FF3 and FF3-1 are removed**, citing Beyne (CRYPTO 2021, linear cryptanalysis via the tweak
  schedule), and FF1 is the only mode left. **radix^minlen >= 1 000 000 is now a requirement** (in 2016 it was
  a recommendation with an absolute minimum of 100). Floating point is banned in FF1, and the inverse AES
  cipher is not allowed as CIPH. Appendix A.2 quotes Hoang's public comment: at the 10^6 domain, recovering one
  target message costs "at least 2^77" data for FF1.
- A final Rev. 1 was **not found**: csrc.nist.gov/pubs/sp/800/38/g/r1/final returns 404 and the 38G page lists no
  Rev. 1 final. Denis (ePrint 2025/1888) [abs] also calls FF3-1 "withdrawn in 2025" and FF1 "the current NIST
  standard".
- **What follows for us:** (a) 1280x720 = 921 600 < 10^6, so FF1 would **not be an approved parameter set** for
  this domain even with AES. Smaller sensors are further below the line. (b) FF1 with Ascon as CIPH is not FF1,
  because CIPH must be an approved block cipher, and it has no conformance claim. (c) NIST itself rests
  small-domain FPE security on attack data complexity, not on proofs. That is the precedent for our §4 argument.

## 3. Small-domain attacks on Feistel FPE (all are multi-tweak, fixed-key settings)

| paper | status | what it does | numbers stated |
|---|---|---|---|
| Bellare-Hoang-Tessaro, CCS 2016 (ePrint 2016/794) | [abs] | message recovery on FF1/FF3, 4-bit messages, 3 messages per tweak | about 2^21 examples (FF3), about 2^25 (FF1); more rounds put the attacks out of reach |
| Durak-Vaudenay, CRYPTO 2017 (ePrint 2017/521) | [abs] | slide attack on FF3 over 2 tweaks; **known-plaintext table recovery of 4-round Feistel** | FF3: O(N^{11/6}) CP, O(N^5) time; 4-round KPA: N^{3/2}(N/2)^{1/6} pairs, O(N^3) time; >= 5 rounds N^{(r-5)N+o(N)} |
| Durak-Vaudenay, ACNS 2018 (ePrint 2018/108) | [abs] | generic round-function recovery, **modular-addition** Feistel (our structure) | prior MITM: data rN/2, time N^{((r-4)/2)N+o(N)}; new: time N^{O(N^{1-1/(r-2)})} at q = N^2 |
| Hoang-Tessaro-Trieu, CRYPTO 2018 (ePrint 2018/556) | [abs] | "The Curse of Small Domains": multi-target KPA message recovery; FF3 odd-length flaw; FNR, DTP | feasible on 8-bit domains at suggested round counts |
| Hoang-Miller-Trieu, EUROCRYPT 2019 (ePrint 2019/244) | [abs] | FF3 on **large** domains; 4-round KPA time O(N^3) -> O(N^{5/3}); Z_M x Z_N | 6-digit PINs about 2^30 ops; SSNs about 2^50 |
| Beyne, CRYPTO 2021 (ePrint 2021/815) | cited in SP 800-38Gr1 2pd [full]; search summary | linear cryptanalysis via alternating round tweaks (FF3-1, FEA) | data O(N^{r/2-1.5}) (from search summary, UNVERIFIED) |

Note: the task named "Hoang-Miller-Trieu on small domains". The small-domain paper is **Hoang-Tessaro-Trieu 2018**.
Hoang-Miller-Trieu 2019 is the *large*-domain FF3 paper. I cite both.

**How these apply to us.** Every attack above needs one fixed permutation family queried across many tweaks, or
a large fraction of one codebook. In our design each packet's round tables are fresh, so there is one
"tweak" per key. The only attack surface left is **one packet's known pairs** (§4).

## 4. Known-plaintext within one packet

The adversary can know some (input pixel -> output pixel) pairs only by knowing the scene. Examples are a
controlled flashing pattern or the sensor's hot pixels. DV17's 4-round KPA on branch size N needs
N^{3/2}(N/2)^{1/6} pairs (script, mixed-radix branch about sqrt(k)):

| sensor | k = W*H | pairs for 4-round table recovery | share of codebook |
|---|---|---|---|
| 34x34 | 1 156 | 318 | 27.5 % |
| 128x128 | 16 384 | 2.9e3 | 17.7 % |
| 346x260 | 89 960 | 1.2e4 | 13.3 % |
| 640x480 | 307 200 | 3.33e4 | 10.8 % |
| 1280x720 | 921 600 | 8.32e4 | 9.0 % |

An attacker who knows a tenth to a quarter of a 4-round packet recovers its whole permutation, and with it the
rest of that packet's layout. **So 4 rounds is ruled out.** For r = 6, DV18's generic attacks cost
N^{O(N^{3/4})} and N^{N} (MITM), and for r = 8, N^{O(N^{5/6})} and N^{2N}, where N is about 10^3. The O-constants
are not stated in the abstract, so I give only the exponent form, but either form is far beyond reach. Even so,
the most an attacker can win is **one 1 ms packet**, never the key and never another packet.

What a perfect per-packet permutation would leak, and so the floor for any V2 design: with m known pairs, the
other k - m pixels are uniformly permuted among the k - m outputs that are left.

## 5. Across packets

- Tables come from the Ascon-AEAD128 keystream under a nonce that holds the packet counter (paper-1 layout:
  session id || counter || purpose). Under the standard assumption that this keystream is a PRF of
  (key, nonce, offset), **the tables of different packets are independent**, so recovering one packet's
  permutation tells nothing about any other. The draft calls this "permutation recovery across packets
  impossible". That holds **only** if nonces never repeat, which needs the epoch/session id on restart.
- Domain separation: paper 1 has one purpose bit. Paper 2 needs at least tag/AEAD, polarity keystream and table
  fill, so either widen the purpose field or derive one stream per packet and slice it at fixed offsets. Write
  the choice into docs/INTERFACES.md before the RTL.
- SP 800-232 (final, 13 Aug 2025) [abs: CSRC page] also specifies Ascon-XOF128 and Ascon-CXOF128. A CXOF with a
  "neuro-perm" customisation string is a clean alternative KDF for the table stream, at the cost of a second
  Ascon mode in hardware. The AEAD keystream reuses the existing core.

## 6. Cycle walking: why a binary domain is a bad fit here

The cycle walk is BR 2002 "Method 2" [full]. Theorem 1 shows the walk loses nothing: if E is an ideal cipher on
T ⊇ M, then Cy is a uniform permutation on M. BR also note that the worst case can take up to k calls and that
the expected count is "two calls (or fewer)" when N <= 2k. For an ideal permutation the script gives the exact
law P(T>j) = prod_{i<j} (N-k-i)/(N-1-i), where E[T] = (N+1)/(k+1) (checked numerically):

| sensor | binary domain | N/k | E[calls] | P(>2) | P(>4) | P(>8) | P(>16) |
|---|---|---|---|---|---|---|---|
| 34x34 | 2^12 | 3.543 | 3.543 | 0.515 | 0.266 | 0.0704 | 0.00493 |
| 128x128 | 2^14 | 1 | 1 | 0 | 0 | 0 | 0 |
| 346x260 | 2^18 (balanced) | 2.914 | 2.914 | 0.431 | 0.186 | 0.0346 | 0.0012 |
| 640x480 | 2^19 (x,y fields 10+9) | 1.707 | 1.707 | 0.171 | 0.0294 | 8.6e-4 | 7.5e-7 |
| 640x480 | 2^20 (balanced) | 3.413 | 3.413 | 0.5 | 0.25 | 0.0624 | 0.0039 |
| 1280x720 | 2^20 (packed y*W+x) | 1.138 | 1.138 | 0.0147 | 2.15e-4 | 4.6e-8 | 2.1e-15 |
| 1280x720 | 2^21 (x,y fields 11+10) | 2.276 | 2.276 | 0.314 | 0.0987 | 0.00975 | 9.5e-5 |
| 1280x720 | 2^22 (fields, balanced) | 4.551 | 4.551 | 0.609 | 0.371 | 0.137 | 0.0189 |

The candidate design is a K-deep unrolled walk, "first in-domain" select, plus a recirculate path. It costs
**K x r table lookups per event**, i.e. ceil(K/2) copies of every round table even with dual-port sharing, and
it still stalls with probability P(>K). The only good case is **1280x720 packed into 2^20** (K = 4: stall rate
2.15e-4 per event). That needs a y*W+x multiply on the way in and a divide by W on the way out. For 34x34,
346x260 and 640x480 a balanced binary domain is about 3x too large, and stalls would be routine (P(>4) of
0.19-0.27). Stalls also make the output timing depend on the key and the data. That is a timing side channel
the mixed-radix design simply does not have. **The mixed-radix Feistel removes the whole problem with N/k = 1.**
Its only extra hardware is a compare-and-subtract per round (a + b < 2W).

## 7. Cost table (8 rounds, 16-bit multiply-shift draws, double-buffered; script)

| sensor | keystream bits/packet | fill clk (100 MHz) | fill time | share of 1 ms | RAMB18 x2 |
|---|---|---|---|---|---|
| 34x34 | 4 352 | 318 | 3.2 us | 0.32 % | 16 |
| 128x128 | 16 384 | 1 164 | 11.6 us | 1.16 % | 16 |
| 346x260 | 38 784 | 2 739 | 27.4 us | 2.74 % | 16 |
| 640x480 | 71 680 | 5 052 | 50.5 us | 5.05 % | 16 |
| 1280x720 | 128 000 | 9 012 | 90.1 us | 9.01 % | 24 |

The Ascon rate is 128 bits per 9 clk plus 12 clk of p12 init, matching `hardware/rtl/ascon_aead128_core.v`
(1 round/clk, p8 per block). At 4 rounds, 1280x720 is 4.51 %; at 10 rounds it is 11.26 %. The binary packed
2^20 variant with 10-bit entries costs about the same keystream (81 920 bits, 5.77 % at r = 8). It would also
need the walk pipeline from §6. The multiply-shift bias (total variation from uniform on Z_W) is 1.3e-4 to
3.1e-3 per entry, and 0 when W is a power of two. Exact-width draws (`exact-width` rows in the script) have a
large mod bias on mixed radix and are listed only as a lower bound on keystream.

**The fill must finish before the packet it serves starts.** With double buffering and a counter-based nonce
known one packet ahead, that is a requirement of 9 % of a packet time, met with large margin. If packets
become shorter than about 0.1 ms at 1280x720, the fill rate becomes the limit.

## 8. Alternatives compared

| option | domain exact? | 1 ev/clk? | per-packet cost | security basis | verdict |
|---|---|---|---|---|---|
| **Mixed-radix table Feistel, r = 8** | yes | yes, latency about 2r clk | §7 | PRF(Ascon) + Feistel cryptanalysis (DV17/18, HMT19) | **recommended** |
| Binary table Feistel + unrolled cycle walk | after walking | only with K-fold tables + stall path | §6/§7, xK tables | same + BR Thm 1 | only sensible for 1280x720 packed |
| Full random permutation table (Knuth shuffle) | yes | yes | 34x34: 4 RAMB18, 2.2 %; 128x128: 28 RAMB18, 34.6 %; >= 346x260 infeasible | ideal permutation under PRF | optional for small sensors |
| Ascon-PRF round function evaluated per event | yes (mixed radix) | needs r full Ascon permutations per event, i.e. 8 x 12 = 96 unrolled Ascon rounds per lane (count only, area not estimated) | none | PRF | too big for xc7z020; tables are the same PRF evaluated over its whole input set once per packet |
| FF1 with Ascon | yes | no: 10 PRF calls per event, each a CBC-MAC | none | not FF1 (CIPH must be an approved block cipher); 921 600 < 10^6 also fails Rev. 1 | reject |
| Swap-or-not (Hoang-Morris-Rogaway 2012) [full via ar5iv] | yes, any N | no | needs R = 164-516 rounds for adv <= 2^-30 at q = N/100..N/2 (script, eq. 1); 1-bit round function over the whole domain means k bits of table per round | best provable bound | reject for hardware; cite as the "provable" alternative |
| CTR-MOD (Perez-Resa et al., IEEE Access 2020) [meta + search summary, UNVERIFIED content] | per symbol | yes (FPGA, GbE) | — | stream-like modular addition, **not a permutation of positions** | does not apply to addresses |

Hardware FPE prior art is thin. **Agbeyibor et al. 2014** (IFIP AICT 441, FF1/FF2/FF3 on Virtex-6) is
UNVERIFIED: the HAL and AFIT pages refused access, and only a search snippet was seen. Perez-Resa 2020's
metadata is verified (DOI 10.1109/ACCESS.2020.2968816) but I could not open the abstract. I found no FPGA design
for a pixel-address permutation at one event per clock. That is a gap our paper can claim, after a proper search
of IEEE Xplore and ACM DL.

## 9. Timestamp-bit XOR (V3) and decoders

- EVT 2.0 [full, Prophesee docs]: a CD word has type[31:28], ts[27:22] (6 LSBs of the time base), x[21:11] and
  y[10:0]. EVT_TIME_HIGH carries ts bits 6..33. The decoder concatenates the low bits with the **last**
  TIME_HIGH. The page states **no monotonicity requirement**.
- XORing b <= 6 low bits leaves every event inside its original 64 us TIME_HIGH bucket. The coarse order is kept,
  but **order inside the bucket becomes non-monotonic**, with errors up to 2^b - 1 us. With b > 6 the timestamp
  leaves the bucket and the stream is no longer well formed with respect to TIME_HIGH. **Do not do that.**
- Whether real decoders tolerate in-bucket non-monotonic timestamps (OpenEB/Metavision, dv-processing, Tonic,
  E2VID loaders) is **UNVERIFIED**. Add a small test to N1/N10 that feeds V3 streams through each loader and
  checks for errors, drops or reordering. Re-sorting after XOR breaks per-event decryption unless the keystream
  index travels with the event, so the receiver must decrypt in arrival order.
- Privacy value: any processing that bins time more coarsely than 2^b us (event frames, voxel grids,
  reconstruction windows) is unchanged by construction. A <= 64 us jitter hides almost nothing from E2VID-style
  attacks. Its only effect is on fine-timing features. **Recommendation:** keep V3 only as an ablation that
  shows this ("timing masking within the format is too small to matter"). Put the effort into V2 plus dummy
  events against rate and motion leaks.

## 10. Limits to state honestly in the paper

- Per packet the permutation is deterministic. Events from the same pixel map to the same output pixel, so the
  per-pixel multiplicity histogram, each pixel's event-time sequence, the event count and (without V1) the
  polarity ratio survive. N5 and N8 must measure what a classifier gets from exactly these statistics (DVS
  Gesture rhythm, N-MNIST saccade timing), not only from E2VID frames.
- Provable bounds do not cover q near the codebook (§1). The claim is "no known attack below N^{O(N^{5/6})} time
  per packet at r = 8, and at most one packet lost". It is not IND-CPA.
- Hot pixels fire in every packet. Their output position changes per packet, so they cannot link positions, but
  their rate stays visible.
- With packets too short (fill > packet time) or nonces reused after a reset, §5 fails.

## 11. References (as opened)

1. M. Luby, C. Rackoff, "How to Construct Pseudorandom Permutations from Pseudorandom Functions", SIAM J. Comput.
   17(2), 1988, doi:10.1137/0217022. [meta, verified via OpenAlex; content UNVERIFIED]
2. J. Patarin, "Luby-Rackoff: 7 Rounds Are Enough for 2^{n(1-eps)} Security", CRYPTO 2003,
   doi:10.1007/978-3-540-45146-4_30. [meta + search summary; UNVERIFIED]
3. J. Patarin, "Security of Random Feistel Schemes with 5 or More Rounds", CRYPTO 2004,
   doi:10.1007/978-3-540-28628-8_7. [meta, verified via OpenAlex; content UNVERIFIED]
4. J. Patarin, "Security of balanced and unbalanced Feistel Schemes with Linear Non Equalities", ePrint 2010/293. [abs]
5. J. Black, P. Rogaway, "Ciphers with Arbitrary Finite Domains", CT-RSA 2002, doi:10.1007/3-540-45760-7_9. [full, PDF from rogaway's site]
6. M. Dworkin, N. Mouha, NIST SP 800-38G Rev. 1 2pd, Feb 2025 (csrc.nist.gov/pubs/sp/800/38/g/r1/2pd). [full]
7. NIST SP 800-38G (2016), csrc.nist.gov/pubs/sp/800/38/g/upd1/final. [abs: status page]
8. M. Bellare, V. T. Hoang, S. Tessaro, "Message-recovery attacks on Feistel-based Format Preserving Encryption",
   CCS 2016, doi:10.1145/2976749.2978390, ePrint 2016/794. [abs]
9. F. B. Durak, S. Vaudenay, "Breaking the FF3 Format-Preserving Encryption Standard Over Small Domains",
   CRYPTO 2017, ePrint 2017/521. [abs]
10. F. B. Durak, S. Vaudenay, "Generic Round-Function-Recovery Attacks for Feistel Networks over Small Domains",
    ACNS 2018, ePrint 2018/108. [abs]
11. V. T. Hoang, S. Tessaro, N. Trieu, "The Curse of Small Domains: New Attacks on Format-Preserving Encryption",
    CRYPTO 2018, ePrint 2018/556. [abs]
12. V. T. Hoang, D. Miller, N. Trieu, "Attacks Only Get Better: How to Break FF3 on Large Domains", EUROCRYPT 2019,
    ePrint 2019/244. [abs]
13. T. Beyne, "Linear Cryptanalysis of FF3-1 and FEA", CRYPTO 2021, ePrint 2021/815. [cited by ref. 6, read there;
    the paper itself not opened, numbers UNVERIFIED]
14. V. T. Hoang, B. Morris, P. Rogaway, "An Enciphering Scheme Based on a Card Shuffle", CRYPTO 2012,
    doi:10.1007/978-3-642-32009-5_1, arXiv:1208.1176. [full via ar5iv; eq. 1 bound used in the script]
15. F. Denis, "HCTR2-FP and HCTR3-FP: Format-Preserving Encryption from Wide-Block Ciphers", ePrint 2025/1888. [abs]
16. NIST SP 800-232, "Ascon-Based Lightweight Cryptography Standards for Constrained Devices", Aug 2025. [abs: CSRC page]
17. A. Perez-Resa, M. Garcia-Bosque, C. Sanchez-Azqueta, S. Celma, "A New Method for Format Preserving
    Encryption in High-Data Rate Communications", IEEE Access 2020, doi:10.1109/ACCESS.2020.2968816. [meta; content UNVERIFIED]
18. Agbeyibor et al., "Evaluation of Format-Preserving Encryption Algorithms for Critical Infrastructure
    Protection", IFIP AICT 441, 2014. [UNVERIFIED: pages refused access]
19. Prophesee, "EVT 2.0 format", docs.prophesee.ai/stable/data/encoding_formats/evt2.html. [full]
