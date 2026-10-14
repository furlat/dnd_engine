# Multiple floors: engine study and implementation plan

Superseded implementation recommendations: follow the [complete implementation plan](MULTI_FLOOR_IMPLEMENTATION_PLAN_2026-10-13.md). This initial study retains its source findings and historical review record; its proposed identity/storage approach is not current implementation guidance.

Date: 2026-10-13. Status: design proposal for the requested engine study; production implementation has not started. Scope clarified by the human: **multiple occupied floors, stairs, openings and cross-floor gameplay; no flight work.**

The engine needs to represent two different places at the same XY, then preserve that distinction through movement, perception, effects, history and the player protocol. Adding a third coordinate to a dictionary does not complete that change. The recommended foundation is the existing Tile's stable identity, multiple supports per XY column, and small physical queries against actual floor/wall material.

This updates the source assessment behind [the September 21 plan](MULTI_Z_MAP_PLAN_2026-09-21.md). That document remains historical. It combined multiple floors with furnished interiors and window development; those additional projects are not prerequisites here. Existing performance work and the [schema-8 choices rework](PLAYER_ACTION_DISCOVERY_REWORK_PLAN_2026-10-13.md) must survive this migration.

## 1. What is actually blocked

A fresh native in-memory reproduction was run during this study, using the existing engine environment and ordinary map/deployment APIs:

1. Create a 2×2 world. Retain the Tile at `(0, 0)`, height 0.
2. Call `grid.set_tile(0, 0, height=2)`; height 2 means a support ten feet up.
3. The new Tile replaces the old one. Total Tile count remains four; the old UUID no longer resolves; the new one resolves.
4. Repeat in a fresh world with a real deployed actor on the lower Tile. The edit rejects with `cannot detach Tile (0, 0) while entity occupancy is present`. The lower Tile and actor remain intact.

The occupied case correctly protects the existing location. Neither case creates an upper location. This is a representation limit, not merely a renderer problem.

| Boundary | Current source | Consequence for multiple floors |
|---|---|---|
| Tile identity/storage | `dnd/core/gridmap.py:205`, `:850`, `:1030` | XY→Tile and UUID→XY→Tile allow one support per column. |
| Spatial acceleration | `gridmap.py:1020` | `_support_columns` is a planar `(x, y//16)` scan index, despite its name. It does not represent vertical columns. |
| Actor placement and occupancy | `dnd/entity.py:894`; `gridmap.py:2482` | Same XY/contact layer returns early; membership resolves the only XY Tile. A same-XY floor transfer would be skipped. |
| Routes and connectors | `gridmap.py:4921`; `dnd/core/traversal_connectors.py:81` | Path nodes and authored connector endpoints are XY. Connector runtime already retains support UUIDs and elevations. |
| Object footprints | `dnd/types/world_placement.py:48`; `gridmap.py:2915` | Committed supports have UUIDs, but admission chooses the only Tile at each footprint XY. |
| Sight and light | `dnd/blocks/sensory.py:90`, `:713`; `gridmap.py:4364`, `:5674` | Origins, visible cells, contacts, light receivers and many caches use XY. |
| Physical obstruction | `dnd/core/world_edges.py:78`; `gridmap.py:1831`, `:5939` | Nonmovement blocking ignores the recorded vertical interval; absent Tile blocks sight/propagation. |
| Targets and shapes | `dnd/core/base_actions.py:1273`, `:1293`; `dnd/core/aoe.py:182`, `:243`, `:353` | Positional aims, range and recipient membership are planar. Sphere is a circle; Cylinder stores height without applying it to recipient inclusion. |
| Ground effects and handlers | `dnd/spatial/memberships.py:253`; `transitions.py:49`; `dnd/core/events.py:2443` | Occupancy intersections and handler subscriptions use XY. |
| Event-time disclosure | `dnd/core/combat_log.py:18`; `events.py:4484`; `dnd/player/projection.py:84` | The witness key is `x,y`. Separate departure/arrival grants would collide for the same XY on different floors. |
| Retained/replayed world | `dnd/world_facts.py:36`; `dnd/player/facts.py:758`; `dnd/player/reduction.py:89` | Tile dictionaries and field updates overwrite by XY. |
| Current compact choices | `dnd/player/choices.py:14`; `choice_projection.py:20`; `dnd/player/commands.py:20` | Interned positions, paths and extra selection vertices cannot distinguish two supports at the same XY. |
| SDK inverses | `sdk/python/src/dnd_player/choices.py:95`; `sdk/player-typescript/src/choices.ts:59` | Position eligibility groups options by XY; it would merge floors. |
| Authoring and native AI | `dnd/world_authoring.py:55`, `:168`; `dnd/scenarios/encounter_assembler.py:455`; `dnd/ai/runtime/world_projection.py:16` | Placement validation, roster deployment and AI spatial summaries also assume unique XY. |

