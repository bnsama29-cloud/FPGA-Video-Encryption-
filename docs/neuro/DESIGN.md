# Paper 2 design specification: authenticated, format-preserving encryption of event-camera streams (contract n1)

Status: **draft contract n1, revision 2, 7 Nov 2026**, branch `neuromorphic`. Nothing is implemented yet, so
revision 2 replaces revision 1 without a version bump (the version byte stays 1). This file does for paper 2
what `docs/INTERFACES.md` does for paper 1. The golden model (`software/neuro/`), the RTL
(`hardware/rtl/neuro/`), the tests and the experiments all follow it. If code and this file disagree, either
the code is wrong or this file is changed first, with a line in §11 (changelog) that says why. Review points
that were not applied as written are listed with reasons in Appendix A.

Inputs: the eight notes in `docs/neuro/notes/` (read 6 Nov 2026) and the review of revision 1 (7 Nov 2026).
Numbers in this file come from three places only.
(a) Script output: `experiments/neuro/fpe_design_numbers.py` writes `sim_out/neuro_fpe/fpe_design_numbers.{json,md}`
("script (a)"). (b) Paper-1 results named in `docs/neuro/notes/repo_crypto.md`. (c) Plain arithmetic on the
format, marked *(arith.)*. Every *(arith.)* figure must be recomputed by the script of the experiment named next
to it before it goes into the paper. Planning guesses (compute budgets, §8.4) are marked *(guess)* and are
replaced by measurements. Citation keys refer to §12 and `docs/neuro/LITERATURE.md`. Only verified references
are cited.

---

## 1. Problem, threat model, novelty claim

### 1.1 Problem

An event camera (DVS) sends one word per brightness change at a pixel: position (x, y), polarity p and a µs
timestamp t. Two published reconstruction networks turn plain event streams back into intensity video:
E2VID [`rebecq2019cvpr`†, `rebecq2021tpami`†] and FireNet [`scheerlinck2020wacv`†]. Faces and identity can be
recognised in that video [`ahmad2023iccv`, `adra2025iwbf`]. So event streams are not private by default.
Event streams can also be actively attacked, for example by perturbation or event injection
[`marchisio2021ijcnn`†, `wang2024eccv`†]. All published event-encryption schemes use a non-standard key function
and none authenticates the stream [`du2021sensors`, `zhang2024nce`, `bao2026secam`]. Paper 2 builds a
sensor-side encryptor on the PYNQ-Z2 (xc7z020clg400-1, 100 MHz). The encryptor:

1. cuts an EVT 2.0 event stream into time packets (default 1024 µs, §3);
2. protects each packet at one of five levels V0-V4 (§4), using only Ascon-AEAD128 (NIST SP 800-232,
   [`nist2025sp800232`†]) as the cryptographic primitive, with every (key, nonce) pair used for one input only
   (§3.4);
3. appends one 16-byte tag per packet, so the receiver detects any change or insertion of a packet, any replay,
   any reordering beyond the replay window, and the deletion of any packet that is followed by an authenticated
   packet or by an authenticated FINAL marker (§3.5); a stream that simply stops is reported as `stall` and,
   at close, as `truncated`;
4. keeps the **payload** of every V1-V3 packet a valid EVT 2.0 word sequence with every coordinate inside the
   sensor's W × H. A keyless consumer extracts the payload from the public framing (`neuro.packet.from_bytes`)
   and can write it to a RAW file that standard EVT 2.0 readers accept (tested in N8-R). The packet bytes on the
   wire are not themselves an EVT 2.0 stream: header, trailer and tag words would decode as garbage events.
   With the key, the payload decrypts exactly.

### 1.2 Assets and trust

- Keys and the encryptor are trusted: the PL fabric and the ARM PS that writes the key registers.
- Keys reach the board through paper 1's hybrid key exchange (`link.keys.kex_init / kex_respond / kex_finish`),
  run **at every boot** in the deployment profile (§3.4). A pre-shared-key profile exists only for offline
  experiments, with the extra conditions of §3.4.
- The network between the sender (board) and the receiver (PC) is not trusted. The receiver is trusted, and its
  replay state (§3.5) is stored persistently.

### 1.3 Passive attacker (eavesdropper)

- Sees every packet byte. Knows the format, the protection level, the algorithm and the geometry (Kerckhoffs).
- Has unlimited offline compute and public pre-trained networks: E2VID and FireNet reconstruction (N3), event
  classifiers and an SNN (N6). It may also train its own network on (ciphertext, plaintext) pairs from other
  scenes under other keys (learned attacker, N4), and it may exploit structure that the format leaves inside a
  packet, such as co-activation of neighbouring pixels (adjacency attack, N4b).
- May know parts of the scene, for example a flashing pattern or hot pixels, which gives known plaintext inside
  a packet (§4.3.6, N8).
- Uses side information the format leaves in the clear: packet size, event count per 64 µs bucket, TIME_HIGH
  values, timestamps (V1/V2), per-pixel multiplicity inside a packet (V2/V3), event rate, the position of
  dummies inside a bucket (§5, N5).

### 1.4 Active attacker (on the network)

It can do everything a passive attacker can, and it can also send, drop, delay and reorder datagrams. Receiver
statuses are defined in §3.5. N7 and `tests/test_neuro_receiver.py` check every row.

| Attack | Attacker action | Required receiver result |
|---|---|---|
| inject | send a forged packet or forged events inside a real packet | tag fails (`forged`). The forged packet has **no effect on receiver state**: the replay window, the epoch and the pinned t_origin move only after a tag verifies (§3.5) |
| replay | resend an old valid packet, inside the session or from an earlier boot | inside a session: counter already seen or below the window (`replay`). From an earlier boot: in the deployment profile the old boot's master is gone, so the tag fails (`forged`) or the boot is unknown (`stale`); in the PSK profile the boot_id is not above the highest one seen (`stale`) |
| delete | drop whole packets or truncate a packet | a missing counter is reported as `gap` when the window passes it, at an epoch switch (from the `link` field and the FINAL flag, §3.3) or at close. Dropping the end of a stream gives `truncated` (no FINAL seen) and, while nothing arrives, `stall`. Truncating a packet makes the tag fail (`forged`). Deletion is detected for any packet followed by an authenticated packet or an authenticated FINAL marker; detection latency is at most the window (64 packets = 65.5 ms at T = 1024 µs *(arith.)*) |
| reorder | swap packets, or swap words inside a packet | packets inside the window are **corrected** (delivered in counter order); outside the window they are **detected** (`replay`, and the counter was already reported as `gap`). Words inside a packet are covered by the tag (`forged`) |
| splice | combine header, payload and trailer from different packets or sessions, or move whole packets between sessions | the tag nonce contains sid and ctr, and the header (sid, ctr, level, geometry, flags, link) is in the tag input, so moving a packet between sessions or positions changes the nonce or the input and the tag fails (`forged`). In the deployment profile the keys are also bound to the boot (§3.4), so a packet from another boot fails under the wrong key as well |
| downgrade | change the level byte, ts_bits, the round count, the padding flags, or replay an older epoch | the header is covered by the tag (`forged`). A sender misconfiguration with a valid tag is caught by the **exact receiver profile** (§3.5 step 3: `policy`). Older epoch: `stale`. Downgrade protection = header authenticity + exact profile match |
| flood | high rate of junk packets | header-only checks run before any MAC (§3.5 steps 1-4): known session, epoch within E_MAX, profile, plausible length, t_start consistency, read-only replay check. Cost: at most one MAC over at most L_max bytes per datagram that passes them; measured in N7 as receiver CPU per junk packet |

### 1.5 Out of scope

- Side channels (power, EM, timing of the PL), fault injection and physical access to the board.
- Compromise of the ARM or of the key exchange.
- Traffic analysis beyond what §5 padding addresses. Packet timing on the network is visible.
- Privacy of what the receiver does with decrypted events.

### 1.6 Novelty claim (exact wording to use)

> *To our knowledge, this is the first protection scheme for event-camera streams that (i) uses a standardised
> authenticated cipher (Ascon-AEAD128, NIST SP 800-232) as its only primitive, (ii) authenticates every packet,
> so injection and splicing are detected, replay and reordering are corrected (inside the window) or detected,
> deletion of any packet followed by an authenticated packet or FINAL marker is detected, and downgrade is
> detected by header authenticity plus an exact receiver profile, (iii) keeps the payload of every packet a
> valid EVT 2.0 word sequence with the original event count and all coordinates inside the sensor geometry,
> through a keyed mixed-radix Feistel permutation whose tables are refreshed every packet, and (iv) runs the
> position permutation and field masking in FPGA logic at fixed latency, one CD word per clock, with an
> end-to-end authenticated throughput of X Mev/s measured on the PYNQ-Z2 (N2, N10).*

X is filled from N2/N10; the pass criteria for (i)-(iv) are fixed in advance in §8.1. Wording rules, from
`lit_event_encryption.md` §3:
- Never claim "first event encryption": Du 2021 [`du2021sensors`] did that.
- Never claim "first hardware-level event privacy": SECAM [`bao2026secam`] is hardware-level, but optical.
- Say "digital, standard and authenticated, in programmable logic", in contrast to SECAM's optical modulation
  with a calibrated offset-map key.
- Format preservation alone is not new: Du 2021 also keeps the event tuple, and Zhang 2024 keeps it but adds
  events. The new part is format preservation together with a standard primitive, a stated security argument
  (§4.3.6) and authentication. Whether format preservation is worth its cost against V4 + padding is measured
  in N11; if no keyless utility survives, V1-V3 are presented as "compatible transport", not as a privacy gain.
- "Original event count" holds only without padding (§5).
- Never call V1 private: it hides polarity only (§9.2 item 1).
- Rerun the IEEE Xplore and Scopus search ("event camera" AND (encrypt* OR authenticat*)) before submission. The
  TU Delft 2026 thesis and the NTU DVS-PUF paper could not be opened (§9.3).

---

## 2. Data format

### 2.1 EVT 2.0 words (source: [`prophesee_evt2`], checked in `notes/evt2_spec_verified.md`)

One 32-bit word per event. Bits 31..28 hold the type. Words are little-endian on the wire and in files
(IMX636 and GenX320 default).

| Type | Code [31:28] | [27:22] | Rest |
|---|---|---|---|
| CD_OFF (p = 0) | `0000` | ts[5:0] | x = [21:11] (11 b), y = [10:0] (11 b) |
| CD_ON (p = 1) | `0001` | ts[5:0] | x = [21:11], y = [10:0] |
| EVT_TIME_HIGH | `1000` | [27:0] = ts[33:6] (28 b) | |
| EXT_TRIGGER | `1010` | ts[5:0] | [12:8] id, [0] edge value, other bits unused |
| OTHERS | `1110` | ts[5:0] | [16] class, [15:0] subtype |
| CONTINUED | `1111` | [27:0] depend on the previous word | |
| other codes | reserved | | |

- Polarity is word bit 28, i.e. the low bit of the type nibble.
- Timestamp t is 34 bits in µs: t = (last TIME_HIGH value << 6) | ts[5:0]. Decoding starts at the first
  TIME_HIGH. The 34-bit rollover (2^34 µs) is not supported in contract n1. On rollover the ARM starts a new
  epoch (§3.4).
- Notation used below: *bucket* = one TIME_HIGH value = 64 µs. *CD word* = type `0000` or `0001`.

### 2.2 Why EVT 2.0 (an honest statement for the paper)

The IMX636 outputs EVT 2.1 and EVT 3.0 (EVT 3.0 is the default). Only the GenX320 outputs EVT 2.0
(`lit_formats_data.md` §0.1). We use EVT 2.0 as the encryptor's wire format because each word is one
self-contained event with fixed fields, which is what word-local format-preserving encryption needs. EVT 3.0 is
stateful (y, base x and time persist across words) and EVT 2.1 packs up to 32 events into one vector, which a
position permutation would have to split. An IMX636 front end therefore needs an EVT 3.0/2.1 to EVT 2.0 unpacker
before the encryptor. That unpacker is not part of the contribution and is not built in contract n1. The
bandwidth cost of staying in EVT 2.0 after protection (no re-vectorisation, worse compression) is measured in
N11.

### 2.3 Supported geometries

The geometry is a runtime register (W, H). The RTL is built for `MAXW x MAXH`, default 1280 x 720.

| Name | W x H | Source of data | Used for |
|---|---|---|---|
| `imx636` | 1280 x 720 | none (no real recording in n1) | **hardware cost and throughput only** (N2, N9 cycle model, N10 synthetic rate). No privacy result is reported at this geometry, because the only events we could produce for it would come from upsampled CIF clips |
| `davis346` | 346 x 260 | none in n1 | hardware cost; DAVIS346 peak 12 MEPS (`lit_formats_data.md` §5) as a rate reference |
| `eventreid` | read from the dataset files in the Kaggle QUICK run (not assumed here) | Event-ReId, real event recordings of people [`ahmad2023iccv`], doi 10.5281/zenodo.8256439 | **main privacy dataset** (N3, N4, N4b, N5 rates, N9 rates) |
| `cif` | 352 x 288 | v2e-lite from Xiph CIF clips at native size (§7.1) | secondary privacy data with exact intensity ground truth; labelled "simulated, no noise model" |
| `dvsgesture` | 128 x 128 | DVS Gesture via Tonic [`amir2017cvpr`ᴹ] | N5, N6, N8; Tonic stores ms precision, so ts[5:0] is almost always 0 (§4.5) |
| `nmnist` | 34 x 34 | N-MNIST via Tonic [`orchard2015fnins`ᴹ] | N5, N6, N8 (real µs timestamps). Not used in N3 (no intensity ground truth) |
| `vga` | 640 x 480 | none | cost tables only |

Legal register values: 1 ≤ W ≤ MAXW, 1 ≤ H ≤ MAXH. W and H do not need to be powers of two. **At V2 and V3,
W ≥ 16 and H ≥ 16 are required** (otherwise `ERR_CFG` at commit, §6.7). Reason: with H = 1 every odd round is
y ← (y + T[x]) mod 1 = 0, so P_ctr collapses to a rotation of x that one known pair recovers, and H = 2 gives one
bit of mixing per round. The bound 16 is a conservative floor chosen by us, not a result; N8 checks the
permutation on the smallest legal domains (16 x 16, 16 x 1280).

### 2.4 Input rules (what the packetizer accepts)

1. Words before the first TIME_HIGH are dropped and counted (`ERR_PRE_TH`).
2. A TIME_HIGH smaller than the current one is dropped and counted (`ERR_ORDER`). An equal TIME_HIGH is
   passed through.
3. A CD word with x ≥ W or y ≥ H is dropped and counted (`ERR_RANGE`) **at every level**. The permutation is
   defined only on Z_W × Z_H, and one rule for all levels keeps the authenticated content independent of the level.
