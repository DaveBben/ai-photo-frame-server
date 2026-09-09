# Spike: Local-Only AI Pipeline on 16GB M4 Mac Mini

**Branch:** `spike/local-ai` — all code here is throwaway, not for merge.
**Started:** 2026-09-09

## Question

Can all four AI capabilities currently served by paid APIs run entirely on the
16GB M4 Mac Mini (`mini`), returning a transformed image in under 60s, with
zero paid API calls?

## Finish line

One end-to-end transform executed wholly on `mini` — input photo + song/artist
in, transformed PNG out — with measured wall-clock and peak RAM recorded here.

## Constraints accepted

* **Latency:** Under ~60s for `POST /images`. Keeps the Pi client's synchronous HTTP contract.
* **Fallback order:** Degrade the image model first. Offload diffusion to `ai-server` only if that fails.
* **Hardware:** `mini` = Mac16,10, Apple M4, 10 CPU cores, 16GB unified memory, macOS 26.5.1, 348GB free.

## Capabilities to replace

| # | Capability | Current model | Call site |
|---|---|---|---|
| A | Image captioning (vision) | `gpt-4o` | `process_images._describe_image` (PUT /images) |
| B | Song visual-aesthetic research | `gpt-4o-search-preview` (web search) | `openai_client.search_aesthetic` (cached in SQLite) |
| C | Flux prompt authoring (text) | `gpt-4o` | `image_transformer._generate_flux_prompt` |
| D | Image-to-image edit | Flux.2 Klein 9B via BFL API | `flux2_client.generate_image` |

Note: A's output is stored in EXIF tag 270 and read back by C. A feeds C.

## Outcome

**IN PROGRESS**

## Findings log

### F1 — `mini` had no toolchain at all
No Homebrew, no uv, system Python 3.9.6 only. Xcode Command Line Tools ARE
present at `/Library/Developer/CommandLineTools`. Installed uv 0.12.11 via the
standalone script (`curl -LsSf https://astral.sh/uv/install.sh | sh`) — no sudo
required, no Homebrew needed. uv provides Python 3.13 itself.

### F2 — FLUX.2 Klein 4B is the direct local analogue of the current model
The paid pipeline uses Flux.2 Klein 9B. Black Forest Labs also ships **Klein 4B**,
and `mflux` (MLX-native, Apple Silicon) supports it including native in-context
editing:

* Text-to-image: `mflux-generate-flux2`
* **Image editing: `mflux-generate-flux2-edit --image-paths ...`** — this is the
  direct replacement for `Flux2Client.generate_image`.
* Traditional img2img via `mflux-generate-flux2 --image-path`.

Klein 4B uses a **single Qwen3 text encoder**, not FLUX.1's dual CLIP+T5 and not
the Mistral-24B encoder of the larger FLUX.2 models. This is why it fits in 16GB.

Pre-quantized 4-bit weights for mflux exist: `Runpod/FLUX.2-klein-4B-mflux-4bit`,
**4.3 GB on disk**, requires mflux >= 0.16.0.

Published timings (not yet reproduced on `mini`):
| Hardware | Resolution | Steps | Time |
|---|---|---|---|
| M3 Pro 18GB | 512x512 | 4 | ~11s |
| M1 Max 64GB | 512x512 | 4 | 12.0s inference / 23.7s wall |
| M1 Max 64GB | 1024x1024 | 4 | 21.4s inference / 31.7s wall |

M4 base has a 10-core GPU, weaker than both. Expect slower. **Must measure.**

**Gotcha:** the CLI entry point is `mflux-generate-flux2`, NOT `mflux-generate`.
`mflux-generate` is for FLUX.1 and will fail on FLUX.2 models.

### F3 — mflux exposes a clean resident Python API for the edit path
Shelling out to `mflux-generate-flux2-edit` reloads 4.3GB per call. The Python
API keeps the model resident:

```python
from mflux.models.flux2.variants import Flux2KleinEdit
model = Flux2KleinEdit(model_path="Runpod/FLUX.2-klein-4B-mflux-4bit")
img = model.generate_image(
    seed=42, prompt=..., image_paths=[Path(src)],
    num_inference_steps=4, width=W, height=H, guidance=1.0,
)
img.save(path="out.png")
```

**Quirks found reading the source:**
* `guidance` MUST be `1.0` for distilled checkpoints (klein 4B is distilled). Any
  other value is a hard error.
* FLUX.2 has **no negative prompt branch**. `--negative-prompt` is rejected outright.
  The current `flux_transform.txt` prompt never uses one, so no change needed.
* Passing an HF repo id to `--model` silently routes it to `model_path` and keeps
  the built-in `flux2-klein-4b` config. In the Python API pass `model_path=` directly.
* `Flux2KleinEdit` uses **reference-image conditioning** (reference tokens concatenated
  into the transformer), not classic img2img denoise-strength. Each reference is encoded
  at its own aspect-preserved size, independent of the output dimensions. This matches
  what the paid Klein 9B endpoint does, so prompt semantics carry over.
* There is a KV-cache path enabled automatically when reference images are present.

### F4 — Capability B needs no web search at all: album art is the aesthetic
`gpt-4o-search-preview` was doing a web search to describe a song's visual world.
The **iTunes Search API is free, keyless, and returns the official album cover**:

```
https://itunes.apple.com/search?term=<song>+<artist>&entity=song&limit=1
```

Verified working. Returns `trackName`, `artistName`, `collectionName`,
`primaryGenreName`, `releaseDate`, and `artworkUrl100`. Swapping `100x100bb.jpg`
for `600x600bb.jpg` in the URL yields full-resolution cover art.

