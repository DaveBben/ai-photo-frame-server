# Route every model call through one pipeline module, and let only the server read config

**Decision:** The code is split into three layers. `api` handles HTTP. `pipeline` runs the upload, aesthetic and transform steps. The model clients and the two stores do one job each and never import each other. `server` is the only module that reads `Settings`, and it builds every client and store once at startup. Encoding today's imports as rules would make the current tangle permanent, because three modules each build their own model client from settings.

## The problem

The server has four routes. `PUT /images` stores a photo and asks a vision model to describe it. `GET /images` returns a random stored photo. `GET /aesthetic` describes a song's visual style. `POST /images` writes an image-edit prompt from that style and the stored description, then sends the photo and prompt to Flux.2 for editing.

Before this decision, model calls started from three places:

- **`process_images.ImageStore`** creates an `OpenAIClient` in its constructor and calls GPT-4o in `put_image`, between saving the original JPEG and saving the described copy. Saving a file to disk needs a working model, and no test can store an image without faking OpenAI.
- **`api/routes.get_aesthetic`** creates its own `OpenAIClient` on each request. It reads the SQLite aesthetic cache, calls `search_aesthetic` on a miss, checks the reply for "No visual data found", and writes the cache.
- **`image_transformer._generate_flux_prompt`** repeats that same cache-then-search logic line for line. `transform_image` then checks `bfl_api_key` and `openai_api_key` and creates a new `OpenAIClient` and `Flux2Client` on each call.

The planned local-AI work (see `SPIKE_FINDINGS.md`, section F13) points the OpenAI client at a local `mlx_vlm.server`, replaces `search_aesthetic` with an iTunes album-art lookup, and replaces the Flux client's BFL polling with one local HTTP call. On the old structure, that work edits the aesthetic logic in two places and client construction in three.

## Why the obvious fixes don't work here

- **Encode the current imports as dependency rules.** The rules would pass on day one. They would also forbid nothing that matters, because the storage module calling a model and the routes calling a model are both edges in today's graph.
- **Add an interface class in front of each client.** Each client has exactly one implementation. The local-AI work replaces what a client does behind its existing methods rather than running two implementations side by side, so an interface adds a file per client and gives the code no second implementation to choose.

The actual cause is that storage, orchestration and HTTP each reach for a model client themselves, so there is no single place where model calls happen.

## What we decided

1. **`api` imports only `pipeline`, `exceptions` and `logger`.** Each route reads its dependencies from `app.state`, calls one `pipeline` function, and turns a `ServiceError` into HTTP 502.
2. **`pipeline` holds `describe_and_store`, `get_aesthetic` and `transform`.** Each takes the clients and stores it uses as arguments, and `get_aesthetic` is the only copy of the cache-then-lookup logic.
3. **`image_store` (renamed from `process_images`) saves, lists and loads files, and reads EXIF.** It never calls a model. The EXIF reading moves here from `image_transformer`, which is deleted.
4. **The model clients and the stores never import `api`, `pipeline`, `server`, `config` or each other.**
5. **Only `server` imports `config`.** It builds both clients, the image store and the aesthetic cache once in the FastAPI lifespan.
6. **`prompts`, `exceptions` and `logger` may be imported by any module.**

## What it buys

Swapping a model client for a local one changes that client's module and the one line in `server.py` that builds it. Before, it changed three call sites. The aesthetic lookup changes in one function instead of two. Image storage becomes testable without a model. The rules in items 1, 2, 4 and 5 are checked by the import-linter tool in `./check`, so a later change that imports a client from `api` fails the check. The change adds import-linter as a dev dependency only.

## What it doesn't buy

The HTTP contract in `openapi.yaml` does not change, and this decision does not test it beyond the tests written to pin the current behaviour of the four routes. Those tests fake both model clients, so they prove the code moved without changing what the routes return. They do not prove the real OpenAI or BFL calls still work. The first local-AI slice exercises the real clients against the local servers.

## Alternatives rejected

- **Encode today's import graph as the rules**: it forbids none of the imports that caused the duplication.
- **An interface class per client**: one implementation each, so it adds files and no choice.
- **Restructure inside the first local-AI slice**: rejected by the user. A pure move with unchanged behaviour is reviewed separately from a change in which models run.

**Detector:** the import-linter rules in `pyproject.toml`, one per numbered item 1, 2, 4 and 5, run by `./check`. They assert import directions only. They do not assert that `pipeline` is the only caller of a model at runtime.

**Supersedes:** none.
