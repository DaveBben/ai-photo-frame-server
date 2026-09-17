# local-ai

## Plan
Outcome:   When a song plays, the frame shows my photo restyled for that song within 60 seconds, no request goes to OpenAI or Black Forest Labs, and I pay no API bill.
Problem:   The frame's owner pays OpenAI for every photo upload, new song lookup and edit prompt, and Black Forest Labs for every restyled image. SPIKE_FINDINGS.md shows the same pipeline running on the Mac mini in 38.5s once a song's aesthetic is cached.
Not doing: No change to any route's request or response in openapi.yaml; the Pi client keeps its synchronous HTTP call.
           No queue or lock for two restyle requests arriving at once.
Decided:   REST over FastAPI, one API server process: src/local_shazam/api/routes.py, openapi.yaml.
           Storage stays as image files plus the SQLite aesthetic cache: image_store.py, aesthetic_cache.py.
           Model calls go only through pipeline.py, and no interface class sits in front of a client: docs/adr/architecture/split-api-pipeline-and-clients.md.
           Python 3.13 for the API server: pyproject.toml.
           Flux runs on the Mac mini in its own process on 0.0.0.0:8081, answering the OpenAI images format, with its code in this repo; the API server moves from ai-server to the Mac mini; every process there starts from a LaunchDaemon: docs/adr/local-ai/generate-restyled-images-on-the-mac-mini.md.
Deferred:  none yet.
Pins:      scripts/deploy fast-forwards main and syncs dependencies: tests/test_deploy.py.
           Boot deploy reruns until it succeeds: tests/test_deploy_plist.py.
           Vision model server answers with a description: tests/macmini/test_vlm_server.py (run with -m macmini).
           Flux server contract, size, reference shrink, steps, lock, warm-up: tests/test_flux_server.py; import rules: tests/test_import_rules_flux_server.py; on the Mac mini: tests/macmini/test_flux_server.py.
Slices:    3. Restyle a photo with the image made by the local Flux server, served by the API server on the Mac mini, which restarts after a reboot; the frame's client points at the Mac mini.
           4. Look up a new song's look from its album cover.
           5. Restyle a photo with the edit prompt written by the local vision model.
           6. Upload a photo and have the local vision model describe it.
           7. Start the server with no OpenAI or Black Forest Labs key set.

## 2026-09-16 — Latest main on the Mac mini
- Done: scripts/deploy fast-forwards the checkout to origin main and runs uv sync --locked; a LaunchDaemon (deploy/com.local-shazam.deploy.plist) runs it as dave at every boot, installed by scripts/install-mac-mini.
- Observed: not yet. Signal: after a restart of the Mac mini, `ssh mini git -C ~/ai-photo-frame-server log -1` shows main's newest commit and ~/Library/Logs/local-shazam-deploy.log has a "deployed" line from that boot.
- Observed: seen 2026-09-16, and the boot deploy failed. The install run logged "deployed 881de91"; after the restart the LaunchDaemon's run logged "Could not resolve host: github.com" and exited, so the checkout was current only because of the install run.
- Accepted: 5abae03
- Learned: **FileVault on the Mac mini keeps the disk locked after a restart until someone types a password, so no LaunchDaemon can start before that**; the user turned FileVault off. docs/adr/local-ai/generate-restyled-images-on-the-mac-mini.md, item 9.
- Learned: **a non-interactive `ssh mini <command>` and launchd both run without ~/.local/bin on PATH, where uv is installed**, so scripts/deploy adds it itself. Not pinned: the test runs uv from the test machine's PATH.
- Learned: **`git commit -a` exports GIT_INDEX_FILE to its hooks, and tests/test_deploy.py passed that to the git commands it runs in its fixture repos**, so under the hook they used the outer repo's temporary index, the new file never reached the fixture clone, and the commit-hash assertion compared the outer repo with itself. The test now drops every GIT_ variable; pinned by the commit hook itself, which runs the test under `git commit -a`.
- Decided: the deploy only fast-forwards, so local commits on the Mac mini or a force-pushed main make it fail without changing the checkout. Tradeoff: those cases need a hand fix.
- Decided: nothing retries when the network is not up at boot; the failed fetch is logged and the previous checkout stays. Tradeoff: that boot deploys nothing until the next restart or a manual deploy.
- Decided: the LaunchDaemon hardcodes /Users/dave/ai-photo-frame-server. Tradeoff: the checkout must live at that path.
- Not caught by: the red run and the one pass with a working script both ran outside a git hook, where GIT_INDEX_FILE is unset. Found by the log commit's hook; the user re-accepted the test with GIT_ variables dropped.

