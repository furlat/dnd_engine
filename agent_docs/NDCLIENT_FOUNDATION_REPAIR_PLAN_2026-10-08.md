# NDClient foundation repair

8 October 2026, later resumption. **The human has restarted foundation repair.**
The next chunk is A0–A4: source-compatible assemblies and their shared positioning
path. Present current results in the running app. Do not build new screenshot or
video galleries for the human; existing event recordings remain Studio inputs.
Current code/evidence is recorded in the
[implementation checkpoint](audits/ndclient-implementation-20261008/FOUNDATION_REPAIR_IMPLEMENTATION.md).
The defect table below describes the repair baseline, not a claim that every
listed defect remains unchanged. The checkpoint does not close A–E.

**The earlier implementation-ready verdict is withdrawn.** Source-family
compatibility, complete authored assemblies and actual reference-renderer parity
were not established. The earlier halt led to the
[asset recovery handoff](NDCLIENT_ENVIRONMENT_ASSET_RECOVERY_HANDOFF_2026-10-08.md),
which continues to govern resumed asset selection. The newly assembled terraced keep is
rejected; its closed topology does not certify compatible artwork.

**Positioning correction, incorporated later October 8:** the animated-wall
author's [notes](PIXI_WALL_DOOR_ELEVATION_POSITIONING_HANDOFF_2026-10-08.md) supply
the owner/edge, directional pose, corner, height, stair-contact and registration
rules below. They correct missing specificity in this plan; they do not establish
the rejected assets' compatibility or certify the client. Prior review verdicts
do not cover this amendment. The human's restart does not certify the current renderer.

This is the immediate repair phase of the [master plan](NDCLIENT_IMPLEMENTATION_PLAN_2026-10-08.md), before its wider content, Studio and playable-UI work resumes. It repairs the existing NDClient in place. It does not replace the master, authorize another demonstration client, or claim that copied assets are implemented features.

The objective is a trustworthy shared world renderer and playback lifecycle: authored floors, stairs, walls, doors, props and actors occupy the correct places in every camera; resources and time cannot desynchronize the scene; Play and Studio use the same result. The user's artwork and registrations are the source of truth. Unsupported data must not be silently replaced with convenient geometry.

The [post-stop review](audits/ndclient-implementation-20261008/REVIEW_AFTER_USER_STOP.md) records the current implementation defects. The [plan review receipt](audits/ndclient-implementation-20261008/FOUNDATION_PLAN_REVIEWS.md) records independent anti-slop and anti-OOP/ECS review of this repair design. Neither is runtime acceptance.

## 1. What failed, and what is still intact

| Finding | Evidence and consequence | Repair owner |
|---|---|---|
| Asset compatibility was never established | The rejected map independently paired generic D1/D2 stone walls with the generated-interior Elegant door. A closed native room and valid individual pivots cannot certify that assembly. | Existing source assemblies/adjacency and authoring selection, before renderer repair |
| Raised ground shows an exposed earth strip | `presentation/terrain.ts` inserts a whole lower tile for each raised tile, even where no disclosed physical edge exists. In the reported fixture the platform continues beyond the disclosed x=5 frontier through x=8. Closing that frontier with an invented cliff would conceal the original mistake. | Terrain selection and registered receiving geometry |
| Door appears detached | The screenshots establish the defect. They do **not** establish whether the cause is pose selection, registration, depth decoding or composition. Per-pose pivots, scale, packed frames and depth calibration survived export and are read by the client. | Environment sample → registered frame → depth/composition trace |
| Static walls use invented ideal faces | `render/world-depth.ts:boundaryDepth` and `presentation/lighting.ts` independently substitute ideal/zero-thickness boundaries. Actual authored thickness and apertures are not carried through. | One derived surface description shared by rendering, picking and visual lighting |
| Stair and cliff fields are bypassed | `contacts_px` and `upper_support_offset` are exported but not consumed; any positive drop becomes one two-step cliff; shader layout assumes three columns instead of the registered contact geometry. | Terrain authoring adapter and existing finite geometry renderer |
| Newly revealed assets may be unavailable | Scene preparation largely inspects the before state; readiness covers effects only. A later presented state can request an unprepared page. | Existing scene/resources preparation |
| Animation uses competing clocks | Live `visualTime` advances while operation playback buffers; environment/water receive operation-local time; actors receive another clock. | Existing playback sampler and its two hosts |
| Audience changes retain stale output/work | Old pixels survive connection failure; an earlier asynchronous preparation can install after switching scope. | Existing app/session lifecycle and scene teardown |
| Actor sizing and equipment need correction | Unsupported cosmetic source overrides existed; partial source edits removed some but are not an approved general sizing policy. Cast `hidden` currently hides the offhand as well as the main weapon. | Existing appearance producers and actor composition |
| Checks did not prove the claimed behavior | Raised/stair screenshot tools mainly detect browser errors, not correct placement. Current images fail visual review. | Replace those acceptance claims and strengthen those same checks |