This table identifies mutation, query and serialization owners. It is not a request to replace every pair of integers: 2D coordinates remain useful for planar geometry and broad-phase indexing.

## 2. What can be reused, and what changed since September

Retain Tile UUIDs, Tile conditions/materials, one GridMap, the current entity placement transaction, object placement, event phases and lineage, observer-owned knowledge, and detached replay facts. There is no need for a second engine or a floor manager.

Existing useful work includes support elevation, stair/ramp transition rules, support-height movement distance, connector identity/endpoints, multi-cell object footprints, item support ownership, physical boundary intervals, partial destroyed bands, windows and aperture traversal. These are existing owners to migrate, not new feature projects.

Several historical assumptions are obsolete:

- `Entity._set_position` now changes only the entity's position (`entity.py:2036`). General `BaseBlock.set_position` still propagates XY (`base_block.py:510`). Do not blindly propagate a new mutable support field through every action/condition child.
- Window construction, attack access and aperture traversal now have native implementations and tests. A new window catalogue, breakage system or furnished-house intake is unnecessary.
- Existing limited flying and forced-fall mechanics have been added since September. They must not be deleted by copying the old exclusions. There is no flight feature work in this plan; shared placement changes must preserve existing callers.
- `upper_volume_sight_planes` explicitly leaves ordinary ground/actor FOV unchanged (`gridmap.py:4794`). Height-aware effect presentation is not completed cross-floor perception.
- Current player ownership is in `dnd/player`, with Python and TypeScript SDKs and Monty consumers. The old plan's `game/player_*` implementation paths are obsolete.
- The current wire schema is 8, saved `PlayerSequence` is version 5, and native `RecordedSequence` is version 2. These are separate versioned boundaries, not one shared number.

## 3. The location model

### Supports, coordinates and physical points

Use `Tile.uuid` as the identity of a supporting surface. Keep its XY and elevation as geometry. Two supports can share XY while having different identities, occupants, conditions, materials and heights. A floor/storey label is optional authoring or display grouping; it cannot decide physics.

GridMap's authoritative storage becomes direct UUID→Tile. Add XY→support identities, ordered by height when useful for local candidate selection. An XYZ→support lookup may be an additional index; XYZ and UUID are not competing architectures. Height edits change an index entry but not the identity of the support being edited. Actual replacement remains a new identity.

No dense XYZ lattice is needed. Empty vertical distance must not allocate rows of empty Tiles. UUIDs need not be repeated in every wire path element: compact response-local indexes already solve that encoding problem. Dense numeric runtime handles are an optional measured optimization, not a prerequisite or public identity.

Distinguish three meanings at existing boundaries:

| Meaning | Required information |
|---|---|
| Supported location | Exact support identity; geometry derives from that support at the relevant native/event time. |
| Physical point/trajectory sample | XY plus absolute physical height in documented units. A ray endpoint or spell vertex does not necessarily stand on a Tile. |
| Perceived contact | Only the location information that this observer actually learned. It must not acquire support identity, height or terrain from private/current state. |

These are passive values, not an object hierarchy with movement or query behavior. Source origin resolution stays with the actual entity, item or device that emits the action. Geometry helpers take explicit data and remain below engine systems in the import DAG.

Tile support elevation remains in its existing five-foot steps. Convert to physical feet at geometry boundaries; finite slab thickness and query samples may use finer units. Do not reuse a renderer's screen Y or storey ordinal as physical Z. Do not invent a global maximum floor count.

