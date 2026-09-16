"""POST /images through the real app, with only the OpenAI and BFL web APIs faked.

Slice: Transform a photo (docs/tasks/restructure-layers/task.md).
Acceptance: POST /images returns identical responses before and after the move.
"""

import base64
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
import respx
from PIL import Image

from local_shazam.server import create_app

SONG = "bad guy"
ARTIST = "Billie Eilish"
DESCRIPTION = "A person in a leather jacket on a beach at golden hour."
AESTHETIC = "Lime green overhead strobe, crushed blacks, #8ACE00."
EDIT_PROMPT = "Relight the scene with a lime green overhead strobe."
PNG = b"PNG1"

OPENAI_CHAT = "https://api.openai.com/v1/chat/completions"
BFL_SUBMIT = "https://api.bfl.ai/v1/flux-2-klein-9b"
BFL_POLL = "https://api.bfl.ai/v1/get_result?id=job-1"
BFL_SAMPLE = "https://delivery.bfl.ai/job-1/sample.png"
SEARCH_MODEL = "gpt-4o-search-preview"


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


@dataclass
class Frame:
    """The app as the photo frame sees it, plus every request sent to the fakes."""

    client: httpx.AsyncClient
    mock: respx.MockRouter
    image_id: str = ""
    openai_requests: list[dict[str, object]] = field(default_factory=list)
    bfl_submits: list[dict[str, object]] = field(default_factory=list)

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
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("BFL_API_KEY", "bfl-test")

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
                if body["model"] == SEARCH_MODEL:
                    return _chat_reply(AESTHETIC)
                if body["messages"][0]["role"] == "system":
                    return _chat_reply(EDIT_PROMPT)
                return _chat_reply(DESCRIPTION)

            def bfl_submit(request: httpx.Request) -> httpx.Response:
                recorded.bfl_submits.append(json.loads(request.content))
                return httpx.Response(200, json={"polling_url": BFL_POLL})

            mock.post(OPENAI_CHAT).mock(side_effect=openai)
            mock.post(BFL_SUBMIT, name="bfl_submit").mock(side_effect=bfl_submit)
            mock.get(BFL_POLL).respond(
                200, json={"status": "Ready", "result": {"sample": BFL_SAMPLE}}
            )
            mock.get(BFL_SAMPLE).respond(200, content=PNG)

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

    prompt_requests = [r for r in frame.openai_requests if r["model"] != SEARCH_MODEL]
    assert len(prompt_requests) == 1
    messages = json.dumps(prompt_requests[0]["messages"])
    assert f"Description: {DESCRIPTION}" in messages
    assert AESTHETIC in messages


async def test_edit_request_carries_written_prompt_and_uploaded_photo(
    frame: Frame,
) -> None:
    await frame.transform()

    assert len(frame.bfl_submits) == 1
    submit = frame.bfl_submits[0]
    assert submit["prompt"] == EDIT_PROMPT
    sent = Image.open(BytesIO(base64.b64decode(str(submit["input_image"]))))
    assert sent.size == (64, 48)
    assert sent.getexif()[270] == DESCRIPTION


async def test_cached_aesthetic_sends_no_search_request(frame: Frame) -> None:
    await frame.transform()

    assert [r for r in frame.openai_requests if r["model"] == SEARCH_MODEL] == []


async def test_out_of_credits_returns_502_with_reason(frame: Frame) -> None:
    frame.mock.routes["bfl_submit"].mock(
        side_effect=None,
        return_value=httpx.Response(402, json={"detail": "no credits"}),
    )

    response = await frame.transform()

    assert response.status_code == 502
    assert response.json() == {"detail": "Insufficient BFL credits"}


async def test_unknown_photo_returns_404(frame: Frame) -> None:
    response = await frame.transform(image_id=str(uuid4()))

    assert response.status_code == 404
