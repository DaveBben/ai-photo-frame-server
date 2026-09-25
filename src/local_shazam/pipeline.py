"""Orchestration for the aesthetic step (look up a song's aesthetic, cache first) and the transform step (caption the photo, write the edit prompt, then call the image model), all in memory."""

import base64
from io import BytesIO

from PIL import Image, ImageOps

from local_shazam.aesthetic_cache import AestheticCache
from local_shazam.flux2_client import Flux2Client
from local_shazam.itunes_client import ItunesClient
from local_shazam.openai_client import OpenAIClient
from local_shazam.prompts import load_prompt

# Pillow upper-cases the format name, so a case change here changes nothing.
_JPEG = "JPEG"  # pragma: no mutate


def _prepare_image_for_api(img: Image.Image) -> str:
    """Thumbnail an image to <=1024px and return base64-encoded JPEG."""
    img = img.copy()
    img.thumbnail((1024, 1024))
    buf = BytesIO()
    img.save(buf, format=_JPEG, quality=85)
    return base64.b64encode(buf.getvalue()).decode()


async def _describe_image(client: OpenAIClient, img: Image.Image) -> str:
    """Ask the vision model to describe the image."""
    b64_data = _prepare_image_for_api(img)
    return await client.describe_image(
        b64_data, load_prompt("describe_image"), max_tokens=800
    )


async def get_aesthetic(
    openai_client: OpenAIClient,
    itunes_client: ItunesClient,
    aesthetic_cache: AestheticCache,
    song_name: str,
    artist_name: str,
) -> str:
    """Return the song's cached aesthetic, or describe it from its iTunes catalog facts and album cover and cache the reply unless it contains "No visual data found"."""
    aesthetic = aesthetic_cache.get(artist_name, song_name)
    if aesthetic is None:
        found = await itunes_client.find_song(song_name, artist_name)
        facts, cover = found or ("No catalog data found.", None)
        aesthetic = await openai_client.describe_song(
            song_name, artist_name, facts, cover
        )
        if "No visual data found" not in aesthetic:
            aesthetic_cache.put(artist_name, song_name, aesthetic)
    return aesthetic


async def _generate_flux_prompt(
    client: OpenAIClient,
    itunes_client: ItunesClient,
    cache: AestheticCache,
    description: str,
    song_name: str,
    artist_name: str,
) -> str:
    """Ask the vision model for a Flux.2 edit prompt from the photo's caption and the song's aesthetic."""
    aesthetic = await get_aesthetic(
        openai_client=client,
        itunes_client=itunes_client,
        aesthetic_cache=cache,
        song_name=song_name,
        artist_name=artist_name,
    )

    user_message = (
        f"Transform this photo to match the vibe of '{song_name}' by {artist_name}.\n\n"
        f"VISUAL AESTHETIC:\n{aesthetic}\n\n"
        f"IMAGE CONTEXT:\nDescription: {description}\n\n"
        f"Apply the visual aesthetic above to transform the image."
    )

    return await client.chat(
        system_prompt=load_prompt("flux_transform"),
        user_content=[{"type": "text", "text": user_message}],
        max_tokens=500,
    )


async def transform(
    openai_client: OpenAIClient,
    itunes_client: ItunesClient,
    flux_client: Flux2Client,
    aesthetic_cache: AestheticCache,
    image: Image.Image,
    song_name: str,
    artist_name: str,
) -> bytes:
    """Caption the upright RGB photo, write the edit prompt from the caption and the song's aesthetic, send the photo and prompt to the image model, and return the PNG bytes it produced."""
    img = ImageOps.exif_transpose(image).convert("RGB")
    description = await _describe_image(openai_client, img)
    flux_prompt = await _generate_flux_prompt(
        openai_client,
        itunes_client,
        aesthetic_cache,
        description,
        song_name,
        artist_name,
    )
    buf = BytesIO()
    img.save(buf, format=_JPEG, quality=95)
    image_b64 = base64.b64encode(buf.getvalue()).decode()
    return await flux_client.generate_image(flux_prompt, image_b64)
