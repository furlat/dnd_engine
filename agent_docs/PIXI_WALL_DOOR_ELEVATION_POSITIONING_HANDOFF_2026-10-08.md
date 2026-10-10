# PixiJS positioning: adjacency, wall owners, doors and elevation

8 October 2026. Notes requested by the human for production. Source-backed positioning guidance, not a new implementation plan or acceptance of the current NDClient renderer. Read alongside the [foundation repair document](NDCLIENT_FOUNDATION_REPAIR_PLAN_2026-10-08.md) and [October 6 wall audit](audits/WALL_FLOOR_ASSET_ALIGNMENT_AUDIT_2026-10-06.md).

**Construct the physical adjacency and support relationships first. Select the registered artwork that represents those relationships. Project its declared owner/contact, then apply that particular image's pivot and scale.** Screen nudges cannot repair a wrong owner, wrong corner, wrong stair profile or wrong base height.

## The data to use

| Question | Existing authority |
|---|---|
| Which cell owns this object? Which edge? At what height? | Received `PlayerObject.placement`: `position`, `tile_uuid`, `kind`, `boundary_direction`, `base_height_steps`, `top_height_steps`, `orientation`, `covered_supports`, `removed_bands` |
| Which cells are adjacent and walkable, and at which elevation? | Received tile `position`, `elevation_steps`, `surface_kind`, `slope_axis` and native edge/action facts |
| Which straight, corner, frame, terrain or stair resource represents it? | `game/data/world_bindings.json`, exported as `release.world` |
| Where is the contact within a static source image? | `game/data/assets.json`: resource `native_size`, `pivot`, `scale`, optional `rect`; exported as `release.assets.resources` |
| Which door/prop state and animation bank? Which pose registration? | `game/data/environment_art.json`: door/prop binding, bank `rows`, `cell`, `pivots_by_pose`, `scale`, frames and depth registration; exported as `release.environment` |
| What did the imported prefab actually place? | NeuroMapEditor occurrence anchor, `sprite.pivotPx`, `occurrenceOffsetPx`, `scale`, `affine`, provenance and explicit elevation metadata; see references below |

The exporter is `game/presentation_export.py`; the client types are generated from these owners. Consume the selected release, rather than copying measurements into a new TypeScript wall table. Editor-only metadata is not automatically present in the production SDK/catalog.

## 1. Keep map coordinates, height, art pose and screen pixels distinct

This engine's map plane is `(x,y)`, with EAST `(+1,0)`, NORTH `(0,+1)`, WEST `(-1,0)`, SOUTH `(0,-1)`. NDClient currently calls the second plane coordinate `z` and height `h`; that naming does not change the units. In these notes **H is elevation**, not the second map coordinate.

At camera quarter zero, before pan/zoom:

```text
P(x,y,H) = (64*(x-y), 32*(x+y) - 64*H)
one map cell projects to a 128×64 diamond
one elevation step lifts its contact by 64 pixels
```

Rotate the map plane by quarter `q` first, then project and apply height. Quarter rotations of a vector are `(x,y)`, `(-y,x)`, `(-x,-y)`, `(y,-x)`. Python rotates positions around `(31.5,31.5)`; NDClient currently rotates around `(0,0)`. These differ by a camera translation, so compare them with corresponding pan/focus. A changed rotation centre cannot explain a relative gap between adjacent objects when every consumer uses the same transform.

Use one pan/zoom convention consistently. The existing client computes screen contacts with camera zoom/pan and gives the image `sourceScale * zoom`; its parent must not also apply that zoom. Alternatively a world container can own pan/zoom while children use unzoomed coordinates and source scale. Do not combine the two conventions. Canvas device-pixel resolution is not another world-unit multiplier.

**Art suffixes are not literal engine cardinal names.** The source-compatible mapping is:

| Native boundary/orientation | q0 | q1 | q2 | q3 |
|---|---|---|---|---|
| EAST | e | s | w | n |
| NORTH | s | w | n | e |
| WEST | w | n | e | s |
| SOUTH | n | e | s | w |

Use `game/projection.py:camera_pose` / NDClient `presentation/environment.ts:cameraPose`. Native footprint rotation is separate: an east-oriented local footprint rotates to SOUTH as `(dy,-dx)`, WEST as `(-dx,-dy)`, NORTH as `(-dy,dx)`. Never index per-art-pose pivots by the native direction string.

## 2. A wall has both an owner contact and a physical edge

