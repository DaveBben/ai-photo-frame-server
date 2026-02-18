"""BFL (Black Forest Labs) API client for Flux.2 image generation."""

import anyio
import httpx

from local_shazam.exceptions import ServiceError

_BASE_URL = "https://api.bfl.ai"
_POLL_INTERVAL_S = 0.5
_POLL_TIMEOUT_S = 120.0


class Flux2Client:
    """Async client for the BFL Flux.2 API."""

    def __init__(self, api_key: str, timeout: float = 30.0) -> None:
        self._api_key = api_key
        self._timeout = timeout

    async def generate_image(self, prompt: str, input_image_b64: str) -> bytes:
        """Submit an image edit job and return the result.

        Args:
            prompt: The Flux.2 edit prompt.
            input_image_b64: Base64-encoded input image.

        Returns:
            The generated image as bytes.

        Raises:
            ServiceError: If the API call fails.
        """
        headers = {"x-key": self._api_key}
        payload = {
            "prompt": prompt,
            "input_image": input_image_b64,
            "output_format": "png",
        }

        async with httpx.AsyncClient(
            base_url=_BASE_URL, timeout=self._timeout
        ) as client:
            response = await client.post(
                "/v1/flux-2-klein-9b",
                headers=headers,
                json=payload,
            )
            self._check_response(response)

            polling_url = response.json().get("polling_url")
            if not polling_url:
                raise ServiceError(f"No polling_url in BFL response: {response.json()}")

            image_url = await self._poll_for_result(client, polling_url)

            image_response = await client.get(image_url)
            image_response.raise_for_status()
            return image_response.content

    def _check_response(self, response: httpx.Response) -> None:
        """Check response status and raise appropriate errors."""
        if response.status_code == 402:
            raise ServiceError("Insufficient BFL credits")
        if response.status_code == 429:
            raise ServiceError("BFL rate limit exceeded")
        response.raise_for_status()

    async def _poll_for_result(
        self,
        client: httpx.AsyncClient,
        polling_url: str,
    ) -> str:
        """Poll until generation is ready and return the image URL."""
        start_time = anyio.current_time()
        while (anyio.current_time() - start_time) < _POLL_TIMEOUT_S:
            response = await client.get(polling_url)
            response.raise_for_status()
            data = response.json()

            status = data.get("status")
            if status == "Ready":
                sample_url = data.get("result", {}).get("sample")
                if not isinstance(sample_url, str):
                    raise ServiceError("Flux.2 returned Ready but no sample URL")
                return sample_url

            if status in ("Failed", "Error"):
                raise ServiceError(f"Flux.2 generation failed: {data}")

            await anyio.sleep(_POLL_INTERVAL_S)

        raise ServiceError(f"Flux.2 polling timed out after {_POLL_TIMEOUT_S}s")
