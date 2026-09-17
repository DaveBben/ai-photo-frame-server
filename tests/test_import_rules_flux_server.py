"""The import rule that keeps the Flux server and the API server's modules apart.

Slice: Flux server on the Mac mini (docs/tasks/local-ai/task.md, item 2), row 9.
Rule: docs/adr/local-ai/generate-restyled-images-on-the-mac-mini.md, item 5.
"""

from pathlib import Path

import pytest
import test_import_rules


@pytest.mark.parametrize(
    ("module", "line"),
    [
        ("flux_server.py", "from local_shazam import pipeline\n"),
        ("flux_server.py", "from local_shazam.api import routes\n"),
        ("flux_server.py", "from local_shazam import server\n"),
        ("api/routes.py", "from local_shazam import flux_server\n"),
        ("pipeline.py", "from local_shazam import flux_server\n"),
    ],
)
def test_import_across_flux_server_and_api_server_fails_the_import_rules(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, module: str, line: str
) -> None:
    monkeypatch.setattr(test_import_rules, "CLIENT_IMPORT", line)
    assert test_import_rules._lint_copy(tmp_path, add_import_to=module) != 0
