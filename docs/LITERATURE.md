# Literature map for the journal version

These are the papers the journal experiments (X1–X30, `docs/JOURNAL_RUNBOOK.md`) are measured against. Each entry was checked at its source on 6 Nov 2026. "Crossref" means the title, authors, venue, year and DOI were confirmed through the Crossref API; "publisher" means they were confirmed on the publisher's page or arXiv. An entry marked **verify** has not been checked yet, and a manuscript must not cite it until it is.

The "Used by" column names the experiment that answers the paper, or the claim the paper backs up.

## 1. Standards and the cipher

| Key | Reference | Checked | Used by |
|---|---|---|---|
| sp800232 | M. Sönmez Turan, K. A. McKay, D. Chang, et al., *Ascon-Based Lightweight Cryptography Standards for Constrained Devices*, NIST SP 800-232, 2025 | publisher | whole design |
| ascon | C. Dobraunig, M. Eichlseder, F. Mendel, M. Schläffer, "Ascon v1.2: Lightweight Authenticated Encryption and Hashing", *J. Cryptology*, 2021, doi:10.1007/s00145-021-09398-9 | Crossref | whole design |
| t81 | ITU-T T.81 (JPEG baseline) | publisher | golden model |
| wallace1992 | G. K. Wallace, "The JPEG Still Picture Compression Standard", 1992 | publisher | background |
| rfc3711 | M. Baugher et al., *The Secure Real-time Transport Protocol (SRTP)*, RFC 3711 | publisher | X24 (`software/system/baselines/stream_protection.py`) |
| fips203 | NIST FIPS 203, ML-KEM, 2024 | publisher | `pq_kex_cost.py` |

## 2. Ascon in hardware: comparison rows for X11 and X12

| Key | Reference | Checked | Used by |
|---|---|---|---|
| gross2015 | H. Gross, E. Wenger, C. Dobraunig, C. Ehrenhöfer, "Suit up! Made-to-Measure Hardware Implementations of ASCON", Euromicro DSD 2015, doi:10.1109/DSD.2015.14 | Crossref | X12: ASIC GE row (low-area and high-throughput designs) |
| gross2017 | the same authors, "Ascon hardware implementations and side-channel evaluation", *Microprocessors and Microsystems*, 2017, doi:10.1016/j.micpro.2016.10.006 | Crossref | X12, X15 |
| khan2024 | S. Khan, K. Inayat, F. B. Muslim, et al., "Securing the IoT ecosystem: ASIC-based hardware realization of Ascon lightweight cipher", *Int. J. Inf. Secur.* 23:3653–3664, 2024, doi:10.1007/s10207-024-00904-1 | publisher | X12 (ASIC area and throughput); its §2.2 lists the FPGA designs below |
| malal2024 | A. Malal, "High-Performance FPGA Implementations of Lightweight ASCON-128 and ASCON-128a With Enhanced Throughput-to-Area Efficiency", ISCTürkiye 2024, doi:10.1109/ISCTrkiye64784.2024.10779273 (also ePrint 2025/825) | Crossref | X8, X11: Artix-7, Kintex-7 and Spartan-7 rows |
| kurian2025 | M. Gladis Kurian, Y. Chen, "Ascon on FPGA: Post-Quantum Safe Authenticated Encryption with Replay Protection for IoT", *Electronics* 14(13), 2025, doi:10.3390/electronics14132668 | Crossref | X11 |
| khairallah2023 | M. Khairallah, S. Yadhunathan, "FPGA Implementations of MACs based on Ascon-p", NIST LWC Workshop 2023 | publisher | X11 (tag-only cost) |
| farahmand2016 | F. Farahmand et al., "A Zynq-based Testbed for the Experimental Benchmarking of Algorithms Competing in Cryptographic Contests" | publisher | X1/X4 (method for measuring on Zynq) |
| — | Yalla & Kaps 2017; Diehl et al. 2018; Rezvani et al. 2019 (Spartan-6 Ascon designs, cited in khan2024 §2.2) | **verify** | X11 |

## 3. Selective and format-compliant image and video encryption: comparison schemes for X19

