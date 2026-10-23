# The papers

Two papers are built from the same data, figures and bibliography:

| File | Format | Length | What it is for |
|---|---|---|---|
| `conference.tex` → `conference.pdf` | IEEEtran `[conference]` | **exactly 6 pages** incl. references | the conference submission: condensed, figure-led, short reference list |
| `access.tex` + `sections/access_*.tex` → `access.pdf` | IEEE Access (`ieeeaccess.cls`) | 24 pages | the journal version: every derivation (lemmas, propositions, algorithms), every experiment, every table |

Shared: `common/preamble.tex` (packages, notation macros), `figures/tikz/*.tex` (architecture, datapath,
block design, key hierarchy, E5 flow: TikZ from the RTL), `figures/netlist/` (gate-level schematics
generated from Verilog),
`figures/fig_*.pdf` and `tables/*.tex` (generated), `refs.bib`.

## Build

```bash
cd paper
make tables      # tables/*.tex, tables/numbers.tex, figures/fig_*.pdf from data/  (python3)
make             # conference.pdf and access.pdf (pdflatex + bibtex); or make conference.pdf / make access.pdf
make schematics     # gate-level figures from Verilog: figures/netlist/*.v -> Yosys -> netlistsvg -> fig_*_slice.pdf
                    # (pip install yowasp-yosys cairosvg; npm install -g netlistsvg)
```

* **Requirements:** a TeX installation with `IEEEtran` (TeX Live: `texlive-publishers`), `booktabs`,
  `tikz`, `circuitikz`, `algorithmicx` (`texlive-science`, `texlive-pictures`).
* **Overleaf:** `python paper/make_overleaf.py` writes `overleaf/conference/` and `overleaf/access/` (only the
  files each paper needs) and `overleaf/conference.zip`, `overleaf/access.zip`. On Overleaf: New Project →
  Upload Project → the zip; compiler pdfLaTeX. Rerun the script after every change; never edit the copies.
* **Page limit.** Check `pdfinfo conference.pdf` after every edit of `conference.tex`: it must stay at 6.
  To make room, cut sentences or move detail to `access.tex`; never shrink fonts or margins.

## How the numbers get into the papers

1. `paper/data/` is the snapshot of the results the papers are built from (Kaggle runs, Vivado runs,
   RTL throughput, SVE-Bench, hardware efficiency; see `data/*/README.md`).
2. `make_assets.py` turns these files into:
   * the LaTeX tables in `tables/`;
   * the macros in `tables/numbers.tex` (e.g. `\TtmMean`), which the prose uses; this includes derived
     constants of the analysis (`\PermBitsQVGA` = log2 of 300!, the lane bounds `\BoundFourMpix`, the
     boot-collision bound `\BootCollide`), so even those are computed, not typed;
   * the figures `figures/fig_*.pdf`.
3. **Never type a result into a `.tex` file.** If a number in the text needs to change, change the data
   or the script. `tests/test_paper_assets.py` fails if either paper uses an undefined number, if the
   committed tables no longer match the data, or if a reference is cited by neither paper.
4. **New results:**
   * **Vivado:** copy `sim_out/vivado/vivado_results.json` to `data/vivado/`.
   * **Board:** copy the board results to `data/board/`, then replace the red `\TODO{A1--A4 ...}` in
     `sections/access_08_hwresults.tex` (Section VIII-D) and the limitation sentence of `conference.tex`.
   * After either, run `make tables && make`.

## Hand-drawn figures (TikZ) and what they must match

| Figure | File | Source of truth |
|---|---|---|
| System architecture | `figures/tikz/arch_system.tex` | `future_work/board/block_design.tcl`, `pynq_driver.py`, `link/` |
| Fabric datapath | `figures/tikz/arch_pl.tex` | `rtl/secure_jpeg_lanes_top.v`, `rtl/encoder_lane.v` (bus widths = port widths) |
| Gate-level encryption bit slice | `figures/fig_selective_enc_bitslice.pdf` (**generated**, `make schematics`) | `figures/netlist/selective_enc_bitslice.v` = one bit of `rtl/selective_enc.v`; `tests/test_paper_figures.py` checks it exhaustively against the golden model |
| Ascon round bit slice | `figures/fig_ascon_sbox_slice.pdf` (**generated**) | `figures/netlist/ascon_sbox_slice.v` = one slice of `rtl/ascon_round.v`; the same test checks 64 slices + linear layer against a model round |
| PYNQ-Z2 block design | `figures/tikz/zynq_bd.tex` | `future_work/board/block_design.tcl` |
| Key and nonce hierarchy | `figures/tikz/keys.tex` | `link/keys.py`, `model/ascon.py`, `model/hw.py` |
| E5 hardware form | `figures/tikz/e5_flow.tex` | `docs/INTERFACES.md` §8.6 |

