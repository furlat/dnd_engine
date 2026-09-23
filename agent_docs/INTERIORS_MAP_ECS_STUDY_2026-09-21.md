# Interiors: native map and ECS study

Date: 2026-09-21. Role: anti-OOP/ECS and native map review. **Study only; no production changes or tests run for this document.** Read the current `RECOVERY_PLAN.md`, particularly its ownership, complete-lineage, subjective-replay and height commitments. This study supports the parent's forthcoming reviewed integration plan; it does not authorize the implementation sequence below.

Source handoff: [INTERIORS-CONSOLIDATED-HANDOFF.md](/home/tommaso/.codex/worktrees/23a9/dnd_engine/output/environment-sprites/house-prefabs/INTERIORS-CONSOLIDATED-HANDOFF.md). Its detached backend checkout is not the native authority. Code evidence below is from the current shared recovery checkout. No source hashes, asset audit framework, asset generation or unrelated optimization was introduced.

## Recommendation

First import one explicitly selected **single-floor furnished layout**, using the existing map, content builders, doors, object damage/remnants, observation and saved replay. Add only the native placement/content fields actually needed by that selection. Preserve furniture support and wall-style distinctions instead of substituting generic assets or invisible mechanics.

Genuine upstairs play is a separate spatial contract change: **multiple independently addressable supports at the same XY**. The existing Tile UUID is a good identity to preserve, with XY and elevation remaining physical data on that support. Actors, targets, visibility and tile effects must address the support as well. Merely adding object height bands, an actor `floor` flag, or a renderer cutaway cannot provide this.

That does not mean inventing a universal 3D world or flight/falling engine. The concrete target can be two floors, their staircase and a declared opening, using the existing event and ECS owners.

## What the handoff actually supplies

The handoff distinguishes native identities from art identities. The eight saved recipes contain fourteen floors; these are preview layouts, not native worlds. Installed doors and doorway traps should remain installed through their current owners.

Read-only inspection of `room-dressing/prefab-review/0-layout.json` found:

- `schema: parametric-house-v2`, six-by-seven footprint, two floors.
- 66 explicit support triples and 88 preview connections.
- A stair from `[3,1,0]`, via `[2,1,1]`, to `[1,1,2]`; separate lower/upper landings, run cells, opening cells and two-step rise.
- Furniture with explicit `footprint_cells`, `approach_cell`, facing and blocking intent.
- Tabletop attachments with parent IDs/socket names, and separate wall fitting heights in Blender units.
- An explicit warning that the preview graph assumes doors can be opened and is **not backend navigation**.

`1-layout.json` is a genuine one-floor candidate; it does not need its upper floors silently discarded. It has **96 physical floor cells but only 75 preview graph supports**: the exact 21-cell difference is the union of blocking furniture footprints. Its bed occupies `[7,2]` and `[7,3]`. `interiors.py:95` collects blocking footprints; lines 157–159 remove their nodes/edges from the preview walking graph; line 162 adds stair nodes back. Therefore `interior.supports` is **not the physical floor inventory**. Import floor coverage from level/terrain records, subtract actual stairwell openings where applicable, then register furniture occupancy independently. Destroying that bed must reveal the two existing supporting floor cells, not leave missing terrain.

`2-layout.json` has three floors and 185 preview supports. Its triples represent physical heights, including intermediate stair heights; treating the third number as an arbitrary storey index changes their meaning. The preview status is `visual_candidate_not_native_world_content`.

The import boundary must interpret these explicit authoring records. It must not execute the preview browser's animation state, treat every art part as a colliding world object, or use preview connectivity as proof that native locked/closed doors are traversable.

## Existing authority and the dependent surface

Line references identify concrete current contracts, not a claim that every related path has been tested in this study.