### Placement and mutation

The existing entity placement transaction commits support identity and contact mode together with occupancy, publication and rollback behavior. Existing XY can be a derived compatibility value during migration, updated only by that owner. Same XY on a different support is a real change. Ground/AIR/UNDERGROUND is a contact mode relative to support, not a storey identifier.

Migrate attach/deploy, move, detach, suspend/restore, simultaneous transfers, relocation/teleport, connector endpoints and existing supported landing callers together. A simultaneous transfer to two distinct supports at the same XY must not fail the current XY-distinctness check. An invalid transfer leaves membership, resources and events unchanged according to the current admission contract.

Keep item `tile_uuid`, `WorldObjectPlacement` and `covered_supports`. Resolve a footprint onto the intended connected surface; never choose every support in neighboring columns. One large object remains one object with its existing HP, conditions and destruction owner. Supporting an object is distinct from a physical volume extending above that support.

Deliberate XY-only authoring remains possible for old single-support layouts when it resolves exactly one support. Ambiguous mechanical requests reject; no first/highest/current-camera-floor fallback. New layouts use explicit authored support references resolved at construction. Duplicate coincident support tops can be rejected unless a concrete mechanic gives them a distinct physical meaning.

## 4. Floors are finite material, and openings are space

An upstairs floor cannot use the same body interpretation as a hill filling the earth below its top. Extend existing support/world facts with the minimum physical distinction:

- Earth/terrain support: gives terrain its intended solid-below physical interpretation. Current native support height is not already a general solid-below optical kernel; qualify existing flat-map behavior explicitly.
- Finite floor/slab: material occupies a bounded depth below the support top. Top comes from support elevation; no second mutable top value.
- An opening: the slab does not cover that space. It is not a floor flagged walkable and transparent.

A lower horizontal ray below the upstairs slab must pass through the room. A vertical ray across the slab must be blocked. A stairwell ray through the opening must be tested against its actual path, rather than against whether a walking route exists.

Reuse boundary providers, physical intervals and channels. Add bounded panel/aperture geometry only where the existing authored structure requires it. A wall is the simple full-width case. Do not derive collision from sprite alpha, import a mesh physics system, or create independently damaged entities for each piece of a window frame.

### Existing opaque Tiles and admission

Keep support-surface state, intrinsic center-cell opacity and physical material spans distinct. A current wall Tile can have height 0 and `blocks_optics=True`/`blocks_propagation=True` with no boundary object (`base_tiles.py:510`). Representing only earth below its top would incorrectly make it transparent above the floor. Conversely, an ordinary floor's `blocks_optics=False` does not make a finite upstairs slab transparent to vertical rays.

Migrate intrinsic wall/center blockers into channel-specific physical contributions with their own vertical span. Old single-support input retains its current full-column blocking meaning through an explicit legacy span interpretation; do not infer an arbitrary finite wall height from Tile elevation. New multi-floor authoring must supply an intentional finite or full-column span. Ordinary floor material and an above-floor wall are separate contributions even when the same Tile owns them. Dynamic fog/darkness retain their existing effect owners and declared volumes, rather than becoming accidental earth or full-column walls. Include ordinary floor, intrinsic wall Tile and boundary-object wall cases in the parity checks.

Existing authoring/world mutation admission must validate local physical coexistence before inserting or editing a support body, blocker or elevation. An upper earth body cannot swallow a retained lower support/actor. An eleven-foot-deep slab with a ten-foot top cannot occupy the lower room. Check intersecting support surfaces, placed object volumes and the relevant mechanical body/headroom envelopes; reject impossible combinations before committing any change. A thin upper slab with adequate headroom is valid. Use the existing transaction/rollback owner and local column/volume candidates, not a collision manager or a scan of the entire world. This does not introduce collapse or automatic occupant displacement.

### Unsupported open space

The engine currently treats an absent XY Tile as blocked/outside. Globally reversing that rule would change existing maps.

