"""FastAPI server for local-shazam."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import uvicorn
from fastapi import FastAPI

from local_shazam.aesthetic_cache import AestheticCache
from local_shazam.api.routes import router as http_router
from local_shazam.config import Settings
from local_shazam.logger import get_logger, setup_root_logger
from local_shazam.process_images import ImageStore

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

log = get_logger(__name__)


def _validate_settings(settings: Settings) -> None:
    """Validate required settings at startup."""
    missing = []
    if not settings.bfl_api_key:
        missing.append("BFL_API_KEY")
    if not settings.openai_api_key:
        missing.append("OPENAI_API_KEY")
    if missing:
        raise RuntimeError(
            f"Missing required environment variables: {', '.join(missing)}"
        )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialize and cleanup application resources."""
    settings = Settings()
    setup_root_logger(level=settings.log_level)
    _validate_settings(settings)

    log.info("Initializing server...")
    app.state.settings = settings
    app.state.image_store = ImageStore(settings)
    app.state.aesthetic_cache = AestheticCache()
    log.info("Server initialized")

    yield

    log.info("Server shutting down")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="local-shazam",
        description="Image transformation server",
        lifespan=lifespan,
    )
    app.include_router(http_router)
    return app


def main() -> None:
    """Entry point for the server."""
    settings = Settings()
    setup_root_logger(level=settings.log_level)

    uvicorn.run(
        "local_shazam.server:create_app",
        factory=True,
        host=settings.server_host,
        port=settings.server_port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
