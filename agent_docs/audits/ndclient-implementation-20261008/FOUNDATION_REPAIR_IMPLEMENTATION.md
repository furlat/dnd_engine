# Foundation positioning repair — implementation checkpoint

8 October 2026. The human resumed A0–A4 and asked to inspect the running app.
This records the bounded repair; it does not close the complete foundation or
NDClient delivery plan. No new screenshot/video gallery was published.

## Confirmed defects and corrections

| Defect | Actual correction and source ownership |
|---|---|
| Resizing left opaque composition at an earlier size, producing a black strip and displaced layers | `render/compositor.ts` refreshes its copy texture/quad with the viewport. Logical CSS sizes and physical depth-buffer dimensions are separate. `render/viewport.ts` handles Pixi 8.22's unchanged-backing-size DPR transition. No world-coordinate compensation. |
| Custom mesh shaders bypassed NeuroClient's pixel-rounding behavior | Material, terrain and ray-media vertices use Pixi's exported `roundPixelsBitGl` and actual render-target resolution. Source sampling remains nearest; the camera remains the original 128×64 orthographic basis, with 64 pixels per height step. |
| Static D1 walls/D6 frames used ideal faces that disagreed with their source art and the registered door leaf | Existing `ImageResourceSource.geometry` now carries the existing `MediaGeometry` union. Source D1/D6 registrations select finite camera-local faces. The shared mesh-depth consumer derives per-pixel depth from registered source UVs. No source alpha is clipped; door depth stays on its existing registered path. |
| Stair rendering invented three solid columns and skipped contact fields | `presentation/terrain.ts` consumes `support_offsets`, per-pose `contacts_px` and cliff `upper_support_offset`/`rise_steps`. The four G17 source surfaces feed the same finite-mesh shader as walls. Edge-on art inherits the nearest finite boundary, without inventing thickness. |
| Raised tiles produced invented lower-floor strips | Removed the blanket lower-earth tiles. Exposed banks come from known support-height differences and registered cliff faces; an unseen neighbor is not treated as an exposed cliff. Intermediate stair supports do not get a full flat floor painted over the flight. |
| Attack arrows used fabricated dimensions/colours | The existing `bolt_style` and native damage palette now drive the arrow shaft/head. Existing action socket, release, trajectory and contact owners are retained. |
| Full source rectangles caused unnecessary transparent passes | Existing resource loading records exact nonzero/fractional-alpha bounds once. Coverage counts use those bounds; faded and explicitly transparent materials use nonzero bounds. Numeric planes and GPU-produced textures retain conservative coverage. Nothing thresholds or removes artwork. |

The Sorcerer/Barbarian and old generic Goblin cosmetic scale overrides were
assistant-added mistakes, not user instructions. Their removal is retained.
This repair introduces no cosmetic actor resizing or changed art perspective.

## Source → export → consumer

| Existing data | Export/consumer |
|---|---|
| Image source path, rect, pivot, scale | Existing presentation catalog → resource frame view → source-local vertex placement. Atlas rect changes sampling, not the image mount. |
| D1/D6 finite faces and G17 source surfaces | `game/data/assets.json` → `ImageResourceSource.geometry` → `render/surface-geometry.ts` → shared `meshDepthGLSL`, used by material and terrain shaders. Authored source-face partitions are triangulated with Pixi's existing earcut export. |
| Door pose offset, frame by physical pose, bank pivots and depth origin/range | Existing environment sampling and registered depth path; no new door-specific offset table. |
| Terrain contacts, support offsets, cliff rise and upper offset | Existing world bindings → `presentation/terrain.ts`; source contact projections are checked before drawing. |
| Native weapon damage and `bolt_style` | Existing attack fact/catalog → delivery colour/style → shared effects renderer. |

The private active catalog is `catalog-063828d25c14a3be5275`. Its new source
metadata reuses unchanged media payloads, including the selected Fireball v4.
No art was regenerated, rescaled, or committed. The accepted separate Fireball
proof was not changed.

## Live references

Studio: `http://127.0.0.1:8791/studio.html#lantern-crypt-authoring.json`.
The area is the existing native Lantern Crypt builder, exported through existing
player-value types by `devtools/export_world_authoring.py`. Its complete
authoring view is labelled explicitly; it is not a private player stream.

The Fantasy A1 door playback uses its source-compatible D1/D6 assembly. Source
assembly evidence is recorded in the asset recovery handoff. The rejected
terraced keep, raised Elegant assembly and unaccepted stair fixtures remain
diagnostic data, not selectable approval examples. This removal is not evidence
that those cases have been repaired.

## Verification

- Eight GPU resize/DPR transitions, including unchanged physical size, matched
  a fresh same-size rendering byte for byte. Opaque and transparent overlap
  remained present in each case.
- Seven current unit checks and the production build passed.
- All 20 selectable recordings were sampled through operation midpoints,
  releases, contacts and endpoints in all four cameras without page/GLSL errors.
  This checks playback availability; it does not certify every frame artistically.
- The four door views and four bow-release views were inspected internally.
  Stair source/consumer review is separate from approving the old stair example.
- Four GPU alpha-coverage cases (opaque, faded parent, forced transparent,
  alpha 1) matched the conservative original pixels exactly. Shared-resource
  teardown and replay seeking checks passed.
- Same complete crypt, 1440×1000 CSS viewport at DPR 1.25: 36→4 transparent
  layers, 72→8 selection/shading submissions; measured headless RAF median
  66.6→16.7 ms. Full-canvas SHA-256 stayed
  `34a6b3e1c9ae605212d8ee49c7e578ee33f22ebe2f07fe03b27992e1e6e4448d`.
  These are measurements on this browser/configuration, not a universal FPS guarantee.

The later explicit `no-premultiply-alpha` setting for numeric mesh textures
corrected their upload interpretation. A controlled browser A/B confirmed that
this changes the crypt pixels; the coverage-only equality above predates that
separate correction. Do not reuse that hash as a final geometry hash. The latest
crypt retained four layers and a 16.7 ms RAF median; pan/zoom/resize retained the
same source count and terrain build count. Final door views were re-inspected
after the numeric-texture correction.

## Review and remaining scope

Anti-slop independently reviewed the viewport/pixel-rounding/attack-style and
Studio source changes: no scoped blocker, with a stale-status documentation
finding corrected in `NDClient/docs/FOUNDATION.md`. That reviewer implemented
the alpha-coverage optimization; its GPU equivalence was checked separately.
Geometry/ECS independently reviewed the consumer implementation (that reviewer
had authored its source geometry and did not independently certify that data).
It found and we corrected dropped `sourcePolygons`: D1/D6 E/W then matched the
reference across 31,410 opaque pixels, maximum error 6.41×10⁻⁸ cells. All four
canonical G17 records produce finite geometry, including the edge-on views.
No scoped consumer blocker remains.

The same review confirmed why the old staircase example remains rejected:
its full upper landing floor extends over the approaching slope. Correct depth
exposes that bad assembly; painter ordering or lowering the actor cannot fix
it. A properly registered landing join is still required before restoring that
example. It is not marked repaired by removing it from the selector.

The complete foundation plan remains open: partial stair shape observation,
general calibrated families, shared picking/cutaway/light geometry, complete
frame readiness and retained-clock/lifecycle work are not claimed complete here.
Nor are full Studio authoring or the playable encounter UI complete. Keep the
existing master plan; this checkpoint is not a replacement plan.
