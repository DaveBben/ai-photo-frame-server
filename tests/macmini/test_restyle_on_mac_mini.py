"""A photo sent to the API server is restyled for a song using only the Mac mini's models.

Slice: captions, song looks and edit prompts from the local vision model
(docs/tasks/local-ai/task.md, item B).
Acceptance: Given the vision model and Flux servers running on the Mac mini, WHEN the
frame sends a photo with a song to POST /images, THEN it gets back an 800x480
PNG, and a second restyle for the same song finishes within 60 seconds, with no
OpenAI or Black Forest Labs key set.

Starts the API server on this machine pointed at the Mac mini, excluded from ./check
and CI:
    uv run pytest -m macmini
VLM_URL and FLUX_URL override the Mac mini's server addresses.
"""

import os
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from io import BytesIO
from pathlib import Path

import httpx
import pytest
from PIL import Image

pytestmark = pytest.mark.macmini

VLM_URL = os.environ.get("VLM_URL", "http://davids-mac-mini.local:8080")
FLUX_URL = os.environ.get("FLUX_URL", "http://davids-mac-mini.local:8081")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port: int = s.getsockname()[1]
        return port


@pytest.fixture
def api_url(tmp_path: Path) -> Iterator[str]:
    port = _free_port()
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in {"OPENAI_API_KEY", "BFL_API_KEY"}
    }
    env.update(
        SERVER_HOST="127.0.0.1",
        SERVER_PORT=str(port),
        DATA_DIR=str(tmp_path),
        VLM_BASE_URL=f"{VLM_URL}/v1",
        FLUX_BASE_URL=f"{FLUX_URL}/v1",
    )
    proc = subprocess.Popen(  # noqa: S603
        [sys.executable, "-m", "local_shazam.server"],
        cwd=tmp_path,  # no .env file supplies a key
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    url = f"http://127.0.0.1:{port}"
    try:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            try:
                httpx.get(f"{url}/health", timeout=1)
                break
            except httpx.TransportError:
                time.sleep(0.2)
        else:
            pytest.fail("API server did not start listening within 30s")
        yield url
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def test_sent_photo_is_restyled_by_the_mac_minis_models(api_url: str) -> None:
    photo = BytesIO()
    Image.new("RGB", (1024, 768), (200, 150, 90)).save(photo, format="JPEG")
    form = {"song_title": "bad guy", "song_artists": "Billie Eilish"}
    files = {"file": ("photo.jpg", photo.getvalue(), "image/jpeg")}

    first = httpx.post(f"{api_url}/images", data=form, files=files, timeout=300)
    assert first.status_code == 200, first.text
    png = Image.open(BytesIO(first.content))
    assert png.format == "PNG"
    assert png.size == (800, 480)

    start = time.monotonic()
    second = httpx.post(f"{api_url}/images", data=form, files=files, timeout=300)
    elapsed = time.monotonic() - start
    assert second.status_code == 200, second.text
    assert elapsed < 60, f"restyle for a cached song took {elapsed:.1f}s"
