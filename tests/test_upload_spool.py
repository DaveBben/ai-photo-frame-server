"""A photo over Starlette's 1 MB spool limit is never written to a temporary file.

Review of shazam-restyle story 1: Starlette's multipart parser rolls every upload
over 1 MB into tempfile.TemporaryFile, which writes the photo's bytes to disk.
Decision: docs/adr/architecture/restyle-photos-in-memory-and-store-none.md.
"""

import tempfile
from pathlib import Path
from typing import Any

import httpx
import pytest

from local_shazam.server import create_app


async def test_photo_over_1mb_is_never_written_to_a_temp_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    temp_files: list[object] = []
    real = tempfile.TemporaryFile

    def recording(*args: Any, **kwargs: Any) -> Any:
        temp_files.append(args)
        return real(*args, **kwargs)

    monkeypatch.setattr(tempfile, "TemporaryFile", recording)
    app = create_app()
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://frame"
        ) as client,
    ):
        response = await client.post(
            "/images",
            data={"song_title": "bad guy", "song_artists": "Billie Eilish"},
            files={"file": ("photo.jpg", b"\0" * (2 * 1024 * 1024))},
        )

    assert response.status_code == 400
    assert temp_files == []
