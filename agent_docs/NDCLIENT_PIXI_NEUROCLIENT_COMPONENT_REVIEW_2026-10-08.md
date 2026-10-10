# NDClient component decisions: existing NeuroClient + current Pixi

Date: 8 October 2026. Required companion to the
[master plan](NDCLIENT_IMPLEMENTATION_PLAN_2026-10-08.md).

The user is correct: NeuroClient already rendered substantial non-VFX content.
Missing the current VFX bank does not justify throwing that work away. A fresh
repository establishes cleaner dependencies; it is not a mandate for fresh versions
of every drawing function. **Inspect existing NeuroClient first, current Pixi API
second, then adapt only for actual missing requirements.** Pygame contributes current
authoring data, behavioral requirements and failure cases, not rendering algorithms.

Source inspected at `/home/tommaso/Dev/NeuroClient/app/src`, repository
`d274f2d62ca9c1c5ed62a77841cacf6cc0347491`. No source edits or fresh browser run in
this pass. "Present" below means implementation found in that checkout, not renewed
acceptance of every feature. Local Pixi docs are the saved official 8.x guides with
selected **v8.22.0** API source; guide examples are not all version-correct.

## 1. Component-by-component decision

Paths in the second column are relative to that existing `app/src`, not proposed
new modules. Decisions are at the function/data level; reusing a capability does
not require importing its old global store, singleton or controller hierarchy.

