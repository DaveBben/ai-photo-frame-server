# AI Photo Frame Server

An image transformation server that applies a song's visual aesthetic to photos. Uses GPT-4o to analyze images and generate prompts, then Flux.2 Klein 9B for image-to-image transformation.

Built in 2 days with heavy AI assistance. Expect rough edges.

## How it works

1. Upload an image → GPT-4o analyzes and describes it
2. Provide a song title and artist → GPT-4o searches for the song's visual aesthetic
3. Request transformation → Flux.2 transforms your image to match the song's vibe

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/images` | PUT | Upload image (analyzed with GPT-4o) |
| `/images` | GET | Get random stored image |
| `/images` | POST | Transform image to match song aesthetic |
| `/aesthetic` | GET | Get visual aesthetic description for a song |

## Configuration

Set these environment variables (or use `.env` file):

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `BFL_API_KEY` | Yes | - | Black Forest Labs API key for Flux.2 |
| `OPENAI_API_KEY` | Yes | - | OpenAI API key for GPT-4o |
| `SERVER_HOST` | No | `0.0.0.0` | Server bind address |
| `SERVER_PORT` | No | `8000` | Server port |
| `LOG_LEVEL` | No | `INFO` | Logging level |

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
