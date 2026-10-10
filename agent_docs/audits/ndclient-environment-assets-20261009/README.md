# NDClient environment migration handoff — sources, authored data and remaining gaps

9 October 2026. **Source consolidation and subsequent authorized copy complete. Existing source information is consolidated here, including sources outside the unified catalog. No bindings changed or new mechanics implemented.** This is an evidence inventory under the [complete implementation plan](../../NDCLIENT_IMPLEMENTATION_PLAN_COMPLETE_2026-10-08.md), not a competing plan or a renderer-completion claim.

The user approved the four proposed environment intake categories: (1) original Fantasy environment art; (2) currently selected animation/media and companions; (3) existing registration, height, contact and assembly records; (4) additional reviewed art, keeping unselected candidates distinct. “Migrate” means copy, preserving originals. This handoff consolidates the actual inputs for that copy and records what remains unresolved. The user's “group E” here means the environment collection at `fantasy-unified-catalog`, not portraits/icons from an earlier lettering scheme.

## Completed copy

Copied into `/home/tommaso/Dev/NDClient` using
[`tools/prepare_environment_assets.py`](/home/tommaso/Dev/NDClient/tools/prepare_environment_assets.py):

- **8,840 source image records → 7,735 unique PNGs / 585,362,999 bytes (558.2 MiB)** in the existing ignored `.media/objects/` store.
- **3,687 exact reference snapshots / 182,498,742 bytes (174.0 MiB)** under `.runtime/environment-assets/authoring-reference/`, including the subsequent 465-file metadata delivery below. Original scene and adjacency documents account for part of this size; these are existing authored inputs, not generated gameplay logs.
- Current selection included: **324 Fantasy animation banks, 556 world/fixture/water resources**, device media and all twelve engine-only hatch/trap companions listed below. Indoor-door leaves and selected masks are included.
- The combined A/B/environment media store contains **2,739,279,241 bytes (2.551 GiB)**. Reference snapshots and receipts are separate.

The [copy summary](/home/tommaso/Dev/NDClient/.runtime/environment-assets/summary.json),
`files.jsonl`, `references.jsonl`, `entries.json` and `excluded.jsonl` retain source paths,
hashes, copied locations, existing statuses and exclusions. Every copied unique
image and reference was compared byte-for-byte with its source. Artwork and
receipts are ignored by Git. Original files were not modified, and no image was
resized, recolored or repacked. Arena/crowd media, project/archive files, review
composites and unrelated generic effects were excluded; shared adjacency metadata
was preserved. Desert is deferred. Candidate artwork remains candidate artwork;
copying it does not select it for runtime. The subsequent authoring delivery
resolves the named missing records, with the qualifications below.

## Missing metadata received — 9 October

Source: [HANDOFF.txt](/mnt/c/Users/tommaso/Documents/assets/fantasy-unified-catalog/data-authoring-2026-10-09/HANDOFF.txt).
The exact delivery is copied under
[`authoring-reference/catalog/data-authoring-2026-10-09/`](/home/tommaso/Dev/NDClient/.runtime/environment-assets/authoring-reference/catalog/data-authoring-2026-10-09/).
Its **465 text/data/source-evidence files total 8,810,760 bytes (8.4 MiB)**.
No new images, review galleries or Blender projects were copied. Existing media
and native selections are unchanged. The importer includes this delivery in a
full intake and can supplement an existing intake with `--authoring-only`.

The combined `authoring-records.json` contains **60 unique catalog identities**:

| Requested group | Records | Delivered data owner |
|---|---:|---|
| Disputed B13/B44/B45 | 3 | `misc-profiles.json`: qualified identity, member solids, cloth/shadow exclusions, physical contacts |
| Modified Misc families listed below | 30 | `misc-profiles.json`: role/mount proposals, footprints, member geometry, state clearance and source-view contacts |
| Generated interiors listed below | 9 | `interior-decal-profiles.json`: measured source meshes/cameras, mount/contact/clearance, timber-flight contacts |
| Generated indoor doors | 6 | `door-assemblies.json` and `DOOR-ASSEMBLIES-HANDOFF.txt`: exact pairs, frame/leaf/header separation, contacts and explicit physical-mount limitation |
| Decorative decals listed below | 12 | `interior-decal-profiles.json`: floor/wall receivers, anchors, orientation, application-size proposals and existing material/alpha |

`profiles.csv` provides the record index. `evidence/` retains the measurements,
source snapshots, arithmetic and independent review. `VALIDATION.json` reports
60 records, 900 checked source hashes and seven unchanged protected inputs;
`BROWSER_VALIDATION.json` concerns the author's review page. These are authoring
receipts, not production renderer or gameplay acceptance. Source-relative art
links still refer to the original catalog; the existing image receipt locates
the separate artwork copies. The CSV inventories below retain their original
engine/catalog observations; this section adds the newly received authoring.

### Data now available, constraints still to respect

- **All six doors retain `shared_physical_mount_validated=false`.** The 56
  recovered door/header occurrences establish logical placement and per-view 2D
  montage. Measured door-local E/S/W/N quarters are 0/3/2/1; the preserved montage
  anchors rotate as 0/1/2/3. S/N differ by (-56,+28)/(+56,-28) unscaled pixels.
  Do not certify a coherent 3D mount, swap source rows or compensate in rendering
  code. Five primary pairings are recovered; original Shabby's G10/G1 pairing is
  a proposal. Preserve the signed frame feet below the source floor.
