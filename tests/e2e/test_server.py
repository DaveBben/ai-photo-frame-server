"""Drive the server the way the photo frame does: a real process over HTTP."""

import os
import socket
import subprocess
import sys
import time
from collections.abc import Iterator

import httpx
import pytest

pytestmark = pytest.mark.e2e


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port: int = s.getsockname()[1]
        return port


@pytest.fixture
def server_url() -> Iterator[str]:
    port = _free_port()
    env = {
        **os.environ,
        "SERVER_HOST": "127.0.0.1",
        "SERVER_PORT": str(port),
        "BFL_API_KEY": "e2e-unused",
        "OPENAI_API_KEY": "e2e-unused",
    }
    proc = subprocess.Popen(  # noqa: S603
        [sys.executable, "-m", "local_shazam.server"],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    url = f"http://127.0.0.1:{port}"
    try:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            try:
                httpx.get(f"{url}/health", timeout=1)
                break
            except httpx.TransportError:
                time.sleep(0.1)
        else:
            pytest.fail("server did not start listening within 15s")
        yield url
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def test_health_responds_over_http(server_url: str) -> None:
    response = httpx.get(f"{server_url}/health", timeout=5)
    assert response.json() == {"status": "healthy"}