Integer `(x,y)` is a cell centre; its bounds are `x±0.5`, `y±0.5`. A boundary object's declared direction identifies:

| Boundary at owner `(x,y)` | Physical segment | Other incident cell |
|---|---|---|
| EAST | `x+0.5`, from `y-0.5` to `y+0.5` | `(x+1,y)` |
| NORTH | `y+0.5`, from `x-0.5` to `x+0.5` | `(x,y+1)` |
| WEST | `x-0.5`, from `y-0.5` to `y+0.5` | `(x-1,y)` |
| SOUTH | `y-0.5`, from `x-0.5` to `x+0.5` | `(x,y-1)` |

`EAST @ (x,y)` and `WEST @ (x+1,y)` share the same physical edge. They are **not interchangeable image mounts**: these authored walls inset their masonry into the owner cell. The two owner contacts differ by a whole projected cell, `(64,32)` at q0. Rendering from the edge midpoint adds another erroneous half-cell displacement if the registered pivot already expects the owner contact.

Use the native canonical incident-cell pair (`AdjacentEdgeKey`) for edge identity, while retaining owner, direction and vertical span for visual placement. Do not discard the owner when deduplicating physical edges. Multiple actual providers on an edge may also have different spans/roles; preserve their identities.

The real Lantern Crypt correction was:

| Partition | Incorrect owner | Correct owner | Same physical edge |
|---|---|---|---|
| Entry → passage; door at y=6 | `(8,y), WEST` | `(7,y), EAST`, y=5..7 | x=7.5 |
| Entry → vault; door at x=5 | `(x,9), SOUTH` | `(x,8), NORTH`, x=4..7 | y=8.5 |
| Passage → hall | `(12,y), WEST` | unchanged | x=11.5 |

This repaired the native assembly's ownership, without adding renderer offsets. A client must render the received owner; an incorrectly authored owner is repaired at the authoring source, not by silently moving it in Pixi.

## 3. Straight runs, corners and openings follow real adjacency

Match endpoints and vertical spans in world space, not projected alpha rectangles. Collinear neighbors continue a straight run; perpendicular faces need the registered turn for that family. Native straight/corner bindings are `stone_wall_straight` / `stone_wall_corner` and the corresponding wood bindings.

The existing legacy corner representation replaces **two perpendicular wall contributions with the same owner, material and base height** with one composite raster. Its q0 representative directions are:

| Native pair at one owner | Representative passed to `cameraPose` |
|---|---|
| NORTH + EAST | EAST |
| EAST + SOUTH | SOUTH |
| SOUTH + WEST | WEST |
| WEST + NORTH | NORTH |

The Crypt corner is NORTH + EAST at `(7,8)`. Keep both physical faces and provider identities for depth, picking and gameplay even though one D2 image represents them. Do not draw a composite corner on top of the two unmodified straight images. Do not collapse different-height walls, unrelated materials, opposite faces, or a three-way junction into that two-face asset. If extending this to another family, its authored height/profile must actually match the represented faces.

A T junction is not inferred just because sprites share an owner. The audited fixture has EAST at `(5,4)` and `(5,5)`, plus NORTH at `(5,4)`; their segments meet at `(5.5,4.5)`. Its topology has three arms. A registered window parent is another path and does not automatically acquire a legacy D2 corner merely because it meets another wall.

A door occupies its declared boundary segment in the wall run. Its frame, leaf, adjoining wall endpoints and any attachments use that same owner/edge/base. Preserve the opening; a full straight wall behind the doorway closes it visually and physically. Whether the native open door blocks movement/sight comes from its current structural facts, not the visible amount of leaf alpha.

For arbitrary prefab families, choose a join by its actual adjoining faces/profile and authored material compatibility. Matching `E`/`N` names or tint is insufficient. Low dirt banks, rock banks and tall cliffs have different reviewed support footprints and corner semantics.

## 4. Base height is not wall height or the higher neighbor's floor

For an object, mount at **`placement.base_height_steps`**. Its physical vertical interval is `[base_height_steps, top_height_steps)`. For a floor, mount at the received support elevation. `top_height_steps` describes the object's top; it is not its sprite mount.

Native authoring defaults an omitted object base to its owner tile's height (`GridMap` placement validation in `dnd/core/gridmap.py`). An explicit committed base is still authoritative. Do not replace it with zero, add tile elevation to it again, or choose `max(incident floor heights)` on the client. A retaining wall can start lower than the surface it supports; a door on a raised landing starts at that landing's authored base.