If you change the RTL or the block design, update the figure in the same commit.

## Open items (search the PDFs for "TODO")

| Where | What is needed | From |
|---|---|---|
| Author block (both) | author order, initials, e-mails; whether the mentor is a co-author | team + mentor |
| access §VIII-D, conference §VII | board bit-exact gate, fps with DMA, ARM baseline, power, energy per frame | GUIDE.md A1–A4, `docs/FPGA_HANDS_ON.md` |
| access Table 1 (our row) | the same board items | as above |
| Acknowledgment (both) | AI-assistance disclosure (below) | team |
| access front matter | biographies + photos, IEEE membership, funding line, corresponding author | team |
| refs.bib | small gaps marked `TODO` (pages/DOI: Lin, Hirose, Puech, Wampler, Farahmand) | IEEE Xplore / ScienceDirect |

## References: how they were checked

Every entry in `refs.bib` has a comment saying where it was verified on 14 Oct 2026: publisher page,
NIST, arXiv, or the authors' institutional page. Before submission:

* open every DOI once more and fill in the three gaps marked `TODO`;
* check the spelling of "Benedetti" against the ACIVS 2002 PDF;
* **cite only papers someone on the team has actually read**, at least the abstract and the part
  you cite. If you add a reference, add a "checked:" comment too.

## Originality, plagiarism and AI assistance

* **Wording.** The draft was written from our own results and design documents, not adapted from
  other papers. Still, every author must read it, rewrite passages in their own words where they
  would explain it differently, and be able to defend every sentence in a viva.
* **Plagiarism check.** Run the final PDF through the plagiarism checker your institution provides
  (RVCE library: Turnitin or iThenticate) before submission; most IEEE conferences also check with
  iThenticate (CrossCheck). Paraphrasing a source is still citing it.
* **Figures and tables** are all our own, generated from our data. The four private clips we tested on
  are copyrighted: the paper reports numbers only and shows no frames from them. Fig. 2 shows a frame
  of the Sintel trailer (© Blender Foundation, CC BY 3.0); the licence requires the attribution that
  is in its caption. Keep it there.
* **AI assistance.** IEEE's policy is that AI-generated content (text, code, figures) must be
  disclosed in the acknowledgments, naming the tool and the sections where it was used; AI tools
  cannot be listed as authors. Check the specific conference's call for papers as well. Fill in the
  acknowledgment TODO honestly. Example: "Parts of the software, test scaffolding and the first draft
  of this manuscript were prepared with the assistance of an AI system (Claude, Anthropic); all
  content was reviewed, verified and revised by the authors."
* **Do not** use paraphrasing or "humanizer" tools to disguise AI-written text. Detectors are
  unreliable, and the disclosure above is what keeps you safe. Your own rewriting and
  understanding of the text is what reviewers and the viva care about.

## Choosing a venue

* **Fit.** The work fits a conference on VLSI/embedded systems, multimedia security, or IoT security.
* **Timing.** For a 15 Dec 2026 deadline, check the IEEE conference calendar (conferences.ieee.org)
  for calls closing mid-December and use their page limit. The draft is 6 pages, the most common
  limit.
* **Format.** Most IEEE conferences use this exact template. Some require the compsoc or A4 variant;
  change only the `\documentclass` options.

## IEEE Access template notes

`access.tex` uses `ieeeaccess.cls` and `access/*.png` from the IEEE Access LaTeX template, unmodified.
Two workarounds live in `access.tex`, not in the class: the class redefines the TeX primitive `\year`
(pgf and `\today` need it), and its PANTONE spot colour is written without a colour space, so the blue is
redefined as its CMYK equivalent. The template's commercial fonts fall back to standard ones (harmless
font warnings in the log).
