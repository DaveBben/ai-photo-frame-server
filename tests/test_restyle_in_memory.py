"""POST /images restyles the photo sent with the request and stores no photo.

Story: the Mac mini restyles a photo sent with a song and keeps nothing
(shazam-restyle, story 1). Decision:
docs/adr/architecture/restyle-photos-in-memory-and-store-none.md.
The vision model server, the Flux server and iTunes are faked.
"""

import base64
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from email.parser import BytesParser
from email.policy import HTTP
from io import BytesIO
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
import yaml
from PIL import Image
from vlm_fakes import VLM_CHAT, chat_reply, is_aesthetic_request, mock_itunes

from local_shazam.server import create_app

ROOT = Path(__file__).resolve().parents[1]
FLUX_EDITS = "http://127.0.0.1:8081/v1/images/edits"
SONG = "bad guy"
ARTIST = "Billie Eilish"
FORM = {"song_title": SONG, "song_artists": ARTIST}


def _photo(size: tuple[int, int] = (64, 48), fmt: str = "JPEG", **save: Any) -> bytes:
    mode = "RGBA" if fmt == "PNG" else "RGB"
    buf = BytesIO()
    Image.new(mode, size, "red").save(buf, format=fmt, **save)
    return buf.getvalue()


def _restyled_png() -> bytes:
    buf = BytesIO()
    Image.new("RGB", (800, 480), (138, 206, 0)).save(buf, format="PNG")
    return buf.getvalue()


def _edit_image(request: httpx.Request) -> bytes:
    """The photo field of the multipart edit request sent to the Flux server."""
    head = f"Content-Type: {request.headers['content-type']}\r\n\r\n".encode()
    message = BytesParser(policy=HTTP).parsebytes(head + request.content)
    for part in message.iter_parts():
        if part.get_param("name", header="content-disposition") == "image":
            payload: bytes = part.get_payload(decode=True)
            return payload
    raise AssertionError("edit request has no image field")


@dataclass
class Frame:
    """The app as the photo frame sees it, plus every request sent to the fakes."""

    client: httpx.AsyncClient
    mock: respx.MockRouter
    data_dir: Path
    png: bytes = field(default_factory=_restyled_png)
    vlm_requests: list[dict[str, object]] = field(default_factory=list)
    flux_edits: list[httpx.Request] = field(default_factory=list)

    async def restyle(
        self, photo: bytes | None = None, name: str = "photo.jpg"
    ) -> httpx.Response:
        return await self.client.post(
            "/images",
            data=FORM,
            files={"file": (name, _photo() if photo is None else photo)},
        )

    def data_dir_entries(self) -> list[str]:
        return sorted(
            str(p.relative_to(self.data_dir)) for p in self.data_dir.rglob("*")
        )


@pytest.fixture
async def frame(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[Frame]:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setenv("DATA_DIR", str(data_dir))
    monkeypatch.delenv("VLM_BASE_URL", raising=False)
    monkeypatch.delenv("FLUX_BASE_URL", raising=False)

    app = create_app()
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://frame"
        ) as client,
    ):
        with respx.mock(assert_all_called=False) as mock:
            recorded = Frame(client=client, mock=mock, data_dir=data_dir)

            def vlm(request: httpx.Request) -> httpx.Response:
                body = json.loads(request.content)
                recorded.vlm_requests.append(body)
                if is_aesthetic_request(body):
                    return chat_reply("Lime green overhead strobe.")
                if body["messages"][0]["role"] == "system":
                    return chat_reply("Relight the scene in lime green.")
                return chat_reply("A red photo.")

            def flux(request: httpx.Request) -> httpx.Response:
                recorded.flux_edits.append(request)
                return httpx.Response(
                    200,
                    json={
                        "created": 0,
                        "data": [{"b64_json": base64.b64encode(recorded.png).decode()}],
                    },
                )

            mock.post(VLM_CHAT, name="vlm").mock(side_effect=vlm)
            mock_itunes(mock)
            mock.post(FLUX_EDITS, name="flux_edit").mock(side_effect=flux)
            yield recorded


# Row 1, criterion a.
async def test_photo_title_and_artist_come_back_as_an_800x480_png(
    frame: Frame,
) -> None:
    response = await frame.restyle()

    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "image/png"
    assert response.content == frame.png
    png = Image.open(BytesIO(response.content))
    assert (png.format, png.size) == ("PNG", (800, 480))


