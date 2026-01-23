VENV := .venv
PY   := $(VENV)/bin/python3
PIP  := $(VENV)/bin/pip3

.PHONY: all install test lint clean

$(VENV):
	python3 -m venv $(VENV)

deps: $(VENV)
	$(PIP) install -e ".[test,lint]"

bootstrap: deps

# Development workflow

lint: deps
	$(VENV)/bin/flake8 lp_to_jira_sync tests

test: deps
	$(PY) -m pytest -q

clean:
	rm -rf $(VENV)