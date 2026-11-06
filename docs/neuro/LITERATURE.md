# Paper 2 references and how each was verified

Copied from the notes in `docs/neuro/notes/` (checked 6 Nov 2026); nothing here comes from memory. Status:
- **full**: full text (PDF, HTML or PMC) read;
- **abstract**: abstract or landing page only; cite only for what the abstract states (†in DESIGN.md);
- **meta**: bibliographic metadata only (Crossref/OpenAlex); cite as a source of a dataset or as a pointer, not
  for content (ᴹ in DESIGN.md);
- **UNVERIFIED**: not opened, or only search snippets seen. Do not cite until someone opens it.

Bibliographic fields follow Crossref where a DOI exists. Where two notes disagree, both readings are given.

## 1. Event-camera privacy, encryption and attacks

| Key | Reference | DOI / id | Status | How verified (note) | Used for |
|---|---|---|---|---|---|
| `du2021sensors` | B. Du, W. Li, Z. Wang, M. Xu, T. Gao, J. Li, H. Wen, "Event Encryption for Neuromorphic Vision Sensors: Framework, Algorithm, and Evaluation," *Sensors* 21(13):4320, 2021 | 10.3390/s21134320 | full | Crossref; PMC8272045 read as text (lit_event_encryption §1.1, lit_privacy_attacks) | main baseline; no authentication in the text; 0.20 µs/event on Pi 4B (their CPU number) |
| `zhang2024nce` | P. Zhang, S. Zhu, E. Y. Lam, "Event encryption: rethinking privacy exposure for neuromorphic imaging," *Neuromorph. Comput. Eng.* 4(1):014002, 2024 | 10.1088/2634-4386/ad207b; arXiv 2306.03369 | full (arXiv HTML v3) | Crossref; arXiv abstract + HTML. Per-cell table numbers **not** copied (column order unlabeled); re-read the PDF before quoting | baseline in the target journal; CF attacker, four denoisers |
| `bao2026secam` | Bao, Shi, Zhai, Wang, "Asynchronous temporal mapping for high-dynamic-range video and hardware-level privacy with event cameras," *Commun. Eng.* 5:136, 2026 | 10.1038/s44172-026-00687-4 | full | PMC13396165 (lit_event_encryption) | wording rule: hardware-level but optical |
| `ahmad2023iccv` | S. Ahmad, P. Morerio, A. Del Bue, "Person Re-Identification without Identification via Event Anonymization," ICCV 2023, pp. 11098-11107 | 10.1109/ICCV51070.2023.01022; arXiv 2308.04402 | full per lit_privacy_attacks (arXiv PDF read: Table 2 SSIM 0.548, Table 3 Du SSIM 0.451); lit_event_encryption lists it as abstract only | Crossref; arXiv PDF text | Event-ReId dataset (doi 10.5281/zenodo.8256439), N3 anchors |
| `ahmad2024access` | Ahmad, Morerio, Del Bue, "Event Anonymization: …," *IEEE Access* 12:66964-66980, 2024 | 10.1109/ACCESS.2024.3399539 | meta (content UNVERIFIED) | Crossref only; DOAJ/publisher 403 | extension only; no numbers |
| `adra2025iwbf` | M. Adra, J.-L. Dugelay, "E2PRIV: Privacy-Preserving Event-to-Video Reconstruction with Face Anonymization," IWBF 2025 | 10.1109/IWBF63717.2025.11113401 | full | Crossref; EURECOM PDF read | faces leak via E2VID (ArcFace ~89 %) |
| `bendig2025wacv` | K. Bendig et al., "AnonyNoise," WACV 2025 | arXiv 2411.16440 (proceedings DOI UNVERIFIED) | abstract | arXiv page; GitHub licence (MIT) | related work |
| `muller2026lovif` | A. T. Müller, M. Kocsis, N. C. Stache, "Generative Anonymization in Event Streams," 2026 | arXiv 2604.12803 | abstract | arXiv page | related work |
| `meng2026eventface` | Q. Meng, X. Dong, Z. Jin, M. Tistarelli, "EventFace," 2026 | arXiv 2604.06782 | abstract | arXiv page | learned attacker motivation |
| `kim2025tip` | J. Kim et al., "Privacy-Preserving Visual Localization with Event Cameras," *IEEE TIP* 34:6215-6230, 2025 | arXiv 2212.03177 (publisher DOI UNVERIFIED) | abstract | arXiv page | related work (optional) |
| `shen2024sscae` | Y. Shen et al., "Privacy Protection of Sensitive Bioinformation Based on Event Cameras," *Strategic Study of CAE* 26(1):202-215, 2024 | 10.15302/J-SSCAE-2024.01.017 | abstract | publisher page | counter-position |
| `wang2019evgait` | Y. Wang et al., "EV-Gait," CVPR 2019, pp. 6351-6360 | 10.1109/CVPR.2019.00652 | meta (content UNVERIFIED) | Crossref | cite only as "identity from events" |
| `marchisio2021ijcnn` | Marchisio et al., "DVS-Attacks," IJCNN 2021 | arXiv 2107.00415 | abstract | arXiv page | active attacks exist |
| `wang2024eccv` | Wang, Guo, Li, Wan, "Event Trojan: Asynchronous Event-based Backdoor Attacks," ECCV 2024 | arXiv 2407.06838 | abstract | arXiv page | injection threat (method not reproduced) |
| `njungle2025privspike` | Njungle, Jahns, Stojkov, Kinsy, "PrivSpike," 2025 | arXiv 2510.03995 | abstract | arXiv page | different problem (HE inference) |
| `adra2025review` | Adra et al., "Event-based Solutions for Human-centered Applications: A Comprehensive Review," 2025 | arXiv 2502.18490 | abstract | arXiv page | background |
| `frsip2025survey` | Frontiers in Signal Processing survey, §2.2 "Privacy preservation," 2025 | 10.3389/frsip.2025.1585242 | full (first half of the page) | publisher page | coverage cross-check |