4. EXT_TRIGGER, OTHERS, CONTINUED and reserved codes pass through unchanged. They are authenticated, not encrypted
   (except at V4), and they consume no keystream.
5. **Canonical input (our encoder, `neuro.evt2.encode`)**: emit a TIME_HIGH before an event whenever ts[33:6]
   changes, and also at every packet boundary even if no event follows (boundary heartbeat, §3.2). This makes
   packet closing deterministic. Whether a real sensor sends periodic TIME_HIGH words is an open question (§9.3).
6. **Time jump.** A TIME_HIGH with `64·value − t_start > MAX_GAP_US` (register, default 1 000 000 µs, i.e. about
   977 empty packets at T = 1024 µs *(arith.)*) is a jump. The response is chosen by `MODE.JUMP_MODE`:
   - `0` (drop, default): the TIME_HIGH is dropped and counted in `ERR_JUMP`. Every following word up to the
     next TIME_HIGH that is not a jump is also dropped and counted in `ERR_JUMP`, because its timestamp would
     be read against the wrong TIME_HIGH. If the sensor really restarted, the stream stays dropped and the
     ARM sees `ERR_JUMP` rise and starts a new epoch (§3.4).
   - `1` (halt): the open packet is closed, one empty FINAL packet is emitted (§3.2), `STATUS.JUMP_HALT` is set
     and input `ready` stays low until the ARM commits a new SID (new epoch) and clears the halt. The jumping
     TIME_HIGH is held and becomes the first word of the new epoch, so no word is lost.
   This bounds the number of empty packets one TIME_HIGH can create by `ceil(MAX_GAP_US / T_us)`. Without it, a
   jump in bit 27 alone would create about 8.4e6 empty packets *(arith.)*, each costing a full tag, and would
   run through the 2^20-packet epoch limit before the ARM could react. The rule is specified first in
   `neuro.packet.packetize(..., max_gap_us, jump_mode)`.

### 2.5 Equality used by all round-trip tests

Two streams are *event-equal* when `neuro.evt2.decode()` gives the same list of (t, type, payload) for every
non-TIME_HIGH word. Extra TIME_HIGH words that do not change t are framing and do not count. The RTL and the model
are compared **bit-exactly on the output words**. Sender input and receiver output are compared by event
equality, over the words the sender did not drop (§2.4).

---

## 3. Packetisation

### 3.1 Time grid

- Packet duration `T_us` is a register, **a multiple of 64 µs, default 1024 µs** (16 buckets, about 1 ms), range
  64 to 65 472.
  - Why a multiple of 64: a packet boundary then always falls on a bucket boundary. So (a) only TIME_HIGH words
    close packets, (b) every non-empty packet starts with a TIME_HIGH word and is self-decodable, and (c) the V3
    timestamp XOR (§4.5) never moves an event across a packet boundary.
- `t_origin = 64 · TH_first`, where TH_first is the first accepted TIME_HIGH of the epoch.
- Packet k of an epoch covers t ∈ [t_origin + k·T, t_origin + (k+1)·T). Its counter is `ctr = ctr0 + k`, where
  `ctr0` comes from the `CTR0` shadow register (normally 0 for a new epoch).

### 3.2 Closing rule

- The open packet closes when a TIME_HIGH with `64·value ≥ t_start + T` arrives. Packets in between that hold no
  words are emitted as **empty packets** (header + trailer + tag, payload of 0 words, padded if PAD is on,
  §5.2), so the counter never skips. The arriving TIME_HIGH becomes the first payload word of its packet.
- Empty packets created by such a skip are known to be empty when they are created. They carry
  `needs_tables = False` (§6.3): no table fill is done for them.
- `CTRL.FLUSH` closes the open packet and then emits **one empty packet with the FINAL flag** (§3.3), whose
  t_start is the next grid point. The FINAL packet marks the authenticated end of the stream.
- At an epoch change (commit with a new SID, §6.7), the last packet of the old epoch carries FINAL and the first
  packet of the new epoch carries FIRST.

### 3.3 Packet layout on the wire

A packet is a byte string. On AXI-Stream, word j carries bytes 4j..4j+3, with byte 4j in tdata[7:0]. So an EVT
word w in the payload appears on AXI exactly as w. `tlast` is set on the last tag word.

```
V0-V3:  packet = header (48 B) || payload (4·n_words B) || trailer || tag (16 B)
        trailer = [bitmap (4·ceil(n_cd/32) B), only if PAD] || n_words (4 B) || n_cd (4 B) || rsvd (4 B)
V4:     packet = header (48 B) || C || tag (16 B),  C || tag = ascon.encrypt(K_aead, make_nonce(sid, ctr, 0),
                                                              AD = header, P = payload || trailer)
```

The fixed trailer fields are **last**, so a receiver finds them at a fixed offset from the end and the parse is
unique (§3.5 step 6). There is one 16-byte tag per packet at every level.

