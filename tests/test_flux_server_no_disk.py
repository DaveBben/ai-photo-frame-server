"""The Flux server restyles a photo without writing it, or anything else, to disk.

Story: the Flux server restyles without writing the photo to disk
(shazam-restyle, story 9). Decision:
docs/adr/architecture/restyle-photos-in-memory-and-store-none.md.

Each test runs the Flux server app in a fresh Python process that imports only
local_shazam.flux_server, as the deployed Flux server does. Two reasons: the API
server's routes set Starlette's upload spool limit for the whole process, so
this pytest process cannot show the Flux server's own limit; and the audit hook
that records every file the app creates cannot be removed once added.

The image model is faked. It loads its reference the way mflux 0.19.1 does
(mflux/utils/image_util.py:164 and mflux/utils/exif_orientation.py:20): a
Pillow image is used as given, anything else goes to Image.open, and the EXIF
Orientation tag is applied before the model sees the pixels.
"""

import asyncio
import base64
import hashlib
import json
import os
import subprocess
import sys
from io import BytesIO
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from PIL import Image, ImageOps

from local_shazam.flux_server import create_app

PROMPT = "Bathe the scene in lime green overhead light"
# Open flags that create or write a file.
_WRITING = os.O_WRONLY | os.O_RDWR | os.O_CREAT
_CREATING_EVENTS = ("os.mkdir", "tempfile.mkstemp", "tempfile.mkdtemp")


class MfluxLikeModel:
    """Stands in for mflux's Flux2KleinEdit and records each reference as mflux would load it."""

    def __init__(self) -> None:
        self.references: list[Image.Image] = []

    def generate_image(
        self,
        *,
        height: int,
        width: int,
        image_paths: list[Any],
        **_settings: Any,
    ) -> SimpleNamespace:
        given = image_paths[0]
        image = given if isinstance(given, Image.Image) else Image.open(given)
        self.references.append(ImageOps.exif_transpose(image).convert("RGB"))
        return SimpleNamespace(image=Image.new("RGB", (width, height), (0, 0, 255)))


def _digest(image: Image.Image) -> dict[str, Any]:
    return {
        "size": list(image.size),
        "mode": image.mode,
        "sha256": hashlib.sha256(image.tobytes()).hexdigest(),
    }


async def _serve_one_edit(photo: bytes, created: list[str]) -> dict[str, Any]:
    """Start the Flux server, send one edit, and report what came back and what the model got."""
    model = MfluxLikeModel()
    created.clear()
    app = create_app(model)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://flux"
        ) as client,
    ):
        response = await client.post(
            "/v1/images/edits",
            files={"image": ("photo.jpg", photo, "image/jpeg")},
            data={"prompt": PROMPT},
        )
    report = {"created": list(created), "status": response.status_code}
    if response.status_code == 200:
        png = base64.b64decode(response.json()["data"][0]["b64_json"])
        with Image.open(BytesIO(png)) as result:
            report["result"] = {"format": result.format, "size": list(result.size)}
    report["references"] = [_digest(r) for r in model.references]
    return report


def _probe() -> None:
    """Run in the child process: read the photo from stdin, print the report as JSON."""
    photo = sys.stdin.buffer.read()
    created: list[str] = []

    def record(event: str, args: tuple[Any, ...]) -> None:
        if event == "open" and isinstance(args[2], int) and args[2] & _WRITING:
            created.append(f"open {args[0]}")
        elif event in _CREATING_EVENTS:
            created.append(f"{event} {args[0]}")

    sys.addaudithook(record)
    report = asyncio.run(_serve_one_edit(photo, created))
    sys.stdout.write(json.dumps(report))


def _run_flux_server(photo: bytes) -> dict[str, Any]:
    """Send one photo to a Flux server running alone in a fresh process."""
    # -B: importing a module mid-request must not write a .pyc and count as a file.
    done = subprocess.run(  # noqa: S603
        [sys.executable, "-B", __file__],
        input=photo,
        capture_output=True,
        timeout=120,
        check=False,
    )
    assert done.returncode == 0, done.stderr.decode()
    report: dict[str, Any] = json.loads(done.stdout)
    return report


def _sideways_jpeg() -> bytes:
    """A 1024x768 JPEG under 1 MB whose EXIF says to turn it 90 degrees (Orientation 6)."""
    image = Image.new("RGB", (1024, 768))
    image.putdata(
        [(x % 256, y % 256, (x + y) % 256) for y in range(768) for x in range(1024)]
    )
    exif = Image.Exif()
    exif[0x0112] = 6
    buf = BytesIO()
    image.save(buf, format="JPEG", quality=85, exif=exif.tobytes())
    return buf.getvalue()


def _noise_png() -> bytes:
    """A 1024x768 PNG of random pixels, well over Starlette's 1 MB spool limit."""
    pixels = os.urandom(1024 * 768 * 3)
    buf = BytesIO()
    Image.frombytes("RGB", (1024, 768), pixels).save(buf, format="PNG")
    return buf.getvalue()


def _todays_reference(photo: bytes) -> dict[str, Any]:
    """The reference the Flux server hands the model today: decoded, RGB, fit to 512 px, no rotation."""
    image = Image.open(BytesIO(photo)).convert("RGB")
    image.thumbnail((512, 512))
    return _digest(image)


@pytest.fixture(scope="module")
def sideways_edit() -> tuple[bytes, dict[str, Any]]:
    photo = _sideways_jpeg()
    return photo, _run_flux_server(photo)


# Row 1
def test_restyle_through_flux_creates_no_file(
    sideways_edit: tuple[bytes, dict[str, Any]],
) -> None:
    photo, report = sideways_edit
    assert len(photo) < 1024 * 1024

    assert report["status"] == 200
    assert report["result"] == {"format": "PNG", "size": [800, 480]}
    assert report["created"] == []


# Row 2
def test_sideways_photo_reaches_the_model_with_todays_pixels(
    sideways_edit: tuple[bytes, dict[str, Any]],
) -> None:
    photo, report = sideways_edit

    assert report["references"][-1] == _todays_reference(photo)
    assert report["references"][-1]["size"] == [512, 384]


# Row 3
def test_photo_over_1mb_is_not_spooled_to_disk() -> None:
    photo = _noise_png()
    assert len(photo) > 2 * 1024 * 1024

    report = _run_flux_server(photo)

    assert report["status"] == 200
    assert report["created"] == []


if __name__ == "__main__":
    _probe()
