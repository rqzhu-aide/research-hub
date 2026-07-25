.PHONY: help venv install install-dev init run test check clean

PYTHON ?= python
VENV   ?= .venv
PIP    := $(VENV)/bin/pip

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

venv: ## Create the virtual environment
	$(PYTHON) -m venv $(VENV)

install: venv ## Install runtime dependencies
	$(PIP) install -r requirements.txt

install-dev: venv ## Install runtime + test dependencies
	$(PIP) install -r requirements-dev.txt

init: ## Initialize (or migrate) the hub database
	$(VENV)/bin/python hub.py init

run: ## Start the local web UI (http://127.0.0.1:5055)
	$(VENV)/bin/python webapp.py

test: ## Run the full test suite
	$(VENV)/bin/python -m pytest

check: ## Validate the shipped config.yaml
	$(VENV)/bin/python -c "import hub; hub.load_config(); print('config.yaml: OK')"

clean: ## Remove caches and compiled files
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache
