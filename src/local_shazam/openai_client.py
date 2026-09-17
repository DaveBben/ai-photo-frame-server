"""Client for the vision model server on the Mac mini, which answers the OpenAI chat completions format."""

import base64
from typing import Any

import openai
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam

from local_shazam.exceptions import ServiceError
from local_shazam.prompts import load_prompt

type ContentBlock = dict[str, Any]

_MODEL = "mlx-community/Qwen3-VL-4B-Instruct-4bit"
# The spike measured 13-29s per request with the Mac mini otherwise idle; a Flux
# edit running on the same GPU slows it further.
_TIMEOUT_S = 120.0
# The vision model server does not read the key, but the openai package requires one.
_API_KEY = "unused"  # pragma: no mutate


class OpenAIClient:
    """Async client for the vision model server's /chat/completions."""

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url

    async def _complete(
        self, messages: list[ChatCompletionMessageParam], max_tokens: int
    ) -> str:
        # max_retries=0: a failed 30s request is reported, not re-sent.
        # One client per call closes its socket when the reply returns.
        try:
            async with AsyncOpenAI(
                base_url=self._base_url,
                api_key=_API_KEY,
                timeout=_TIMEOUT_S,
                max_retries=0,
            ) as client:
                response = await client.chat.completions.create(
                    model=_MODEL, messages=messages, max_tokens=max_tokens
                )
        except openai.APIError as e:
            raise ServiceError(f"Vision model failed: {e}") from e
        content = response.choices[0].message.content
        if not content:
            raise ServiceError("Vision model returned an empty response")
        return content.strip()

    async def describe_image(
        self, image_b64: str, prompt: str, *, max_tokens: int
    ) -> str:
        """Describe a base64 JPEG with the prompt.

        Raises:
            ServiceError: If the server fails, cannot be reached, or returns empty content.
        """
        return await self._complete(
            [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"},
                        },
                        {"type": "text", "text": prompt},
                    ],
                },
            ],
            max_tokens,
        )

    async def chat(
        self, system_prompt: str, user_content: list[ContentBlock], *, max_tokens: int
    ) -> str:
        """Send a system message and user content blocks, and return the reply.

        Raises:
            ServiceError: If the server fails, cannot be reached, or returns empty content.
        """
        return await self._complete(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},  # type: ignore[list-item, misc]
            ],
            max_tokens,
        )

    async def describe_song(
        self, song: str, artist: str, facts: str, cover: bytes | None
    ) -> str:
        """Describe the song's look from its catalog facts and album cover JPEG.

        Raises:
            ServiceError: If the server fails, cannot be reached, or returns empty content.
        """
        text = (
            f'Song: "{song}"\nArtist: {artist}\n\nCATALOG DATA:\n{facts}\n\n'
            f"The attached image is this release's official album cover. Read its actual "
            f"colors, textures and lighting and treat them as primary evidence for the "
            f"Sacred Elements section. Combine with what you know about the artist."
        )
        content: list[ContentBlock] = [{"type": "text", "text": text}]
        if cover:
            url = f"data:image/jpeg;base64,{base64.b64encode(cover).decode()}"
            content.insert(0, {"type": "image_url", "image_url": {"url": url}})
        return await self.chat(
            load_prompt("search_aesthetic"), content, max_tokens=1000
        )