For example, a two-step wall/door based at H=2 has top H=4, but its registered contact lifts by **128 pixels**, not 256. Raising its entire supported assembly by one step keeps every XY and adjacency unchanged and subtracts 64 pixels from every corresponding unzoomed contact. Frame and leaf receive the same lift once.

Attached windows/bars must share the parent's owner, boundary direction and base; native placement validation explicitly enforces this. `supported_by_uuid` is an attachment relationship, not an instruction to draw every child at the parent's top height. Use each child's own registered pivot with the shared physical mount.

Large props retain `covered_supports` and their authored footprint/orientation. Do not centre their art by the transparent canvas or derive occupancy from a canopy. Existing placement-registration patches already contain per-art-pose pivots for two-cell props; use the selected registration across intact, moving and wreck frames.

## 5. Cliffs support an upper surface; their lower owner Z does not settle draw order

A cliff is a directed support relationship:

```text
base owner = (x,y,L)
rise = R from the authored profile
supported surface = (x+dx, y+dy, L+R)
physical faces = the profile's oriented downhill faces
```

The current production `terrain_cliff` has `rise_steps=2`, `upper_support_offset=[0,0]`, and explicit straight/corner tables. Thus a registered cliff below an H=4 floor mounts at H=2 at the same XY, while its upper attachment reaches H=4. That is a relationship between two heights, not a reason to put the H=4 floor globally above the cliff raster.

At the rim, preserve the actual cliff faces over the portion of their **own supported upper tile** that overlaps those faces. Preserve cliff feet over the lower floor where their physical surfaces are in front. A neighboring raised tile that is physically in front must still occlude a farther cliff. Resolve these local overlaps with the registered surface/depth/footprint relationship; global “all cliffs last”, “all upper floors last”, and `zIndex = lifted screenY` each fail different views.

When deriving exposed terrain sides from received supports, a known unequal neighbor can establish a rise; an undisclosed neighbor does not establish a lower floor or cliff. The exposed earth strip reported in NDClient came from a blanket lower tile under every raised tile at a disclosure frontier. Copying that lower-bed behavior from the old raster path is not evidence that a real edge exists there.

The cliff `corner_faces` table is its own contract. Currently q0 art `e` represents EAST+SOUTH, `s` NORTH+EAST, `w` WEST+NORTH, `n` SOUTH+WEST. This differs from the legacy wall corner representative mapping. Rotate the declared profile; do not reuse one family's corner table for another.

The editor's reviewed small banks declare a one-step rise, while tall cliffs declare two. Their `elevationBoundary` supplies `downhillFaces`, `supportedSurfaceCellDelta` and sometimes a multi-cell `supportedSurfaceFootprint`. These are explicit semantics; a convex corner can support two cells and a concave corner a single diagonal plateau cell. Filename matching or pretending all corners support the owner loses that distinction.

For a taller exposed column, compatible authored segments must cover the required interval without gaps: e.g. a two-step family spanning H=0..6 uses bases H=0,2,4 at the same physical XY and face orientation. This is authoring/constructor output, not permission for the player client to invent hidden providers or supports. A one-step remainder requires a matching one-step profile; stretching a two-step sprite is not a substitute.

## 6. Stairs are authored traversal contacts, not flat floor copies

The current production stair profile is a **whole two-step flight**, not one sprite per arbitrary positive height difference:

```json
"rise_steps": 2,
"support_offsets": [[0,0,0], [-1,0,1], [-2,0,2]]
```

Its canonical example ascends west: lower `(x,y,L)`, middle `(x-1,y,L+1)`, upper `(x-2,y,L+2)`, with downhill direction EAST. Rotate that actual support pattern for the other directions and camera poses. Match the received stair surface kind, slope axis and elevations before choosing the flight. Do not fabricate a flight from proximity alone.

`contacts_px[pose]` are source-local points corresponding to those support contacts. The current registration is:

| Art pose | Lower contact / pivot | Middle contact | Upper contact |
|---|---|---|---|
| e | (160,224) | (96,128) | (32,32) |
| s | (96,224) | (160,128) | (224,32) |
| w | (96,192) | (160,160) | (224,128) |
| n | (160,192) | (96,160) | (32,128) |

For each contact i, the placement identity is:

```text
P(lower) + sourceScale * (contacts_px[pose][i] - image.pivot)
    = P(the corresponding native support)
```

