# AI Photo Frame Server

An image transformation server that applies a song's visual aesthetic to photos. Uses the Mac mini's Qwen3-VL-4B vision model to describe photos, read the song's iTunes album cover and write edit prompts, then Flux.2 Klein 4B for image-to-image transformation. No OpenAI or Black Forest Labs key is needed.

You can find the client code which I have running on the Raspberry Pi 3B here:
[https://github.com/DaveBben/ai-photo-frame-client](https://github.com/DaveBben/ai-photo-frame-client)

Built in 2 days with heavy AI assistance. Expect rough edges.

## How it works

Send a photo with a song title and artist in one request. The server keeps the photo in memory and writes no copy of it or of the result:

1. The vision model describes the photo
2. The vision model describes the song's look from its iTunes album cover and catalog data (cached)
3. The vision model writes an edit prompt, and Flux.2 Klein 4B transforms the photo to match the song's vibe

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/images` | POST | Restyle the photo sent as multipart `file`, with form fields `song_title` and `song_artists`, and return an 800x480 PNG |
| `/aesthetic` | GET | Get visual aesthetic description for a song |

## Configuration

Set these environment variables (or use `.env` file):

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `VLM_BASE_URL` | No | `http://127.0.0.1:8080/v1` | Vision model server's OpenAI chat API |
| `FLUX_BASE_URL` | No | `http://127.0.0.1:8081/v1` | Flux server's OpenAI images API |
| `SERVER_HOST` | No | `0.0.0.0` | Server bind address |
| `SERVER_PORT` | No | `8000` | Server port |
| `LOG_LEVEL` | No | `INFO` | Logging level |
| `DATA_DIR` | No | `data/` in the repo | The aesthetic cache |

## Mac mini

First-time setup:

```bash
ssh mini git clone https://github.com/DaveBben/ai-photo-frame-server ~/ai-photo-frame-server
ssh -t mini ~/ai-photo-frame-server/scripts/install-mac-mini
```

Deploy after a merge to main (pulls main, syncs dependencies, restarts the API server):

```bash
ssh mini ~/ai-photo-frame-server/scripts/deploy
```

`install-mac-mini` installs four LaunchDaemons, each running as `dave`:

| LaunchDaemon | Runs | Port | Log |
|--------------|------|------|-----|
| `com.local-shazam.api` | API server (`local-shazam-server`) | 8000 | `~/Library/Logs/local-shazam-api.log` |
| `com.local-shazam.vlm` | Vision model server (`mlx_vlm.server`) | 8080 | `~/Library/Logs/local-shazam-vlm.log` |
| `com.local-shazam.flux` | Flux server (`local-shazam-flux`) | 8081 | `~/Library/Logs/local-shazam-flux.log` |
| `com.local-shazam.deploy` | `scripts/deploy` at boot | - | `~/Library/Logs/local-shazam-deploy.log` |

Check the Mac mini from the laptop (`API_URL` overrides `http://davids-mac-mini.local:8000`):

```bash
uv run pytest -m macmini
```

## Development

```bash
uv sync                      # install dependencies
uv run local-shazam-server   # run the API server
uv run pre-commit install    # install the commit hook
./check                      # format, lint, type check, tests
```

Run `./check` before creating a PR.