| Concern | Current evidence | Consequence for interiors / stacked floors |
| --- | --- | --- |
| Support identity and storage | `dnd/core/base_tiles.py:55` defines Tile as a condition-bearing support with XY, surface and height; `height` is five-foot steps at line 100. `dnd/core/gridmap.py:131` stores `dict[XY, Tile]`; its UUID index maps back to XY. | Native support identity already exists, but only one support may occupy a column. `set_tile` replaces the previous support at that XY (`gridmap.py:527`); it does not add a storey. |
| Object support and vertical placement | `dnd/types/world_placement.py:30` carries `tile_uuid`, XY, center/boundary kind, base/top height and orientation. `gridmap.py:2278` selects that Tile from XY; collision is checked against its local height bands at line 2324. | Wall mounting can reuse vertical placement concepts. An upper band is not an independent floor. The placement's Tile UUID is valuable for the later support migration. |
| Object footprint | `WorldPlacementSpec` at `world_placement.py:20` has kind, band occupancy and vertical extent; `WorldObjectPlacement` has one XY. `gridmap.py:1513` tests blockers at that single center. | There is no general horizontal footprint in this placement contract. Do not import a genuinely multi-cell blocking object as a one-cell blocker unless the authored physical footprint really is one cell. Establish the first layout's needs before adding footprint offsets. |
| Actor occupancy | `dnd/entity.py:779` commits XY and ground/air contact layer; `gridmap.py:2092` updates membership in the old/new XY Tiles. `entity.py:796` returns early when both XY and layer are unchanged. | Two actors on different floors at one XY cannot presently have separate support occupancy. Moving to another support at the same XY would currently be a no-op. |
| Ground/air is not a storey | `dnd/types/world.py:6` defines `OccupancyLayer` relative to local support. | Keep jump contact semantics intact. Do not encode upstairs as AIR or add flight to this integration. |
| Ordinary movement and stairs | `gridmap.py:1715` permits progressive elevation transitions using surface kind/slope axis; `compute_paths` at line 3316 returns XY-keyed distances and XY paths, using rectangular-grid BFS/Dijkstra at line 3501. | Ordinary terrain stairs are reusable for single-support height fields. General paths need support-addressed nodes to distinguish downstairs from upstairs. |
| Explicit connectors | `dnd/core/traversal_connectors.py:70` defines costs/direction/policy; endpoint runtime records have support Tile UUID/elevation at line 122. `gridmap.py:826` resolves endpoint XY to its one Tile. Non-passage endpoints must be distinct cardinal-adjacent XY at `traversal_connectors.py:100`. | Useful existing actions and identities, not stacked-floor support. Same-XY vertical connections cannot presently be authored. Don't replace every progressive stair step with a teleporter. |
| Connector execution | `dnd/actions.py:1158` has one shared `TraverseConnector`; its admitted source-exit `StepMovementEvent`, costs and position commit are at line 1449 onward. | Reuse its actual reaction/cost semantics if a selected ladder or discrete connector needs it. Ordinary staircase walking can remain ordinary Steps. |
| Connector presentation boundary | `game/event_record.py:39` has no concrete `TraverseConnectorEvent`; `game/presentation.py:614` retains selected movement families but the unhandled connector root becomes an ordinary header at line 629. Its native child Step retains endpoint elevations. | Connector mechanics do not prove that a fully authored climb/lift program is already wired into saved playback. If selected, connect that actual family explicitly; do not claim it complete based on its name or child Step alone. |
| Boundaries | `dnd/core/world_edges.py:36` identifies adjacent edges by two XY cells. `gridmap.py:2945` derives source/destination support UUIDs and height intervals after choosing the one Tile at each XY. | Existing movement/optical/propagation channels and height envelopes should survive. Boundary ownership needs the correct support when several floors share an edge in XY. |
| Walls and native item composition | `dnd/items/environment.py:44` provides the generic wall; its envelope is two steps at line 90. `dnd/blocks/base_item.py:731` already gives `WorldItem` passive `world_placement_spec` and `boundary_structure` fields. | Use data-driven structural content rather than a subclass for every wall image. Open timber, windows and rails need their actual channel/interval semantics. A pretty opening cannot be modeled as a solid opaque wall. |
| Wall appearance | `game/app.py:950` groups wall entries by XY and physical material; line 974 chooses stone versus wood banks. `BoundaryStructure` at `world_placement.py:73` contains kind/material/channels. | Different plaster/log/plank profiles sharing a material will currently collapse to the same family. Introduce/consume an authored presentation identity at the existing data boundary; don't make material names double as art-family names. |
| Sensory state | `dnd/types/senses.py:42` stores observed contact XY. `SensesSnapshot` at line 141 stores visible/seen cells, light and hazards by XY. Native field solving selects the one Tile at each XY (`dnd/blocks/sensory.py:657`). | This must distinguish supports before any floor is disclosed. A renderer cannot safely repair upstairs information that was merged with downstairs in a public snapshot. Preserve existing observer rules and event-time grants. |
| Native optical/light solving | `gridmap.py:3105` scans an XY FOV; `compute_light_fov` at line 3312 reuses that topology. `_compute_light_tiles` at line 3976 stores XY light contributions. | A stacked floor/ceiling is not an existing horizontal wall edge. Need explicit support/slab/opening semantics for vertical optical and propagation routes; never flood visibility along walking paths. |
| Spatial conditions | `dnd/spatial/area_conditions.py:42` owns one XY anchor and a set of XY affected cells. `gridmap.py:142` indexes those footprints; memberships compare actor positions with them (`dnd/spatial/memberships.py:269`). | Blood, traps, Web and Silence must not apply to every floor at matching XY. Ground residues need the receiving support; spatial areas need explicitly resolved support membership. Ground/air policy is a separate dimension. |
| Targeting/range | `dnd/core/base_actions.py:1217` obtains an XY target origin and measures XY grid distance. `dnd/core/elevation.py:24` already provides an independent support-height distance primitive; ordinary Senses distance remains XY (`sensory.py:212`). | Adding stacked supports requires examining actual target-origin/range/reach consumers. Do not change every distance formula merely because heights exist; identify which rules need support-aware location and preserve the project's chosen distance policy. |
| Recorded world | `dnd/core/events.py:794` already records Tile UUID, XY and elevation. `dnd/world_facts.py:36` and its reducer at line 130 collapse Tiles into an XY dictionary. `game/player_facts.py:502` repeats that key for public state. | The source facts contain a useful identity, but both native replay and public reduction currently overwrite an earlier same-XY support. Changing live storage alone is insufficient. |
| Recorded movement/observation | `StepMovementEvent` at `events.py:4522` retains XY and actual endpoint elevations. `SensoryUpdateEvent` at line 3287 uses XY visible cells and `x,y` light/hazard keys. | Elevation snapshots are useful historical facts but not an unambiguous support identity. Carry exact source/destination support through ordinary movement/admission/sensory facts and public projection. |
| Public disclosure | `game/player_projection.py:501` selects world Tiles from visible XY; connectors require both endpoint XY visible. | Upgrade the existing projection to the same support-addressed sensory facts. Do not send the whole building and rely on Pygame hiding unobserved storeys. |
| Picking | `game/projection.py:270` already defines a candidate with Tile UUID, XY and elevation; `pick_support` at line 290 consumes detached candidates. | Reuse it. Feed distinct disclosed supports, return their identity to actions, and verify ordering/cutaway selection with overlapping floors. Its existence alone does not establish current overlap ordering is correct. |
| World initialization | `dnd/scenarios/battlefield_catalog.py:1127` composes a cold world, then publishes `WorldInitializedEvent` before dynamic settlement. `dnd/world_authoring.py:194` handles ordinary placed-item world mutations. | The prefab importer belongs upstream of these owners. Initial state remains events. No preview server, runtime generator or live-world query is needed during replay. |

