# Generate restyled images on the Mac mini, not on ai-server

**Decision:** The restyled image is made by Flux.2 Klein 4B, 4-bit, loaded once and kept in memory by its own process on the Mac mini. The API server calls that process over HTTP. `ai-server` already serves the larger Klein 9B and makes an image in 5.4s, but it unloads the model 120s after the last request and takes 44.7s to load it again. A photo frame that restyles now and then would pay that load on most requests.

## The problem

`POST /images` restyles a stored photo for a song. `pipeline.transform` has a language model write an edit prompt, then sends the photo and the prompt to `Flux2Client.generate_image`, which today calls the paid Black Forest Labs API running Flux.2 Klein 9B. The Pi client waits on that one HTTP call, and the frame's owner wants the restyled photo within 60 seconds with no paid API call.

Two local machines can run Flux. `SPIKE_FINDINGS.md` on `main` measured both:

- **Mac mini** (Apple M4, 16GB unified memory): Klein 4B 4-bit through `mflux`'s `Flux2KleinEdit`. With the photo scaled to 512px on its long edge, 800x480 output and 3 steps, one image takes 25.1s every time once the model is loaded (F15, F22). Writing the prompt with Qwen3-VL-4B took 13.4s, so a restyle for a song whose aesthetic is cached took 38.5s.
- **ai-server** (RTX 3090 Ti): Klein 9B at Q8 through `sd-server` behind `llama-swap`, which answers `POST /v1/images/edits` in the OpenAI images format. It took 5.4s with the model loaded and 44.7s when it had to load 17.3GB first (F23). `llama-swap` unloads the model 120s after its last request (`ttl: 120`).

## Why the obvious fixes don't work here

- **Use ai-server because it is five times faster.** It is faster only while the model is loaded. After two idle minutes the next request loads the model for 44.7s, and with the 13.4s prompt a restyle takes 58.1s, 1.9s under the limit. That prompt time was measured on the Mac mini, and nothing measured it together with a cold load.
- **Raise `ttl` on ai-server so the model stays loaded.** Klein 9B holds 18.6GB of the 3090 Ti. The GPU's other large models share it through `llama-swap` and would be evicted for as long as Flux stays loaded (F14).

The actual cause is that the fast machine gives up its speed whenever requests are more than two minutes apart, and a photo frame's requests are.

## What we decided

1. **Flux runs on the Mac mini.** It is Klein 4B 4-bit (`Runpod/FLUX.2-klein-4B-mflux-4bit`, 4.3GB on disk), loaded through `mflux`.
2. **Flux runs in its own process, separate from the API server.** `Flux2Client` keeps making an HTTP call and only the host changes. The Flux process can be restarted without stopping the API server (F13).
3. **The model stays loaded between requests.** `Flux2KleinEdit` loads its weights on the first `generate_image` call, so the process makes that call once at startup and holds the model after it (F11).
4. **The Flux process answers the OpenAI images format.** It takes `POST /v1/images/edits` as multipart with the photo as a file and the prompt as a form field, and returns JSON with the PNG as base64 in `data[0].b64_json`. `llama-swap` on ai-server answers the same request (F23), so pointing `Flux2Client` at ai-server later is a URL change.
5. **The Flux process's code lives in this repo.** It is its own module with its own start command, and `mflux` is installed only on macOS through a `sys_platform == 'darwin'` marker, because no `mflux>=0.16` install resolves for Linux x86_64, where CI and the `Dockerfile` build. An import rule in `pyproject.toml` keeps the Flux module and the API server from importing each other.

## What it buys

A restyle for a cached song takes about 38.5s whether the last request was a minute ago or a day ago. On ai-server the same restyle takes 18.8s or 58.1s depending on that gap. The 3090 Ti's other models are never evicted by the frame. The paid Black Forest Labs call and its API key go away, and no new machine joins the request path.

## What it doesn't buy

- **Memory is at its limit.** With Flux and Qwen3-VL-4B both loaded and after one image, the Mac mini had 203MB free out of 16GB (F19). Nothing else can run on it. Qwen3-VL-8B does not fit alongside Flux. Measure free memory with `top` after the prompt-writing model moves to the Mac mini in the third piece of work. If the machine starts swapping, move prompt writing to ai-server's `qwen3.6-4b`, which is never unloaded (F20).
- **The image is from the smaller model.** Klein 4B at 512px drifted the leather jacket in the test photo toward a sequinned texture, while face, pose and scarf held (F18). No one has compared it side by side with Klein 9B.
- **A new song still takes over 60s.** Looking up a new song's aesthetic added 28.7s, for 67.2s in total (F22). Only the first play of each song pays it, because `AestheticCache` stores the result.
- **Only single, one-off runs were measured.** A frame restyling repeatedly may slow as the Mac mini heats up. Time ten restyles in a row after the first piece of work ships.
- **The reference size and step count are not decided here.** The 25.1s figure uses a 512px reference and 3 steps. The first piece of work sets both.

## Alternatives rejected

- **ai-server with `ttl: 120`**: a restyle after two idle minutes takes 58.1s, and a new song on top of that goes to about 87s.
- **ai-server with a longer `ttl`**: keeps 18.6GB of the 3090 Ti away from the models that share it.
- **A separate repo for the Flux process**: keeps `mflux` out of this repo's lock file, but a change to the request format would need two pull requests merged in step, with no test covering both sides.
- **A JSON endpoint of our own returning PNG bytes**: fewer lines in the client and the Flux process, but moving image generation to ai-server would mean rewriting `Flux2Client` again.

**Detector:** none yet. No test asserts which host makes the image or how long a restyle takes.

**Supersedes:** none.
