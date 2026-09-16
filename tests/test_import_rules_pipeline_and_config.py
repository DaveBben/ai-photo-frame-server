"""The import-linter rules for ADR items 2 and 5, which the client-import tests do not reach.

Rules: docs/adr/architecture/split-api-pipeline-and-clients.md, items 2 and 5.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LINT_IMPORTS = Path(sys.executable).parent / "lint-imports"


@pytest.mark.parametrize(
    ("module", "line"),
    [
        ("pipeline.py", "from local_shazam.api import routes\n"),  # item 2
        ("__init__.py", "from local_shazam.config import Settings\n"),  # item 5
    ],
)
def test_forbidden_import_fails_the_import_rules(
    tmp_path: Path, module: str, line: str
) -> None:
    package = tmp_path / "src" / "local_shazam"
    shutil.copytree(
        ROOT / "src" / "local_shazam",
        package,
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    path = package / module
    path.write_text(line + path.read_text())
    result = subprocess.run(  # noqa: S603
        [str(LINT_IMPORTS), "--config", str(ROOT / "pyproject.toml"), "--no-cache"],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(tmp_path / "src")},
        capture_output=True,
        check=False,
    )
    assert result.returncode != 0
