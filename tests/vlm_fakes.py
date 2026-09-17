"""Fakes for the Mac mini's vision model server and the iTunes Search API, shared by the route tests.

Slice: captions, song looks and edit prompts from the local vision model
(docs/tasks/local-ai/task.md, item B).
"""

from io import BytesIO
from typing import Any

import httpx
import respx
from PIL import Image

from local_shazam.prompts import load_prompt

VLM_CHAT = "http://127.0.0.1:8080/v1/chat/completions"
VLM_MODEL = "mlx-community/Qwen3-VL-4B-Instruct-4bit"
ITUNES_SEARCH = "https://itunes.apple.com/search"
COVER_100 = "https://is1-ssl.mzstatic.com/image/thumb/Music/bad-guy/100x100bb.jpg"
COVER_600 = "https://is1-ssl.mzstatic.com/image/thumb/Music/bad-guy/600x600bb.jpg"
ITUNES_TRACK = {
    "trackName": "bad guy",
    "artistName": "Billie Eilish",
    "collectionName": "WHEN WE ALL FALL ASLEEP, WHERE DO WE GO?",
    "primaryGenreName": "Alternative",
    "releaseDate": "2019-03-29T12:00:00Z",
    "artworkUrl100": COVER_100,
}


def cover_jpeg() -> bytes:
    buf = BytesIO()
    Image.new("RGB", (600, 600), (10, 10, 10)).save(buf, format="JPEG")
    return buf.getvalue()


def chat_reply(content: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "id": "chatcmpl-1",
            "object": "chat.completion",
            "created": 0,
            "model": VLM_MODEL,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                }
            ],
        },
    )


def is_aesthetic_request(body: dict[str, Any]) -> bool:
    """True when the chat request asks for a song's look (its system prompt is search_aesthetic)."""
    first = body["messages"][0]
    return bool(
        first["role"] == "system"
        and first["content"] == load_prompt("search_aesthetic")
    )


def mock_itunes(mock: respx.MockRouter, *, found: bool = True) -> respx.Route:
    """iTunes answers one song with its cover, or no results."""
    mock.get(COVER_600).respond(200, content=cover_jpeg())
    return mock.get(ITUNES_SEARCH, name="itunes").respond(
        200,
        json={
            "resultCount": 1 if found else 0,
            "results": [ITUNES_TRACK] if found else [],
        },
    )
