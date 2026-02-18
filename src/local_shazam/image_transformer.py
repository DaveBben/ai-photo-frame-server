"""Image transformation using GPT-4o analysis + Flux.2 Klein 9B editing."""

import base64
from pathlib import Path

import anyio
from PIL import Image
from PIL.ExifTags import GPS, IFD

from local_shazam.aesthetic_cache import AestheticCache
from local_shazam.config import Settings
from local_shazam.exceptions import ServiceError
from local_shazam.flux2_client import Flux2Client
from local_shazam.openai_client import OpenAIClient
from local_shazam.prompts import load_prompt


def _convert_gps_to_decimal(
    coords: tuple[float, float, float],
    ref: str,
) -> float:
    """Convert GPS coordinates from degrees/minutes/seconds to decimal degrees."""
    degrees, minutes, seconds = coords
    decimal = degrees + minutes / 60.0 + seconds / 3600.0
    if ref in ("S", "W"):
        decimal = -decimal
    return decimal


def _extract_image_metadata(image_path: Path) -> dict[str, str | None]:
    """Extract EXIF metadata from an image file.

    Args:
        image_path: Path to the image file.

    Returns:
        Dictionary containing extracted metadata fields.
    """
    metadata: dict[str, str | None] = {
        "description": None,
        "datetime": None,
        "camera_make": None,
        "camera_model": None,
        "gps_coords": None,
    }

    with Image.open(image_path) as img:
        exif = img.getexif()
        if not exif:
            return metadata

        # ImageDescription (tag 270)
        metadata["description"] = exif.get(270)

        # DateTime (tag 306) or DateTimeOriginal (tag 36867 in EXIF IFD)
        metadata["datetime"] = exif.get(306)
        if not metadata["datetime"]:
            exif_ifd = exif.get_ifd(IFD.Exif)
            if exif_ifd:
                metadata["datetime"] = exif_ifd.get(36867)

        # Camera Make (tag 271) and Model (tag 272)
        metadata["camera_make"] = exif.get(271)
        metadata["camera_model"] = exif.get(272)

        # GPS coordinates
        gps_ifd = exif.get_ifd(IFD.GPSInfo)
        if gps_ifd:
            lat = gps_ifd.get(GPS.GPSLatitude)
            lat_ref = gps_ifd.get(GPS.GPSLatitudeRef)
            lon = gps_ifd.get(GPS.GPSLongitude)
            lon_ref = gps_ifd.get(GPS.GPSLongitudeRef)

            if lat and lat_ref and lon and lon_ref:
                lat_decimal = _convert_gps_to_decimal(lat, lat_ref)
                lon_decimal = _convert_gps_to_decimal(lon, lon_ref)
                metadata["gps_coords"] = f"{lat_decimal:.6f}, {lon_decimal:.6f}"

    return metadata


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

    metadata = _extract_image_metadata(image_path)

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


async def transform_image(
    image_path: Path,
    song_name: str,
    artist_name: str,
    settings: Settings | None = None,
    aesthetic_cache: AestheticCache | None = None,
) -> bytes:
    """Transform an image to match a song's vibe using GPT-4o + Flux.2.

    Three-stage pipeline:
    1. Lookup/fetch visual aesthetic for the song (cached in SQLite)
    2. GPT-4o generates a Flux.2 prompt using aesthetic + image context
    3. Flux.2 Klein 9B executes the image transformation

    Args:
        image_path: Path to the input image file.
        song_name: Name of the identified song.
        artist_name: Name of the artist.
        settings: Optional settings instance. Created if not provided.
        aesthetic_cache: Optional cache instance. Created if not provided.

    Returns:
        The transformed image as PNG bytes.

    Raises:
        ServiceError: If the transformation fails.
    """
    if not await anyio.Path(image_path).exists():
        raise ServiceError(f"Image not found: {image_path}")

    if settings is None:
        settings = Settings()

    if aesthetic_cache is None:
        aesthetic_cache = AestheticCache()

    if not settings.bfl_api_key:
        raise ServiceError("BFL_API_KEY not configured")
    if not settings.openai_api_key:
        raise ServiceError("OPENAI_API_KEY not configured")

    openai_client = OpenAIClient(settings.openai_api_key)
    flux_prompt = await _generate_flux_prompt(
        openai_client, aesthetic_cache, image_path, song_name, artist_name
    )

    image_bytes = await anyio.Path(image_path).read_bytes()
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")

    flux_client = Flux2Client(settings.bfl_api_key)
    return await flux_client.generate_image(flux_prompt, image_b64)
