"""The Flux server loads the model and runs every generation on one thread, because MLX cannot evaluate a graph built on another thread.

Bug: on the Mac mini, local-shazam-flux exited at startup with
"RuntimeError: There is no Stream(cpu, 0) in current thread": main() built
Flux2KleinEdit on the main thread and the startup generation ran on an anyio
worker thread. The front-door reproduction is tests/macmini/test_flux_server.py.
"""

import sys
import threading
from io import BytesIO
from types import ModuleType, SimpleNamespace
from typing import Any

import httpx
import pytest
from PIL import Image

from local_shazam import flux_server


async def test_model_load_and_every_generation_share_one_thread(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    load_threads: list[int] = []
    generate_threads: list[int] = []

    class Flux2KleinEdit:
        def __init__(self, **_: str) -> None:
            load_threads.append(threading.get_ident())

        def generate_image(
            self, *, width: int, height: int, **_: Any
        ) -> SimpleNamespace:
            generate_threads.append(threading.get_ident())
            return SimpleNamespace(image=Image.new("RGB", (width, height)))

    variants = ModuleType("mflux.models.flux2.variants")
    variants.Flux2KleinEdit = Flux2KleinEdit  # type: ignore[attr-defined]
    for name in ("mflux", "mflux.models", "mflux.models.flux2"):
        monkeypatch.setitem(sys.modules, name, ModuleType(name))
    monkeypatch.setitem(sys.modules, "mflux.models.flux2.variants", variants)
    served: dict[str, Any] = {}
    monkeypatch.setattr(
        flux_server.uvicorn, "run", lambda app, **_: served.update(app=app)
    )

    flux_server.main()
    app = served["app"]
    photo = Image.new("RGB", (64, 48))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://flux"
        ) as client,
    ):
        for _ in range(2):
            buf = BytesIO()
            photo.save(buf, format="PNG")
            response = await client.post(
                "/v1/images/edits",
                files={"image": ("photo.png", buf.getvalue(), "image/png")},
                data={"prompt": "green"},
            )
            assert response.status_code == 200, response.text

    assert len(generate_threads) == 3
    assert set(generate_threads) == set(load_threads)
