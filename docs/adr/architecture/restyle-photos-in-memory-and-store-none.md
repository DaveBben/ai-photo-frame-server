# Restyle a photo sent with each request, and store no photo on the Mac mini

**Decision:** `POST /images` takes the photo itself, as the multipart field `file`, with the form fields `song_title` and `song_artists`, and returns the restyled 800x480 PNG. The server writes neither the photo nor the result to disk. `PUT /images` and `GET /images` are removed, along with `ImageStore`. The owner's reason: "Privacy, photos should only live on the Pi's drive." Keeping the old endpoints and deleting the stored copy after each restyle would still put every photo on the Mac mini's disk for the length of a restyle.

## The problem

The frame client on the Raspberry Pi now owns the photos. The host uploads them through the Pi's web page, and the Pi stores them on its removable drive. When a song plays, the Pi asks this server to restyle the photo currently on screen.

Before this decision the server kept its own photo library. `PUT /images` saved each upload twice, to `data/img/original/<id>.jpg` and to `data/img/analyzed/<id>.jpg` with the vision model's caption in EXIF tag 270. `GET /images` returned a random photo from `data/img/analyzed/`. `POST /images` took an `image_id` and restyled that stored photo. Every photo ever uploaded stayed on the Mac mini's disk until someone deleted the files by hand.

The Mac mini runs with FileVault off (`docs/adr/local-ai/generate-restyled-images-on-the-mac-mini.md`, item 9), so anyone holding the machine can read those files.

## Why the obvious fixes don't work here

- **Add a new `POST /restyle` next to the old endpoints.** The old client keeps working, but `PUT /images` stays, and any caller can still write a photo to `data/img/`. The owner's rule is that no code path on the server stores a photo.
- **Keep upload-then-restyle and delete the stored copy after the restyle returns.** The owner first leaned this way. The photo is still written to `data/img/original/` and `data/img/analyzed/` for the 40 to 60 seconds of a restyle. When the server crashes or the Mac mini loses power in that window, the delete never runs and the photo stays on an unencrypted disk. (Agent's point, accepted by the owner.)

The actual cause is that the server has a photo store at all. The fix is to remove it.

## What we decided

1. **One request carries the photo.** `POST /images` reads the multipart field `file` and the form fields `song_title` and `song_artists`, all required, and returns `image/png` bytes at 800x480.
2. **The photo stays in memory.** The server decodes the uploaded bytes with Pillow, captions them with the vision model, and sends them to Flux. It writes no file of the photo or of the result.
3. **The store goes.** `PUT /images`, `GET /images` and `image_store.py` are deleted, and `data/img/` is no longer created at startup.
4. **Song looks stay cached.** `data/aesthetic_cache.db` keeps its (artist, song) to text rows. They describe a song's album art and hold nothing from a photo.

## What it buys

Before, every photo the Pi ever uploaded sat on the Mac mini's disk indefinitely. After, a photo exists on the Mac mini only in the server process's memory for the one request that carries it. The Pi makes one HTTP call per restyle instead of two.

## What it doesn't buy

- **Every restyle is about 16 seconds slower.** The vision model used to caption a photo once, at upload (16.5s measured), and every later restyle reused the caption stored in EXIF. Now it captions the photo on every request. A restyle for a song the server has seen goes from about 38s to about 55s, and a new song from 60 to 67s to about 77 to 84s. These are the earlier measurements added together, not measured end to end. If the wait matters, the Pi can store the caption text and send it back, as a later change.
- **Memory is not disk-proof.** macOS can page process memory to its swap file, which FileVault-off leaves unencrypted. Nothing here prevents that.
- **Logs and `mlx_vlm.server` are not audited.** This decision covers the API server's and the Flux server's own writes. The Flux server no longer writes the reference photo: it hands mflux the Pillow image in memory and keeps every upload out of Starlette's temp file (`tests/test_flux_server_no_disk.py`). Whether `mlx_vlm.server` writes inputs to disk is still not established; checking its data and cache directories after a restyle would establish it.
- **The old client stops working.** `ai-photo-frame-client` calls `GET /images` and the old `POST /images`, and both break. It is retired.

## Alternatives rejected

- **`POST /restyle` alongside the old endpoints** — leaves `PUT /images` able to write photos to disk.
- **Upload, restyle, then delete** — writes each photo to disk for the length of a restyle, and a crash in that window leaves it there.

**Detector:** a route test in `tests/` (added by the story that makes this change) sends a photo, title and artist to `POST /images` against a temporary `DATA_DIR` and asserts an 800x480 PNG comes back and that no file was created under `DATA_DIR` except `aesthetic_cache.db`. It does not check swap or the model servers.

**Supersedes:** none. It changes the route list in `docs/adr/architecture/split-api-pipeline-and-clients.md`, which stays as the record of the layer split.
