"""The import-linter rules in pyproject.toml reject a model client imported outside the pipeline.

Slice: Upload a photo (docs/tasks/restructure-layers/task.md).
Rules: docs/adr/architecture/split-api-pipeline-and-clients.md, items 1, 2, 4 and 5.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LINT_IMPORTS = Path(sys.executable).parent / "lint-imports"
CLIENT_IMPORT = "from local_shazam.openai_client import OpenAIClient\n"


def _lint_copy(tmp_path: Path, add_import_to: str | None = None) -> int:
    """Run lint-imports on a copy of the package, optionally adding a client import to one module."""
    package = tmp_path / "src" / "local_shazam"
    shutil.copytree(
        ROOT / "src" / "local_shazam",
        package,
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    if add_import_to:
        module = package / add_import_to
        module.write_text(CLIENT_IMPORT + module.read_text())
    result = subprocess.run(  # noqa: S603
        [str(LINT_IMPORTS), "--config", str(ROOT / "pyproject.toml"), "--no-cache"],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(tmp_path / "src")},
        capture_output=True,
        check=False,
    )
    return result.returncode


def test_current_code_passes_the_import_rules(tmp_path: Path) -> None:
    assert _lint_copy(tmp_path) == 0


@pytest.mark.parametrize("module", ["api/routes.py", "aesthetic_cache.py"])
def test_client_import_outside_pipeline_fails_the_import_rules(
    tmp_path: Path, module: str
) -> None:
    assert _lint_copy(tmp_path, add_import_to=module) != 0
