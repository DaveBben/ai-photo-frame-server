"""HTTP endpoints for local-shazam server."""

from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING

from fastapi import APIRouter, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response
from PIL import Image

from local_shazam import pipeline
from local_shazam.exceptions import ServiceError

_MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB

if TYPE_CHECKING:
    from local_shazam.aesthetic_cache import AestheticCache
    from local_shazam.flux2_client import Flux2Client
    from local_shazam.itunes_client import ItunesClient
    from local_shazam.openai_client import OpenAIClient

router = APIRouter()


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}


@router.post("/images")
async def transform_image_endpoint(
    request: Request,
    file: UploadFile,
    song_title: str = Form(...),
    song_artists: str = Form(...),
) -> Response:
    """Restyle the uploaded photo to match a song's aesthetic, keeping it in memory.

    Args:
        request: FastAPI request (provides access to app state).
        file: Uploaded photo.
        song_title: Name of the song.
        song_artists: Artist name(s).

    Returns:
        PNG image bytes of the transformed image.
    """
    openai_client: OpenAIClient = request.app.state.openai_client
    itunes_client: ItunesClient = request.app.state.itunes_client
    flux_client: Flux2Client = request.app.state.flux_client
    aesthetic_cache: AestheticCache = request.app.state.aesthetic_cache

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

    try:
        png_bytes = await pipeline.transform(
            openai_client=openai_client,
            itunes_client=itunes_client,
            flux_client=flux_client,
            aesthetic_cache=aesthetic_cache,
            image=img,
            song_name=song_title,
            artist_name=song_artists,
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
    openai_client: OpenAIClient = request.app.state.openai_client
    itunes_client: ItunesClient = request.app.state.itunes_client
    aesthetic_cache: AestheticCache = request.app.state.aesthetic_cache

    try:
        aesthetic = await pipeline.get_aesthetic(
            openai_client=openai_client,
            itunes_client=itunes_client,
            aesthetic_cache=aesthetic_cache,
            song_name=song_title,
            artist_name=artist,
        )
    except ServiceError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    return {"aesthetic": aesthetic}
