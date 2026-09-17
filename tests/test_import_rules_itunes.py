"""The iTunes lookup sits with the model clients and stores: api cannot import it, and it imports no other client.

Slice: captions, song looks and edit prompts from the local vision model
(docs/tasks/local-ai/task.md, item B).
Rules: docs/adr/architecture/split-api-pipeline-and-clients.md, items 1 and 4.
"""

from pathlib import Path

import pytest
import test_import_rules


@pytest.mark.parametrize(
    ("module", "line"),
    [
        ("api/routes.py", "from local_shazam import itunes_client\n"),  # item 1
        ("itunes_client.py", "from local_shazam import openai_client\n"),  # item 4
        ("itunes_client.py", "from local_shazam import pipeline\n"),  # item 4
    ],
)
def test_itunes_client_import_outside_its_layer_fails_the_import_rules(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, module: str, line: str
) -> None:
    monkeypatch.setattr(test_import_rules, "CLIENT_IMPORT", line)
    assert test_import_rules._lint_copy(tmp_path, add_import_to=module) != 0
