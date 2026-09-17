"""The Flux server on the Mac mini returns an edited 800x480 PNG while the vision model server is running.

Slice: Flux server on the Mac mini (docs/tasks/local-ai/task.md, item 2), row 1.
Acceptance: Given the running VLM and Flux server WHEN I send a photo and an edit
prompt then I get back an edited 800x480 PNG.

Runs against the real Mac mini, excluded from ./check and CI:
    uv run pytest -m macmini
FLUX_URL and VLM_URL override the server addresses.
"""

import base64
import os
import time
from io import BytesIO

import httpx
import pytest
from PIL import Image

pytestmark = pytest.mark.macmini

FLUX_URL = os.environ.get("FLUX_URL", "http://davids-mac-mini.local:8081")
VLM_URL = os.environ.get("VLM_URL", "http://davids-mac-mini.local:8080")
# The 60s restyle limit minus the 13.4s the spike measured for writing the prompt.
EDIT_BUDGET_S = 60 - 13.4


def _photo() -> bytes:
    img = Image.new("RGB", (1024, 1024))
    img.putdata([(x // 4, y // 4, 128) for y in range(1024) for x in range(1024)])
    buf = BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _edit(photo: bytes) -> httpx.Response:
    return httpx.post(
        f"{FLUX_URL}/v1/images/edits",
        files={"image": ("photo.jpg", photo, "image/jpeg")},
        data={"prompt": "Bathe the scene in lime green overhead light"},
        timeout=300,
    )


def test_flux_server_returns_an_edited_800x480_png_within_budget() -> None:
    assert httpx.get(f"{VLM_URL}/health", timeout=10).status_code == 200
    photo = _photo()

    first = _edit(photo)
    assert first.status_code == 200, first.text
    png = Image.open(BytesIO(base64.b64decode(first.json()["data"][0]["b64_json"])))
    assert png.format == "PNG"
    assert png.size == (800, 480)

    start = time.monotonic()
    second = _edit(photo)
    elapsed = time.monotonic() - start
    assert second.status_code == 200, second.text
    assert elapsed < EDIT_BUDGET_S, f"edit took {elapsed:.1f}s"
