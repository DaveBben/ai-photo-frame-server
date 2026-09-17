"""The API server's start command and startup checks, with uvicorn faked.

Added for item A (docs/tasks/local-ai/task.md): CI mutation testing reaches every
line of server.py once a change touches it, and these lines had no test.
"""

from pathlib import Path
from typing import Any

import pytest

from local_shazam import server


async def test_server_refuses_to_start_without_an_openai_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)  # no .env file supplies a key

    app = server.create_app()
    with pytest.raises(
        RuntimeError, match=r"^Missing required environment variables: OPENAI_API_KEY$"
    ):
        async with app.router.lifespan_context(app):
            pass


def test_main_serves_the_app_factory_with_the_configured_address(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SERVER_HOST", "127.0.0.2")
    monkeypatch.setenv("SERVER_PORT", "9123")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    monkeypatch.setattr(
        server.uvicorn, "run", lambda *args, **kwargs: calls.append((args, kwargs))
    )

    server.main()

    assert calls == [
        (
            ("local_shazam.server:create_app",),
            {
                "factory": True,
                "host": "127.0.0.2",
                "port": 9123,
                "log_level": "warning",
            },
        )
    ]