## A bounded single-floor integration

### Native content, not a second runtime

Select one genuine one-floor recipe and a finite set of required families. Resolve source art identities into normal item/content definitions and renderer bindings. Use the handoff's existing allowlist and explicit paths offline; no new runtime asset hashing or directory scanning.

Reuse:

- `StaticBlockerDefinition` (`dnd/content/items/authored_item_definitions.py:122`) for appropriate health-bearing static center blockers; it already has authored placement data and blocking policy.
- `WorldItem` for passive placed world geometry, including declarative boundary contributions.
- Existing sixteen door profiles and their action/state/destruction data. Opening a door must continue to change native channels, with the authored animation at the normal interaction contact.
- `StorageChest` for lid/loot/inventory semantics (`dnd/items/environment_interactables.py:451`). Style pairs are content/presentation data, not six independent chest mechanics.
- `BaseItem.destroy` (`dnd/blocks/base_item.py:508`) for real destruction, light/condition cleanup, native replacement and persistent remnant facts. Media is selected from the accepted observed event and remnant state.
- Torch/light owners for fixtures that actually illuminate, with explicit brightness and mounting choices; emitted light is never inferred from a painted flame.

Do not map all barrels to the oil barrel or all tables to campfire cooking. Thematic names do not authorize crafting, trading, resting or restraint mechanics. Decoration-only pieces should be explicit.

The generic chest is currently not targetable by default. Making its new destruction reachable requires authored HP/targetability, not just a bank mapping. There is also a concrete lineage issue to address when that feature is selected: the existing chest spill hook ignores `parent_event` and calls `item.place_on_grid(pos)` without it (`environment_interactables.py:489`). A breakable-chest acceptance case must keep content spill under the actual destruction cause; do not mask it with renderer-produced drops.

### Physical support is not inventory containment

An exposed cup on a table and an item inside a chest are different facts. Current world placement records support only a Tile. There is no parent-object/socket relationship in `WorldObjectPlacement`; `stored_in_uuid` describes container ownership, not a visible tabletop attachment. Current destruction cleans container membership and creates a remnant but has no shared table-supported-child release path.