# Row 2, criterion b.
async def test_successful_restyle_leaves_only_the_aesthetic_cache(
    frame: Frame,
) -> None:
    response = await frame.restyle()

    assert response.status_code == 200, response.text
    assert frame.data_dir_entries() == ["aesthetic_cache.db"]


# Row 3, criterion b.
async def test_failed_restyle_leaves_only_the_aesthetic_cache(frame: Frame) -> None:
    frame.mock.routes["flux_edit"].mock(
        side_effect=None,
        return_value=httpx.Response(500, json={"detail": "out of memory"}),
    )

    response = await frame.restyle()

    assert response.status_code == 502, response.text
    assert frame.data_dir_entries() == ["aesthetic_cache.db"]


# Row 4, criterion c.
async def test_oversized_photo_returns_413_without_calling_a_model(
    frame: Frame,
) -> None:
    response = await frame.restyle(b"\0" * (10 * 1024 * 1024 + 1))

    assert response.status_code == 413
    assert response.json() == {"detail": "File too large. Maximum size is 10 MB"}
    assert frame.vlm_requests == []
    assert frame.flux_edits == []


# Row 5, criterion c.
async def test_unreadable_photo_returns_400_without_calling_a_model(
    frame: Frame,
) -> None:
    response = await frame.restyle(b"not a photo")

    assert response.status_code == 400
    assert response.json()["detail"].startswith("Invalid image:")
    assert frame.vlm_requests == []
    assert frame.flux_edits == []


# Row 6, criterion c.
@pytest.mark.parametrize("missing", ["file", "song_title", "song_artists"])
async def test_missing_field_returns_422_naming_it(frame: Frame, missing: str) -> None:
    data = {k: v for k, v in FORM.items() if k != missing}
    files = {} if missing == "file" else {"file": ("photo.jpg", _photo())}

    response = await frame.client.post("/images", data=data, files=files)

    assert response.status_code == 422
    assert [e["loc"] for e in response.json()["detail"]] == [["body", missing]]


# Row 7, criterion d.
async def test_vision_model_failure_returns_502_with_reason(frame: Frame) -> None:
    frame.mock.routes["vlm"].mock(
        side_effect=None,
        return_value=httpx.Response(500, json={"detail": "out of memory"}),
    )

    response = await frame.restyle()

    assert response.status_code == 502
    assert response.json()["detail"].startswith("Vision model failed:")


# Row 8.
async def test_sideways_photo_reaches_flux_upright(frame: Frame) -> None:
    exif = Image.Exif()
    exif[274] = 6  # Orientation: rotate 90 degrees clockwise
    response = await frame.restyle(_photo(exif=exif.tobytes()))

    assert response.status_code == 200, response.text
    (edit,) = frame.flux_edits
    assert Image.open(BytesIO(_edit_image(edit))).size == (48, 64)


# Row 9.
async def test_transparent_png_is_restyled(frame: Frame) -> None:
    response = await frame.restyle(_photo(fmt="PNG"), name="photo.png")

    assert response.status_code == 200, response.text
    assert response.content == frame.png


def _resolve(spec: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    ref = schema.get("$ref")
    if ref is None:
        return schema
    node: Any = spec
    for key in ref.removeprefix("#/").split("/"):
        node = node[key]
    return _resolve(spec, node)


def _interface(spec: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    """Each operation's query parameters and, per request content type, its required fields."""
    interface = {}
    for path, operations in spec["paths"].items():
        for method, op in operations.items():
            body = op.get("requestBody", {}).get("content", {})
            interface[(path, method)] = {
                "params": sorted(
                    (p["in"], p["name"]) for p in op.get("parameters", [])
                ),
                "body": {
                    media: sorted(_resolve(spec, c["schema"]).get("required", []))
                    for media, c in body.items()
                },
            }
    return interface


# Row 10, criterion e.
def test_openapi_yaml_describes_the_one_step_restyle_the_app_serves() -> None:
    documented = yaml.safe_load((ROOT / "openapi.yaml").read_text())

    assert _interface(documented) == _interface(create_app().openapi())
    images = documented["paths"]["/images"]
    assert list(images) == ["post"]
    form = images["post"]["requestBody"]["content"]["multipart/form-data"]["schema"]
    assert sorted(form["required"]) == ["file", "song_artists", "song_title"]
    assert form["properties"]["file"]["format"] == "binary"
    assert list(images["post"]["responses"]["200"]["content"]) == ["image/png"]
