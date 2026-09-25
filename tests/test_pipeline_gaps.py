"""Pipeline behaviour CI mutation testing found untested once item B changed pipeline.py.

Slice: captions, song looks and edit prompts from the local vision model
(docs/tasks/local-ai/task.md, item B).
"""

import json
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
import respx
from vlm_fakes import VLM_CHAT, chat_reply, is_aesthetic_request, mock_itunes

from local_shazam.server import create_app


@pytest.fixture
async def frame(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[httpx.AsyncClient]:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.delenv("VLM_BASE_URL", raising=False)
    app = create_app()
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://frame"
        ) as client,
    ):
        yield client


async def test_song_without_itunes_data_still_names_the_requested_artist(
    frame: httpx.AsyncClient,
) -> None:
    requests: list[dict[str, object]] = []

    def vlm(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if is_aesthetic_request(body):
            requests.append(body)
        return chat_reply("A look.")

    with respx.mock(assert_all_called=False) as mock:
        mock_itunes(mock, found=False)
        mock.post(VLM_CHAT).mock(side_effect=vlm)
        await frame.get(
            "/aesthetic", params={"song_title": "Teardrop", "artist": "Massive Attack"}
        )

    (text,) = requests[0]["messages"][1]["content"]  # type: ignore[index]
    assert "Artist: Massive Attack" in text["text"]