- **The timber flight is a distinct 12-tread source:** floor-to-top rise
  0.908693 height steps; entry-to-exit 0.822968. Preserve these measured values
  and contacts. It is not the existing two-step staircase and must not be
  stretched or rounded to fit an unrelated landing.
- **Estimates remain labelled.** B13 is a qualified supported-platform proposal
  conflicting with the current loose-floorboard identity; B44's apparent lower
  member is shadow, while the leaning pole/crossbar are solid; B45 is upright.
  Contacts/member profiles now exist, but copying them does not change native
  identities. Other visually estimated dimensions retain their uncertainty.
- **Use component geometry, not solid envelopes.** Keep cage openings, annular
  rims, roof panels, clearance and cloth exclusions. Preserve
  `geometry_schema_notes`: capsule axis and radius define the solid; capsule
  `z_steps` describes the axis interval, not its radius-expanded bounds.
- **Contact and pivot stay distinct.** For physical contact `c`, source pivot
  `p` and mount `M`, use `position=P(M)+scale*(p-c)` with `pivot=p`; geometry uses
  the same mount. Preserve measured camera/unit transforms; atlas coordinates
  are UV data and camera/height transforms apply once. Existing selected
  stairs/cliffs, corrected tables, larger props and adjacency remain intact.
- **Decals are receiver decoration.** Their source alpha already includes 0.6
  opacity; do not apply it again. No new damage, slipperiness or collision follows.

Remaining decisions are canonical adoption/selection, the explicit door physical
registration conflict, and the separately deferred Fork/trap-style/destruction
choices. This delivery contains no new depth/normal exports and does not establish
a blanket re-export requirement. It supplies the requested metadata; it does not
resume renderer implementation or create another gameplay registry.

## Start here: the complete information to migrate

The unified catalog is an art browser and one source collection. **The migration input is the union of the current engine selection, original artwork, authored workshop registrations, source assemblies and the corrected editor terrain data.** Existing information below is part of the handoff regardless of which repository currently stores it. The inventory is a navigation aid, not the scope boundary.

| Information needed | Exact current source | What to carry forward |
|---|---|---|
| Selected environment animation, state and attachment media | Engine `game/data/environment_art.json` | All selected non-Desert banks, door/frame selections, props/traps, wreck states, selection/aperture masks and attachment-dependent destruction selections. |
| Actual registered source values and media paths | [runtime-metadata.csv](runtime-metadata.csv) | Each row now includes the **absolute source owner, JSON pointer and actual authored values**: pivots, source cell/scale, pose registration, timings, depth calibration or static geometry. Full per-frame regions remain in the pointed canonical JSON. |
| Exact accepted prop source and integrated patches | [selected-prop-sources.csv](selected-prop-sources.csv) | All 84 current source declarations, actual scale/pivot/state-frame overrides, and resolved metadata locations in the unified archive and original study when present. |
| Physical prop height, footprint and blocking | Engine `dnd/content/items/world_prop_builders.py::WORLD_PROP_PROFILES`; `authored_item_definitions.py`; `environment_item_builders.py` | Actual `vertical_extent_steps`, footprint offsets, material, movement/optic/propagation channels, occupancy and debris policy. Server facts carry resulting placements; do not duplicate native rules into the client. |
| Door height/mechanism; window parent/insert height and opening behavior | Engine `door_profiles.py::DOOR_PROFILES`; `window_definitions.py::WINDOW_DEFINITIONS`; `window_builders.py`; `game/data/window_media_sources.json` | Doors generally have a two-step profile; lift gates block movement rather than silently becoming opaque walls. Window families have two-step wall profiles and separate insert semantics. Preserve selected family's values, masks and physical placement. |
| Static world resources, selected terrain and fixture phases | Engine `game/data/assets.json`, `game/data/world_bindings.json`, `game/data/portals.json` | Original source pivots/scale/crops, terrain family selection, current stair contacts/cliff profiles, torch/lever/trap phases, hatch front/overlay and aperture data. |
| Full original environment family source | `/mnt/c/Users/tommaso/Documents/assets/fantasy-unified-catalog/a-original/vendor/` and matching `a-original/unity-import-provenance/` | Original artwork and relevant import pivots/crops. Preserve chosen metadata without needing duplicate Unity payloads/ZIPs. |
| Corrected prop contacts and multi-cell registration | `/mnt/c/Users/tommaso/Documents/assets/environment-production-audit/placement-registration-53/` | `placement-registration.json`, `table-anchor-patch.json`, `larger-footprint-patch.json`; source-ground and overhang evidence, not just the latest copied PNG. |
| Architecture family identities and mechanism mapping | `/home/tommaso/.codex/worktrees/23a9/dnd_engine/output/environment-sprites/architecture-handoff/backend-mapping.json` | Original wall/door sources, art family IDs, proposed height profiles and mechanism distinctions. Preserve its proposal/verification status. |
| Door authoring source | Same worktree `output/environment-sprites/door-workshop/families/<family>/metadata.json`; selected generated doors' metadata paths in catalog CSV | Complete family, matching closed/open source, frame/leaf relation, pose offset, contact and animation states. |
| Eight authored prefab layouts | `/home/tommaso/Dev/terrain-prefab-study-2026-09-24/house-prefabs/room-dressing/prefab-review/0-layout.json` through `7-layout.json` | Parts with family/pose/position/base height/assembly level; surfaces, roof strategy, terraces, footprint and attachment sockets. Original copies also exist in worktree `23a9` at the corresponding `output/environment-sprites` path. |
| Four original composed source examples | `/mnt/c/Users/tommaso/Documents/assets/arena-study/prototype-v1/grid-kit/constructor/review/unity-reference/compositions.json` | `patches`: timber-service-court, masonry-house, quay-store, stone-court; each retains exact placements and directional contacts. These are reusable source evidence, not arena crowd content. |
| Source family adjacency and finishes | Unified catalog `c-new-props/arena-kit/tile-connections.json`; `constructor/themes/{ground-sources,roof-sources}.json`; original constructor `themes/source-manifest.json`, `encounter-art/{unity-motifs,manifest}.json`, `DISTRICT_RULES.md` | Actual joins, source finishes and grouped motifs. Preserve these even though arena geometry/crowds are excluded. |
| Corrected multi-height terrain semantics | `/home/tommaso/Dev/NeuroMapEditor/src/model/causalHeight.ts`, `src/import/compilePhaseOne.ts`, `src/model/types.ts`, `src/model/lattice.ts`, `src/render/spritePresentation.ts` | Explicit support deltas/footprints, downhill faces, one-/two-step rises, stair lane/contact topology, owner rebases and exact sprite mapping. The correction functions are part of the recoverable authoring information. |
| Original/editor occurrence evidence | NeuroMapEditor `public/assets/unity-reference/{scene,semantics,manifest}.json`, `docs/PHASE_ONE_IMPLEMENTATION_RECORD.md` | Original occurrence provenance **plus** later corrected ownership. Reading only the original scene discards the reviewed corrections. |

