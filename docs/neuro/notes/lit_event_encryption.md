# Literature: encryption and privacy protection of event-camera (DVS) data

Novelty check for paper 2 (authenticated, format-preserving Ascon encryption of event streams on the FPGA).
Search date: 2026-11-06. Method: web searches (Google-Scholar-style keywords, arXiv, MDPI, PMC, IEEE, Springer, Frontiers, TU Delft repository) plus opening each cited page.

Status tags:
- **VERIFIED**: I opened the page (full text, or abstract page where noted) and the facts below come from it.
- **ABSTRACT ONLY**: only the abstract or landing page was opened. Details beyond the abstract are not claimed.
- **UNVERIFIED**: the page could not be opened, or only search snippets were seen. Do not cite these as fact until someone opens them.

No DOI below is guessed. A DOI is listed only if it appeared on the opened page.

---

## 1. The two anchor papers (verified at source)

### 1.1 Du et al., Sensors 2021 (the "2D-NVS" chaotic scheme). VERIFIED, full text (PMC8272045)
B. Du, W. Li, Z. Wang, M. Xu, T. Gao, J. Li, H. Wen, "Event Encryption for Neuromorphic Vision Sensors: Framework, Algorithm, and Evaluation", *Sensors* 21(13):4320, 2021. DOI 10.3390/s21134320.
- **What is encrypted:** event positions (x, y) are scrambled (two rounds) and polarity p is flipped. **The timestamp t passes through unchanged.** Output is still an event tuple (t, x', y', p').
- **Cipher:** custom. A 2D Sine ICMIC modulation map (2D-SIMM) produces six pseudo-random sequences. The key is the chaotic initial conditions (they claim about 306 bits). An "updating score" sets how often the sequences are regenerated. There is no formal security proof and no known/chosen-plaintext analysis.
- **Standard ciphers:** the paper says DES/IDEA/AES "are inefficient for vision sensors, since visual data is redundant and the scale is large." Its only AES use is a baseline that encrypts *part* of the events ("partial discarding"). They reject it because encrypted and unencrypted events can be told apart.
- **Authentication/integrity:** none. The threat model covers confidentiality only.
- **Hardware:** software only (Raspberry Pi 4B, i9-9900K desktop, Xeon cloud). The paper reports about 0.20 us/event on the Pi and about 0.04 us/event on the desktop at updating score 8.4. These are the paper's own CPU numbers, not FPGA numbers.
- **Attacks evaluated:** E2VID grayscale reconstruction (PSNR, SSIM, NPCR, UACI) on DAVIS and DDD17. Recognition on EV-Gait with a CNN and a GCN (about 86% clean vs. 5% encrypted for the CNN). Key sensitivity is shown qualitatively only.

### 1.2 Zhang, Zhu, Lam, Neuromorphic Computing and Engineering 2024. VERIFIED (arXiv abstract plus HTML full text, arXiv 2306.03369)
P. Zhang, S. Zhu, E. Y. Lam, "Event Encryption: Rethinking Privacy Exposure for Neuromorphic Imaging", *Neuromorph. Comput. Eng.* 4(1):014002, 2024. DOI 10.1088/2634-4386/ad207b. This is the **target journal of paper 2**, so the paper is the most important one to position against.
- **Method:** the inverse of denoising. The method synthesises noise events in empty neighbouring pixels (recursively, until the mask is filled), with timestamps tied to nearby real events. It then remaps polarity with a reversible XOR keyed on a Szudzik pairing of the coordinates.
- **Cipher:** the key is rho(szudzik(E_x)), where rho is "any well-established encryption method", and no cipher is named. The noise-generation core is not a standard cipher.
- **Authentication/integrity:** none.
- **Hardware:** none. The authors say runtime and energy were not fully studied. They also note that the algorithm has at least quadratic, non-deterministic runtime, which is the opposite of a fixed-latency hardware pipeline.
- **Format:** the output is still an event stream, but it is longer because noise events are added. That is bandwidth expansion.
- **Attacks evaluated:** reconstruction with CF (Scheerlinck) and event-frame visualisation; E2VID/FireNet are not used. Recognition on N-MNIST and ASL-DVS; detection on 1MP and GEN1 (YOLOv3E, RVT). Denoising attacks: four denoisers. There is no key-space analysis and no formal security argument.

---

## 2. Every other hit, by category

Legend for the table: (a) uses a standard cipher, (b) authenticates (integrity/tag), (c) hardware implementation, (d) output keeps a readable event format, (e) evaluates reconstruction attacks.

| # | Work | Status | (a) std cipher | (b) auth | (c) HW | (d) format kept | (e) recon attack | Note |
|---|---|---|---|---|---|---|---|---|
| 1 | Du et al., Sensors 2021 (2D-NVS) | VERIFIED | No (chaotic 2D-SIMM; AES only as a partial baseline) | No | No (CPU/RPi) | Yes (t, x', y', p') | Yes (E2VID) | closest keyed, format-preserving scheme |
| 2 | Zhang, Zhu, Lam, NCE 2024 | VERIFIED | No (unnamed rho for the key) | No | No | Yes, but adds events | Yes (CF; recognition, detection, denoisers) | same journal as our target |
| 3 | Bao, Shi, Zhai, Wang, "Asynchronous temporal mapping for high-dynamic-range video and hardware-level privacy with event cameras" (SECAM), *Communications Engineering* 5:136, 2026, DOI 10.1038/s44172-026-00687-4 (PMC13396165) | VERIFIED | No (per-pixel temporal offset map from DMD modulation acts as the key) | No | **Yes, optical**: DMD plus event camera prototype; no FPGA or encryption logic | Raw IPE stream is noise-like without the key; readability by standard tools not discussed | Yes (E2VID, NER-Net+ baselines; KPA via OCR; ciphertext-only) | **the only "hardware-level" event encryption found**; optical-modulation, not cryptographic; benchmarks against Du 2021 |
| 4 | Ahmad, Morerio, Del Bue, "Person Re-Identification without Identification via Event Anonymization", ICCV 2023 (arXiv 2308.04402) | ABSTRACT ONLY | No (learned scrambling network) | No | No | Yes (event stream) | Yes (image reconstruction attack) | anonymisation, not reversible by key |
| 5 | Ahmad, Morerio, Del Bue, "Event Anonymization: Privacy-Preserving Person Re-Identification and Pose Estimation in Event-Based Vision", IEEE Access 12:66964-66980, 2024 | UNVERIFIED (DOAJ page returned 403; facts from search snippets) | No | No | No | n/a | reportedly yes | journal extension of #4 |
| 6 | Bendig, Schuster, Thiemer, Joisten, Stricker, "AnonyNoise", WACV 2025 (arXiv 2411.16440) | ABSTRACT ONLY | No (learned noise) | No | No | Yes | Yes (reconstruction and inversion) | non-reversible anonymisation |
| 7 | Mueller, Kocsis, Stache, "Generative Anonymization in Event Streams", CVPR 2026 LoViF workshop (arXiv 2604.12803) | ABSTRACT ONLY | No (generative re-identity) | No | No | Yes (re-encoded events) | Yes (E2V reconstructions) | anonymisation |
| 8 | Kim et al., "Privacy-Preserving Visual Localization with Event Cameras", IEEE TIP 34:6215-6230, 2025 (arXiv 2212.03177) | ABSTRACT ONLY | No | No | No | n/a | not stated in abstract | sensor-level filtering plus split inference |
| 9 | Boetius, "Encryption of Event Camera Data for Visual Localisation", TU Delft bachelor thesis, 2026 | UNVERIFIED (repository refused connection; search snippets only) | No (implements Zhang 2024) | No | No | Yes | reportedly privacy metrics | snippets say polarity mapping does most of the obfuscation, noise timestamps carry no randomness, and privacy degrades with event density. **Useful independent critique of Zhang 2024 if it can be opened.** |
| 10 | Njungle, Jahns, Stojkov, Kinsy, "PrivSpike", arXiv 2510.03995, 2025 | ABSTRACT ONLY | Yes (CKKS homomorphic) | No | No (CPU) | No (ciphertexts) | No | SNN inference on encrypted N-MNIST and CIFAR10-DVS; 212 s (N-MNIST, LeNet-5) and 1846 s (CIFAR10-DVS, ResNet-19) per the abstract; different problem (private inference) |
| 11 | Isik et al., "NEUROSEC: FPGA-Based Neuromorphic Audio Security", arXiv 2401.12055, 2024 | ABSTRACT ONLY | not stated in abstract (a search snippet claims AES; UNVERIFIED) | No | Yes (FPGA SNN) | n/a (audio) | No | audio, adversarial-attack detection; not event-camera encryption |
| 12 | Marchisio et al., "DVS-Attacks", IJCNN 2021 (arXiv 2107.00415) | ABSTRACT ONLY | n/a | n/a | n/a | n/a | n/a | **active attack on event streams** (perturbation); motivates authentication |
| 13 | Wang, Guo, Li, Wan, "Event Trojan: Asynchronous Event-based Backdoor Attacks", ECCV 2024 (arXiv 2407.06838) | ABSTRACT ONLY | n/a | n/a | n/a | n/a | n/a | **event injection / poisoning** of streams; motivates per-packet tags |
| 14 | Frontiers in Signal Processing survey 2025 (DOI 10.3389/frsip.2025.1585242), section 2.2 "Privacy preservation" | VERIFIED (first half of page) | survey | | | | | lists only Du 2021, Zhang 2024, Ahmad 2023/2024 and Bendig 2024 as event-privacy methods; says these are "far from seamlessly integrat[ed]" |
| 15 | emergentmind topic page "Privacy-Preserving Neuromorphic Sensing" | VERIFIED (aggregator, not citable) | | | | | | listed nothing new beyond #2, #10 and FL/membership-inference works; useful only as a coverage cross-check |
| 16 | NTU "A New Event-driven Dynamic Vision Sensor based ..." (DVS PUF for camera ID and key generation) | UNVERIFIED (HTTP 405) | | | possibly on-chip | | | security *primitive* on a DVS; not stream encryption. Open it before citing. |

### Searches that returned nothing relevant
I ran each query below and found no paper that does what the query describes:
- AER (address-event representation) encryption or authentication on a link or chip. The hits were only AER transport papers, e.g. the UDP AER format (arXiv 2501.09128), which deals with transport and has no security.
- AES / ChaCha / Ascon applied to event-camera streams. The hits were frame-video ciphers only.
- "authenticated encryption" with event camera, DVS or neuromorphic stream.
- FPGA or ASIC encryption of DVS/event streams. The FPGA event papers found (gesture HOTS, contrast maximisation, orbital detection, Loihi 2 fall detection) do no encryption.
- Format-preserving encryption of event coordinates.
- Ascon with neuromorphic, event camera or spiking data.

### Supporting (non-event) reference for the cycle-walking risk
- Bellare, Rogaway, Ristenpart, Stegers, "Format-Preserving Encryption", SAC 2009. VERIFIED (landing page). It revisits cycle walking and states that the timing information cycle walking may leak is "not a damaging thing to leak". This is a citable argument for the variable-latency issue, but **it does not remove the hardware throughput problem**. The design still needs a fixed-latency variant (e.g. an unrolled bounded number of walks plus a fallback, or a permutation built directly on the W x H domain) or an elastic buffer sized from the worst-case walk distribution.
- FF1/FF3 small-domain attacks show up in the FPE results (e.g. "Breaking The FF3 Format-Preserving Encryption Standard Over Small Domains"; snippet: FF1 with N=7 and FF3 with 7<=N<=10 fall short of 128-bit security). UNVERIFIED. These matter because our position domain (W x H, about 2^16 to 2^20 points) is small. Open them before writing the security section.

---

## 3. Conclusion: does the gap still hold?

**Claimed gap:** a standard, authenticated cipher (Ascon-AEAD128, NIST SP 800-232) applied to event-camera data at sensor speed on an FPGA, with output that stays in a readable event format.

**Verdict: the gap holds on every axis I could check, with two caveats.**

1. **No standard cipher on events (only weakly contested).** Du 2021 uses a chaotic map. Zhang 2024 uses noise synthesis with an unnamed key function. SECAM 2026 uses an optical offset map. The anonymisation works (Ahmad, Bendig, Mueller) are learned and keyless. PrivSpike uses a standard scheme (CKKS), but for private SNN inference, not stream protection, and it is far from sensor speed.
2. **No authentication on events (clear gap).** None of the event-privacy works provides integrity, a tag, replay or deletion protection. Active attacks on event streams are published (DVS-Attacks 2021, Event Trojan 2024), so per-packet tags plus a nonce counter answer a documented threat. This is the strongest novelty claim.
3. **No FPGA/ASIC event encryption (clear, but SECAM needs careful wording).** SECAM (Communications Engineering 2026) calls itself "hardware-level privacy" for event cameras. It is optical (a DMD modulates light before the sensor), not digital or cryptographic, and needs offline neural decoding. Paper 2 must cite it and state the difference: a digital, standard, authenticated cipher in programmable logic, versus optical analogue scrambling with a calibrated offset-map key.
4. **Format-preserving (partly shared with prior work).** Du 2021 also keeps the event tuple format, and Zhang 2024 keeps it but adds events. Format preservation alone is **not** novel. What is new is format preservation with a standard primitive and a security argument, a keyed permutation inside W x H rather than chaotic scrambling. Paper 2 should say this plainly.
5. **Reconstruction attacks are expected.** Every prior work evaluates them: E2VID in Du, CF plus four denoisers in Zhang, E2VID and NER-Net+ in SECAM. N3 (E2VID/FireNet) and the learned attacker (N4) are required to be credible, not a novelty. A denoising attack in the style of Zhang is worth adding against V1-V3. Timestamps and event rate stay in the clear at V1/V2, and the Du 2021 timestamps are also unencrypted, so the motion and rate leakage experiment (N5) is a fair and new point of comparison.

**Closest prior work:**
- **Du et al. 2021**: keyed, reversible, format-preserving (x, y, p scrambled, t clear), with an E2VID attack. Software, chaotic, no authentication. This is the primary baseline for the active-attack experiment N9 and for E2VID.
- **Zhang, Zhu, Lam 2024 (NCE)**: in the same venue, so the paper must address it directly. Noise-based, software, no authentication, non-deterministic quadratic runtime.
- **Bao et al. 2026 (SECAM)**: the only "hardware-level" event encryption, and the newest. Optical, non-standard, no authentication. It also reports 2D-NVS (Du) at about 1.9 us/event, a useful second measurement of the software baseline's cost.

**Risks to the novelty claim:**
- The TU Delft 2026 thesis (#9) and the NTU DVS-PUF paper (#16) could not be opened. Neither seems to use a standard authenticated cipher in hardware, but check both before submission.
- IEEE Xplore could not be searched directly (no Xplore pages came back). Run a final Xplore and Scopus query ("event camera" AND (encrypt* OR authenticat*)) before submission. A 2026 conference paper may have appeared since this search.
- Do not claim "first event encryption" or "first hardware event privacy": Du 2021 and SECAM 2026 rule those out. A defensible claim is "first standard authenticated encryption (NIST SP 800-232 Ascon) of event-camera streams, implemented at sensor rate in FPGA logic, with format-preserving modes and evaluation of active attacks (inject, replay, delete, splice)".

---

## Sources opened
- https://pmc.ncbi.nlm.nih.gov/articles/PMC8272045/ (Du 2021)
- https://arxiv.org/abs/2306.03369 and https://arxiv.org/html/2306.03369 (Zhang 2024)
- https://pmc.ncbi.nlm.nih.gov/articles/PMC13396165/ (SECAM 2026)
- https://arxiv.org/abs/2308.04402 (Ahmad 2023)
- https://arxiv.org/abs/2411.16440 (AnonyNoise)
- https://arxiv.org/abs/2604.12803 (Generative Anonymization)
- https://arxiv.org/abs/2212.03177 (Kim, TIP 2025)
- https://arxiv.org/abs/2510.03995 (PrivSpike)
- https://arxiv.org/abs/2401.12055 (NEUROSEC)
- https://arxiv.org/abs/2107.00415 (DVS-Attacks)
- https://arxiv.org/abs/2407.06838 (Event Trojan)
- https://www.frontiersin.org/journals/signal-processing/articles/10.3389/frsip.2025.1585242/full (survey, first half)
- https://www.emergentmind.com/topics/privacy-preserving-neuromorphic-sensing (aggregator, cross-check only)
- https://web.cs.ucdavis.edu/~rogaway/papers/fpe.html (Bellare et al. FPE, SAC 2009)

Not opened (UNVERIFIED): TU Delft thesis (repository.tudelft.nl, connection refused); IEEE Access 2024 Ahmad (DOAJ 403); NTU DVS PUF PDF (HTTP 405); FF3 small-domain attack papers; SteganoSNN (Springer, login redirect; it does not appear to concern event cameras).
