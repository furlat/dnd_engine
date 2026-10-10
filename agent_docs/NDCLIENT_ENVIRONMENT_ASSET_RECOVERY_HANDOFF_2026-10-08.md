# Environment assets: recovery handoff after the rejected NDClient area

8 October 2026. **Originally written during the human's halt; foundation repair has now been explicitly resumed.** This handoff's source/compatibility requirements remain binding and the terraced keep remains rejected. Review current results in the running app; do not export new screenshot/video galleries for the human. Historical halt/review receipts below describe their original work period, not a current stop. No communication with other chats or artists is authorized.

This corrects the [asset migration chapter](NDCLIENT_ASSETS_AND_RIG_AUTHORING_2026-10-08.md) and [foundation repair plan](NDCLIENT_FOUNDATION_REPAIR_PLAN_2026-10-08.md). Copying files and preserving their individual pivots does not preserve an authored environment. The missing obligation is to recover and consume **compatible assemblies, directional adjacency, support ownership and occurrence-level placement** before composing a scene.

**Later October 8 correction incorporated:** the human supplied the animated-wall
author's [positioning notes](PIXI_WALL_DOOR_ELEVATION_POSITIONING_HANDOFF_2026-10-08.md).
Their concrete owner, pose, height, contact and registration rules are part of
this recovery, not optional background. §3.5 records their consequences; the
foundation plan's A0–A4 and comparison requirements are amended accordingly.
The earlier document reviews predate this amendment and do not certify it.

## 1. What went wrong

The assistant selected generic native stone walls, which resolve to Fantasy Wall D1/D2, and independently selected `environment.door.indoor_door_elegant`. That door comes from the generated-interiors family. No source assembly or compatibility record was established for that pairing. An existing registered asset is not permission to mount it in an unrelated wall.

The new `terraced_keep.py` therefore is **rejected and not a reference layout**, even though its native perimeter closes. A topology review that checks a closed room and matching tile heights cannot approve its art composition. The area also initially used the same stone finish above and below the terrace, obscuring the elevation under review. The subsequent wood/stone change was made before the halt; it does not make the area accepted.

The repeated defects must not be addressed by:

- Building another improvised map or substituting a different door until a screenshot looks plausible.
- Moving a leaf independently of its opening, changing sprite scale, or adding camera-specific offsets without source evidence.
- Treating `material == stone` as a wall family or assuming all stone corners, apertures, frames and doors are interchangeable.
- Treating a per-asset registration, inventory count, loaded texture or passing topology check as proof of assembly compatibility.
- Treating the GPU depth path as the cause before comparing the same correctly authored assembly against the reference renderer.

The source assets and hand-authored data are still present. Their use was incomplete; this is not evidence that the user's original work was deleted.

## 2. Source map: read these records, not recalled labels

All paths below were checked on disk in this pass. Paths are source locations, not instructions to copy or modify them now.

