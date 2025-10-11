.PHONY: install lint test run

install:
	@pip install -e .[dev]

lint:
	@ruff check src tests
	@black --check src tests
	@mypy src

test:
	@pytest

run:
	@uvicorn src.main:app --reload --host $${HOST:-0.0.0.0} --port $${PORT:-8000}
