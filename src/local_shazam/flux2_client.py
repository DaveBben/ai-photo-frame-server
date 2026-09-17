"""Client for the Flux server on the Mac mini, which answers the OpenAI images format."""

import base64

import openai
from openai import AsyncOpenAI

from local_shazam.exceptions import ServiceError


class Flux2Client:
    """Async client that sends photo edits to the Flux server's /images/edits."""

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url

    async def generate_image(self, prompt: str, input_image_b64: str) -> bytes:
        """Edit the photo with the prompt and return the PNG bytes.

        Raises:
            ServiceError: If the Flux server answers an error or cannot be reached.
        """
        # An edit takes 25-40s. A cold start after a restart loads weights first.
        # max_retries=0: a failed edit is reported, not re-run for another 40s.
        # One client per call closes its socket when the edit returns.
        try:
            async with AsyncOpenAI(
                base_url=self._base_url, api_key="unused", timeout=300.0, max_retries=0
            ) as client:
                result = await client.images.edit(
                    image=(
                        "photo.jpg",
                        base64.b64decode(input_image_b64),
                        "image/jpeg",
                    ),
                    prompt=prompt,
                )
        except openai.APIError as e:
            raise ServiceError(f"Flux server failed: {e}") from e
        return base64.b64decode(result.data[0].b64_json)  # type: ignore[arg-type,index]
