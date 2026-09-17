"""HTTP server that edits a photo with Flux.2 Klein on the Mac mini, answering the OpenAI images format."""

import base64
import secrets
import tempfile
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from io import BytesIO
from pathlib import Path
from typing import Annotated, Any

import anyio
import uvicorn
from fastapi import FastAPI, Form, HTTPException, UploadFile
from PIL import Image


def _generate_png(
    model: Any, prompt: str, reference: Image.Image, width: int, height: int
) -> bytes:
    """Run one generation from a reference image and return the result as PNG bytes."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "reference.png"
        reference.save(path, format="PNG")
        result = model.generate_image(
            seed=secrets.randbelow(2**31),
            prompt=prompt,
            num_inference_steps=3,
            width=width,
            height=height,
            guidance=1.0,
            image_paths=[path],
        )
    buf = BytesIO()
    result.image.save(buf, format="PNG")
    return buf.getvalue()


def create_app(model: Any) -> FastAPI:
    """Build the Flux server around a loaded image edit model."""
    # ponytail: one lock for the whole process, since the Mac mini has one GPU.
    lock = anyio.Lock()

    async def generate(
        prompt: str, reference: Image.Image, width: int, height: int
    ) -> bytes:
        async with lock:
            return await anyio.to_thread.run_sync(
                _generate_png, model, prompt, reference, width, height
            )

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        # mflux loads the weights on the first generation, so pay that before serving.
        await generate("warm up", Image.new("RGB", (512, 512)), 800, 480)
        yield

    app = FastAPI(title="local-shazam-flux", lifespan=lifespan)

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

    model = Flux2KleinEdit(model_path="Runpod/FLUX.2-klein-4B-mflux-4bit")
    uvicorn.run(create_app(model), host="0.0.0.0", port=8081)  # noqa: S104


if __name__ == "__main__":
    main()
