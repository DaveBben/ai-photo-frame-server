"""Image store: save, list and load photos and their described copies, and read EXIF."""

from __future__ import annotations

import random
import uuid
from typing import TYPE_CHECKING

from PIL import Image, ImageOps
from PIL.ExifTags import GPS, IFD

from local_shazam.logger import get_logger

if TYPE_CHECKING:
    from pathlib import Path
    from uuid import UUID

log = get_logger(__name__)


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


def extract_image_metadata(image_path: Path) -> dict[str, str | None]:
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


class ImageStore:
    """Store and retrieve original photos and their described copies."""

    def __init__(self, data_dir: Path) -> None:
        """Create the original and analyzed directories under data_dir."""
        self._original_dir = data_dir / "original"
        self._analyzed_dir = data_dir / "analyzed"
        self._original_dir.mkdir(parents=True, exist_ok=True)
        self._analyzed_dir.mkdir(parents=True, exist_ok=True)

    def save_original(self, image_id: UUID, img: Image.Image) -> None:
        """Save the photo as <image_id>.jpg under original."""
        original_path = self._original_dir / f"{image_id}.jpg"
        img.save(original_path, format="JPEG", quality=95)
        log.info("Saved original: %s", original_path.name)

    def save_described(
        self, image_id: UUID, img: Image.Image, description: str
    ) -> None:
        """Save the photo as <image_id>.jpg under analyzed, with the description in EXIF tag 270."""
        analyzed_path = self._analyzed_dir / f"{image_id}.jpg"
        exif = Image.Exif()
        exif[270] = description  # ImageDescription tag
        img.save(analyzed_path, format="JPEG", quality=95, exif=exif.tobytes())
        log.info("Saved analyzed: %s", analyzed_path.name)

    def _list_images(self) -> list[UUID]:
        """List all analyzed image UUIDs.

        Returns:
            List of UUIDs for all analyzed images.
        """
        uuids = []
        for path in self._analyzed_dir.glob("*.jpg"):
            try:
                uuids.append(uuid.UUID(path.stem))
            except ValueError:
                continue
        return uuids

    def get_random_image(self) -> tuple[UUID, Image.Image] | None:
        """Get a random analyzed image.

        Returns:
            Tuple of (image_id, PIL Image), or None if no images exist.
        """
        images = self._list_images()
        if not images:
            return None
        # Not security-sensitive: random selection for user display, not crypto
        image_id = random.choice(images)  # noqa: S311

        analyzed_path = self._analyzed_dir / f"{image_id}.jpg"
        with Image.open(analyzed_path) as raw_img:
            transposed = ImageOps.exif_transpose(raw_img)
            img: Image.Image = transposed if transposed is not None else raw_img.copy()

        return image_id, img

    def get_image_path(self, image_id: UUID) -> Path:
        """Get path to analyzed image file.

        Args:
            image_id: UUID of the image.

        Returns:
            Path to the analyzed image file.

        Raises:
            FileNotFoundError: If image doesn't exist.
        """
        path = self._analyzed_dir / f"{image_id}.jpg"
        if not path.exists():
            raise FileNotFoundError(f"Image not found: {image_id}")
        return path
