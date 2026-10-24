# The papers

Three manuscripts are built from the same data, figures and bibliography:

| File | Format | What it is |
|---|---|---|
| `conference.tex` | IEEEtran `[conference]`, 6 pages including references | the conference version (IEEE ICCE 2027) |
| `tce.tex` + `sections/access_*.tex` | IEEEtran `[journal]` | the journal version for the IEEE Transactions on Consumer Electronics (8 pages without overlength charges): the conference paper extended with the proofs, the board evaluation, the full benchmark and the protocol analysis |
| `access.tex` + the same sections | IEEE Access (`ieeeaccess.cls`) | the same journal text in the IEEE Access format (no page limit) |

Shared: `common/preamble.tex` (packages, notation), `figures/tikz/*.tex` (architecture, datapath, block design,
key hierarchy, E5 flow, drawn from the RTL), `figures/netlist/` (gate-level schematics generated from
Verilog), `figures/fig_*.pdf` and `tables/*.tex` (generated), `refs.bib`.

## Build

```bash
python paper/make_assets.py      # tables/*.tex, tables/numbers.tex, figures/fig_*.pdf from data/
cd paper && make                 # conference.pdf and access.pdf (pdflatex + bibtex)
make schematics                  # gate-level figures from Verilog: Yosys -> netlistsvg (optional)
```

A TeX installation with `IEEEtran`, `booktabs`, `tikz`, `circuitikz` and `algorithmicx` is needed. For
Overleaf, `python paper/make_overleaf.py` writes a self-contained project of each paper
(`overleaf/conference.zip`, `overleaf/tce.zip`, `overleaf/access.zip`; compiler pdfLaTeX).

## How the numbers get into the papers

1. `data/` is the snapshot of the results the papers are built from; each folder's `README.md` names the run,
   the script and the commit that produced it.
2. `make_assets.py` turns these files into the tables in `tables/`, the figures `figures/fig_*.pdf`, and the
   macros in `tables/numbers.tex` (e.g. `\TtmMean`) that the prose uses. Derived constants of the analysis
   (`\PermBitsQVGA` = log2 300!, the lane bounds, the boot-collision bound) are computed there too.
3. No result is typed into a `.tex` file. `tests/test_paper_assets.py` fails if a paper uses an undefined
   number, if a committed table no longer matches the data, or if a reference is cited by no paper.

## Figures drawn by hand and what they must match

| Figure | File | Source of truth |
|---|---|---|
| System architecture | `figures/tikz/arch_system.tex` | `system/board/block_design.tcl`, `pynq_driver.py`, `link/` |
| Fabric datapath | `figures/tikz/arch_pl.tex` | `rtl/secure_jpeg_lanes_top.v`, `rtl/encoder_lane.v` (bus widths = port widths) |
| Gate-level encryption bit slice | `figures/fig_selective_enc_bitslice.pdf` (generated) | `figures/netlist/selective_enc_bitslice.v` = one bit of `rtl/selective_enc.v`; `tests/test_paper_figures.py` checks it exhaustively against the model |
| Ascon round bit slice | `figures/fig_ascon_sbox_slice.pdf` (generated) | `figures/netlist/ascon_sbox_slice.v` = one slice of `rtl/ascon_round.v`; the same test checks 64 slices + linear layer against a model round |
| PYNQ-Z2 block design | `figures/tikz/zynq_bd.tex` | `system/board/block_design.tcl` |
| Key and nonce hierarchy | `figures/tikz/keys.tex` | `link/keys.py`, `model/ascon.py`, `model/hw.py` |
| E5 hardware form | `figures/tikz/e5_flow.tex` | `docs/INTERFACES.md` §8.6 |

## References

Every entry in `refs.bib` carries a comment saying where it was verified (publisher page, NIST, arXiv or the
authors' page).

## Media

All figures and tables are generated from our own data. The private clips are reported as numbers only; no
frame of them appears. The frame in the visual comparison is from the Sintel trailer (© Blender Foundation,
CC BY 3.0), credited in its caption.

## IEEE Access template

`access.tex` uses `ieeeaccess.cls` and `access/*.png` from the IEEE Access LaTeX template, unmodified. Two
workarounds live in `access.tex`: the class redefines the TeX primitive `\year` (pgf and `\today` need it),
and its spot colour is written without a colour space, so the blue is redefined in CMYK. The template's
commercial fonts fall back to standard ones.
