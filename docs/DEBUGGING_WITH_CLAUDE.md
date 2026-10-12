# Resolving errors with the help of Claude

Claude is most useful when it gets the same evidence a good TA would want: **what failed, where it first went wrong, the code involved, the reference it should match, and what you changed last**. This repository is built to produce exactly that evidence automatically.

## 1. The five-step loop (use it every time)

1. **Reproduce.** Note the seed from the log (`random seed = N`) and rerun with `make one T=<test> SEED=N`. A bug you cannot reproduce cannot be fixed reliably.
2. **Localise.** Read the assertion: every test reports the *first* mismatch (block, index, input, got, expected). For a top-level failure, find which stage diverges first (unit tests of each stage, or `make vectors` and compare stage files).
3. **Package.** `make bundle T=<test> SEED=N` writes `debug_bundle.md`: environment, command, seed, failure lines, log tail, the RTL under test, the golden-model functions it must match, and the testbench. Edit its first line ("What I changed last: …").
4. **Ask** (section 2), using a template from section 3.
5. **Verify the answer yourself.** Apply the fix, rerun the failing test with the same seed, run `make test`, and add a test that would have caught the bug (and a line in docs/TESTING.md §8). Do not accept an explanation that does not name a specific line and a specific clock cycle or value.

## 2. Three ways to ask

**a) Claude chat (claude.ai), simplest.** Attach `debug_bundle.md` (≈10–40 KB) and ask. Keep this repository's `README.md` and `docs/INTERFACES.md` in your Claude Project's knowledge so every chat starts with the register map, stream formats and arithmetic contract. Add a GTKWave screenshot when timing is involved (select the handshake signals of the failing stage, zoom to the cycle in the error message).

**b) Claude Code in WSL, best for this repository.** Claude Code works inside the repo, runs `make` itself, reads the logs and edits files, so it can do the reproduce → fix → re-run loop for you. It needs a paid Claude plan (the free plan does not include it) and WSL 2.

```bash
# inside the WSL terminal (not PowerShell)
curl -fsSL https://claude.ai/install.sh | bash
cd ~/secure-jpeg-sim && source .venv/bin/activate
claude
```

Setup details: https://code.claude.com/docs/en/setup. The file `CLAUDE.md` in the repo root is read automatically and tells Claude Code the rules of this project (the model is the referee, never edit generated files, run `make test` before declaring success). Review every diff it proposes before accepting; it is your design and your viva.

**c) VS Code.** If you work in VS Code (WSL window), you can run Claude Code in the integrated terminal and keep the waveform and source side by side.

## 3. Prompt templates

**Failing unit test**
> `make one T=tb/test_dct_quant.py::test_dct8x8 SEED=4242` fails: "block 3: first mismatch at index 9: got -14 expected -13". Bundle attached. I last changed the rounding in dct_stage.v. Find the root cause (exact line), propose the smallest fix, and tell me which signal at which time in `sim_build/dct8x8/dct8x8.fst` will confirm it.

**Test hangs / `TimeoutError: collect_stream timed out`**
> The top-level test times out after 2,000,000 cycles with 0 output words; unit tests all pass. A deadlock between stages is likely. Bundle attached. Which valid/ready pair should I look at first, and what condition could keep a `full[]` flag set forever?

**Passes alone, fails with stalls**
> The test passes with `p_stall=0` but fails with random backpressure. Check whether any output changes while `valid && !ready` (AXI hold rule) and whether a `go`/`take` condition ignores `ready`.

**Vivado synthesis or timing**
> Vivado OOC synthesis of secure_jpeg_top on xc7z020clg400-1 at 100 MHz: WNS = -2.3 ns; the worst path (from timing.txt below) goes from u_dct/u_cols/rsel to out_data. Propose a pipelining change to dct_stage.v that keeps the same output order and arithmetic, and the testbench changes needed (if any).

**Board result differs from simulation**
> On the PYNQ-Z2, OUT_BYTES = 1141 as in `vectors/scene_64x64_q75_m2/config.txt`, but scan bytes differ from `scan.bin` from offset 512. Simulation passes. What board-level causes (DMA buffer caching, word order, clock/reset) should I check, in order?

**Understanding, not fixing**
> Explain, cycle by cycle, how `bit_packer.v` handles a 0xFF byte followed by the frame's last bits. I need to present this in my review.

**New test**
> Write a cocotb test for `tag_unit.v` that checks a tampered byte in the middle of a frame changes the tag, using `tb/common.py` helpers and `model.ascon.mac` as the reference.

## 4. What to include, what to leave out

Include: the exact error text, the first mismatch, the seed, the RTL module, the matching model function, the testbench, versions (the bundle does all this), and *one sentence on what you changed last*: it is usually the cause.

Leave out: 10,000-line logs (the bundle keeps the tail), the 260 KB KAT file, `sim_build/`, binary files. Never paste real keys from a deployment; the test keys here are fine.

## 5. Common errors and their usual causes

| Error / symptom | Usual cause | First thing to try |
|---|---|---|
| `ModuleNotFoundError: No module named 'model'` or `cocotb` | not in repo root, or venv not active | `cd ~/secure-jpeg-sim && source .venv/bin/activate` |
| `Can't convert LogicArray to int: it contains non-0/1 values` | X/Z reaching an output: register without reset, undriven wire, port not connected | look for the signal in the waveform at the failing time; add a reset value |
| `TimeoutError ... collect_stream` | handshake deadlock or an `flast`/`last` never generated | trace valid/ready of each stage from the output backwards; the first stage holding `valid=1, ready=0` forever is the culprit |
| first mismatch at index 0 of every block | stage misaligned (counter not reset per block / frame) | check `idx`/`wptr` reset and `blast` handling |
| mismatch only for negative values | unsigned arithmetic: one unsigned operand makes the whole Verilog expression unsigned | use `$signed()` on every operand, check `>>>` vs `>>` |
| passes without stalls, fails with stalls | output changed while `valid && !ready`, or input accepted without `ready` | gate every register update with the handshake |
| off-by-one-cycle mismatch in a testbench that reacts to DUT outputs | sampling right after `RisingEdge` returns pre-edge values | decide at `FallingEdge` (+ `ReadOnly`), see TESTING.md §3 |
| `Unable to open input file "dct_coeffs.vh"` / `include not found` | include path missing | Icarus: runner uses `rtl/include`; Vivado: `-include_dirs rtl/include`; regenerate with `make tables` |
| JPEG will not open but matches the model | the model or the header is wrong | `make test-model`; open `vectors/*/frame.jpg` |
| receiver: `invalid Huffman code` | scan corrupted, wrong frame size, or marker parsing | compare scan with the model; never byte-search for markers |
| receiver: `tag-mismatch` on an untouched frame | key/nonce word order, or tag computed over different bytes than sent | compare `config.txt` N_MAC with the registers; tag is over stuffed bytes |
| `iverilog: ... syntax error` on SystemVerilog keywords | file uses SV in a Verilog flow | keep RTL Verilog-2001 (`reg`/`wire`, no `logic`) or add `-g2012` |
| Python on the board cannot find an IP | `.bit` and `.hwh` from different builds | copy both from the same Vivado run |

## 6. Ground rules (worth agreeing as a team)

* The golden model is the referee. Change it only if it disagrees with ITU-T T.81 or NIST SP 800-232, and then explain why in the commit.
* Generated files (`rtl/include/*.vh`, `hls/dct_coeffs.h`) are never edited by hand: `make tables`.
* A fix is not done until the same seed passes, `make test` passes, and a regression test exists.
* Ask Claude to explain the fix in terms you can defend in a review; if you cannot explain it, do not merge it.
