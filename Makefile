# AudioAtlas dev tasks. Run `make help` for the menu.

PY ?= python
VENV ?= .venv
VENV_BIN := $(VENV)/bin
DEMO_OUT ?= reports/_demo
GOLDEN_WAV := tests/fixtures/sine_1k_-6dbfs_2s.wav
CALIBRATION_REPORTS ?= private_calibration/reports
CALIBRATION_REVIEW ?= private_calibration/finding_review.csv
CALIBRATION_MAP ?= private_calibration/private_asset_map.csv

.PHONY: help venv install test lint check demo golden calibration-fixtures calibration-review clean

help:  ## Show this help.
	@grep -E '^[a-zA-Z_-]+:.*?##' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?##"} {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

venv:  ## Create a local virtualenv at $(VENV).
	$(PY) -m venv $(VENV)
	@echo "Activate it with: . $(VENV_BIN)/activate"

install:  ## Editable install with dev extras (assumes $(VENV) is active).
	pip install -e ".[dev]"

test:  ## Run the test suite.
	pytest

lint:  ## Run ruff.
	ruff check .

check: test lint  ## Run tests and lint (the pre-commit gate).

demo:  ## Analyze the golden fixture and write a report to $(DEMO_OUT).
	@mkdir -p $(dir $(DEMO_OUT))
	audioatlas analyze $(GOLDEN_WAV) --out $(DEMO_OUT)
	@echo
	@echo "Wrote $(DEMO_OUT). Open $(DEMO_OUT)/report.md."

golden:  ## Regenerate the golden WAV + expected JSON.
	$(PY) tests/fixtures/_build_golden.py

calibration-fixtures:  ## Generate rights-safe deterministic calibration audio.
	$(PY) scripts/generate_calibration_fixtures.py

calibration-review:  ## Seed an anonymous review CSV from $(CALIBRATION_REPORTS).
	$(PY) scripts/prepare_calibration_review.py $(CALIBRATION_REPORTS) \
		--out $(CALIBRATION_REVIEW) --private-map $(CALIBRATION_MAP)

clean:  ## Remove caches, builds, demo outputs.
	rm -rf .pytest_cache .ruff_cache .mypy_cache
	rm -rf build dist *.egg-info src/*.egg-info
	rm -rf $(DEMO_OUT) reports/_*
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
