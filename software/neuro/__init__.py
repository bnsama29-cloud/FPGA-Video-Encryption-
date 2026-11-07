"""Golden model of paper 2: authenticated, format-preserving encryption of EVT 2.0 event streams.

Contract n1 (docs/neuro/DESIGN.md). The model is the referee for the RTL in hardware/rtl/neuro/. It is
pure Python + numpy and reuses paper 1's shared crypto unchanged (model.ascon, link.keys); no paper-1
file is edited.

    geometry  sensor geometries (DESIGN §2.3)
    evt2      EVT 2.0 words: canonical encoder, decoder, input rules, event equality, RAW files (§2.1-§2.5)
    keys      key schedule, nonces, domain separation, epoch ratchet (§3.4)
    stats     shared confidence intervals and mutual information for the experiments (§8.3)
"""

CONTRACT = "n1"
VERSION = 1          # header version byte (DESIGN §3.3)
