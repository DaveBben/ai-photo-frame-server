"""POST /images through the real app, with the Mac mini's vision model server, Flux server and iTunes faked.

Slice: Transform a photo (docs/tasks/restructure-layers/task.md), then Restyle a photo
with the image made by the local Flux server (docs/tasks/local-ai/task.md, item A),
then captions, song looks and edit prompts from the local vision model (item B).
Acceptance (item A): Given a stored photo and a cached song aesthetic, WHEN the frame
posts /images, THEN it gets back the PNG the Flux server at FLUX_BASE_URL made, and no
request goes to api.bfl.ai.
"""

import base64
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from email.parser import BytesParser
from email.policy import HTTP
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
import respx
from PIL import Image
from vlm_fakes import VLM_CHAT, VLM_MODEL, is_aesthetic_request, mock_itunes

from local_shazam.server import create_app

SONG = "bad guy"
ARTIST = "Billie Eilish"
DESCRIPTION = "A person in a leather jacket on a beach at golden hour."
AESTHETIC = "Lime green overhead strobe, crushed blacks, #8ACE00."
EDIT_PROMPT = "Relight the scene with a lime green overhead strobe."
PNG = b"PNG1"

FLUX_EDITS = "http://127.0.0.1:8081/v1/images/edits"


def _chat_reply(content: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "id": "chatcmpl-1",
            "object": "chat.completion",
            "created": 0,
            "model": "gpt-4o",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                }
            ],
        },
    )


def _form_fields(request: httpx.Request) -> dict[str, bytes]:
    """Split a multipart/form-data request into its fields' raw bytes."""
    head = f"Content-Type: {request.headers['content-type']}\r\n\r\n".encode()
    message = BytesParser(policy=HTTP).parsebytes(head + request.content)
    return {
        str(part.get_param("name", header="content-disposition")): part.get_payload(
            decode=True
        )
        for part in message.iter_parts()
    }


@dataclass
class Frame:
    """The app as the photo frame sees it, plus every request sent to the fakes."""

    client: httpx.AsyncClient
    mock: respx.MockRouter
    image_id: str = ""
    openai_requests: list[dict[str, object]] = field(default_factory=list)
    flux_edits: list[dict[str, bytes]] = field(default_factory=list)

    async def transform(self, image_id: str | None = None) -> httpx.Response:
        return await self.client.post(
            "/images",
            params={
                "image_id": image_id or self.image_id,
                "song_title": SONG,
                "song_artists": ARTIST,
            },
        )


@pytest.fixture
async def frame(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[Frame]:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.delenv("VLM_BASE_URL", raising=False)
    monkeypatch.delenv("FLUX_BASE_URL", raising=False)

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=transport, base_url="http://frame") as client,
    ):
        with respx.mock(assert_all_called=False) as mock:
            recorded = Frame(client=client, mock=mock)

            def openai(request: httpx.Request) -> httpx.Response:
                body = json.loads(request.content)
                recorded.openai_requests.append(body)
                if is_aesthetic_request(body):
                    return _chat_reply(AESTHETIC)
                if body["messages"][0]["role"] == "system":
                    return _chat_reply(EDIT_PROMPT)
                return _chat_reply(DESCRIPTION)

            def flux_edit(request: httpx.Request) -> httpx.Response:
                recorded.flux_edits.append(_form_fields(request))
                return httpx.Response(
                    200,
                    json={
                        "created": 0,
                        "data": [{"b64_json": base64.b64encode(PNG).decode()}],
                    },
                )

            mock.post(VLM_CHAT).mock(side_effect=openai)
            mock_itunes(mock)
            mock.post(FLUX_EDITS, name="flux_edit").mock(side_effect=flux_edit)

            photo = BytesIO()
            Image.new("RGB", (64, 48), "red").save(photo, format="JPEG")
            upload = await client.put(
                "/images",
                files={"file": ("photo.jpg", photo.getvalue(), "image/jpeg")},
            )
            recorded.image_id = upload.json()["image_id"]
            await client.get(
                "/aesthetic", params={"song_title": SONG, "artist": ARTIST}
            )
            recorded.openai_requests.clear()

            yield recorded


async def test_transform_returns_the_image_model_png(frame: Frame) -> None:
    response = await frame.transform()

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content == PNG


async def test_prompt_request_carries_photo_description_and_song_aesthetic(
    frame: Frame,
) -> None:
    await frame.transform()

    prompt_requests = [r for r in frame.openai_requests if not is_aesthetic_request(r)]
    assert len(prompt_requests) == 1
    assert prompt_requests[0]["model"] == VLM_MODEL
    messages = json.dumps(prompt_requests[0]["messages"])
    assert f"Description: {DESCRIPTION}" in messages
    assert AESTHETIC in messages


async def test_edit_request_carries_written_prompt_and_uploaded_photo(
    frame: Frame,
) -> None:
    await frame.transform()

    assert len(frame.flux_edits) == 1
    fields = frame.flux_edits[0]
    assert fields["prompt"].decode() == EDIT_PROMPT
    sent = Image.open(BytesIO(fields["image"]))
    assert sent.size == (64, 48)
    assert sent.getexif()[270] == DESCRIPTION


async def test_cached_aesthetic_sends_no_search_request(frame: Frame) -> None:
    await frame.transform()

    assert [r for r in frame.openai_requests if is_aesthetic_request(r)] == []


async def test_flux_server_error_returns_502_with_reason(frame: Frame) -> None:
    frame.mock.routes["flux_edit"].mock(
        side_effect=None,
        return_value=httpx.Response(500, json={"detail": "out of memory"}),
    )

    response = await frame.transform()

    assert response.status_code == 502
    assert response.json()["detail"].startswith("Flux server failed:")


async def test_unreachable_flux_server_returns_502_with_reason(frame: Frame) -> None:
    frame.mock.routes["flux_edit"].mock(side_effect=httpx.ConnectError("refused"))

    response = await frame.transform()

    assert response.status_code == 502
    assert response.json()["detail"].startswith("Flux server failed:")


async def test_unknown_photo_returns_404(frame: Frame) -> None:
    response = await frame.transform(image_id=str(uuid4()))

    assert response.status_code == 404
