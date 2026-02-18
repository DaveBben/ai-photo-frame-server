"""HTTP endpoints for local-shazam server."""

from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING
from uuid import UUID  # noqa: TC003 - needed at runtime for FastAPI/Pydantic

from fastapi import APIRouter, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response
from PIL import Image

from local_shazam.exceptions import ServiceError
from local_shazam.image_transformer import transform_image
from local_shazam.openai_client import OpenAIClient

_MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB

if TYPE_CHECKING:
    from local_shazam.aesthetic_cache import AestheticCache
    from local_shazam.config import Settings
    from local_shazam.process_images import ImageStore

router = APIRouter()


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}


@router.put("/images")
async def upload_image(request: Request, file: UploadFile) -> dict[str, str]:
    """Upload an image to the store.

    The image will be analyzed with GPT-4o and saved with its description.

    Args:
        request: FastAPI request (provides access to app state).
        file: Uploaded image file.

    Returns:
        JSON with the assigned image UUID.
    """
    image_store: ImageStore = request.app.state.image_store

    contents = await file.read()
    if len(contents) > _MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {_MAX_UPLOAD_SIZE // 1024 // 1024} MB",
        )

    try:
        img = Image.open(BytesIO(contents))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image: {e}") from e

    image_id = await image_store.put_image(img)
    return {"image_id": str(image_id)}


@router.get("/images")
async def get_random_image(request: Request) -> Response:
    """Return a random image.

    Args:
        request: FastAPI request (provides access to app state).

    Returns:
        JPEG image bytes with X-Image-ID header containing the image UUID.
    """
    image_store: ImageStore = request.app.state.image_store
    result = image_store.get_random_image()

    if result is None:
        raise HTTPException(status_code=404, detail="No images available")

    image_id, img = result
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=90)

    return Response(
        content=buf.getvalue(),
        media_type="image/jpeg",
        headers={"X-Image-ID": str(image_id)},
    )


@router.post("/images")
async def transform_image_endpoint(
    request: Request,
    image_id: UUID = Query(...),  # noqa: B008
    song_title: str = Query(...),
    song_artists: str = Query(...),
) -> Response:
    """Transform an image to match a song's aesthetic.

    Args:
        request: FastAPI request (provides access to app state).
        image_id: UUID of a previously uploaded image.
        song_title: Name of the song.
        song_artists: Artist name(s).

    Returns:
        PNG image bytes of the transformed image.
    """
    image_store: ImageStore = request.app.state.image_store
    settings: Settings = request.app.state.settings
    aesthetic_cache: AestheticCache = request.app.state.aesthetic_cache

    try:
        image_path = image_store.get_image_path(image_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    try:
        png_bytes = await transform_image(
            image_path=image_path,
            song_name=song_title,
            artist_name=song_artists,
            settings=settings,
            aesthetic_cache=aesthetic_cache,
        )
    except ServiceError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    return Response(content=png_bytes, media_type="image/png")


@router.get("/aesthetic")
async def get_aesthetic(
    request: Request,
    song_title: str = Query(...),
    artist: str = Query(...),
) -> dict[str, str]:
    """Get the visual aesthetic description for a song.

    Args:
        request: FastAPI request (provides access to app state).
        song_title: Name of the song.
        artist: Artist name.

    Returns:
        JSON with the aesthetic description.
    """
    settings: Settings = request.app.state.settings
    cache: AestheticCache = request.app.state.aesthetic_cache

    aesthetic = cache.get(artist, song_title)
    if aesthetic is None:
        try:
            client = OpenAIClient(settings.openai_api_key)
            aesthetic = await client.search_aesthetic(artist, song_title)
        except ServiceError as e:
            raise HTTPException(status_code=502, detail=str(e)) from e
        if "No visual data found" not in aesthetic:
            cache.put(artist, song_title, aesthetic)

    return {"aesthetic": aesthetic}