At q0 for the westward ascent, the contact displacements are `(0,0)`, `(-64,-96)`, `(-128,-192)`. This checks the stair XY and elevation together, independent of visual taste. Apply zoom/pan to both sides consistently. The contact points also describe the receiving/support surfaces; a shader's arbitrary three equal columns do not.

Keep the lower entry and upper landing's support identity. The flight artwork represents the intermediate slope; an ordinary full flat tile at its middle height can hide a tread or manufacture a floating floor. Support identity does not require duplicating a floor raster for every contact.

In the imported prefab study, G16 is the edge lane and G17 continues **width**. Adjacent lanes share lower/upper height; they do not stack their lift. The editor's explicit `elevationTraversal.contacts` distinguishes entry, midpoint, top-stair and supported-surface points, including Q4 corner contacts. That richer occurrence contract is not identical to the production three-cell flight above; adapt by the source profile, not a G16/G17 filename heuristic or duplicate G16 workaround.

A stair opening covers its actual traversal part of a raised perimeter. Its exposed side returns still need the appropriate wall/cliff pieces. In the arena constructor, every raised perimeter must close through validated boundary pieces and stair interfaces before adding the next terrace; a stair does not automatically close its sides. This is an authoring invariant, not a reason to hide a player's partially disclosed upper floor.

## 7. Apply the selected registration exactly once

For source-frame point `u`, pivot `p`, source scale `s`, and projected contact `C`, the image mapping before camera zoom is:

```text
image point = C + s*(u-p)
full source image top-left = C - s*p
```

For a normal untrimmed Pixi Sprite in the existing screen-position convention:

```ts
// Texture is a view of the selected full source cell, not the entire atlas.
sprite.texture = frameTexture;
sprite.anchor.set(0, 0);
sprite.pivot.set(pivot[0], pivot[1]); // source pixels, not normalized fractions
sprite.scale.set(sourceScale * camera.zoom);
sprite.position.set(...project(x, y, placement.base_height_steps, camera));
```