| Component | Existing NeuroClient implementation to recover | Pixi reference checked | Decision / specific extension |
|---|---|---|---|
| Camera and browser input | `ui/boardViewportController.ts`, `iso.ts`, keyboard/pointer focus helpers | [Events](references/pixijs-8.22.0-20261008/guides/components/events.md), [render groups](references/pixijs-8.22.0-20261008/guides/concepts/render-groups.md), [resize](references/pixijs-8.22.0-20261008/guides/components/application/resize-plugin.md) | Keep pan/zoom gestures, focus suppression and change-only hover updates. Replace flat positive rectangular picking with presented support/face picking and current SDK interaction. `iso.ts` uses 64×32; normalize explicitly to current source calibration, not a silent scale change. Return cleanup for ticker/window/observer subscriptions. |
| Grid | `grid.ts` already uses Geometry/Mesh/Shader and a highlight uniform | [Mesh](references/pixijs-8.22.0-20261008/guides/components/scene-objects/mesh.md), [layers](references/pixijs-8.22.0-20261008/guides/concepts/render-layers.md) | Retain shader approach and small highlight updates. Replace global one-plane mesh with registered support geometry, correct floor/wall insertion and explicit instance state. No CPU grid redraw, blanket screen overlay or new grid engine. |
| Terrain, structures and props | `tiles.ts`, `render/staticBoardSync.ts`, `render/structuralEdgeOrder.ts`, `render/connectorPresentation.ts` | [Graphics](references/pixijs-8.22.0-20261008/guides/components/scene-objects/graphics.md), [sprites](references/pixijs-8.22.0-20261008/guides/components/scene-objects/sprite.md), layers | Recover stable identities, structure-state updates and separate geometry/light/visibility invalidation. This checkout's terrain path includes procedural Graphics, not all current animated environment art. Supply current registrations/frames/UVs and raised supports. Replace full-map signatures/old Store subscriptions with changed displayed facts. |
| Ordinary depth and elevation | `render/worldDepth.ts`, structural edge ordering and contact helpers | Mesh, layers, pinned [State](references/pixijs-8.22.0-20261008/api-source/src/rendering/renderers/shared/state/State.ts) | Retain deterministic ties/contact concepts. Flat X+Y and effect screen-Y depth are insufficient for elevation. Use the selected common physical composition; do not copy Python image partitioning or claim zIndex handles intersecting transparency. |
| Spritesheets and facing | `render/SpriteAssetRegistry.ts`, `render/facing.ts` | [Textures](references/pixijs-8.22.0-20261008/guides/components/textures.md), sprite guide | Keep shared TextureSource/Texture-region slicing and nearest filtering for pixel art. Replace fixed sheet columns/cell dimensions and `/spritesheets` URLs with current source registration/release references; retain per-frame crop/origin and aliased image reuse. |
| Body layers, gear and pose | `render/AnimatedEntity.ts`, `equipmentVisuals.ts`, `equipmentAdapter.ts`, `visualAnchors.ts` | Sprite, [Container](references/pixijs-8.22.0-20261008/guides/components/scene-objects/container.md), layers | Recover layer transforms, visibility and anchor calculations that match current data. Extract render operations over passive records; do not copy actor/FSM/clip ownership. Extend the same path to all 44 current rigs, baked accents, current sockets, coatings and prone/death semantics. |
| Colour replacement/material | `render/MultiTintFilter.ts`, `paletteMap.ts`, `vfxFilters.ts` | [Filters](references/pixijs-8.22.0-20261008/guides/components/filters.md), pinned [Shader](references/pixijs-8.22.0-20261008/api-source/src/rendering/renderers/shared/shader/Shader.ts), Mesh | Reuse useful mask/source-colour preparation. MultiTint multiplies source RGB and is not the requested colour swap. Implement finite shared material programs with current palette/mask/donor data. Use a filter only for a composed-image operation; no automatic filter per layer. |
| Projectiles and action motion | `render/angleMath.ts`, `projectileEndpoints.ts`, `clips/GridMotion.ts`, `spellAuthoring/SpriteProjectileFx.ts` | Sprite transforms, Mesh, [Ticker](references/pixijs-8.22.0-20261008/guides/components/ticker.md) | Recover mathematical helpers and directional frame selection where compatible. Old VFX code is not coverage of accepted current VFX. Replace async clip-owned timing, flat screen-Y depth and asset-first launch waits with shared absolute-time sampling and prepared resources. Retain current sockets/release times, bank+tangent alignment. |
| Persistent conditions, markers, shadows | `render/conditionPresentation.ts`, condition/controller drawing, original body layers | Sprite, layers, filters | Recover placement/layer utilities; current recipes own lifetimes, suppression, marker playlist and size. Keep body effects separate from head-marker rotation. Do not carry condition-specific controllers as new behavior owners. |
| Lighting and fog | `light.ts`, `staticBoardSync.ts` | Mesh/Shader, [BufferImageSource](references/pixijs-8.22.0-20261008/api-source/src/rendering/renderers/shared/texture/sources/BufferImageSource.ts), filters | Existing light mesh/texture and change-only updates are useful. Adapt to current subjective effective levels, support continuity, historical state and consistent receivers. Do not retain hidden/raw emitter inference or a single floor overlay as the complete lighting solution. |
| Modern volumetric VFX | Existing generic loading/transform/blend functions; no claim that current Fireball/cloud package already works there | Mesh, State, Shader, textures, filters | The accepted Fireball proof supplies evidence; the representation chapter fixes all family formats. N1/N3 test delivery, physical intersections and translucent layering in production; reuse common rendering infrastructure instead of a spell engine. |
| Blood, bone and vapor | Shared sprites/geometry/resources; current authored particle data is in engine presentation sources | [ParticleContainer](references/pixijs-8.22.0-20261008/guides/components/scene-objects/particle-container.md), Mesh, Ticker | Batch finite shapes and analytic trajectories; use the representation chapter's compact instance buffers and analytic shader flight; measure their batching. No Python surfaces, per-droplet entities or stateful fluid/particle simulation. |
| Ground/wall materials | Static board update pattern plus current receiver/deposit registrations | Mesh, [cache-as-texture](references/pixijs-8.22.0-20261008/guides/components/scene-objects/container/cache-as-texture.md), textures | Retain settled local coverage and finite active material increments on actual receivers. Invalidate at displayed changes, preserve seek/rebuild; do not use a full-map screenshot cache or rescan all deposits each frame. |
| Resource load/prepare/unload | `render/presentationAssetService.ts`, SpriteAssetRegistry | [Assets](references/pixijs-8.22.0-20261008/guides/components/assets.md), [background loader](references/pixijs-8.22.0-20261008/guides/components/assets/background-loader.md), [PrepareBase](references/pixijs-8.22.0-20261008/api-source/src/prepare/PrepareBase.ts), textures | Recover request joining, shared-source ownership, texture-limit checks, prepare and leases. Simplify into the one resource owner; do not reproduce every service/evidence wrapper. Extend storage beyond fixed strips; budget pages/uploads/decoded residency, not just asset counts. |
| Compression and numeric planes | Texture-limit/metadata helpers; current archive is source material only | [Compressed textures](references/pixijs-8.22.0-20261008/guides/components/assets/compressed-textures.md), pinned [package exports](references/pixijs-8.22.0-20261008/api-source/package.json), BufferImageSource | Explicitly register only chosen loader. Compare alpha quality, transfer, transcode/upload and resident bytes. Numeric/owner data has separate formats/calibration; original full XYZ is not the mandatory browser format. |
| Lifetime and culling | `destroyContainerChildren.ts`, asset release functions, scene lifecycle teardown | [GC](references/pixijs-8.22.0-20261008/guides/concepts/garbage-collection.md), pinned [GCSystem](references/pixijs-8.22.0-20261008/api-source/src/rendering/renderers/shared/GCSystem.ts), [culler](references/pixijs-8.22.0-20261008/guides/components/application/culler-plugin.md) | Keep explicit resource ownership/cleanup. Unload GPU resources without destroying shared views still in use. Cull spatially where measured; never run two competing cull systems or stop event/lifetime progression when offscreen. |
| Loop, playback and measurement | `render/perfMetrics.ts`, scene tick entry points | [Render loop](references/pixijs-8.22.0-20261008/guides/concepts/render-loop.md), pinned [Ticker](references/pixijs-8.22.0-20261008/api-source/src/ticker/Ticker.ts) | Keep instrumentation/display plumbing. One application-owned presentation clock, independent SDK consumer. Do not inherit ClipQueue/FSM or use ticker delta as server progress. Absolute sample time supports pause/seek and queued AI turns. |
| HUD, inventory and portraits | `ui/actionBar.ts`, `actionBarModel.ts`, `equipmentPanel.ts`, `initiativeBar.ts`, portrait/icon utilities | Events, sprite, Graphics, [Canvas Text](references/pixijs-8.22.0-20261008/guides/components/scene-objects/text/canvas.md), resize | These existing widgets are largely Pixi, not presumed DOM. Recover icon/layout/slot/portrait drawing and input functions with current SDK-fed view data. Remove direct old API/store/command-wait coupling; add requested four blocks, choices and interaction behavior. Do not force a DOM rewrite merely because the repo is new. |
| Text, combat log and tooling panels | `render/pixiRendering.ts`, `pretextLayout.ts`, `ui/combatHistoryPanel.ts`, Studio DOM | Canvas Text, [text](references/pixijs-8.22.0-20261008/guides/components/scene-objects/text.md), events | Retain readable text/layout work where useful. Move text by transform without rerasterizing each frame. DOM is appropriate for selectable/copyable log, forms and Studio controls; same typed log data, no duplicate narrative or action dispatcher. |
| Studio editing/lifecycle | `ui/studio/StudioDocumentHistory.ts`, `StudioModalBoundary.ts`, `StudioPixiSurface.ts`, `StudioPixiLifecycle.ts`, inspectors | Application/resize, events, texture ownership | Recover editing history, modal/focus and viewport lifecycle utilities. Replace synthetic battle/event hosts with one production runtime on actual SDK records. Preserve useful inspector/UI code while covering current source schemas and fixed rigs. |
| Studio channel timeline | `ui/studio/StudioTimelineLayout.ts`, `StudioTimelinePixi.ts`, `StudioTimelineView.ts`, old timeline builders as reference only | Graphics, text, events and existing shared Studio viewport | Retain animator-style lanes/ruler/playhead/selection controls. Derive tracks from current compiler occurrences and canonical source references; replace fixed caster/projectile/target assumptions and separate spell/action/condition builders. Timeline edits use inspector source commands, not an independently serialized editor animation. See master §8.2. |

