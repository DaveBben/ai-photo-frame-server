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
           API server gets restyled images from FLUX_BASE_URL (default 127.0.0.1:8081), 502 on Flux failure, no retries, no BFL key: tests/test_transform_route.py, tests/test_local_flux_config.py, tests/test_flux_client_single_attempt.py; on the Mac mini: tests/macmini/test_flux_client.py.
           Captions, song looks (iTunes cover) and edit prompts from VLM_BASE_URL, 502 on vision model failure, no retries, no keys: tests/test_upload_route.py, test_aesthetic_route.py, test_transform_route.py, test_local_vlm_config.py, test_vlm_requests.py, test_itunes_incomplete_answer.py, test_pipeline_gaps.py; on the Mac mini: tests/macmini/test_restyle_on_mac_mini.py.
           API server LaunchDaemon and install: tests/test_api_plist.py; on the Mac mini: tests/macmini/test_api_server_on_mac_mini.py.
           Flux server contract, size, reference shrink, steps, lock, warm-up: tests/test_flux_server.py; import rules: tests/test_import_rules_flux_server.py; on the Mac mini: tests/macmini/test_flux_server.py.
Slices:    none left in this repo. Remaining for the user: point the frame's client (ai-photo-frame-client, on the Pi) at http://davids-mac-mini.local:8000, and copy any photos the frame should keep into data/img on the Mac mini.

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
           API server gets restyled images from FLUX_BASE_URL (default 127.0.0.1:8081), 502 on Flux failure, no retries, no BFL key: tests/test_transform_route.py, tests/test_local_flux_config.py, tests/test_flux_client_single_attempt.py; on the Mac mini: tests/macmini/test_flux_client.py.
           Captions, song looks (iTunes cover) and edit prompts from VLM_BASE_URL, 502 on vision model failure, no retries, no keys: tests/test_upload_route.py, test_aesthetic_route.py, test_transform_route.py, test_local_vlm_config.py, test_vlm_requests.py, test_itunes_incomplete_answer.py, test_pipeline_gaps.py; on the Mac mini: tests/macmini/test_restyle_on_mac_mini.py.
           API server LaunchDaemon and install: tests/test_api_plist.py; on the Mac mini: tests/macmini/test_api_server_on_mac_mini.py.
           Flux server contract, size, reference shrink, steps, lock, warm-up: tests/test_flux_server.py; import rules: tests/test_import_rules_flux_server.py; on the Mac mini: tests/macmini/test_flux_server.py.
