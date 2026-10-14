# cd paper && make           -> main.pdf (regenerates tables/figures from data/ first)
PY ?= python3
main.pdf: main.tex refs.bib tables/numbers.tex
	pdflatex -interaction=nonstopmode -halt-on-error main.tex > build.log
	bibtex main >> build.log
	pdflatex -interaction=nonstopmode -halt-on-error main.tex >> build.log
	pdflatex -interaction=nonstopmode -halt-on-error main.tex >> build.log
	@grep -c "TODO" main.tex | xargs -I{} echo "{} TODO markers in main.tex"
tables/numbers.tex: make_assets.py $(shell find data -name '*.json' -o -name '*.md' -o -name '*.txt' | head -400)
	$(PY) make_assets.py
tables: ; $(PY) make_assets.py
clean: ; rm -f *.aux *.bbl *.blg *.log *.out main.pdf
.PHONY: tables clean
