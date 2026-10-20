# cd paper && make           -> conference.pdf and access.pdf (regenerates tables/figures from data/ first)
#   conference.pdf   IEEEtran [conference], 6 pages including references
#   access.pdf       IEEE Access, full length (sections/access_*.tex)
PY ?= python3
SHARED = refs.bib tables/numbers.tex common/preamble.tex $(wildcard figures/tikz/*.tex)
all: conference.pdf access.pdf
conference.pdf: conference.tex $(SHARED)
	pdflatex -interaction=nonstopmode -halt-on-error conference.tex > build_conference.log
	bibtex conference >> build_conference.log
	pdflatex -interaction=nonstopmode -halt-on-error conference.tex >> build_conference.log
	pdflatex -interaction=nonstopmode -halt-on-error conference.tex >> build_conference.log
	@pdfinfo conference.pdf 2>/dev/null | grep Pages || true
	@grep -c "TODO" conference.tex | xargs -I{} echo "{} TODO markers in conference.tex"
access.pdf: access.tex $(wildcard sections/access_*.tex) ieeeaccess.cls $(SHARED)
	pdflatex -interaction=nonstopmode -halt-on-error access.tex > build_access.log
	bibtex access >> build_access.log
	pdflatex -interaction=nonstopmode -halt-on-error access.tex >> build_access.log
	pdflatex -interaction=nonstopmode -halt-on-error access.tex >> build_access.log
	@pdfinfo access.pdf 2>/dev/null | grep Pages || true
tables/numbers.tex: make_assets.py $(shell find data -name '*.json' -o -name '*.md' -o -name '*.txt' | head -400)
	$(PY) make_assets.py
tables: ; $(PY) make_assets.py
figures-tikz: ; $(PY) figures/tikz/gen_ascon_slice.py
clean: ; rm -f *.aux *.bbl *.blg *.log *.out conference.pdf access.pdf
.PHONY: all tables figures-tikz clean