### Concrete placement and height information already available

These are current documented values, not suggestions to invent a new binding:

- **Engine projection:** unzoomed `P(x,y,H) = (64*(x-y), 32*(x+y)-64*H)` after camera-quarter rotation of XY. A whole assembly raised one height step moves its contact up 64 pixels. One source-to-world conversion and one camera transform apply to every related channel.
- **Mounting:** an object's `placement.base_height_steps` is its mount. `top_height_steps` and a neighbor's floor height are different values. Owner/contact, physical edge and image pivot are separate. Attachments retain parent owner/direction/base and their own source registration.
- **Current cliff:** `world_bindings.json#/terrain_cliff` has `rise_steps=2`, `upper_support_offset=[0,0]`; its art-pose face pairs are e→east+south, s→north+east, w→west+north, n→south+west. Those face pairs are not the wall-corner table.
- **Current two-step stair:** `world_bindings.json#/terrain_stairs` has supports `[[0,0,0],[-1,0,1],[-2,0,2]]`. Source contacts lower/middle/upper are e `[(160,224),(96,128),(32,32)]`, s `[(96,224),(160,128),(224,32)]`, w `[(96,192),(160,160),(224,128)]`, n `[(160,192),(96,160),(32,128)]`. Its pivot is the lower contact. Keep the flight rather than painting a flat floor over the middle contact.
- **Editor low banks:** G1–G5 and G8–G11 have a 64-pixel / one-step support relation. G1–G5 and G8–G11 use different directional support mappings. `causalHeight.ts` contains the reviewed convex/concave support footprints and the G5 owner exception; preserve these rather than deriving all corners from one image name.
- **Editor tall cliffs:** G12–G14 and G18–G22 have a 128-pixel / two-step support relation. Their `elevationBoundary` declares orientation, downhill faces, supported-surface delta and footprint. The compiler records reviewed source-owner rebases once.
- **Editor stairs:** `elevationTraversalForAssetLabel` in `causalHeight.ts` gives G16 edge and G17 continuation lanes, `totalZDelta=2`, `totalLiftPx=128`, entry/midpoint/top/supported-surface contacts and Q4 points. Width continuation does not add another rise. The E example is owner `(0,0,z0)`, midpoint `(0,0,z1)`, stair top `(-1,-1,z2)`, supported terrain `(-2,0,z2)`. This richer source assembly is distinct from the selected production three-support flight above.
- **Coordinate convention:** the editor uses +Y south and Q4 with four units per macro cell; native engine cardinals use their own explicit mapping. Preserve the conversion from the source handoff rather than reusing label strings as vectors.
- **Existing Fantasy-bank door pose contract:** physical pose selects the external frame; bank pose is `[e,s,w,n][(physicalIndex-pose_offset+4)%4]`. Fantasy C1/C3 have offset 1. That existing contract uses a shared frame/leaf physical mount; it does not certify the six generated indoor-door assemblies, whose new records explicitly leave shared physical mounting unvalidated.
- **Actual registrations:** legacy D1/D2/D6 cell 256, pivot `(128,207.36)`, scale `128/127`; selected stone floor cell 256, pivot `(128,208)`, scale 1; fixed padded wall/window banks cell 320, pivot `(160,240)`, scale 1. Indoor Elegant has e `(100,198)`, s `(156,198)`, w `(156,226)`, n `(100,226)` at scale `128/127`. Do not normalize these differing registrations to a universal pivot.
- **Props:** B37/B38 corrected pivot `(192,204.5)` is already selected. Larger two-cell source registrations include e `(160.25,255.485)`, s `(223.75,255.485)`, w `(223.75,287.235)`, n `(160.25,287.235)` for the specific patched families; their native footprints and optional optical/overhang caveats remain in the matching study/profile.
- **Source-space channels:** packed `rect` is UV selection, not position. Mounting pivot differs from `ground_origins_by_pose` used for depth calibration. Color/depth/normals/masks/sockets use the same source pose and frame mapping. Editor occurrence pixel offsets remain separate from cell deltas and source scale.

