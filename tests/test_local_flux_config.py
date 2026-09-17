"""The API server finds the Flux server through FLUX_BASE_URL and needs no Black Forest Labs key.

Slice: Restyle a photo with the image made by the local Flux server
(docs/tasks/local-ai/task.md, item A).
"""

import base64
from io import BytesIO
from pathlib import Path

import httpx
import pytest
import respx
from PIL import Image
from vlm_fakes import mock_itunes

from local_shazam.server import create_app


async def test_server_starts_without_a_black_forest_labs_or_openai_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.delenv("BFL_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)  # no .env file supplies a key

    app = create_app()
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://frame"
        ) as client,
    ):
        assert (await client.get("/health")).status_code == 200


async def test_flux_base_url_sends_the_edit_to_that_server(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("FLUX_BASE_URL", "http://flux.test:9000/v1")
    png = b"PNG-from-flux-test"

    app = create_app()
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://frame"
        ) as client,
    ):
        with respx.mock(assert_all_called=False) as mock:
            mock.post("http://127.0.0.1:8080/v1/chat/completions").respond(
                200,
                json={
                    "id": "c",
                    "object": "chat.completion",
                    "created": 0,
                    "model": "gpt-4o",
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": "text"},
                            "finish_reason": "stop",
                        }
                    ],
                },
            )
            mock_itunes(mock)
            edit = mock.post("http://flux.test:9000/v1/images/edits").respond(
                200,
                json={
                    "created": 0,
                    "data": [{"b64_json": base64.b64encode(png).decode()}],
                },
            )
            photo = BytesIO()
            Image.new("RGB", (64, 48), "red").save(photo, format="JPEG")
            upload = await client.put(
                "/images", files={"file": ("photo.jpg", photo.getvalue(), "image/jpeg")}
            )
            response = await client.post(
                "/images",
                params={
                    "image_id": upload.json()["image_id"],
                    "song_title": "bad guy",
                    "song_artists": "Billie Eilish",
                },
            )

    assert edit.call_count == 1
    assert response.content == png
