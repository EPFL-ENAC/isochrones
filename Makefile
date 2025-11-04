install:
	uv pip install -e .

test:
	uv run pytest -s