Slices:    D. The API server runs on the Mac mini and restarts after a reboot; a full restyle from the laptop over HTTP finishes within 60s. Pointing the frame's client at the Mac mini is a change in ai-photo-frame-client, left to the user.
           Reordered 2026-09-17 by the agent, which the user asked to finish the remaining items alone: each item can now be tested against the Mac mini without paid API keys.

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
           API server gets restyled images from FLUX_BASE_URL (default 127.0.0.1:8081), 502 on Flux failure, no retries, no BFL key: tests/test_transform_route.py, tests/test_local_flux_config.py, tests/test_flux_client_single_attempt.py; on the Mac mini: tests/macmini/test_flux_client.py.
           Captions, song looks (iTunes cover) and edit prompts from VLM_BASE_URL, 502 on vision model failure, no retries, no keys: tests/test_upload_route.py, test_aesthetic_route.py, test_transform_route.py, test_local_vlm_config.py, test_vlm_requests.py, test_itunes_incomplete_answer.py, test_pipeline_gaps.py; on the Mac mini: tests/macmini/test_restyle_on_mac_mini.py.
           API server LaunchDaemon and install: tests/test_api_plist.py; on the Mac mini: tests/macmini/test_api_server_on_mac_mini.py.
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
- Observed: failed 2026-09-17. After deploying dc730e6 the LaunchDaemon's server exited at startup with "RuntimeError: There is no Stream(cpu, 0) in current thread" (exit code 3, three runs); fixed by the next entry.
- Observed: seen 2026-09-17 after ebe025b. Both macmini tests passed from the LaunchDaemon's server, and again after a restart (vlm and flux runs = 1, never exited); 298MB free while generating.
- Accepted: 1e68ba9
- Learned: **the edit guard refuses every file the red commit changed, and the red commit included a stub in src/**, so the build agent could not replace the stub and the user had to clear agile.redCommit before the build could land. Red commits now hold test files only; stubs go in a separate commit.
- Learned: **tests/test_flux_server.py and tests/macmini/test_flux_server.py shared a basename with no __init__.py in either directory**, so pytest imported both as module test_flux_server and every run stopped at collection. tests/macmini/__init__.py makes the second one macmini.test_flux_server. Caught by the turn-end hook.
- Learned: **mflux 0.19.1 asks for mlx[cuda13]<0.32 on Linux while mlx-vlm needs mlx>=0.32.2, and uv's universal lock rejects the pair even though both are macOS-only here**. The [tool.uv] override pins mlx>=0.32.2,<0.33 on macOS; an mflux or mlx-vlm needing mlx 0.33 fails to lock until it is edited.
- Decided: two import-linter contracts, one per direction, because one forbidden contract listing api and pipeline on both sides would also forbid api importing pipeline. Tradeoff: two rules to keep in step.
- Decided: the seed is random per request (secrets.randbelow). Tradeoff: the same photo and song give a different image each time; the user said either is fine.
- Decided: the reference is converted to RGB and saved as PNG in a temporary directory, so a CMYK JPEG does not fail. Tradeoff: no test covers CMYK or truncated uploads.
- Decided: size parsing accepts "0x480" or "-5x3" and passes them to mflux. Tradeoff: those get whatever error mflux raises instead of a 400.
- Decided: mypy ignores missing imports for mflux.*, because mflux ships no type information and does not install on Linux. Tradeoff: calls into mflux are untyped.

## 2026-09-17 — Bug: Flux server crashes at startup on the Mac mini
- Done: flux_server.py builds the model and runs every generation on one module-level single-worker ThreadPoolExecutor; scripts/install-mac-mini waits up to 30s for launchctl bootout to finish before bootstrap.
- By hand: none. The user asked the agent to write the criterion and table and to merge.
- Observed: not yet. Signal: after deploy and reinstall, `launchctl print system/com.local-shazam.flux` shows the server running and `uv run pytest -m macmini` passes.
- Observed: seen 2026-09-17. install-mac-mini reinstalled all three LaunchDaemons with no bootstrap error; after a restart the boot deploy failed once on DNS and deployed ebe025b on its second run.
- Accepted: 828df6f
- Learned: **MLX 0.32.2 raises "There is no Stream(cpu, 0) in current thread" when a graph built on one thread is evaluated on another**, and main() built Flux2KleinEdit on the main thread while anyio ran generations on pool threads. Reproduced with plain mlx on the Mac mini. Pinned by tests/test_flux_server_thread.py.
- Learned: **mutmut 3.8.0 forks a child per mutant after the parent has started the executor's thread, and a forked executor has no thread**, so every submit waited and all 49 mutants timed out. os.register_at_fork gives each child a new executor.
- Learned: **`launchctl bootout` returns before the job is gone**, so an immediate `launchctl bootstrap` failed with "Bootstrap failed: 5: Input/output error" and left com.local-shazam.vlm unloaded until it was bootstrapped by hand. Not pinned by a test.
- Learned: **mutmut copies only src/ and tests/ into mutants/**, so tests/test_deploy.py failed in CI's mutation step the first time a PR changed src/. pyproject.toml's [tool.mutmut] also_copy adds scripts/ and deploy/.
- Learned: **with the vision model server and the Flux server both loaded and generating, the Mac mini had 162MB free and 6.9GB compressed**; two edits still took 27.9s and 24.5s.
- Decided: one module-level executor plus a fork hook. Tradeoff: one line of production code exists only for mutmut's forking.
- Decided: the install script's wait loop gives up silently after 30s and lets bootstrap fail. Tradeoff: a stuck job shows launchctl's own "Input/output error" instead of a message naming the job.
- Not caught by: the Flux server tests faked the model, and a fake has no thread affinity; the review applied the table's mutations by hand and ran nothing on the Mac mini before merge. tests/test_flux_server_thread.py now asserts one thread; the Mac mini test now runs against the real server before a Flux change is merged.

## 2026-09-17 — Restyle with the image from the local Flux server
- Done: Flux2Client(base_url) sends the photo and prompt to {FLUX_BASE_URL}/images/edits through the openai package and returns the PNG; failures become 502 "Flux server failed: ..."; BFL_API_KEY and the BFL polling client are gone.
- By hand: none. The agent wrote the criterion and table at the user's request.
- Observed: not yet. Signal: the frame shows a restyled photo once item D runs the API server on the Mac mini; until then tests/macmini/test_flux_client.py passing against the Mac mini (22.8s) is the only real call.
- Observed: seen 2026-09-17 in part. After the API server moved to the Mac mini, restyles through it got their image from the Mac mini's Flux server (tests/macmini/test_api_server_on_mac_mini.py passed). The frame itself not yet checked.
- Accepted: 3c0523d
- Learned: **the openai package retries a 500 or a connection error twice by default**, so a failed 25-40s edit would have been sent three times. max_retries=0, pinned by tests/test_flux_client_single_attempt.py.
- Learned: **an AsyncOpenAI client kept on the Flux2Client instance left its socket open, and filterwarnings=error turned the ResourceWarning into a failure of the macmini row**. The client is opened and closed per edit.
- Learned: **mutmut segfaults on this machine for flux2_client.py and server.py too**, not only pipeline.py; the review applied every row's mutation by hand. Not pinned; CLAUDE.md's Mutation Testing note covers pipeline.py only.
- Decided: timeout 300s per edit. Tradeoff: a hung Flux server holds the frame's request for 5 minutes before a 502; no test pins it.
- Decided: every photo is sent as photo.jpg, image/jpeg, because pipeline.transform passes only base64 bytes. Tradeoff: a PNG upload is mislabelled; flux_server.py reads neither the name nor the type.
- Decided: httpx stays a runtime dependency although no src module imports it now. Tradeoff: one redundant line in pyproject.toml; openai depends on httpx anyway.

## 2026-09-17 — Captions, song looks and edit prompts from the local vision model
- Done: OpenAIClient(VLM_BASE_URL) sends captions, edit prompts and song looks to mlx_vlm.server's Qwen3-VL-4B; a song look reads the iTunes album cover and catalog facts (ItunesClient), treating any iTunes failure or incomplete answer as no catalog data; OPENAI_API_KEY and the startup key check are gone, so item C is folded in.
- By hand: none. The agent wrote the criterion and table at the user's request.
- Observed: not yet. Signal: once item D runs the API server on the Mac mini, the frame shows a restyled photo with no key set. Before merge, tests/macmini/test_restyle_on_mac_mini.py passed from the laptop against the Mac mini's servers in 124s (upload, cold song look, two restyles; the second under 60s).
- Observed: seen 2026-09-17 in part. The Mac mini's API server, with no key set, captioned, looked up "Midnight City" by M83 from its cover, and restyled within the test's 60s second-restyle limit. The frame itself not yet checked.
- Accepted: b8a2fa4 (corrected by 91252b6)
- Learned: **ImageStore.save_described writes only EXIF tag 270**, so the GPS, date and camera lines the edit prompt was built from never ran for an uploaded photo; they were deleted from pipeline.py. extract_image_metadata in image_store.py still parses them for nothing.
- Learned: **a changed src file puts every one of its lines under CI's mutation step**, so each item here also tested or deleted older untested lines (log calls, a one-key list join, FastAPI title, unused defaults). Hand mutations locally must delete __pycache__ and set PYTHONDONTWRITEBYTECODE=1: a same-size restore in the same second reused a stale .pyc and gave false reds.
- Learned: **the red run for item B hid a wrong test**: tests/test_local_flux_config.py restyled an uncached song without mocking iTunes, and startup failing on the missing key masked respx's AllMockedAssertionError. Corrected in 91252b6.
- Decided: an iTunes failure, empty result, missing field or non-JSON body all mean "No catalog data found." Tradeoff: a malformed iTunes answer is silent.
- Decided: vision model timeout 120s, no retries. Tradeoff: a cold model load over 120s returns 502.
- Decided: logging of prompts and replies removed from openai_client.py. Tradeoff: less to read when a caption or look is poor.
- Decided: captions use Pillow's default thumbnail filter instead of LANCZOS. Tradeoff: slightly different pixels; caption quality not compared.
- Decided: openapi.yaml still says GPT-4o in two descriptions, and OpenAIClient keeps its name. Tradeoff: names that no longer match what runs; a rename is its own change.

## 2026-09-17 — API server on the Mac mini
- Done: deploy/com.local-shazam.api.plist keeps local-shazam-server running on 0.0.0.0:8000 as dave; install-mac-mini installs all four LaunchDaemons; scripts/deploy ends the running API server after uv sync so launchd restarts it on the deployed code; README has a Mac mini section.
- By hand: none. The agent wrote the criterion and table at the user's request.
- Observed: not yet. Signal: tests/macmini/test_api_server_on_mac_mini.py passes after install and again after a restart, then the frame shows a restyled photo once its client points at davids-mac-mini.local:8000.
- Observed: seen 2026-09-17. After install the test passed in 134.6s; scripts/deploy restarted the API server (pid 2391 to 2526, launchd runs = 2); after a restart of the Mac mini all five macmini tests passed in 315.5s. The frame is not yet pointed at the Mac mini.
- Learned: **bash reads scripts/deploy while it runs, and the deploy's git merge rewrote that file mid-run**, so the first deploy of 465046b stopped printing after uv sync and skipped its last lines. Later runs were whole. Not pinned; wrapping the script body in a function that bash reads before running would stop it.
- Accepted: cf0dc70
- Learned: **no API server was running on ai-server when this work started**: nothing listened on port 8000 and the only container was llama-swap, so none of these merges could break a live frame.
- Decided: scripts/deploy restarts only the API server, with pkill on this checkout's .venv/bin/local-shazam-server path. Tradeoff: no automated test covers that line (deleting it leaves the suite green); the vision model and Flux servers keep old code until a restart, because each reload costs minutes of model loading.
- Decided: every boot restarts the API server once after the boot deploy's uv sync. Tradeoff: a few seconds of downtime at boot.
- Decided: DATA_DIR stays at data/ inside the checkout on the Mac mini. Tradeoff: photos live next to the code; the two photos in the laptop's data/ were not copied.

## 2026-09-17 — Bug: song look used the wrong song's album cover
- Done: ItunesClient uses the first search result (limit 25) whose title equals the song ignoring case and whose artist contains the requested artist ignoring case; otherwise it searches the artist and looks through up to 200 of their songs; no match is still "No catalog data found."
- By hand: none. The agent wrote the criterion and table at the user's request.
- Observed: not yet. Signal: after deploy and deleting the cached "365" look on the Mac mini, restyling IMG_3216.JPG for "365" by Charli XCX sends the BRAT cover.
- Accepted: 0b7c9da
- Learned: **iTunes search for "365 Charli XCX" does not list 365 in its top 200 results, and its top result is "party 4 u"**; find_song took results[0], so the song look described how i'm feeling now's cover. The artist lookup (id 432942256, entity song, limit 200) lists 365 on BRAT. Pinned by tests/test_aesthetic_route.py::test_song_missing_from_search_is_found_in_the_artists_catalog.
- Learned: **the frame's client (ai-photo-frame-client, recognition.py) sends Shazam's track subtitle as song_artists and waits 60s for POST /images (app.py, ImageClient timeout=60.0)**. A first play of a new song took 23.1s for the look plus 41.4s for the restyle on the Mac mini, over that 60s.
- Decided: exact title and contained artist, no fuzzy matching. Tradeoff: a title or artist written differently from iTunes ("Guess (feat. Billie Eilish)" against "Guess featuring Billie Eilish", "Lady Gaga, Bruno Mars" against "Lady Gaga & Bruno Mars") gets "No catalog data found." where results[0] often had the right cover.
- Decided: a miss makes up to three iTunes requests before the cover, each with httpx's default 5s timeout per phase. Tradeoff: a slow miss adds seconds to a new song's look.
- Not caught by: the item B tables faked iTunes with the right song first, and the macmini tests used songs whose top result is correct. The row above now fakes a wrong top result.