| Source | What it actually provides | How it must be used |
|---|---|---|
| `/mnt/c/Users/tommaso/Documents/assets/environment-production-audit/audit.json` and `HANDOFF.txt` | Per-family IDs, original/reviewed sources, installed registrations, native IDs, parent/insert evidence, eight prefab assembly pointers and explicit integration gaps | Follow each selected family's source links. The October 1 audit is historical evidence; verify current bindings separately. Its notes explicitly do not certify arbitrary wall geometry/adjacency. |
| `/home/tommaso/.codex/worktrees/23a9/dnd_engine/output/environment-sprites/architecture-handoff/backend-mapping.json` | Original wall IDs, source sprites/hashes, visual roles and proposed height/material profiles; door family source directory, mechanism and pose offset | Preserve proposed versus certified status. Its door entries explicitly say the frame is separate from the leaf and requires an explicit architecture profile. Do not promote proposals into rules. |
| `/home/tommaso/.codex/worktrees/23a9/dnd_engine/output/environment-sprites/door-workshop/families/<family>/metadata.json` | Closed/open family pairing, cell, pivot, scale, rows, timing, mechanism, limitations and destruction selections | These describe the door's own animation and mount. They do not by themselves prove compatibility with every opening. Example: `fantasy-a1` names closed A1/open A2; Fantasy C1 has a different mechanism/pose mapping. |
| `/home/tommaso/.codex/worktrees/23a9/dnd_engine/output/environment-sprites/house-prefabs/room-dressing/prefab-review/0-layout.json` and the other seven assembly files listed in the audit | Saved layout parts, footprint, levels, terraces, attachment sockets, surface profile, roof strategy and interior | Recover the complete relevant assembly, including its internal relative placements. Do not extract one attractive component and discard its surrounding constraints. The audit does not claim these are already production recipes. |
| `/home/tommaso/Dev/NeuroMapEditor/public/assets/unity-reference/{scene,semantics,manifest}.json` | Imported source occurrences, asset identity, tilemap/layer provenance and authored placement | Keep asset-level calibration distinct from occurrence offsets, ownership and Z grid. Use the editor's correction record below when interpreting the imported snapshot. |
| `/home/tommaso/Dev/NeuroMapEditor/docs/PHASE_ONE_IMPLEMENTATION_RECORD.md` with `src/model/types.ts`, `src/model/lattice.ts`, `src/render/spritePresentation.ts` | Corrected anchors, Z-grid ownership, source-role distinctions, terrain contacts and known limitations | Recover completed corrections, not the older flattened assumptions. Do not copy its whole application architecture. |
| `/mnt/c/Users/tommaso/Documents/assets/arena-study/prototype-v1/grid-kit/constructor/review/unity-reference/compositions.json` | Four actual source compositions: `timber-service-court`, `masonry-house`, `quay-store`, `stone-court`; exact placements and `directional_contacts` | Each placement carries asset ID, native position, `anchorPx`, `offsetPx`, `renderScale` and source provenance. Preserve the observed arrangement. Contact counts are evidence of a placed example, not universal permissions. |
| Same constructor: `DISTRICT_RULES.md`, `encounter-art/unity-motifs.json`, `encounter-art/manifest.json`, `themes/{source-manifest,ground-sources,roof-sources}.json` | Complete furnishing motifs, source finishes and their appropriate architectural use | Preserve internal offsets and relative facing as a group. Ground, facade and roof textures are different roles. Do not repeat a stepped bank image as flat ground. |
| Same constructor: `DELIVERY.json`, `RULES.md`, and a selected `builds/<id>/{placement-contract,adjacency,game-data,scene}.json` | Constructed arena geometry, complete cell inventory, shared cross-sections, exposed retaining faces, supports, barriers and closed layer perimeters | This is an actual geometry-based adjacency contract for that arena family. It is not a generic permission table for unrelated Fantasy or generated-interior sprites. Select the build from the delivery record; do not pick an arbitrary archived build. |
| `/mnt/c/Users/tommaso/Documents/assets/environment-production-audit/placement-registration-53/` | Reviewed table pivot patch, two-cell prop pivots/footprints, four-camera/native-direction checks and explicit coarse geometry limitations | Keep these corrections across intact, animated and broken states. Do not bottom-align each frame or derive a collider from decorative overhang. |
| Engine `game/data/{assets,world_bindings,environment_art,environment_prop_sources,window_media_sources}.json` | Current selected resource registration, runtime role mapping, animation families, placement corrections, parent/insert bindings | Existing canonical ownership. Extend only the owner missing a field; do not build a competing asset registry inside NDClient. |

The source Unity scene hash recorded by the composition study is `3be50d751cef67323201b9812e28770de348ffb597dc45ec627f853a9f473be1`. Match the source and correction record before relying on a historical screenshot.

## 3. Concrete evidence recovered in this pass

### 3.1 The selected wall and door were not one established assembly

