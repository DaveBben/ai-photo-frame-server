"""The Mac mini's boot LaunchDaemon reruns scripts/deploy until it succeeds, so a boot with no network yet still reaches newest main.

Slice: Boot deploy waits for the network (docs/tasks/local-ai/task.md, bug card).
Acceptance: Given a reboot of the mac WHEN the deploy scripts starts then it should be
able to reach the newest commit on main by itself.

No CI machine can restart a Mac, so this test reads the property list launchd loads.
The restart itself is checked by hand in ~/Library/Logs/local-shazam-deploy.log.
"""

import plistlib
from pathlib import Path

PLIST = Path(__file__).resolve().parents[1] / "deploy" / "com.local-shazam.deploy.plist"


def test_boot_deploy_is_rerun_after_a_failed_exit_until_it_succeeds() -> None:
    job = plistlib.loads(PLIST.read_bytes())

    assert job["RunAtLoad"] is True
    # launchd reruns the job after a non-zero exit and leaves it stopped after exit 0.
    assert job.get("KeepAlive") == {"SuccessfulExit": False}
    throttle = job.get("ThrottleInterval")
    assert isinstance(throttle, int)
    assert throttle > 0