These values and source locations are included so migration can use the work already done. **No rediscovery or new export is required merely because the unified art catalog omitted a field.** Remaining uncertainty is limited to the specific unselected roles, source caveats and genuinely new surface/light representation described below.

## Remaining backend and metadata differences

- **No missing builder was found for any of the 138 native IDs explicitly associated with artwork in the catalog.** This verifies registered definitions, not correctness of every gameplay transition. Selected doors, chests, furniture, windows, walls, devices and structural traps already have native owners.
- **Some art is not implemented as selected content.** Thirty reviewed modified Misc families and nine generated interior appearances have no selected current native/media association. Fork has no assigned gameplay/media binding. Alternative trap styles and fixture destruction candidates are also unselected. This does not imply dozens of missing simulation systems: existing props/traps/devices can provide mechanics after their intended role is specified.
- **The 60 requested authoring records have arrived**, as detailed above. They include qualified B13/B44/B45 interpretations, member geometry, contacts and receivers; they do not resolve canonical selection, the door physical-mount conflict, or the unpopulated new surface/normal contract in the 324 selected animation banks. Existing depth, source pivots, collision profiles, contacts and assembly evidence must be retained.
- **The catalog is not a complete runtime package.** It omits 12 current packed/hatch image files and several current metadata owners. Those files exist in the backend; they do not need to be recreated.

## Complete inventories and how to read them

| File | Coverage | Meaning |
|---|---|---|
| [catalog-assets.csv](catalog-assets.csv) | All **760 catalog rows**, with 20 explicit exclusions | One row per asset family/package. Exact catalog ID, source example, declared native IDs, separately identified existing mechanism, selected banks/resources, available source JSON fields, Unity sidecar evidence, placement classification, actual architecture profile and source-assembly/terrain-semantics links, and specific gap notes. |
| [runtime-metadata.csv](runtime-metadata.csv) | **883 current registrations**: 324 animation banks, 556 world/fixture/water resources, 2 devices, 1 hatch shell | Absolute source owners/JSON pointers, actual authored values and media paths, numeric depth/normal availability, and catalog copy omissions. Resource rows may be frames of one sheet; these are not 883 separate files or behaviors. |
| [placement-evidence.csv](placement-evidence.csv) | All **53 entries** in the authored registration study | Native identity, selected height, grounding-evidence status, original source pointer and the author's interpretation/caveat. |

These files describe evidence; **they are not new runtime manifests or alternate bindings**. Existing JSON/Python owners remain canonical. `native_ids` is the catalog's explicit association; `existing_mechanism_context` is separately checked engine capability, not permission to bind that appearance. `selected_descendant_native_ids` means a modified version has an owner, not that every original variant is selected. Exact-byte resource matches identify unchanged pixels, not equivalent placement or compatibility.

The 740 non-excluded source rows comprise 475 static original families, 57 vendor animation packages, 127 modified families and 81 new appearances. The 57 vendor packages include generic effect packages and a skeleton explosion; their inclusion in the inventory does **not** select them as new spell/creature media or expand this environment step. Twenty excluded rows are 11 arena/crowd, 7 character-package, 1 ZIP archive and 1 imported-provenance entry. Desert is deferred and outside this catalog audit. The runtime source contains its six doors/48 banks; their absence from the Fantasy selection is intentional.

## 1. Backend coverage and genuine implementation boundaries

| Family / behavior | Existing owner | What remains |
|---|---|---|
| Selected props/furniture and destructible objects | `dnd/content/items/world_prop_builders.py` (76 profiles), `authored_item_builders.py`, `authored_item_definitions.py` | Preserve native footprint/height/material/channel/destruction data. Unselected artwork does not yet have an agreed physical profile or selected appearance. |
| Doors, openings, damage and wreck outcomes | `door_profiles.py`, `environment_item_builders.py`; current `environment_art.json` door selections | Existing 11 non-Desert door selections. Keep swing/lift mode, ownership, state and matching source family; shared stone framing is not universal compatibility evidence. |
| Ten window families and inserts | `window_definitions.py`, `window_builders.py`, `window_media_sources.json` | Keep wall and insert identities plus aperture/parent relationships. No new independent window mechanic is missing merely because the art is split. |
| Solid walls and destruction | Seven skin definitions in `environment_item_builders.py`, generic directional wall, `solid_wall_media_sources.json` | Four selected original debris banks and native retirement already exist. Remaining wall skins are content/assembly choices, not new wall mechanics. |
| Swinging blades/crushers | `trap_hardware_builders.py`, `dnd/spatial/mechanisms.py` | All 12 stone/wood × style combinations have native profiles and selected active/destruction media. |
| Spikes, darts, jaw, pressure plate, tripwire, gas vent | `ground_hardware_builders.py`, native spatial mechanisms/gas traps; `world_bindings.json` | Basic mechanisms and base media exist. Candidate destruction sequences and alternative appearances lack current media selection; preserve existing triggers/payload/control links. |
| Portal hatch | `ground_hardware_builders.py`, `dnd/spatial/portals.py`, `game/data/portals.json` | Existing hatch open/close/transport behavior and front/overlay split. Catalog omissions do not mean a new portal implementation is needed. |
| Levers, torches, barricade, boulder | `environment_item_builders.py`, `authored_item_definitions.py`, world bindings | Existing interactions/light/damage/blocking. The nine fixture destruction deliveries are unselected; barricade/boulder artwork also has no current sprite association found. |
| Cannon and arcane device | `environment_item_builders.py`, `spell_devices.json` | Implemented native devices and timed/pitched media with muzzle data. Fork is not selected and its intended behavior is unspecified. |
| Scenery, roofs, flora, decals and unused original skins | Existing world placement, terrain and prop systems where applicable | Decorative pictures need no individual gameplay class. Their selected appearance, mount/support/layer and physical behavior, if any, are content decisions. Do not derive a new water/poison/interaction mechanic from a picture name. |

