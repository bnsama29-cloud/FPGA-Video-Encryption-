# docs: specification and method

| File | Contents |
|---|---|
| `INTERFACES.md` | The specification: handshake convention, AXI4-Lite register map, nonce layout, tag, keystream order, JPEG container (contract v2 and v3), link configuration. Kept in sync with every interface change. |
| `TESTING.md` | Verification method and the bug log: every defect found, its root cause, fix and regression test. |
| `BENCHMARK_METHOD.md` | How SVE-Bench scores every scheme the same way, and the references it re-implements. |
| `JOURNAL_RUNBOOK.md` | The journal experiments X1–X30 in order: the software phase (laptop, Vivado, simulation), then the board phase, then the paper phase, each with its command and output folder. |
| `LITERATURE.md` | The papers each journal experiment is measured against, each checked at its source (DOI), and the gaps still open. |
| `RESEARCH.md` | Research notes R1-R8: throughput, lanes, rate control, change-driven coding, clock limits, size side channel, chosen plaintext; what held and what did not. |
| `neuro/` | Paper 2 (event-camera encryption, branch `neuromorphic`): `README.md` (overview), `DESIGN.md` (contract n1), `LITERATURE.md` (verified references), `notes/` (source notes). |