The current custom material mesh uses source-cell local coordinates and the same pivot/scale/position arithmetic; `anchor` is Sprite-specific. Do not subtract the pivot again from `position`, bottom-align by alpha bounds, set `width=128`, or apply the character rig's separate scale to environment images. Setting a Sprite's width/height changes its scale, including on subsequent texture changes. See the [official Sprite guide](https://pixijs.com/8.x/guides/components/scene-objects/sprite).

Current source examples, inspected on October 8:

| Registration | Full source cell | Pivot | Source scale |
|---|---|---|---|
| Legacy stone D1 straight, D2 corner, D6 frame | 256×256 | (128,207.36) | 128/127 |
| Stone ground D1 | 256×256 | (128,208) | 1 |
| Fantasy A1 opening bank | 256×256 | (128,209.92), each current pose | 128/127 |
| Indoor Elegant outward opening bank | 256×256 | e (100,198), s (156,198), w (156,226), n (100,226) | 128/127 |
| Fixed fantasy window/solid sibling banks | 320×320 | (160,240) | 1 |
| Current G17 flight | 256×256 | its pose-specific lower contact above | 1 |

These examples explain the data; they are not replacement defaults. In particular, **do not use a universal (128,208) door pivot**. The earlier October 6 snapshot and a newly selected release may contain different registrations; always inspect the active bank.

The fixed 320×320 banks pad the original 256×256 art at `(32,32)`. Pivot `(160,240)` therefore keeps the original content contact equivalent to `(128,208)`. Legacy D1 uses a different scale/pivot even where its raw original matches the fixed D1 content. Do not strip that padding or force both registrations to agree without source evidence.

Atlas `rect=[atlasX,atlasY,width,height]` selects UVs, not world placement. Current static and environment packed regions preserve the full source-cell dimensions; their pivots remain frame-local. If another family is genuinely trimmed, preserve original dimensions and its source-local trim offset: with a cropped quad, local pixel `u` means full-source point `u+trimOffset`. Pixi's `orig`/`trim` representation can already perform that mapping; do not add the trim twice. Atlas X/Y is never the trim offset. See the [official texture guide](https://pixijs.com/8.x/guides/components/textures).

Colour, depth, normals, aperture/selection masks and sockets must share the same frame-to-source mapping, pose and world mount. `ground_origins_by_pose` calibrates depth independently of the mounting pivot; it must not replace `pivots_by_pose`. Decode the declared depth encoding/range/pixels-per-unit once rather than treating every companion as a generic normalized image.

### Door pose offset: use its inverse, and keep the frame on the physical edge

For a door, first calculate physical art pose from its native boundary and camera. In clockwise art order `[e,s,w,n]`:

```text
bankPose = poses[(index(physicalPose) - door.pose_offset + 4) % 4]
frameResource = door.frame_resource_by_pose[physicalPose]
bankPivot = selectedBank.pivots_by_pose[bankPose]
```

Fantasy C1 and C3 have `pose_offset=1`. Thus EAST at q0 selects physical frame pose `e`, but animated source-bank pose `n`. Picking both from `e` detaches/misorients the leaf. Both still mount at the same owner/base. If a bank contains its own static frame regions instead of an external frame resource, use that bank's recorded source pose and registration. Opening, closing, destruction and settled wreck retain their selected bank registration; do not introduce a per-state screen shift.

### Imported prefab offsets are a separate, explicit data path

NeuroMapEditor's `SpritePresentation` preserves `pivotPx`, `occurrenceOffsetPx`, source `scale`, and an optional Pixi/Y-down affine. Its current arithmetic is:

```text
mapPixel(u) = P(anchor,H) + occurrenceOffsetPx + affine.translationPx
             + affine.linear * (scale*(u-pivotPx))
screenPixel(u) = pan + zoom*mapPixel(u)
```

The occurrence offset is a post-projection pixel vector in that representation, not a cell delta, not automatically multiplied by source scale, and not a freely tuned per-camera nudge. Geometry offsets such as `supportedSurfaceCellDelta` are instead **world-cell vectors**: resolve them in world coordinates before projection. Q4 points use four units per macro cell. Keep these units explicit.

When migrating a Unity source occurrence to a reviewed physical owner, preserve provenance and apply the recorded normalization once. The editor's cliff/bank owner rebases and pixel-preserving height reassignment are ingestion/authoring conversions, not additional renderer offsets for already committed production XYZ. Repeating them changes ownership again. Do not copy an older editor suffix/direction table into the engine: use the current explicit geometry deltas and the engine cardinal convention above.

## 8. Placement correctness and overlap correctness are separate checks

An image can be perfectly mounted and still be covered by the wrong neighbor. Sprite insertion order, global Z layers or a single `screenY` key cannot reconstruct a tall wall's varying surface depth. The current basis has ray-null direction `(1,1,1)` in `(x,y,H)`: `P(x+1,y+1,H+1)=P(x,y,H)`. Identical screen pixels therefore do not imply identical physical positions or height.

Mount using owner/pivot; reconstruct depth from calibrated physical surfaces and the selected depth data. Boundary midpoint/endpoints are for the actual edge relationship, not a substitute sprite anchor. Corners carry both real faces. Use local role/stable-ID ties only for genuinely coincident surfaces. Drawing a door last may conceal a detached mount in one view while clipping it in another.

The existing static wall registrations currently provide pixels/pivot/scale but not a complete calibrated 3D wall mesh; animated banks can also have empty optional surface geometry. The [post-stop review](audits/ndclient-implementation-20261008/REVIEW_AFTER_USER_STOP.md) specifically found ideal zero-thickness wall substitutes in depth and lighting. A measured pivot is not proof of wall thickness, aperture shape or physical top height. Where that geometry is absent, record the missing calibration at its existing source owner; do not derive a fictitious universal wall volume from its PNG rectangle.

Draw, picking/highlights, receiving surfaces and cosmetic lighting must consume the same derived registered sample/geometry. The window target mask selects the window object; its aperture mask identifies the opening; neither is automatically the full wall's collision footprint. Native movement, crawl/climb and attack eligibility still come from the received mechanics.

## 9. Practical diagnosis using the existing fixtures

For an offending wall/door, expose its native owner, incident cells, boundary endpoints, base/top heights, support IDs, selected resource/bank, physical/source poses, pivot, scale, source cell, frame rect and reconstructed depth origin. Overlay the owner contact, physical edge and authored stair/attachment contacts on the unchanged artwork.

Compare without depth composition first. A wrong contact/pose there is placement/selection; correct placement that becomes detached or hidden when depth returns is a depth/composition question. The reported raised Indoor Elegant door's exact root cause remains unproven: current export and client retain/read its per-pose pivots, scale and depth fields. Do not assert that an ignored pivot caused it without this comparison.

Use the existing Crypt, raised door and three-support stair recordings, plus the four-view October 6 gallery. Useful concrete checks are:

1. Adjacent run endpoints coincide at the same physical height in all four cameras; the Crypt two partitions use the corrected owners above.
2. Frame and leaf remain on the same boundary before/during/after opening and destruction, including a nonzero `pose_offset` door and the raised Indoor Elegant case.
3. Changing an entire assembly's base by one step shifts each contact by `(0,-64*zoom)` without changing XY, corners or support IDs.
4. Every flight's source contact reprojects onto its native lower/middle/upper support, in all cameras; parallel lanes increase width without increasing rise.
5. The floor at a cliff's upper support preserves its rim, the lower floor preserves its foot, and an unrelated foreground surface remains in front. Check these relations together rather than globally changing a layer.
6. A known platform continuing into undisclosed space gains no invented cliff or exposed blanket earth tile. An authoring constructor, separately, rejects a genuinely open required perimeter.

These are geometric checks for the reported failures, not a new screenshot quota or claim that all families are already certified. October 6 preservation/native receipts are historical evidence; this document makes no new runtime acceptance claim.

Documentation arithmetic checked against the current JSON and `game.projection`: all 16 native-direction/camera pose cases matched; all 48 stair contact comparisons (four directions × four cameras × three contacts) had zero pixel error; all 16 one-step assembly-lift comparisons were exactly `(0,-64)` before zoom. The listed current cliff, C1 pose-offset and Indoor Elegant pivot examples also matched their catalog records. These checks verify the notes' arithmetic, not the current Pixi scene output.

## Saved references

Production root: `/mnt/c/Users/tommaso/Documents/Dev/dnd_engine/`. Current Pixi client: `/home/tommaso/Dev/NDClient/` (PixiJS 8.22.0). The following remain durable on disk:

- [Wall/door/floor ownership handoff](WALL_FLOOR_ASSET_ALIGNMENT_HANDOFF_2026-10-06.md) and [machine-readable registration audit](audits/WALL_FLOOR_ASSET_ALIGNMENT_AUDIT_2026-10-06.json).
- Engine sources: `dnd/types/world_placement.py`, `dnd/core/gridmap.py`, `dnd/core/world_edges.py`; `game/projection.py`, `game/environment_draw.py`, `game/app.py`, `game/asset_types.py`, `game/world_binding_types.py`, `game/environment_art.py`.
- Client consumers: `/home/tommaso/Dev/NDClient/src/math/isometric.ts`, `src/presentation/environment.ts`, `src/presentation/terrain.ts`, `src/render/environment.ts`, `src/render/terrain.ts`, `src/render/resources.ts`. These show current consumption, not proof it is correct.
- Prefab/editor occurrence and elevation contracts: `/home/tommaso/Dev/NeuroMapEditor/src/model/types.ts`, `src/model/lattice.ts`, `src/render/spritePresentation.ts`, `docs/PHASE_ONE_IMPLEMENTATION_RECORD.md`, `docs/WESTERN_MULTI_HEIGHT_VERTICAL_COMPLETION_STUDY.md`. Read the implementation record/current explicit metadata when older study documents differ.
- Arena adjacency/perimeter rules: `/mnt/c/Users/tommaso/Documents/assets/arena-study/prototype-v1/grid-kit/constructor/RULES.md`; current selection in `DELIVERY.json`. Its `placement-contract.json`, `adjacency.json` and `game-data.json` retain physical contacts, profiles and support ownership. This validates that arena family; it does not declare unrelated source families interchangeable.
- Existing large-prop pivot/footprint work: `/mnt/c/Users/tommaso/Documents/assets/environment-production-audit/placement-registration-53/HANDOFF.txt` and its recorded patches/actual-projection validation.

Scope reminder for the earlier animation confusion: `environment.directional_wall` and legacy D2 retain static intact registrations; a window parent/insert uses its own approved destruction bank. The October 8 [wall completion handoff](WALL_BREAKABILITY_PIXI_HANDOFF_2026-10-08.md) now registers existing source debris for the generic stone/wood walls and seven solid siblings. Intact banks remain one frame; finite lethal debris is separate. Do not choose a window-wall animation to make a solid/corner wall “animated”, change its silhouette, or regenerate already delivered break artwork. Pygame is off; Pixi consumption and browser acceptance remain outstanding.
