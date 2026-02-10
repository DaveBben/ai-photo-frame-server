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

Run: `uv run ruff check src && uv run mypy src && uv run pytest`