## 2. Reconstruction and recognition tools

| Key | Reference | DOI / id | Status | How verified | Used for |
|---|---|---|---|---|---|
| `rebecq2019cvpr` | H. Rebecq, R. Ranftl, V. Koltun, D. Scaramuzza, "Events-To-Video," CVPR 2019, pp. 3852-3861 | 10.1109/CVPR.2019.00398; arXiv 1904.08298 | abstract + code | Crossref; arXiv; checkpoint read statically (SHA-256 `4cfeb2c8…6574128`) | N3 attacker |
| `rebecq2021tpami` | same authors, "High Speed and High Dynamic Range Video with an Event Camera," *TPAMI* 43(6):1964-1980, 2021 | 10.1109/TPAMI.2019.2963386 | abstract | Crossref; arXiv | cite with the CVPR paper |
| `scheerlinck2020wacv` | C. Scheerlinck et al., "Fast Image Reconstruction with an Event Camera" (FireNet), WACV 2020, pp. 156-163 | 10.1109/WACV45572.2020.9093366 | abstract + code | Crossref; project page; checkpoint read statically (SHA-256 `a64af319…a696e`) | N3 attacker |
| `stoffregen2020eccv` | T. Stoffregen et al., "Reducing the Sim-to-Real Gap for Event Cameras," ECCV 2020 | arXiv 2003.09078 (publisher DOI UNVERIFIED) | abstract | arXiv page; GitHub README | HQF dataset, optional stronger attacker |
| Scheerlinck complementary filter (CF) | used by Zhang 2024 as its reconstruction attacker | **UNVERIFIED** (not opened; no citation in the notes) | – | – | N3 CF attacker: open the paper and add it here before use |
| `fang2021iccv` | Fang et al., "Incorporating Learnable Membrane Time Constant…" (PLIF), ICCV 2021 | 10.1109/ICCV48922.2021.00266; arXiv 2007.05785 | full (arXiv HTML) | OpenAlex; arXiv HTML | N6 context: 99.61 % N-MNIST, 97.57 % DVS Gesture |
| snnTorch tutorial 7 | snntorch.readthedocs.io tutorial_7 | URL | full (page) | opened | N6 SNN starting point (~60 % demo only) |
| `eshraghian2023procieee` | Eshraghian et al., "Training Spiking Neural Networks Using Lessons From Deep Learning," *Proc. IEEE* 2023 | 10.1109/JPROC.2023.3308088 | meta | OpenAlex | cite snnTorch |
| `fang2023sciadv` | Fang et al., SpikingJelly, *Science Advances* 2023 | 10.1126/sciadv.adi1480 | meta | OpenAlex | optional |

## 3. Data formats, sensors, datasets

| Key | Reference | Status | How verified | Used for |
|---|---|---|---|---|
| `prophesee_evt2` | Prophesee Metavision SDK 5.3.1 docs, "EVT 2.0 Format" | full | page read in Chrome (evt2_spec_verified) | word layout |
| IMX636 | Prophesee IMX636 product brief 2024 v3.0; FRAMOS news (1.06 Geps) | full (pages) | opened (lit_formats_data §5) | rate bound |
| DAVIS346 | iniVation DAVIS346 documentation (12 MEPS) | full (page) | opened | rate reference |
| DVS128 | Lichtsteiner, Posch, Delbruck, *IEEE JSSC* 43(2):566-576, 2008, doi 10.1109/JSSC.2007.914337 | meta; peak rate **UNVERIFIED** | OpenAlex | not cited for rate |
| GenX320 | Prophesee GenX320 doc page | page opened; event-rate figures **UNVERIFIED** | opened | EVT 2.0 sensor |
| `orchard2015fnins` | Orchard et al., "Converting Static Image Datasets to Spiking Neuromorphic Datasets Using Saccades," *Front. Neurosci.* 2015, doi 10.3389/fnins.2015.00437 | meta | OpenAlex; Tonic source read | N-MNIST |
| `amir2017cvpr` | Amir et al., "A Low Power, Fully Event-Based Gesture Recognition System," CVPR 2017, doi 10.1109/CVPR.2017.781 | meta (abstract 403); 96.5 % from the IBM page only | OpenAlex; IBM page | DVS Gesture |
| Tonic 1.7.0 | PyPI JSON and source files on GitHub | full (source) | opened; Kaggle install **UNVERIFIED** | loaders |
| expelliarmus | GitHub README | full (README) | opened | independent EVT 2.0 reader (N8-R, N11) |
| `hu2021v2e` | Hu, Liu, Delbruck, "v2e," CVPRW 2021, arXiv 2006.07722 | abstract + source files | arXiv; `v2ecore` files; `emulator_utils` formulas **UNVERIFIED** | v2e-lite idea |
| ESIM | Rebecq, Gehrig, Scaramuzza, CoRL 2018 | meta; method **UNVERIFIED** | OpenAlex/ZORA | not used |

