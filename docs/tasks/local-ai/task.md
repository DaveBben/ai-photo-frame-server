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
           Flux runs on the Mac mini in its own process, answering the OpenAI images format, with its code in this repo: docs/adr/local-ai/generate-restyled-images-on-the-mac-mini.md.
Deferred:  none yet.
Slices:    1. Restyle a photo with the image made by a local Flux model.
           2. Look up a new song's look from its album cover.
           3. Restyle a photo with the edit prompt written by a local model.
           4. Upload a photo and have a local model describe it.
           5. Start the server with no OpenAI or Black Forest Labs key set.
           6. Have the local model servers start again by themselves after the machine reboots.
