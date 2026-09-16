"""Orchestration for the upload, aesthetic and transform steps."""

from pathlib import Path

from local_shazam.aesthetic_cache import AestheticCache
from local_shazam.flux2_client import Flux2Client
from local_shazam.openai_client import OpenAIClient
from local_shazam.process_images import extract_image_metadata
from local_shazam.prompts import load_prompt


async def _generate_flux_prompt(
    client: OpenAIClient,
    cache: AestheticCache,
    image_path: Path,
    song_name: str,
    artist_name: str,
) -> str:
    """Use GPT-4o with image metadata and cached aesthetics to generate a Flux.2 prompt."""
    # Check cache first, search web on miss
    aesthetic = cache.get(artist_name, song_name)
    if aesthetic is None:
        aesthetic = await client.search_aesthetic(artist_name, song_name)
        if "No visual data found" not in aesthetic:
            cache.put(artist_name, song_name, aesthetic)

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
    raise NotImplementedError