Two broader native/presentation gaps affect asset use and are already in the master plan; they are **not asset-export failures**:

1. `WorldTileState` currently lacks the planned `observed_stair_run` shape information. When only a middle stair tile is visible, the renderer cannot reliably place the existing whole-flight art from that fact alone. The user approved revealing run direction/length; that owner amendment remains distinct from copying the existing source contacts.
2. Current native map support is not arbitrary stacked playable floors at the same XY. Existing elevations and layered visual occurrences must not be described as a completed multi-support backend. No asset import should invent bridges/upper-room gameplay to hide this boundary.

### Unselected reviewed modified families — all 30

Their variant metadata says independently accepted artwork. That is not a selected native role or a production renderer registration. Source animation metadata is present; current native/media association and role-specific placement/physical data are not selected. Reuse existing systems if these become gameplay objects; purely decorative uses need no new mechanic.

| Catalog asset | Source family |
|---|---|
| modified.fantasy.misc.b12 | Misc B12 |
| modified.fantasy.misc.b25 | Misc B25 |
| modified.fantasy.misc.b29 | Misc B29 |
| modified.fantasy.misc.b30 | Misc B30 |
| modified.fantasy.misc.b31 | Misc B31 |
| modified.fantasy.misc.b32 | Misc B32 |
| modified.fantasy.misc.b33 | Misc B33 |
| modified.fantasy.misc.b34 | Misc B34 |
| modified.fantasy.misc.b35 | Misc B35 |
| modified.fantasy.misc.b36 | Misc B36 |
| modified.fantasy.misc.b41 | Misc B41 |
| modified.fantasy.misc.b42 | Misc B42 |
| modified.fantasy.misc.b43 | Misc B43 |
| modified.fantasy.misc.b46 | Misc B46 |
| modified.fantasy.misc.b47 | Misc B47 |
| modified.fantasy.misc.b51 | Misc B51 |
| modified.fantasy.misc.b55 | Misc B55 |
| modified.fantasy.misc.b56 | Misc B56 |
| modified.fantasy.misc.b59 | Misc B59 |
| modified.fantasy.misc.b7 | Misc B7 |
| modified.fantasy.misc.c1 | Misc C1 |
| modified.fantasy.misc.c12 | Misc C12 |
| modified.fantasy.misc.c13 | Misc C13 |
| modified.fantasy.misc.c14 | Misc C14 |
| modified.fantasy.misc.c3 | Misc C3 |
| modified.fantasy.misc.d1 | Misc D1 |
| modified.fantasy.misc.d2 | Misc D2 |
| modified.fantasy.misc.d3 | Misc D3 |
| modified.fantasy.misc.d4 | Misc D4 |
| modified.fantasy.misc.d5 | Misc D5 |

### New appearances without a catalog native selection — every row

The following 49 rows include existing mechanics that the catalog failed to associate. Read the distinction in the middle column; this is not a list of 49 missing backend systems. Exact source metadata files/statuses are in the CSV. The other 32 new appearances have explicit native IDs: 12 interiors, 12 blade/crusher styles, 6 doors and 2 devices.