| Key | Reference | Checked | Used by |
|---|---|---|---|
| massoudi2008 | A. Massoudi, F. Lefebvre, C. De Vleeschouwer, B. Macq, J.-J. Quisquater, "Overview on Selective Encryption of Image and Video: Challenges and Perspectives", *EURASIP J. Inf. Security*, 2008, doi:10.1155/2008/179290 | Crossref | framing |
| liu2010 | F. Liu, H. Koenig, "A survey of video encryption algorithms", *Computers & Security*, 2010, doi:10.1016/j.cose.2009.06.004 | Crossref | framing; X19 |
| tang1996 | L. Tang, "Methods for encrypting and decrypting MPEG video data efficiently", ACM Multimedia 1996, doi:10.1145/244130.244209 | Crossref | X19: scheme "Tang" (zig-zag permutation) in `benchmark_suite.py` |
| kurihara2015 | K. Kurihara, S. Shiota, H. Kiya, "An encryption-then-compression system for JPEG standard", PCS 2015, doi:10.1109/PCS.2015.7170059 | Crossref | X19: scheme "EtC" in `benchmark_suite.py` |
| vandroogenbroeck2002 | M. Van Droogenbroeck, R. Benedett, "Techniques for a Selective Encryption of Uncompressed and Compressed Images", ACIVS 2002 | publisher | X19 |
| puech2005 | W. Puech, J. M. Rodrigues, "Crypto-Compression of Medical Images by Selective Encryption of DCT", EUSIPCO 2005 | publisher | X19 |
| auer2013 | S. Auer, A. Bliem, D. Engel, et al., "Bitstream-Based JPEG Encryption in Real-time", 2013 | publisher | X19 |
| boyadjis2017 | B. Boyadjis et al., "Extended Selective Encryption of H.264/AVC (CABAC)- and HEVC-Encoded Video Streams", *IEEE TCSVT*, 2017 | publisher | X19 (the codec-level alternative) |
| hirose2024 | M. Hirose, S. Imaizumi, H. Kiya, "On the Security of Bitstream-level JPEG Encryption with Restart Markers", 2024 | publisher | E5 design; X18 |
| li2025shuffle | S. Li et al., "Fast Attack Algorithm for JPEG Image Encryption with Block Position Shuffle", 2025 | publisher | X18 (attack on E5) |
| lin2024 | R. Lin, S. Liu, J. Jiang, S. Li, et al., "Recovering Sign Bits of DCT Coefficients in Digital Images as an Optimization Problem", 2024 | publisher | `sign_recovery.py`, X18 |
| sirichotedumrong2020 | W. Sirichotedumrong, H. Kiya, "Visual Security Evaluation of Learnable Image Encryption Methods against Ciphertext-only Attacks", 2020 | publisher | X18 |

## 4. Encryption of images and video on FPGAs: the closest prior work for X11

| Key | Reference | Checked | Used by |
|---|---|---|---|
| kishore2015 | B. Kishore, B. K. Shreyamsha Kumar, et al., "FPGA Based Simple and Fast JPEG Encryptor", 2015 | publisher | X11 |
| bagbaba2015 | A. Ç. Bağbaba et al., "Hardware Implementation of Novel Image Compression-Encryption System on a FPGA", 2015 | publisher | X11 |
| qiu2025 | H. Qiu, J. Lian, X. Wang, et al., "Securing Satellite Communications: Real-Time Video Encryption Scheme on Satellite Payloads", arXiv 2025 | publisher | X11 |
| logijpge / castjpeg | Xylon logiJPGE and CAST JPEG-E-S data sheets (commercial JPEG encoder IP) | publisher | X11: JPEG encoder rows with no security |

## 5. Video privacy metrics and attackers (X17, X18, X21)

