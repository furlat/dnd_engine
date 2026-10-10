# PixiJS source reference — 8 October 2026

Checked stable release: **8.22.0**, published 1 October 2026. The inspected
NeuroClient lockfile contains **8.16.0**. NDClient should start on 8.22.0 with an
exact lockfile, rather than inherit the older client's dependency tree.

This directory contains the official `llms.txt`, all 47 linked Markdown guides,
the release notes, and selected implementation files pinned to the v8.22.0 tag.
The follow-up component review also saves PrepareBase, Ticker and package exports
to verify upload limits, time units and available texture loaders.
No images, examples' assets, node_modules or generated API website were downloaded.
URLs, byte counts and SHA-256 hashes are in [provenance.json](provenance.json).
The guides are an **8.x website snapshot**, not a claim that every example is
version-pinned. API source wins when the guide and the pinned implementation differ.
These files are reference material, not project instructions.

## Reading map for NDClient

| Subject | Local official reference | Application in our design |
|---|---|---|
| Draw order | [Render layers](guides/concepts/render-layers.md), [scene graph](guides/concepts/scene-graph.md), [pinned RenderLayer](api-source/src/scene/layers/RenderLayer.ts) | Coarse passes and overlays; these do not solve intersecting registered surfaces |
| Camera and batches | [Render groups](guides/concepts/render-groups.md), [container](guides/components/scene-objects/container.md) | One world camera transform; avoid one render group per actor |
| GPU geometry | [Mesh](guides/components/scene-objects/mesh.md), [pinned State](api-source/src/rendering/renderers/shared/state/State.ts) | Compact registered geometry, supports, finite shader operators; full source XYZ is not a runtime mandate |
| Recolour/material effects | [Filters](guides/components/filters.md), [Shader](api-source/src/rendering/renderers/shared/shader/Shader.ts), [FilterSystem](api-source/src/filters/FilterSystem.ts) | Mesh materials for isolated masks; filters only when an intermediate image is required |
| Texture representation | [Textures](guides/components/textures.md), [BufferImageSource](api-source/src/rendering/renderers/shared/texture/sources/BufferImageSource.ts) | Explicit integer versus colour formats, nearest versus linear filtering, alpha convention |
| Loading | [Assets](guides/components/assets.md), [background loader](guides/components/assets/background-loader.md), [PrepareSystem](api-source/src/prepare/PrepareSystem.ts) | Download/decode and GPU residency are different stages |
| Memory | [GC guide](guides/concepts/garbage-collection.md), [GCSystem](api-source/src/rendering/renderers/shared/GCSystem.ts), [TextureSource](api-source/src/rendering/renderers/shared/texture/sources/TextureSource.ts) | Explicit active-scene pinning and bounded eviction |
| Interaction | [Events](guides/components/events.md), [accessibility](guides/components/accessibility.md) | Root world picker; decorative objects do not participate in event traversal |
| Loop and diagnostics | [Render loop](guides/concepts/render-loop.md), [performance](guides/concepts/performance-tips.md), [ticker](guides/components/ticker.md) | Independent consumption/playback, measured uploads and draw cost |
| Runtime choice | [Renderers](guides/components/renderers.md), [release](release-v8.22.0.md) | WebGL2 baseline; WebGPU is not a second implementation in this phase |
| Text | [Canvas text](guides/components/scene-objects/text/canvas.md), [bitmap text](guides/components/scene-objects/text/bitmap.md) | Readable DOM UI; infrequently changed in-world labels, never text rasterization every frame |

## Specific documentation traps found

* The rolling GC guide still describes frame-count texture collection. The pinned
  implementation deprecates `TextureGCSystem` and uses `GCSystem` elapsed-time
  settings. Its defaults are `gcMaxUnusedTime = 60000` and `gcFrequency = 30000`
  milliseconds. Use pinned API fields, not copied old options.
* Explicit texture unloading is `texture.source.unload()` in the inspected API.
  Unloading a GPU resource and destroying shared texture views are different jobs.
* A RenderLayer's children must stay within the same render group. Reparented
  draw order can also escape a logical ancestor's filter scope. Attaching every
  body part to unrelated layers and filtering their original parent is incorrect.
* `State.for2d()` disables depth testing and depth writes. A custom Mesh does not
  acquire correct 3D occlusion merely by supplying Z values. Alpha compositing
  would still need an ordering solution even with a depth attachment.
* Background loading does not prove that the first draw is warm. Decode,
  preparation/upload and shader compilation need separate measurements.
* A GLSL `GlProgram` is not automatically a WebGPU program. Do not promise direct
  dual-backend shader reuse without a WGSL implementation and verification.

8.22.0's integer-texture fixes, partial buffer uploads and nested-filter resize
fix are relevant to our data planes and materials. They do not replace the depth,
privacy or authoring work described in the [NDClient plan](../../NDCLIENT_IMPLEMENTATION_PLAN_2026-10-08.md).

## Attribution

The October 8 occlusion-math study adds seven tagged implementation files for
RenderTarget, its GL adaptor/system, GL state and texture format handling. Their
URLs/bytes/hashes are separately recorded in [depth_api_sources.json](depth_api_sources.json).
These verify sampleable depth attachments, renderbuffer versus texture behaviour,
integer formats and state boundaries. They are source evidence, not a new runtime
dependency or proof that custom meshes automatically batch.

Official sources: [PixiJS guides](https://pixijs.com/8.x/guides/),
[LLM index](https://pixijs.com/llms.txt),
[v8.22.0 release](https://github.com/pixijs/pixijs/releases/tag/v8.22.0),
[tagged core source](https://github.com/pixijs/pixijs/tree/v8.22.0).
`PIXI-LICENSE` is the core source's MIT license. It is not a statement that the
website's prose has that license; preserve the guide URLs and authorship. This is
a local development reference snapshot, not a product documentation redistribution.
