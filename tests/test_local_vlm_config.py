"""The API server finds the vision model server through VLM_BASE_URL, reports its failures as 502, and does not retry them.

Slice: captions, song looks and edit prompts from the local vision model
(docs/tasks/local-ai/task.md, item B).
"""

import base64
from collections.abc import AsyncIterator
from io import BytesIO
from pathlib import Path

import httpx
import pytest
import respx
from PIL import Image
from vlm_fakes import VLM_CHAT, chat_reply, mock_itunes

from local_shazam.server import create_app


@pytest.fixture
async def client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[httpx.AsyncClient]:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.delenv("VLM_BASE_URL", raising=False)
    app = create_app()
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://frame"
        ) as frame,
    ):
        yield frame


async def test_vlm_base_url_sends_every_chat_request_to_that_server(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("VLM_BASE_URL", "http://vlm.test:9000/v1")
    monkeypatch.delenv("FLUX_BASE_URL", raising=False)
    photo = BytesIO()
    Image.new("RGB", (64, 48), "red").save(photo, format="JPEG")

    app = create_app()
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://frame"
        ) as frame,
    ):
        with respx.mock() as mock:
            mock_itunes(mock)
            chat = mock.post("http://vlm.test:9000/v1/chat/completions").mock(
                return_value=chat_reply("A red photo.")
            )
            mock.post("http://127.0.0.1:8081/v1/images/edits").respond(
                200,
                json={
                    "created": 0,
                    "data": [{"b64_json": base64.b64encode(b"P").decode()}],
                },
            )
            response = await frame.post(
                "/images",
                data={"song_title": "bad guy", "song_artists": "Billie Eilish"},
                files={"file": ("photo.jpg", photo.getvalue(), "image/jpeg")},
            )

    assert response.status_code == 200, response.text
    # caption, song look, edit prompt
    assert chat.call_count == 3


async def test_vision_model_error_returns_502_after_one_request(
    client: httpx.AsyncClient,
) -> None:
    with respx.mock() as mock:
        mock_itunes(mock)
        vlm = mock.post(VLM_CHAT).respond(500, json={"detail": "out of memory"})
        response = await client.get(
            "/aesthetic", params={"song_title": "bad guy", "artist": "Billie Eilish"}
        )

    assert response.status_code == 502
    assert response.json()["detail"].startswith("Vision model failed:")
    assert vlm.call_count == 1


async def test_unreachable_vision_model_returns_502(client: httpx.AsyncClient) -> None:
    with respx.mock() as mock:
        mock_itunes(mock)
        mock.post(VLM_CHAT).mock(side_effect=httpx.ConnectError("refused"))
        response = await client.get(
            "/aesthetic", params={"song_title": "bad guy", "artist": "Billie Eilish"}
        )

    assert response.status_code == 502
    assert response.json()["detail"].startswith("Vision model failed:")