- Current `stone_wall_straight` maps to `stone.wall.straight.*`, identified by the audit as Fantasy Wall D1. `stone_door_frame` maps to Fantasy Wall D6.
- Several current Fantasy/Desert door registrations explicitly reference `stone.door.frame.*`; this is an existing implementation binding, **not certification that all those cross-family combinations are visually valid**.
- `environment.door.indoor_door_elegant` instead has an empty `frame_resource_by_pose`. Its source is generated interior artwork. Mounting it beside D1 was the assistant's choice, not a recovered compatibility relation and not the user's choice.
- The installed door bank has per-art-pose pivots E `(100,198)`, S `(156,198)`, W `(156,226)`, N `(100,226)`, scale `128/127`. Those values match the current engine data. Equality of those numbers does not approve the surrounding architecture, or establish that the complete Pixi composition matches Pygame.
- A registered door leaf, its optional in-bank frame and an external opening/frame are separate roles. The family decides which pieces exist; the renderer must neither omit the required opening nor duplicate an already included frame.

**No new universal door compatibility list is asserted by this handoff.** The selected compatible assembly must be named from source evidence before any replacement is implemented.

### 3.2 There are real adjacency records, with different scopes

`compositions.json` contains `directional_contacts` of the form `{asset, neighbour, direction, count}` plus the actual placements. For example, the masonry-house composition records repeated Fantasy Ground H1 paving contacts; the quay-store composition includes `fantasy.door.c5.e` alongside its actual architectural placements. The exact surrounding placements must be read; sharing a patch does not establish that any two members can touch.

The arena's `adjacency.json` instead measures area contacts of neighboring closed solids. It records each side's port hash and exposed remainder. Unequal heights deliberately retain exposed supporting faces. Matching a name or forcing equal whole profiles would destroy that meaning. Its `RULES.md` explicitly rejects missing side returns and open lower perimeters.

These records must remain source-owned and distinguishable. Do not flatten both into a guessed “allowed neighbor” boolean.

### 3.3 Multi-Z and terrain registration were already worked on

The editor separates `VisualPlacement.anchor`, `zGridId`, Z-grid projection offsets and source sprite appearance. Its correction record contains specific half-height-bank owner/pivot rebasing, different directional conventions for dirt and rock banks, corner support endpoints, and cosmetic pieces that carry no elevation. Those are not interchangeable generic cliff sprites.

The current NDClient path uses `WorldTileState.elevation_steps` plus broad terrain bindings and inferred G17 flights. It does not consume the editor's whole authored assembly/ownership model or the arena's adjacency contracts. A copied catalog alone does not close that gap. The handoff must map the selected source assembly into native supports and rendering registrations without flattening separate levels, supports or occurrence identities.

Multiple visual Z layers are not automatically multiple independently playable
supports at the same XY. Native `GridMap._tiles` currently stores one tile per XY.
A source assembly requiring stacked playable supports must be recorded as an
unsupported arrangement. This handoff does not authorize stacked-grid, traversal
or pathfinding changes; preserve the source assembly without pretending that
flattening it is a faithful implementation.

### 3.4 Full footprint and attachment work already exists

The registration pass fixes the B37/B38 table pivot to `(192,204.5)` without pixel or scale changes. Its larger-footprint patch keeps the supplied two-cell pivots for wagons/carts/logs and distinguishes structural support from canopy overhang. It also documents B13 as unresolved, not a floor decal. Use these records; do not recompute a convenient bottom-center or invent a role.

Window source documentation distinguishes insert-only break art from combined parent-wall previews. The latter must not be drawn as independent inserts. Parent/insert ownership, aperture masks, selection masks and intact-supported attachments must survive the migration.

### 3.5 Animated-wall author's positioning corrections — incorporated October 8

The [source notes](PIXI_WALL_DOOR_ELEVATION_POSITIONING_HANDOFF_2026-10-08.md)
specify the following corrections to the incomplete recovery account. These
are requirements for the existing consumers, not another runtime table.