| Asset | Backend / selection status | Existing mechanism context |
|---|---|---|
| created.decal.candle-soot | decorative source; no dedicated backend mechanic required |  |
| created.decal.damp-streaks | decorative source; no dedicated backend mechanic required |  |
| created.decal.dirt-scuff | decorative source; no dedicated backend mechanic required |  |
| created.decal.moss-damp | decorative source; no dedicated backend mechanic required |  |
| created.decal.plaster-chips | decorative source; no dedicated backend mechanic required |  |
| created.decal.shoe-scuffs | decorative source; no dedicated backend mechanic required |  |
| created.decal.soot | decorative source; no dedicated backend mechanic required |  |
| created.decal.straw | decorative source; no dedicated backend mechanic required |  |
| created.decal.wall-crack | decorative source; no dedicated backend mechanic required |  |
| created.decal.watermark | decorative source; no dedicated backend mechanic required |  |
| created.decal.wax-drips | decorative source; no dedicated backend mechanic required |  |
| created.decal.wine-spill | decorative source; no dedicated backend mechanic required |  |
| created.weapon.fork | unselected device appearance; fork has no assigned gameplay |  |
| created.fixture.barricade | existing native fixture mechanics; these destruction candidates unselected | environment.blocker.barricade |
| created.fixture.boulder | existing native fixture mechanics; these destruction candidates unselected | environment.blocker.boulder |
| created.fixture.lever | existing native fixture mechanics; these destruction candidates unselected | environment.trap_lever |
| created.fixture.spikes-coated | existing native fixture mechanics; these destruction candidates unselected | environment.trap.spikes |
| created.fixture.spikes-coated-bloodied | existing native fixture mechanics; these destruction candidates unselected | environment.trap.spikes |
| created.fixture.spikes-plain | existing native fixture mechanics; these destruction candidates unselected | environment.trap.spikes |
| created.fixture.spikes-plain-bloodied | existing native fixture mechanics; these destruction candidates unselected | environment.trap.spikes |
| created.fixture.torch-standing | existing native fixture mechanics; these destruction candidates unselected | environment.standing_torch |
| created.fixture.torch-wall | existing native fixture mechanics; these destruction candidates unselected | environment.wall_torch |
| generated-hanging-utensils | unselected generated appearance |  |
| generated-papers-and-ink | unselected generated appearance |  |
| generated-tableware | unselected generated appearance |  |
| generated-timber-stair-flight | unselected generated appearance |  |
| generated-tool-rack | unselected generated appearance |  |
| generated-wall-candle-holder | unselected generated appearance |  |
| generated-wall-shelves | unselected generated appearance |  |
| generated-wash-basin | unselected generated appearance |  |
| generated-washstand | unselected generated appearance |  |
| created.trap.dart-projectile | delivery media for existing dart launcher; not an independent backend entity | spatial_effect.environment.dart_launcher |
| created.trap.darts | existing mechanism and base media; catalog omitted association | environment.trap.dart_emitter |
| created.trap.darts-brassbound | existing mechanism; appearance variant unselected | environment.trap.dart_emitter |
| created.trap.darts-fortress | existing mechanism; appearance variant unselected | environment.trap.dart_emitter |
| created.trap.hatch | existing mechanism and base media; catalog omitted association | environment.trap.portal_hatch |
| created.trap.hatch-brassbound | existing mechanism; appearance variant unselected | environment.trap.portal_hatch |
| created.trap.hatch-fortress | existing mechanism; appearance variant unselected | environment.trap.portal_hatch |
| created.trap.jaw | existing mechanism and base media; catalog omitted association | environment.trap.jaw |
| created.trap.jaw-brassbound | existing mechanism; appearance variant unselected | environment.trap.jaw |
| created.trap.jaw-fortress | existing mechanism; appearance variant unselected | environment.trap.jaw |
| created.trap.plate | existing mechanism and base media; catalog omitted association | environment.trap.pressure_plate |
| created.trap.plate-hex | existing mechanism; appearance variant unselected | environment.trap.pressure_plate |
| created.trap.plate-long | existing mechanism; appearance variant unselected | environment.trap.pressure_plate |
| created.trap.plate-round | existing mechanism; appearance variant unselected | environment.trap.pressure_plate |
| created.trap.tripwire | existing mechanism and base media; catalog omitted association | environment.trap.tripwire |
| created.trap.vent | existing mechanism and base media; catalog omitted association | environment.trap.gas_vent |
| created.trap.vent-brassbound | existing mechanism; appearance variant unselected | environment.trap.gas_vent |
| created.trap.vent-fortress | existing mechanism; appearance variant unselected | environment.trap.gas_vent |

The nine generated interiors without a selected current association are **hanging utensils, papers and ink, tableware, timber stair flight, tool rack, wall candle holder, wall shelves, wash basin and washstand**. A timber stair drawing is not yet a traversable registered flight. Wall-hung decorations need an actual mount, and lit candle behavior would need an explicit selection; none of that is implied by copying the picture.

The twelve static decals are **candle soot, damp streaks, dirt scuff, moss damp, plaster chips, shoe scuffs, soot, straw, wall crack, watermark, wax drips and wine spill**. Their media exists, but no current placement/material binding was found. Existing gameplay residues are separate and must not be silently assigned these appearances.

## 2. Metadata gaps and the metadata already authored

### Existing data — preserve it instead of regenerating it

- All 475 original static families and all 57 vendor animation packages have matching Unity image sidecars in this catalog. Source crop/pivot/import metadata exists. A Unity sprite pivot is **not** a measured world height, physical footprint, mount or compatibility rule.
- All **302 unique variant-metadata JSON paths** referenced by non-arena catalog rows exist and were read. No missing referenced variant JSON was found. A parsed file alone does not establish that its semantics or geometry are correct.
- Some current wall/debris/window catalog rows have no `variants[].metadata` entry but do have current bank data and separate source-owner JSON. They are not “missing all metadata.”
- Five full catalog snapshots equal the current engine documents: `environment_art.json`, `environment_prop_sources.json`, `window_media_sources.json`, `solid_wall_media_sources.json`, `spell_devices.json`.
- `environment_art.json` has 372 banks overall; its non-Desert selection is 324. The Fantasy subset has 11 door, 113 prop, 12 structural-trap selections and 2 generic wall-destruction assignments. Wreck identities are retained in the full document.
- Native physical metadata lives in Python profile definitions and `WorldPlacementSpec`, not in an imaginary `environment_prop_definitions.json`. That proposed filename exists in neither backend nor this catalog and is not a required missing file.

### Three disputed selected assets — new evidence received, native reconciliation pending

| Source | Current identity | Delivered evidence / remaining discrepancy |
|---|---|---|
| misc-b44 | environment.furniture.short_red_banner | New member/contact evidence identifies leaning pole and crossbar; apparent lower member is shadow. Cloth is not solid opaque furniture. Native adoption remains pending. |
| misc-b45 | environment.furniture.tall_red_banner | New member/contact evidence identifies an upright pole, excluding cloth/shadow from solid geometry. Native adoption remains pending. |
| misc-b13 | environment.furniture.loose_floorboards | Qualified supported-platform proposal with trestles/contacts; source art conflicts with the selected loose-floorboard identity and historical partition. Do not admit as flat_ground. |

These assets currently have selected native identities despite the source caveats. That is a real unresolved content-authoring discrepancy, not proof that their existing implementation is correct. Do not conceal it with a convenient floor decal, tall solid box or guessed pole.

