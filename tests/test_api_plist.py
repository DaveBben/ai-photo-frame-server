"""The Mac mini's LaunchDaemon keeps the API server running from the checkout, and install-mac-mini installs it.

Slice: the API server runs on the Mac mini (docs/tasks/local-ai/task.md, item D).
No CI machine runs launchd; the Mac mini itself is checked by
tests/macmini/test_api_server_on_mac_mini.py and by a restart.
"""

import plistlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LABEL = "com.local-shazam.api"


def test_api_server_starts_at_boot_and_restarts_when_it_exits() -> None:
    job = plistlib.loads((ROOT / "deploy" / f"{LABEL}.plist").read_bytes())

    assert job["Label"] == LABEL
    assert job["ProgramArguments"] == [
        "/Users/dave/ai-photo-frame-server/.venv/bin/local-shazam-server"
    ]
    assert job["UserName"] == "dave"
    assert job["RunAtLoad"] is True
    assert job["KeepAlive"] is True


def test_install_script_installs_the_api_server() -> None:
    script = (ROOT / "scripts" / "install-mac-mini").read_text()

    assert LABEL in script.split("for label in", 1)[1].split(";", 1)[0]
