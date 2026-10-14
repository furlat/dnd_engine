# Multiple floors: complete implementation plan

Date: 2026-10-13. Status: implementation proposal; no production implementation started. This is the current plan, superseding the recommendations in [the initial study](MULTI_FLOOR_ENGINE_STUDY_AND_PLAN_2026-10-13.md) and [the September proposal](MULTI_Z_MAP_PLAN_2026-09-21.md). Those documents retain historical evidence, not implementation authority.

The requested outcome is a physically coherent world with several simultaneously occupied floors at the same XY, ordinary stairs, openings, cross-floor perception and combat, and correct native history and player updates. The work includes the systems that consume locations, not just map storage. The human excluded flight work. Preserve existing supported movement/landing callers without adding free flight or hovering.

The human also corrected two foundations: use XYZ as the spatial address, with Z representing actual height rather than a sorted floor ordinal; and preserve the existing directional support system instead of replacing it with a simplistic lower-tile predicate. This plan incorporates both corrections.

## 1. Completion means a playable integrated feature

A fresh server must construct a valid stacked world; deploy two actors at the same XY on different supports; move them through real stairs; compute independent light, visibility, occupancy, targets and effects; publish exact event-time changes; accept SDK commands; and reconstruct both player views from saved records. Client integration must render and pick the intended support, including when one floor hides another visually.

Required behavior includes supported object footprints, doors/windows, light emitters, moving effects, reactions, hazards, relocation, construction and destructive changes that affect physical support. No system may silently choose the highest Tile, union all floors at a visible XY, or fall back to same-floor-only mechanics.

This is one engine with passive spatial data and existing mutation/system owners. No FloorManager, actor-per-floor duplicates, new event bus, second live world, imported editor application architecture, or C++ workstream. Preserve the compact Choices/Preview/Command design, event-associated tile field updates, every event, and mutable native Event history. New construction artwork and an entire arena-content integration are not prerequisites for the native feature.

## 2. Source findings that determine the design

The initial native probes showed that setting a higher Tile at an occupied XY rejects, and setting one at an empty XY replaces the old Tile. GridMap currently stores XY → Tile; Tile height does not participate in spatial addressing. These probes were run during the earlier study; this plan is not a claim of new gameplay test results.

The directional support system was found after the initial study and materially changes the plan:

| Existing source | Useful contract | Qualification |
|---|---|---|
| [NeuroMapEditor types](/home/tommaso/Dev/NeuroMapEditor/src/model/types.ts:213) | Oriented downhill faces, rise, exact supported footprints; stair lanes and entry/midpoint/top/landing contacts. | These are reusable physical semantics, distinct from pixel calibration and asset names. |
| [Causal height computation](/home/tommaso/Dev/NeuroMapEditor/src/model/causalHeight.ts:1906) | Directed lower-to-upper component relations, support witnesses and conflicting height claims; an upper relation becomes usable only after its lower component is established. | Much of this code reconstructs ownership from a flattened art import. Do not execute that reconstruction during gameplay. |
| [Editor edit boundary](/home/tommaso/Dev/NeuroMapEditor/src/editor/store.ts:1306) | Undoable placement and geometry editing. | It does not universally reject physically invalid edits. Its authoring-patch export is not an engine world importer. |
| [Arena constructor rules](/mnt/c/Users/tommaso/Documents/assets/arena-study/prototype-v1/grid-kit/constructor/RULES.md:29) | Closed material pieces, directional contact polygons, exposed faces, support surfaces, stairs and component dependencies. | Family-specific compatible assemblies, not permission to join arbitrary unrelated assets. |
| [Constructor adjacency](/mnt/c/Users/tommaso/Documents/assets/arena-study/prototype-v1/grid-kit/constructor/adjacency.py:42) | Actual X/Y/Z area contacts and shared-source cut continuity; edge-only touch is not an area join. | Does not independently establish every possible bearing relation between different source components. |
| [Constructor verification](/mnt/c/Users/tommaso/Documents/assets/arena-study/prototype-v1/grid-kit/constructor/verify.py:48) | Raised perimeter closure and retained supporting owners, local solid closure and authored stair checks. | Some checks compare with the generated expected assembly; support-reference existence alone is not a general physical-validity proof. |
| [Constructor native adapter](/mnt/c/Users/tommaso/Documents/assets/arena-study/prototype-v1/grid-kit/constructor/compile.py:223) | Samples support at cell centers. | It deliberately selects the highest surface per XY and rounds its height upward. Full physical exports retain more information. This reduction must not become the multi-floor importer. |
| Native GridMap, world_authoring and battlefield_catalog | Existing placement, event phases, cancellation, complete cold-build publication and object assembly admission. | Current checks do not consume the complete directional assembly contract. |

The source delivery explicitly records that the production loader and curved-collision adapter are unconnected. Its saved validation is useful evidence, not a fresh test of current code or proof of integration. The editor's historical western-height failure counts are also not current reproduced failures; current source has subsequent refinements. Reuse reviewed metadata and acceptance fixtures without claiming every inference algorithm is certified.

## 3. Spatial data and units

### 3.1 Canonical addresses

Use a supported location consisting of integer X/Y cell coordinates and canonical physical support-top Z. GridMap's primary spatial lookup is XYZ → Tile; UUID → XYZ remains a reverse lookup for the existing Tile lifecycle, conditions, items and events. UUID is not the hidden primary spatial address.

Recommended unit policy to qualify against the first building and source samples: store support Z as integer inches. Existing five-foot elevations convert exactly by multiplying by 60; ten-foot floors become Z=120; the constructor's six treads per five-foot rise can retain ten-inch increments. This is a proposed technical choice, not a claim that the human selected inches. Inspect actual support-top precision before fixing the schema. Normalize tiny source floating-point error once at import; reject a genuinely unrepresentable support top with a specific diagnostic rather than silently round it to another floor. Do not ceil a tread into the physical height of a different surface.

Local polygon vertices and ray samples may remain finite floating-point geometry in documented units. Coordinate identity uses the canonical support Z. Geometry tolerances govern intersection, not whether two separately keyed supports are accidentally considered equal. Derive feet, renderer lift and compatibility elevation values from the authoritative location; do not keep independently editable Z and Tile.height.

Normalize all three axes before vector/range arithmetic: an XY cell is five feet, while the proposed stored Z unit is one inch. A raw length computed directly from the mixed-unit address tuple is invalid. Keep source physical geometry and authored tactical walking contacts distinct so retaining fractional tread geometry does not manufacture additional walking steps.

| Value | Meaning |
|---|---|
| Supported location | Exact XYZ of a playable support top; used for occupancy, navigation, ground effects and ground selections. |
| Physical point | Position in physical units, possibly between supports; used for ray origins, body samples and spell geometry. |
| Physical piece address | Source material cell/band or provider placement. Its base is not the support top: a piece at band Z−1 may support a surface at Z0. |
| Tile UUID | Existing identity across mutation. A height edit retains it; replacement at the same XYZ creates a new identity. |
| Storey/editor layer | Optional grouping and display information. It cannot establish support, visibility, collision or movement legality. |

A boundary and a surface can coexist at one XYZ; they are different contributions with existing owners. Do not make every material fragment a walkable Tile or an independently damaged entity. Coincident playable support tops need one unambiguous supported location; reject contradictory duplicated surface definitions or combine fragments of the same authored surface during construction.

### 3.2 Finite sparse storage

Maintain existing occupied XY chunks, with actual support elevations ordered inside each column and local material spans indexed by their physical bounds. Sorting is for range lookup, never identity. Adding a height between two others changes no existing coordinates. Negative elevations and holes between authored heights are legal.

Do not allocate empty layers between stored heights. Optional integer slots for arrays/bitsets are internal handles; they must not depend on the sorted rank of a height or become public map-wide IDs that reveal hidden geometry. Start from a single authoritative sparse store and only add an index with a named query owner.

### 3.3 Passive facts and dependency direction

Keep coordinate/body/support-relation records under dependency-neutral type/geometry owners. Geometry functions consume explicit snapshots; they do not resolve BaseBlock registries, call the server, or dispatch events. GridMap owns indexes and committed spatial mutation. Entity/BaseItem remain data and system composers. Source emission originates from the actual actor, item or device, not a guessed parent chain or copied mutable location on every action/condition child.

