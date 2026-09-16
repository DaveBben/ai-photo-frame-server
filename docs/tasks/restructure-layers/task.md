# restructure-layers

## Plan
Outcome:   When I swap a paid model for a local one, I edit one place, and `./check` fails if any other code calls a model.
Problem:   The developer starting the local-AI work in SPIKE_FINDINGS.md. Today model clients are built from settings in three places
           (api/routes.py, image_transformer.py, ImageStore in process_images.py) and the song-aesthetic lookup is written twice.
Not doing: No change to any route's request or response; openapi.yaml stays as it is.
           No interface class in front of a model client (docs/adr/architecture/split-api-pipeline-and-clients.md).
           No change to the prompt files or the SQLite aesthetic cache schema.
           No local models; that is the next piece of work.
Slices:
  1. Transform a photo: POST /images goes through pipeline.transform, server builds both clients, image_transformer.py deleted (a day)
  2. Look up a song's aesthetic: GET /aesthetic and transform share one pipeline.get_aesthetic (hours)
  3. Upload a photo: PUT /images goes through pipeline.describe_and_store, store renamed image_store and stops calling the model, import-linter rules land (hours)
