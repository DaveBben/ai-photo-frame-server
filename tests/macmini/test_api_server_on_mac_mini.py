"""The API server on the Mac mini restyles an uploaded photo using only the Mac mini's models.

Slice: the API server runs on the Mac mini (docs/tasks/local-ai/task.md, item D).
Acceptance: Given the API server, vision model server and Flux server started by their
LaunchDaemons on the Mac mini, WHEN a client on the network uploads a photo to port 8000
and asks for it restyled for a song, THEN it gets back an 800x480 PNG, and a second
restyle for the same song finishes within 60 seconds.

Runs against the real Mac mini, excluded from ./check and CI:
    uv run pytest -m macmini
API_URL overrides the address.
"""

import os
import time
from io import BytesIO

import httpx
import pytest
from PIL import Image

pytestmark = pytest.mark.macmini

API_URL = os.environ.get("API_URL", "http://davids-mac-mini.local:8000")


def test_mac_mini_api_server_restyles_an_uploaded_photo() -> None:
    assert httpx.get(f"{API_URL}/health", timeout=10).json() == {"status": "healthy"}
    photo = BytesIO()
    Image.new("RGB", (1024, 768), (60, 140, 90)).save(photo, format="JPEG")
    upload = httpx.put(
        f"{API_URL}/images",
        files={"file": ("photo.jpg", photo.getvalue(), "image/jpeg")},
        timeout=300,
    )
    assert upload.status_code == 200, upload.text
    params = {
        "image_id": upload.json()["image_id"],
        "song_title": "Midnight City",
        "song_artists": "M83",
    }

    first = httpx.post(f"{API_URL}/images", params=params, timeout=300)
    assert first.status_code == 200, first.text
    png = Image.open(BytesIO(first.content))
    assert (png.format, png.size) == ("PNG", (800, 480))

    start = time.monotonic()
    second = httpx.post(f"{API_URL}/images", params=params, timeout=300)
    elapsed = time.monotonic() - start
    assert second.status_code == 200, second.text
    assert elapsed < 60, f"restyle for a cached song took {elapsed:.1f}s"
