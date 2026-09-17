"""GET /aesthetic through the real app, with the Mac mini's vision model server and iTunes faked.

Slice: Look up a song's aesthetic in one place (docs/tasks/restructure-layers/task.md),
then captions, song looks and edit prompts from the local vision model
(docs/tasks/local-ai/task.md, item B).
"""

import base64
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path

import httpx
import pytest
import respx
from PIL import Image
from vlm_fakes import (
    ITUNES_SEARCH,
    VLM_CHAT,
    VLM_MODEL,
    chat_reply,
    cover_jpeg,
    is_aesthetic_request,
    mock_itunes,
)

from local_shazam.prompts import load_prompt
from local_shazam.server import create_app

SONG = "bad guy"
ARTIST = "Billie Eilish"
AESTHETIC = "Lime green overhead strobe, crushed blacks, #8ACE00."
EDIT_PROMPT = "Relight the scene with a lime green overhead strobe."


@dataclass
class Frame:
    """The app as the photo frame sees it, plus every song-look request sent to the vision model."""

    client: httpx.AsyncClient
    mock: respx.MockRouter
    search_reply: str = AESTHETIC
    searches: list[dict[str, object]] = field(default_factory=list)

    async def aesthetic(self) -> httpx.Response:
        return await self.client.get(
            "/aesthetic", params={"song_title": SONG, "artist": ARTIST}
        )


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
            recorded = Frame(client=client, mock=mock)

            def vlm(request: httpx.Request) -> httpx.Response:
                body = json.loads(request.content)
                if is_aesthetic_request(body):
                    recorded.searches.append(body)
                    return chat_reply(recorded.search_reply)
                if body["messages"][0]["role"] == "system":
                    return chat_reply(EDIT_PROMPT)
                return chat_reply("A red photo.")

            mock.post(VLM_CHAT).mock(side_effect=vlm)
            mock_itunes(mock)

            yield recorded


async def test_uncached_song_is_described_from_its_album_cover(frame: Frame) -> None:
    response = await frame.aesthetic()

    assert response.status_code == 200
    assert response.json() == {"aesthetic": AESTHETIC}
    itunes = frame.mock.routes["itunes"].calls.last.request
    assert dict(itunes.url.params) == {
        "term": f"{SONG} {ARTIST}",
        "entity": "song",
        "limit": "1",
    }
    assert len(frame.searches) == 1
    request = frame.searches[0]
    assert request["model"] == VLM_MODEL
    messages = request["messages"]
    assert messages[0] == {  # type: ignore[index]
        "role": "system",
        "content": load_prompt("search_aesthetic"),
    }
    cover, text = messages[1]["content"]  # type: ignore[index]
    assert cover == {
        "type": "image_url",
        "image_url": {
            "url": "data:image/jpeg;base64," + base64.b64encode(cover_jpeg()).decode()
        },
    }
    assert text["type"] == "text"
    for line in (
        f'Song: "{SONG}"',
        f"Artist: {ARTIST}",
        "Album: WHEN WE ALL FALL ASLEEP, WHERE DO WE GO?",
        "Genre: Alternative",
        "Released: 2019-03-29",
    ):
        assert line in text["text"]


async def test_song_missing_from_itunes_is_described_without_a_cover(
    frame: Frame,
) -> None:
    mock_itunes(frame.mock, found=False)

    response = await frame.aesthetic()

    assert response.json() == {"aesthetic": AESTHETIC}
    (only,) = frame.searches[0]["messages"][1]["content"]  # type: ignore[index]
    assert only["type"] == "text"
    assert "No catalog data found." in only["text"]
    assert f'Song: "{SONG}"' in only["text"]


@pytest.mark.parametrize(
    "failure",
    [httpx.Response(503), httpx.ConnectError("itunes unreachable")],
    ids=["itunes-503", "itunes-unreachable"],
)
async def test_itunes_failure_is_treated_as_no_catalog_data(
    frame: Frame, failure: httpx.Response | Exception
) -> None:
    route = frame.mock.get(ITUNES_SEARCH, name="itunes")
    if isinstance(failure, Exception):
        route.mock(side_effect=failure)
    else:
        route.mock(return_value=failure)

    response = await frame.aesthetic()

    assert response.status_code == 200
    (only,) = frame.searches[0]["messages"][1]["content"]  # type: ignore[index]
    assert "No catalog data found." in only["text"]


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
    assert response.json() == {"detail": "Vision model returned an empty response"}


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
