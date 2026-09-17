"""Running scripts/deploy leaves the checkout at the newest commit on main, with that commit's dependencies installed.

Slice: Latest main on the Mac mini (docs/tasks/local-ai/task.md, item 0).
Acceptance: Given the running mac mini WHEN the deploy script is ran THEN the latest
changes from main (code and dependencies) are available on disk.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PYPROJECT = """[project]
name = "deploy-fixture"
version = "0.1.0"
requires-python = ">=3.13"
dependencies = {dependencies}
{sources}"""

TINYDEP_PYPROJECT = """[project]
name = "tinydep"
version = "1.0.0"
requires-python = ">=3.13"

[build-system]
requires = ["uv_build>=0.8,<0.13"]
build-backend = "uv_build"
"""


def _env() -> dict[str, str]:
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in {"VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT"}
    }
    env.update(
        UV_OFFLINE="1",
        UV_PYTHON=sys.executable,
        GIT_AUTHOR_NAME="test",
        GIT_AUTHOR_EMAIL="test@example.com",
        GIT_COMMITTER_NAME="test",
        GIT_COMMITTER_EMAIL="test@example.com",
    )
    return env


def _run(*args: str | Path, cwd: Path) -> str:
    result = subprocess.run(  # noqa: S603
        [str(a) for a in args],
        cwd=cwd,
        env=_env(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"{args} exited {result.returncode}\n{result.stdout}\n{result.stderr}"
    )
    return result.stdout.strip()


def _write_project(repo: Path, *, with_tinydep: bool) -> None:
    if with_tinydep:
        dependencies = '["tinydep"]'
        sources = '\n[tool.uv.sources]\ntinydep = { path = "tinydep" }\n'
    else:
        dependencies = "[]"
        sources = ""
    (repo / "pyproject.toml").write_text(
        PYPROJECT.format(dependencies=dependencies, sources=sources)
    )
    _run("uv", "lock", cwd=repo)


def test_deploy_brings_checkout_to_newest_main_with_its_dependencies(
    tmp_path: Path,
) -> None:
    # The repo on GitHub, reduced to a project with no dependencies and the deploy script.
    origin = tmp_path / "origin"
    (origin / "scripts").mkdir(parents=True)
    shutil.copy2(ROOT / "scripts" / "deploy", origin / "scripts" / "deploy")
    tinydep = origin / "tinydep"
    (tinydep / "src" / "tinydep").mkdir(parents=True)
    (tinydep / "pyproject.toml").write_text(TINYDEP_PYPROJECT)
    (tinydep / "src" / "tinydep" / "__init__.py").write_text("")
    _run("git", "init", "-q", "-b", "main", cwd=origin)
    _write_project(origin, with_tinydep=False)
    _run("git", "add", "-A", cwd=origin)
    _run("git", "commit", "-qm", "first", cwd=origin)

    # The Mac mini's checkout, cloned and synced at the first commit.
    mini = tmp_path / "mini"
    _run("git", "clone", "-q", origin, mini, cwd=tmp_path)
    _run("uv", "sync", "--locked", cwd=mini)

    # A merge to main that changes code and adds a dependency.
    (origin / "app.py").write_text("print('new code')\n")
    _write_project(origin, with_tinydep=True)
    _run("git", "add", "-A", cwd=origin)
    _run("git", "commit", "-qm", "second", cwd=origin)

    _run(mini / "scripts" / "deploy", cwd=tmp_path)

    assert _run("git", "rev-parse", "HEAD", cwd=mini) == _run(
        "git", "rev-parse", "main", cwd=origin
    )
    assert (mini / "app.py").read_text() == "print('new code')\n"
    _run("uv", "sync", "--locked", "--check", cwd=mini)
