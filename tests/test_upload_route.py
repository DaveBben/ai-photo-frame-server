"""PUT /images through the real app, with the Mac mini's vision model server faked.

Slice: Upload a photo (docs/tasks/restructure-layers/task.md), then captions, song looks
and edit prompts from the local vision model (docs/tasks/local-ai/task.md, item B).
"""

import base64
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from uuid import UUID

import httpx
import pytest
import respx
from PIL import Image
from vlm_fakes import VLM_CHAT, VLM_MODEL, chat_reply

from local_shazam.exceptions import ServiceError
from local_shazam.prompts import load_prompt
from local_shazam.server import create_app

DESCRIPTION = "A person in a leather jacket on a beach at golden hour."


def _photo(size: tuple[int, int], fmt: str = "JPEG", **save: object) -> bytes:
    mode = "RGBA" if fmt == "PNG" else "RGB"
    buf = BytesIO()
    Image.new(mode, size, "red").save(buf, format=fmt, **save)
    return buf.getvalue()


@dataclass
class Frame:
    """The app as the photo frame sees it, plus every request sent to OpenAI."""

    client: httpx.AsyncClient
    openai_requests: list[dict[str, object]] = field(default_factory=list)
    reply: str = DESCRIPTION

    async def upload(self, contents: bytes, name: str = "photo.jpg") -> httpx.Response:
        return await self.client.put("/images", files={"file": (name, contents)})


@pytest.fixture
async def frame(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[Frame]:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.delenv("VLM_BASE_URL", raising=False)

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=transport, base_url="http://frame") as client,
    ):
        with respx.mock(assert_all_called=False) as mock:
            recorded = Frame(client=client)

            def openai(request: httpx.Request) -> httpx.Response:
                recorded.openai_requests.append(json.loads(request.content))
                return chat_reply(recorded.reply)

            mock.post(VLM_CHAT).mock(side_effect=openai)
            yield recorded


async def test_uploaded_photo_is_returned_to_the_frame(frame: Frame) -> None:
    upload = await frame.upload(_photo((64, 48)))

    assert upload.status_code == 200
    body = upload.json()
    assert list(body) == ["image_id"]
    image_id = str(UUID(body["image_id"]))

    shown = await frame.client.get("/images")
    assert shown.status_code == 200
    assert shown.headers["x-image-id"] == image_id
    assert Image.open(BytesIO(shown.content)).size == (64, 48)


async def test_describe_request_carries_shrunk_photo_and_prompt(frame: Frame) -> None:
    await frame.upload(_photo((2000, 1500)))

    assert len(frame.openai_requests) == 1
    request = frame.openai_requests[0]
    assert request["model"] == VLM_MODEL
    content = request["messages"][0]["content"]  # type: ignore[index]
    image_url = content[0]["image_url"]["url"]
    sent = Image.open(BytesIO(base64.b64decode(image_url.split(",", 1)[1])))
    assert sent.size == (1024, 768)
    assert content[1]["text"] == load_prompt("describe_image")


async def test_empty_description_stores_no_photo_for_the_frame(frame: Frame) -> None:
    frame.reply = ""

    with pytest.raises(
        ServiceError, match=r"^Vision model returned an empty response$"
    ):
        await frame.upload(_photo((64, 48)))

    assert (await frame.client.get("/images")).status_code == 404


async def test_oversized_upload_returns_413_without_calling_the_model(
    frame: Frame,
) -> None:
    response = await frame.upload(b"\0" * (10 * 1024 * 1024 + 1))

    assert response.status_code == 413
    assert response.json() == {"detail": "File too large. Maximum size is 10 MB"}
    assert frame.openai_requests == []


async def test_non_image_upload_returns_400(frame: Frame) -> None:
    response = await frame.upload(b"not a photo")

    assert response.status_code == 400
    assert response.json()["detail"].startswith("Invalid image:")


async def test_exif_rotated_photo_is_stored_upright(frame: Frame) -> None:
    exif = Image.Exif()
    exif[274] = 6  # Orientation: rotate 90° clockwise
    await frame.upload(_photo((64, 48), exif=exif.tobytes()))

    shown = await frame.client.get("/images")
    assert Image.open(BytesIO(shown.content)).size == (48, 64)


async def test_transparent_png_upload_is_stored(frame: Frame) -> None:
    response = await frame.upload(_photo((64, 48), fmt="PNG"), name="photo.png")

    assert response.status_code == 200
