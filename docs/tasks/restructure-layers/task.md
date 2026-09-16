# restructure-layers

## Plan
Outcome:   When I swap a paid model for a local one, I edit one place, and `./check` fails if any other code calls a model.
Problem:   The developer starting the local-AI work in SPIKE_FINDINGS.md. Today model clients are built from settings in three places
           (api/routes.py, image_transformer.py, ImageStore in process_images.py) and the song-aesthetic lookup is written twice.
Not doing: No change to any route's request or response; openapi.yaml stays as it is.
           No interface class in front of a model client (docs/adr/architecture/split-api-pipeline-and-clients.md).
           No change to the prompt files or the SQLite aesthetic cache schema.
           No local models; that is the next piece of work.
Slices:    none left. Close-out is next: turn each Learned line below into a test, an ADR or an AGENTS.md line.

## 2026-09-16 — Transform a photo
- Done: POST /images goes through pipeline.transform; server.py builds the OpenAI and Flux clients once at startup; image_transformer.py deleted.
- By hand: none: the user asked the agent to write pipeline.transform.
- Observed: seen 2026-09-16. The user deployed the branch and the frame showed a transformed photo.
- Accepted: b07e0be
- Learned: **`with sqlite3.connect(path) as conn` commits but never closes the connection**, so AestheticCache left one open per read or write until garbage collection. Pinned by tests/test_aesthetic_cache.py.
- Decided: route tests call the app in-process through httpx.ASGITransport instead of Starlette's TestClient, because Starlette 1.6 deprecates TestClient with httpx and asks for an httpx2 package. Tradeoff: an exception the route does not catch reaches the test as that exception, where a running server returns 500.
- Decided: pipeline.transform keeps the image-file existence check the route already makes, so a photo deleted between the two checks still returns 502. Tradeoff: one repeated filesystem check per transform.
- Not caught by: the connection leak had no test, and warnings were not errors until the harness made them so. tests/test_aesthetic_cache.py now fails on an unclosed connection.

## 2026-09-16 — Look up a song's aesthetic
- Done: GET /aesthetic and the POST /images transform both call pipeline.get_aesthetic, the one copy of the cache-then-search lookup. GET /aesthetic now uses the OpenAI client server.py builds at startup instead of building one per request.
- By hand: none: the user asked the agent to write pipeline.get_aesthetic. The user wrote a three-line merge description and skipped the ten questions comparing it with the diff.
- Observed: seen 2026-09-16. The user deployed the branch, GET /aesthetic returned the aesthetic JSON, and the frame showed a transformed photo.
- Accepted: 5be50cf
- Learned: **prompts/search_aesthetic.txt tells the model to reply "Insufficient visual data found.", and get_aesthetic skips the cache write only for replies containing "No visual data found"**, so a failed lookup is cached and reused by every later transform for that song. Kept unchanged by this move. tests/test_aesthetic_route.py::test_no_visual_data_reply_is_returned_and_not_cached pins today's string.
- Learned: **every mutmut mutant in pipeline.py ends as "segfault" on the developer's machine**, so scripts/mutate-changed gave no result and the review applied the mutations by hand. Cause not established; a mutmut run in CI would show whether the crash is local. Not pinned.
- Decided: the branch was rebased onto origin/main, dropping the spike and pre-squash harness commits it had been cut on top of. Tradeoff: the ADR cites SPIKE_FINDINGS.md, which is on spike/local-ai and not on main.
- Decided: routes.py keeps OpenAIClient as a type-only import because two routes annotate with it. Tradeoff: api still names a client type, and the import-linter rule in the next change must allow type-only imports or the annotations go.
- Decided: the transform calls get_aesthetic with keyword arguments, because get_aesthetic takes the song first, the cache and search take the artist first, and mypy passes a swap of two str arguments. Tradeoff: four extra lines.

## 2026-09-16 — Upload a photo
- Done: PUT /images goes through pipeline.describe_and_store; process_images.py is renamed image_store.py and no longer builds or calls a model client; ./check runs lint-imports with one import rule per ADR item 1, 2, 4 and 5.
- By hand: none: the user asked the agent to write pipeline.describe_and_store, and skipped the merge description.
- Observed: not yet. Signal: after deploy, a photo uploaded from the frame with PUT /images appears on the frame through GET /images.
- Accepted: e5067e6
- Learned: **deleting the import rule for ADR item 2 (pipeline imports no api, server or config) or item 5 (only server imports config) left every test green**, because the accepted rule tests only add a client import to routes.py and image_store.py. Pinned by tests/test_import_rules_pipeline_and_config.py.
- Decided: the import rules skip imports inside `if TYPE_CHECKING:`, so routes.py keeps annotating app.state values with client and store types. Tradeoff: a type-only client import in api passes the rules; it cannot build or call a client at runtime.
- Decided: item 1's rule allows indirect imports, because api reaches the clients through pipeline by design. Tradeoff: api reaching a client through exceptions, logger or prompts is not caught by any rule.
- Decided: the image store has two methods, save_original and save_described, because the model call runs between the two saves and a failed call must still leave the original on disk. Tradeoff: two methods where one could take the description.
- Decided: the build is one commit, because the pre-commit hook runs the rule tests, which fail until both the move and the rules exist. Tradeoff: git bisect cannot separate the move from the rules.