For the first chosen attached prop, a small passive relation can identify its parent world object and authored support/mount, while keeping the ultimate floor support unambiguous. The existing destruction owner should resolve the selected outcome (detach/drop/destroy) and publish its real item/world facts in the same lineage. This is a demonstrated relation needed by the supplied data; it is not a reason to build a general physics graph, ownership manager or rollback framework.

Do not copy fractional Blender mounting height into the engine's five-foot support `height` field. Physical floor elevation, collision envelope, local attachment position and visual pivot/lift are separate meanings. Define the unit conversion at the intake boundary for selected content. Ground-baked destruction cannot be raised onto a wall; select a bank and final floor placement that actually agree.

### Layout acceptance and honest exclusions

Preserve explicit footprints, two-cell shared circulation, approached sides, door ownership/swing and furniture facing. Native collision and discovered actions must confirm the plan's legal routes. A chair's occupied sitting socket is not necessarily an empty walk-up square; sitting is not automatically a requested gameplay feature.

The proposed one-floor `1-layout.json` already contains a two-cell bed, so its faithful intake needs a small one-object/many-cells extension. The minimum coherent route is authored local occupied-cell offsets on the existing placement capability, resolved once through placement orientation, and the resulting committed footprint on the existing placement fact. Preserve one item UUID, one HP/condition owner, one draw identity and one destruction/remnant operation. GridMap's existing local band index (`gridmap.py:2364`) can index that same UUID at each occupied support; admission/removal/move must update all those memberships through the current placement owner. Do not create unrelated invisible blocker objects whose lifecycle can outlive the furniture.

The event's affected cells and sensory candidate invalidation must include the whole changed footprint, not only its anchor. Native approach/reach and collision need to query the same occupied cells. Observing a portion of a bed should not disclose unrelated room/floor state; check the existing single-contact projection when adding that exact partial-view case. A remnant must carry its own authored footprint/blocking result, so destruction releases cells according to the actual wreck rather than guessing from sprite bounds. This does not require changing ordinary item inventories, creature size, or every object into a collision mesh.

These are occupancy indexes over still-existing floor Tiles. They are not the floor support graph. A furniture cell may also carry a blood condition before or after the object breaks; deleting/recreating its Tile to represent blocking would lose that state and support identity.

Single-floor roof/cutaway selection is view policy. It must not remove collision, doors, lighting or native objects from the world. It can select only already disclosed scene material. Cosmetic grime decals can remain authored surface dressing; a floor coating that changes movement or damage belongs to the existing Tile/condition/spatial owners.

An intact single-floor house with supported furniture is a valid deliverable. A flattened copy of a multilevel house that overwrites its downstairs Tiles is not.

## Options for genuine multiple storeys

| Option | What it gives | Actual cost / limitation |
| --- | --- | --- |
| Separate floors as disconnected maps/scenes | A simpler game where a stair transitions between separately loaded floors. | Not one simultaneous building. Cross-floor sight, ranged attacks, light, areas and occupants are not shared. Current singleton `GridMap` also means even this needs an explicit world-transfer design. Do not sell it as transparent multistorey support. |
| Add a third coordinate everywhere | Different spatial addresses can coexist in a column. | Still requires all the same occupancy, FOV, conditions and wire migrations. A storey index is not physical elevation; actual height as the key makes elevation changes identity changes. It does not by itself specify neighbors or floor/ceiling blocking. |
| Address existing supports explicitly, retain XY/elevation as geometry | Several Tile UUIDs per XY; actors, items, boundaries and effects point at the correct support. Existing connector endpoint identities align with this. | Requires a coherent migration through the dependent surface above. UUID lookup plus a column index is sufficient; no generic scene-graph registry is needed. This is the recommended direction for simultaneous upstairs/downstairs play. |

For the recommended direction, retain Tile as the passive condition/system composer. Let GridMap own a direct support-ID lookup and the index from XY to supports. One resolved support reference should be authoritative at admission/movement. Avoid independent actor floor, actor elevation and actor Tile values with separate mutation paths; derive geometry from the selected support and record needed historical endpoint facts in events.

Keep three meanings distinct: **Tile identity** identifies the support and its persistent conditions; **occupied volume** describes the actor/object envelope relative to that support; **floor/slab occlusion** decides whether sight, light or propagation crosses the assembly between supports. Neither occupied furniture nor a roof-cutaway choice may create/destroy the support identity. An integer floor number or elevation alone does not encode any of these three contracts.

Preserve existing XY callers only where the map has exactly one eligible support or the caller supplies its current support context. There must be no implicit "highest floor", "first inserted floor" or renderer-selected floor in a mechanical lookup. A deliberate conversion for old single-support archives can resolve their recorded Tile UUID/XY facts; an ambiguous archive must not be assigned a guessed storey. The wire changes need an explicit compatibility/version decision, not universal default-zero fields.

