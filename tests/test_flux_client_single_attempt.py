"""A failed Flux edit is reported after one request, without re-sending a 25-40s edit.

Slice: Restyle a photo with the image made by the local Flux server
(docs/tasks/local-ai/task.md, item A).
"""

import base64

import pytest
import respx

from local_shazam.exceptions import ServiceError
from local_shazam.flux2_client import Flux2Client


async def test_flux_server_error_is_not_retried() -> None:
    with respx.mock() as mock:
        edit = mock.post("http://flux.test/v1/images/edits").respond(500)

        with pytest.raises(ServiceError):
            await Flux2Client("http://flux.test/v1").generate_image(
                "prompt", base64.b64encode(b"jpeg").decode()
            )

    assert edit.call_count == 1
