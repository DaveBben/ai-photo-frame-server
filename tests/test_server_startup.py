"""The API server's start command and startup checks, with uvicorn faked.

Added for item A (docs/tasks/local-ai/task.md): CI mutation testing reaches every
line of server.py once a change touches it, and these lines had no test.
"""

from pathlib import Path
from typing import Any

import pytest

from local_shazam import server


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