| Correction | Consequence for this recovery |
|---|---|
| Physical boundary identity is not the image mount (§2) | Preserve both the canonical incident-cell pair and the authored owner/direction. Opposite owners can describe the same edge but move the registered masonry a whole cell. Do not replace the owner contact with the edge midpoint. Repair wrong native ownership at authoring, not with a Pixi offset. |
| Native cardinals and art poses differ (§1); frame and leaf poses can also differ (§7) | Use the documented native-direction/camera mapping. Compute `bankPose = poses[(index(physicalPose) - pose_offset + 4) % 4]`; external frame selection remains indexed by `physicalPose`. C1/C3's offset is a concrete case to preserve. This rule does not prove the current client gets it wrong; trace its actual selection. |
| Base, top, support height and occurrence offset have different meanings (§§4,7) | Mount at the committed `base_height_steps` once. Attachments retain the parent's owner/edge/base and their own pivots. Apply source scale/pivot and camera zoom once. Editor occurrence offsets are post-projection pixels; support deltas are world-cell vectors; prior owner rebases must not run again on committed placements. |
| Elegant's pivots are present and consumed (§9) | Retract any explanation that its pivots were simply ignored. Its detached appearance is observed; the exact transform/depth cause is unproven. Its compatibility with the chosen D1 assembly is independently unestablished. |
| Wall corners and cliff corners use different contracts (§§3,5) | Preserve both physical faces/provider identities when one legacy corner raster replaces two matching wall contributions. Do not also draw both straight rasters, collapse a T junction, or reuse the wall corner table for cliffs. |
| Cliffs relate lower owners to upper supports (§5) | Consume the selected rise, supported-surface offsets/footprints and face directions. Keep rim and foot relationships local to actual surfaces. No blanket lower earth tile, invented cliff at an unknown neighbor, or global “cliffs last” rule. |
| Stairs have explicit source contacts and width semantics (§6) | Match the actual native run to the selected flight and reproject each authored contact. G16/G17 lanes in the imported study extend width, not rise; that study is not identical to the production three-support flight. Do not cover the intermediate slope with an arbitrary flat floor. Close real exposed side returns. |
| Packing and depth origins do not redefine registration (§7) | Atlas XY selects UVs, not a world offset. Preserve full-cell padding or explicit source-local trim. Colour/depth/normals/masks/sockets share one mapping. `ground_origins_by_pose` calibrates depth; it does not replace the mounting pivot. |
| Source pivot data is not complete surface geometry (§8) | Some static resources lack calibrated 3D geometry and some bank geometry fields are empty. Zero-thickness wall substitutes and PNG bounds do not establish actual thickness/apertures. Reuse measured data where present; record a missing calibration at its source owner instead of inventing it. |
| Animation coverage is partial (scope reminder) | Legacy directional walls/D2 are static; seven imported solid siblings have one-frame intact banks and empty destruction bindings. Separate source break effects require their matching binding. A window-wall animation is not a substitute for a solid/corner wall. |

The author reports arithmetic checks for 16 direction/camera poses, 48 stair
contacts and 16 assembly lifts. That is evidence for the notes' formulas, **not**
a new test run here, complete compatibility evidence or acceptance of Pixi output.
The exact pose/contact tables remain in that one source document rather than
being copied into several editable plans.

## 4. What an environment selection must carry

This is a checklist over existing source data, **not a new transport schema or a demand to duplicate types**.

