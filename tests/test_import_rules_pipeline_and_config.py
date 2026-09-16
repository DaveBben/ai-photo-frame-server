"""The import-linter rules for ADR items 2 and 5, which the client-import tests do not reach.

Rules: docs/adr/architecture/split-api-pipeline-and-clients.md, items 2 and 5.
"""

from pathlib import Path

import pytest
import test_import_rules


@pytest.mark.parametrize(
    ("module", "line"),
    [
        ("pipeline.py", "from local_shazam.api import routes\n"),  # item 2
        ("__init__.py", "from local_shazam.config import Settings\n"),  # item 5
    ],
)
def test_forbidden_import_fails_the_import_rules(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, module: str, line: str
) -> None:
    monkeypatch.setattr(test_import_rules, "CLIENT_IMPORT", line)
    assert test_import_rules._lint_copy(tmp_path, add_import_to=module) != 0
