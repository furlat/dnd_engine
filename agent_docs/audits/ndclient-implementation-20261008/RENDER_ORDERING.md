# Renderer implementation — bounded ordering repair

**Historical implementation record; raised/stair placement is not accepted.**
The user subsequently stopped implementation. The
[post-stop review](REVIEW_AFTER_USER_STOP.md) supersedes any geometric-validation
claim below: the raised/stair tool captured images without asserting placement,
and the resulting scenes failed visual review. Immediate work follows the
[foundation repair plan](../../NDCLIENT_FOUNDATION_REPAIR_PLAN_2026-10-08.md).

The complete NDClient implementation remains in progress in
`/home/tommaso/Dev/NDClient`. This records the floor/camera correction requested by
the user, not completion of N1–N5 or a replacement delivery plan.

## Changes

- Shared camera-space depth derives from native grid coordinates and elevation.
  Terrain source pages are GPU batches. Pan/zoom updates uniforms; grid marks
  belong to the floor tops. Reversing tile serialization does not change pixels.
- Raised supports select the registered beds and cliff faces. Native three-support
  stair flights select their existing full-flight artwork and depth columns.
  Joined walls retain constituent boundary directions; environment depth uses the
  canonical pose origin, including its ground-pivot default. Resized destruction
  frames resize their mesh rather than retain the previous image dimensions.
- Character layers compose in authored slot order into a reusable native-cell
  target. Only the resulting body enters world depth; its shadow remains on the
  support. Ground-depth sockets preserve prone/death registration.
- Source alpha is not a tile visibility stencil. Opaque contributors retain depth
  and a tie key; translucent edges and projectiles are selected in physical depth
  order. The finite pass bound is actual maximum quad coverage, not a fixed cap.
  This implementation still selects over the full viewport; local overlap
  optimization and the remaining volume/material families are not complete.
- Curved projectiles now obtain their depth from the same path sampler as their
  visible position. Palette caches compare effective values instead of transient
  treatment-object identity. Paused panning retains terrain and character buffers.
- Resource owners lease Pixi's shared URL textures. Closing one preview cannot
  unload another scene's textures. This follows the shared-cache behavior in
  [Pixi Assets documentation](https://pixijs.com/8.x/guides/components/assets).
- Play and Studio share pan/zoom/rotation controls. Floor picking intersects known
  support elevations. Actor orientation is presentation data across programs and
  seeks, rather than mutable renderer history. Environment transitions retain
  causal event IDs for reaction shifts; empty attack selectors no longer wildcard.

## Evidence and scope

Browser checks are in NDClient `tools/`. Generated images/results remain ignored
under `.runtime/review/`; native recording JSON remains under `public/recordings/`.

- `world-order-check.mjs`: four cameras, reversed floor insertion order, identical
  pixels; panning does not rebuild terrain.
- `world-support-check.mjs`: raised-door recording, both stair directions in four
  cameras, and the canonical animated-water source. Source pixels were inspected.
- `transparency-check.mjs`: crossing translucent planes remain identical after
  insertion-order reversal. Coplanar red-transparent / green-opaque /
  blue-transparent produces `[0,128,127,255]`, excluding the hidden red layer.
- `studio-check.mjs`: repeated Magic Missile, split Scorching Ray, bow, melee and
  door recordings complete without browser errors.
- `material-cache-check.mjs`: four-actor paused panning retains source count,
  terrain buffers and four character composites. A 40-draw run after the opaque
  owner attachment averaged 2.39 ms including a final GPU completion; submission
  median 2.10 ms, p95 5.5 ms. This is a bounded headless Chromium measurement,
  not all-family or full-game performance acceptance.

Independent read-only reviews found the curve-depth mismatch and transparent
ordering defect, then the coplanar opaque-owner omission. These are repaired and
the crossing/tie cases above exercise their observable result. Resource/facing
changes are undergoing their own bounded review. Full final anti-slop and ECS/DAG
approval remains required for complete delivery.

Full light/material integration, calibrated source geometry, all effect families,
remaining causal playback, editable Studio authoring and the playable interface
remain on the master plan. The Fireball proof is unchanged. No commit was created.
