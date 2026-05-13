.PHONY: setup

setup:
	test -d venv || python3 -m venv venv
	venv/bin/pip install -r requirements.txt -r requirements-dev.txt
	venv/bin/pre-commit install
	venv/bin/pre-commit install --hook-type pre-push