The original 53-registration study classified **20 bulk props with unconfirmed ground, 8 bulk props with optical caution, 10 coarse grid placements, 10 existing flat-surface policies, 2 corrected one-cell registrations, and the 3 deferred cases above.** Preserve that study as provenance; the new named profiles supplement it. Neither source claims exact hidden 3D surfaces for every original family.

B37/B38 table pivots already carry the correction to `(192, 204.5)`. The selected large-prop records retain authored footprint/pivot adjustments. These are **present corrections to preserve**, not work to redo. In particular the small wooden table uses a different source family; its different pivot is not evidence the B37/B38 patch was forgotten.

### Precise gap classes

| Gap | Affected assets | Data that exists | Missing or incomplete |
|---|---|---|---|
| Current appearance/role selection | 30 modified families; 9 new interiors; Fork; alternative trap styles; decals | Original pixels and source metadata; new role/contact/member/receiver proposals for the named Misc, interiors and decals | Canonical adoption/selection; Fork and alternative trap choices are outside this delivery. Do not request the delivered profiles again. |
| Ground/support/mount interpretation | B13/B44/B45; caution/coarse entries in the 53-row study | New qualified member/contact profiles for the named assets, plus preserved study/native policies | Reconcile current native identities with the evidence; retain uncertainty on visual estimates. No invented geometry. |
| Asset-specific physical definitions for unused originals | Original families without direct current selection or an explicitly associated descendant; individually listed in CSV | Unity import metadata, source art and some authored assemblies | The CSV includes the architecture proposals where present (87 original Fantasy wall families), source assembly occurrences and editor terrain contracts. Any remaining production role/physical choice must use that evidence; scenery may need only presentation placement. |
| Compatibility and assembly selection | Door/frame/wall/window/roof/stair assemblies, especially unused combinations | Source layouts/adjacency/window records and six new exact indoor-door assembly records | Six indoor-door shared physical mounts remain unvalidated, including the documented S/N conflict. Canonical assembly consumption is not implemented. Similar materials do not prove compatibility. |
| Whole-flight stair and boundary semantics | G12/G13/G16/G17 and additional stair/cliff art | Selected cliff/stair profiles and contacts; corrected editor semantics; new measured timber-flight contacts/rise | Consume existing data. The new fractional-rise flight cannot inherit the selected two-step profile. Partial observed run fact remains native work. |
| New light/depth surface representation | 324 selected animated banks, static world assets, devices, hatch | Legacy depth for some banks; 12 current resource geometry profiles; source workshop depth data | The new common normal/surface representation is not populated across all selected assets; existing registered geometry and source contracts above are available now. Per-bank fields are in the runtime CSV; source depth/geometry and the terrain/editor contracts above remain inputs even when that bank field is empty. |
| Fixture destruction selection | All 9 created fixture rows; nonstructural trap destruction variants | Existing native breakability plus candidate color/depth/timing metadata | Candidate media not selected by `environment_art.json`; do not mark native destruction itself missing. |

### Depth and normals: new capability, with an exact inventory

Of the **324 selected non-Desert banks**, **88 have legacy `actor_depth` metadata** (default `rg16le_contact`), **236 have none**, **0 populate `surface_geometry_by_pose`**, and **0 register normal maps**. Every bank is named in the runtime CSV. Legacy contact depth is not automatically the same data convention as the accepted Fireball's depth/normal channels.

Among the **556 world/fixture/water resource registrations** inspected, 12 have geometry: four stone wall straight views, four stone door-frame views and four stair views. Cliffs also have role/rise/corner/support metadata in `world_bindings.json`; absence of a resource-level geometry field does not erase those records. Water has its own existing normal resource and shader parameters; the “zero normals” statement applies to the animated environment bank table, not all assets.

Cannon/arcane have pitch banks and per-frame muzzle pixels but no registered numeric depth/normal channels. Hatch has a front/overlay split and apertures but no numeric depth/normal channel. Workshop sources include `depth-geometry.json` and depth images for multiple families; “not registered in the current bank” is not “never exported.”

**No universal re-export requirement follows.** Flat floors can use their registered plane; planar walls may use existing geometry; decorative overlays need only their intended receiver. Request new sampled surfaces/normals where the asset's required composition/light behavior cannot be represented by its existing authored data. Copy existing evidence first. Do not recover XYZ arrays, use alpha bounds as collision or fabricate per-family geometry to fill empty columns.

## 3. Additional existing migration inputs beyond the unified catalog

### Twelve current image files absent from the catalog by content hash

These were checked against the catalog's recorded SHA-256 inventory. The current engine files were hashed; absence means no equal file in that inventory, not a missing source file. This extends the earlier ten-sheet finding with two portal-hatch companions.

- `game/assets/environment/portal/hatch-front.png`
- `game/assets/environment/portal/hatch-overlay.png`
- `game/assets/packed/environment/lever/256x256-000.png`
- `game/assets/packed/environment/spikes-blood/256x256-000.png`
- `game/assets/packed/environment/spikes-coated/256x256-000.png`
- `game/assets/packed/environment/spikes/256x256-000.png`
- `game/assets/packed/environment/trap-workshop/dart-projectile/256x256-000.png`
- `game/assets/packed/environment/trap-workshop/darts/256x256-000.png`
- `game/assets/packed/environment/trap-workshop/jaw/256x256-000.png`
- `game/assets/packed/environment/trap-workshop/plate/256x256-000.png`
- `game/assets/packed/environment/trap-workshop/tripwire/256x256-000.png`
- `game/assets/packed/environment/trap-workshop/vent/256x256-000.png`

