# The conference paper

`main.tex` is a complete first draft in the IEEE two-column conference format (IEEEtran), currently
6 pages with references. It reports what has been measured: RTL simulation, a Yosys area estimate
and the full system simulation. Everything that still waits for Vivado or the board is a red
`[TODO: ...]` in the PDF, so nothing unfinished can slip through.

## Build

```bash
cd paper
make tables      # tables/*.tex, tables/numbers.tex, figures/fig_*.pdf from data/  (python3)
make             # main.pdf (pdflatex + bibtex)
```

* **Requirements:** a TeX installation with `IEEEtran` (TeX Live: `texlive-publishers`), `booktabs`
  and `tikz`.
* **Overleaf:** upload the `paper/` folder after running `make tables` locally.

## How the numbers get into the paper

1. `paper/data/` is the snapshot of the results the paper is built from. It holds:
   * the Kaggle run of 14 Oct 2026 (`kaggle_complete.py`, 47 steps);
   * the one clip rerun noted in `data/run_log.json`;
   * the Yosys estimate in `data/yosys/`.
2. `make_assets.py` turns these files into:
   * the LaTeX tables in `tables/`;
   * the macros in `tables/numbers.tex` (e.g. `\TtmMean`), which the prose uses;
   * the figures in `figures/`.
3. **Never type a result into `main.tex`.** If a number in the text needs to change, change the data
   or the script. `tests/test_paper_assets.py` fails if `main.tex` uses an undefined number, or if the
   committed tables no longer match the data.
4. **New results:**
   * **Vivado:** copy `sim_out/vivado/vivado_results.json` to `data/vivado/`, and the resource table
     switches from the Yosys estimate to post-route automatically.
   * **Board:** copy the board results to `data/board/`, then write §VI's board paragraph from them.
   * After either, run `make tables && make`.

## Open items in the draft (search the PDF for "TODO")

| Where | What is needed | From |
|---|---|---|
| Author block | author order, initials, e-mails; whether the mentor is a co-author | team + mentor |
| §III-A | nonce-uniqueness argument, reboot behaviour | GUIDE.md B3 |
| §IV | XSim result; Table III post-route numbers | GUIDE.md 4.1 |
| Fig. 2 | an openly licensed real frame instead of the synthetic one | GUIDE.md B2 |
| §VI, last paragraph | ARM baseline, FPGA fps, energy per frame | GUIDE.md A1–A4, B1 |
| Acknowledgment | AI-assistance disclosure (below) | team |
| refs.bib | 3 small gaps marked `TODO` (pages/volume for Puech, Lin, Boyadjis) | IEEE Xplore / ScienceDirect |
| §II / §IV | comparison table with prior designs (numbers ready in GUIDE.md §7) | GUIDE.md B14, after Vivado |
| §V | standard image-encryption metrics (key sensitivity, NPCR/UACI, entropy, histograms) | GUIDE.md B13 |

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
* **Figures and tables** are all our own, generated from our data. The movie trailers we tested on
  are copyrighted: the paper reports numbers only and shows no frames from them (GUIDE.md B2).
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