For the new physical queries, an XY column containing supports has a physical domain: test its actual earth/slabs/objects/boundaries, and treat the remaining space as air. A normal stairwell above an existing lower floor requires no additional air record.

Where an XY column has no support at any height, allow a sparse, explicitly authored open-space volume: a finite XY footprint and bottom/top physical heights. Add it to existing world authoring/facts and the local spatial index. It supplies query domain, not occupancy, a walking destination or ground effects. This is useful for a bridge gap or an unsupported shaft; it is not mandatory room metadata.

| Query location | Meaning |
|---|---|
| Column with a support | Test its actual physical bodies; empty portions are air. |
| Unsupported column inside an authored open-space volume | Air where no blocking material intersects. |
| Unsupported column outside those volumes | Blocked/outside, preserving legacy missing-cell behavior. |
| Material inside either admitted domain | Its channel-specific blocking takes precedence. |

Keep open-space volumes static for the first proof. Opening a door or changing a slab changes material and its local dependencies; no room graph or floor tick is required. Removal of the last support leaves open space only where an authored volume says so. The existing restriction on replacing/removing occupied supports remains; structural collapse is a separate mechanic.

### The physical query

Add small segment/interval intersection functions under existing geometry/world-edge owners. A query carries physical endpoints and a channel. Enumerate crossed XY columns and boundaries once, filter their height intervals, and intersect only relevant slabs/panels. Include blockers anchored on intermediate or different supports, not just the endpoint supports.

The finite segment's parameter interval must be covered by the admitted physical domain, then checked against channel-blocking material. Same-XY vertical segments are a mandatory case: zero horizontal displacement must not skip their nonzero vertical length. Endpoint-on-surface and corner-touch conventions must be explicit and tested, so an actor's own floor does not block every outgoing query.

Walking clearance, sight, light, attack access and effect propagation can share geometry inputs; they retain distinct rules. A point ray through a narrow aperture does not prove a creature fits. Existing creature-size/passage checks remain, with an explicit mechanical vertical envelope where ceiling/body clearance requires one. Rendered sprite dimensions never supply that envelope.

## 5. Routes, stairs and interactions

Ordinary navigation nodes become exact supports. Candidate edges come from neighboring XY columns and existing authored connectors, then pass elevation, slope, boundary, occupancy, clearance, movement-cost and hazard checks. Height-sorted column indexes must narrow candidates to the supported transition's admissible height interval before testing them; walking one step must not inspect every distant storey in that column. Merely sharing XY creates no free vertical walking edge.

Example proof route, with heights in existing native steps:

```text
lower A (4,1,0) -> stair L (3,1,0) -> stair S (2,1,1)
               -> stair U (1,1,2) -> upper B (1,2,2)
                                      lower C (1,2,0) is a different support
```

L, S and U have the compatible stair/axis facts required by current rules; the upper slab leaves the ascending run open. B and C can contain different actors. There is no B↔C walking shortcut.

Keep bounded single-source navigation and the current movement budget. Costs remain the existing movement rules. Diagonal checks need compatible intermediate supports; a lower corner cannot borrow an upper bridge to authorize passage. Preserve safety/hazard and opportunity-attack route information with exact supports.

The Move action still publishes actual Step events with the existing reaction/interruption phases. Record source/destination support and event-time geometry. A stopped or killed actor stays on its actual committed support; neither history nor client playback completes an abandoned route.

Portals, relocation, item use, adjacency/reach, deployment and native AI choices must use the same location semantics. Readable stairs are ordinary movement; reuse paid connectors for genuine ladder/aperture/other selected traversal. Do not build a second baked navigation graph for a building.

## 6. Perception, light and subjective event history

Move supported visibility/seen state, tile light and hazards to exact support identities. Entity/object contacts carry admitted physical location independently from whether the supporting terrain is disclosed. Seeing part of an upper object or volume is not permission to see all its floor or occupants.

Recompute uses the observer's actual committed support and mechanical source samples. Candidate support/actor enumeration is spatially bounded. Capture local geometry once per query batch, not once per recipient ray. Existing upper-volume observations remain distinct from support/body visibility.

