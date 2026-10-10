# Fireball: actual depth, normals and light proof

Date: 8 October 2026. Engine reference `804b0f7e073c658b52609a8926dc98e5dffd79a3`.
This receipt separates the original **v1** measurements from later v3 reach
experiments and the currently selected **v4** hookup. The human accepted the current
v4 demo as a useful baseline; this does not close general-map or production work.
The selected asset is pinned in the [handoff](../../FIREBALL_SINGLE_VIEW_PIXI_HANDOFF_2026-10-08.md#current-default-delivery--v4-selected-8-october-2026).
The master remains [NDClient implementation](../../NDCLIENT_IMPLEMENTATION_PLAN_2026-10-08.md).

## October 8 — v4 and the two-room reach example

Current preview: `http://127.0.0.1:8790/?scene=solid&review=fireball-v4`.
The selector also offers the open doorway and original layout; **Wall reach**
compares region clipping while retaining camera occlusion. The original layout
has no added reach inference. The current user acceptance is of this bounded
visual baseline, not of a general region compiler or all remaining N−1 cases.

* `export-reach-cases.py` bakes the native `connected_propagation_positions` result
  for 132 possible cast cells in each straight-wall layout. It checks exact
  equivalence of each footprint and its two room permissions. There are **264**
  verified footprints. This invokes the query Fireball uses, not a full spell
  command or a replayed subjective cast. Full native propagation/breach tests
  were separately run during the preceding investigation: **19 passed**.
* Starting cast: solid wall **36** cells, open doorway **49**. Offline objective
  fixtures are explicit. No Python/rules engine runs in the browser.
* `reach.js` maps room permission to the actual stone-face X bounds; `shaders.js`
  reconstructs each represented world point and checks those bounds, finite stone
  boxes and scene depth separately. No per-tile image stencil, source-ray wedge,
  extra texture or extra rendering pass was added.
* **v3 reach-example playback**, 1440×1000 Chromium/ANGLE RTX 5090:
  solid-wall p95 **16.7 ms**, doorway p95 **16.8 ms**, zero buffering in each
  observed single cast; no page/console errors. `reach-review/playback.json`
  stores these results. These short local observations exclude initial setup and
  are not v4 measurements, cold-start guarantees or concurrent-cast acceptance.
  Terminal GPU/CPU/pass counters were taken after expiry and are not active-cost
  evidence. On/off screenshots in four cameras are in `reach-review/`.
* **v4 asset hookup:** 46 frames at 24 FPS, **1.916667 s**, 184 runtime files,
  **26,675,421 compressed bytes**. All paired-plane compressed/decoded hashes and
  lengths passed. The browser submitted all 46 frames in sequence, expired the
  effect correctly, had no page/HTTP errors and no buffering in one cast. All 185
  media requests (manifest plus planes) used v4. Four-camera solid/doorway captures
  and `check-v4.mjs` results are in `v4-review/`; this is not a fresh performance
  benchmark or a numeric proof of every depth intersection.

V4 retains v3's appearance and geometry for its selected frames. It removes two
small-ignition frames and retimes the fitted light curve together with playback:
peak .44 s, faint tail at 1.64375 s, end 1.916667 s. The original six-frame ignition
becomes four frames. Sampler, prefetch and retirement now use the manifest's FPS,
frame count and duration. No wall/depth/material algorithm changed for the hookup.

**Scope limits:** two otherwise empty rooms divided by a straight wall permit an
exact one-axis region reduction. This is 2D reach extruded vertically; it does not
model over-wall flow or pressure/advection, nor arbitrarily shaped rooms. The
subjective stream's omitted cells still cannot authorize exclusions. General
region evidence/compilation, low/finite/L walls, destruction stages, Globe/Antimagic
and combined/performance cases are the concrete work in
[occlusion §1.1](../../NDCLIENT_OCCLUSION_MATH_AND_PIXI_2026-10-08.md#11-native-reach-to-continuous-render-regions).
Two representative depth bands and approximate stone geometry remain limitations.

Current example fingerprints (private files; no artwork committed):

| Relative to `.runtime/ndclient-fireball-proof/` | SHA-256 |
|---|---|
| `export-reach-cases.py` | `8ac893921523a800d0768752d4f2d7a04979815fcb0b78980a65c69ee269806f` |
| `reach-cases.json` | `085287b046081ce555b70164d5925c3ba59787cfa0ed894c3f0ea8cf401a28cc` |
| `reach.js` | `4bd0ceaa6b567253f6230340dd948aa8db6fb725e8b8c045654769833efc5153` |
| `shaders.js` | `934580bf46901cded51686bd5756c96abfae8600fe032e01c1a1d361b53f1e2f` |
| `renderer.js` | `f86a82d6260f87097956de19e2051b9e07c46c4e4413b31fa9b7122c62caa7e8` |
| `main.js` | `21fe4c8e1d54357f3d32dea756099e6ee911acb6cf52413aa8ebb01e06f2c579` |
| `scene.js` | `01c373cd83a9109b392231cd0894465434134fd5a540d2c5f638295dcfaaf9d4` |
| `frames.js` | `aa5c8baa435820ebd49b12fb79500cae24dc805d5d9a9191b97488767a546b49` |
| `reach-review/playback.json` | `b4a20761404b23dbc3b5a3b7f63a499eec6a44d5e4509e3cbd98f70250bb8f39` |
| `v4-review/result.json` | `4ddc3748390a0fc67e8ef241dcb5d7f0b3afecd1a0320a2934073767483a92ee` |
| `media/fireball-single-view-24fps-v4/manifest.json` | `192fa78c65c8cc1f574a317d64f78663898dbe49e0078b8ce756e8b3cc703061` |

## Historical v1 evidence

All following measurements, original limitations and fingerprints describe v1.
The later bounded acceptance above supersedes the corresponding simple-room
wall/ignition status; it does not silently reattribute these measurements to v4.

## Delivered scope

`dnd_engine/.runtime/ndclient-fireball-proof/` runs PixiJS 8.22.0/WebGL2 at
`http://127.0.0.1:8790/`. It has real Fantasy H1 floors, D1 wall sprites and stone
arch frames, mouse placement, four camera rotations, light/bloom/normal/depth
controls and a **Receive light** comparison. Scene placements and warm/cool lights
are synthetic. There is no engine, SDK, gameplay, production Studio or Globe in
this demo. Source provenance is in `environment-selection.json` and the export.

The delivered single-view export has 48 frames at 24 FPS over two seconds, two
true depth bands, and paired RGBA8 appearance and packed depth/normal data per
band. Transfer is 33,347,140 compressed bytes (31.80 MiB); all decoded frames
total 531,842,064 bytes (507.20 MiB), **not simultaneously resident**. The proof
uses bounded loading/worker decode and retained paired-frame resources. It does
not restore the old multi-view XYZ banks or import separate smoke captures.

## What now works, and what it establishes

| Evidence | Result | Limit |
|---|---|---|
| `check-depth-order.mjs`, `wall-depth-review/depth-order-result.json` | 12/12 front/behind/doorway sampled outcomes across four camera quadrants; no page errors | This is a known-depth diagnostic plane through the real draw path, not 12 complete Fireball-contact tests |
| `check-wall-depth.mjs`, `wall-depth-review/` | Actual source artwork and Fireball captured from four views; normal/depth registration corrected | Regular wall proxy, not exact per-stone geometry; other wall banks still need registration checks |
| Projection algebra | Pixel-to-ray-to-host reprojection matches the original pixel/pivot; depth direction projects to zero | Correct transform does not make representative translucent depth exact |
| `check-effect-light.mjs`, `effect-light-review/` | Whole effect receives light via existing normals/position and retains emitted appearance; colour comparisons at 0.2/0.8/1.6 s | Authored neutral reflectance, not recovered albedo or volumetric scattering |
| `effect-light-review/comparison.json` | Lit comparisons brighten without any negative channel delta; no-light and normals-debug pairs are pixel-identical with receiving toggled | Tests additive-response invariants on these captures, not all future materials |
| Source/pass inspection | Shared direct-light functions for world/effect; no texture or extra pass added for receiving light | Overall composition still requires several passes and more work for crossing transparency |

Wall correction: asset-specific inner-quarter-cell faces (0.25 thickness, height 2)
replace the initial wrongly centred proxy. Connected collinear walls share receiving
surfaces, removing artificial internal end-face normals. The arch keeps its own
frame/aperture; light blockers leave the opening free. Original alpha retains the
stones' silhouette. These measurements belong in environment registration rather
than hardcoded global wall dimensions.

Material decision: all Fireball pixels may receive light while retaining the
delivered combined radiance. The demo authors neutral diffuse reflectance 0.18;
the existing opacity/additive radiance estimates coverage. Its independent emitted
point-light curve peaks at 0.22 s, reaches relative intensity 0.04 at 1.6 s, and
ends at 2 s. The exporter labels that curve fitted visual authoring. The demo's
intensity multiplier of four is scene calibration. No claim of recovered light
energy, smoke-only masks or native gameplay illumination is made.

The production equations, source-field roles and reuse boundaries are in
[lighting §4.1](../../NDCLIENT_DEPTH_MATERIAL_LIGHTING_2026-10-08.md#41-proven-emitting-and-receiving-material).
They preserve depth ordering, receiving light, visual emission and neighbour-light
curves as distinct operations using shared geometry and finite shader functions.

## Recorded playback observations

`measure.mjs` / `measurements.json`: local Playwright Chromium at 1920×1080,
ANGLE reports D3D12 NVIDIA GeForce RTX 5090. The raw script saves cumulative
session arrays of 125, 260 and 538 samples. The table below separates them using
suffixes `[15:125]`, `[125:260]` and `[260:538]` (only the first interval drops the
initial 15 samples). Buffering is the difference between cumulative snapshots.
These are not full cold-start percentiles, native Windows browser certification
or an isolated GPU-cost result. This correction uses saved data, not a new run.

| Workload | p95 / p99 / max frame interval | Playback buffering |
|---|---|---|
| One cast | 16.7 / 16.8 / 16.8 ms | 0 ms |
| Repeated cast | 16.8 / 16.8 / 16.8 ms | 0 ms |
| Four distinct-age casts | 16.8 / 33.4 / 50.0 ms | 1,866.6 ms |

The session-wide high-water marks reported after each scenario stay about
128 MiB of effect payload separately in CPU and GPU residency; these are not
independent scenario peaks. Pixi retains raw upload buffers. Render targets add 132,710,400 bytes
(126.56 MiB) at this viewport, excluding ordinary environment textures. No page
errors were recorded. Terminal GPU stats were sampled after effects expired and
must **not** be quoted as active-Fireball GPU timing. Four-cast buffering remains
an open delivery/working-set problem despite mostly responsive UI frames.

## Remaining work and rejected approach

1. **Natural wall contact is not solved.** Camera depth orders the effect and wall,
   but does not reshape the explosion against a barrier. An origin-to-fragment
   blocker erased angular sectors and doorway cones; the human rejected it and
   it was removed. Do not substitute tile masks, ray-shadow wedges or softened
   versions of that same cutout. Light-ray tests affect received light only.
2. **Opening pop/export limitations.** Original frames expand abruptly and drop
   central radiance; the [opening handoff](../../FIREBALL_OPENING_REPAIR_HANDOFF_2026-10-08.md)
   records the issue. The client fixes initial skipped samples, not missing source
   motion. The improved asset is a later release replacement, not a reason to stop
   geometry/material/resource work. Retain existing band/fringe-depth limitations.
3. **Remaining N−1 coverage.** Existing Globe and Antimagic cases, other volumes,
   elevated actors, blood/ground/deposits and combined stress scenes are unproven.
   Fix the measured four-cast stalls without silently dropping frames/casts.
4. **Production migration.** Author source fields in the existing media/material/
   environment owners, integrate shared functions once, apply displayed audience
   lighting policy and build the client/Studio. No magic six-light limit, 24-box
   demo limit, global wall dimensions or two-second hardcode belongs in production.
   Compile admitted light/blocker lists per relevant scene change and use measured
   local culling/batching; do not silently discard excess gameplay emitters.

## Evidence fingerprints

These bind the ignored proof to this receipt. N0's explicit private snapshot/copy
runbook preserves source, small receipts and selected media before migration.
The public report contains no artwork or large recordings.

| Relative to `.runtime/ndclient-fireball-proof/` | SHA-256 |
|---|---|
| `renderer.js` | `36fafe228af7af1e4735e411339d14fadce3e14022aeea93fc361f39b90682bd` |
| `shaders.js` | `a33f7cb6b82e4cb0414e2bac5a64dfca2907d4c729bf032b08f5a8dcd4271b7b` |
| `scene.js` | `b0b62c23b8ed2aef20282591a527f6d11aa002aa7a4461e17fc48fef0dc0ac3a` |
| `export/manifest.json` | `7de6a7241208186c6bb8fa41befd1e087a0de775065d357bcf0e3eaabb87e7d8` |
| `measurements.json` | `6f520b9ae39a64e94202d3a520f2088a9cd27d23bcaf4492fe2f54087b339994` |
| `wall-depth-review/depth-order-result.json` | `5a14b4d2156bb96b2548a10f5139133dc13da11525f3b4b65fa32cd05cab1b9e` |
| `effect-light-review/comparison.json` | `44981c64621118c0ae2405e423352263e0d3dbb90d50510be5180405cec5c8ce` |

Independent review of this reconciliation is recorded in
[PLAN_REVIEWS.md](PLAN_REVIEWS.md), separately from earlier plan approvals.