## 2026-09-16 — Boot deploy waits for the network
- Done: deploy/com.local-shazam.deploy.plist sets KeepAlive with SuccessfulExit false and ThrottleInterval 30, so launchd reruns scripts/deploy every 30s after a failed exit and stops after the first success.
- Observed: not yet. Signal: after `scripts/install-mac-mini` is rerun and the Mac mini restarts, ~/Library/Logs/local-shazam-deploy.log shows any "Could not resolve host" lines followed by a "deployed" line from that boot.
- Observed: seen 2026-09-16. After reinstall and a restart, the log showed "Could not resolve host: github.com" and then "deployed 926cb59"; `launchctl print system/com.local-shazam.deploy` showed runs = 2, last exit code = 0.
- Accepted: 8a3fc01
- Decided: a deploy that fails for a lasting reason, such as local commits blocking the fast-forward, retries every 30s until fixed. Tradeoff: one git fetch and a few log lines every 30s while it is broken.
- Decided: ThrottleInterval is 30s. Tradeoff: a boot waits up to 30s past the network coming up before deploying.
- Not caught by: the proposal for the first deploy listed "the network is up when the LaunchDaemon runs at boot" as an assumption to check by restart, and nothing automated can restart a Mac. The restart found it. tests/test_deploy_plist.py now asserts the retry keys; the boot behaviour itself stays a manual check.

## 2026-09-16 — Vision model server on the Mac mini
- Done: mlx-vlm is a macOS-only dependency; deploy/com.local-shazam.vlm.plist keeps mlx_vlm.server with Qwen3-VL-4B-Instruct-4bit on 0.0.0.0:8080 at boot and after any exit; scripts/install-mac-mini installs both LaunchDaemons.
- Observed: not yet. Signal: after deploy, reinstall and a restart of the Mac mini, `uv run pytest -m macmini` passes from the laptop.
- Observed: seen 2026-09-16. After install the macmini test passed in 2.9s; after a restart the server's process was 50s old at 56s uptime (launchd runs = 1, never exited), the deploy log showed "deployed 385759f", and the test passed in 1.5s. 6.2GB free with the model loaded.
- Accepted: 418c82c
- Learned: **the spike's mlx_vlm.server ran under nohup and was gone after the Mac mini's first restart**, and the 608MB free before that restart became 11GB free after it. What used the memory is not established; `top -o mem` before the next unexplained drop would show it.
- Decided: the server can start before the boot deploy's uv sync finishes; if mlx-vlm is missing it exits and launchd restarts it about 10s later. Tradeoff: a few failed starts in the log on the first boot after a dependency change.
- Decided: model downloads are not blocked, so a model missing from the Hugging Face cache downloads at startup. Tradeoff: a changed model id needs network at boot.
- Decided: mlx-vlm locked at 0.7.1 where the spike ran 0.7.0. Tradeoff: the macmini test is the first run on 0.7.1.

## 2026-09-16 — Flux server on the Mac mini
- Done: local-shazam-flux serves POST /v1/images/edits in the OpenAI images format on 0.0.0.0:8081, shrinking the photo to 512px, generating at 3 steps behind one lock, after one warm-up generation at startup; deploy/com.local-shazam.flux.plist keeps it running; scripts/install-mac-mini installs three LaunchDaemons.
- By hand: none: the user asked the agent to write it and skipped the merge description.
- Observed: not yet. Signal: after deploy, reinstall and a restart of the Mac mini, `uv run pytest -m macmini` passes, including the second edit under 46.6s, and `top -l 1 | grep PhysMem` on the Mac mini shows free memory with both models loaded.
- Accepted: 1e68ba9
- Learned: **the edit guard refuses every file the red commit changed, and the red commit included a stub in src/**, so the build agent could not replace the stub and the user had to clear agile.redCommit before the build could land. Red commits now hold test files only; stubs go in a separate commit.
- Learned: **tests/test_flux_server.py and tests/macmini/test_flux_server.py shared a basename with no __init__.py in either directory**, so pytest imported both as module test_flux_server and every run stopped at collection. tests/macmini/__init__.py makes the second one macmini.test_flux_server. Caught by the turn-end hook.
- Learned: **mflux 0.19.1 asks for mlx[cuda13]<0.32 on Linux while mlx-vlm needs mlx>=0.32.2, and uv's universal lock rejects the pair even though both are macOS-only here**. The [tool.uv] override pins mlx>=0.32.2,<0.33 on macOS; an mflux or mlx-vlm needing mlx 0.33 fails to lock until it is edited.
- Decided: two import-linter contracts, one per direction, because one forbidden contract listing api and pipeline on both sides would also forbid api importing pipeline. Tradeoff: two rules to keep in step.
- Decided: the seed is random per request (secrets.randbelow). Tradeoff: the same photo and song give a different image each time; the user said either is fine.
- Decided: the reference is converted to RGB and saved as PNG in a temporary directory, so a CMYK JPEG does not fail. Tradeoff: no test covers CMYK or truncated uploads.
- Decided: size parsing accepts "0x480" or "-5x3" and passes them to mflux. Tradeoff: those get whatever error mflux raises instead of a 400.
- Decided: mypy ignores missing imports for mflux.*, because mflux ships no type information and does not install on Linux. Tradeoff: calls into mflux are untyped.