Reuse incremental light contributions, observer reverse indexes, candidate event dispatch and local revisions. Ground changes address exact supports. Slab/door/physical-volume changes invalidate the observers and sources whose physical dependencies intersect them, potentially on other floors. Dependencies include blocked frontiers: opening a barrier must reveal previously blocked recipients. A dependency subscription remains private computation, never an observation grant.

Current FOV, transition and AoE caches are keyed partly by XY and revisions (`gridmap.py:4613`, `:4869`, `:6095`; `entity.py:6109`; `aoe.py:74`). Keys and dependency lifetimes must include the relevant support/physical origin, source sample, query channel and local geometry. A same-XY support change cannot reuse the old origin's result.

Retain an optimized 2D path only where captured local geometry proves equivalent behavior. Being assigned the same floor label is not proof. Do not run the full existing FOV once per floor and union the results; it cannot model an oblique ray through a stairwell.

Migrate EventQueue spatial subscriptions, `encounter.py` perceiver candidates, event-time location witnesses and public projectors together. Source and destination grants must have separate exact locations even when XY matches. Preserve independent before/after evidence, all phases, ordering, complete lineages and mutable native Event history. No archival/GC redesign belongs here.

World/Tile after-values, light maps, sensory deltas, movement, residue deposition, object removal and remembered placements all need support-aware keys. A hidden upstairs change cannot refresh or delete remembered upstairs state because the downstairs support is visible. The same rule applies to combined audiences: union actual admitted facts, not all floors in a visible column.

Special senses retain their existing owners and distinctions. They need vertical range and relevant physical-contact/propagation context; copying ordinary LOS to every sense is wrong. Representative special-sense cases belong in the release matrix rather than being silently treated as 2D exceptions.

## 7. Targeting and effects

Ground-targeted selections name supports. Physical spell origins/vertices name admitted physical points or an explicit supported aim. Subject selections retain entity/object identity. A target directly upstairs no longer has distance zero just because its XY matches.

There are currently two different metrics: ordinary targeting uses floored planar Euclidean distance (`geometry.py:8`), while support movement uses `max(planar_distance, rounded_vertical_distance)` (`elevation.py:24`). Do not silently call either one a preexisting complete 3D targeting rule. Recommended starting policy for supported targets is the existing tactical support-distance helper; ordinary movement costs remain unchanged. This is a proposed gameplay choice to settle with concrete examples, not a storage decision. Physical intersection tests use actual coordinates independently of tactical range rounding.

Optional AoE remains deferred in Choices. Only a selected Preview computes its subjective affected supports/subjects; execution computes native authoritative outcomes. Never perform one full area solve for every spell at every floor position during discovery.

Migrate shared shape and propagation owners, not an upstairs switch in individual spells:

| Family | Work needed |
|---|---|
| Ground patch/trap/residue | Exact receiving supports and existing contact/entry/exit semantics. No other support in the same column inherits it. |
| Sphere | Physical center and vertical extent; select recipients in the actual volume, then use the effect's propagation rule. Current planar circle behavior cannot simply repeat on every floor. |
| Cone/line/cube and wall vertices | Explicit physical origin, direction/orientation and extent; migrate ordered extra positions and any origin-plane rule. Preserve authored length/allocation rules. |
| Cylinder | Use the currently stored height and explicit vertical origin/direction. Preserve its existing distinct lateral-wall behavior; decide slab interaction separately instead of imposing ordinary radial LOS. |
| Connected clouds/areas | Traverse connected admitted space within the bounded shape, including openings without walking supports. A walking path or set of support nodes is not a volume-propagation graph. |

For connected effects, a local traversal of open column intervals/regions split at relevant material boundaries is a candidate implementation. Build only what the selected bounded effect needs, clip by actual shape, and test shared boundary openings. Do not allocate a persistent world-sized voxel lattice. Profile this separately from direct rays; it is the most substantial new geometry algorithm in this plan.

Supported aims supply the required vertical origin, and existing actions remain responsible for their shape orientation/extent. Do not add an unrelated arbitrary 3D spell-rotation interface. Define the vertical meaning needed for actual cross-floor targets through the shared shape owners.