| Key | Reference | Checked | Used by |
|---|---|---|---|
| erdelyi2017 | Á. Erdélyi, T. Winkler, B. Rinner, "Privacy protection vs. utility in visual data: an objective evaluation framework", *Multimedia Tools and Applications*, 2017, doi:10.1007/s11042-016-4337-7 | Crossref | X17: face-detection and recognition metrics on protected frames, the design of `privacy_metrics.py` |
| korshunov2012 | P. Korshunov, S. Cai, T. Ebrahimi, "Crowdsourcing approach for evaluation of privacy filters in video surveillance", ACM MM 2012 Workshop on Crowdsourcing for Multimedia, doi:10.1145/2390803.2390817 | Crossref | X21: method for the viewer study |
| — | "A framework for objective evaluation of privacy filters in video surveillance" (EPFL, SPIE): face detection as the intelligibility metric and recognition as the privacy metric | **verify** (authors and DOI not confirmed) | X17 |
| ssim | Z. Wang, A. C. Bovik, H. R. Sheikh, E. P. Simoncelli, "Image Quality Assessment: From Error Visibility to Structural Similarity", *IEEE TIP*, 2004 | publisher | X17 |
| lpips2018 | R. Zhang, P. Isola, A. A. Efros, E. Shechtman, O. Wang, "The Unreasonable Effectiveness of Deep Features as a Perceptual Metric", CVPR 2018, doi:10.1109/CVPR.2018.00068 | Crossref | X17: LPIPS column |
| yunet2023 | W. Wu, H. Peng, S. Yu, "YuNet: A Tiny Millisecond-level Face Detector", *Machine Intelligence Research*, 2023, doi:10.1007/s11633-023-1423-y | Crossref | X17: face detector |
| ren2015 | S. Ren, K. He, R. Girshick, J. Sun, "Faster R-CNN", NeurIPS 2015 | publisher | `recognition.py` |
| unet / isola2017 | U-Net (MICCAI 2015); pix2pix (CVPR 2017) | publisher | `learned_attack.py`, X18 |
| pomeranz2011 / gallagher2012 | jigsaw-puzzle solvers | publisher | E5 attacks |

## 6. Traffic analysis of encrypted video (size leak, padding: X7)

| Key | Reference | Checked | Used by |
|---|---|---|---|
| schuster2017 | R. Schuster, V. Shmatikov, E. Tromer, "Beauty and the Burst: Remote Identification of Encrypted Video Streams", USENIX Security 2017 | publisher | X7, `size_leak.py` |
| wampler2015 | C. Wampler, S. Uluagac, R. Beyah, "Information Leakage in Encrypted IP Video Traffic", 2015 | publisher | X7 |
| apthorpe2019 | N. Apthorpe et al., "Keeping the Smart Home Private with Smart(er) IoT Traffic Shaping", PoPETs 2019 | publisher | X7: padding policies |

## 7. Neuromorphic and event cameras (the second paper, X26–X30)

| Key | Reference | Checked | Used by |
|---|---|---|---|
| gallego2022 | G. Gallego, T. Delbruck, G. Orchard, C. Bartolozzi, et al., "Event-Based Vision: A Survey", *IEEE TPAMI*, 2022, doi:10.1109/TPAMI.2020.3008413 | Crossref | background |
| du2021 | B. Du, W. Li, Z. Wang, M. Xu, T. Gao, J. Li, H. Wen, "Event Encryption for Neuromorphic Vision Sensors: Framework, Algorithm, and Evaluation", *Sensors* 21(13):4320, 2021, doi:10.3390/s21134320 | publisher | X26–X30: chaotic-map baseline (position shuffle, polarity flip) |
| zhang2024 | P. Zhang, S. Zhu, E. Y. Lam, "Event encryption: rethinking privacy exposure for neuromorphic imaging", *Neuromorphic Computing and Engineering*, 2024, doi:10.1088/2634-4386/ad207b | Crossref | X26–X30: noise-injection baseline; the target journal |
| zhu2024 | S. Zhu et al., "Neuromorphic encryption: combining speckle correlography and event data for enhanced security", *Advanced Photonics Nexus*, 2024, doi:10.1117/1.APN.3.5.056002 | Crossref | X26–X30 |

## Gaps still to fill before the paper phase

- **X11 (state of the art):** verify the Spartan-6 Ascon papers above. Add two or three FPGA JPEG encoders from 2018 or later that report LUTs and throughput on 7-series parts. The search results so far, mostly DergiPark and SAI conference papers, are weak venues and do not belong in a Q1 table without a reason.
- **X15 (TCHES only):** find a masked Ascon on FPGA and a TVLA methodology reference.
- **X21:** find an ITU-R BT.500 or P.910 reference for the viewer-study protocol.
