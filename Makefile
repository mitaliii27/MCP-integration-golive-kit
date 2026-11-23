.PHONY: install test sim charts docs
install: ; pip install -r requirements.txt
test:    ; python -m pytest -q
sim:     ; python -m integration.simulate
charts:  ; python scripts/make_charts.py
docs:    ; python scripts/make_docs.py
