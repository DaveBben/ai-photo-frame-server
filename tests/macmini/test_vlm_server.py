"""The vision model server on the Mac mini answers an image with a description of it.

Slice: Vision model server on the Mac mini (docs/tasks/local-ai/task.md, item 1).
Acceptance: Given a running Mac Mini when I sent a HTTP request to its VLM server with
an image then I receive a text description of the image back.

Runs against the real Mac mini, so it is excluded from ./check and CI:
    uv run pytest -m macmini
VLM_URL overrides the server address.
"""

import base64
import os
from io import BytesIO

import httpx
import pytest
from PIL import Image

pytestmark = pytest.mark.macmini

VLM_URL = os.environ.get("VLM_URL", "http://davids-mac-mini.local:8080")
MODEL = "mlx-community/Qwen3-VL-4B-Instruct-4bit"


def test_vlm_server_describes_a_red_image() -> None:
    buf = BytesIO()
    Image.new("RGB", (256, 256), (220, 20, 20)).save(buf, format="JPEG")
    image_url = "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()

    response = httpx.post(
        f"{VLM_URL}/v1/chat/completions",
        json={
            "model": MODEL,
            "max_tokens": 60,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": image_url}},
                        {
                            "type": "text",
                            "text": "Describe this image in one sentence.",
                        },
                    ],
                }
            ],
        },
        timeout=120,
    )

    assert response.status_code == 200, response.text
    description = response.json()["choices"][0]["message"]["content"]
    assert "red" in description.lower()