Membership application/removal and overlap ownership remain with existing spatial systems. Also migrate direct location consumers such as Silence's verbal-casting handler (`dnd/spells/illusion.py:1304`); fixing Deafened membership alone would leave cross-floor spell cancellation wrong. Test actual actions and effects, not just membership sets.

Mechanical sample heights/body envelopes, vertically directed shape semantics, the target distance policy and each sense's new vertical meaning must be explicit before claiming general cross-floor combat. The proof scene can establish these with a small number of representative cases; it must not silently restrict unsupported spells to the caster's floor.

## 8. Server, compact protocol, SDKs and client handoff

Preserve the schema-8 shared subjects, location domain, target sets and original native selection indexes. Extend the location entries so two same-XY supports remain distinct. A practical shape is a passive supported-location entry versus a physical-point entry, resolved within one response. Exact field names are implementation choices; mandatory properties are:

1. A support target can be selected without copying a full Tile record into each action.
2. Two floors at the same XY have different location references and different eligible options.
3. Paths, safe paths, opportunity exposures, selected routes, range origins, affected supports and extra selection vertices carry the intended location semantics end to end.
4. Preview domains remain self-contained, including new points/landing destinations not present in Choices.
5. Ordered multi-target selections, repeats and secondary eligibility remain unchanged. The server resolves existing native indices and revalidates current state.
6. A location grant does not automatically disclose terrain, every same-column support, hidden creatures or extra geometry. Current coordinate-only observations need deliberate treatment, not invented identity/height.

Change event-associated `TileFieldUpdate` addressing from XY to exact support identity. For example, the proposed update shape could be `{tile_uuid: upper_id, changes: {resolved_light: 2}}`. Retain full records for discovery/identity replacement and field-only changes for known identities. Apply in event order; unknown bases reject; lower-floor light stays unchanged. Removal/replacement facts must name exactly which support left and which new identity was disclosed.

Update the native retained world, Python player reducer, wire schema/generator, both SDKs, typed helper inverses and Monty documentation/examples in the same coordinated protocol migration. Existing SDKs are transport/schema packages; renderer state reduction remains a client responsibility. Reinstall the sandbox's packaged SDK and use fresh services for its live check.

Version each changed boundary deliberately: current live wire schema 8, player saved sequence 5, native saved sequence 2. Do not maintain two competing live worlds or an implicit `(x,y)→top floor` compatibility mode. For saved single-support records, a bounded version adapter can resolve only identities established by their initialization and preceding events. Coordinate-only public evidence remains coordinate-only where identity was never disclosed. No lookup into the final/private world, no replay execution, and no fabricated zero height. Inspect representative existing recordings before fixing the exact adapter shape; this study does not claim a legacy conversion has been implemented.

The client handoff must cover support-keyed reduction and set membership, independent light/visibility at the same XY, unambiguous floor picking, a manual visible-floor/cutaway control, finite-slab rendering, receiving support for routes/effects, and event-time motion endpoints. Cutaway changes presentation only. It neither removes collision nor grants hidden entities. Do not reintroduce full collection rebuilding, full-target expansion or repeated validation.

Current NDClient runtime source was not available at the documented `/home/tommaso/Dev/NDClient` checkout during this study (it contained authoring/docs but no runtime source). The handoff is therefore based on inspected native/SDK contracts; current frontend implementation details still need source verification in its actual checkout. No client code is changed here.

## 9. Implementation sequence and completion gates

The first demonstration is one small native scene: two overlapping levels, two independently controlled actors, ordinary stairs, one closed slab and opening, an existing door/boundary, a light and one ground effect. Use existing content. Add other objects only for a named acceptance case. Keep incomplete multi-floor scenes out of the public encounter catalogue until their interacting systems agree.

