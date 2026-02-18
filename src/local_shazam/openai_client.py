"""OpenAI API client for GPT-4o vision and chat completions."""

from typing import TYPE_CHECKING, Any

from openai import AsyncOpenAI

from local_shazam.exceptions import ServiceError
from local_shazam.logger import get_logger
from local_shazam.prompts import load_prompt

if TYPE_CHECKING:
    from openai.types.chat import ChatCompletionMessageParam

log = get_logger(__name__)

type ContentBlock = dict[str, Any]


class OpenAIClient:
    """Async client for OpenAI GPT-4o vision and chat APIs."""

    def __init__(self, api_key: str, timeout: float = 60.0) -> None:
        self._client = AsyncOpenAI(api_key=api_key, timeout=timeout)

    async def describe_image(
        self,
        image_b64: str,
        prompt: str,
        *,
        max_tokens: int = 800,
        mime_type: str = "image/jpeg",
    ) -> str:
        """Describe an image using GPT-4o vision.

        Args:
            image_b64: Base64-encoded image data.
            prompt: System prompt describing desired output format.
            max_tokens: Maximum tokens in response.
            mime_type: MIME type of the image.

        Returns:
            The model's text response.

        Raises:
            ServiceError: If the API call fails or returns empty content.
        """
        image_url = f"data:{mime_type};base64,{image_b64}"

        messages: list[ChatCompletionMessageParam] = [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": image_url}},
                    {"type": "text", "text": prompt},
                ],
            },
        ]
        log.info(
            "describe_image request: prompt=%r, image_size=%d, mime_type=%s",
            prompt[:100],
            len(image_b64),
            mime_type,
        )

        response = await self._client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            max_tokens=max_tokens,
        )

        content = response.choices[0].message.content
        if not content:
            raise ServiceError("GPT-4o returned empty response")

        result = content.strip()
        log.info(
            "describe_image response: %r", result[:400] if len(result) > 400 else result
        )
        return result

    async def chat(
        self,
        system_prompt: str,
        user_content: list[ContentBlock],
        *,
        max_tokens: int = 200,
    ) -> str:
        """Send a chat completion request with system and user messages.

        Args:
            system_prompt: System message setting context/behavior.
            user_content: User message content blocks (text and/or image_url).
            max_tokens: Maximum tokens in response.

        Returns:
            The model's text response.

        Raises:
            ServiceError: If the API call fails or returns empty content.
        """
        log.debug(
            "chat request: system_prompt=%r, user_content=%r",
            system_prompt[:100],
            user_content,
        )

        response = await self._client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},  # type: ignore[list-item, misc]
            ],
            max_tokens=max_tokens,
        )

        content = response.choices[0].message.content
        if not content:
            raise ServiceError("GPT-4o returned empty response")

        result = content.strip()
        log.info("chat response: %r", result[:1000] if len(result) > 1000 else result)
        return result

    async def search_aesthetic(self, artist: str, song: str) -> str:
        """Search web for song/artist visual aesthetic.

        Uses gpt-4o-search-preview which ALWAYS performs a web search.
        Returns ~150 word description of colors, mood, album art, visual style.

        Args:
            artist: Artist name.
            song: Song title.

        Returns:
            Aesthetic description with visual details, colors, mood.

        Raises:
            ServiceError: If the API call fails or returns empty content.
        """
        log.info("search_aesthetic request: '%s' by %s", song, artist)

        system_prompt = load_prompt("search_aesthetic")

        user_message = f'Song: "{song}"\nArtist: {artist}'

        response = await self._client.chat.completions.create(
            model="gpt-4o-search-preview",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            max_tokens=1000,
        )

        content = response.choices[0].message.content
        if not content:
            raise ServiceError("gpt-4o-search-preview returned empty response")

        result = content.strip()
        log.info(
            "search_aesthetic response: %r",
            result[:400] if len(result) > 400 else result,
        )
        return result