Ordinary movement should traverse support-addressed neighbors with the existing costs, boundary channels and Step/reaction sequence. The stair's lower landing, intermediate supports and upper landing belong to that same graph. Discrete connector kinds retain their existing authored costs/provocation where actually selected. Their data should refer to those supports rather than independently inferring floors from XY.

Optical and propagation geometry is a separate question from walking connectivity. A valid stair route does not mean an actor sees around its turns. Closed floor slabs must block the relevant crossing; a stairwell/window/terrace opening grants only its geometrically legal route. This can be a bounded model of authored supports, boundary spans and declared apertures; it does not require a voxel world or general rigid-body physics. An initial multilevel scope that deliberately omits cross-floor combat must say so explicitly and still prevent accidental cross-floor hits/visibility.

Areas and ground traces must resolve their actual receiving supports through the engine. Don't copy the same XY footprint onto every level. Presentation should receive exact observed supports and causal effects, retaining the existing complete-lineage queue and independent historical clock.

### Proposed multilevel order, after the selected scope is approved

1. Establish two supports at one XY with independent actors/items/Tile conditions and unambiguous cold initialization/replay. Keep current single-support worlds valid.
2. Add explicit support movement through a short real staircase; preserve Step costs, opportunity reactions, ground arrival and interrupted movement. Verify both directions.
3. Connect support-specific boundaries, floor closure/openings, sensory/light and action target origins. Prove downstairs does not discover or damage upstairs through the slab, plus the selected legal opening case.
4. Extend actual spatial footprints and surface residues to those same supports; no duplicate mechanics per storey.
5. Feed the resulting public support facts to existing projection/picking/composition; introduce cutaway selection without changing disclosure or world state. Replay both participants through the same saved bytes from all four cameras.
6. Only then import upper furnished floors and terraces. Preserve the incoming descending stair at its original lower elevation; upper-floor occlusion should hide the correct portion.

This is a design outline, not a commitment to replace all spatial code at once. Every step must exercise the same minimal two-floor world and retain the already working single-floor game.

## Substantive product decisions

These affect the model and belong in the root plan's user-facing discussion; ordinary schema spelling or art lookup choices do not need user supervision.

1. **First deliverable:** furnished single-floor gameplay first, then true stacked supports; or invest immediately in simultaneous multiple storeys before importing a complete house. Recommendation: the former, while designing the support contract before any supposed upstairs feature.
2. **Cross-storey play:** must actors see/shoot/cast between floors through stairwells, balconies and windows in the first multilevel slice, or can those interactions be explicitly deferred? Separate scenes are only a valid substitute if the user chooses that restriction.
3. **Supported-item aftermath:** does a table's exposed cup drop intact, break, or disappear as part of the wreck? The source preview removes attachments; its text suggests detach-to-debris. That is authoring evidence, not an accepted engine rule. Choose one actual example and publish its native result.
4. **Architecture damage boundary:** break furniture/chests and installed doors in this slice, or also permit destroying structural floors/walls? Recommendation: preserve the approved furniture/door scope; do not introduce support collapse, falling or structural simulation from the art's destruction inventory.

Per-style HP, material, blocking aftermath and action availability are authored content decisions with obvious consequences, not reasons to create a new mechanics framework. The plan should state its first selections explicitly rather than leave them to import-time guesses.

## Review and eventual evidence

The parent plan should include both required reviewers: anti-slop review checks the selected gameplay and handoff reuse; anti-OOP/ECS review checks passive support/content data, existing system ownership, cleanup/lineages and the import DAG. This study provides the latter investigation, not automatic approval of an unwritten implementation.

For the single-floor slice, proposed meaningful acceptance is: navigate actual circulation; use/open/close doors from both sides; verify actor/leaf collision and four-view occlusion; hit and destroy the selected furniture/chest; observe correct contents/support aftermath and persistent wreck; turn a fixture off/on and see native sensory consequences; save/restore and replay both players without live engine lookup. Existing `test_environment_destruction`, `test_environment_loot`, `test_world_geometry_contract`, `test_world_modification`, `test_recorded_world_facts` and the environment presentation tests are reusable reference surfaces, **not newly rerun evidence**.

For multiple storeys, add the two-same-XY-support cases above, including independent light/conditions, upstairs/downstairs actor occupancy, observed/unseen mutation, exact support picking and native path/reaction facts. No full visual-regression framework or global serializer is required to validate this bounded contract.