**Header (48 bytes, integer fields big-endian, as paper 1's AD prefix).** The sender knows every field when the
packet opens.

| Off | Size | Field | Value |
|---|---|---|---|
| 0 | 4 | magic | ASCII `NVE1` (cannot be confused with paper 1's `SJV1`) |
| 4 | 1 | version | 1 (contract n1) |
| 5 | 1 | level | 0..4 (V0..V4) |
| 6 | 1 | flags | bit0 PAD (§5), bit1 FIRST (first packet of the epoch), bit2 FINAL (last packet of the epoch or of the stream), bits 7..3 = 0 |
| 7 | 1 | ts_bits b | 0 at V0-V2 and V4; 1..6 at V3 (default 6); exactly 6 when PAD = 1 (§5.3) |
| 8 | 8 | session_id | cam_id[63:48] ‖ boot_id[47:16] ‖ epoch[15:0] (§3.4) |
| 16 | 8 | packet_ctr | 63-bit counter, bit 63 = 0 |
| 24 | 8 | t_start | µs, 34 bits used, upper bits 0 |
| 32 | 2 | W | |
| 34 | 2 | H | |
| 36 | 2 | T_us | |
| 38 | 1 | rounds r | 8 (receiver rejects anything else in n1) |
| 39 | 1 | pad_policy | 0 none, 1 floor, 2 ladder (§5); 0 when PAD = 0 |
| 40 | 8 | link | if FIRST: last ctr of the previous epoch of the same boot, or 2^64 − 1 if there is none; otherwise: ctr0 of this epoch |

**Trailer, big-endian.** Its fields are known only at packet end. The header is streamed out before the
payload, and hardware cannot hold a 1 ms packet back (up to 102 400 words at 1 event/clock *(arith.)*).

| Field | Size | Meaning |
|---|---|---|
| bitmap | 4·ceil(n_cd/32), only if PAD | dummy bitmap, masked (§5.3) |
| n_words | 4 | payload words |
| n_cd | 4 | CD words in the payload, dummies included |
| rsvd | 4 | 0; a receiver rejects any other value as `malformed` |

**Tag** (16 bytes, Ascon byte order, V0-V3) = `ascon.mac(K_tag, make_nonce(sid, ctr, 1), header ‖ payload ‖ trailer)`.
This is the same primitive as paper 1's frame tag (AD = data, empty message) and the same order,
encrypt-then-MAC: the tag covers the payload *after* protection.

**Transport.** Each packet travels as one `link.wire` message of its own type, fragmented by
`link.wire.fragment` (1200-byte fragments). A packet at 1 word/clk and T = 1024 µs can be about 410 KB
*(arith.)*, above the UDP datagram limit. One lost fragment loses the packet, which the receiver then reports as
`gap`. N7 and N10 count fragment loss (from `link.wire.Reassembler`) separately from `gap`, so network loss and
deletion are not mixed up.

### 3.4 Keys, nonces and domain separation

**Primitive.** `kdf(key, label, ctx)` is `link.keys.kdf` unchanged = `ascon.mac(key, make_nonce(0, ctx, 1),
label)`. Session id 0 is reserved for the KDF, so a KDF nonce never equals a packet nonce. Paper 1's nonce is
reused unchanged: `make_nonce(sid, ctr, purpose)` = sid (8 B LE) ‖ (ctr << 1 | purpose) (8 B LE). It has only one
purpose bit, so **domain separation uses separate subkeys**, and **every KDF call under a given key uses its own
ctx**, so no (key, nonce) pair is used for two different inputs. All of this lives in `neuro/keys.py`; paper-1
files are not edited.

```
C62       = 1 << 62
base      = cam_id << 32 | boot_id           # 48 bits; cam_id != 0, so base != 0
K_ev[0]   = kdf(master_boot, "nv1-events",  C62 | base)
K_ev[e]   = kdf(K_ev[e-1],   "nv1-ratchet", e)                  # e = 1 .. 0xFFFF, one-way
K_x       = kdf(K_ev[e],     "nv1-" + x,    C62 | i_x)           # x: tag=1, pol=2, perm=3, dum=4, aead=5
sid       = base << 16 | e                    # = link.keys.session_id(base, e)
```

KDF ctx table (one row per key; the ctx values under each key are pairwise distinct):

| Key | Label | ctx | Other ctx used under the same key |
|---|---|---|---|
| master_boot | `nv1-events` | 2^62 + base (2^62+1 .. 2^62+2^48−1) | paper 1: `video`, `feedback` at ctx 0 (paper 1's own calls; see §9.3 item 8) |
| K_ev[e−1] | `nv1-ratchet` | e (1 .. 0xFFFF) | subkeys of epoch e−1 at 2^62 + 1..5 |
| K_ev[e] | `nv1-tag`, `-pol`, `-perm`, `-dum`, `-aead` | 2^62 + 1, 2, 3, 4, 5 | ratchet to e+1 at ctx e+1 ≤ 0xFFFF |

Packet-level use of the subkeys (sid ≠ 0, so these nonces never meet the KDF nonces):

| Subkey | Nonce | Use | Mode |
|---|---|---|---|
| K_tag | (sid, ctr, 1) | packet tag | `ascon.mac` (AD only) |
| K_pol | (sid, ctr, 0) | V1/V3 XOR bits | `ascon.Keystream` |
| K_perm | (sid, ctr, 0) | V2/V3 round tables | `ascon.Keystream` |
| K_dum | (sid, ctr, 0) | dummy-event content, then the dummy-bitmap mask from the **same** stream (§5.3) | `ascon.Keystream` |
| K_aead | (sid, ctr, 0) | V4 | `ascon.encrypt` |

- No subkey is used both as a keystream and as a MAC with AD (repo_crypto §3.7). Nonce purpose 1 under K_dum is
  unused.
- Labels start with `nv1-` and the root uses ctx ≥ 2^62, so no key collides with paper 1's keys.

**Profiles (how master_boot and boot_id are obtained).**

| | Deployment profile (`kex`) | Experiment profile (`psk`) |
|---|---|---|
| master_boot | fresh per boot: `kex_respond` on the board, `kex_init/kex_finish` on the receiver (paper 1, `link.keys`) | the pre-shared key K_psk |
| boot_id | first 4 bytes, big-endian, of SHA-256(M1 ‖ M2) of that boot's exchange | 32-bit counter in a file on the SD card, read and incremented at power-up. **If the file is missing, the sender refuses to start** (no random fallback) |
| receiver rule | accepts a (cam_id, boot_id) only for a completed exchange; the master of a finished boot is erased | persists the highest boot_id seen per cam_id; a lower boot_id is `stale`; a higher one is taken as a new boot only after one of its packets verifies (epoch ≤ E_MAX), which closes the old boot with its `gap`/`truncated` notices |
| cam_id | 16 bits, nonzero, unique per receiver | 16 bits, nonzero, **unique per master** (two cameras with one cam_id under one K_psk collide) |
| used by | N7 live tests, N10, the paper's system | N1, N3-N9 offline runs, test vectors |

**Nonce uniqueness argument.** (1) Different boots: in `kex` the master differs; in `psk` the base differs
(boot_id strictly increases) and K_ev[0] is bound to base through its ctx. (2) Different epochs of one boot: the
ratchet gives different keys and sid differs in its low 16 bits. (3) One epoch: ctr strictly increases and has 63
bits; the hardware refuses a counter rewind (§6.7). A restored SD card in `psk` mode replays an old boot_id; the
receiver rejects it as `stale`, but the sender would reuse nonces towards any receiver without that state. That is
why `kex` is the deployment profile.

**Epoch rules (exact).**
- The epoch is a 16-bit value held in ARM RAM for the current boot. It starts at 0 for every new boot_id. It does
  **not** survive a reboot and does not need to, because a reboot changes boot_id (and, in `kex`, the master).
- It advances by one on exactly these events: (a) an explicit rekey by the ARM; (b) every 2^20 packets (about
  18 min at T = 1024 µs *(arith.)*, a policy default); (c) the 34-bit timestamp rollover; (d) a jump halt
  (§2.4 rule 6).
- **Epoch 0xFFFF is the last.** The sender then stops and needs a new boot_id (new exchange in `kex`) before it
  continues. The hardware enforces this: a commit with the same base and an epoch not above the active one gives
  `ERR_CFG` (§6.7), so 0xFFFF → next cannot wrap. 2^16 epochs of 2^20 packets last about 2.2 years of
  continuous use *(arith.)*.
- The ARM computes subkeys at each epoch change (`neuro.keys.subkeys`) and writes them, with the new SID, into
  the shadow registers. They take effect at the packet chosen by `COMMIT_AT` (§6.7).

### 3.5 Receiver checks, in this order (`neuro.receiver.Decryptor.accept`)

Steps 1-4 read only the header and the length and **change no state**. State changes only in step 7, after the
tag has verified.

1. **Framing.** Length ≥ 48 + 12 + 16, magic, version, `rounds == 8`, reserved flag bits 0, upper t_start
   bits 0; otherwise `malformed`.
2. **Session and epoch.** cam_id and boot_id known and accepted under the profile rules of §3.4; otherwise
   `stale`. Epoch below the current one: `stale` (old keys are erased). Epoch above `current + E_MAX`
   (E_MAX = 2): `policy`, without computing any key. Only then is the epoch key computed with
   `EventRatchet.peek(epoch)`, which costs at most E_MAX KDF calls.
3. **Profile and plausibility (header only).**
   - (level, ts_bits, PAD, pad_policy) is in the receiver profile's allowed set, checked exactly; W, H, T_us
     equal the session's; otherwise `policy`. Default profile: `{(V3, 6, *, *)}` or `{(V4, 0, *, *)}`.
   - Length L ≤ L_max = 48 + 4·W_max + 4·ceil(min(W_max, MAX_CD_PAD)/32)·PAD + 12 + 16, with
     W_max = R_max·T_us·(2 if PAD else 1) + (T_us/64)·(1 + PAD_MIN·PAD) and R_max (words per µs, all word
     types) from the profile; otherwise `malformed`.
   - If the epoch's ctr0 and t_origin are already pinned: non-FIRST packets must have `link == ctr0` and every
     packet must satisfy `t_start == t_origin + (ctr − ctr0)·T_us`; otherwise `policy`.
4. **Replay (read-only).** `NeuroWindow.would_accept(ctr)`: true iff ctr > top, or ctr is inside the 64-entry
   window and not yet marked. Otherwise `replay`. This step has no side effects.
5. **Tag.** Verify in constant time (V0-V3) or AEAD-decrypt (V4); on failure `forged`. This is the only MAC per
   datagram.
6. **Structure (after the tag, so the parse is authenticated).** V0-V3: read n_words, n_cd, rsvd at
   L − 16 − 12; V4: at the end of the decrypted P. Require rsvd = 0 and
   48 + 4·n_words + 4·ceil(n_cd/32)·PAD + 12 + 16 == L (V0-V3; for V4 the same sum on |P|); otherwise
   `malformed`. (The fixed fields can also be read before the tag at V0-V3 as a cheap filter; the result is only
   trusted after step 5.)
7. **Commit (state changes happen only here).**
   - If epoch > current: report the old epoch's missing counters as `gap` (up to `link` if FIRST is set),
     report `truncated` for the old epoch if its FINAL packet was not seen, then `EventRatchet.forward(epoch)`,
     erase the old key and start a new window.
   - `NeuroWindow.mark(ctr)`; pin ctr0 (= ctr if FIRST, else link) and t_origin = t_start − (ctr − ctr0)·T_us on
     the first authenticated packet of the epoch; remember FINAL.
   - Strip dummies and check pad conformance (§5.3; a non-conforming padding is `policy`), decrypt (§4) and
     deliver in counter order.

**Notices** (not per-packet results): `gap` (a counter left the window unmarked, or was missing at an epoch
switch or at close), `truncated` (an epoch or the stream closed without an authenticated FINAL), `stall` (no
authenticated packet for more than `STALL_K · T_us` of wall time, default STALL_K = 100, i.e. about 0.1 s;
returned by `Decryptor.tick(now)`). A genuine packet delayed beyond the window is indistinguishable from a replay
and is reported as `replay`; its counter was already reported as `gap`.

---

## 4. Protection levels

### 4.1 Summary

| Level | x, y | p (bit 28) | ts[5:0] (bits 27..22) | TIME_HIGH, other words | Keystream per CD word | Payload readable as EVT 2.0 |
|---|---|---|---|---|---|---|
| V0 | clear | clear | clear | clear | 0 | yes (plain + tag) |
| V1 | clear | XOR k0 | clear | clear | 1 bit (K_pol) | yes |
| V2 | permuted P_ctr | clear | clear | clear | 0 (+ tables from K_perm) | yes |
| V3 | permuted P_ctr | XOR k0 | XOR k1..kb | clear | 1 + b bits (K_pol) + tables | yes; ts non-monotone inside a bucket |
| V4 | AEAD | AEAD | AEAD | AEAD | n/a | no (ciphertext) |

- All levels carry the same tag and the same header.
- The levels are **not ordered by protection**: V2 does not include V1 (V2 leaves polarity in the clear). This is
  why the receiver checks an exact profile, not a minimum level (§3.5).
- **V1 hides polarity only.** Positions and timestamps are in the clear, and a plain event-count image shows the
  scene (§9.2 item 1).
- Order of operations inside a CD word does not matter: the permutation acts on (x, y), the XOR on p and ts, and
  these fields do not overlap. The hardware therefore applies the XOR before the permutation (§6.1) and the model
  may apply them in either order.

### 4.2 Keystream bit order (V1, V3)

`ks = ascon.Keystream(K_pol, make_nonce(sid, ctr, 0))` starts again in every packet. Only real CD words consume
keystream, in payload order; dummies consume none (§5). Per real CD word, `k = ks.take(1 + b)` (bit 0 = first bit
handed out, paper 1's LSB-first contract), and:

```
w ^= ((k & 1) << 28) | (((k >> 1) & ((1 << b) - 1)) << 22)        # V1: b = 0 ; V3: b = ts_bits
```

So keystream bit 0 goes to the polarity and keystream bit 1+i goes to ts[i] (i = 0..b−1). Flipping bit 28 turns
CD_OFF and CD_ON into each other, and the word stays a valid CD word. XOR is an involution, so the receiver
applies the same function. One K_pol stream per packet (no per-lane sub-streams in n1, §6.4).

### 4.3 V2 position permutation: mixed-radix table Feistel

**Choice.** Binary-domain cycle walking is dropped. We use a Feistel network on Z_W × Z_H with modular addition:
Black-Rogaway "Method 3" with a = W, b = H, so Δ = ab − k = 0 [`black2002ctrsa`]. It is a permutation of exactly
the W·H pixel addresses. It **never walks**, has a fixed latency and accepts one event per clock, so the
permutation itself **needs no stall path**. The risk raised before this work began (variable-latency cycle
walking) is therefore removed by construction.

The data behind the choice (script (a), table "Cycle walking"): for a binary domain the expected number of cipher
calls is 2.914 for 346 x 260, 3.543 for 34 x 34 and 2.276 for 1280 x 720 with 11+10-bit fields. P(more than 4
calls) is between 0.0987 and 0.266. Mixed radix gives exactly 1 call for every sensor.

#### 4.3.1 Tables

r = 8 rounds and tables T_0..T_7:

| Round j | Index | Entries | Value range | Updates |
|---|---|---|---|---|
| even (0, 2, 4, 6) | y ∈ Z_H | H | Z_W | x |
| odd (1, 3, 5, 7) | x ∈ Z_W | W | Z_H | y |

Keystream bits per packet = 16 · 4 · (W + H). For 1280 x 720 that is 128 000 bits (script (a)).

#### 4.3.2 Table derivation (per packet that needs tables)

```
ks = ascon.Keystream(K_perm, make_nonce(sid, ctr, 0))
for j in 0..7:                       # T_0 first
    M, n = (W, H) if j even else (H, W)
    for i in 0..n-1:                 # index order
        r16 = ks.take(16)            # LSB-first, paper-1 order
        T_j[i] = (r16 * M) >> 16     # multiply-shift reduction into Z_M
```

One K_perm stream per packet; the tables are not split across generators in n1 (§6.3). The multiply-shift bias
(total variation from uniform per entry) is at most 3.13e-3 for W = 1280, and 0 when M is a power of two
(script (a)). Exact-width draws are not used: their modulo bias is larger on mixed radix.

#### 4.3.3 Encryption (sender) and exact inverse (receiver)

```
P_ctr(x, y):  for j in 0..7:   if j even: x = (x + T_j[y]) mod W      else: y = (y + T_j[x]) mod H
P_ctr^-1:     for j in 7..0:   if j even: x = (x - T_j[y]) mod W      else: y = (y - T_j[x]) mod H
```

- Each round adds a table value that depends only on the coordinate the round does not change, so each round is
  a bijection of Z_W × Z_H. The inverse undoes the rounds in reverse order with the same tables. This is BR's
  `fe[r, a, b]` for even r, written without the swap.
- In hardware, each "mod" is one compare-and-subtract, because both operands are below the modulus, so
  a + b < 2M. In the inverse it is a borrow-and-add.
- For W, H powers of two this is a plain binary Feistel.

#### 4.3.4 Cycle-walking rule

**Cycle walking is not used in contract n1.** The domain is exactly Z_W × Z_H, so every output is already
in range. For comparison only (ablation N2b), the binary variant is specified as:

- encrypt (x, y) packed into the smallest balanced binary domain;
- repeat while the result is outside W × H, at most K = 4 times, then recirculate.

It is implemented as `nv_feistel_walk.v` only if N2b is run. It is not part of the IP.

#### 4.3.5 Round count

- r = 4 is ruled out. The Durak-Vaudenay 4-round known-plaintext table recovery [`durak2017crypto`†] needs
  N^1.5 (N/2)^(1/6) pairs for a balanced branch of size N. With N = √(W·H) that is 8.32e4 pairs, or 9.0 % of the
  codebook, for 1280 x 720, and 27.5 % for 34 x 34 (script (a)). **For W ≠ H this is the balanced-branch formula
  applied with N = √(WH), an approximation for the unbalanced domain Z_W × Z_H** (the paper itself is verified
  at abstract level only, †). N8 measures r = 4 recovery empirically on the unbalanced domain.
- At r = 8 the generic attacks of [`durak2018acns`†] cost on the order of N^{O(N^{5/6})} time, with N ≈ 10^3. FF1
  uses 10 rounds [`nist2025sp80038gr1`].
- r = 8 costs 2 more tables than r = 6, a margin we take.

#### 4.3.6 Security statement (write exactly this, not more)

1. Under the assumption that the Ascon-AEAD128 keystream is a PRF of (key, nonce), the tables of different
   packets are independent. Recovering one packet's permutation reveals nothing about any other packet or about
   the key. This holds only if nonces never repeat (§3.4).
2. Inside one packet, provable Feistel bounds are vacuous at this domain size. The Black-Rogaway Theorem 2 bound
   reaches advantage 1/2 at q = 20.2 queries for 1280 x 720 (script (a)). FF1 is in the same position, and NIST's
   own small-domain argument rests on the data complexity of attacks [`nist2025sp80038gr1`]. Our argument rests on
   the best known attacks (§4.3.5) plus freshness per packet. **A successful attack recovers the layout of one
   packet; packets must be attacked independently, at the cost stated in §4.3.5 each.** A static scene with hot
   pixels or a known background gives fresh known plaintext in every packet, so the total loss grows linearly
   with the attacker's effort. N8 measures how much known plaintext real packets actually contain.
3. V2 is **confidentiality of layout, not IND-CPA**. Inside a packet it leaks:
   - the event count and the count per bucket;
   - per-pixel multiplicity (equal inputs give equal outputs);
   - each pixel's time sequence, and with it the **co-activation structure** of neighbouring pixels: a moving
     edge fires adjacent pixels at nearby times, so an attacker can build a graph over the permuted addresses
     and embed it in 2D without the key (N4b measures this and sets the T default);
   - polarity (V2 only).
   N4b, N5 and N8 measure these leaks.
4. The statement assumes W ≥ 16 and H ≥ 16 (§2.3).
5. FF1 itself is not used. Ascon is not an approved CIPH for FF1, and 1280 x 720 = 921 600 < 10^6 would also fail
   the Rev. 1 domain minimum [`nist2025sp80038gr1`]. Swap-or-not [`hoang2012crypto`] is the provable alternative:
   164 to 516 rounds (script (a)), too many for one event per clock. Cite it as such.

### 4.4 Optional ablation: true random permutation for small sensors

For 34 x 34 and 128 x 128 a Knuth shuffle into a table is feasible:
- 34 x 34: 4 RAMB18, 2.2 % of a 1 ms packet;
- 128 x 128: 28 RAMB18, 34.6 %;
- 346 x 260: 176 RAMB18, 208.7 % of a 1 ms packet, so not feasible (script (a)).

Model only (`neuro.feistel.shuffle_table`). It is the "ideal permutation" control in N3, N4b and N8: a leak that
also appears under the shuffle is a leak of V2 in principle, not of the Feistel.

### 4.5 What V3 does to timestamps

- Only ts[5:0], inside each CD word, is changed. TIME_HIGH words stay in the clear and are authenticated. Every
  event therefore stays inside its original 64 µs bucket and inside its packet, because T is a multiple of 64.
- Coarse order (bucket order) is kept. Order inside a bucket becomes **non-monotone**, with errors up to
  2^b − 1 µs. The EVT 2.0 page states no monotonicity rule [`prophesee_evt2`], so the stream stays decodable.
  Whether OpenEB, Tonic, expelliarmus and our E2VID loader tolerate it is **unverified** and is tested in N8-R.
- The receiver decrypts in arrival order. The keystream index is the ordinal of the real CD word, so the
  ciphertext must not be re-sorted before decryption.
- Privacy value is small. Anything that bins time more coarsely than 64 µs is unchanged (voxel grids, event
  frames). On DVS Gesture (ms precision) the field is almost always 0 before encryption. V3 is kept as an
  ablation that shows this, and it is the only event-format level that allows padding (§5).

### 4.6 V4

Payload and trailer are encrypted with Ascon-AEAD128 under (K_aead, nonce(sid, ctr, 0)) with AD = header (§3.3).
V4 output is not an event stream. It is the "full confidentiality" baseline for N3, N4, N9 and N11.

---

## 5. Dummy-event padding (optional, PAD flag)

### 5.1 Allowed configurations

Padding is allowed at **V3 with ts_bits = 6, and at V4**; the sender (`Encryptor`, and `ERR_CFG` at commit in
hardware) and the receiver profile reject PAD in any other configuration.
- In V0-V2 the clear ts[5:0] and the clear positions make dummies stand out: dummies sit at the end of each
  bucket (§5.2), so clear dummy timestamps would break the monotone order inside the bucket, and in V0/V1 clear
  positions show that dummies are uniform noise.
- At V3 with b < 6, real words keep ts[5:b] in the clear and these bits increase inside the bucket, while dummy
  ts bits are random, so dummies would stand out (on DVS Gesture, where real ts = 0, a dummy would be any word
  with a nonzero upper bit). Hence b = 6 is required.

### 5.2 Policy (per 64 µs bucket, so per-bucket rate is shaped; the per-bucket count is visible to a passive attacker)

- `pad_policy = 1` (floor): pad every bucket of the packet to at least `PAD_MIN` CD words.
- `pad_policy = 2` (ladder): pad each bucket to the smallest `PAD_MIN · 2^k ≥ n_real` (k ≥ 0). Above `PAD_CAP` no
  padding is added.
- **What each policy leaks:** the ladder leaks ⌈log2(PAD_CAP/PAD_MIN)⌉ + 1 classes for n_real ≤ PAD_CAP and the
  exact count above PAD_CAP; the floor leaks the exact count above PAD_MIN. The busy buckets (motion, gestures)
  are the informative ones, so N5 reports the fraction of buckets above the cap (or floor) for each dataset and
  the mutual information with class for each policy.
- With padding on, every bucket in the packet gets a TIME_HIGH word, inserted if absent, and ≥ PAD_MIN CD words.
  So empty buckets become indistinguishable from quiet ones.
- **Empty packets are padded like any other packet** (including the empty packets of a time gap, §3.2, and the
  FINAL packet), because otherwise silence is visible. Vector case "time gap with PAD floor at V3" (§7.2).
- Dummies are appended **at the end of their bucket**, after its real words. The bucket's real count is known
  then, and no buffering of real events is needed. This placement leaks: in a bucket the real words are a
  prefix and the dummies a suffix. The leak is stated (§5.4, §9.2) and measured (N5); keyed interleaving is
  an open question (§9.3 item 3).
- **Overflow.** A PAD packet holds at most `MAX_CD_PAD` CD words (parameter, default 131 072 = 8 RAMB18 of
  bitmap *(arith.)*). When it is reached, further real CD words of that packet are dropped and counted
  (`ERR_PADOVF`), and no further dummies are added in that packet. Non-CD words still pass. Specified in
  `neuro.pad.pad_packet` first.

### 5.3 Dummy content and authentic removal

- **One K_dum stream per packet:** `ks_d = Keystream(K_dum, make_nonce(sid, ctr, 0))`, consumed strictly in
  payload order, LSB-first. For the i-th CD word of the payload (real or dummy), in order:
  1. take 1 bit `m_i` (the mask bit of bitmap bit i);
  2. if the word is a dummy, take 39 more bits for its content (below).
  After the last CD word, take `32·ceil(n_cd/32) − n_cd` further mask bits for the zero padding of the bitmap.
- **Dummy word:** CD word with x = (r16·W) >> 16, y = (r16'·H) >> 16, p = 1 bit, ts[5:0] = 6 bits, drawn in this
  order (16 + 16 + 1 + 6 = 39 bits). Dummies are output words as they are: they do not pass through the
  permutation or the XOR and consume no K_pol bits.
- **Bitmap:** bit i (LSB-first in bytes, bytes in order) = d_i XOR m_i, where d_i = 1 if the i-th CD word of the
  payload is a dummy; the zero padding bits are masked the same way. The bitmap is part of the trailer, so the
  tag covers it. So the mask continues the dummy stream: one generator, no second nonce, and every bit position
  is fixed by the payload order alone.
- **Receiver:** verify the tag; regenerate `ks_d` and walk the payload: for CD word i take m_i, compute
  d_i = bitmap_i XOR m_i, and if d_i = 1 take 39 bits and check that the word equals the regenerated dummy
  (otherwise `policy`); drop the dummies; check per bucket that the CD count equals `bucket_target(n_real,
  policy)` (pad conformance, otherwise `policy`); then decrypt the remaining CD words with K_pol keystream
  indices 0, 1, 2, ... The bitmap costs 1 bit per CD word, 3.125 % of payload *(arith.)*.
- **V4:** the same payload and trailer (with bitmap) form the AEAD plaintext.

### 5.4 Known weaknesses (stated in the paper, measured in N5)

1. **Multiplicity.** Dummies are uniform over Z_W × Z_H and each one is a singleton. Real events under V3 keep
   their per-pixel multiplicity inside a packet.
2. **Position in bucket.** Dummies form the suffix of each bucket. In a floor-policy bucket of exactly PAD_MIN
   words the attacker knows the real words are a prefix; with multiplicity (real repeats tend to come early,
   singletons late) the split point can be estimated.
N5's dummy distinguisher therefore reports AUC for three feature sets: multiplicity only, position in bucket
only, and both.

---

## 6. Hardware architecture (PYNQ-Z2, xc7z020clg400-1, 100 MHz)

### 6.1 Top level `nv_top` (Golden model: software/neuro/sender.py :: Encryptor.push())

Every unit that can stall sits **in front of** the fixed-latency section. Header, payload, trailer and bitmap
words travel **in-band** through one ordered path.

```
AXI-S in (32b EVT words, DMA MM2S)
  -> nv_packetizer  (header words, payload words, EOP marker; kind + bypass flags)
  -> nv_trailer     (PAD: inserts dummies at bucket end, bitmap; always: emits bitmap + fixed trailer words at EOP)
  -> nv_xor         (K_pol keystream_gen #1; only real CD words; stalls on ks_avail)
  -> skid_buf
  -> nv_feistel     (r = 8, fixed latency LAT, no stage enable; bypass words ride through unchanged)
  -> nv_word_fifo   (512 x 35: word + kind[1:0] + last)
  -> nv_tag32       (nv_ascon_core_u, MAC or ENC; one-block look-ahead)
  -> nv_out_mux     (forwards words, appends 4 tag words after `last`, sets tlast) -> AXI-S out (DMA S2MM)

nv_table_gen (keystream_gen #2, K_perm) -> nv_table_bank (16 x nv_sdp_ram) -> nv_feistel read ports
AXI-Lite (GP0) -> nv_axil_regs (shadow set, commit, counters)
```

- **Feistel gate:** a credit counter C starts at the FIFO depth; it is decremented when nv_feistel accepts a word
  and incremented when nv_tag32 pops a word from the FIFO. nv_feistel accepts iff C > 0. So no word that enters
  the fixed-latency section can find the FIFO full, and no word is lost or overwritten.
- Field order does not matter (§4.1), and dummies and non-CD words bypass both the XOR and the permutation
  (bypass flag), so this order gives the same output words as the model.
- The K_pol generator for packet k+1 is restarted when packet k's last real CD word has passed nv_xor; this is
  upstream of the Feistel, so the restart (about 15 clk with `ks_avail = 0`) is a stall in front of the
  fixed-latency section, counted in `KS_WAIT`.
- All streams use valid/ready, and data is held while `valid && !ready`.
- `default_nettype none`, synchronous active-high `rst`, Verilog-2001 for Icarus 12 and Vivado.
- Reused unchanged from `hardware/rtl/`: `ascon_round.v`, `ascon_aead128_core.v` (U = 1 reference),
  `keystream_gen.v` and `skid_buf.v`. Paper-1 files are **not edited**.

### 6.2 Modules (all new files in `hardware/rtl/neuro/`, prefix `nv_` to avoid name clashes)

| Module | Golden model | Function |
|---|---|---|
| `nv_packetizer.v` | `neuro.packet :: packetize()`, `PacketHeader.pack()` | EVT 2.0 parser. Applies the §2.4 rules (including the jump rule), the bucket and packet FSM of §3.2 (empty packets, FINAL on FLUSH, FIRST/FINAL at a commit), emits the 12 header words in-band, then payload words, then an EOP marker. Tags each word with `kind`, `bypass` (= not a CD word), `cd_idx`, `bank`. Holds `needs_tables` per packet and requests tables from nv_table_gen. Latches the shadow set at the commit packet (§6.7) |
| `nv_trailer.v` (parameter `PAD`) | `neuro.pad :: pad_packet()`, `dummy_word()`; `neuro.packet :: Trailer.pack()` | Counts n_words and n_cd. With PAD: at the end of each bucket inserts `need − n_real` dummy words (bypass = 1) from keystream_gen #3 (K_dum; 1 mask bit per CD word, plus 39 content bits per dummy in 3 takes, §5.3), stalls upstream while doing so (and for about 15 clk at each packet start while K_dum restarts), records masked bitmap bits in a BRAM of MAX_CD_PAD bits, applies ERR_PADOVF, and at EOP takes the padding mask bits and emits the masked bitmap. Always: at EOP emits n_words, n_cd, rsvd and the `last` flag. Without PAD it is a counter and a 3-word emitter |
| `nv_xor.v` | `neuro.levels :: xor_fields()`; stage view `neuro.hw :: xor_word()` | `keystream_gen` #1 with K_pol. Takes `1 + b` bits for each real CD word at V1/V3 (`ks_n` from a register, paper-1 bug #38). Stalls while `ks_avail < 1 + b`. Restarts per packet |
| `nv_feistel.v` + `nv_feistel_round.v` | `neuro.feistel :: permute()`; stage view `neuro.hw :: feistel_round()` | 8 rounds × 2 clk: read address, then add plus conditional subtract. Bypass words ride through unchanged, so word order is kept. Bank select travels with each word. **Fixed latency LAT = 16 clk** (24 with BRAM output registers, parameter `BRAM_REG`). No stage enable |
| `nv_table_gen.v` | `neuro.feistel :: make_tables()`; `neuro.hw :: table_fill_entries()` | `keystream_gen` #2 with K_perm and nonce(sid, ctr, 0) for the next packet with `needs_tables`. Takes 16 bits per entry, computes `(r16·M) >> 16` (one 16 × 11 multiplier) and writes the free bank in table order. Aborts and restarts if the target packet changes (time jump, §3.2); the lost clocks count in `TABLE_WAIT` |
| `nv_table_bank.v` | n/a (storage) | 16 instances of `nv_sdp_ram #(DEPTH, WIDTH = 11, DO_REG = BRAM_REG)` in a generate loop (2 banks × 8 tables), written with the Vivado simple-dual-port template (one write port for the fill, one registered read port for round j). Never one shared memory array (Vivado could not give 8 independent read ports). Depth MAXH for even tables, MAXW for odd |
| `nv_sdp_ram.v` | n/a | parameterised SDP RAM template |
| `nv_ascon_core_u.v` | `model.ascon :: encrypt()` | Ascon-AEAD128 with **U rounds per clock** (U ∈ {1, 2, 4}, which divide both 12 and 8), built from U `ascon_round` instances. U = 1 has the same timing as the paper-1 core. Plan of record U = 2, stretch U = 4 (§9.1) |
| `nv_tag32.v` | `model.ascon :: mac()` (MAC), `ascon.encrypt()` (ENC, V4); stage view `neuro.hw :: tag_input()` | 32-bit block collector over one ordered stream (header words = AD; at V0-V3 payload and trailer are AD too; at V4 they are PT). **One-block look-ahead:** a full 16-byte block is released only when the next word of the same type arrives; at the end of a type it is released as a full block followed by an empty `blk_last` block (the core requires `blk_bytes < 16` on the last block of each type). **ENC backpressure:** a PT block is offered (`blk_valid`) only when the 4-word ciphertext holding register is empty and the output path has ≥ 4 word credits, because the core's `ct_valid` is a one-clock pulse with no ready. The tag is latched on `tag_valid` and held until nv_out_mux has sent all 4 tag words. A new packet's init waits for the previous tag; nv_word_fifo absorbs the gap |
| `nv_word_fifo.v` | n/a | BRAM FIFO, 512 × 35 b (word + kind[1:0] ∈ {hdr, payload, trailer/bitmap} + last), one RAMB18 in 512 × 36 mode |
| `nv_out_mux.v` | `neuro.packet :: Packet.to_words()`; `neuro.hw :: out_words()` | Forwards the ordered stream (MAC mode) or the ciphertext words (ENC mode), inserts the 4 tag words after `last`, sets `tlast` on the last tag word |
| `nv_axil_regs.v` | n/a | §6.7 |
| `nv_feistel_walk.v` | `neuro.feistel :: permute_walk()` | **Ablation N2b only**: binary Feistel with a K = 4 unrolled walk, a "first in domain" select and a recirculate/stall path |

### 6.3 Throughput (what is claimed, and the limits)

- **Feistel and XOR.** One CD word per clock, fixed latency LAT through nv_feistel. Tested in cocotb: each word
  leaves nv_feistel exactly LAT clk after it enters when the FIFO has credit (§7.2).
- **Keystream (K_pol).** V3 needs 1 + 6 = 7 bits per word. One `keystream_gen` sustains 128 bits per 9 clk =
  14.2 bits/clk (measured, repo_crypto §2.1), enough for L = 1. Per-packet restart: about 15 clk *(from RTL
  reading)*, i.e. at most 1.5 % of a 1024-clk packet at full rate *(arith.)*, counted in `KS_WAIT`.
- **Table fill.** Only for packets with `needs_tables` (level ∈ {V2, V3} and not a skipped empty packet). The
  fill for packet k+1 runs while packet k is processed. It takes 9 012 clk for 1280 x 720 and 2 739 clk for
  346 x 260 (script (a)): 9.0 % and 2.7 % of a 1024 µs packet **when events arrive in real time**. In replay at
  maximum rate (N10) a packet with n CD words takes n clk, so the sustained replay rate is
  **min(1, tag rate, n_cd_per_packet / fill_clk(W, H)) words per clock**, much less than 1 for sparse packets.
  N9 (cycle model) and N10 report it per sensor and T. One K_perm generator in n1; a second one would need a
  model definition of how two streams split the tables and is deferred (Appendix A).
- **Dummies (PAD).** Every CD word takes 1 mask bit (1 bit/clk at full rate, within the 14.2 bits/clk supply);
  a dummy takes 1 + 39 = 40 bits, at most 16 bits per take: 3 takes per dummy, so at most
  14.2 / 40 = 0.355 dummies/clk sustained and 1 per 3 clk in a burst *(arith.)*. The x and y multiplies share
  one 16 × 11 multiplier over 2 clk. Dummies stall nv_packetizer (they are upstream of the Feistel). At trailer
  time only the < 32 padding mask bits are taken (§5.3); the K_dum restart at each packet start (about 15 clk)
  is a stall in front of the Feistel.
- **Tag (the bottleneck).** One word per clock means 4 B/clk.
  - U = 1: 16 B / 9 clk = 1.78 B/clk, i.e. 0.44 words/clk (from the measured 9 clk/block).
  - U = 2: 16 B / 5 clk = 0.8 words/clk *(arith.)*. **Plan of record.**
  - U = 4: 16 B / 3 clk = 1.33 words/clk *(arith.)* **if** 4 unrolled rounds close timing at 100 MHz, which is
    doubtful on a -1 part (about 12 LUT levels plus routing). **Stretch goal**, measured in N2.
  - An empty packet costs one full tag, about init 13 + 4 blocks × 9 + p12 ≈ 65 clk at U = 1 *(from RTL
    reading, to be measured in N1)*.
  - The IMX636 peak of 1.06 Geps is out of reach of any 100 MHz single-lane design. The paper claims "sensor
    rate" only for rates below the measured authenticated throughput, which at U = 1 still covers DAVIS346's
    12 MEPS peak (0.12 words/clk at 100 MHz *(arith.)*).
- **End-to-end:** authenticated throughput = min(1, tag rate(U), fill-bound rate, dummy rate) words per clock,
  measured in N2 (simulation) and N10 (board).
- **Bursts.** At U = 1 a full-rate burst fills the 512-word FIFO in about 512 / (1 − 0.44) ≈ 914 clk ≈ 9 µs
  *(arith.)*; after that input `ready` drops. A sensor that cannot be backpressured then loses events. N9's cycle
  model sizes the FIFO from real traces.
- **V4.** Same unit and same rate as the tag.

### 6.4 Lanes study (N2)

- L lanes of Feistel (+ XOR) process consecutive CD words in parallel.
- **V3 at L ≥ 2 is keystream-bound:** L = 2 needs 14 bits/clk against 14.2 supplied (98.6 % utilisation, so every
  restart costs throughput) and L = 4 needs 28 bits/clk *(arith.)*. Per-lane K_pol sub-streams would change the
  contract and are not in n1. So **L = 2 and L = 4 are studied for V0 and V2 only**; V1/V3 builds use L = 1.
- L = 2 needs a second read port per table (true dual port; the fill then needs a time slot). L = 4 duplicates
  the banks.
- The tag stays one serial Ascon stream per packet, because splitting it would change the tag definition. So the
  system rate = min(L, tag rate(U)).
- N2 reports area and Fmax for L ∈ {1, 2, 4} × U ∈ {1, 2, 4}, with the number of K_pol generators per build in
  the table (1 for every n1 build).
- Packet-level interleaving (two full pipelines on alternate packets) would need a one-packet input buffer and is
  not pursued (§9).

### 6.5 Latency

- **Datapath latency** (input word to FIFO): LAT (16-24 clk) + nv_xor + skid_buf, a few tens of clocks, valid
  only while the input rate is below the authenticated throughput. Above it, the FIFO fills and latency grows;
  FIFO occupancy and latency are N2/N10 measurements, not claims.
- **Authenticated latency** is what a verify-then-use receiver sees: about T + tag finalisation. Finalisation is
  roughly the last block + p12 = 25 clk at U = 1 (from RTL reading, repo_crypto §2.4). In total about 1.03 ms at
  T = 1024 µs. N9 measures it.
- Shorter T lowers latency but raises overhead (§6.6, N9). Below about 0.1 ms, table fill limits the rate at
  1280 x 720 (script (a)).

### 6.6 Resource estimate (to be replaced by N2 measurements)

| Item | Count | Basis |
|---|---|---|
| keystream_gen (K_pol, K_perm) | 2 × (949 LUT / 851 FF) | paper-1 post-route, repo_crypto §2.3. One K_pol generator for every n1 build (§6.4) |
| keystream_gen (K_dum, PAD only) | + 1 × the same | same; one generator suffices because the mask continues the dummy stream (§5.3) |
| tag core, U = 1 | about 1 344 LUT / 1 072 FF | paper-1 `tag_unit` incl. core (§2.4). The 32-bit collector replaces the byte collector |
| tag core, U = 2, 4 | unknown | N2. Round logic grows about U-fold; no number is claimed before synthesis |
| table banks, 1280 x 720, r = 8 | 24 RAMB18 (16 for ≤ 640 x 480) | script (a), as 16 `nv_sdp_ram` instances; N2 reports RAMB18 per instance and checks 24/16. xc7z020 has 280 RAMB18 |
| word FIFO | 1 RAMB18 (512 × 36) | |
| dummy bitmap (PAD only) | 8 RAMB18 for MAX_CD_PAD = 131 072 bits *(arith.)* | §5.2 |
| Feistel datapath | 8 × (11-bit adder + compare/subtract + pipeline regs) | no number before N2 |
| DSP48 | 1 (table multiply-shift) + 1 with PAD (time-shared dummy x/y multiply) | |

### 6.7 AXI-Lite register map (draft; copied into `docs/INTERFACES.md` §11 when the RTL is written)

**Shadow set and commit.** {MODE, GEOM, T_US, SID, CTR0, PAD_MIN, PAD_CAP, MAX_GAP_US, all keys} form **one
shadow set**. Writes go to the shadow copy only (reads return the shadow copy). `CTRL.COMMIT` with
`COMMIT_AT = a` makes the shadow set active **for the packet that would have counter a under the active set**:

- Accepted only if a ≥ (counter of the open packet) + 2. Then neither packet a−1 (which must carry FINAL when the
  SID changes) nor packet a's table prefetch (which runs during packet a−1) has started. Otherwise the commit is
  refused: `STATUS.COMMIT_LATE`, `ERR_CFG` += 1, `CFG_CODE` = LATE; the ARM retries with a later a. This rule is
  a function of counters only, so the model reproduces it exactly (`Encryptor.commit(at_ctr, cfg)`).
- While `ENABLE = 0` a commit applies at once (COMMIT_AT is ignored).
- Configuration checks at commit (`ERR_CFG`, `CFG_CODE`): W ≤ MAXW, H ≤ MAXH; W, H ≥ 16 at V2/V3; T_US a
  multiple of 64 in 64..65 472; TS_BITS = 0 except at V3 (1..6); PAD only at V3 with TS_BITS = 6 or at V4;
  PAD built in (VERSION bit 6) if PAD is requested.
- **Counter and SID rules:** with the SID unchanged the counter continues (CTR0 is ignored). With a new SID,
  CTR0 is loaded. A new SID with the same base (SID[63:16]) as `LAST_SID` must have a higher epoch, or the same
  epoch with CTR0 > `LAST_CTR`; otherwise `ERR_CFG` (code REWIND). Epoch 0xFFFF therefore cannot be followed
  under the same base. `LAST_SID` and `LAST_CTR` hold the last emitted (sid, ctr); they are cleared only by
  power-on reset, not by `SOFT_RST`.
- `SOFT_RST` clears `KEYS_VALID`. A new commit (with a SID/CTR0 that passes the rules above) is needed before
  `ENABLE` has any effect.
- With a new SID, packet a−1 carries FINAL and packet a (counter CTR0) carries FIRST with link = a−1 if the base
  equals the previous base, else 2^64 − 1.

| Off | Name | Acc | Bits |
|---|---|---|---|
| 0x00 | VERSION | RO | {8'h4E, 8'h56, 8'h01 (contract n1), build byte = {1'b0, PAD, log2U[1:0], L[3:0]}} |
| 0x04 | CTRL | RW | [0] ENABLE, [1] SOFT_RST (W1P), [2] FLUSH (W1P), [3] COMMIT (W1P), [4] SNAP (W1P: copy all counters into their read registers at once), [5] CLEAR_HALT (W1P) |
| 0x08 | STATUS | RO | [0] BUSY, [1] COMMIT_PENDING, [2] TABLE_READY, [3] OPEN_PACKET, [4] KEYS_VALID, [5] COMMIT_LATE (sticky, cleared by the next accepted commit), [6] JUMP_HALT, [7] CFG_ERR (sticky) |
| 0x0C | MODE | RW shadow | [2:0] LEVEL, [6:4] TS_BITS, [8] PAD, [10:9] PAD_POLICY, [12] JUMP_MODE |
| 0x10 | GEOM | RW shadow | [10:0] W, [26:16] H |
| 0x14 | T_US | RW shadow | multiple of 64 |
| 0x18 / 0x1C | SID_LO / SID_HI | RW shadow | session id |
| 0x20 / 0x24 | CTR0_LO / CTR0_HI | RW shadow | first counter of a new SID |
| 0x28 / 0x2C | PAD_MIN / PAD_CAP | RW shadow | |
| 0x30 | MAX_GAP_US | RW shadow | §2.4 rule 6, default 1 000 000 |
| 0x34 / 0x38 | COMMIT_AT_LO / HI | RW | counter at which the next commit applies |
| 0x3C | CFG_CODE | RO | reason of the last refused commit: 0 none, 1 LATE, 2 GEOM, 3 LEVEL/TS/PAD, 4 T_US, 5 REWIND, 6 NO_KEYS |
| 0x40-0x4C | K_TAG0-3 | WO shadow | KEY0 = bytes 0..3 LE (paper-1 order) |
| 0x50-0x5C | K_POL0-3 | WO shadow | |
| 0x60-0x6C | K_PERM0-3 | WO shadow | |
| 0x70-0x7C | K_DUM0-3 | WO shadow | |
| 0x80-0x8C | K_AEAD0-3 | WO shadow | |
| 0x90 / 0x94 | CUR_CTR_LO / HI | RO | counter of the open packet (active set) |
| 0x98 / 0x9C | LAST_SID_LO / HI | RO | power-on persistent |
| 0xA0 / 0xA4 | LAST_CTR_LO / HI | RO | power-on persistent |
| 0xA8 / 0xAC | PKTS_LO / HI | RO, snapshot | packets emitted (64 bit) |
| 0xB0 / 0xB4 | WORDS_IN_LO / HI | RO, snapshot | 64 bit |
| 0xB8 / 0xBC | WORDS_OUT_LO / HI | RO, snapshot | 64 bit |
| 0xC0 / 0xC4 | CYCLES_LO / HI | RO, snapshot | clocks since ENABLE, 64 bit |
| 0xC8 | IN_WAIT | RO, snapshot | clocks with ready = 1 and no input (32 bit, saturating) |
| 0xCC | OUT_STALL | RO, snapshot | clocks with output valid and no ready |
| 0xD0 | TABLE_WAIT | RO, snapshot | clocks stalled on late or restarted tables |
| 0xD4 | KS_WAIT | RO, snapshot | clocks nv_xor stalled on `ks_avail` |
| 0xD8 | ERR_RANGE | RO, snapshot | §2.4 rule 3 |
| 0xDC | ERR_ORDER | RO, snapshot | §2.4 rule 2 |
| 0xE0 | ERR_PRE_TH | RO, snapshot | §2.4 rule 1 |
| 0xE4 | ERR_JUMP | RO, snapshot | §2.4 rule 6 (words dropped) |
| 0xE8 | ERR_PADOVF | RO, snapshot | §5.2 overflow (words dropped) |
| 0xEC | ERR_CFG | RO, snapshot | refused commits |

Counters run from ENABLE; `CTRL.SNAP` copies all of them into the read registers in the same clock, so a
64-bit LO/HI pair and the set as a whole are consistent. `nv_driver.py` always snaps before reading.

---

## 7. Golden model (`software/neuro/`) and test vectors

The model is the referee. It is pure Python plus numpy and imports only `model.ascon` and `link.keys` /
`link.feedback` / `link.wire`, which are shared code (no paper-1 file is edited). Add `"neuro*"` to
`[tool.setuptools.packages.find] include` in `pyproject.toml`.

### 7.1 Modules and API

| Module | Contents |
|---|---|
| `neuro/geometry.py` | `@dataclass(frozen=True) Geometry(name: str, W: int, H: int)`; `SENSORS: dict[str, Geometry]` (§2.3); `MIN_PERM_DIM = 16` |
| `neuro/evt2.py` | constants `CD_OFF=0x0, CD_ON=0x1, TIME_HIGH=0x8, EXT_TRIGGER=0xA, OTHERS=0xE, CONTINUED=0xF`; `EVENT_DTYPE = [("t","<u8"),("x","<u2"),("y","<u2"),("p","u1")]`; `encode(events, T_us=1024) -> np.ndarray[uint32]` (canonical, with boundary heartbeat, §2.4); `decode(words) -> (events, extras)`; `event_equal(a, b) -> bool` (§2.5); `read_raw(path) -> (words, Geometry)`, `write_raw(path, words, geom)` (Prophesee RAW header `% format EVT2;height=H;width=W`, `% end`) |
| `neuro/keys.py` | `C62 = 1 << 62`; `LABELS = {"tag": 1, "pol": 2, "perm": 3, "dum": 4, "aead": 5}`; `@dataclass(frozen=True) SubKeys(tag, pol, perm, dum, aead: bytes)`; `base(cam_id, boot_id) -> int`; `root_key(master, cam_id, boot_id)`; `epoch_key(master, cam_id, boot_id, epoch)`; `subkeys(master, cam_id, boot_id, epoch) -> SubKeys`; `session_id(cam_id, boot_id, epoch) -> int`; `split_session(sid) -> (cam_id, boot_id, epoch)`; `class EventRatchet(master, cam_id, boot_id, epoch=0)` with `.peek(epoch)` (refuses older epochs and epochs above `epoch + E_MAX`), `.forward(epoch)`; `boot_id_from_kex(m1, m2) -> int`; `E_MAX = 2`, `EPOCH_LAST = 0xFFFF` |
| `neuro/packet.py` | `HEADER_LEN = 48`, `TRAILER_FIXED = 12`; `@dataclass(frozen=True) PacketHeader(...)` with the §3.3 fields, `.pack() -> bytes48`, `.unpack(b)`; `@dataclass Trailer(n_words, n_cd, bitmap: bytes = b"")`, `.pack()` (bitmap first, fixed fields last), `.unpack(b, pad)`; `@dataclass Packet(header, payload: np.ndarray, trailer, tag: bytes)`, `.to_bytes()`, `.to_words()`; `from_bytes(b) -> Packet` (keyless extraction of header, payload and trailer from the public framing; used by N8-R); `packetize(words, geom, T_us, ctr0=0, max_gap_us=1_000_000, jump_mode=0) -> list[RawPacket]`, where `RawPacket(ctr, t_start, words, flags, needs_tables: bool, errors)` (rules of §2.4 and §3.2) |
| `neuro/feistel.py` | `@dataclass(frozen=True) Tables(W, H, r, t: tuple[np.ndarray, ...])`; `make_tables(k_perm, sid, ctr, W, H, r=8) -> Tables` (raises for W or H < 16); `permute(x, y, tables)`, `unpermute(x, y, tables)` (vectorised on numpy arrays); `permute_walk(...)` (ablation N2b); `shuffle_table(...)` (§4.4) |
| `neuro/levels.py` | `xor_fields(words, cd_mask, ks_bits, b) -> words`; `protect(words, level, b, tables, ks) -> words`; `unprotect(...)` |
| `neuro/pad.py` | `@dataclass PadPolicy(kind: int, pad_min: int, pad_cap: int, max_cd: int = 131072)`; `bucket_target(n_real, policy) -> int`; `dummy_word(ks, geom) -> int`; `pad_packet(words, policy, k_dum, sid, ctr, geom) -> (words, masked_bitmap, n_dropped)`; `strip(words, masked_bitmap, k_dum, sid, ctr, geom, policy) -> words` (unmask, check dummy content and pad conformance, §5.3) |
| `neuro/sender.py` | `@dataclass(frozen=True) Config(level, ts_bits, T_us, geom, pad: PadPolicy | None, max_gap_us, jump_mode)`; `class Encryptor(subkeys, sid, cfg, ctr0=0)`: `.push(words) -> list[bytes]`, `.flush() -> list[bytes]` (adds the FINAL packet), `.commit(at_ctr, cfg=None, subkeys=None, sid=None, ctr0=0)` (same acceptance rules and FIRST/FINAL/link behaviour as §6.7; raises `ConfigError(code)`), `.counters` (ERR_* as in §6.7) |
| `neuro/receiver.py` | `@dataclass(frozen=True) Profile(allowed: frozenset[tuple[int, int, int, int]], geom, T_us, R_max_words_per_us, pad: PadPolicy | None, window=64, e_max=2, stall_k=100)`; `class NeuroWindow(size=64)` with `.would_accept(ctr) -> bool` (no side effects) and `.mark(ctr) -> list[int]` (returns counters that left the window unmarked); `class Decryptor(keyring, profile, state_path=None)`: `.accept(pkt: bytes, now: float) -> Result`, `.tick(now) -> list[Notice]`, `.close() -> list[Notice]`; `@dataclass Result(status: Literal["ok","forged","replay","malformed","stale","policy"], ctr: int | None, words: np.ndarray | None, notices: list[Notice])`; `@dataclass Notice(kind: Literal["gap","truncated","stall"], sid: int, ctrs: tuple[int, int] | None)`. `keyring` maps (cam_id, boot_id) to a master (from a kex, or K_psk); `state_path` persists the highest boot_id per cam_id (PSK profile) |
| `neuro/hw.py` | stage view for testbenches: `table_fill_entries(k_perm, sid, ctr, W, H)`, `feistel_round(x, y, j, tables)`, `xor_word(w, k, b)`, `tag_blocks(header, payload, trailer, mode) -> list[(bytes, blk_bytes, blk_last, type)]` (exact block sequence including the empty last block), `tag_input(header, payload, trailer) -> bytes`, `out_words(packet) -> list[int]`, `commit_ok(open_ctr, at_ctr, last_sid, last_ctr, new_sid, ctr0) -> (bool, code)`. Must match the packet view (`tests/test_neuro_equivalence.py`) |
| `neuro/vectors.py` | `write_vectors(out_dir, cases, full=False)`, CLI `python -m neuro.vectors --out hardware/vectors/neuro [--full]` (Makefile target `vectors-neuro`) |
| `neuro/v2e_lite.py` | `frames_to_events(y_frames, fps, C=0.2, refractory_us=500, seed=0) -> events`. Log-intensity per-pixel memory, following `hu2021v2e`'s core idea with the noise and bandwidth models off (`lit_formats_data.md` §7). Used at the clip's native size only |
| `neuro/datasets.py` | `load_nmnist(root, split)`, `load_dvsgesture(root, split)` (Tonic 1.7.0, official train/test files), `load_eventreid(root, split)` (format read from the dataset files in the QUICK run), returning `(events, label, group, Geometry)` where `group` is the recording/subject id used for cluster statistics; `manifest(root) -> dict` (SHA-256 per file); `cache_counts(dataset, out_npz)` (per-bucket counts for N5, so the laptop never needs Tonic) |
| `neuro/baselines/du2021.py` | reimplementation of [`du2021sensors`] with **its own 2D-SIMM generator** (default) from the equations in `docs/neuro/BASELINES.md`; variant `ascon_keyed=True`, labelled "Ascon-keyed Du", used only in N7/N9 |
| `neuro/baselines/zhang2024.py` | reimplementation of [`zhang2024nce`] (noise-event mask + `p XOR (szudzik mod 2)`), from the construction written in BASELINES.md. The unspecified key function ρ is instantiated with our Ascon keystream and labelled as such (Zhang leaves ρ open, so there is no "own" generator to use) |
| `neuro/attacks.py` | active attacks on packet bytes: `inject, replay, delete, delete_tail, reorder, splice, downgrade, flood, epoch_jump` (§1.4). The same functions run on the Du and Zhang outputs, which carry no tag. Passive: `polarity_collapse(events)`, `event_count_frame(events, geom)`, `time_surface(events, geom)`, `adjacency_embed(events, dt_us, k)` (N4b) |
| `neuro/stats.py` | `bootstrap_ci(values, n=2000, seed=0)`, `mean_ci(v)` (Student-t), `cluster_bootstrap_ci(values, groups, n=2000, seed=0)` (resamples whole groups), `paired_bootstrap_diff(a, b, groups, n=2000, seed=0)`, `clopper_pearson(k, n, alpha=0.05)`, `mi_plugin_mm(x, y)` (plug-in MI with Miller-Madow correction), `mi_perm_null(x, y, n=200, seed=0)`: one shared copy, not a fourth copy (repo_experiments §1) |
| `neuro/voxel.py` | `voxel_grid(events, B=5, H, W)`, matching `events_to_voxel_grid` of E2VID (5 bins, bilinear in time, polarity ±1); cross-checked against upstream in N3 |
| `neuro/cycle_model.py` | timed replay of real traces into a model of nv_xor / Feistel / FIFO / tag (parameters L, U, FIFO depth, fill_clk), returning occupancy, drops and latency; checked against N1 RTL simulation on the §7.2 vectors |

### 7.2 Test vectors for RTL (`hardware/vectors/neuro/<case>/`)

| File | Format |
|---|---|
| `config.json` | `{"geom":[W,H], "level":L, "ts_bits":b, "T_us":T, "pad":{...}|null, "sid":"0x..", "ctr0":n, "max_gap_us":g, "jump_mode":m, "subkeys":{"tag":"hex32",...}, "commits":[{"at_ctr":a, "cfg":{...}, "expect":"ok|LATE|REWIND|..."}], "model_commit":"<git sha>"}` |
| `in.hex` | one 8-hex-digit input word per line, in AXI order; an optional `@<clk>` line delays the next word (timed input) |
| `out.hex` | one output word per line; `L` after the word marks `tlast` |
| `tables_<ctr>.hex` | optional, for `test_nv_table_gen`: per table j, one entry per line in fill order |
| `ks_pol_<ctr>.hex` | optional, for `test_nv_xor`: the keystream bits as consumed, 32 per line LSB-first |
| `blocks_<ctr>.hex` | optional, for `test_nv_tag32`: the `neuro.hw.tag_blocks` sequence |
| `counters.json` | expected ERR_*, PKTS, WORDS_IN, WORDS_OUT |

Default cases (run by `make test`; small T = 64-256 µs and low event counts, so the whole set stays within the
`make test` budget of about 40 s):
- one per (sensor ∈ {nmnist, dvsgesture, 16 x 16, 16 x 1280}) × (level ∈ V0..V4);
- empty packets and a time gap; a time gap with PAD floor at V3; a time jump in each JUMP_MODE;
- out-of-range, pre-TH and backwards TIME_HIGH words; all non-CD word types;
- PAD floor and ladder at V3 (b = 6); PAD overflow with a small MAX_CD_PAD; PAD with b < 6 refused (ERR_CFG);
- n_words ≡ 0, 1, 2, 3 (mod 4), with and without the bitmap, MAC and ENC; the empty packet (n = 0);
- commits: at a boundary (ok); during a table fill for the next packet (refused LATE, then ok at a later
  counter); a MODE write in mid-packet (takes effect only at COMMIT_AT); a CTR rewind (REWIND); epoch 0xFFFF →
  next (REWIND); SOFT_RST followed by the old SID and ctr0 (REWIND); FLUSH (FINAL packet).

Full cases, behind `FULL=1` / `RUN_SLOW=1` (as in the Makefile): davis346 and imx636 geometries at T = 1024 µs
and high event rates. Testbench checks beyond word equality: random output `tready` (no word lost or duplicated,
V0-V4, compared against `ascon.encrypt` at V4); each word leaves nv_feistel exactly LAT clk after it enters when
the FIFO has credit (the fixed-latency claim, tested). Vectors are generated, never edited.

### 7.3 Model tests (`tests/`)

`test_neuro_keys.py` (ctx table pairwise distinct per key, subkeys differ per base and epoch, EPOCH_LAST),
`test_neuro_evt2.py`, `test_neuro_packet.py` (trailer parse unique for random payloads that contain
trailer-like word pairs; jump rule), `test_neuro_feistel.py` (inverse on all points for 16 x 16, 34 x 34,
16 x 1280; refusal below 16), `test_neuro_levels.py`, `test_neuro_pad.py` (b < 6 refused; empty packet padded;
overflow; mask offset), `test_neuro_receiver.py` (every §1.4 row, plus: a forged packet with
ctr = top + 2^40 followed by the next genuine packet gives `ok`; a junk packet with epoch = current + 65 535 is
`policy` with no KDF call and bounded receiver time; tail truncation gives `truncated`; FIRST/link gives the old
epoch's `gap`), `test_neuro_sender_commit.py`, `test_neuro_equivalence.py` (packet view == hw stage view),
`test_neuro_experiments.py` (each script on tiny input).

---

## 8. Experiments

All scripts are `experiments/neuro_<name>.py`, with the paper-1 header convention: docstring with question,
usage, method, controls and "Writes …"; `argparse(description=__doc__)`. Each writes
`sim_out/neuro/<exp>/<name>.json` (data + `meta`: inputs with SHA-256, commit, seeds, number of keys, number of
clusters, CI method) and `.md` (the paper table). Finished runs are copied unchanged to
`results/<area>/neuro_<exp>/`. Where: L = laptop CPU (light), K = Kaggle GPU, V = Vivado, B = board.

### 8.1 Claims and the evidence that decides them (criteria fixed before any run)

| Claim | Experiment | Metric | Pass criterion (fixed now) | If it fails |
|---|---|---|---|---|
| (i) only Ascon-AEAD128, nonce-respecting | `test_neuro_keys.py`, code audit, paper-1 KATs | ctx table distinct per key; all crypto calls go through `model.ascon` | all pass | bug; fix before any other run |
| (ii) authenticity | N7, `test_neuro_receiver.py` | required status per §1.4 row | 100 % of trials, reported with the Clopper-Pearson lower bound; forgery bound stated analytically (2^-128 per attempt) | bug |
| (iii) payload is EVT 2.0 | N8-R | events read back by expelliarmus (`Wizard(encoding="evt2")`), Tonic and our voxel loader from extracted payloads | count read back = n_cd and 0 decode errors, for V1 and V2. V3: reported per reader; claim (iii) for V3 only if it passes | narrow the claim to the readers that pass |
| (iv) fixed latency, 1 CD word/clk | N1 latency check, N2 | exact LAT in cocotb; WNS at 100 MHz | latency exact; WNS ≥ 0 for the plan-of-record build (L = 1, U = 2) | report the measured Fmax and rate |
| (iv) authenticated throughput X | N2, N10 | Mev/s | claim "≥ 1 word/clk authenticated" only if the U = 4 build has WNS ≥ 0 at 100 MHz; otherwise state the measured X | restate X |
| P1: V2/V3 defeat reconstruction on real events | N3, N4, N4b | best attack per window vs control (f), paired cluster bootstrap | upper 95 % bound of (SSIM_attack − SSIM_control(f)) < 0.05 on every dataset that passes the validity gate | report as a leak, with the level and T at which it appears |
| P2: V1 is not private | N3 | event-count image + YuNet / classifier | reported, expected to leak | (none: this is a stated limitation) |
| P3: layout leak via adjacency | N4b | recovered 4-neighbour fraction | none; the result sets the T default and the limitation text | lower the default T or state the rate limit |
| U: utility with key, none without | N6 | accuracy (ii) − chance, CI | gates of §8.2 N6 met; result reported as is | (none) |
| FPE worth it | N11 | keyless utility kept by V1-V3 and lost by V4 + pad | at least one keyless function with AUC within 0.05 of plaintext | reframe V1-V3 as "compatible transport" |

The thresholds 0.05 are our choice, written here before any run so that they cannot be tuned afterwards.

### 8.2 Experiment list

**N1 `neuro_rtl_exact.py`** (wraps `hardware/tb/neuro/`), L. Is the RTL bit-exact against the model? Inputs:
§7.2 vectors + random streams (SEED). Metrics: words compared, first mismatch (index, input, got, expected),
pass/fail per module and case, cycles per word, Feistel latency check, random-tready loss check. Baseline: model.

**N2 `hardware/vivado/neuro/run_vivado_neuro.py`** (+ `experiments/neuro_hw_tables.py`), V. Area, Fmax, power.
Builds: L ∈ {1, 2, 4} × U ∈ {1, 2, 4} (L ≥ 2 only for V0/V2, §6.4), MAXW × MAXH ∈ {34², 128², 346 × 260,
1280 × 720}; N2b walk ablation. Metrics: LUT, FF, RAMB18 (per `nv_sdp_ram` instance), DSP, WNS at 100 MHz,
authenticated events/s = min(L, tag rate, fill-bound rate)·f, K_pol generators per build. Power: `report_power`
with a SAIF from the N1 simulation at a stated event rate, labelled "post-route estimate (SAIF)"; no measured
energy is claimed unless a board-level measurement is added. Baselines: paper-1 `tag_unit`, `keystream_gen`.

**N3 `neuro_recon_attack.py`**, K. Can reconstruction recover the scene from protected events?
- Datasets: **Event-ReId (mandatory, real events of people)** [`ahmad2023iccv`]; HQF [`stoffregen2020eccv`†]
  optional for intensity ground truth; v2e-lite on Xiph CIF clips at native 352 × 288 (secondary, labelled
  simulated). N-MNIST is not used in N3. No result at the `imx636` geometry.
- **Validity gate (first output):** E2VID on plaintext vs ground truth. A dataset counts only if plaintext SSIM
  exceeds the ciphertext floor (control (c), below) by ≥ 0.05 with a CI that excludes 0. Anchor on Event-ReId:
  Ahmad 2023 report SSIM 0.548 for plaintext E2VID (Table 2).
- **Attack set per level** (report the most revealing result per window, paper 1's `privacy_metrics` rule):
  - all levels: E2VID, FireNet, CF reconstruction [complementary filter of Scheerlinck et al.; citation to be
    verified before use, see LITERATURE.md], denoise-then-reconstruct with the denoisers Zhang 2024 used
    (re-read from the PDF) and Tonic `Denoise`;
  - V1: E2VID on polarity-collapsed voxels (|voxel| and p := 1), event-count image, time surface;
  - V2/V3: the above plus the N4b adjacency embedding fed to E2VID.
- Controls: (c) training-median frame; (f) prior conditioned on the public per-bucket count series; Knuth-shuffle
  ideal permutation (§4.4) on DVS Gesture (128 × 128, against plaintext E2VID output, labelled as such).
- Metrics: SSIM, PSNR, LPIPS, edge correlation vs ground truth (or vs plaintext reconstruction, labelled);
  face recall (YuNet) and ArcFace verification where faces exist; re-ID rank-1 on Event-ReId.
- Baselines: plain, V0-V4, Du 2021 (own 2D-SIMM), Zhang 2024. Du sanity anchor: Ahmad 2023 Table 3 reports Du at
  75 % encryption on Event-ReId with SSIM 0.451; our Du reimplementation must land within ±0.03 SSIM.
- Statistics: ≥ 5 independent master keys; `cluster_bootstrap_ci` over recordings/subjects; number of clusters
  next to every CI; `paired_bootstrap_diff` for V2 vs Du, V3 vs V2, padded vs unpadded on identical windows.

**N4 `neuro_learned_attack.py`**, K. Can a network trained on (ciphertext, plaintext) pairs undo V1-V3? Voxel
grids of ciphertext events, fresh key per sample, train and test recordings disjoint (overlap guard). Target:
the GT/APS frame where it exists (Event-ReId if it has frames, HQF), else the plaintext E2VID reconstruction,
labelled as such. Controls: (c) training-median frame; (f) a network given only the public per-bucket count
series. Leakage measure: network SSIM − control (f) SSIM, paired cluster-bootstrap CI. ≥ 5 master keys.
Baselines: V1, V2, V3; Du, Zhang.

**N4b `neuro_adjacency_attack.py`**, L (CPU). Does co-activation reveal the layout without the key? For each
packet, build a k-NN graph over permuted addresses from timestamp proximity (Δt ∈ {5, 20, 64} µs), compute a
Laplacian eigenmap to 2D, align it to the true (x, y) by Procrustes, and report the fraction of recovered
4-neighbour pairs and the Procrustes error. Sweep T ∈ {256, 1024, 4096} µs and event rate (rate percentiles from
N9). Control: Knuth-shuffle ideal permutation (§4.4), which tells whether a leak belongs to V2 in principle.
Data: Event-ReId, DVS Gesture, N-MNIST, v2e-lite CIF. The result is stated as a limitation or as a constraint on
the T default (§8.1 P3).

**N5 `neuro_leakage.py`**, K for data loading (Tonic), L for the analysis on cached `.npz` counts
(`neuro.datasets.cache_counts`), so the laptop never needs Tonic on Python 3.14. What do event rate, motion
energy, multiplicity and dummy position reveal, and what does padding cost?
- MI between per-bucket count series and class: `mi_plugin_mm` (plug-in with Miller-Madow correction),
  permutation null of 200 label shuffles, bootstrap CI and p-value.
- Classifiers: gradient-boosted trees on the per-bucket count series and a 1D CNN, official train/test split
  (DVS Gesture: Tonic's train/test files; the subject split is checked from the file metadata and written in
  `meta`), balanced accuracy with chance level and cluster-bootstrap CI.
- Dummy distinguisher AUC (§5.4): multiplicity only, position in bucket only, both.
- Padding: fraction of buckets above PAD_CAP (ladder) or PAD_MIN (floor) per dataset; MI per policy; bandwidth
  overhead per policy.
- Levels: V2, V3, V3 + pad floor and ladder, V4 (+ pad).

**N6 `neuro_task_accuracy.py`**, K. Is utility kept with the key and lost without it? N-MNIST and DVS Gesture
(Tonic 1.7.0, official train/test files, split written in `meta`).
- Decryption is exact, so "accuracy on decrypted data" is not a result: the script asserts `event_equal` over the
  whole test set and reports the count of equal samples in one sentence.
- Models: one frame CNN and one SNN (snnTorch), both trained to convergence. **Gate:** clean accuracy ≥ 98 %
  (N-MNIST) and ≥ 90 % (DVS Gesture) before any ciphertext row is reported; context numbers from PLIF
  [`fang2021iccv`] (99.61 % / 97.57 %).
- Rows: (i) trained on clear, tested on ciphertext; (ii) trained on ciphertext with fresh keys per sample. The
  measure fixed in advance is accuracy (ii) − chance, with a CI. V1 is expected to keep almost all accuracy and
  is presented as a leak.
- ≥ 3 training seeds, Student-t interval (`mean_ci`). Baselines: plain, V1-V4, Du, Zhang.

**N7 `neuro_active_attacks.py`**, L. Detection is 100 % for ours and acceptance 100 % for Du/Zhang by
construction, so the main table states this together with the analytical forgery bound (2^-128 per attempt), and
the experimental budget goes to:
- (i) downstream impact of an undetected injection on Du/Zhang: a simple event patch trigger of our own
  (motivated by Event Trojan [`wang2024eccv`†], which we know at abstract level only) injected into N-MNIST /
  DVS Gesture test streams; classifier attack success for Du/Zhang vs rejection for ours;
- (ii) utility under benign loss: N6 accuracy and N3 SSIM vs random packet-loss rate p ∈ {0, 1e-3, 1e-2, 5e-2}
  and T ∈ {256, 1024, 4096} µs (a lost packet loses a whole T of events);
- (iii) tail truncation and epoch-boundary deletion: detected via FINAL / link (§3.5);
- (iv) gap-detection latency in ms (bounded by the window, §1.4);
- flood: receiver CPU µs per junk packet that passes the header checks, and per junk packet that fails them;
- epoch jump: bounded receiver time with epoch = current + 65 535.
Proportions with Clopper-Pearson intervals. Fragment loss counted separately from `gap`.

**N8 `neuro_perm_strength.py`**, L. Does the permutation behave as specified?
- Inverse exactness over all W·H points per sensor, including 16 × 16 and 16 × 1280; refusal below 16.
- Table bias vs script (a); cross-packet independence (correlation of P_ctr, P_ctr+1).
- Known plaintext: (i) distribution of distinct known (x, y) pairs per packet under the §1.3 assumptions
  (hot pixels, flashing pattern), measured on real datasets, against the attack data requirement per sensor and
  T; (ii) the r = 4 attack run with oracle access to a full packet's codebook on 34 × 34, labelled "oracle, not
  achievable in-packet at measured rates", and on an unbalanced domain to check the §4.3.5 approximation;
  (iii) r = 8 under the same oracle. No outcome is asserted in advance.
- **N8-R (readers):** write the extracted payloads (no header, trailer or tag) of V1/V2/V3 packets to a `.raw`
  file and read it with expelliarmus, Tonic and the voxel loader; report the count read back vs n_cd, decode
  errors, drops and reorders (claim (iii), and the V3 tolerance question).

**N9 `neuro_overhead.py`**, L + B (ARM timing).
- Event-rate distribution per dataset (Event-ReId, N-MNIST, DVS Gesture, v2e-lite CIF): median, p99 and max burst
  over 10 µs, 100 µs and 1 ms windows.
- Overhead bytes/event (header 48 + trailer 12 + tag 16 = 76 B per packet *(arith.)*, bitmap, padding) and
  authenticated latency **at those percentiles**, for T ∈ {256, 512, 1024, 4096} µs. At low rates the fixed
  76 B per T (74 kB/s at T = 1024 µs *(arith.)*) can exceed the payload; the table shows where.
- Cycle model (`neuro.cycle_model`, checked against N1): timed replay of the real traces; FIFO occupancy, drops
  or backpressure vs FIFO depth and U; sizes `nv_word_fifo`; replay throughput per sensor and T (§6.3).
- Software cost: ours, Du and Zhang in the **same Python on the same machine** (laptop and ARM). Our hardware
  rate is given separately. Du's own published CPU numbers (0.20 µs/event on a Pi 4B) are quoted separately with
  citation, never mixed into our table.

**N10 `software/system/board/neuro/nv_replay.py`** (+ `experiments/neuro_board_tables.py`), B. Does the PYNQ-Z2
run bit-exactly over UDP? RAW EVT 2.0 files replayed by DMA in two modes: **timed** (a PL timer gates input by
timestamp, i.e. sensor timing) and **maximum rate**. Metrics: bit-exact vs model (first mismatch), PL throughput
(from CYCLES / WORDS_IN, snapshotted) reported separately from UDP/ARM throughput, IN_WAIT / OUT_STALL /
TABLE_WAIT / KS_WAIT, fragment loss vs `gap`, receiver statuses under live N7 attacks (deployment profile, kex at
boot). "Sensor speed" is claimed only for whichever of PL or end-to-end is measured, at the timed-mode rates.
Baseline: `--mock` (model) path.

**N11 `neuro_fpe_utility.py`**, L. Is format preservation worth its cost compared with V4 + padding?
(a) Size of plain vs V1/V2/V3 payloads after re-encoding to EVT 3.0 with expelliarmus and after zstd: the
bandwidth cost of FPE vs V4. (b) One keyless function an untrusted node can still perform on V1-V3 and that V4 +
padding loses: activity / wake-up detection from per-packet event rate (AUC vs plaintext) and a rate-based
recording trigger. (c) Reader compatibility (from N8-R). If no keyless utility survives, V1-V3 are reframed as
"compatible transport" (§1.6).

### 8.3 Datasets, baselines, statistics

- **Datasets.** N-MNIST (`Train.zip`, `Test.zip` from Mendeley) and DVS Gesture (figshare
  `ibmGestureTrain/Test.tar.gz`); sizes and MD5 values are in `lit_formats_data.md` §6. Event-ReId from Zenodo
  (doi 10.5281/zenodo.8256439); its size, licence and file format are read in the QUICK run, not assumed. HQF
  optional. All are downloaded on Kaggle by `software/scripts/get_events.py` with a SHA-256 manifest. v2e-lite
  events are generated from the Xiph clips that `get_xiph.py` already fetches.
- **Baselines (`docs/neuro/BASELINES.md`, written before any baseline code).** It must contain, read from the
  PDFs with section numbers: Du 2021 §3 in full (2D-SIMM iteration and parameters, the mapping from the six
  sequences to the position permutation, the polarity flip, the updating score rule) and the target number to
  reproduce (Ahmad 2023 Table 3: Du on Event-ReId, SSIM 0.451, tolerance ±0.03); Zhang 2024's noise-mask
  construction (neighbourhood, recursion stop, timestamp assignment, polarity rule) and its N-MNIST recognition
  table re-read from the PDF as the anchor (tolerance ±3 pp). Du runs with its own 2D-SIMM; the Ascon-keyed Du
  variant is labelled and used only in N7/N9. The attacker knows the scheme and not the key.
- **Statistics.** N3/N4/N5: cluster bootstrap over recordings/subjects, ≥ 5 master keys, cluster count next to
  every CI, paired differences on identical windows. N6: ≥ 3 seeds, Student-t. N7/N10 proportions:
  Clopper-Pearson. MI: Miller-Madow + permutation null.
- The FPE design script (script (a)) moves to `experiments/neuro_fpe_numbers.py`, which writes
  `sim_out/neuro/fpe/` (N0, design numbers).

### 8.4 Kaggle budget (paper 1's quota first)

Kaggle's weekly GPU quota is shared with paper 1, and one paper-1 learned-attacker run took about 2 h. Each
paper-2 session starts only when paper 1 has no pending Kaggle step. The table holds planning guesses until the
QUICK run replaces them with measured values (written to `meta.budget` by `kaggle_neuro.py`).

| Step | GPU-h (guess → QUICK-measured) | Peak disk | Download | Session |
|---|---|---|---|---|
| data (N-MNIST 1.18 GB, DVS Gesture 3.14 GB compressed, Event-ReId unknown) | 0 | sizes from `lit_formats_data.md` §6 plus extraction; measured | measured | 1 |
| N5 count cache | ≈ 0.2 *(guess)* | small `.npz` | – | 1 |
| N3 | ≈ 2 *(guess)* | checkpoints 43 MB + 0.5 MB | – | 1 |
| N6 | ≈ 3 *(guess)* | checkpoints | – | 2 |
| N4 | ≈ 2-4 *(guess, paper-1 analogue ≈ 2 h)* | checkpoints | – | 3 |

QUICK run assertions (fail fast): `pip install tonic==1.7.0` succeeds; `torch.load(weights_only=True)` works for
both checkpoints, else falls back with the SHA-256 checked; free disk after extraction is printed and must leave
room for checkpoints within the `/kaggle/working` limit; Event-ReId downloads and its geometry is printed. Both
checkpoints are mirrored, SHA-256 pinned, into a private Kaggle dataset and fetched from there, with the upstream
URL (FireNet: Google Drive) as fallback.

---

## 9. Risks, honest limitations, open questions

### 9.1 Risks (with mitigation)

| Risk | Effect | Mitigation |
|---|---|---|
| U = 4 Ascon does not close at 100 MHz | tag below 1 word/clk | U = 2 is the plan of record (0.8 words/clk *(arith.)*); U = 4 is a stretch goal; U = 1 (0.44 words/clk) still covers DAVIS-class rates. Report the measured rate, never the target |
| Table fill late for short T, big sensors or sparse replay | stall at packet start; replay rate fill-bound | needs_tables rule; TABLE_WAIT counter; replay rate formula in §6.3; minimum T per sensor reported (N9) |
| Commit arrives too late | refused commit | COMMIT_AT ≥ open ctr + 2 rule, LATE code, ARM retries (§6.7) |
| BRAM for MAXW × MAXH | 24 RAMB18 at 1280 × 720 (script (a)) + 8 for the PAD bitmap | fine on xc7z020 (280). L = 4 doubles the banks |
| Du 2021 / Zhang 2024 reimplementation wrong | unfair comparison | BASELINES.md with equations and section numbers before code; Du anchored on Ahmad 2023 Table 3 (±0.03 SSIM), Zhang on its N-MNIST table (±3 pp) |
| Event-ReId unavailable or unsuitable on Kaggle | N3 has no real-event people dataset | checked in the QUICK run before any paid step; fallback HQF (no people) and a stated limitation |
| E2VID/FireNet code is GPL-3.0 and old PyTorch | licensing, load errors | download at run time into the Kaggle working dir and never commit it; patch `np.int` / `delim_whitespace` in that copy; checkpoints pinned by SHA-256 and mirrored |
| Tonic does not install on the Kaggle image | N5/N6 blocked | QUICK smoke run first; Tonic 1.7.0 ships cp311 wheels (unverified install) |
| Paper-1 shared files (`common.py`, `vivado_ooc.tcl`, `wire.py`, `kaggle_runs.py`) | merge conflicts, or disturbing paper-1 runs | paper 2 uses its own files (§10). The only shared-file edits are an `include` entry in `pyproject.toml` and README rows |
| boot_id reuse (SD card restored) in the PSK profile | nonce reuse towards a receiver without state | deployment uses the `kex` profile (fresh master per boot); PSK receiver persists the highest boot_id; PSK sender refuses to start without its counter file |

### 9.2 Limitations to state in the paper

1. **V1 hides polarity only**; positions and timestamps are in the clear and an event-count image reveals the
   scene. V2/V3 hide layout within a packet, not activity: they leak the event count (per packet and per
   bucket), the TIME_HIGH values, the timestamps (V2) and per-pixel multiplicity and co-activation within a
   packet (N4b). Only V4 + padding hides content and (partly) rate.
2. V2/V3 are not IND-CPA. Within-packet security rests on cryptanalysis (§4.3.6), as FF1 does. A successful
   attack recovers one packet's layout; packets are attacked independently, so total loss grows with effort.
3. V3's timestamp masking is ≤ 63 µs and buys almost nothing against binned representations (§4.5).
4. Dummies are distinguishable by multiplicity and by their position at the end of the bucket (§5.4). The
   ladder leaks exact counts above PAD_CAP. Padding costs bandwidth (N5, N9).
5. Authenticated latency is about T, because verify-then-use must wait for the tag.
6. EVT 2.0 is the GenX320's format; the IMX636 needs an unpacker (§2.2). Real-sensor event rates beyond the
   DAVIS346 class exceed one lane at 100 MHz. The wire bytes are not an EVT 2.0 stream; only extracted payloads
   are.
7. DVS Gesture in Tonic has ms timestamps, so V3 results on it are trivial. N-MNIST, Event-ReId and v2e-lite give
   real µs timing.
8. v2e-lite has no noise or bandwidth model. Privacy claims rest on Event-ReId (real events).
9. Deletion of the tail of a stream is detected only as `truncated` / `stall`, not located.

### 9.3 Open questions

1. Do real sensors (GenX320) send TIME_HIGH words while there are no events? This decides whether packets can
   close without the heartbeat (§2.4) and whether `stall` is meaningful during silence. If not, add a local µs
   timer to close packets (contract n2).
2. Do OpenEB/Metavision and dv-processing accept in-bucket non-monotone timestamps (V3)? Tested in N8-R for the
   readers we can run; OpenEB is unverified.
3. Keyed dummy interleaving inside a bucket (removes the suffix leak, §5.4) needs a one-bucket buffer (up to
   6 400 words at 1 word/clk, 64 µs *(arith.)*) and keyed slot positions from K_dum. Is the RAMB18 cost
   acceptable for n2? Is a padding scheme that copies real multiplicity possible?
4. Should the table key be derived with Ascon-CXOF128 (SP 800-232) instead of a fifth AEAD subkey? That would
   need a second Ascon mode in hardware, so it is rejected for n1.
5. Beyond Event-ReId and HQF, is a real DAVIS recording with people and frames available and usable?
6. Novelty threats that could not be opened: TU Delft 2026 thesis, NTU DVS-PUF, FF3 small-domain papers. Open
   them, and repeat the Xplore and Scopus search before submission.
7. A tag-tree (several Ascon lanes combined) or per-lane K_pol sub-streams would lift the tag and keystream
   bottlenecks but change the contract. Deferred to a contract n2 if N2 shows U = 2 is not enough.
8. Paper 1's `feedback_key` and `video_key` both call `kdf(master, …, ctx = 0)`, i.e. the same nonce under the
   master for two labels. This is outside paper 2 (paper 2 uses ctx ≥ 2^62 under the master) and is reported
   to paper 1, not changed here.

---

## 10. Folder layout and entry points (within the six top-level folders)

```
hardware/rtl/neuro/          nv_*.v (§6.2); reuses ../ascon_round.v, ../ascon_aead128_core.v, ../keystream_gen.v, ../skid_buf.v
hardware/tb/neuro/           common_nv.py (SOURCES_NV, run_sim_nv with test_dir = this folder), test_nv_*.py (one per module + test_nv_top.py)
hardware/vectors/neuro/      generated by `python -m neuro.vectors` (make vectors-neuro; FULL=1 adds the large cases)
hardware/vivado/neuro/       vivado_ooc_neuro.tcl (reads the 4 reused files + rtl/neuro/*.v), run_vivado_neuro.py (steps: ooc, lanes, walk, bd, power, parse, collect), xsim_neuro.prj
software/neuro/              golden model package (§7)
software/system/board/neuro/ nv_bd_top.v, block_design_neuro.tcl, nv_driver.py (NvIP, VERSION 0x4E5601xx with the build byte of §6.7, snap-then-read counters, MockBackend), nv_first_contact.py, nv_replay.py (--timed / --max-rate)
software/system/kaggle/      kaggle_neuro.py (JOB "neuro", BRANCH "neuromorphic", writes neuro_results.zip, meta.budget)
software/scripts/            get_events.py (datasets + SHA-256 manifest)
experiments/                 neuro_*.py (§8), README rows
tests/                       test_neuro_*.py (§7.3)
docs/neuro/                  README.md, DESIGN.md (this file), LITERATURE.md, BASELINES.md, RUNBOOK.md (N1-N11 commands), notes/
results/<area>/neuro_<exp>/  finished runs, copied unchanged
```

- `hardware/tb/common.py` hard-codes `test_dir`, and `vivado_ooc.tcl` globs only `hardware/rtl/*.v`. Paper 2 uses
  its own `common_nv.py` and TCL rather than editing these shared files.
- `make test` collects `hardware/tb/neuro/test_nv_*.py` via pytest recursion. Basenames are unique thanks to the
  `nv_` prefix. Default cases are small (§7.2) so that `make test` stays near its 40 s budget; large cases run
  with `FULL=1` / `RUN_SLOW=1`.

**Entry points.**
- Model and RTL (L): `python -m pytest tests/test_neuro_*.py hardware/tb/neuro/`
- One RTL test: `make one T=hardware/tb/neuro/test_nv_feistel.py::test_nv_feistel SEED=<n>`
- Kaggle (K): paste `software/system/kaggle/kaggle_neuro.py` into one cell. `QUICK=True` is a 20-minute smoke
  run with the §8.4 assertions; steps run the N5 count cache, N3, N6 and N4, GPU steps last, and `checkpoint()`
  runs after each step.
- Vivado (V, only when the PC is free of paper-1 runs):
  `python hardware/vivado/neuro/run_vivado_neuro.py --steps ooc lanes bd power parse`
- Board (B): `sudo -E python3 -m system.board.neuro.nv_first_contact --bitfile overlay/neuro/nv.bit`, then
  `... nv_replay --file <rec.raw> --udp <host>:<port> --timed`. Both have a `--mock` path that is tested on the
  laptop first.

Order of work: BASELINES.md from the PDFs → model + tests → vectors → RTL module by module (N1) → N4b, N7, N8,
N9, N11 on the laptop → Kaggle N5 cache, N3, N6, N4 → Vivado N2 → board N10. Paper 1's board day takes precedence
over every paper-2 step.

---

## 11. Changelog

| Date | Change | Why |
|---|---|---|
| 2026-11-06 | n1 draft | From notes. Changes from the draft plan: T = 1024 µs (multiple of 64); event count moved to the trailer; mixed-radix Feistel instead of cycle walking; subkeys for domain separation; padding only at V3/V4 |
| 2026-11-07 | n1 revision 2 (review) | Receiver state moves only after the tag (read-only replay check, bounded epoch peek, `EventRatchet` rooted at `nv1-events`); keys bound to the boot (kex profile; ctx table with distinct ctx per key); header 48 B with FIRST/FINAL flags and `link` (tail and epoch-boundary deletion detectable); trailer fixed fields last (unique parse); exact receiver profile instead of a minimum level; PAD only at V3 with b = 6 or V4, empty packets padded, mask bits interleaved in the same K_dum stream (1 per CD word, before each dummy's 39 content bits), MAX_CD_PAD; time-jump rule; one shadow set with COMMIT_AT and counter-rewind refusal; pipeline reordered (stalling units before the Feistel, in-band header/trailer, credit gate, 35-bit FIFO); tag32 look-ahead and ENC backpressure; SDP RAM template; 64-bit counters with SNAP; VERSION build byte; register map renumbered; W, H ≥ 16 at V2/V3; lanes limited to V0/V2; claims narrowed ((iii) payload, (iv) measured throughput) with pass criteria; experiments reworked (Event-ReId mandatory, N4b, N11, cluster statistics, Kaggle budget) |

---

## 12. References (keys; full table with verification status in `docs/neuro/LITERATURE.md`)

Legend:
- (no mark): verified at full text or at the source page.
- †: verified at abstract or landing page only; cite only for what the abstract states.
- ᴹ: bibliographic metadata verified (OpenAlex/Crossref); cite as the source of a dataset, not for content.

UNVERIFIED items in the notes are **not** cited (Luby-Rackoff content, Patarin 2003/2004, Beyne 2021, Agbeyibor
2014, Perez-Resa 2020 content, NEUROSEC, TU Delft theses, Ahmad 2024 Access content, DVS128 rate, the
Scheerlinck complementary-filter paper until it is opened).

| Key | Reference | Note file |
|---|---|---|
| `du2021sensors` | Du et al., "Event Encryption for Neuromorphic Vision Sensors…", Sensors 21(13):4320, 2021, doi 10.3390/s21134320 | lit_event_encryption, lit_privacy_attacks |
| `zhang2024nce` | Zhang, Zhu, Lam, "Event encryption: rethinking privacy exposure for neuromorphic imaging", Neuromorph. Comput. Eng. 4(1):014002, 2024, doi 10.1088/2634-4386/ad207b | same |
| `bao2026secam` | Bao, Shi, Zhai, Wang, "Asynchronous temporal mapping … hardware-level privacy with event cameras", Commun. Eng. 5:136, 2026, doi 10.1038/s44172-026-00687-4 | lit_event_encryption |
| `rebecq2019cvpr`†, `rebecq2021tpami`† | E2VID, CVPR 2019 (doi 10.1109/CVPR.2019.00398); TPAMI 43(6), 2021 (doi 10.1109/TPAMI.2019.2963386) | lit_privacy_attacks |
| `scheerlinck2020wacv`† | FireNet, WACV 2020, doi 10.1109/WACV45572.2020.9093366 | same |
| `stoffregen2020eccv`† | Reducing the Sim-to-Real Gap (E2VID+/FireNet+, HQF), ECCV 2020, arXiv 2003.09078 | same |
| `ahmad2023iccv` | Ahmad, Morerio, Del Bue, ICCV 2023, doi 10.1109/ICCV51070.2023.01022; Event-ReId doi 10.5281/zenodo.8256439 | same |
| `adra2025iwbf` | Adra, Dugelay, E2PRIV, IWBF 2025, doi 10.1109/IWBF63717.2025.11113401 | same |
| `marchisio2021ijcnn`† | DVS-Attacks, IJCNN 2021, arXiv 2107.00415 | lit_event_encryption |
| `wang2024eccv`† | Event Trojan, ECCV 2024, arXiv 2407.06838 | same |
| `bendig2025wacv`†, `muller2026lovif`†, `meng2026eventface`† | AnonyNoise; Generative Anonymization; EventFace (related work) | lit_privacy_attacks |
| `black2002ctrsa` | Black, Rogaway, "Ciphers with Arbitrary Finite Domains", CT-RSA 2002, doi 10.1007/3-540-45760-7_9 | lit_fpe_crypto |
| `nist2025sp80038gr1` | Dworkin, Mouha, NIST SP 800-38G Rev. 1 2pd, Feb 2025 | same |
| `bellare2009sac`† | Bellare, Ristenpart, Rogaway, Stegers, "Format-Preserving Encryption", SAC 2009 (landing page) | lit_event_encryption |
| `hoang2012crypto` | Hoang, Morris, Rogaway, swap-or-not, CRYPTO 2012, doi 10.1007/978-3-642-32009-5_1 | lit_fpe_crypto |
| `durak2017crypto`†, `durak2018acns`†, `bellare2016ccs`†, `hoang2018crypto`†, `hoang2019eurocrypt`† | small-domain FPE attacks (ePrint 2017/521, 2018/108, 2016/794, 2018/556, 2019/244) | same |
| `nist2025sp800232`† | NIST SP 800-232, Ascon, Aug 2025 (CSRC page; the implementation is checked against the official KATs in paper 1) | same |
| `prophesee_evt2` | Prophesee Metavision SDK 5.3.1 docs, "EVT 2.0 Format" | evt2_spec_verified |
| `hu2021v2e`† | Hu, Liu, Delbruck, v2e, CVPRW 2021, arXiv 2006.07722 | lit_formats_data |
| `fang2021iccv` | PLIF, ICCV 2021, doi 10.1109/ICCV48922.2021.00266 (arXiv HTML read) | same |
| `orchard2015fnins`ᴹ, `amir2017cvpr`ᴹ | N-MNIST (doi 10.3389/fnins.2015.00437); DVS Gesture (doi 10.1109/CVPR.2017.781; 96.5 % quoted from the IBM page only) | same |

---

## Appendix A. Review points not applied as written (review of 7 Nov 2026)

| Review point | What was done instead | Reason |
|---|---|---|
| Commit at "the first packet boundary whose table prefetch has not started" | Explicit `COMMIT_AT` counter; refused (LATE) unless ≥ open ctr + 2 | The suggested rule depends on fill timing, which the model cannot reproduce bit-exactly. A counter-defined rule gives the same safety (no stale bank, FINAL settable) and is exact in the model |
| Make the kex mandatory at every boot | Mandatory in the deployment profile; a PSK profile is kept for offline experiments with the reviewer's fallback conditions (base-bound root key, strictly increasing boot_id persisted at the receiver, cam_id unique per master, no random boot_id fallback) | N1 and N3-N9 run without a live peer; they need reproducible keys from a seed |
| Exact profile match including PAD_MIN / PAD_CAP from the header | (level, ts_bits, PAD, pad_policy) checked exactly from the header; PAD_MIN/PAD_CAP checked by **pad conformance** after stripping (each bucket's CD count must equal `bucket_target`) | Keeps the header at 48 B; conformance checks what the sender actually did, which is stronger than a header value |
| Dummy placement: (a) keyed interleaving or (b) state the leak | (b): tail placement kept, leak stated in §5.4/§9.2, N5 reports AUC for multiplicity, position and both | (a) needs a one-bucket buffer and a second placement stream; moved to §9.3 item 3 for n2 |
| Dummy ts for b < 6: require b = 6, or copy upper bits | Require b = 6 with PAD | Simpler in model and RTL; V3 default is b = 6 anyway |
| Bitmap mask "continues the same stream after the last dummy" | Same single K_dum stream, but the mask bits are **interleaved**: 1 mask bit per CD word in payload order, followed by the 39 content bits if the word is a dummy (§5.3) | The receiver does not know the dummy count before unmasking, so a mask that starts right after the last dummy could not be located. Interleaving fixes every bit position by payload order alone, keeps one generator and one nonce, and costs 1 bit/clk |
| Bitmap overflow: drop rule or config rejection | Drop rule (ERR_PADOVF) | The real rate is not known at configuration time |
| Second K_perm generator / per-lane K_pol sub-streams | Not in n1; L ≥ 2 limited to V0/V2; one stream each | Both change the model contract; deferred to n2 (§9.3 item 7) |
| ERR_JUMP at 0xB8 | ERR_JUMP at 0xE4 | The map was renumbered for the 64-bit counters and the shadow set |
| FINAL only in the first packet's `prev_epoch_last_ctr` (crypto review) and a final flag bit (evaluation review) | Both merged: flags FIRST/FINAL and an 8-byte `link` in every packet (prev last ctr in FIRST, ctr0 otherwise) | Carrying ctr0 in every packet lets the receiver pin t_origin even if the FIRST packet is lost |
| Event-Trojan-style trigger in N7 | Our own simple patch trigger, Event Trojan cited only for the threat | Event Trojan is verified at abstract level only (†), so its method is not reproduced |
| Move N5 to Kaggle | Data loading and count caching on Kaggle; analysis on the laptop from the `.npz` cache | Keeps GPU quota for N3/N4/N6 |
| DVS Gesture subject split "1-23 train, 24-29 test" | Use Tonic's official train/test files and record the subjects found in them in `meta` | The split numbers are not in our verified notes (Amir 2017 abstract not opened) |
