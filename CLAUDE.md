# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project Overview

A CLI tool

## Development Commands

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest

# Run single test file
uv run pytest tests/test_local_shazam.py

# Run tests with coverage
uv run pytest --cov

# Type checking
uv run mypy src

# Linting and formatting
uv run ruff check src tests
uv run ruff format src tests

# Run the CLI
uv run local-shazam
```

## Architecture

TODO: Document your architecture here.

## Key Dependencies

- **httpx**: HTTP client for API calls
- **pydantic-settings**: Configuration management
- **structlog**: Structured logging

## Configuration

- Log level controlled via `LOG_LEVEL` environment variable

## Before Creating PR

Run: `./check` (or `./check --offline` without network, which skips pip-audit). The commit hook and CI run the same steps.

Silencing a check is not passing it. Disabling a rule, loosening a config, weakening an assertion, or skipping a test to reach green is not a fix.

## Mutation Testing

- **Apply mutations to `src/local_shazam/pipeline.py` by hand:** every mutmut mutant there ends as "segfault" on the developer's machine, so `scripts/mutate-changed` reports nothing for it. Edit the line, run the test that should catch it, confirm it goes red, restore the file. Cause not established; a mutmut run in CI would show whether the crash is local.
