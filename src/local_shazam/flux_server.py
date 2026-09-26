"""HTTP server that edits a photo with Flux.2 Klein on the Mac mini, answering the OpenAI images format."""

import asyncio
import base64
import os
import secrets
import time
from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from io import BytesIO
from typing import Annotated, Any

import uvicorn
from fastapi import FastAPI, Form, HTTPException, UploadFile
from PIL import Image
from starlette.formparsers import MultiPartParser

# Starlette writes any upload over 1 MB to a temporary file on disk. A spool size
# of 0 keeps every upload in memory, so no photo touches the Mac mini's disk
# (docs/adr/architecture/restyle-photos-in-memory-and-store-none.md).
# ponytail: no body-size cap before the read; the route's own image.read() already
# held the whole upload in memory, add a Content-Length check if that matters.
MultiPartParser.spool_max_size = 0

# MLX evaluates a graph only on the thread that built it, and the Mac mini has one GPU.
_worker = ThreadPoolExecutor(max_workers=1)
# A forked process copies the executor without its thread, so mutmut's forked
# test runs would wait forever; give each child its own executor.
os.register_at_fork(
    after_in_child=lambda: globals().update(_worker=ThreadPoolExecutor(max_workers=1))
)


def _generate_png(
    model: Any, prompt: str, reference: Image.Image, width: int, height: int
) -> bytes:
    """Run one generation from a reference image and return the result as PNG bytes."""
    # Any whole-number seed is valid; only its type is tested.
    seed = secrets.randbelow(2**31)  # pragma: no mutate
    # mflux applies the Orientation tag, from EXIF or XMP, to a Pillow image it is
    # given. The reference PNG it used to read carried neither, so drop both.
    reference.info.clear()
    result = model.generate_image(
        seed=seed,
        prompt=prompt,
        num_inference_steps=3,
        width=width,
        height=height,
        guidance=1.0,
        # mflux loads a Pillow image as given (mflux/utils/image_util.py:160), so no file is written.
        image_paths=[reference],
    )
    buf = BytesIO()
    result.image.save(buf, format="PNG")  # pragma: no mutate
    return buf.getvalue()


def create_app(model: Any) -> FastAPI:
    """Build the Flux server around a loaded image edit model."""

    async def generate(
        prompt: str, reference: Image.Image, width: int, height: int
    ) -> bytes:
        return await asyncio.wrap_future(
            _worker.submit(_generate_png, model, prompt, reference, width, height)
        )

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        # mflux loads the weights on the first generation, so pay that before serving.
        await generate("warm up", Image.new("RGB", (512, 512)), 800, 480)
        yield

    app = FastAPI(lifespan=lifespan)

    @app.post("/v1/images/edits")
    async def edit_image(
        image: UploadFile,
        prompt: Annotated[str, Form()],
        size: Annotated[str, Form()] = "800x480",
    ) -> dict[str, Any]:
        try:
            width, height = (int(n) for n in size.split("x"))
        except ValueError:
            raise HTTPException(
                400, "size must be WIDTHxHEIGHT, e.g. 800x480"
            ) from None
        try:
            reference = Image.open(BytesIO(await image.read())).convert("RGB")
        except OSError:
            raise HTTPException(400, "image is not a readable photo") from None
        reference.thumbnail((512, 512))
        png = await generate(prompt, reference, width, height)
        return {
            "created": int(time.time()),
            "data": [{"b64_json": base64.b64encode(png).decode()}],
        }

    return app


def main() -> None:
    """Load Flux.2 Klein and serve edits on 0.0.0.0:8081."""
    from mflux.models.flux2.variants import Flux2KleinEdit

    model = _worker.submit(
        Flux2KleinEdit, model_path="Runpod/FLUX.2-klein-4B-mflux-4bit"
    ).result()
    uvicorn.run(create_app(model), host="0.0.0.0", port=8081)  # noqa: S104