Additional reusable details found by independent source review: `AnimatedEntity.ts`
manually samples ordered layer frames, guards stale appearance loads with a generation,
and installs a complete new appearance when ready. Keep those useful guarantees
without the entity/FSM shell. `ui/studio/StudioInspectorControls.ts` and
`StudioPixiSurface.ts` provide real inspector and mount/resize/teardown work to recover.
`light.ts` correctly refuses to substitute raw light for a missing effective-map key;
retain that disclosure rule while replacing its flat full-grid canvas overlay.

The old `render/clips/ProjectileFx.ts` also contains a per-frame Graphics clear/rebuild
particle path. This is an explicit **non-reuse** choice, not overlooked existing
work: retain any useful motion data/formulas, use the pinned Graphics advice and
batched geometry, and do not reproduce that raster/tessellation churn.

## 2. Specific API checks that change implementation choices

1. **Shared sources already exist.** Texture regions need not copy pixels. Retain
   NeuroClient's approach; don't import Pygame's camera/palette-specific images.
2. **Prepare is item-count bounded, not byte/time bounded.** Pinned PrepareBase
   processes up to four items per turn by default. A single huge texture can still
   stall. Measure actual uploads; that API default does not impose a page size or
   justify splitting usable assets before integration.
3. **Custom shaders do not automatically batch.** Pinned Mesh disables ordinary
   batching for custom shaders or depth/cull state; MeshPipe breaks the batch.
   Group compatible instances/geometry explicitly;
   do not replace thousands of sprites with thousands of custom meshes and assume
   it is faster. Preserve correct translucent order while batching. Depth-writing
   world bodies/environment use explicit shared geometry/state; recovered ordinary
   Sprite batching serves depth-free UI/resolved overlays, not automatic world depth.
