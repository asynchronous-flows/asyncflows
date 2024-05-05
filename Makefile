schema:
	python asyncflows/scripts/generate_config_schema.py

type:
	pyright asyncflows

test:
	pytest asyncflows

test-no-skip:
	pytest --disallow-skip

test-fast:
	pytest -m "not slow" asyncflows

test-config:
	pytest asyncflows/tests/test_config.py asyncflows/tests/static_typing/test_workflow.py

lint:
	ruff check --fix

format:
	ruff format

all: schema format lint type test-fast
