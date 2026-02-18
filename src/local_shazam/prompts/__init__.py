"""Prompt loading utilities."""

from functools import cache

__all__ = ["load_prompt"]
from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent


@cache
def load_prompt(name: str) -> str:
    """Load a prompt from the prompts directory.

    Args:
        name: Prompt filename without extension (e.g., "describe_image").

    Returns:
        The prompt text content.

    Raises:
        FileNotFoundError: If the prompt file doesn't exist.
    """
    prompt_path = _PROMPTS_DIR / f"{name}.txt"
    return prompt_path.read_text().strip()