4. **Depth requires actual geometry and state.** `State.for2d()` disables depth test
   and depth writes. RenderLayer controls ordering, not physical intersections;
   RenderGroups have costs/boundaries. No separate render group per actor.
5. **Filters are composed-image passes.** Useful for truly composited effects, not
   the default for every palette/mask. Material shaders can sample local masks
   without repeated intermediate images. Existing source-colour multiplication
   must not masquerade as the user's requested colour replacement.
6. **Ticker time has different units/policies.** `deltaTime` is scaled/dimensionless;
   `deltaMS` is capped/scaled, `elapsedMS` raw. Presentation owns its timestamp and
   pause/resume/seek policy. Browser tab resume must not skip queued semantic events
   because wall time elapsed, nor rescale spell duration by applying two speed factors.
7. **Pointer behavior changed in v8.** Ordinary pointermove is hit-dependent;
   globalpointermove or an explicit canvas hit area supports continuous world hover.
   Keep VFX noninteractive and use one presented geometry picker. UI focus/cursor
   and pointer capture must not steal spell targeting or move through open panels.
8. **Caches are not free.** cacheAsTexture creates a texture/render group and needs
   invalidation. GC guide options lag pinned GCSystem. No cache-per-camera-per-colour
   explosion, giant map capture or destruction of still-shared TextureSources.
9. **GLSL is not WGSL.** Existing NeuroClient GLSL is a useful starting point for the
   chosen WebGL2 backend. Do not claim WebGPU compatibility from the same string.

October 8 follow-up rechecked animated assets against official guides and installed
8.22.0 loader/AnimatedSprite source. The required
[asset packing policy](NDCLIENT_ASSETS_AND_RIG_AUTHORING_2026-10-08.md#22-animated-assets-pixi-source-check-and-packing-policy)
records current sheets versus per-frame Fireball data, independently loadable resources,
the automatic multipack-loading trap, coupled numeric planes, upload/source leases
and disabling independent world-animation tickers. Existing sheets are reused;
an atlas is not assumed to reduce decoded bytes or automatically batch depth meshes.

## 3. Review and proof, without a second development programme

This matrix is a source/documentation check. It must not be described as an already
running restored client or measured compatibility with Pixi 8.22.0. N1 production
integration reuses compatible NeuroClient camera/grid/sprite/resource helpers in
the final modules. The existing standalone Fireball proof remains evidence; no
additional study application or reduced release is created. Reference checkouts
stay untouched.

Before implementing a component, use its cited docs/API and existing source above.
Record only real API differences, changed ownership and measured problems; no new
per-component approval ceremony, schema generator or long-running regeneration loop.
Reviewers verify reuse decisions and reject both unnecessary rewrites and blind
copies of old global state/transport. New shaders/functions remain shared by play
and Studio, and consume authored data rather than spell/creature-specific branches.

The [review receipt](audits/ndclient-plan-20261008/PLAN_REVIEWS.md) covers this matrix
along with the revised master and media representation chapter.
