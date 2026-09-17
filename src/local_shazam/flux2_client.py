"""Client for the Flux server on the Mac mini, which answers the OpenAI images format."""

import base64

import openai
from openai import AsyncOpenAI

from local_shazam.exceptions import ServiceError

# An edit takes 25-40s. A cold start after a restart loads weights first.
_TIMEOUT_S = 300.0
# The Flux server reads neither the key nor the upload's name and type, but the
# openai package requires a key; changing these strings changes nothing.
_API_KEY = "unused"  # pragma: no mutate
_UPLOAD_NAME, _UPLOAD_TYPE = "photo.jpg", "image/jpeg"  # pragma: no mutate


class Flux2Client:
    """Async client that sends photo edits to the Flux server's /images/edits."""

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url

    async def generate_image(self, prompt: str, input_image_b64: str) -> bytes:
        """Edit the photo with the prompt and return the PNG bytes.

        Raises:
            ServiceError: If the Flux server answers an error or cannot be reached.
        """
        # max_retries=0: a failed edit is reported, not re-run for another 40s.
        # One client per call closes its socket when the edit returns.
        try:
            async with AsyncOpenAI(
                base_url=self._base_url,
                api_key=_API_KEY,
                timeout=_TIMEOUT_S,
                max_retries=0,
            ) as client:
                result = await client.images.edit(
                    image=(
                        _UPLOAD_NAME,
                        base64.b64decode(input_image_b64),
                        _UPLOAD_TYPE,
                    ),
                    prompt=prompt,
                )
        except openai.APIError as e:
            raise ServiceError(f"Flux server failed: {e}") from e
        return base64.b64decode(result.data[0].b64_json)  # type: ignore[arg-type,index]
