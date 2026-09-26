"""The Flux server edits a photo and answers in the OpenAI images format, with the model faked.

Slice: Flux server on the Mac mini (docs/tasks/local-ai/task.md, item 2).
Acceptance: Given the running VLM and Flux server WHEN I send a photo and an edit
prompt then I get back an edited 800x480 PNG. The front-door row runs against the
Mac mini in tests/macmini/test_flux_server.py; these rows run in CI.
"""

import base64
import threading
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from io import BytesIO
from types import SimpleNamespace
from typing import Any

import anyio
import httpx
from openai import AsyncOpenAI
from PIL import Image

from local_shazam.flux_server import create_app

PROMPT = "Bathe the scene in lime green overhead light"


class FakeModel:
    """Stands in for mflux's Flux2KleinEdit: records each generation and returns a solid image."""

    def __init__(
        self, color: tuple[int, int, int] = (0, 0, 255), delay: float = 0.0
    ) -> None:
        self.color = color
        self.delay = delay
        self.calls: list[dict[str, Any]] = []
        self.active = 0
        self.max_active = 0
        self._counter = threading.Lock()

    def generate_image(
        self,
        *,
        seed: int,
        prompt: str,
        num_inference_steps: int,
        height: int,
        width: int,
        guidance: float,
        image_paths: list[Image.Image],
    ) -> SimpleNamespace:
        with self._counter:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        self.calls.append(
            {
                "seed": seed,
                "prompt": prompt,
                "steps": num_inference_steps,
                "guidance": guidance,
                "size": (width, height),
                "reference_size": image_paths[0].size,
            }
        )
        time.sleep(self.delay)
        with self._counter:
            self.active -= 1
        return SimpleNamespace(image=Image.new("RGB", (width, height), self.color))


def _jpeg(width: int, height: int) -> bytes:
    buf = BytesIO()
    Image.new("RGB", (width, height), (200, 120, 40)).save(buf, format="JPEG")
    return buf.getvalue()


def _png_of(response: httpx.Response) -> Image.Image:
    assert response.status_code == 200, response.text
    data = base64.b64decode(response.json()["data"][0]["b64_json"])
    return Image.open(BytesIO(data))


@asynccontextmanager
async def _flux(model: FakeModel) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(model)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://flux"
        ) as client,
    ):
        yield client


async def _edit(
    client: httpx.AsyncClient,
    image: bytes,
    size: str | None = None,
    filename: str = "photo.jpg",
) -> httpx.Response:
    data = {"prompt": PROMPT}
    if size is not None:
        data["size"] = size
    return await client.post(
        "/v1/images/edits",
        files={"image": (filename, image, "image/jpeg")},
        data=data,
    )


# Row 2
async def test_openai_package_reads_the_edited_image() -> None:
    model = FakeModel(color=(0, 0, 255))
    async with _flux(model) as client:
        openai = AsyncOpenAI(
            api_key="unused", base_url="http://flux/v1", http_client=client
        )
        result = await openai.images.edit(
            image=("photo.jpg", _jpeg(1024, 1024), "image/jpeg"), prompt=PROMPT
        )

    assert result.data is not None
    b64 = result.data[0].b64_json
    assert b64 is not None
    png = Image.open(BytesIO(base64.b64decode(b64)))
    assert png.format == "PNG"
    assert png.size == (800, 480)
    assert png.convert("RGB").getpixel((400, 240)) == (0, 0, 255)
    assert model.calls[-1]["prompt"] == PROMPT


# Row 3
async def test_size_is_honoured_and_a_malformed_size_is_rejected() -> None:
    model = FakeModel()
    async with _flux(model) as client:
        png = _png_of(await _edit(client, _jpeg(640, 480), size="512x288"))
        calls_before_bad_size = len(model.calls)
        bad = await _edit(client, _jpeg(640, 480), size="big")

    assert png.size == (512, 288)
    assert bad.status_code == 400
    assert "size must be WIDTHxHEIGHT, e.g. 800x480" in bad.text
    assert len(model.calls) == calls_before_bad_size


# Row 4
async def test_reference_is_shrunk_to_512_on_its_long_edge_and_never_enlarged() -> None:
    model = FakeModel()
    async with _flux(model) as client:
        _png_of(await _edit(client, _jpeg(1024, 768)))
        _png_of(await _edit(client, _jpeg(300, 200)))

    assert [c["reference_size"] for c in model.calls[-2:]] == [(512, 384), (300, 200)]


# Row 5
async def test_every_generation_uses_3_steps_and_guidance_1() -> None:
    model = FakeModel()
    async with _flux(model) as client:
        _png_of(await _edit(client, _jpeg(640, 480)))

    assert len(model.calls) == 2
    assert all(c["steps"] == 3 and c["guidance"] == 1.0 for c in model.calls)


# Row 6
async def test_a_file_that_is_not_a_photo_is_rejected_without_generating() -> None:
    model = FakeModel()
    async with _flux(model) as client:
        calls_after_startup = len(model.calls)
        response = await _edit(client, b"not a photo at all", filename="notes.txt")

    assert response.status_code == 400
    assert "image is not a readable photo" in response.text
    assert len(model.calls) == calls_after_startup


# Row 7
async def test_two_requests_together_both_succeed_one_generation_at_a_time() -> None:
    model = FakeModel(delay=0.2)
    responses: list[httpx.Response] = []
    async with _flux(model) as client:

        async def send() -> None:
            responses.append(await _edit(client, _jpeg(640, 480)))

        async with anyio.create_task_group() as tg:
            tg.start_soon(send)
            tg.start_soon(send)

    assert [_png_of(r).size for r in responses] == [(800, 480), (800, 480)]
    assert model.max_active == 1


# Row 8
async def test_model_generates_once_at_startup_before_any_request() -> None:
    model = FakeModel()
    async with _flux(model):
        assert len(model.calls) == 1
