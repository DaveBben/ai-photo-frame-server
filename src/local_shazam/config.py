"""Application configuration via environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Attributes:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        bfl_api_key: Black Forest Labs API key for Flux.2 image generation.
        openai_api_key: OpenAI API key for GPT-4o vision and chat.
        server_host: Host address to bind the server to.
        server_port: Port number for the HTTP server.
    """

    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", env_file_encoding="utf-8"
    )

    log_level: str = "INFO"
    bfl_api_key: str = ""
    openai_api_key: str = ""

    # Server settings
    server_host: str = "0.0.0.0"  # noqa: S104
    server_port: int = 8000
