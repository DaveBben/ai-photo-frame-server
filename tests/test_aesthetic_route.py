"""GET /aesthetic through the real app, with only the OpenAI and BFL web APIs faked.

Slice: Look up a song's aesthetic in one place (docs/tasks/restructure-layers/task.md).
Acceptance: GET /aesthetic returns identical responses before and after the move.
"""

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path

import httpx
import pytest
import respx
from PIL import Image

from local_shazam.server import create_app

SONG = "bad guy"
ARTIST = "Billie Eilish"
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
    """The app as the photo frame sees it, plus every search request sent to OpenAI."""

    client: httpx.AsyncClient
    search_reply: str = AESTHETIC
    searches: list[str] = field(default_factory=list)

    async def aesthetic(self) -> httpx.Response:
        return await self.client.get(
            "/aesthetic", params={"song_title": SONG, "artist": ARTIST}
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
            recorded = Frame(client=client)

            def openai(request: httpx.Request) -> httpx.Response:
                body = json.loads(request.content)
                if body["model"] == SEARCH_MODEL:
                    recorded.searches.append(body["messages"][1]["content"])
                    return _chat_reply(recorded.search_reply)
                if body["messages"][0]["role"] == "system":
                    return _chat_reply(EDIT_PROMPT)
                return _chat_reply("A red photo.")

            mock.post(OPENAI_CHAT).mock(side_effect=openai)
            mock.post(BFL_SUBMIT).respond(200, json={"polling_url": BFL_POLL})
            mock.get(BFL_POLL).respond(
                200, json={"status": "Ready", "result": {"sample": BFL_SAMPLE}}
            )
            mock.get(BFL_SAMPLE).respond(200, content=PNG)

            yield recorded


async def test_uncached_song_returns_the_search_model_aesthetic(frame: Frame) -> None:
    response = await frame.aesthetic()

    assert response.status_code == 200
    assert response.json() == {"aesthetic": AESTHETIC}
    assert frame.searches == [f'Song: "{SONG}"\nArtist: {ARTIST}']


async def test_second_request_is_served_from_the_cache(frame: Frame) -> None:
    await frame.aesthetic()

    response = await frame.aesthetic()

    assert response.json() == {"aesthetic": AESTHETIC}
    assert len(frame.searches) == 1


async def test_no_visual_data_reply_is_returned_and_not_cached(frame: Frame) -> None:
    frame.search_reply = "No visual data found for this song."

    response = await frame.aesthetic()
    await frame.aesthetic()

    assert response.json() == {"aesthetic": "No visual data found for this song."}
    assert len(frame.searches) == 2


async def test_empty_search_reply_returns_502_with_reason(frame: Frame) -> None:
    frame.search_reply = ""

    response = await frame.aesthetic()

    assert response.status_code == 502
    assert response.json() == {
        "detail": "gpt-4o-search-preview returned empty response"
    }


async def test_transform_caches_the_aesthetic_for_get_aesthetic(frame: Frame) -> None:
    photo = BytesIO()
    Image.new("RGB", (64, 48), "red").save(photo, format="JPEG")
    upload = await frame.client.put(
        "/images", files={"file": ("photo.jpg", photo.getvalue(), "image/jpeg")}
    )
    await frame.client.post(
        "/images",
        params={
            "image_id": upload.json()["image_id"],
            "song_title": SONG,
            "song_artists": ARTIST,
        },
    )

    response = await frame.aesthetic()

    assert response.json() == {"aesthetic": AESTHETIC}
    assert len(frame.searches) == 1