| Concern | Required evidence and interpretation |
|---|---|
| Identity | Exact source pack/family/member; selected revision; current binding and original path/hash. Material is not identity. |
| Assembly | Source layout or explicit compatible family relation; walls, corners, end pieces, opening, frame and leaf; preserve relative anchors. |
| Orientation | Native direction → camera quarter → authored pose; apply the family's pose offset once. Never index art pivots directly by native north/south labels. |
| Placement | Native support position/elevation, occurrence offset, source crop/padding, per-pose pivot and original scale. Separate placement pivot from depth-map ground origin. |
| Geometry | Which surfaces the pixels represent; actual opening shape, height spans, supports and side returns; decorative overhang separate from occupancy. Mark coarse or missing geometry honestly. |
| Adjacency | Shared boundary/port or source contact record; required corner/end/transition; allowable exposed face at unequal height; complete enclosure at each raised level. |
| Terrain | Source surface role, supported height, lower/upper contact and stair landing; coherent floor motifs and visibly distinct upper/lower finish in the repair reference. No random tile alternation. |
| State | Intact/open/closed/inward/outward/destruction/remnant, original timings, frame selection, matching depth and masks. An animation does not authorize a different mount. |
| Attachments | Parent identity, attachment socket, support dependency and matching after-destruction variant. No invented duplicate parent body. |
| Runtime | Existing native entity/item/tile identity and semantic mechanics; asset selection remains presentation authoring. No ECS entity per decorative layer. |
| Consumer | Which current engine export field carries each source value; which Pixi path consumes it; explicitly identify dropped/unconsumed values. |

Existing ownership is narrower than a complete assembly schema: static registration
belongs to `ImageResourceSource`; animated bank/depth/mount data and door-frame
selection belong to `EnvironmentBankSource` / `EnvironmentDoorSource`; broad
rendering-role selection belongs to `WorldBindingsSource`. Those types do **not**
establish a complete occurrence/assembly owner. The missing relationship remains
explicit authoring work; this handoff does not authorize inventing a client
registry or claim that an existing native assembly schema already carries it.

The source-to-consumer row must name a concrete asset/assembly, not merely “doors supported.” If a required field is absent, record the missing field at its existing owner. Do not proceed by renderer inference or create a parallel asset database.

## 5. Actual code boundaries for the resumed repair

| Current location | Confirmed limitation | Required direction |
|---|---|---|
| New `dnd/maps/terraced_keep.py` | Chooses art-bearing identities without an established compatible source assembly | Rejected. Do not use it as the art/placement oracle or author more maps from the same arbitrary choices. |
| Native generic wall + NDClient `src/presentation/environment.ts` | `stone`/`wood` selects a single broad straight/corner family; door selection occurs independently by item ID | Recover explicit selected appearance/assembly identity through the existing authoring/export owner. Native material remains mechanical data. No family-name guessing in the draw loop. |
| `game/data/environment_art.json` and NDClient `environmentFrame` | Individual bank metadata is present, but does not itself encode or establish complete family adjacency | Keep metadata; establish the selected assembly and required frame/opening relationship from the source records. |
| `src/presentation/terrain.ts` / `src/render/terrain.ts` | Generic material lookup and inferred stair support geometry do not represent all editor/arena authored terrain contracts | Consume the actual selected supported surfaces, contacts and enclosing faces. Do not use a complete native rectangle to excuse incorrect source placement. |
| `src/render/environment.ts` | Has placement/pivot/depth calculations, but no completed same-input parity proof for the reported assemblies | Compare against Pygame using the same compatible assets and state before altering offsets or depth. A formula review alone is insufficient. |
| Existing release export and asset chapter | Dependency copying was treated as stronger evidence than it is; current chapter still has stale “small copy only” language | Separate files present, registrations exported, assembly metadata preserved and runtime behavior demonstrated. Current complete local release exists, but does not imply correct composition. |

The correction must retain passive data + shared functions. No new inheritance hierarchy, client rule engine, duplicated combat state or per-map rendering exceptions. Live play and Studio continue to use the same renderer. Resumption authorizes the documented repair, not arbitrary artwork substitutions or rescaling.

## 6. Reference comparison required after the handoff

The human explicitly requested **the same authored area rendered in Pygame and Pixi**. That is the comparison, not two similar scenes.