## 4. Format-preserving encryption and Feistel cryptanalysis

| Key | Reference | Status | How verified (lit_fpe_crypto §11) |
|---|---|---|---|
| `black2002ctrsa` | J. Black, P. Rogaway, "Ciphers with Arbitrary Finite Domains," CT-RSA 2002, doi 10.1007/3-540-45760-7_9 | full | PDF from Rogaway's site |
| `nist2025sp80038gr1` | M. Dworkin, N. Mouha, NIST SP 800-38G Rev. 1 2pd, Feb 2025 | full | csrc.nist.gov |
| NIST SP 800-38G (2016) | status page | abstract | csrc.nist.gov |
| `bellare2009sac` | Bellare, Ristenpart, Rogaway, Stegers, "Format-Preserving Encryption," SAC 2009 | abstract (landing page) | rogaway's page |
| `bellare2016ccs` | Bellare, Hoang, Tessaro, CCS 2016, doi 10.1145/2976749.2978390, ePrint 2016/794 | abstract | ePrint |
| `durak2017crypto` | Durak, Vaudenay, "Breaking the FF3 … Over Small Domains," CRYPTO 2017, ePrint 2017/521 | abstract | ePrint |
| `durak2018acns` | Durak, Vaudenay, "Generic Round-Function-Recovery Attacks for Feistel Networks over Small Domains," ACNS 2018, ePrint 2018/108 | abstract | ePrint |
| `hoang2018crypto` | Hoang, Tessaro, Trieu, "The Curse of Small Domains," CRYPTO 2018, ePrint 2018/556 | abstract | ePrint |
| `hoang2019eurocrypt` | Hoang, Miller, Trieu, "Attacks Only Get Better," EUROCRYPT 2019, ePrint 2019/244 | abstract | ePrint |
| `hoang2012crypto` | Hoang, Morris, Rogaway, "An Enciphering Scheme Based on a Card Shuffle," CRYPTO 2012, doi 10.1007/978-3-642-32009-5_1 | full | ar5iv (eq. 1 used in script (a)) |
| `patarin2010eprint` | Patarin, ePrint 2010/293 | abstract | ePrint |
| `denis2025eprint` | Denis, "HCTR2-FP and HCTR3-FP," ePrint 2025/1888 | abstract | ePrint |
| `nist2025sp800232` | NIST SP 800-232, Ascon, Aug 2025 | abstract (CSRC page); implementation checked against the official KATs in paper 1 | CSRC |

## 5. UNVERIFIED (do not cite until opened)

- Luby-Rackoff 1988 (doi 10.1137/0217022): metadata only, content unverified.
- Patarin CRYPTO 2003 (doi 10.1007/978-3-540-45146-4_30) and CRYPTO 2004 (doi 10.1007/978-3-540-28628-8_7):
  content unverified.
- Beyne, CRYPTO 2021 (ePrint 2021/815): only read as cited inside SP 800-38G Rev. 1.
- Perez-Resa et al., IEEE Access 2020 (doi 10.1109/ACCESS.2020.2968816): content unverified.
- Agbeyibor et al., IFIP AICT 441, 2014: pages refused access.
- FF3 small-domain snippet ("FF1 with N = 7 … fall short of 128-bit security").
- Boetius, TU Delft bachelor thesis 2026, and the two TU Delft privacy theses: repository refused connection.
- NTU DVS-PUF paper: HTTP 405.
- NEUROSEC (arXiv 2401.12055): abstract seen; the AES claim is from a snippet only.
- "Neuromorphic encryption: combining speckle correlography and event data" (Adv. Photonics Nexus 2024): snippet.
- Chinese patent CN122339855A: snippet, not peer reviewed.
- Ahmad 2024 Access content (metadata only, above).
- DVS128 peak event rate; GenX320 event-rate figures; v2e `lin_log` / `compute_event_map`; ESIM method;
  AEDAT layouts; Tonic install on Kaggle; Amir 2017 abstract.
- The Scheerlinck complementary-filter paper (needed for the N3 CF attacker).
- The DVS Gesture subject split (which subjects are in train/test): read it from the dataset files.

## 6. Searches that found nothing (repeat before submission)

No paper was found that applies a standard AEAD (Ascon, AES-GCM) with per-packet tags to event streams, or that
implements event encryption on an FPGA (lit_event_encryption §2, lit_privacy_attacks §1). This is a search
result, not a proof of absence: rerun the IEEE Xplore and Scopus query ("event camera" AND (encrypt* OR
authenticat*)) before submission.