The 12 indoor-door `leaf_path` files are a different case: they are absent from the catalog's `production-media` directory **but present elsewhere under `c-new-props/indoor-door-animation` with matching hashes**. Preserve those paths or copy the current engine versions; do not report them as absent from the entire catalog.

The selected bank closure has 1,030 distinct image paths: 1,018 in the catalog's production-media area plus the 12 leaf companions. Device media contributes its own 72 files. These counts overlap neither the notion of bank count nor frame count and are not imposed runtime budgets. No full archive or 10 GB catalog copy is needed to repair these omissions.

### Authoritative metadata owners to include in migration

| Existing owner | Preserve for |
|---|---|
| `game/data/assets.json` | Current crops, pivots, scale, geometry, water material and static resource registration. |
| `game/data/world_bindings.json` | Selected materials/poses, cliff rise/support/corners, stair contacts/flight, fixture state frames and source rates. |
| `game/data/portals.json` | Hatch front/overlay images, phases, timing and apertures; portal effect dependencies belong to the later VFX family as well. |
| `dnd/content/items/{world_prop_builders,door_profiles,window_definitions,trap_hardware_builders,ground_hardware_builders,environment_item_builders,authored_item_definitions}.py` | Existing native behavior and physical profile owners; consumed through native facts rather than duplicated into a new client rules table. |
| `/mnt/c/Users/tommaso/Documents/assets/environment-production-audit/placement-registration-53/` | All 53 grounding reviews, table correction and larger-footprint patches, including unresolved evidence. |
| `/home/tommaso/.codex/worktrees/23a9/dnd_engine/output/environment-sprites/architecture-handoff/backend-mapping.json` | Architecture-family source mappings. |
| `/home/tommaso/Dev/terrain-prefab-study-2026-09-24/house-prefabs/room-dressing/prefab-review/` | Existing source assembly layouts; original worktree pointers also remain evidence. |
| `/mnt/c/Users/tommaso/Documents/assets/arena-study/prototype-v1/grid-kit/constructor/review/unity-reference/compositions.json` | Original placements and source-compatible assemblies, separate from crowd/arena content. |
| `/home/tommaso/Dev/NeuroMapEditor/src/import/compilePhaseOne.ts` and `src/model/types.ts` | Corrected boundary/traversal/support/visual-layer semantics. Rich fields are derived by the importer, not all stored in the raw original `semantics.json`. |
| `/home/tommaso/Dev/NeuroMapEditor/public/assets/unity-reference/{scene,semantics,manifest}.json` | Preserved original scene references and imported ownership evidence. |

The catalog itself contains useful shared rules **inside the otherwise excluded arena folder**: `c-new-props/arena-kit/tile-connections.json` and `constructor/themes/{ground-sources,roof-sources}.json`. Excluding arena geometry and crowds must not discard those reusable source-rule records. Source-reference paths above are preservation pointers, not a claim every family already has a complete runtime assembly schema.

The [wall/door/elevation handoff](../../PIXI_WALL_DOOR_ELEVATION_POSITIONING_HANDOFF_2026-10-08.md) and [asset recovery handoff](../../NDCLIENT_ENVIRONMENT_ASSET_RECOVERY_HANDOFF_2026-10-08.md) specify how those records relate: physical owner versus rendered edge, physical facing versus bank pose, base height versus support height, authored cliff rise and stair contacts, original pixel units and depth origin separate from placement pivot. Preserve these meanings; copying only media JSON would repeat the previous failure.

## 4. Boundaries and evidence

This pass reads the current engine media/physical owners, actual native builder registry, source variant JSON, registration studies, source prefab/architecture/composition records and corrected editor terrain code, cross-referenced through the catalog. It confirms all 138 catalog-native IDs exist in `DIRECT_ITEM_BUILDERS`; it does not instantiate every item, run gameplay tests or certify every source assembly. It matches unchanged current files by hash where needed, using the catalog's existing copy-verification hashes for the archive rather than rehashing 51,572 archived files. No asset inventory here is a GPU-residency requirement.

The CSVs deliberately preserve unselected/unverified states. There is no claim that all unused original scenery already has native gameplay, that all reviewed art is approved for runtime selection, that current coarse geometry is measured source geometry, or that bank existence proves correct rendering. The deleted client supplies no implementation evidence.

Canonical source hashes for this audit snapshot:

- `/mnt/c/Users/tommaso/Documents/assets/fantasy-unified-catalog/catalog.json` — `3345e16e34fec31256539663e375da9dac266e5dd6b922a20cb999e64058d346`
- `/mnt/c/users/tommaso/documents/dev/dnd_engine/game/data/environment_art.json` — `eb01e44e958e484676f786ba29d39ef03066979f79c7bd90b3bb522c407e0d0c`
- `/mnt/c/users/tommaso/documents/dev/dnd_engine/game/data/world_bindings.json` — `41f351b45c133bea469c0c39c81030ff2488b149630c4a1b89e691937b76f498`
- `/mnt/c/users/tommaso/documents/dev/dnd_engine/game/data/assets.json` — `90edc61feac2411b41a377ca544554e3455c00532cd394ddd4beaea2acd20242`
- `/mnt/c/users/tommaso/documents/dev/dnd_engine/game/data/portals.json` — `cd76c23f31968d9c66b4c4694c8943eb3d063b7afc3fb232f09d839394c2c9fe`
- `/mnt/c/Users/tommaso/Documents/assets/environment-production-audit/placement-registration-53/placement-registration.json` — `21e1148c5532ddb8c32f986f3f744ad0ddd77104b2abd90ecb6eb9a8b38fd353`
