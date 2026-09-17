"""The Flux server's start command loads the pinned model and listens where the Mac mini's clients expect, with mflux and uvicorn faked.

Slice: Flux server on the Mac mini (docs/tasks/local-ai/task.md, item 2). Added after
the table: CI mutation testing showed no test reached main() or the seed's type.
Pins: docs/adr/local-ai/generate-restyled-images-on-the-mac-mini.md items 1 and 7.
"""

import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import httpx
import pytest
from PIL import Image

from local_shazam import flux_server


async def test_main_loads_klein_4b_and_serves_on_all_interfaces_port_8081(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loaded: list[str] = []
    served: dict[str, Any] = {}

    class Flux2KleinEdit:
        def __init__(self, *, model_path: str) -> None:
            loaded.append(model_path)

        def generate_image(
            self, *, width: int, height: int, **_: Any
        ) -> SimpleNamespace:
            return SimpleNamespace(image=Image.new("RGB", (width, height)))

    variants = ModuleType("mflux.models.flux2.variants")
    variants.Flux2KleinEdit = Flux2KleinEdit  # type: ignore[attr-defined]
    for name in ("mflux", "mflux.models", "mflux.models.flux2"):
        monkeypatch.setitem(sys.modules, name, ModuleType(name))
    monkeypatch.setitem(sys.modules, "mflux.models.flux2.variants", variants)
    monkeypatch.setattr(
        flux_server.uvicorn,
        "run",
        lambda app, **kwargs: served.update(app=app, **kwargs),
    )

    flux_server.main()

    assert loaded == ["Runpod/FLUX.2-klein-4B-mflux-4bit"]
    app = served.pop("app")
    assert served == {"host": "0.0.0.0", "port": 8081}  # noqa: S104
    async with app.router.lifespan_context(
        app
    ):  # the startup generation uses the loaded model
        pass


class IntSeedModel:
    """Fails like a real model would if the seed is not a whole number."""

    def __init__(self) -> None:
        self.seeds: list[object] = []

    def generate_image(
        self, *, seed: object, width: int, height: int, **_: Any
    ) -> SimpleNamespace:
        if not isinstance(seed, int):
            raise TypeError(f"seed must be an int, got {seed!r}")
        self.seeds.append(seed)
        return SimpleNamespace(image=Image.new("RGB", (width, height)))


async def test_every_generation_gets_a_whole_number_seed(tmp_path: Path) -> None:
    model = IntSeedModel()
    app = flux_server.create_app(model)
    photo = tmp_path / "photo.png"
    Image.new("RGB", (64, 48)).save(photo)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://flux"
        ) as client,
    ):
        response = await client.post(
            "/v1/images/edits",
            files={"image": ("photo.png", photo.read_bytes(), "image/png")},
            data={"prompt": "green"},
        )

    assert response.status_code == 200, response.text
    assert len(model.seeds) == 2
