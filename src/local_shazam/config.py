"""Application configuration via environment variables."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Attributes:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        flux_base_url: Base URL of the Flux server's OpenAI images API.
        vlm_base_url: Base URL of the vision model server's OpenAI chat API.
        server_host: Host address to bind the server to.
        server_port: Port number for the HTTP server.
        data_dir: Directory holding stored images and the aesthetic cache.
    """

    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", env_file_encoding="utf-8"
    )

    log_level: str = "INFO"
    flux_base_url: str = "http://127.0.0.1:8081/v1"
    vlm_base_url: str = "http://127.0.0.1:8080/v1"

    # Server settings
    server_host: str = "0.0.0.0"  # noqa: S104
    server_port: int = 8000

    data_dir: Path = Path(__file__).resolve().parents[2] / "data"