| Stage | Concrete work | Observable completion |
|---|---|---|
| A — settle the few gameplay meanings | Record physical sample/ceiling policy, target distance examples, representative vertical shapes and special-sense behavior. Finalize passive support/body/location facts and protocol outline. | Two levels have unambiguous addresses; the expected same-XY and cross-opening outcomes are written before algorithms. No flight branch. |
| B — support identity through state/history | Native storage/authoring including local material/headroom admission, direct lookups, column indexes, placement/deployment/transfer, object footprints; support-addressed ground membership, event subscriptions/witnesses and corresponding fact/reducer/version changes. | Two actors/items/ground conditions coexist at the same XY. Independent mutation/removal and same-XY relocation remain correct after cold replay; invalid upper bodies leave the lower world intact. |
| C — real movement between supports | Bounded navigation, stairs/diagonals, connectors, adjacency/reach, existing relocation callers, ground contact/entry/exit dispatch and direct support checks. Preserve cost/safety/reaction rules. | Real route up/down stairs; blocked route/door; interruption at the actual support; no vertical shortcut or wrong-floor trap. |
| D — physical query and perception | Earth/slab/center-blocker spans, bounded segment/domain query, existing apertures, support/body sight and light, observer dependencies/cache origins, grants/projection. | Closed slab separates occupants; legitimate opening passes physical sight/light/line-of-effect queries; lower room remains usable; local changes and replay agree with full refresh. Actual cross-floor attack admission is stage E. |
| E — combat and shared effect families | Actual target-origin/range migration, selected previews, shape/connected-space geometry, volumetric memberships and their direct handlers, special senses and native AI. | Preview and actual commands agree across supports; ground effects remain local; volume effects and direct handlers obey the selected rules without disclosure leaks. |
| F — production transport and consumers | Final generated schema/SDK coordinated release, compact domains/deltas, Monty, verified NDClient handoff and client integration. | Fresh server plus clients can select/play both floors, retain event history, render/pick receiving supports and cold-replay the recorded match. |
| G — performance and final review | Same scenarios, phase timings/candidate counts, payload measurements and independent anti-slop/ECS review of installed code. | No all-world/floors multiplication on local actions; reported timing and correctness evidence covers the actual delivered path. |

Fields/producers/consumers should migrate together within these stages; the ordering is not permission to leave an event producer and its projector disagreeing until stage F. Keep the native/public distinction explicit throughout. A storage prototype is useful evidence but is not delivery of playable multiple floors.

## 10. Validation and performance

Follow `HOW_TO_TEST.MD`. The requested behavior is concurrent independent supports plus legitimate interactions between them. Test at native actions/events, projected player records and actual SDK commands; expected output includes location, occupancy, costs, recipient effects and observer-authorized history. Do not freeze private layouts or add tests that merely mirror new helpers.

| Case | Required observed result |
|---|---|
| Same XY, two supports | Distinct actors/items/light/residues/occupancy; modifying one leaves the other intact. Empty support insertion does not replace its neighbor. |
| Physical coexistence admission | Reject upper earth or an overly deep slab that would engulf the lower support/body; reject conflicting body/elevation edits without changing lower state/history. Admit the thin slab with sufficient headroom. |
| Same-XY relocation and simultaneous transfer | Exact support changes commit, source/destination witnesses remain separate, invalid operations leave state unchanged. |
| Stairs and diagonal corners | Real costs/steps, reaction interruption and final support; no path using an unrelated upper corner to cross a lower obstruction. |
| Closed floor versus opening | Same-XY vertical ray tests actual material; clear stairwell path works; downstairs horizontal path does not hit material above it. |
| Intrinsic and boundary blockers | Current opaque wall Tiles remain opaque on flat-map references; ordinary floor flags do not defeat vertical slab blocking; explicit finite walls allow only geometrically valid above/below/opening paths. |
| Unsupported gap | Ray inside the authored finite gap passes, rays outside its XY or bottom/top bounds fail, and material inserted inside still blocks. It offers no walking/ground target. A legacy missing Tile without that domain keeps its old blocking behavior. |
| Occlusion changes | Door/slab/light changes update previously blocked dependents on the appropriate floors; remote observers remain unaffected; incremental results equal full native refresh. |
| Ground and volume effects | A ground trigger affects only the actual receiving support. Shared shapes and connected clouds respect their volume/propagation; Silence is tested by real verbal casting and removal. |
| Disclosure and memory | Never-observed upper contents are absent from lower player bytes; remembered hidden upper state does not refresh/delete due to lower visibility. Audience union preserves that distinction. |
| Choices, Preview and Command | Upper/lower same-XY aims remain distinct; shared tables stay shared; repeated targets/order preserved; direct command needs no mandatory Preview; selected Preview resolves its own domain. |
| Tile field updates and replacement | Only the named support changes, every intermediate event survives, and unknown/replaced bases cannot accidentally update another support. |
| History and presentation | Fresh-process reduction/rendering uses saved admitted geometry only; picking/cutaway choose the intended support; interrupted motion stays on the committed floor. |
| Full match | Two independent Monty agents on the multi-floor proof map use real SDK/server choices, stairs and cross-floor combat through terminal state; both saved views replay. |

