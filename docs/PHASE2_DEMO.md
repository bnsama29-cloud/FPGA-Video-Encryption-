# Phase 2 demo: what we show, who prepares what, and answers for the judges

Everything here works today with the simulated sender; on board day the PYNQ-Z2 replaces it and nothing
else changes. Setup and commands: `docs/DASHBOARD_LAN_DEMO.md` (laptop + second device + VLC, done by
Aravind) and `docs/FPGA_HANDS_ON.md` (the board).

## 1. The setup (three stations on one private LAN)

| Station | Runs | Shows |
|---|---|---|
| **PYNQ-Z2** (sender / camera) | `board_sender`: FPGA encodes, encrypts and tags; ARM adds headers and the E5 order | the board itself, its LEDs, the terminal with ms/frame |
| **Host laptop** (network + receiver) | `link.run_all --no-sender`: channel with the attacker, authenticated receiver, defence feedback, dashboard | dashboard on the projector |
| **Judge's laptop / phone** (viewer) | only a browser (and VLC) | `http://<HOST>:8000` and `http://<HOST>:8000/stream/wire.mjpg` |

Until the board arrives the host laptop also runs the sender (`py -m link.run_all ...`); the demo is the
same.

## 2. The 6-minute script

| Time | Do | Say (one line) | Audience sees |
|---|---|---|---|
| 0:00 | normal playback | "The FPGA encodes and encrypts inside the JPEG encoder; every frame carries a 128-bit Ascon tag." | Receiver view plays; *verified* counter rising, *rejected* 0 |
| 0:45 | open the wire stream in VLC on the judge's laptop | "Any standard player can play the stream, but without the key it only sees this." | scrambled video in VLC (format-compliant) |
| 1:30 | show the Eavesdropper tile at E2, then switch the level to E5 | "Encrypting signs and amplitudes still leaks the outline; E5 shuffles the blocks with a new key every frame." | outline visible at E2, gone at E5 |
| 2:30 | press **bit flip** | "Someone changes bits on the network." | red *rejected* count; receiver keeps the last good frame; level jumps to E5; alert in the log |
| 3:15 | press **replay**, then **downgrade** | "Old frames and a forged lower level are rejected too: the level is inside the tag." | rejections, threat score, rekey event |
| 4:00 | stop attacks | "When the evidence stops, protection returns to the floor level after 8 s." | level back to E2 |
| 4:30 | wrong key (restart the receiver side with a different key) | "A receiver without the right key accepts nothing: it never shows a wrongly decrypted picture." | every frame rejected at the tag check |
| 5:15 | board terminal: `first_contact` table | "On the board every frame is byte-identical to our golden model; this is the measured speed." | bit-exact = yes, ms/frame |

## 3. Who prepares what (before the board comes)

| Person | Task | Done when |
|---|---|---|
| 1 | LAN dashboard + VLC + firewall | ✅ done (Aravind, `docs/DASHBOARD_LAN_DEMO.md`); rehearse once on the college Wi-Fi |
| 2 | Tamper demo: run the script above twice end to end on the simulation; time it; note which attacks show the clearest effect; record a screen video as a fallback | a 6-minute run with no surprises, video saved |
| 3 | Board prep: SD card written, jumpers, `scripts/demo_key.py`, the run-7 `.bit` + `.hwh` on a USB stick and in the shared drive, `FPGA_HANDS_ON.md` §1–§7 dry-read | board boots and answers `ping` within 10 min of unboxing |
| 4 | Papers: author block, AI disclosure, read `access.pdf` §III–VI so everyone can explain the maths | each author can explain Lemma 1 and Proposition 2 |

## 4. Questions judges will ask (short answers)

**"Where do you enter the key?"** Nowhere on the dashboard, on purpose. Both ends are provisioned with the
same 128-bit key before the session (`py scripts\demo_key.py` makes a fresh one and prints the two
commands). Sending a key through a web page would be the insecure part of the system. Every published
scheme we compare with assumes a pre-shared key, as SRTP does; a key exchange (X25519 at session start
on the ARM) is listed as future work and needs no FPGA change.

**"What if a receiver has a wrong key?"** It rejects every frame at the tag check (measured: 0 accepted,
all rejected). It does not show a garbled picture as if it were real.

**"Can VLC decrypt it?"** No, and it does not need to. VLC shows that the stream is standard MJPEG
(format compliance); decryption and the tag check are done by our receiver. A VLC plug-in would be extra
integration work with no research value.

**"Can the judge's PC be the receiver?"** In this demo the judge's device is a viewer of our receiver.
An independent receiver needs our receiver software on that PC (Python, or a packaged executable); VLC
alone cannot verify Ascon tags. If they insist, run `link.run_all --no-sender` on their PC from a USB
copy of the repo.

**"What if someone edits the video after it is received?"** Out of scope: we protect the stream in
transit (confidentiality and integrity on the network). A decrypted file on a compromised PC is an
endpoint-security problem, as for TLS or SRTP.

**"Why not just use TLS / a VPN?"** TLS hides everything from every tool and costs cipher work on every
byte; ours keeps a playable standard stream, encrypts about a third of the payload bits at E5, costs zero
encoder cycles, and authenticates every frame with its metadata.

**"Is the shuffle not broken by a jigsaw solver?"** We ran two solvers, a chosen-plaintext attack and
two trained neural networks: all at chance on E5 (paper, Section IX).