## 4. Physical map construction and validity

### 4.1 Preserve the authored rules

Translate the recovered physical contracts into native passive data: receiving surface footprint/top; occupied material volumes; oriented boundary/contact faces; supported endpoints or footprints; stair slope/run; support-provider/dependent relationships; blocked channels; existing component ownership. Use the source's declared relation and geometry. A random lower Tile, matching material name, projected overlap, or sorted layer position is not proof of support.

Keep source-family compatibility at authoring. Do not port asset-name inference, pixel matching, camera ordering or all of the editor's repair solver into the engine. Normalize axes explicitly: the editor's art direction conventions and native cardinal directions differ. The source adapter emits canonical native vectors, units and contacts once.

The native world needs explicit supports, bodies and dependencies. It does not need the full source scene, art inventory or a copy of every build checksum. Deduplicate reusable shape definitions through existing content/authoring ownership; retain occurrence-specific geometry and provider identity where it differs.

Foundation/earth support is an explicit authored basis for the support relations; it is not inferred from Z=0 or from the lowest object in a column. Raised solid terrain can be foundational without another Tile beneath it. A finite upstairs floor must satisfy its declared bearing/contact relations. This avoids both an infinite chain of lower Tiles and arbitrary floating pieces promoted to foundations.

### 4.2 Admission checks

Before a complete map becomes playable, validate:

1. Canonical positions, unique playable surfaces and valid referenced providers.
2. Directed contact geometry, permitted profile joins, height differences and supported footprint coverage according to the selected authored contract.
3. Required lower component establishment; reject unsupported or circular bearing justification. Same-height contact loops can be valid closed perimeter assemblies; a contact loop is not itself a circular support claim. Do not impose the arena's closed-ring rule on unrelated valid architectural families.
4. Complete required spans, risers and side returns. Exposed faces from unequal profiles remain legitimate; demanding identical whole profiles would erase valid retaining walls.
5. Physical coexistence across supports: an upper earth volume or deep slab cannot engulf a retained lower surface, actor envelope or placed object.
6. Clear walking endpoints, stair contacts, available headroom and coherent multi-cell footprints.
7. Correct openings and declared empty-space bounds; absence of material and absence of a playable surface have different meanings.

The cold builder can construct a candidate batch in dependency order, then validate the entire assembly before WorldInitialized is published. Do not require each intermediate tile insertion to be a complete building. Existing battlefield construction already suppresses events until cold validation, then activates lights/traps after initialization; extend that owner.

For runtime geometry edits, construct the candidate after-state, collect its affected contacts/dependents, validate, run the existing cancellable declaration phases, revalidate changed dependencies, and commit before publishing completion. Failed admission must not leave occupancy, indexes, partial assemblies or public after-values changed. Extend existing prepared object/assembly admission; do not add a parallel transaction framework.

### 4.3 Support loss and destruction

Physical validity applies after destruction as well as creation. Existing BaseItem destruction cascades attached children, removes aperture connectors and preserves authored remnants; partial section removal changes occupied bands without necessarily replacing the object. Migrate those paths and recompute affected support claims.

Distinguish an authored attachment that requires its parent from a floor with alternative valid bearing contacts. Re-evaluate the remaining declared support rule; do not destroy a whole floor merely because one of several providers changed. Retain source component grouping and existing damage identity.

Proposed behavior for newly introduced support-loss cases: prepare one destructive after-state under the existing mutation owner. Retain the old support/geometry facts; admit and reserve the settled outcomes for affected occupants and items; prepare dependent cleanup and route/effect invalidation. Preserve live source membership until transfers can commit, then retire invalid owned supports and publish coherent ordered before/after facts under the same destructive lineage. No dispatch or revalidation may observe actors attached to missing supports.

The current Tile removal rejects live references, and forced movement reads the source Tile. Extend the existing forced-fall/landing owner for a prepared support-loss transfer where a valid lower landing exists; do not assume it already handles a deleted source. This is an extension of existing mutation and placement ownership, not a new transaction framework. It does not add free flight or a stress/fracture simulation. Exact alternative-support requirements, no-landing outcomes, supported item aftermath and cascade limits are gameplay decisions in §18; settle them before implementing or admitting destructible bearing structures. Do not silently make existing breakable objects indestructible, leave floating usable surfaces, or claim this branch complete with detection alone.

## 5. Ownership and migration inventory

This is the owner checklist for implementation and review. The paths identify current source, not a requirement to move code into new modules. Search remaining direct XY consumers as their owning behavior is migrated and classify their meaning; a blanket tuple-length replacement is incorrect.