Extend the relevant current tests rather than invent a new framework: `test_traversal_connectors.py`, `test_windows.py`, `test_window_attack_access.py`, `test_local_optical_inputs.py`, `test_moving_ordinary_light.py`, `test_sensory_movement_origin.py`, `test_cloud_propagation.py`, `test_globe_propagation.py`, `test_deferred_aoe_discovery.py`, and player `test_compact_choices.py`, `test_projection_local_world.py`, `test_tile_field_updates.py`.

Performance acceptance follows the user's existing scalability goal:

- Preserve the current single-support path as the comparison baseline; do not charge the feature to a different map/observer order or profiling mode.
- Measure navigation, physical input capture, intersections, observer recompute, light updates, handler dispatch, selected-area computation, projection, encoding, payload bytes and SDK admission separately with existing temporary instrumentation.
- Hold the local scene fixed while adding distant rooms/floors and irrelevant vertical supports. Candidate counts should follow the finite query's relevant region, not total map size or every stored floor. Adding genuinely visible/reachable recipients naturally adds work.
- Compare local edits with equivalent full recomputation for correctness; verify the local path does not invoke that full solve in normal operation.
- Preserve shared choices and event-associated field updates; do not serialize a full floor per action or repeatedly sort/rebuild all location membership sets.
- Keep native mutable history and all events. Do not insert a C++ module, history-compaction project, checksum scheme or new event bus into this rework.

The existing 9.5 ms movement goal remains open. This study supplies no new timing claim for unimplemented multi-floor geometry. Measure before selecting further numeric/native acceleration; changing language does not repair ambiguous location identity or unbounded work.

## 11. Decisions and review record

Settled human scope: multiple floors and cross-floor gameplay, **no flight work**. Stable support identity with sparse spatial indexes is the technical recommendation. Storage names and routine schema fields need no separate permission cycle.

The remaining gameplay decisions are concrete: vertical target distance, mechanical sight/target/body samples, shared shape vertical orientation/extent and cylinder/slab behavior, and the vertical meaning of special senses. They should be settled against the representative cases in stage A, preserving current flat-map behavior where equivalent and explicitly recording intentional changes on elevated terrain. There is no need to ask the human to choose data-structure names.

Read-only native/ECS reviewer: `multifloor_ecs_review`. Read-only perception/performance anti-slop reviewer: `multifloor_antislop_review`. Both inspected the historical plan and current owners; the ECS reviewer ran the two native storage/occupancy probes described above.

Both reviewers approved the revised design proposal on 2026-10-13 after these amendments:

- **ECS/anti-OOP:** distinguish intrinsic center opacity from floor/earth material; preserve old wall-Tile meaning through explicit spans; validate local physical coexistence/headroom on insertion and edits before commit. These are in §4, stage B and the acceptance matrix.
- **Anti-slop:** move support-specific ground memberships, subscriptions and witnesses into B/C before wrong-floor movement/trigger gates; keep actual attack admission in E after physical queries; test the exact finite bounds of authored open space and material overriding openness.

No remaining material issue was found within the inspected design scope. Approval covers plan coherence and owner/scope choices; it does not certify unimplemented algorithms, timing, the recorded vertical-rule decisions or the uninspected client runtime.

Study limits: source inspection plus the two in-memory probes, not an implemented multi-floor feature or a new full-suite/performance result. No production engine/server/SDK/client code has been changed by this study.
