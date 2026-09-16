"""Orchestration for the upload step (save, describe, save the described copy), the aesthetic step (look up a song's aesthetic, cache first) and the transform step (write the edit prompt, then call the image model)."""

import base64
import uuid
from io import BytesIO
from pathlib import Path
from uuid import UUID

import anyio
from PIL import Image, ImageOps
from PIL.Image import Resampling

from local_shazam.aesthetic_cache import AestheticCache
from local_shazam.exceptions import ServiceError
from local_shazam.flux2_client import Flux2Client
from local_shazam.image_store import ImageStore, extract_image_metadata
from local_shazam.logger import get_logger
from local_shazam.openai_client import OpenAIClient
from local_shazam.prompts import load_prompt

log = get_logger(__name__)


def _prepare_image_for_api(img: Image.Image) -> str:
    """Thumbnail an image to <=1024px and return base64-encoded JPEG."""
    img = img.copy()
    img.thumbnail((1024, 1024), Resampling.LANCZOS)
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


async def _describe_image(client: OpenAIClient, img: Image.Image) -> str:
    """Call GPT-4o vision to describe the image."""
    b64_data = _prepare_image_for_api(img)
    return await client.describe_image(
        b64_data, load_prompt("describe_image"), max_tokens=800
    )


async def describe_and_store(
    openai_client: OpenAIClient,
    image_store: ImageStore,
    image: Image.Image,
) -> UUID:
    """Save the upright RGB photo, describe it with the vision model, save the described copy, and return its id."""
    image_id = uuid.uuid4()

    img = ImageOps.exif_transpose(image)
    if img is None:
        img = image
    if img.mode != "RGB":
        img = img.convert("RGB")

    image_store.save_original(image_id, img)

    description = await _describe_image(openai_client, img)
    log.info("Got description (%d chars)", len(description))

    image_store.save_described(image_id, img, description)
    return image_id


async def get_aesthetic(
    openai_client: OpenAIClient,
    aesthetic_cache: AestheticCache,
    song_name: str,
    artist_name: str,
) -> str:
    """Return the song's cached aesthetic, or search for it and cache the reply unless it contains "No visual data found"."""
    aesthetic = aesthetic_cache.get(artist_name, song_name)
    if aesthetic is None:
        aesthetic = await openai_client.search_aesthetic(artist_name, song_name)
        if "No visual data found" not in aesthetic:
            aesthetic_cache.put(artist_name, song_name, aesthetic)
    return aesthetic


async def _generate_flux_prompt(
    client: OpenAIClient,
    cache: AestheticCache,
    image_path: Path,
    song_name: str,
    artist_name: str,
) -> str:
    """Use GPT-4o with image metadata and cached aesthetics to generate a Flux.2 prompt."""
    aesthetic = await get_aesthetic(
        openai_client=client,
        aesthetic_cache=cache,
        song_name=song_name,
        artist_name=artist_name,
    )

    metadata = extract_image_metadata(image_path)

    # Build context from available metadata
    context_parts = []

    if metadata["description"]:
        context_parts.append(f"Description: {metadata['description']}")

    if metadata["gps_coords"]:
        context_parts.append(f"GPS Coordinates: {metadata['gps_coords']}")

    if metadata["datetime"]:
        context_parts.append(f"Date/Time: {metadata['datetime']}")

    camera_info = " ".join(
        filter(None, [metadata["camera_make"], metadata["camera_model"]])
    )
    if camera_info:
        context_parts.append(f"Camera: {camera_info}")

    image_context = (
        "\n".join(context_parts) if context_parts else "No metadata available"
    )

    user_message = (
        f"Transform this photo to match the vibe of '{song_name}' by {artist_name}.\n\n"
        f"VISUAL AESTHETIC:\n{aesthetic}\n\n"
        f"IMAGE CONTEXT:\n{image_context}\n\n"
        f"Apply the visual aesthetic above to transform the image."
    )

    return await client.chat(
        system_prompt=load_prompt("flux_transform"),
        user_content=[{"type": "text", "text": user_message}],
        max_tokens=500,
    )


async def transform(
    openai_client: OpenAIClient,
    flux_client: Flux2Client,
    aesthetic_cache: AestheticCache,
    image_path: Path,
    song_name: str,
    artist_name: str,
) -> bytes:
    """Write the edit prompt from the song's aesthetic and the photo's metadata, send the photo and prompt to the image model, and return the PNG bytes it produced."""
    if not await anyio.Path(image_path).exists():
        raise ServiceError(f"Image not found: {image_path}")

    flux_prompt = await _generate_flux_prompt(
        openai_client, aesthetic_cache, image_path, song_name, artist_name
    )
    image_bytes = await anyio.Path(image_path).read_bytes()
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    return await flux_client.generate_image(flux_prompt, image_b64)
