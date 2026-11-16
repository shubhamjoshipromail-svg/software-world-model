# Common tasks. `make help` lists them. APP is one of: invoiceninja dolibarr odoo17 odoo18
APP ?= odoo17
PY  ?= .venv/bin/python
PYTHON ?= $(shell for p in python3.12 python3.11 python3.10; do command -v $$p && break; done)

.PHONY: help install doctor up down smoke report test
help:            ## show this list
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | sed -E 's/:.*## /\t/'
install:         ## create .venv (Python 3.10-3.12), install the package and the Chromium browser
	@if command -v uv >/dev/null 2>&1; then \
		uv venv --python 3.12 .venv && uv pip install -q -p .venv -e ".[dev]"; \
	elif [ -n "$(PYTHON)" ]; then \
		$(PYTHON) -m venv .venv && $(PY) -m pip install -q --upgrade pip && $(PY) -m pip install -q -e ".[dev]"; \
	else \
		echo "Need Python 3.10, 3.11 or 3.12 (3.13 is not supported yet), or install uv: https://docs.astral.sh/uv/"; exit 1; \
	fi
	$(PY) -m playwright install chromium
doctor:          ## check Docker, browser, model key and disk space
	$(PY) -m swm.cli doctor
up:              ## start and seed APP (default odoo17)
	$(PY) -m swm.cli up $(APP)
down:            ## stop APP and delete its containers
	$(PY) -m swm.cli down $(APP)
smoke:           ## run one task per skill on APP with the default model
	$(PY) -m swm.cli run --app $(APP) --per-skill 1 --tag smoke/$(APP)/clean
report:          ## rebuild the published tables from results/phase0_episodes.jsonl
	$(PY) -m swm.cli report --from results/phase0_episodes.jsonl
test:            ## unit tests (no Docker, no API key)
	$(PY) -m pytest -q
