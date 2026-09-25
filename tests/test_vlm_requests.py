"""The exact requests sent to the vision model and iTunes: message shapes, token limits, timeout, image encoding and catalog lines.

Slice: captions, song looks and edit prompts from the local vision model
(docs/tasks/local-ai/task.md, item B). The caption and edit-prompt tests go through
POST /images since shazam-restyle story 1 removed the photo store. Gap tests found while building it: CI's mutation
step checks every line of a changed file, and the route tests leave these unasserted.
"""

import base64
import json
from io import BytesIO
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from PIL import Image
from vlm_fakes import (
    COVER_600,
    ITUNES_SEARCH,
    ITUNES_TRACK,
    VLM_MODEL,
    chat_reply,
    cover_jpeg,
    mock_itunes,
)

from local_shazam import pipeline
from local_shazam.aesthetic_cache import AestheticCache
from local_shazam.itunes_client import ItunesClient
from local_shazam.openai_client import OpenAIClient
from local_shazam.prompts import load_prompt
from local_shazam.server import create_app

VLM = "http://vlm.test/v1"
FLUX = "http://flux.test/v1"


def _record(mock: respx.MockRouter, reply: str = "text") -> list[httpx.Request]:
    requests: list[httpx.Request] = []

    def answer(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return chat_reply(reply)

    mock.post(f"{VLM}/chat/completions").mock(side_effect=answer)
    return requests


def _body(request: httpx.Request) -> dict[str, Any]:
    body: dict[str, Any] = json.loads(request.content)
    return body


async def _restyle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, photo: Image.Image
) -> list[dict[str, Any]]:
    """Send the photo for "bad guy" through POST /images and return every vision model request body."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("VLM_BASE_URL", VLM)
    monkeypatch.setenv("FLUX_BASE_URL", FLUX)
    buf = BytesIO()
    photo.save(buf, format="PNG")
    app = create_app()
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://frame"
        ) as frame,
    ):
        with respx.mock(assert_all_called=False) as mock:
            mock_itunes(mock)
            requests = _record(mock, reply="A photo.")
            mock.post(f"{FLUX}/images/edits").respond(
                200,
                json={
                    "created": 0,
                    "data": [{"b64_json": base64.b64encode(b"P").decode()}],
                },
            )
            response = await frame.post(
                "/images",
                data={"song_title": "bad guy", "song_artists": "Billie Eilish"},
                files={"file": ("photo.png", buf.getvalue(), "image/png")},
            )
    assert response.status_code == 200, response.text
    return [_body(r) for r in requests]


async def test_caption_request_sends_a_quality_85_jpeg_within_1024px_and_800_tokens(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    portrait = Image.new("RGBA", (1500, 2000), "red")
    bodies = await _restyle(tmp_path, monkeypatch, portrait)

    (body,) = [b for b in bodies if b["messages"][0]["role"] == "user"]
    image_url = body["messages"][0]["content"][0]
    assert body["model"] == VLM_MODEL
    assert body["max_tokens"] == 800
    assert body["messages"] == [
        {
            "role": "user",
            "content": [
                image_url,
                {"type": "text", "text": load_prompt("describe_image")},
            ],
        }
    ]
    assert image_url["type"] == "image_url"
    prefix, b64 = image_url["image_url"]["url"].split(",", 1)
    assert prefix == "data:image/jpeg;base64"
    sent = Image.open(BytesIO(base64.b64decode(b64)))
    assert sent.size == (768, 1024)
    reference = BytesIO()
    Image.new("RGB", (768, 1024), "red").save(reference, format="JPEG", quality=85)
    assert sent.quantization == Image.open(reference).quantization  # type: ignore[attr-defined]


async def test_edit_prompt_request_is_the_flux_transform_system_prompt_and_one_text_block(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    AestheticCache(tmp_path / "aesthetic_cache.db").put(
        "Billie Eilish", "bad guy", "Lime green strobe."
    )
    bodies = await _restyle(tmp_path, monkeypatch, Image.new("RGB", (64, 48), "red"))

    (body,) = [
        b
        for b in bodies
        if b["messages"][0]["content"] == load_prompt("flux_transform")
    ]
    assert body["max_tokens"] == 500
    assert body["messages"] == [
        {"role": "system", "content": load_prompt("flux_transform")},
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "Transform this photo to match the vibe of 'bad guy' by Billie Eilish.\n\n"
                    "VISUAL AESTHETIC:\nLime green strobe.\n\n"
                    "IMAGE CONTEXT:\nDescription: A photo.\n\n"
                    "Apply the visual aesthetic above to transform the image.",
                }
            ],
        },
    ]


async def test_song_look_request_allows_1000_tokens_and_120_seconds(
    tmp_path: Path,
) -> None:
    with respx.mock() as mock:
        mock_itunes(mock)
        requests = _record(mock)
        await pipeline.get_aesthetic(
            OpenAIClient(VLM),
            ItunesClient(),
            AestheticCache(tmp_path / "cache.db"),
            "bad guy",
            "Billie Eilish",
        )

    body = _body(requests[0])
    assert body["max_tokens"] == 1000
    assert [m["role"] for m in body["messages"]] == ["system", "user"]
    assert requests[0].extensions["timeout"]["read"] == 120.0


async def test_song_missing_from_itunes_sends_no_catalog_data_as_its_own_line(
    tmp_path: Path,
) -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock_itunes(mock, found=False)
        requests = _record(mock)
        await pipeline.get_aesthetic(
            OpenAIClient(VLM),
            ItunesClient(),
            AestheticCache(tmp_path / "cache.db"),
            "bad guy",
            "Billie Eilish",
        )

    (text,) = _body(requests[0])["messages"][1]["content"]
    assert "No catalog data found." in text["text"].splitlines()


async def test_itunes_facts_are_the_matched_tracks_catalog_lines() -> None:
    track = {
        **ITUNES_TRACK,
        "trackName": "Bad Guy",
        "artistName": "BILLIE EILISH & Justin Bieber",
    }
    with respx.mock() as mock:
        mock.get(ITUNES_SEARCH).respond(
            200, json={"resultCount": 1, "results": [track]}
        )
        mock.get(COVER_600).respond(200, content=cover_jpeg())
        found = await ItunesClient().find_song("bad guy", "Billie Eilish")

    assert found is not None
    facts, cover = found
    assert facts.splitlines() == [
        "Track: Bad Guy",
        "Artist: BILLIE EILISH & Justin Bieber",
        "Album: WHEN WE ALL FALL ASLEEP, WHERE DO WE GO?",
        "Genre: Alternative",
        "Released: 2019-03-29",
    ]
    assert cover == cover_jpeg()