| System/current owners | Required migration | Completion evidence |
|---|---|---|
| dnd/core/base_tiles.py; gridmap.py | XYZ storage, reverse identity lookup, exact elevation mutation, sparse columns, physical bodies, support dependencies and reset. | Independent stacked Tiles; address edits and replacements preserve distinct identity semantics. |
| dnd/core/world_edges.py; world_placement.py; physical_access.py | Exact support endpoints, incident boundaries, finite spans and access-specific geometry. | Same-XY vertical intersections; valid aperture versus blocked body passage. |
| dnd/world_authoring.py; scenarios/battlefield_catalog.py | Complete physical admission and event-time before/after facts. | Invalid finished assembly never becomes an initialized world. |
| Source adapters; scenarios/encounter_assembler.py; core/content/battlefields.py | Preserve every support, explicit deployment addresses and authored defaults/previews. | Import never selects only the highest surface; scenario choices identify floors. |
| dnd/entity.py; game.py | Attach/deploy/move/transfer/detach/suspend/restore/retire, reservations and occupant origins. | Same-XY transfers, rejected operations and pending returns remain coherent. |
| dnd/blocks/base_item.py; content/items; GridMap placement | Covered supports, absolute bodies, parent assemblies, loose-item drop/retirement and destruction. | Large object remains one identity; no cross-floor overlap or wrong-floor drops. |
| GridMap compute_paths; Entity navigation materialization; actions.Move | Support-node navigation, budget/costs, route safety, steps and reaction interruption. | Real stairs, exact intermediate support, no vertical shortcuts. |
| traversal_connectors.py; actions.TraverseConnector | Exact endpoint supports, orientation, access and paid traversal lifecycle. | Connector costs/reactions stay distinct from ordinary walking. |
| blocks/sensory.py; types/senses.py | Observer origins, visibility, light evidence, contacts, memory, hazards and special senses. | Upper/lower knowledge stays independent, including same-XY origin changes. |
| GridMap FOV/optical snapshots and revisions | Finite 3D geometry inputs, cache keys, blocked-frontier dependencies and bounded candidates. | Physical cross-opening sight, including intervening floors/providers. |
| GridMap light sources/contributions; sensory light updates | Emitter height, receiver locations, source candidates and incremental delta application. | Carried/ordinary/magical light and darkness update the correct receivers. |
| core/base_actions.py; actions_functional.py; Entity action discovery | Origins, range, primary/secondary choices, route and selected-area computation. | Choices, Preview and Command agree without eager full-AoE expansion. |
| dnd/actions.py; reactions.py; core attack handlers | Reach, melee pressure, ranged access, opportunity reactions, shove and forced movement. | A nearby XY upstairs actor is not automatically reachable/threatened. |
| core/aoe.py; geometry.py; wall_geometry.py; presentation_geometry.py | Shared 3D shapes, actual propagation and recorded shape/aim geometry. | Representative shape families work vertically; flat references retain their rules. |
| spatial/area_conditions.py; memberships.py; transitions.py | Ground versus volume membership, anchor motion, overlapping sources, suppression and removal. | Entry/exit/turn handlers execute for the right support/body. |
| spatial/mechanisms.py; jaws.py; gas_traps.py; environmental_conditions.py; ignition.py | Hardware positions, lanes, payloads, clouds, ground conversions and discovery. | Trap/fire/ice/wet effects do not leak to another floor at the same XY. |
| residues.py; core/residue_geometry.py; types/residues.py | Receiving surface/face, splashes and existing residue-triggered mechanics. | Deposits and fear/condition consumers use actual receiving geometry. |
| spells/* including illusion, walls, wall_fields, wall_constructions | Direct location handlers, moving auras, constructions, wall crossing, device origins and special spell constraints. | Silence casting, barriers and suppression use the same spatial answer as membership. |
| summoning/*; existing relocation/transformation callers | Legal placement, footprint and origin after form/size change, summons and return locations. | No support aliasing or materialization inside another floor. |
| core/events.py; combat_log.py; encounter.py | Exact changed locations, subscriptions, candidate witnesses and distinct before/after grants. | Same-XY departure/arrival remain separate; event order and lineage survive. |
| world_facts.py; types/event_facts.py; player/capture.py and recorded.py | Cold geometry, address rekeys, detached after-values and native saved history. | Cold replay reconstructs height edits without querying the final live world. |
| player/facts.py; projection.py; actor_projection.py; reduction.py | Disclosed geometry, memory, XYZ field updates/removal and reducer ownership. | Hidden upper edits do not change lower-only player records. |
| player/choices.py; choice_projection.py; commands.py; server/worker.py | Shared location domains, exact selections, retained indices and current-state command validation. | Compact representations remain compact and preserve selection order. |
| server/protocol.py; recording/service/session consumers; SDK generators | Deliberate wire/recorded versions, fresh-process loading and transport fixtures. | Fresh server and regenerated clients agree; unsupported schemas fail explicitly. |
| sdk/python; sdk/player-typescript; monty_sandbox | Typed locations, inverses, selected previews, examples and packaged sandbox SDK. | SDK-driven stair moves and cross-floor commands work in fresh services. |
| dnd/ai/contracts; ai/runtime/world_projection, subjective_projection, knowledge_reduction, decision_epoch, execution | Native AI's separate spatial schema, candidate keys, knowledge, costs and secondary selections. | AI cannot merge or infer hidden floors; real commands use exact support locations. |
| NDClient consumer handoff | Reduction, selection, motion, cutaway, physical receiving surfaces and record playback. | Two floors are playable and pickable; visual cutaway changes no mechanics. |

## 6. Placement, lifecycle and atomic address changes

Commit support address and contact mode together through the existing entity placement owner. Ground/AIR/UNDERGROUND remains a contact mode, not a floor index. Same XY on another support is a location change. Source-exit and arrival publications, footprint membership and rollback must use exact locations.

Migrate deployment, simultaneous swaps/transfers, suspension reservations, restoration after support replacement, summon placement, relocation/teleport, jump landing, current forced movement and item drop paths. A missing/replaced support cannot resolve to another Tile at the same XY. Keep the existing operation's rejection, resource and event behavior; do not silently select a nearby floor.

Current Tile elevation edits allow resident actors while rejecting placed center objects and anchored connectors. Preserve this admitted behavior: rekey the same Tile and resident supported actor addresses atomically, including subscriptions, attached origins and before/after witnesses. Do not simplify implementation by banning occupied height edits. Existing boundary objects have explicit absolute height spans; changing their supporting Tile is not automatically permission to lift them. Validate the resulting geometry and define any intentional assembly-height edit separately.

Object admission must query bodies on other supports and opposite incident boundary owners. The current per-owner Tile-band collision check is insufficient. Preserve exact covered support footprints, parent/insert boundary/base relationships, component HP and partial removed bands. Detachment/reset must clean all new indexes and reject live referenced support removal according to the applicable operation, without wiping the whole column.

## 7. Shared physical queries

### 7.1 Geometry representation

Separate receiving support surfaces, supporting material and above-surface blockers. A finite upstairs slab occupies only its authored thickness; earth terrain can have a solid-below interpretation; a wall or fog volume has its own span and channel behavior. Current height-zero wall Tiles with intrinsic optical/propagation blocking must remain blocking on legacy flat maps. Do not infer an arbitrary finite wall height from their Tile elevation. Legacy input needs an explicit compatibility interpretation; new multi-floor input supplies intentional spans.

Represent ordinary slabs and panels with the cheapest exact bounds/polygons that describe them. Reuse source convex fragments for partial/curved pieces when their shape matters. Do not replace a curved aperture with a full-cell blocker or import a mesh-physics engine. A primitive is owned by an existing Tile/object/effect, with channel behavior supplied by that owner.

### 7.2 Domain and broad phase

Keep the legacy distinction between missing map cells and admitted empty space. Retain finite query-domain bounds as passive authored facts, separately from material bounds, through initialization, edits and replay. A thin slab's occupied interval does not describe the room air used by eyes, torch mounts and cross-floor rays. Support-column authoring declares its admitted air extent; unsupported gaps/shafts likewise require finite query-domain volumes. Require complete domain coverage along each queried segment or connected region; missing intervals remain outside. Air is not a walkable Tile. Material overrides admitted openness. Removing the last support must not silently change an undeclared outside region into infinite air.

For a bounded query, visit intersecting occupied XY chunks, then select existing supports and material spans within its vertical interval. A segment enumerates crossed columns/boundaries once and intersects only candidate material. Same-XY vertical segments explicitly query that column over their nonzero height interval. No empty voxel lattice and no loop over every floor in the map.

Candidate bounds must conservatively contain the consumer's selected range metric and full receiver/body extent; they must never discard a possible valid result. Under the proposed max(planar tactical, rounded vertical) metric, a target ten feet across and ten feet up is within ten feet, although Euclidean distance exceeds fourteen feet. A Euclidean sphere cannot prune that tactical query. Likewise, a large body's admitted contact can intersect a shape while its anchor lies outside. Use bounds that include those candidates, then apply the exact metric and recipient test. Sharing an index does not make all consumers use the same range shape.

### 7.3 Query contracts

| Query | Inputs/result | Rule distinction |
|---|---|---|
| Support candidates | Finite XY/height bounds → exact existing support addresses and footprints. | Presence is not reachability or disclosure. |
| Material intersection | Physical segment/volume + channel → contacts, terminal surfaces and dependency region. | Shared arithmetic; caller chooses endpoint/corner semantics. |
| Walking transition | Supported endpoints + creature/mode → admissibility, cost and contacts. | Requires body/footprint clearance; a clear point ray is insufficient. |
| Sight/light | Source sample + receiver samples + optical conditions → physical access. | Light and senses add their own range/obscurement rules. |
| Attack access | Actual action origin, target body/object contact and delivery type → legality/contact. | Remote actions and physical missiles do not acquire identical barriers. |
| Connected effect | Bounded shape and propagation channel → reachable open regions and recipients. | Air connectivity is not the walking graph. |

Make endpoint-on-floor, first opaque surface, exact corners and terminal target-provider conventions explicit. Existing movement/FOV and weapon reach differ at diagonal boundaries; preserve those policies while sharing intersection enumeration. The source's own floor must not block every outgoing ray, and a visible first wall/slab surface does not make its hidden contents visible.

Capture local immutable inputs once for a query batch and reuse them for multiple target samples. Retain the optimized 2D slope-envelope FOV only when local geometry and source/receiver sampling establish equivalence; another floor existing somewhere is not a reason to disable it globally. A floor label is not sufficient proof of equivalence. The general path is bounded physical queries, not running the old FOV separately for every floor and unioning results.

## 8. Navigation and movement

### 8.1 Reachability graph

Nodes are exact supported XYZ locations. Ordinary edges come from adjacent XY columns; height-range lookup narrows candidate supports before checking surface kind, stair axis, slope, clearance, occupancy, barriers, hazards and costs. Sharing XY creates no free vertical edge. Authored paid connectors retain their separate action/economy owner; they do not become zero-cost walking links.

For diagonals, resolve compatible intermediate supports and apply the existing corner policy to those actual edges. A lower route cannot borrow a bridge above it to pass a blocked lower corner. Creature footprint and ceiling clearance use the admitted body profile, not sprite dimensions.

Use bounded single-source reachability for the current movement budget. Keep current movement-cost semantics and existing locally selected BFS/Dijkstra behavior until an independently validated change is justified. Physical inch resolution is not an instruction to charge one five-foot movement step for every inch or visual tread. A visual stair flight does not create dozens of new walking nodes; select the authored tactical contacts.

### 8.2 Subjective routes and quality

Preserve current observer-owned seen/visible route filtering, subjective occupancy/boundary information and route disclosure. Unknown floors must not become discoverable through reachability size, paths, safe-path alternatives or costs. Objective execution still validates each committed step.

Preserve current equal-cost safety/reaction and direct-route preferences. Compute threatened supports using actual hostile origins, reach, perception and delivery access; same XY on another floor does not imply melee pressure. Straight-route shortcuts require the full walking-transition/body/cost contract, not merely an empty optical ray. This work must not reintroduce a whole-map movement-cost scan.

### 8.3 Execution and invalidation

Move retains its ordered Step events and reaction windows. If a reaction stops the mover on a stair, its native position, cost, ground contacts and player animation stop there. Arrival cannot be published at the final planned floor ahead of commitment. Same-XY relocation and connector travel have distinct departure/arrival witnesses.

Navigation cache keys include exact origin, movement mode/capabilities, footprint, budget and relevant local movement/knowledge revisions. Height/body/door/occupancy changes invalidate affected edges and routes, including an endpoint that becomes reachable through an opening. Light-only changes must not automatically solve navigation again unless perception/knowledge changes require it.

Proof fixture: lower A → stair L → stair midpoint S → stair U → upper B, with another occupied lower C sharing B's XY. Verify both directions, a blocked door, a diagonal near the opening, a paid connector alternative and a reaction interruption at S.

## 9. Sight, senses, contacts and knowledge

An observer origin includes committed support height plus an explicit mechanical sample profile. A target surface, actor body and object face are different receivers; do not infer actor visibility from the floor Tile alone. The absent mechanical eye/body-height policy is recorded in §18, not guessed from art.

The general visibility path:

1. Resolve the observer's actual source and active sense modes once.
2. Enumerate bounded candidate supports, bodies, object faces and active effect volumes using conservative bounds for the active sense metric and complete receiver extents (§7.2).
3. Capture relevant geometry/obscurement and dependency inputs once.
4. Use the qualified planar batch path where equivalent; otherwise batch physical tests for required receiver samples.
5. Apply ordinary/darkvision/devil's-sight/truesight range, effective light, fog/darkness, stealth and contact rules through the current sensory owner.
6. Produce support visibility, surface/effect evidence and entity/object contacts separately; update seen/memory and publish actual deltas.

Current upper-volume sight reveals effect surfaces and explicitly does not establish ordinary actor visibility. Preserve that distinction. Nonvisual contacts need not reveal terrain or light. Current blindsight and tremorsense both use propagation-FOV geometry; there is no existing vibration-through-structure solver to migrate. Preserve each sense's established distinctions and settle the new vertical rule explicitly; do not silently add a ground-connectivity rule or same-floor filter.

Cache keys include exact origin/sample, channel/mode/range and local geometry/knowledge revisions. Same-XY height edits must fail the current-field reuse check. Observer reverse dependencies include blocked frontiers and empty admitted paths so opening a barrier can reveal previously hidden recipients. Candidate chunk membership is never an observation grant.

Hidden upper-floor edits cannot refresh or delete remembered upper facts merely because a lower support is currently visible. Combined audiences union admitted facts for exact locations, not entire columns. Sounds or uncertain contacts retain only the location precision actually learned; no fabricated support identity or Z from current private state.

Preserve current effect-surface perception: exclude an effect's own obscuration when determining whether its near surface is visible, evaluate light at the appropriate entrance/surface sample, and retain dependencies for rejected routes. Seeing a fog/darkness surface does not expose the actors inside it. Migrate current string-encoded X,Y witness/contact/light keys and their parsers together with typed location facts.

## 10. Light and darkness

Give every existing emitter an explicit physical source position derived from its actor/device/object mount or authored world location. Support Z alone is not the light's height above the floor. Moving a carried light between same-XY floors is a real source move.

Maintain contributions per source and exact receiver, retaining the existing incremental add/remove/resolve behavior. Light receivers include playable supports and the existing visible volume/object surfaces needed by perception; do not make one XY brightness value illuminate all floors. Preserve bright/dim ranges, base light, overlapping sources, magical darkness caps and source removal behavior.

Share geometry snapshots/intersection functions with sight. Reuse final visibility results only when physical source sample, receiver definition, radius and channel semantics match. An eye-height ray and a floor-mounted light ray are not interchangeable.

Add spatial candidates for light sources whose finite influence intersects changed geometry. The current geometry-change path scans all light sources; retaining that scan would undermine scalability. The index must include potential influence through currently closed barriers, not just cells lit today, so opening a door/slab finds the previously blocked source.

For a light/source/geometry mutation: remove obsolete source contributions, compute affected new contributions, resolve changed receivers, then update observer light evidence and entity contacts before freezing completion facts. Coalesce work only within an existing mutation's safe calculation boundary; preserve every event-associated intermediate light change across distinct events.

Prove: torch upstairs behind slab; torch through opening; same-XY torch transfer; overlap with another source; darkness added/removed; opaque door opening; source destruction; no changes to remote unrelated lights/observers. Report source candidate count, tested receivers, intersections, contribution changes and observer updates separately.

## 11. Targeting, combat and available actions

### 11.1 One authoritative origin and selection meaning

Migrate BaseAction target origin/distance/access, entity action discovery, actions_functional binding and execution, device overrides and direct handlers together. An action emitted by a cannon uses the cannon's physical origin even when an actor operates it. A ground selection carries supported XYZ; a physical spell vertex carries a physical point; entity/object selections retain subject identity.

Tactical range is distinct from physical intersection and route cost. Recommended supported-target policy is the existing support-distance metric extended to canonical height, with the current flat-map range behavior preserved. Record vertical examples and intentional changes before implementation. Eye-height offsets should not inadvertently change a weapon's displayed tactical range; physical access uses those samples separately.

Melee/reach, ranged normal/long ranges, physical object contact, touch, grappling, shove and opportunity reactions all need the exact location and applicable access rule. A closed slab can block a target within range. Visibility does not automatically grant physical access, and a spell that does not require ordinary LOS must not acquire it from a universal helper.

### 11.2 Discovery, preview and execution

Keep shared subjects and location domains. Build local candidate supports and perceived subjects once per applicable origin/range/knowledge context; reuse eligibility inputs across action variants where their rules match. Do not solve every AoE at every floor position, enumerate every object hit by every aim, or return duplicate full target records per spell.

Choices enumerates legal selections according to current subjective rules. Optional Preview computes the selected shape using disclosed facts and its own self-contained domain. Command resolves retained native selection indexes and checks current authoritative state without requiring a previous Preview. Secondary selections retain order, repeated targets and per-step eligibility. Extend extra vertices and position paths to exact locations without merging same-XY candidates.

Audit direct position/range consumers in spells, reaction validation, weapon handlers, action outcomes, AI scoring, summons and interactions. Table-driven family checks can find omissions; avoid a per-spell upstairs allowlist. The implementation inventory must classify remaining 2D helpers as intentionally planar geometry, rendering, or still-unmigrated mechanics.

## 12. Areas, fields and propagation

Shapes provide bounded physical geometry; propagation supplies how an effect reaches through that geometry; receiver membership supplies who/what it affects. Keep these answers separate. A correct drawing of a sphere is not proof that its native recipients are correct.

| Family | Required physical behavior and migration |
|---|---|
| Ground patch, trap, residue | Exact receiving support footprints/contact mode; another support in the column does not inherit it. |
| Sphere | Full vertical extent around an explicit physical origin; bounded candidate bodies/supports, then the existing propagation policy. A circle repeated per floor is incorrect. |
| Cone | Physical origin/direction and length/angle. Upward or downward aim uses the actual vector; preserve origin exclusion and flat footprint conventions. |
| Line | Finite physical direction, width and length; actual contacted bodies/material. Do not extend a vertical aim into an empty 2D direction. |
| Cube | Preserve centered versus extending form and existing planar axis choice; add explicit vertical extent and supported orientation policy. No unrelated free-rotation UI. |
| Cylinder | Apply stored height and explicit top/base/origin. Preserve its distinct lateral-wall behavior; settle slab/ceiling delivery separately instead of silently imposing ordinary radial LOS. |
| Wall/line of panels/dome | Ordered vertices, thickness, vertical spans, apertures/removed sections, allowed support and current material/destruction ownership. |
| Connected cloud/spread | Traverse open physical regions clipped to the bounded shape; connect through real openings. Empty air may connect effects even where no actor can walk. |
| Moving aura/field | Anchor to the actual emitting entity/item support and physical origin; update membership on movement, elevation, suppression and removal. |

For connected spread, derive local open column intervals/regions from candidate material and connect overlapping clear boundary portions. Partial/curved blockers may split a column horizontally as well as vertically; an interval-only approximation must not join two separated passages. Reuse authored convex boundaries for those local regions, with a simple rectangle/slab fast case. Build only the region graph needed by this selected bounded effect; no persistent world-sized voxel flood.

Use one receiver-inclusion policy per shape family, shared by native execution and disclosed preview. The mechanical body/sample policy and boundary-touch conventions must be explicit. Preserve current flat-map recipient sets where geometry/rules are equivalent; new vertical behavior gets its own authored expected cases.

Migrate SpatialCondition footprint activation/change/removal, membership-source ownership, material arbitration/displacement, suppression and anchor movement. Direct handlers are mandatory consumers: Silence's verbal-casting cancellation, wall missile/forced-crossing contacts, zone entry/turn exposure and ignition must use the same membership/access results. Test the actual spell/attack/turn outcome, not just membership sets.

Replace XY-Tile-only crossing candidates with indexed physical owner bounds so a projectile or effect can cross admitted air without a walkable Tile. The current missile-interception path scans every spatial condition; select bounded intersecting owners through the same physical broad phase and preserve each owner's interception order/rule. Source position arithmetic in companion teleport, guardian footprints and directional emissions also needs explicit XYZ origin/endpoint handling, not only a changed membership container.

Creation effects, wall construction, summon placement and form/size changes go through physical admission. Antimagic or other suppression that removes a physical contribution must invalidate its dependent geometry; restoring it must revalidate coexistence. Existing spell-specific placement requirements remain with their rule owners.

## 13. Invalidation, events and history

Extend existing channel revisions and reverse indexes rather than creating a global floor revision that expires every cache. Distinguish an exact changed support, changed physical bounds and changed source/occupant. The candidate set may be coarse; final dependency intersection and rules decide actual recomputation.

| Change | Recompute/invalidate | Preserve/locality requirement |
|---|---|---|
| Actor step or same-XY transfer | Occupancy/contact, applicable observer origin, hazard membership, threats, anchored effects/light. | No structural assembly validation or unrelated-floor solve. |
| Tile height/body change | Old and new addresses/bounds, affected support relations, walking edges, rays, lights and memberships. | Dependents from both before and after geometry; not only the new location. |
| Door/window/partial wall change | Intersecting access, navigation, optical/propagation and source dependencies. | Include previously blocked observers/sources. |
| Light source/range/state change | Old/new source influence, changed contributions and relevant contacts. | Avoid navigation recomputation unless knowledge actually changes. |
| Effect creation/move/removal/suppression | Its ground or volume membership, crossing/channel contributions and direct handlers. | Keep source ownership and overlap semantics. |
| Knowledge/sense-mode change | Observer-owned visibility/contact/eligibility/navigation domains. | Never rebuild public state from undisclosed objective geometry. |
| Support/provider removal | Exact owned surfaces, dependent support claims, attached parts, connectors and affected occupants. | Apply the settled destructive outcome under the actual lineage. |

Spatial subscriptions and event candidate selection must accept exact supported locations and, where applicable, physical volumes. Migrate EventQueue, encounter perceiver selection, sensory reverse indexes and condition dispatch in the same slice as the producing mutation. Do not broadcast every event to every floor's handlers.

Before/after event witnesses retain distinct XYZ even when XY matches. Freeze location and geometry facts at their own event phase; historical lookup must not obtain today's height through a retained UUID. Keep all declaration/execution/effect/completion/cancellation ordering and full lineages. Computation dependencies remain private and never become grants.

WorldFacts and player reduction must remove an old address and add the new one for a height edit while retaining the Tile UUID. Identity replacement at one address remains a different operation. Cold facts include admitted bodies, support endpoints, bounds and changed provider state needed for replay; they do not require replay to rerun commands or import authoring tools. Preserve native mutable history; no archival or GC redesign.

## 14. Protocol, SDKs, recordings and AI

### 14.1 Compact player contract

Extend the shared location domain with explicit supported-location and physical-point forms. Document the units in the schema and helper APIs. Reuse response-local indices for repeated paths/eligibility; do not transmit a Tile UUID or full geometry record in every target entry. Native object identity remains where replacement, selection and lifecycle require it.

XYZ addresses distinguish Tile records, field updates and removals. Retain full records for discovery/replacement; field-only changes for an already known base; event-order application and unknown-base rejection. Elevation rekeys need explicit old/new address semantics, not an ordinary height field patch leaving the old dictionary entry behind. Hidden rekeys cannot tell an observer an unseen new address; reducer changes depend on admitted event-time evidence.

Disclose only known physical facts and location precision. A location selection does not disclose every other support in its column, a global height list, hidden support dependencies or private collision geometry. Preview must not use a live objective lookup to complete unknown vertical facts.

### 14.2 Coordinated versions and delivery

Current boundaries are live player wire schema 8, PlayerSequence 5 and RecordedSequence 2. Version each changed boundary intentionally, regenerate Python/TypeScript contracts and schema copies, and update generated fixtures in the same release. Include choices/path inverses, command/preview encoding, movement and spatial facts, contacts, world reducers, recording capture and transport admission.

For currently supported pre-migration single-support recordings, use only initialization and preceding admitted facts to resolve legacy XY plus recorded height. Some coordinate-only observations may lack height; preserve their older meaning rather than invent Z=0 or consult final/private state. Inspect representative actual archives before fixing the adapter. The current public decoder rejects older PlayerSequence versions and directs callers to reproject preserved native records; retain that delivery policy while making the required native input readable after the migration. Direct reading of every old public format is not a new requirement. If a native record cannot be unambiguously converted, retain explicit versioned reading or report the unsupported migration; no silent data loss. Previously unsupported archived APIs remain historical evidence, not a commitment to restore obsolete servers or live engines.

Reinstall the sandbox's packaged SDK, restart fresh services for qualification, and update Monty examples/guides to select the intended support. A currently running server does not acquire a modified Python module automatically; report the tested fresh-server version and installation path at delivery.

Native AI has a separate spatial contract from the compact player SDK. Migrate its world/subjective projection, knowledge reducer, candidate semantic keys, decision epochs, distance/threat scoring, execution and extra position validation. Audit string keys that currently format only X,Y. Controlled agents must use their own admitted facts; the new geometry cannot be a shortcut to objective hidden targets.

## 15. Client and authoring handoff

The engine plan includes consumer requirements without claiming current NDClient runtime code was inspected: the documented checkout currently exposes authoring/docs, not its runtime source. Verify the actual runtime checkout before assigning file-specific frontend edits.

The handoff must supply schema/examples and a recorded two-floor match demonstrating:

- Incremental membership/reduction keyed by exact support address; independent light, visibility, memory and selection at the same XY.
- Floor/cutaway controls and picking by the presented surface; cutaway never removes collision or discloses hidden occupants.
- Motion through actual supported stair contacts, including interrupted routes and same-XY relocation.
- Finite floor/underside, wall/opening and receiving-surface geometry from admitted data; no guessed lower floor at an unknown boundary.
- Shared choice domains, selected AoE preview and ordered multi-target/vertex selections without target expansion or repeated full validation.
- Event-time geometry and recorded playback without consulting final current state.

Keep source authoring, engine physical facts and renderer presentation separate. A richer editor document may retain incomplete candidate work; exporting a playable native map must pass the physical admission contract. Do not make every undoable editor gesture an engine mutation or copy its reconstruction solver into the client.

## 16. Computation and scalability

The design must keep local work local. Initial physical-map validation is allowed to inspect the completed map. A structural edit follows the changed assembly/contact dependencies; its cost may scale with a genuinely affected large structure. An ordinary movement action must not validate all structures, scan every support height, or recompute every light/observer.

Expected work bounds are expressed in relevant candidates, not promised timings:

| Operation | Intended work |
|---|---|
| Exact support lookup | One canonical XYZ lookup. |
| Candidate supports in a column | Ordered-height range lookup plus returned supports. |
| Budgeted navigation | Reached support nodes/edges inside the actual budget; preserve the uniform-cost fast path where valid. |
| Physical ray | Crossed indexed columns/boundaries plus overlapping candidate fragments. |
| Observer/light solve | Relevant receiver samples and local geometry; captured once per batch. |
| Geometry invalidation | Intersecting dependency/source candidates, including blocked frontiers. |
| Selected AoE | Bounded shape candidates/connected regions, performed on demand. |
| Projection/encoding | Actual disclosed changes; shared locations and field deltas. |

Extend the existing movement/action-discovery diagnostics and devtools/player_server_acceptance/movement_scaling.py with its movement_scaling_fixture.py. Record source filesystem/environment because WSL /mnt/c I/O affects startup. Measure plain wall-clock samples separately from fine instrumentation; do not compare different observer order, route, actor, instrumentation or event semantics as a speedup.

Temporary phase instrumentation must break down navigation neighbor capture/search/materialization/threats; geometry candidate capture/intersections; observer geometry/light/contact/hazard/delta work; light source selection/contribution work; dispatch; selected shape geometry/propagation/membership; native capture; projection; serialization; SDK admission. Report inclusive and exclusive time without double-counting GC. Add counts for candidate supports/fragments, path nodes/edges, source/observer candidates, rays/columns, changed recipients, allocations/payload bytes and cache reuse.

Scaling matrix: the same local stair/torch/action fixture with increasing remote XY content; increasing remote Z floors outside query influence; additional genuinely relevant local floors; increasing active observers/lights; increasing retained history; repeated geometry edits. Compare incremental output against a full refresh reference. Neither correctness nor performance can be certified by timing one helper on a toy map.

The existing 9.5 ms movement goal remains open. Keep the benchmark's end-to-end receipt, worker and client-consumption clocks separate; a fast geometry helper or worker time alone does not meet the whole target. Establish measured phase budgets after the first integrated slice; do not invent gains for unimplemented algorithms. Remove or disable detailed diagnostics in the qualified production path after evidence is saved.

## 17. Implementation sequence

Start with one small authored building: two occupied supports at the same XY, a stair, a finite floor slab, an opening, a door and a carried torch. Qualify its actual heights and the range/body rules it exercises before fixing their representation. Reuse reviewed source geometry and directional support relations. Keep the existing flat-map behavior and timings as the comparison.

**Make that building playable through the real server and SDK.** Introduce XYZ storage and physical admission, then connect placement, walking, sight, light and attack access in that fixture. Actors must walk upstairs, see and illuminate through the opening but not through the slab, select a legal attack, and stop on the correct support when a reaction interrupts movement. Migrate events, projection, protocol, SDK locations and recorded facts alongside these operations, so the same journey can be commanded and replayed from outside the engine. Movement is only demonstrated when its perception and reaction dependencies work too. Measure this journey immediately and provide its recording/schema to the client integration work.

Migrate existing fixture inputs and preserve the affected flat-map regressions alongside these changes, following §19. Passing only the new building example is insufficient.

**Extend the working building to the remaining mechanics.** Use the owner inventory and acceptance cases to cover shape families, direct spell handlers, special senses, traps/residue, large footprints, connectors, relocation, construction, suppression and occupied geometry changes. For each addition, make its real action, disclosure and replay work together. Settle support-loss outcomes before adding destructible bearings; prepare occupant/item transfers before retiring their source support. Complete native AI and legacy recording readers against the same location contract. These are coverage tasks with shared dependencies, not separate subsystem releases. Keep incomplete scenes out of the public encounter catalogue.

**Qualify the complete feature on the actual consumers.** Use fresh server and sandbox installations, the frontend journey in §15, a two-agent match and saved replay. Run the remaining acceptance cases and scaling comparisons in §16/§19; resolve regressions and remove detailed diagnostics. SDK/client checks and measurements start with the first working building and continue as its mechanics expand. This last pass establishes that the full feature can ship; it is not the first integration attempt.

The required plan-adherence subagent tracks progress toward this playable result and missing owner/case coverage. Anti-slop and anti-OOP reviewers check the changes. Internal commit order can follow real code dependencies; it does not create more milestones or require a separate framework for each subsystem.

## 18. Explicit rule decisions before dependent implementation

These are proposed policies where existing code does not settle the new vertical behavior. Resolve each against concrete examples before implementing the affected behavior. Height representation and the first building's body/range rules come first; support-loss decisions are needed when adding destructible bearings. Unrelated decisions do not block work on the building. Ordinary file/type/index choices remain implementation work within the authorized design.

| Decision | Recommended starting point | Cases that must fix the meaning |
|---|---|---|
| Canonical support-height precision | Integer inches after source precision qualification; physical geometry preserves finer local detail. | Legacy 0/5/10 ft supports, ten-inch tread, six-inch slab, unsupported source precision and exact SDK round trip. |
| Tactical vertical range | Extend existing max(planar tactical distance, rounded vertical distance) support metric, retaining flat-map behavior. | Same XY ten feet apart; diagonal plus rise; normal/long weapon range; device origin. |
| Body/eye/target samples and clearance | One explicit coarse mechanical profile per relevant creature size/form, with posture effects owned by mechanics; source fixtures use their mount. No art-derived dimensions. | Low ceiling, prone target behind sill, large creature at stair, same-XY ray, target above a railing. Numeric profiles and partial-cover policy require an explicit gameplay decision. |
| Shape origins/orientation and recipient inclusion | Preserve current flat family rules; explicit physical origin, vertical extent and one shared body/sample inclusion policy. | Upward cone/line, centered/extended cube, sphere crossing slab, cylinder above/below a ceiling, ordered wall vertices. Cylinder's lateral-wall exception must remain explicit. |
| Special senses | Preserve current sense distinctions and disclosure. Do not introduce a vibration simulation under tremorsense migration. | Blindsight/tremorsense through floor/opening versus opaque wall; truesight/darkness; nonvisual contact without terrain disclosure. |
| Loss of supporting material | Existing authored dependencies and alternative bearing requirements; remove genuinely unsupported surfaces and reuse native supported falling where applicable. | One of several bearings removed, sole bearing lost with actor/item above, no lower landing, suppressed/restored provider, partial destruction and complete lineage. Confirm unsupported/no-landing outcomes before adding them. |

Flight remains excluded. Record unresolved behavior explicitly; do not silently make a shape, sense or action work only on the caster's floor.

## 19. Validation matrix

Follow HOW_TO_TEST.MD: observable inputs and outcomes, native actions/events first, thin transport tests, then a small real client/agent journey. Extend existing relevant fixtures; do not freeze private dictionary layouts or mirror helper code. The expected state includes exact location, costs, contacts, effect recipients, event order and audience-visible history.

| ID | Input/scenario | Required observed result |
|---|---|---|
| MF01 | Import two support tops at one XY, plus fractional physical stair faces. | Both playable locations retained; physical geometry is not replaced by the old highest-surface adapter. |
| MF02 | Insert intermediate height; include negative/basement height. | Existing XYZ addresses unchanged; units round-trip exactly. |
| MF03 | Valid directional assembly/contact loop versus missing return, incompatible join, unsupported component or circular bearing justification. | Valid geometry admitted; invalid completed map rejected before initialization; contact cycles alone do not reject. |
| MF04 | Upper earth/deep slab versus thin supported slab over occupied lower room. | Invalid overlap rejected without mutation; valid headroom permits both levels. |
| MF05 | Actor/item/condition/light on each of two same-XY supports. | Independent occupancy, ownership, light and ground state. |
| MF06 | Occupied height edit; cancellation; collision at new height. | Accepted edit atomically rekeys resident state; rejected/canceled edits preserve previous locations and resources. |
| MF07 | Same-XY simultaneous transfer; suspend/return after support replacement. | Exact destinations/reservations; stale support never aliases a different floor. |
| MF08 | Large object/attached window across supports; tall lower object versus upper slab. | Coherent footprint, parent ownership and physical coexistence; one damage identity. |
| MF09 | Up/down stairs, blocked landing/door, wrong-axis stair and diagonal near bridge. | Valid route/cost; invalid transitions rejected without borrowing another floor's corner. |
| MF10 | Equal-cost routes near hazards/reactions; proposed straight route. | Existing safety and direct-route preference preserved; shortcuts validate actual movement. |
| MF11 | Paid connector and ordinary stair alternative; reaction stops stair move. | Correct action/resource cost; interruption and ground contact at committed support. |
| MF12 | Same-XY vertical ray; closed slab, opening, wall below/above ray and legacy opaque Tile. | Correct material intersection and compatibility; own floor does not block every ray. |
| MF13 | Room air above a thin slab, finite unsupported gap, missing domain interval and inserted material; initialize/edit/replay. | Domain facts survive; admitted air participates; any uncovered interval remains outside/blocked; no invented walkable support. |
| MF14 | Door/slab opens after observer was blocked. | Reverse dependency finds observer; incremental visibility equals full refresh. |
| MF15 | Eye and light at different heights near aperture. | Independent correct sight/light results; inappropriate final-FOV reuse cannot pass. |
| MF16 | Torch transfer, overlap, darkness cap, source removal and remote sources. | Exact receiver deltas, preserved event chronology and bounded candidate work. |
| MF17 | Ordinary/special senses, invisibility, stealth, fog and darkness. | Selected vertical rules and existing contact/disclosure distinctions hold. |
| MF18 | Melee/reach/ranged/touch/object contact/device origin across floors; ten feet across plus ten feet up under the selected tactical metric. | Range and physical access both correct; no XY-only threat, zero distance or candidate pruning inconsistent with the final metric. |
| MF19 | Choices → selected Preview → Command, and Command without Preview. | Exact native selection, correct subjective preview, authoritative execution and no mandatory preview dependency. |
| MF20 | Ordered repeated targets and extra wall/shape vertices sharing XY at different Z. | No deduplication, reordering or wrong-floor inverse mapping. |
| MF21 | Sphere, cone, line, cube, cylinder and wall/dome across slab/opening; large body intersects while anchor is outside. | Explicit family geometry/propagation and actual damage/effect recipients agree; candidate bounds retain all possible recipients. |
| MF22 | Connected cloud around aperture through air without walking supports. | Correct bounded space connectivity; no teleport across separated regions. |
| MF23 | Ground trap/fire/ice/wet/residue below another actor. | Only actual receiving/contact supports trigger; real turn/entry effects agree. |
| MF24 | Moving aura, Silence verbal cast, wall crossing and suppression/removal. | Direct handlers and membership use the same geometry; all sources clean up. |
| MF25 | Construction, summon/form change, attached destruction, partial bearing loss and restoration with occupants/items. | Physical admission or settled aftermath; transfers prepare before support retirement; no dispatch sees actors on missing supports, invalid live support or leaked partial state. |
| MF26 | Hidden upper mutation/elevation/removal; lower visibility; audience union. | No unauthorized upper contents, new coordinates or memory refresh in player bytes. |
| MF27 | Tile field delta/replacement/rekey and unknown base. | Exact addressed update; correct identity semantics; every intermediate change preserved. |
| MF28 | Fresh-process replay of movement, geometry edits and destructive lineage. | Saved native/player state reconstructs without final-world lookup or command execution. |
| MF29 | Reset/rebuild and fresh sandbox SDK/server. | No stale spatial/dependency/source indexes; actual packaged client accepts current schema. |
| MF30 | Native AI and two independent Monty agents through a terminal match. | Real exact-location actions, stairs and cross-floor combat; both saved views replay. |
| MF31 | Frontend picking/cutaway/interrupted motion/preview and playback. | Presented support matches selected support; cutaway changes neither knowledge nor mechanics. |
| MF32 | Fixed local work plus remote XY/Z content; relevant extra floor; long history. | Correctness parity and reported phase/candidate scaling; no whole-map/floor multiplication. |

Relevant current tests include engine test_world_geometry_contract, test_world_modification, test_traversal_connectors, test_windows, test_window_attack_access, test_local_optical_inputs, test_moving_ordinary_light, test_sensory_movement_origin, test_senses_light_stealth, test_cloud_propagation, test_globe_propagation, test_deferred_aoe_discovery, test_multicell_objects and test_multicell_residue_fear; player test_compact_choices, test_projection_local_world and test_tile_field_updates; SDK choice/transport tests and Monty player tests. Verify exact paths before implementation. New cases belong with their owning feature, not a new parallel test framework.

Run focused checks as each observable behavior is added, then the affected native/player/SDK/architecture suites and real match/replay qualification. Repeat or broaden checks for a new change, failure or unresolved concern. Report actual environments, commands, results and limitations. Passing a source-policy check or saved constructor report does not prove playable multiple floors.

### 19.1 Existing-suite audit

The first version of this plan identified acceptance cases but did not audit the cost of migrating existing tests. The following inventory comes from a 2026-10-13 read-only source audit using `rg --files` and Python AST parsing. These are test-file and function-definition counts, **not collected/parameter-expanded cases, expected failures or passing results**. No suite ran during this audit.

| Current source | Files | Python test definitions | Migration significance |
|---|---:|---:|---|
| tests/engine | 168 | 1,498 | Map/actor setup, paths, senses, spatial spell effects, placement, native facts and lifecycle. |
| tests/player | 32 | 106 | Live/recorded projection, compact choices, event-associated deltas, audience privacy and transport. |
| tests/ai | 13 | 55 | Separate AI knowledge/selection schema, movement guards, real controller execution and live matches. |
| tests/progression | 13 | 127 | Mostly preserve rule expectations; migrate spatial setup where used. |
| tests/architecture and root test files | 15 | 111 | Dependency/schema/code-generation/packaging checks; not evidence of correct gameplay. |
| tests/manual | 203 | 1,937 | Contains real spatial and spell regression coverage as well as older contracts; not automatically excluded. |
| tests/paused_server | 3 | 8 | Documented old-server import failures; distinguish these from new regressions. |
| sdk/python/tests; monty_sandbox/tests | 4 | 41 | Exact selections, packaged protocol validation and actual sandbox client behavior. |

The current player TypeScript SDK additionally has two test files with 30 lexically counted `test(...)` calls. The separate older sdk/typescript package has nine test files with 81 such calls; its older replication contract must not be mistaken for coverage of the current player SDK. Counts do not imply all these tests need edits. The native suite alone has 411 parametrization decorators, so definition counts cannot be used as an execution-time estimate.

[Root pytest configuration](/mnt/c/Users/tommaso/Documents/Dev/dnd_engine/pyproject.toml:37) searches all of tests without a manual/paused exclusion; it does not discover the SDK or Monty directories. [Paused-server documentation](/mnt/c/Users/tommaso/Documents/Dev/dnd_engine/tests/paused_server/README.md:15) explicitly records broken old imports. The documented tests/game directory is absent in this checkout, and some devtools still import it; tests/architecture/test_presentation_schema_export.py also imports the absent game.export_schema. Do not copy those commands into a claimed validation result. No .github workflow directory was found here; local validation must not be described as an existing CI gate.

### 19.2 Migrate fixtures and assertions with their owners

[Root conftest](/mnt/c/Users/tommaso/Documents/Dev/dnd_engine/tests/conftest.py:11) only installs content. The main actor helper is [create_test_entity](/mnt/c/Users/tommaso/Documents/Dev/dnd_engine/tests/engine/support.py:26), whose module is imported by 88 test files in the scanned suites. It receives an already constructed EntityConfig: changing its deployment call cannot repair coordinates rejected during configuration construction. The [spell regression helper](/mnt/c/Users/tommaso/Documents/Dev/dnd_engine/tests/manual/spell_regression_support.py:17) owns both its rectangular arena and actor configuration; 46 test files across the scanned suites import that module. Feature-local constructors in grid pathfinding, spellcasting, spell families and senses need migration too.

Use explicit locations when constructing configs, map entries, targets, paths and expected facts. An existing flat-only fixture may translate its declared base plane at its input boundary, before config validation; this must not become a production fallback that guesses the floor. Raised fixtures use their actual authored support height. Preserve XY dimensions, footprint offsets, cardinal deltas and planar polygon coordinates. The generic two-element-array case in tests/test_player_python_codegen.py remains a valid generator test; a field called position does not make every tuple test a world-location contract.

Concrete cases to carry through the first building's implementation:

| Existing test owner | Required handling |
|---|---|
| [Grid paths](/mnt/c/Users/tommaso/Documents/Dev/dnd_engine/tests/engine/test_grid_pathfinding.py:170) | Update path keys/endpoints and map calls; retain destination-cost sums and established route behavior. |
| [Fireball propagation](/mnt/c/Users/tommaso/Documents/Dev/dnd_engine/tests/engine/test_globe_propagation.py:33) | Preserve the flat 36/49-support doorway outcomes, deposits and subjective preview. Update position unpacking without throwing away Z in assertions. |
| [Occupied observer elevation](/mnt/c/Users/tommaso/Documents/Dev/dnd_engine/tests/engine/test_cloud_propagation.py:172) | Preserve raise/restore behavior and private ground state; this fixture cannot be flattened to Z=0. |
| [Geometry setup](/mnt/c/Users/tommaso/Documents/Dev/dnd_engine/tests/engine/test_world_geometry_contract.py:558) | Replace direct Tile.height assignment with admitted height rekey; preserve the walking/slope rule being tested. |
| [Recorded world facts](/mnt/c/Users/tommaso/Documents/Dev/dnd_engine/tests/engine/test_recorded_world_facts.py:81) and [AI knowledge](/mnt/c/Users/tommaso/Documents/Dev/dnd_engine/tests/ai/test_event_knowledge.py:88) | Migrate recorded addresses, sensory string keys and exact remembered positions; retain registry-independent replay and event-time knowledge. |
| [Player local world](/mnt/c/Users/tommaso/Documents/Dev/dnd_engine/tests/player/test_projection_local_world.py:57) and [tile field updates](/mnt/c/Users/tommaso/Documents/Dev/dnd_engine/tests/player/test_tile_field_updates.py:35) | Migrate fabricated cold facts and reducer keys. Split ordinary field updates from height rekeys; keep event order, replacement identity, unknown-base rejection and hidden-state behavior. |

For each failure, establish whether it is setup/API breakage, an intentionally changed spatial contract, or an actual regression. Save/resource/concentration/damage expectations do not change merely because their actors now have XYZ addresses. Review changed expected values against the approved rule. Never normalize output to XY, add blanket skips, or replace all expected output with a newly generated result.

### 19.3 Add vertical coverage without multiplying every test

Use one small valid building fixture through native construction/admission, with named exact supports, stair contacts, physical/query-domain facts and provider identities. Give each test an isolated runtime lifecycle. Actor/spell selection, resources, commands and expected outcomes stay in the owning test. The fixture must not compute expected visibility, mark every floor known or inject private memberships.

The MF cases above are coverage requirements, not a requirement for 32 new test files or for duplicating every spell at every height. Put shape/range/propagation matrices at their shared native boundary, then test real effects for distinct execution paths such as Silence cancellation, moving auras, ground traps, wall interception and support destruction. Extend existing feature helpers when they express the case clearly. A small named matrix should include same XY/different Z, opening versus slab, exact range/body boundaries, occupied rekey/cancellation and hidden-floor evidence.

Add a few invariants through those same helpers: translate a finite authored assembly and its query bounds together vertically; insert an unrelated remote floor; vary support insertion order; compare incremental light/visibility with a full refresh. Assert specified outcomes as well as agreement, since two paths can share the same bug. Do not introduce a new property-testing framework or run the entire spell catalogue across a Cartesian product of floors.

A current encoder/decoder round trip cannot prove old-record compatibility. Retain representative currently supported native-version bytes with independently stated expected observations before changing producers, then prove their conversion/reprojection under §14.2. Existing replay tests generally create current records immediately before reading them; they do not provide that fixed old-input coverage. Keep old inputs separate from fixtures intentionally regenerated for the new live protocol, and leave the explicitly frozen agent_docs/server-api-v1 evidence untouched. For new records, assert exact intermediate locations, audience privacy and rekey behavior after a fresh-process replay, not just equality of two reducers fed the same mistaken facts. Generated schema equality must be accompanied by positive XYZ and negative ambiguous/malformed-location admission cases in both current SDKs. Existing invalid-handshake, selection order, unknown-base and transport lifecycle tests remain required.

Add a same-XY/different-Z eligibility inverse case in both SDKs: the current TypeScript implementation explicitly formats an X,Y key, whereas Python already constructs tuple(position) but declares a 2D type. These can fail differently. Current Monty tests use mocked transport or REPL execution, and its flat trial/scout journey does not establish stair behavior; the recorded two-floor server journey must cover actual SDK movement and selection as well. Monty's operator journal is not a complete native game replay: retain the server recording for replay qualification. Preserve small transport lifecycle tests as transport tests; they do not each need a building simulation.

### 19.4 Execution and baseline

Before the first engine edit, use the documented uv environment to collect and run a current baseline with reported node IDs, collection failures, durations and source location. Establish the working native/player/AI/progression/architecture/root selectors; inspect manual failures individually rather than declaring the whole directory obsolete. Report paused-server failures separately without silently hiding them or expanding this feature into an old-server repair. The audit above supplies scope, not that execution baseline.

As each behavior changes, run its focused existing tests and new vertical cases. Broaden once a coherent building journey works, and again when later mechanics warrant it. Run sdk/python/tests, monty_sandbox/tests and `npm test` in sdk/player-typescript explicitly; root pytest does not cover them. Verify all schema/identity copies written by devtools/export_player_protocol.py, then the Python and TypeScript generated declarations and actual package admission. Select real process/service tests deliberately: tests/ai/test_live_ai_matchups.py launches services, and cold-load/replay tests may spawn Python. A directory name does not guarantee a cheap in-memory lane. Existing engine singleton state must remain isolated; do not run multiple worlds concurrently in one test process to accelerate the suite.

Keep rule permutations in native tests and a small number of server/SDK/frontend journeys for wiring. Extend the existing devtools/player_server_acceptance/run.py installed-client journey; install the regenerated SDK in Monty's own environment too. Measure the first building and subsequent scaling cases separately from instrumented correctness tests; do not turn the 9.5 ms goal into a flaky per-test assertion. Gallery's current movement policy measures XY, and movement_scaling.py selects a local XY window. Define the compared physical region and exact supported routes for the vertical benchmark; preserve Z and causal order in compared values. Actual frontend tests require the runtime checkout identified in §15. Final qualification reports exactly what ran, what passed and what remains blocked; a green subset is not a full-suite result.

## 20. Review and delivery record

Required reviewers: multifloor_ecs_review for ECS/anti-OOP and lifecycle coherence; multifloor_antislop_review for complete behavior, computation, scope and performance. Both supplied additional source findings for this replacement plan. Their earlier approval of the initial study does not approve this replacement automatically.

Replacement-plan review completed on 2026-10-13. Both reviewers read this saved document, requested material amendments, reviewed the revisions, and approved it as an implementation plan with no remaining material issue in their reviewed scope:

| Reviewer | Finding resolved in this plan |
|---|---|
| ECS / anti-OOP | Prepare occupant/item outcomes before removing source supports; retain source membership through transfer and publish coherent destructive facts (§4.3, MF25). |
| ECS / anti-OOP | Store finite query-domain facts separately from material bounds through initialization, editing and replay (§7.2, MF13); distinguish valid contact loops from circular bearing justification (§4.2, MF03). |
| Anti-slop / computation | Candidate bounds conservatively follow the consumer's metric and full body extent, including diagonal-plus-rise and outside-anchor cases (§7.2, §9, MF18, MF21). |
| Anti-slop / integration | Full subjective movement/reaction qualification requires working perception and reach/access together (§17). |

This review validates the plan's scope, ownership, dependencies and qualification strategy. It does not approve unresolved §18 gameplay decisions, certify unimplemented behavior, or establish performance gains. Implementation review remains separate and requires actual code/test/performance evidence.

The human subsequently rejected the eleven-stage structure. Section 17 now organizes work around a playable building, completion of its mechanics and production qualification. The owner inventory remains a coverage checklist. Both reviewers separately approved this revision: it brings movement, perception, reactions, server/SDK commands and replay into the first playable result while preserving physical admission, lifecycle dependencies and decisions before affected mechanics.

The human then identified insufficient study of existing-test migration. Both reviewers audited current test/fixture owners and separately approved the added §19.1–19.4 and the supported-archive clarification in §14.2. The audit recorded source counts, actual helper boundaries, existing behavioral expectations, schema/SDK differences, replay limitations and stale test lanes. No tests ran; the execution baseline and actual migration failures remain to be measured before engine changes.

Delivery must state which behaviors and acceptance cases passed, the fresh server/SDK/client path tested, the measured timings, and any explicitly unresolved gameplay or consumer limitation. A storage demonstration, one upstairs screenshot or a fast standalone ray is not completion of this plan.
