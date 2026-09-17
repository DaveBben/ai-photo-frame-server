"""HTTP server that edits a photo with Flux.2 Klein on the Mac mini, answering the OpenAI images format."""

from typing import Any

from fastapi import FastAPI


def create_app(model: Any) -> FastAPI:
    """Build the Flux server around a loaded image edit model."""
    raise NotImplementedError
