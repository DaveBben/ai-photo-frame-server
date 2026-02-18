"""Image store: save images with GPT-4o descriptions."""

from __future__ import annotations

import base64
import random
import uuid
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image, ImageOps
from PIL.Image import Resampling

from local_shazam.logger import get_logger
from local_shazam.openai_client import OpenAIClient
from local_shazam.prompts import load_prompt

if TYPE_CHECKING:
    from uuid import UUID

    from local_shazam.config import Settings

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXTENSIONS = {".jpg", ".jpeg", ".png"}

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


class ImageStore:
    """Store and retrieve images with GPT-4o descriptions."""

    def __init__(self, settings: Settings, data_dir: Path | None = None) -> None:
        """Initialize the image store.

        Args:
            settings: Application settings.
            data_dir: Root data directory. Defaults to PROJECT_ROOT/data/img.
        """
        base_dir = data_dir or (PROJECT_ROOT / "data" / "img")
        self._original_dir = base_dir / "original"
        self._analyzed_dir = base_dir / "analyzed"
        self._original_dir.mkdir(parents=True, exist_ok=True)
        self._analyzed_dir.mkdir(parents=True, exist_ok=True)
        self._client = OpenAIClient(settings.openai_api_key)

    async def put_image(self, image: Image.Image) -> UUID:
        """Store an image, analyze it with GPT-4o, and save with description.

        Args:
            image: PIL Image to store.

        Returns:
            UUID identifying the stored image.
        """
        image_id = uuid.uuid4()

        # Normalize image
        img = ImageOps.exif_transpose(image)
        if img is None:
            img = image
        if img.mode != "RGB":
            img = img.convert("RGB")

        # Save original
        original_path = self._original_dir / f"{image_id}.jpg"
        img.save(original_path, format="JPEG", quality=95)
        log.info("Saved original: %s", original_path.name)

        # Get description from GPT
        description = await _describe_image(self._client, img)
        log.info("Got description (%d chars)", len(description))

        # Save analyzed with description in EXIF
        analyzed_path = self._analyzed_dir / f"{image_id}.jpg"
        exif = Image.Exif()
        exif[270] = description  # ImageDescription tag
        img.save(analyzed_path, format="JPEG", quality=95, exif=exif.tobytes())
        log.info("Saved analyzed: %s", analyzed_path.name)

        return image_id

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