Read-only comparison found no changed or missing source fields from `game/data/assets.json`, `game/data/world_bindings.json` or `game/data/environment_art.json` in the active release, and those source documents matched Git HEAD. This establishes preservation of those documents, **not** correct use of them or verification of every external delivery.

Useful implementation remains: the delivered SDK/server, subjective reducer, raw recording intake, source export, private asset copy, URL resource leases, retained motion/facing sampling and accepted Fireball depth/light work. Keep these owners. Do not rebuild the transport, schema hierarchy or client repository.

## 2. Existing sources and the exact boundaries

Client root: `/home/tommaso/Dev/NDClient`, branch `codex/ndclient`.
Engine/source-authoring root: `/mnt/c/users/tommaso/documents/dev/dnd_engine`.
Assets, generated recordings and browser evidence remain Git-ignored. Preserve both existing catalog releases and the accepted standalone Fireball proof. No repository creation, asset recopy or wholesale repacking is needed for this repair.

| Source | Use during this repair |
|---|---|
| [Animated-wall author's positioning notes](PIXI_WALL_DOOR_ELEVATION_POSITIONING_HANDOFF_2026-10-08.md) | Exact owner/edge and art-pose distinctions, frame/leaf pose offset, corners, height, stair contacts, packing/occurrence units and diagnostic procedure. Its arithmetic checks are not runtime acceptance. |
| `game/data/assets.json`, `world_bindings.json`, `environment_art.json`; their existing Python types/exporter | Canonical image/frame coordinates, pivots, scales, terrain contacts, environmental poses, transition/depth data and appearance inputs |
| `game/environment_draw.py`, terrain/environment code in `game/app.py` | Cross-check source-frame placement and calibration arithmetic; do not port CPU raster/depth algorithms or assume every historical behavior was correct |
| `/home/tommaso/Dev/NeuroMapEditor/src/model/{types,lattice}.ts`, `src/render/{orderPhaseOne,spritePresentation,alphaPicking}.ts`, `docs/PHASE_ONE_IMPLEMENTATION_RECORD.md` | Distinguish grid identity, visual composition and image calibration; recover compatible projection/picking functions. The implementation record supersedes the older README's objects/roofs deferral. |
| `/mnt/c/Users/tommaso/Documents/assets/environment-production-audit/placement-registration-53/` | Existing table/large-prop placement decisions, all camera/native-orientation combinations, original-pixel preservation and allowed decorative overhang |
| `/mnt/c/Users/tommaso/Documents/assets/arena-study/prototype-v1/grid-kit/` and `constructor/{RULES.md,DELIVERY.json}` | Measured pivots, integer XYZ pieces, actual adjoining faces, support/contact and closed-platform examples. Read the current delivery selection, not an archived arena variant. This is reference evidence, not a new arena-import task. |
| Preserved NeuroClient reference under `/home/tommaso/Dev/ndclient-reference/2026-10-08/NeuroClient/source/app/src` | Existing useful camera/grid/resource behavior; no resurrection of its old state or server architecture |
| `.runtime/ndclient-fireball-proof/{scene,renderer,shaders}.js` in the engine | Accepted registered D1 wall/arch and Fireball reconstruction math. Its wall measurements belong to those assets, not every wall family. |

### Multi-Z: preserve the distinction rather than inventing engine state

The current engine uses one `WorldTileState` support per XY cell, with `elevation_steps` and slope data. The client reducer faithfully has that same limitation. Ground/flying occupancy is not a stacked-floor identifier. NeuroMapEditor's independently named Z-grids are a richer **editing** model, not fields already delivered by the current SDK.

The renderer must nevertheless support multiple **visual pieces** at different heights over the same XY: floor tops, actual risers, stair surfaces, doors, props, bodies, shadows and effects. They keep separate source registration, support contact, physical surface/depth and composition identity. Do not flatten those pieces into one screen-Y value or make Z-grid labels the painter order.

This repair correctly renders the engine's existing raised/sloped maps. It neither fabricates a second walkable floor at the same XY nor expands backend pathfinding, perception and protocol into stacked-floor gameplay. That broader capability remains an explicit future design decision. Do not copy the editor's inferred-height rules into authoritative player state.

### One directional dependency chain

`SDK facts + canonical authoring → pure presentation samples/geometry → Pixi draws, picking and visual light inputs → host UI`

`src/math/` owns coordinate transforms; `src/player/` owns received state; `src/presentation/` owns pure derivation and sampling; `src/render/` owns Pixi resources and GPU execution; `src/session/` owns recording/scope lifecycle. App and Studio are hosts. No entity renderer subclasses, spell controllers, reflective dispatch, second geometry registry, world simulation or renderer-to-player imports.

Reuse `MediaGeometry` and its finite existing variants at their existing source owners where necessary. `residue_wall_faces` contains **2D source-face mappings for deposits**, not a complete 3D wall mesh. Reuse those mappings for their actual purpose; only lift a source polygon into a physical face when that face's plane/calibration is known. An absent 3D field is not permission to reinterpret a 2D field as one.

## 3. Repair A — one registration and geometry path

Primary files: `src/math/isometric.ts`, `src/presentation/{terrain,environment}.ts`, `src/render/{terrain,environment,world-depth,material-sprite}.ts`. Source changes, if needed, stay in `game/{asset_types,world_binding_types,environment_art,presentation_export}.py` and their existing JSON owners.

### A0. Recover the compatible assembly before judging its rendering

Use the [asset recovery handoff](NDCLIENT_ENVIRONMENT_ASSET_RECOVERY_HANDOFF_2026-10-08.md)
to select a saved source assembly with established wall/corner/opening/frame/leaf
relationships and terrain/support ownership. Preserve its source occurrences,
relative offsets and enclosure; resolve them through existing source owners.
Neither a material match nor an installed door registration establishes that
relationship. No replacement map assembled from guessed parts is authorized.

Use the same authored state, selected release, poses, viewport, zoom and projected
focus in Pygame and Pixi. Account for their different rotation centres through
camera translation. Keep upper/lower floor finishes distinguishable as requested.
The existing broken fixtures remain regression evidence; they are not references
that certify their asset pairing. Missing source compatibility must remain named,
not be hidden by rendering compensation.

### A1. Establish where the reported door diverges

Use the existing **Indoor Door Elegant raised** recording and original frames. Add a diagnostic view to the existing Studio/tool, not a new scene renderer. For the offending object show the retained native position/base height/boundary direction and current open/destruction state alongside:

1. source assembly/compatibility evidence, native owner/incident cells/physical edge, selected bank, physical art pose, offset-adjusted bank pose and frame;
2. full source cell, packed rectangle, trim origin if applicable, pivot and scale;
3. projected support and authored ground/contact origin;
4. decoded depth interval, byte order, zero/invalid convention and pixels-per-unit;
5. resulting rendered colour and depth, separately and together.

Overlay the original contact marks on the unchanged art. The Elegant door's per-pose pivots are already exported and read: “ignored pivot” is not an established diagnosis. First render that same object without depth composition to distinguish a placement error from a depth error. Then compare its depth against its neighboring registered wall and floor, with compatibility established under A0 before claiming assembly correctness. This is a diagnostic switch, not a second production placement policy.

Repair the first divergent transform in the shared path: wrong pose means correcting pose selection; incorrect packed coordinates mean fixing the pack/source-coordinate mapping; a wrong depth origin means correcting depth conversion. Do not move the pivot or resize the image until comparison with the canonical source proves that source value is wrong. Remove any superseded compensation instead of stacking another offset on it. All equivalent door/bank consumers receive the fix.

### A2. Coordinate and source-frame arithmetic

Keep the existing authored basis: rotate world `(x,z)` by camera quarter; screen before pan/zoom is `((x'-z')*64, (x'+z')*32 - height*64)`. Screen/CSS/device pixels remain a final transform, not new world units.

Preserve native owner, physical edge identity and vertical span separately. An
EAST boundary and the adjacent cell's WEST boundary share an edge but not an
image mount. Project the received owner contact, not the edge midpoint. Mount
objects at committed `base_height_steps`, never their top or the higher neighbor;
do not add the owner tile's elevation again. Raising an entire assembly one step
must shift every registered contact by `(0,-64*zoom)` without changing XY.

Use the source notes' native-direction/camera mapping, not cardinal names as art
suffixes. Apply pan/zoom either at the parent or in child screen transforms, never
both. Preserve editor occurrence pixel offsets separately from source-scaled local
coordinates and world-cell support deltas. Existing source owner rebases are
ingestion corrections, not extra runtime offsets on already committed placements.

For an untrimmed registered frame, image origin is projected contact minus source pivot times source scale. Current packed environment frames retain the full original cell dimensions: their atlas rectangle x/y changes **UV sampling only**, never placement. Actual trimming, if present in another family, uses a separately recorded source-local trim offset; atlas x/y is not that offset. Packing must not quietly turn full-source pivots into cropped-frame pivots. Colour, depth, normals, face masks and sockets use the **same** source-frame mapping and pose.

Keep `x'+z'` as the comparable ray-depth coordinate used by the current accepted basis; calculate it at the reconstructed **surface point**, not at the sprite's screen rectangle. Height affects projection and the recovered point along that ray. Apply the existing depth units/range/origin conversion once. Stable contributor keys resolve authored ties; they must not disguise wrong physical depth.

Create a passive derived surface description in the existing presentation path, using the existing finite geometry types. It carries the selected source frame/transform and physical contact/face geometry. Draw/depth, receiving normals, hit testing and cosmetic-light barriers derive from that description. Different purposes may select different faces or native blocking flags; they must not independently invent different wall locations.

Static `ImageResourceSource` currently lacks a geometry field. Extend that existing owner with optional `geometry: MediaGeometry`, reusing the existing union; registered static walls/cliff/stair images select its calibrated plane/mesh variant with source polygons and source-to-local registration. The existing terrain profile continues selecting the image and its support contacts. Animated banks keep their existing depth/surface-geometry fields. UI images need no geometry. Packing/export preserves these source records; no parallel profile registry or handwritten TS copy is introduced.

### A3. Floors, exposed sides and stairs

- Floor top and the asset's small edge skirt have distinct surface depth. Adjacent equal-height tops remain continuous regardless of insertion order. Do not erase artwork skirts globally or force all floors behind every body.
- Select a cliff only from an actually known support-height difference or explicit native boundary. Apply `upper_support_offset` and `rise_steps`; assemble actual exposed straight/corner pieces, including the top-to-side joins. A known platform must close on its exposed physical sides in every camera.
- Remove the blanket lower earth tile under every raised tile. Emit bed/backing pieces only where the registered support assembly needs them; they may not extend as an invented lower floor into undisclosed space. At a disclosure frontier, preserve the admitted top/art overhang and unknown backdrop without claiming that the frontier is a physical cliff.
- Do not represent every positive drop as one two-step asset. Use only assemblies supported by the current registered profiles; repeated risers require a demonstrated valid join. Otherwise return a specific unsupported-profile error naming the support and rise instead of silently drawing a wrong height. The current two-step asset is not a universal height renderer. Do not invent one-step art or stretch a two-step image.
- For a stair flight, use `support_offsets`, its lower anchor, orientation and per-pose `contacts_px`. Project each registered support and compare it with the corresponding source contact after pivot/scale. Those collinear contacts establish registration, **not** width, tread/riser topology or source-face boundaries. Recover/calibrate those faces independently from the existing artwork/studies and record them in the image's finite geometry above. Do not infer a ramp or three columns from contact points. The installed flight having three contacts is source data, not a rule for all stairs.
- Keep support identity separate from its raster: a full flat floor at the intermediate stair height can cover the actual flight. In the imported study G16 is an edge lane and G17 extends width; preserve their common rise rather than stacking it. Use that source's explicit traversal contacts, not a filename heuristic or an assumed equivalence with the production three-support flight.
- Select cliff corners from their own `corner_faces`/supported-surface profile; the wall corner table is different. Preserve local upper-rim, lower-foot and foreground-surface relationships. A raised constructor assembly must close actual perimeter faces, including stair side returns; an undisclosed neighbor is not an exposed perimeter.
- A partially disclosed staircase is not an invalid native world. The current facts cannot identify its flight from an isolated middle/upper member. Use the explicit proposed observation below; never demand hidden tile records, guess a lower anchor, substitute a flat tread or crash ordinary exploration.
- Stair transitions and actors use the same retained native support heights. The art is placed around those contacts; do not alter path height to make a screenshot fit.

#### Partial stairs: one explicit proposed observation, not a hidden fallback

**User-approved policy (8 October):** seeing a stair member admits the direction and length of its physical flight for presentation. The user answered “yeah fine” to this exact shape-only disclosure question. This is some additional assembly-shape disclosure; merely omitting neighbor UUIDs would not make it disclosure-free. No generic flat-floor replacement or guessed flight is allowed.

For the current straight, unit-rise native flights, add optional `WorldTileState.observed_stair_run` at `dnd/types/event_facts.py`, with only:

```text
uphill_direction: CardinalDirection
member_index: nonnegative integer, zero at the lowest member
support_count: positive integer, member_index < support_count
```

The admitted member already supplies position, elevation and slope axis. Derive `lower_position = position - member_index * uphill_direction` and `lower_height = elevation_steps - member_index`; do not serialize those redundant values or an artwork ID. A pure helper in `dnd/world_facts.py` derives the unambiguous straight monotonic run from the cold recorded support facts. `dnd/player/projection.py:_world_update` attaches the observation before comparison with remembered tiles. No live `GridMap` lookup, native artwork import, run entity or traversal change. Ambiguous/branched/non-unit runs receive no invented assignment.

The observation reveals no neighboring tile records, UUIDs, materials, light, creatures, current visibility or legal movement. Derived member positions are visual placement inputs only: they are never inserted into the reducer's tile/seen sets, picking support map or SDK action targets. Retain the observation through ordinary remembered-state handling; do not refresh it while its owning member is unobserved.

The existing terrain profile matches the observed physical run to its registered `support_offsets`; an admitted flight's source silhouettes/overhang may render without pretending its undisclosed support cells are now known. Run mismatch is an explicit unsupported registration. Old recordings with no observation can render a uniquely established flight from their received supports; otherwise they retain the stated limitation and need a fresh native capture for partial-flight acceptance.

This is **narrow native observation/schema work** specified inside the repair under the approved policy. Fold it into the master's existing single source-derived SDK amendment with reach/cancellation, not another server redesign or generation loop. Add a native projection case that starts with only a middle or upper member visible and proves the exact shape-only disclosure; consume that same record in Studio. This extension is unnecessary for purely visual geometry, atlas or scale fixes. Approving this policy does not lift the implementation stop.

### A4. Walls, apertures, animated doors and props

For the existing legacy composite corner, replace only two perpendicular wall
contributions sharing owner, material and base with the corresponding registered
corner. Preserve both physical faces and provider IDs; do not also draw the two
straight images or collapse opposite faces/T junctions. Other families require
their own compatible profiles. Preserve the doorway's actual opening instead of
drawing a full straight wall behind it.

Frame and bank pose selection are distinct: in `[e,s,w,n]` order use
`bankPose = poses[(index(physicalPose) - door.pose_offset + 4) % 4]`, while an
external `frame_resource_by_pose` uses `physicalPose`. C1/C3 at offset 1 are the
concrete nonzero-offset case. The selected bank's pivot follows its bank pose;
frame and leaf retain the same native owner/edge/base through all states. Keep
depth ground origins separate from these mounting pivots. Do not demand an
external frame where the family already supplies its own registered frame.

Static walls need calibrated faces, including thickness and returns, from the selected art's existing registrations/reference studies. Prefer the available registered depth/mesh. Where a static image lacks geometry, place its calibrated finite geometry at the existing asset/profile owner; export through the existing presentation catalog. The accepted D1 quarter-cell face measurement is reusable for its verified family only. Do not add another wall-name table inside shaders.

For animated banks, continue consuming per-pose frame pivots, ground origins and registered depth; open/close/destruction must not switch to unrelated ideal geometry. Preserve open apertures and the current leaf/frame depth. Current bank `surface_geometry_by_pose` is empty for the reported door: diagnose its existing depth first instead of demanding a new export as the default repair.

Do not describe all walls as animated: legacy directional/D2 registrations are
static, and the seven imported solid siblings have intact-only banks with empty
destruction bindings in the inspected data. Keep each family's actual coverage
explicit. Separate delivered solid-wall break effects need matching integration;
do not substitute a window-wall bank or regenerate artwork to mask that gap.

For props, preserve native multi-cell footprint, visual overhang, pose, scale and pivot separately. A coarse collision cell does not authorize shrinking a table into that cell. Compare the existing 53-bank delivery and large-prop patch with current source values before applying anything; already integrated authoring must not be applied twice.

Derived visual geometry is updated from the **displayed** door/destruction state. It does not change collision, spell propagation or server light rules. Future native reach regions remain a separate master-plan obligation. Never clip an admitted Fireball/cloud silhouette to cells or a blast-origin wedge while fixing ordinary world surfaces.

## 4. Repair B — source-faithful actor appearance

Owners: `src/presentation/appearance.ts`, `src/render/actors.ts`, existing rig/motion/contact sampling, source factories `dnd/content/characters/premades.py`, `dnd/monsters/{beasts,bestiary,srd_roster}.py`, and the existing condition recipe's `persistent.bodyScale` contract (`game/condition_animation.py` and `game/data/PRESENTATION_CONTRACT.md`, “Condition body presentation and maintained media”).

Audit the **effective** scale chain: original rig tile units → existing source-to-world conversion → explicitly authored appearance scale/width → gameplay size effect → camera zoom. `128/64` is a coordinate conversion, not permission to add creature-class cosmetic scaling. Apply each term once; shadows, feet, sockets, hit regions and attached layers inherit the same placement transform.

Remove unrequested Sorcerer/Barbarian and goblin cosmetic normalization at the original producer. Review the edits already made before the stop: restricting a generic size table to beasts still does not justify shrinking every tiny/small beast. Keep named, documented animal enlargements (including the accepted wolf at twice original size), halfling sizing and actual Enlarge/Reduce semantics. Do not introduce a new default size-category table. Natural differences between fixed monster sprites remain intact.

Halfling appearance follows the existing `dnd/content/characters/build_types.py:CharacterAppearance.config()` → `AppearanceConfig` → retained actor appearance path. Preserve an explicit authored character scale there. The current inspected source does not supply a separate automatic halfling multiplier: do not invent one or claim that a species-driven renderer exists.

Implement the narrow missing `persistent.bodyScale` consumer as part of B. Retained active condition membership and `size_change` select the existing authored enlarge/reduce values; the existing transition duration supplies interpolation. Apply the result once to the resolved actor contact, including body, gear, shadow registration, sockets and attached effects, around its unchanged ground anchor. Application, removal, suppression/resumption and seek sample the same retained intervals; rendering an already resolved contact cannot multiply it again. No spell-name branch, new scale table or native occupancy change. This does not require implementing unrelated condition materials in this repair.

Preserve original recording appearance data. Correct new source appearances by producing a fresh native recording; do not normalize old recordings on load. Distinguish old recorded values from the live corrected values in review evidence.

Fix cast equipment policy at slot granularity: the current main-weapon `hidden` behavior must not remove the offhand. Keep source clips, wings, weapon sockets and previously authored animation choices unchanged by this repair. Complete condition-material delivery remains in N3; do not claim this scale audit implements every missing condition renderer.

Evidence: original-scale modular human, current named animal enlargement, natural fixed goblin/demon proportions, explicitly authored character build scale, Enlarge/Reduce application/removal/suppression and seek, and a main-weapon-hidden cast retaining its offhand. Use the source/current effective-scale values with the images, not subjective guesses based on PNG canvas size.

## 5. Repair C — one displayed timeline and atomic resource readiness

Owners: `src/presentation/{playback,timeline-types,environment-timing}.ts`, `src/render/{scene,resources,effects,terrain,environment,actors}.ts`, `src/app/main.ts`, `src/studio/main.ts`, `src/session/{live,journal}.ts`.

### C1. A single retained presentation time

The existing presentation timeline owns absolute displayed time. Program/track time is derived from its recorded/compiled start, not a second advancing clock. Idle/body loops, water, flames, environment transitions, effects and receiving/emitted light sample this same time with their own authored local offsets/rates.

Before advancing, sample the candidate displayed frame and determine its resource dependencies. Present it only when that complete frame is ready. Otherwise retain the last complete frame and its displayed time; do not let idle/water/light advance separately. Camera/UI remain responsive. Ingestion, retention and the received/consumed cursors continue independently of rendering; readiness never becomes an engine-animation handshake.

Pause, speed change, seek backward and program boundaries follow that same clock. Save the presentation position needed to restore loop phase; do not rebuild it from wall-clock time or the renderer's previous draw calls. Remove the independent `visualTime` state and Studio-only equivalents after migrating their consumers.

Make the retained data concrete in the existing journal: extend `PlaybackPosition` with `absoluteTimeMs`, keeping `sequence` as the last completed operation and `timeMs` as the next operation's local offset. Each started operation's existing retained record gets local presentation metadata `presentationStartMs` (separate from its unchanged raw SDK bytes). `Program` uses that start for `local = absolute - start`; presentation metadata is not sent to the server or fed into the reducer. Release/compiler identity qualifies this derived schedule under the master's existing replay policy.

While live playback waits for another operation, `absoluteTimeMs` advances so idle/water do not freeze, while `sequence` and `timeMs = 0` stay fixed. When a new ready operation first presents, retain its start at the current absolute time; buffering does not add a hidden idle gap. On reload restore that checkpoint and start metadata, with no wall-clock catch-up. Replaying a started operation reuses its start; a recording without local start metadata receives deterministic consecutive starts from compiled durations. Studio consumes the same schedule when metadata exists. Authoring a different release/compiler explicitly recomputes the derived schedule, preserving raw gameplay records. Save complete checkpoint tuples at the existing lifecycle/pause/operation checkpoints, not an IndexedDB write per frame.

### C2. Prepare what can actually become visible

Expand the existing program preparation to include before state, each presented commit state and transition-only resources. This covers a newly revealed floor material/door/prop, a newly admitted actor/equipment set and companion depth/normal pages, not just effects. Derive the union from the compiler's existing states/channels; do not invent a second event traversal in the renderer.

The resource owner continues leasing pages by URL. Scene readiness covers **all** visible consumers of the candidate frame. A colour/depth/normal set is usable together, never one plane at a time. Camera changes select a fully prepared pose or retain the complete old view until the new pose is ready; they do not draw missing pages or synchronously decode inside a draw.

The displayed frame pins its entire dependency lease set until replacement. Prepare candidate demand **in addition to** displayed demand; `effects.ready()` must no longer evict the displayed frame by retaining only the newest requested paths. Once ready, atomically install candidate frame, absolute/local time, displayed camera, picking/cutaway geometry and light inputs, then release superseded demand. Cancelling a candidate releases only its demand. Requested camera/seek and displayed camera/seek remain distinguishable while buffering, so input never picks against a new projection while showing old pixels. This is a small retained-frame record and commit function within scene/playback ownership, not another resource manager.

Keep working-set loading and release unused resources through existing leases. Do not preload the complete art collection, create another cache manager, repack everything, or impose a made-up page-size budget. Keep failures explicit with resource path, asset/pose/frame, recording/program and scope context; no catch-and-ignore placeholders.

### C3. Scope isolation and retirement

On audience/game replacement, synchronously remove the old visible world and picking state before awaiting the next connection. Increment the existing connection generation (or add that small host-local token if absent), detach old listeners, and invalidate pending preparation callbacks. A completion can install only into the generation that requested it; stale work releases its own leases. The same scope/request guard covers a newer seek, camera-pose preparation and Studio recording replacement, not only live connection changes.

The new connection failing leaves an empty/error state, never the previous audience's canvas. Camera/selection, lights and resource references follow the same retirement. This repairs the existing lifecycle, not a new session framework. A recording keeps its release identity; resuming against a different release is explicit, never an unnoticed catalog swap.

## 6. Repair D — shared geometry for interaction and light

Use the same displayed samples from A for floor picking, wall/door/prop hit geometry, highlight placement and visual-light receiving. Native action eligibility stays with the delivered SDK. A camera rotation changes projection, not which disclosed door exists or can be selected.

Keep grid and ground feedback on their registered receiving top/stair surfaces, below supported bodies and walls. No fullscreen grid overlay through geometry. World occlusion and UI overlay order remain separate.

The existing master requirement for automatic wall cutaway remains: walls covering visible interactive space must allow that space to be seen/targeted without requiring Alt or a camera workaround. Derive covering faces from the displayed calibrated geometry; do not fade unrelated walls by tile ID. Faded colour does not erase the physical wall or turn off its native blocking. Pick through the cutaway to the exposed target while retaining a direct visible-door/object target and Alt highlighting.

Normals and receiving positions use the same surface/pose/camera transform. Static walls, animated doors and neighboring floor must not use different light origins or response conventions. Derive cosmetic-light barriers from the same calibrated current faces and native blocking flags, including an open aperture; do not create another CPU light simulation. Authoritative disclosed visibility and baseline light remain SDK state. Cutaway is a display choice, not a change to light/physics.

Do not broaden this repair into normals generation for every asset, global material reauthoring or complete spell propagation. Preserve accepted Fireball source/depth/normal/emission math and test its composition against the repaired world as one regression. The remaining volume/reach/protection work is still N0–N3 in the master.

## 7. Repair E — remove the actual hot-path waste

The reviewed code rebuilds terrain when the whole `PlayerState` identity changes, even when terrain is unchanged. Scope this repair to eliminating that demonstrated invalidation problem and resource/clock stalls; do not reopen a general performance project.

Keep static source-frame geometry reusable. Rebuild only when its consumed support/material/pose data changes; update light/visibility attributes when those change; pan/zoom update transforms. Quarter-camera changes select registered geometry/frames but reuse loaded pages. Derive dirty inputs from the existing reduction/presentation updates or a small owner-local revision; no deep full-world JSON hashing every frame, duplicate world snapshots or generic cache framework.

Record startup preparation separately from steady playback, and CPU submission separately from GPU time when available. Inspect the existing counters for terrain rebuilds, uploads, texture leases and compositor work in the combined repair case. A correct screenshot cannot excuse a stall, and capped FPS alone is not a benchmark. Use observed regressions to choose further optimization; no invented MiB/frame-count targets or permanent profiling dashboard.

## 8. Coverage and evidence that actually decide correctness

Extend existing client tests, Studio fixtures and browser tools. No second renderer or new acceptance application. Review through the running Studio/app: select the real case, rotate, play/pause and seek against source registration evidence. The human explicitly replaced exported screenshot/video galleries with live app review. Historical images may remain evidence; do not generate another gallery as the deliverable. Actual native recordings, played through the shared renderer, prove changes caused by gameplay.

| Case | Required observation/assertion |
|---|---|
| Source-compatible assembly and reported raised Elegant door | Compare the same source-compatible area in Pygame/Pixi, with matched state/release/framing and explicit cutaway. Keep the rejected Elegant pairing as a diagnostic regression, not a compatibility oracle. Four cameras; inspect registered contacts before depth and composition afterward, closed/open/intermediate states, and no invented earth strip/cliff at disclosure frontiers. |
| Flat floor | Existing reversed-insertion comparison still passes; no raised edge strip paints over an adjacent top. Camera pan changes only projection/culling. |
| Known platform and partial disclosure | A fully known platform closes its actual exposed faces; the same platform under partial disclosure does not acquire a cliff where it continues into unknown space. |
| Stairs | Both slope axes and all cameras; ascending/descending native actor movement follows registered contacts; foot/shadow/picking and grid agree. Start with only a middle or upper member visible: use the approved shape observation without exposing other tile state. Unsupported rise cannot silently become a two-step cliff. |
| Wall/door orientations | All native cardinal directions against all four camera quarters; preserve owner versus shared edge, physical frame pose versus source-bank pose (including C1/C3), original pivots and shared base lift. Door states use current depth/aperture; corners preserve both faces without duplicated straights. Compare relevant static and animated families. |
| Multi-cell props | Original table and large-prop examples retain their source pivots, footprints and overhang; no wall clipping caused by a second offset or shrink. |
| Actor proportions/gear | Effective scale chain matches source policy, original natural differences survive, accepted animal enlargement remains, authored character scale is preserved, condition bodyScale applies/removes/suppresses/restores once under seek, and hidden main weapon does not remove offhand. |
| Asset reveal | Native reveal introduces a previously unprepared material, object and actor; readiness prevents partial frames and missing-page errors, then advances automatically. No objective data is used to preload undisclosed content. |
| Deterministic playback | Same absolute displayed time reached through continuous play, seek, buffer/resume and journal reload produces the same loop, transition and material phases, including live idle before the next operation; no operation-boundary reset. |
| Atomic camera/frame replacement | Delayed pose/frame loading keeps the old frame's leases and matching picking/light geometry; a new seek cancels only obsolete candidate demand; replacement never mixes cameras or frames. |
| Scope replacement | Switch while preparation is delayed; fail the new connection; no old pixels, selection or late callbacks appear. Shared leases survive destruction of only one owner. |
| Picking/cutaway/light | Visible space behind a wall can be seen/selected; door remains selectable in every camera; faded wall still has its physical light/blocking role; floor/door/wall receive coherent light. |
| Existing VFX regression | Accepted Fireball has consistent front/back depth against repaired walls, receives/emits light, and keeps its silhouette; ordinary cast socket/palette and projectile behavior are not changed accidentally. |
| Combined live case and Studio | Reveal, rotate, move on stairs, open door, cast and seek through the same compiled data. No per-frame static geometry rebuild, repeated decode or renderer-only state drift. |

Assertions must use independent evidence: registered source contacts, native positions/heights, original bank calibration, expected causal states and controlled resource delays. A test repeating the renderer's own formula proves only self-consistency. A browser run with no exceptions does not prove visual alignment. Inspect the actual images at scale 1 and camera rotations before claiming success; use annotated contact/depth views to explain discrepancies.

For foundation asset fields, record one source→export→consumer table in the repair evidence, by existing family/field, including pivots, trim, scale, contacts, pose mapping, depth units/origin and receiving faces. Mechanically check the selected entries use that family path. This is a review table, not a new runtime schema or a mandatory per-file audit of every historical asset. Fields owned by later spell/material/Studio work remain explicitly incomplete in the master coverage ledger; do not mark them supported because their generated TS type exists.

## 9. Work order, deletion list and stopping rules

1. **Source assembly, then placement:** resumption is now explicit. Retain existing bad recordings/images, recover the compatible assembly under A0, compare identical Pygame/Pixi inputs and trace the detached door under A1–A4. Do not start with another guessed map. The first checkpoint is the correctly registered scene in the running client, not a new proof app or exported gallery.
2. **Shared appearance/lifecycle:** finish B and C in their existing owners. These can proceed independently of individual art-family corrections; no reason to spend hours repeating a floor-only check while these known defects remain.
3. **World integration:** finish D and the measured invalidation repair E; exercise the combined case and complete the focused coverage above.
4. **Independent implementation review:** anti-slop reviewer checks source fidelity, unnecessary systems and whether each complaint is actually fixed; anti-OOP/ECS reviewer checks passive data, ownership/DAG, time/resource/privacy boundaries and shared consumers. They inspect code and the relevant images/results. Repair their concrete findings, then obtain follow-up review of the changed findings only.
5. **Report and return to the master:** summarize actual changes, evidence and remaining global stages. Foundation completion is not full-client completion.

Remove the superseded logic as each replacement lands: blanket raised-bed emission, ideal wall-face formulas where calibrated geometry belongs, independent light-barrier placement assumptions, hardcoded stair columns in place of registration, unsupported size normalization, offhand over-hiding, competing visual clocks and stale-scope callbacks. Correct the old raised/stair validation claims. Keep useful tests/resource leases and ordinary source-preserving helpers.

Do not add a new asset registry, transformation DSL, scene format, entity hierarchy, server, SDK adapter or general observability subsystem. Small passive geometry/frame/time records may extend existing types where a required distinction is currently missing. Pure visual schema changes remain in the presentation export and its generated types; they do not trigger player-SDK regeneration. The approved partial-stair observation above is the separately identified native exception, integrated with the already planned amendment. No image editing or asset rescaling merely to make a test pass.

Review is not a serial ritual before every function. Run the checks appropriate to an independent change once; repeat when a fix or unresolved concern justifies it. Do not re-export all assets or regenerate every recording to validate a change to a shared transform. If work uncovers a real missing registration, name the exact asset/field and use its existing source owner; do not convert it into an open-ended research phase or silently narrow the delivered scene.

### Completion and what comes next

This repair is complete when A–E and the above cases pass with source-based visual evidence, Play/Studio share the repaired path, the two implementation reviews have no unresolved correctness/ownership findings in this scope, and the status documents state the actual remaining work. The user decides visual acceptance from the review page; reviewer approval does not replace that.

Then resume the existing N0–N5 work: remaining native reach/cancellation amendment; all action/spell/condition/construction/blood/material consumers; full canonical Studio editing/A–B/save; complete playable Fighter/Sorcerer encounter UI and final performance/interaction acceptance. None of those are declared finished by this repair, and the movement-only app is not a substitute for them.

**Implementation was resumed by the human later on October 8. The source constraints, rejected-assembly status and remaining acceptance work remain binding.**
