# syntax=docker/dockerfile:1
# Production-ready multi-stage Dockerfile for Python applications with uv
# https://docs.astral.sh/uv/guides/integration/docker/

# ------------------------------------------------------------------------------
# Build stage: Install dependencies and compile bytecode
# ------------------------------------------------------------------------------
FROM ghcr.io/astral-sh/uv:0.6-python3.13-bookworm-slim AS builder

WORKDIR /app

# Enable bytecode compilation for faster startup
ENV UV_COMPILE_BYTECODE=1
# Copy files instead of hardlinks (required for multi-stage builds)
ENV UV_LINK_MODE=copy
# Exclude dev dependencies
ENV UV_NO_DEV=1
# Don't download Python - use the image's Python
ENV UV_PYTHON_DOWNLOADS=0

# Install dependencies first (cached layer)
# Using bind mounts to avoid copying files that change frequently
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project

# Copy application code
COPY . /app

# Install the project itself
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-editable

# ------------------------------------------------------------------------------
# Runtime stage: Minimal image for production
# ------------------------------------------------------------------------------
FROM python:3.13-slim-bookworm AS runtime

# Create non-root user for security
RUN groupadd --system --gid 1000 app \
    && useradd --system --gid 1000 --uid 1000 --create-home app

# Copy the application from the builder
COPY --from=builder --chown=app:app /app /app

WORKDIR /app

# Add the virtual environment to PATH
ENV PATH="/app/.venv/bin:$PATH"

# Switch to non-root user
USER app

# Default command - override in docker-compose or at runtime
ENTRYPOINT ["python", "-m", "local_shazam"]
