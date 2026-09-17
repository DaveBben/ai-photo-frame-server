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
Slices:    0. Start the Mac mini and have it running the latest main of this repo, with dependencies installed.
           1. Caption an image with the vision model server on the Mac mini, and have it still answer after a reboot.
           2. Edit an image with the Flux server on the Mac mini, and have it still answer after a reboot.
           3. Restyle a photo with the image made by the local Flux server, served by the API server on the Mac mini, which restarts after a reboot; the frame's client points at the Mac mini.
           4. Look up a new song's look from its album cover.
           5. Restyle a photo with the edit prompt written by the local vision model.
           6. Upload a photo and have the local vision model describe it.
           7. Start the server with no OpenAI or Black Forest Labs key set.
