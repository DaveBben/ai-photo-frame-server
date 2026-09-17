"""The API server's Flux client gets an edited 800x480 PNG from the real Flux server on the Mac mini.

Slice: Restyle a photo with the image made by the local Flux server
(docs/tasks/local-ai/task.md, item A).

Runs against the real Mac mini, excluded from ./check and CI:
    uv run pytest -m macmini
FLUX_URL overrides the server address.
"""

import base64
import os
from io import BytesIO

import pytest
from PIL import Image

from local_shazam.flux2_client import Flux2Client

pytestmark = pytest.mark.macmini

FLUX_URL = os.environ.get("FLUX_URL", "http://davids-mac-mini.local:8081")


async def test_flux_client_gets_an_800x480_png_from_the_mac_mini() -> None:
    buf = BytesIO()
    Image.new("RGB", (640, 480), (30, 90, 160)).save(buf, format="JPEG")

    png = await Flux2Client(f"{FLUX_URL}/v1").generate_image(
        "Bathe the scene in lime green overhead light",
        base64.b64encode(buf.getvalue()).decode(),
    )

    image = Image.open(BytesIO(png))
    assert image.format == "PNG"
    assert image.size == (800, 480)