This is arguably *better* input than a web search for this specific job: the
`search_aesthetic.txt` prompt demands "specific colors with hex codes" and
"textures and material qualities". A local VLM reading the actual album cover
gets those from pixels rather than from prose. The catalog metadata (genre, year,
album) plus the model's own parametric knowledge covers the artist-identity section.

**Cost: $0, no API key, no scraping, no rate-limit risk at this volume.**

### F5 — Capability D produces convincing output at 512x512 / 4 steps
First real generation on `mini` succeeded. Source: a stock portrait (person from
behind, beach at golden hour, leather jacket, mustard scarf, sunglasses). Prompt:
a hand-written stand-in for the "bad guy" aesthetic (lime green overhead strobe,
warehouse haze, #8ACE00, heavy grain, crushed blacks).

Output honoured every instruction that matters:
* Overhead green strobe rendered as an actual overhead source, not a colour wash.
* Warehouse haze and depth present; beach fully replaced.
* Leather rendered wet/specular as described.
* Heavy grain and crushed blacks applied.
* **Identity preserved** — same pose, same scarf weave, same sunglasses, same hair,
  same jacket silhouette. The "preserve facial features / silhouette" tail of
  `flux_transform.txt` is respected.

Quality at 4 steps is not meaningfully below what the paid Klein 9B endpoint returns
for this class of edit. `flux_transform.txt` needs **no changes** to work against
Klein 4B.

### F6 — mlx_vlm.server is a drop-in for the OpenAI client
`python -m mlx_vlm.server` exposes `/v1/chat/completions` accepting
`data:image/...;base64,...` in `image_url` — byte-identical to what
`OpenAIClient.describe_image` already sends. Useful flags:
`--model` (preload at startup), `--port`, `--api-key`, `--vision-cache-size`,
`--max-kv-size`. Integration for capabilities A and C is a `base_url` swap on the
existing `AsyncOpenAI` construction, nothing more.

### F7 — 768x768 is the quality sweet spot, 512 is the fallback
Same prompt, same seed, 4 steps. 768 is a clear step up from 512: the overhead
source resolves into an actual strip-light fixture rather than a glow blob,
warehouse depth becomes legible, grain is finer, scarf weave and leather
specularity hold detail. Identity preservation is equally good at both.

Recommend generating at 768 and letting the frame client scale, unless the frame
panel is genuinely >768px on its long edge.

### F8 — Generate at 800x480, not square: the frame is 800x480
The client (`DaveBben/ai-photo-frame-client`) drives an 800x480 Raspberry Pi
touchscreen. Both dimensions are divisible by 16, so Flux can target the panel
resolution directly.

| Target | Pixels | vs 768x768 |
|---|---|---|
| 512x512 | 262,144 | -56% |
| **800x480** | **384,000** | **-35%** |
| 768x768 | 589,824 | baseline |
| 1024x1024 | 1,048,576 | +78% |

Generating square and letterboxing was costing ~35% more compute than the panel
can even display. Diffusion cost scales with pixel count, so 800x480 should land
close to the 512x512 timing while filling the screen edge to edge.

**This is the single cheapest latency win available and it costs no quality.**

### F9 — iTunes lookup verified across genres, degrades cleanly
Five queries, no key, no auth, sub-second each:

| Query | Resolved | Genre | Cover |
|---|---|---|---|
| bad guy / Billie Eilish | WHEN WE ALL FALL ASLEEP... | Alternative | 40KB |
| Midnight City / M83 | Hurry Up, We're Dreaming | Electronic | 100KB |
| Alright / Kendrick Lamar | To Pimp a Butterfly | Hip-Hop/Rap | 117KB |
| Teardrop / Massive Attack | Mezzanine | Electronic | 77KB |
| (nonsense string) | **NO MATCH** — empty `results`, no error | — | — |

The miss path returns an empty `results` array rather than throwing, so the
"Insufficient visual data found" branch in `search_aesthetic.txt` still has a
clean trigger. On a miss the model falls back to parametric knowledge only.

### F10 — 1024x1024 thrashes swap on 16GB; 768 and below do not
During the 1024x1024 pass the worker hit `MEM=10G, STATE=stuck` in `top`, with
system swap at 1.65GB used and 229MB unused. It completed, but only by paging.
512 and 768 ran without entering that state.

**Ceiling for this box: do not generate above 768 on the long edge.** Since the
frame is 800x480 (F8) this costs nothing.

Note: `resource.getrusage(...).ru_maxrss` reported a useless 1.9GB throughout —
MLX allocates through Metal buffers that do not appear in RSS. **Measure Apple
Silicon memory with `top`/`PhysMem`, not `ru_maxrss`.**

### F11 — First benchmark numbers were contaminated; large fixed overhead exposed
Run 1 (concurrent with a 4GB HF download and a macOS Photos library re-index,
under swap pressure):

| Size | Steps | Time |
|---|---|---|
| 512x512 | 4 | 68.3s |
| 768x768 | 4 | 87.9s |
| 1024x1024 | 4 | 115.1s |

The marginal cost is strikingly linear at **~59.7s per megapixel** (512->768 and
768->1024 agree to within 1%). Extrapolating to zero pixels leaves **~52s of fixed
overhead per process**, which is weight loading, not generation.

`Flux2KleinEdit(...)` returned in 0.6s — **construction is lazy, weights load on the
first `generate_image` call.** Any timing that measures the constructor is measuring
nothing. This is why a resident model process matters: that ~52s is paid once at
startup, not per request. Re-measured in F12 with the model warm and the box idle.

## Dead ends

(none yet)

## Open questions

* Actual wall-clock and peak RAM on M4 base — all published numbers are from faster GPUs.
* Can the VLM and the diffusion model be resident simultaneously in 16GB, or must they swap?
* What replaces the web search in capability B without an API key?
