# local-shazam

A CLI tool

## Development

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov

# Type checking
uv run mypy src

# Linting and formatting
uv run ruff check src tests
uv run ruff format src tests

# Run the CLI
uv run local-shazam

# Install pre-commit hooks
uv run pre-commit install
```

## Before Creating PR

```bash
uv run ruff check src && uv run mypy src && uv run pytest
```