1. Select a saved source assembly with established component relationships. Preserve its coordinates, relative offsets, supported levels, directions and footprints. Name its source record in the output.
2. Resolve its original selected registrations, including the matching opening/frame/leaf and terrain transitions. Unknown compatibility stays unresolved; do not substitute a visually similar part.
3. Give both renderers the same complete authoring state, same camera quarter, projected focus, zoom and viewport. Label authoring visibility separately from subjective gameplay.
4. Compare all four views. First inspect original contacts and silhouettes with depth composition disabled, then compare the same registered samples with depth restored. Distinguish intentional Pygame wall cutaway from placement differences. A transparent reference wall must not be compared blindly against a fully opaque Pixi wall. Corresponding camera pan/focus must account for Python's rotation centre versus NDClient's; that camera translation cannot explain relative gaps inside an assembly.
5. For a discrepancy, report the specific source coordinate, resolved mount and affected pixels in each renderer. Determine whether the error is the assembly, export, pose, placement, depth or source renderer. Apply the correction at that owner once.
6. After registration is correct, inspect the chosen assembly's existing closed/open/intermediate/destruction states without moving its parts. No new map is needed for each discrepancy.

Do not assert Pygame is perfect. Equally, do not ignore the user's working reference and invent offsets from screenshots. No arbitrary numerical budgets, repeated SDK generation, blanket re-export or broad all-asset validation loop is required for this correction.

## 7. Preserved rejected work and evidence

These remain on disk so the next person can see exactly what was done. They are not approved artifacts and have not been deleted or reverted during the halt:

- Engine `dnd/maps/terraced_keep.py`: native rejected map builder.
- Engine exporter at the halt was `devtools/export_terraced_keep.py`. Resumed work renamed it `devtools/export_world_authoring.py` and uses the existing native Lantern Crypt builder as its default; its full authoring view still uses existing player-value types, not private seat data. This does not reinstate the rejected keep.
- Engine `devtools/render_terraced_keep_reference.py`: calls the existing Pygame `draw_frame` on that exported state.
- NDClient `src/studio/main.ts`, `src/studio/style.css`, `src/render/scene.ts`: initial-state display, fit-area and resize support added in this attempt; not a renderer repair.
- NDClient `tools/terraced-keep-check.mjs`, `public/recordings/terraced-keep-authoring.json`, `public/reviews/terraced-keep/`: rejected map and captures.
- The Pygame process already launched before the halt finished its four captures under `public/reviews/terraced-keep/comparison/pygame-*.png`. It is no longer running. Those captures used the later wood/stone version; existing Pixi screenshots used the earlier all-stone version and different framing. **They are not a matched parity comparison and must not be presented as one.** No further render was launched after the halt.

No actor scale changes were made in this narrow map attempt. That does not settle older appearance issues.

## 8. Handoff completion and independent review

This handoff is complete when the source locations, observed misuse, missing consumer relationships and halted state are clear. It does not require pretending that every source-family relation has already been recovered. Unestablished compatibility remains named work; implementation readiness is withdrawn.

- **Anti-slop review:** check that existing sources are reused, evidence scopes are not inflated, no arbitrary compatibility is invented, and copying/readiness checks do not substitute for the actual rendering result.
- **Anti-OOP / ECS review:** check that source data stays with existing owners, native mechanics stay in the engine, existing SDK types are not cloned, and shared rendering consumes authored selections rather than accumulating asset-name branches.
- Neither review can override the halt or approve the rejected area. Implementation resumes only on the user's instruction.

### Document review result

Both independent document reviews completed during the halt. Anti-slop found no
blocking document correction. The anti-OOP/ECS reviewer required explicit wording
on the one-native-tile-per-XY limitation and on the missing complete assembly
owner; both corrections are incorporated above. These were document reviews,
not fresh asset compatibility certification or runtime acceptance. No additional
implementation, map edits or rendering experiments followed the halt.

**Review scope after the positioning amendment:** the result above covers the
earlier handoff version. The new source-backed corrections are incorporated, not
newly independently reviewed or runtime-validated. In the already required next
implementation review, anti-slop must distinguish source compatibility, formula
checks and actual matched rendering; anti-OOP/ECS must check native ownership,
source/occurrence units and shared geometry consumers without duplicated tables.
Neither review changes the halt.
