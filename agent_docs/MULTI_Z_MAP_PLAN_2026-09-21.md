# Multiple supports, usable windows and multi-storey gameplay

Date: 2026-09-21. **Design proposal; no production implementation authorized by this document.** The user requested reasoning and a delegated multi-Z plan. The order of furnished single-floor intake versus a small multi-storey proof has not been chosen. This document extends the [native/ECS study](INTERIORS_MAP_ECS_STUDY_2026-09-21.md) and accompanies the [interiors integration plan](INTERIORS_INTEGRATION_PLAN_2026-09-21.md). Read `RECOVERY_PLAN.md` first. Independent anti-slop and anti-OOP/ECS review is required before implementation; the review record is below.

The concrete objective is one encounter in which two characters can occupy the same XY on different supports, use a real staircase, see or attack through a legitimate opening, and remain separated by a closed floor. This must work through ordinary native actions, observation and saved subjective replay. It is not a general 3D physics project.

## Recommended direction

Keep **Tile UUID as support identity**. Keep XY and support elevation as that Tile's geometry. GridMap stores multiple independently addressable supports in an XY column. Actors, placed items, ground effects, paths and observed contacts identify the support they mean. Floor slabs and boundary panels supply the limited physical geometry needed to decide whether a path crosses solid material.

This reuses the current Tile, placement, event, sensory, handler and replay owners. It does require a connected spatial migration. Changing only `_tiles`, only rendered height, or only pathfinding would leave different systems talking about different places.

| Choice | Useful result | Limitation for this request |
| --- | --- | --- |
| Separate scenes for each storey | A stair can transfer between otherwise independent maps. | No simultaneous sight, projectiles, light or area effects between floors. The current singleton map still needs a world-transfer contract. This is a different game behavior, not a free multistorey implementation. |
| Sparse XYZ-indexed supported tiles | Direct coordinate lookup distinguishes stacked surfaces without storing empty air. | A legitimate alternative index, compatible with existing Tile UUID identity. Elevation edits update coordinate keys; all occupancy/query/observation consumers still need unambiguous addresses. It does not itself specify slab thickness, openings or neighbors. |
| Full volumetric/voxel grid | Addresses occupied and empty volume cells throughout space. | More representation than the selected supported-floor game needs; support, queries and replay still require design. This is distinct from sparse XYZ indexing, not an inevitable consequence of using a third coordinate. |
| Existing supported surfaces, explicitly addressed | Several floors, intermediate stair supports and balcony surfaces coexist; empty air is geometry between them. | All mechanically meaningful support lookups must carry enough context. This is the smallest model matching the requested encounter. |

The first proof should be a small two-level structure plus one usable window. A complete furnished house should follow that proof if multi-storey work is selected first. Alternatively, the selected one-floor lodge can exercise furniture/attachments while the shared aperture work is implemented there. Neither order has user approval yet. The two branches converge on the same support and boundary contracts; there should not be a temporary second house engine.

## What the current model means

These are current scope limits, not newly discovered defects in an allegedly complete 3D engine.

| Owner | Current contract and evidence | Required change for simultaneous storeys |
| --- | --- | --- |
| `dnd/core/base_tiles.py:55`, `:100` | Tile owns persistent conditions, XY, surface, and height in five-foot steps. | Retain identity and composition; allow another support in the same column. |
| `dnd/core/gridmap.py:131`, `:805` | `_tiles` is XY→Tile; `_tiles_by_uuid` resolves UUID→XY→that one Tile. | Direct UUID→Tile storage and an XY→support IDs column index. |
| `dnd/entity.py:658`, `:779`; `gridmap.py:2092` | Deployment/movement centrally commits entity position and Tile membership. Same XY/layer currently returns early. | Commit the actual support as part of the existing placement transaction, including same-XY support changes. |
| `dnd/types/world_placement.py:30` | Object placement already records its supporting Tile UUID, XY and vertical envelope. | Resolve by support, preserve the actual footprint and local mount relation. |
| `gridmap.py:1715`, `:3316`; `dnd/core/world_edges.py:133` | Paths use XY nodes; gradual height changes require matched stair/ramp surfaces and slope axis. | Support-addressed nodes and the same admitted per-edge rules. |
| `dnd/core/traversal_connectors.py:122` | Connector runtime endpoints already carry support UUID/elevation; definitions and registration still resolve XY. | Definitions resolve support endpoints explicitly where ambiguity exists. Reuse the action only for genuine discrete traversal. |
| `dnd/core/world_edges.py:76` | Structural contributions have height intervals, but every listed nonmovement channel is blocked regardless of query height. | A real height-aware segment/panel query for apertures and cross-floor optical/propagation paths. New fields alone do nothing. |
| `gridmap.py:3105`, `:3312`, `:3976`; `dnd/blocks/sensory.py:657` | FOV/light and visible cells use XY. | Resolve candidate supports and physical ray geometry before publishing support-specific results. |
| `dnd/spatial/area_conditions.py:42`, `memberships.py:269`, `transitions.py:47` | Spatial condition footprints, membership and event-handler indexing use XY. | Support footprints for ground effects; explicitly resolved supported recipients for volumetric effects. |
| `dnd/core/base_actions.py:1217`; `dnd/core/aoe.py:188` | Target origin/range and area shapes are predominantly XY. | Carry support geometry through the existing shared target/shape owners; decide vertical rule semantics explicitly. |
| `dnd/core/events.py:4569`; `dnd/core/combat_log.py:13` | Step source/destination grants are independently frozen, but their coordinate keys are XY strings. | Preserve those independent grants and distinguish their supports. |
| `dnd/world_facts.py:31`; `game/player_facts.py:502` | Retained world/player tile maps collapse by XY. | Keep disclosed supports separately; never fill an unseen floor from live native state. |
| `game/projection.py:270`, `:290` | Pick candidates already contain Tile UUID, XY and elevation; their producer and ordering assume the current world. | Submit the permitted support surfaces and make floor/cutaway selection explicit. A UUID on the candidate alone is not complete stacked picking. |

The incoming art's preview graph is not authoritative support coverage. Layout 1 has 96 physical floor cells and only 75 preview walkable nodes because 21 furniture cells were removed. Physical floor intake uses level/floor records minus real openings, then indexes furniture separately. A destroyed bed releases occupancy over existing Tiles; it never creates previously missing floor. The full evidence and handoff paths are in the companion study.

## Passive data contracts

The names below describe responsibilities, not a request for a new registry or class hierarchy. Prefer additions to the existing records. New records should remain dependency-leaf values consumed by existing systems.

### 1. Support identity and geometry

- `Tile.uuid` is the support address. `Tile.position` remains XY, and `Tile.height` remains the current five-foot support elevation unit. No UUID derived from a coordinate or file hash.
- GridMap owns `tiles_by_uuid` and `support_ids_by_xy`. The latter is an index over the former, not another mutable world. Removal and replacement continue through existing world modification admission/events.
- An authoring label such as `lower_hall` or `upper_gallery` may resolve to a Tile UUID when constructing the world. A building's storey label is authoring/view grouping, not a physics key. Stair supports at intermediate elevations need no artificial fractional storey.
- A support elevation change retains its identity and emits its normal world change. Moving or replacing an occupied support still respects current admission rules; moving platforms and structural collapse are outside this feature.
- XY-only queries remain valid when the caller deliberately requests a column, or at legacy single-support boundaries that can resolve exactly one support. A mechanical target lookup must never silently select the highest, first or camera-selected support.

Several distinct supports can share XY. The first feature does not need two independent supports at exactly the same XY **and** top elevation; overlapping support surfaces at the same elevation should be rejected at authoring/admission unless a later concrete mechanic establishes another meaning. This is a bounded geometry invariant, not a floor-index convention.

### 2. Placed actors and items

An actor needs an authoritative supporting Tile reference in its spatial placement. Proposed minimal implementation: add that reference to Entity's existing placement data and use the present attach/move/detach/suspend/restore owner to maintain it with Tile membership. Existing inherited XY remains a compatibility projection of that support during the migration; it is not an independently writable floor choice. Do not add a second mutable actor elevation or an actor `floor` flag. Senses receives the same committed support context.

Before implementing this field, finish the concrete call-site pass through deployment and `BaseBlock.set_position` propagation. Mechanics-bearing children currently inherit XY. Their spatial origin must resolve through their actual owning entity/item or the typed origin already supplied to the action; copying a separately mutable support field into every condition/action would recreate drift. The implementation review must confirm the single mutation owner rather than merely add assertions around two independent states.

BaseItem already has Tile ownership and `WorldObjectPlacement.tile_uuid`; reuse it. Placement admission accepts a support ID and derives XY/base elevation. An exposed cup uses a parent-object support/mount relation plus its ultimate floor support, not container inventory and not a new walkable Tile. The first selected aftermath remains native detachment/breakage under the parent's destruction lineage, as described in the interiors plan.

Large furniture has one identity, HP owner and destruction event. Its committed placement lists the actual occupied support IDs resolved from authored local footprint offsets and orientation. The offsets cannot simply choose every Tile at a neighboring XY: placement must select a coherent supported footprint at the intended surface and reject an unsupported/ambiguous placement. GridMap's existing band index can reference the same object UUID at several supports. Reach, blocking, partial observation, removal and remnant occupancy use that same footprint. Do not create one invisible blocker entity per occupied cell.

Creature volume and furniture volume differ from support identity. Preserve current creature size/space rules; do not turn a one-cell Medium creature into a mesh or reinterpret the existing AIR contact layer as upstairs. The small proof uses ample headroom. Supporting arbitrary cramped ceilings or large creatures under low beams requires an explicit creature envelope policy, not a guessed height copied from sprite pixels.

### 3. Solid earth and finite floors

A hilltop support currently belongs to the height-field terrain model. An upstairs floor must not become an earth column filling the downstairs room. Add a minimal authored support-body description to the existing Tile/world fact:

| Body | Meaning |
| --- | --- |
| Earth/solid terrain below the top | Retains the existing raised-terrain meaning for existing maps. It is not an upstairs floor. |
| Finite slab | Has a physical depth below the support top and explicit relevant blocked channels. Its underside/top delimit the obstructing interval. Empty space remains below it. |

Keep the top derived from Tile elevation; do not store competing mutable top values. A finite slab's thickness may be expressed in feet finer than a five-foot walking rise. Converting all native support heights to arbitrary floats is unnecessary. The initial example can author a one-foot slab at a ten-foot support top, but those are illustrative content dimensions, not inferred facts about every supplied house.

A stairwell hole has no slab over the opening. It is not a transparent flag on an otherwise solid floor. Stair supports have their own finite physical assembly; do not fill the space below a staircase by copying the earth-column rule. Floors and roof slabs can occlude without becoming destructible in this unit. Presentation cutaway never removes them from mechanical queries.

### 4. Boundary panels and apertures

Reuse `WorldEdgeStructuralContribution` / `BoundaryStructure` for provider identity, material, current state and channels. An authored window contributes a few rectangular solid panels on its cardinal boundary: horizontal interval along the edge, lower/upper physical height relative to its support, and blocked channels. Full-width walls are the simple case. Sill, header and side frame are a few records belonging to one structure, not a scene of independently damaged bars.

The horizontal boundary coordinate can remain an XY edge for spatial indexing. A **walking transition** is identified by its actual pair of supports. A physical ray collects relevant contributions along the crossed XY boundary, including providers anchored on another support whose physical span intersects the ray. Looking only at the two endpoint supports would miss a wall in between; mixing all heights without intersection would restore today's coarse blocking.

The structure's footprint/bands are broad-phase occupancy. Its aperture panels answer the precise selected optical/propagation query. Parent support, physical span and visual wall family are separate data. No image-alpha collision and no runtime mesh import are needed.

## Walking from A to B

Use one small two-level scene with the staircase layout already represented in the art study. The following aliases denote separate Tile UUIDs; heights are native five-foot steps:

```text
A_lower = (4, 1), height 0, ordinary ground
L       = (3, 1), height 0, stairs, east-west axis
S       = (2, 1), height 1, stairs, east-west axis
U       = (1, 1), height 2, stairs, east-west axis
B_upper = (1, 2), height 2, ordinary finite floor
B_lower = (1, 2), height 0, ordinary ground

Admitted walking route: A_lower -> L -> S -> U -> B_upper
Independent lower support: B_lower (same XY as B_upper)
```

Both height-changing endpoints deliberately satisfy the current progressive stair rule. The upper slab has a real opening over the ascending run; the lower ground under the upper room remains present. `B_lower` and `B_upper` have different occupants and ground conditions. No ordinary vertical walking edge joins them just because their XY matches.

`compute_paths` becomes support-node Dijkstra/BFS with the existing movement costs and surface checks. Candidate adjacent columns are small broad-phase sets; each candidate support pair passes the actual elevation, boundary, occupancy and hazard rules. Diagonal corner checks must examine legal intermediate support transitions, not any walkable Tile found in an XY column. Do not introduce a second baked house navigation graph or use the art preview's assumed-open-door edges.

The Move action continues issuing the actual `StepMovementEvent` sequence. Each step retains source/destination support UUIDs, endpoint XY/elevation at that time, movement/contact mode, admitted costs, source-exit reaction policy and commitment result. Reuse the present pre-step interception, damage/condition interruption and post-arrival handlers. An opportunity attack at S can stop or kill the mover there; no renderer may finish the route to B merely because the original path named B.

Ground/AIR/UNDERGROUND remains contact relative to support. Jumps retain the current launch/air/landing contract, with an unambiguous destination support. Passing above a downstairs trap does not ground-contact it; landing on its actual support can trigger it. This does not add flight, hovering, falling between storeys or underground gameplay. Forced movement, Misty Step, portal relocation and suspension/restoration must commit through the same support-aware owner rather than keep an XY bypass. Their spell/trap rules remain their existing owners.

Discrete connectors remain useful for a selected paid passage or climb. `TraverseConnector` already owns cost, source-exit Step, reaction recheck and commitment. Its `PASSAGE` name does not prove window climbing has a complete action/presentation. Ordinary stairs stay ordinary walking. If selected connector code is touched, replace its existing derived `_connector_digest`/selector integrity token with actual identity and relevant current state/revision checks where necessary; do not make hashes a requirement of the new support contract. No unrelated connector rewrite or fresh signature scheme is proposed.

## Real geometric queries, not new fields alone

There are three different operations:

1. **Walking/reach across a supported transition:** existing movement rules plus selected support endpoints and passability.
2. **Optical/light/straight targeting path:** a physical segment from an authored mechanical source sample to a mechanical destination sample.
3. **Effect footprint/propagation:** the existing effect's shape and propagation rule, evaluated against the actual receiving supports and intervening geometry.

They can share the small slab/panel intersection functions and facts; they must not share an answer simply because one has already computed a walking path. A path up the stairs does not give sight around the stairwell corner. A clear projectile path does not admit a creature through bars.

The concrete seam is `dnd/core/world_edges.py:world_edge_contribution_allows` and its GridMap/world-fact consumers. Today a listed nonmovement channel returns false without considering height. Keep the existing movement interval behavior where appropriate; add the actual segment intersection operation needed by the optical/propagation callers. A boundary crossing computes its distance along the edge and physical ray height, then tests the authored solid panels for that channel. A floor crossing tests the finite slab's footprint and vertical interval. Adjacent full wall, below-sill and through-opening paths must produce different results because of geometry, not a `window=True` exception in the spell.

Implementation uses the existing grid/column broad phase, not scanning every structure in the map for every ray. Existing FOV caches/revisions remain owners; invalidation must include a changed physical contribution's affected region and possible observers across levels. Keying subscriptions only to the changed support would miss observers looking through it from another floor. Preserve the indexed sensory cascade and derive deltas from real changes; do not rebuild every observer/world per frame.

The current AoE fast path in `dnd/core/aoe.py` skips propagation when its geometric XY footprint is disjoint from known barrier positions. In a multilevel query, that candidate set must include relevant slab/panel intersections, or an overhead floor would disappear from legality merely because no XY wall was listed. Preserve a genuinely clear-query fast path; qualify its inputs and caches with the actual source support/height, selected geometry and current relevant revision. The current subjective cache key `(originXY, radius)` cannot distinguish lower and upper casts. These are shared shape/query changes, not one exception per spell.

Live mechanics and passive recorded world consumers use the same dependency-leaf geometric functions. Player previews supply only disclosed facts and retain the current unknown-versus-known rules. Objective target execution still recomputes legality from objective state. Renderer body/hand sockets and cosmetic curved projectile arcs never grant mechanical line of effect.

### Mechanical ray heights need an explicit policy

The current `Entity.size` is not a complete eye/body-height model, and appearance scale is not one. A real sill needs some mechanical height policy. Proposed first scope: a small agreed standing Medium profile for optical and targeted-body samples, with stationary fixtures using their existing physical mount context. Do not add per-animation native keypoints.

The choice between one representative point and a small body-span/cover test affects whether a short/prone target is visible through a window and how much cover it receives. That is a gameplay decision to settle before those queries are implemented, not a reason to derive mechanics from rendered pixels. The initial proof must state its selected profile and what it does **not** certify. Existing special-sense rules remain authoritative; geometric optical closure must not indiscriminately turn every sense into eyesight or invent new tremorsense transmission rules.

Likewise, the existing `support_distance_feet` (`dnd/core/elevation.py:24`) is the maximum of tactical grid distance and rounded vertical distance. Preserve that existing tactical rule for migrated support-aware range checks; do not introduce Euclidean range as an unrelated choice. Identify the affected direct/secondary range sites and preserve each action's current origin ownership, including device origins. Multi-Z is not permission to change all spells' range semantics.

## Usable windows: required proving behavior

The user explicitly requires usable windows. The lodge's delivered C4 is a **fixed barred aperture**; C6 is a doorway arch. The handoff's ten-foot outer wall envelope does not certify sill/header or opening dimensions. Those few physical values must be authored from the selected asset/design once, in native units, rather than guessed independently by every query. Art currently delivered for bars is not evidence of an opening-shutter animation.

The first window narrative places two characters on actual supports on opposite sides. A neighboring full wall blocks the chosen sight/shot. A segment through the open aperture succeeds. A segment below the sill or through the frame fails. Moving to a support on the stairs changes the segment height and can change this result. Light from an actual fixture passes or is blocked by the same aperture for its optical channel. Record the resulting native contacts and actual attacks from both perspectives.

For illustration only, a five-foot boundary could have an opening between 1 and 4 feet along the edge and between 3 and 7 feet above the floor. A height-4-foot ray through the central opening clears it; a height-2-foot ray hits the sill. These are query examples, **not approved dimensions for C4**.

| Variant | Required rule distinction | First-slice status |
| --- | --- | --- |
| Fixed bars in an opening | See/illuminate through the opening; body passage blocked. Projectile/cover treatment is an explicit coarse gameplay choice, not per-bar pixel ballistics. | Delivered asset; candidate for the first real window proof. |
| Open unbarred aperture | Legal optical/shot paths; paid body passage only if it fits and the destination is supported. | Select an actual delivered matching variant or acknowledge missing art. |
| Opaque shutter | Closed state blocks its declared channels; open state changes them and publishes real state/sensory changes. | Do not invent operation art for fixed bars. Implement only a chosen variant. |
| Clear pane | Can transmit sight/light while still blocking body passage and possibly effect propagation; broken state retains its frame. | Requires a selected rule/content/media variant, not inferred from a bright painted window. |

Opening, closing and breaking belong to ordinary item/actions/state handlers. Frame and closure may be one composed item's state or existing related content when independently targetable; avoid a new subclass per style. Destroying a selected closure/bars must leave the intended frame and update actual channels, not delete the entire wall provider merely to obtain a hole. Existing HP/destruction/remnant events are the relevant owners.

A window crossing connects adjacent supported spaces at compatible heights and pays its declared movement/action cost. Reuse existing traversal and reaction owners, with a properly authored body motion if selected. An upstairs window opening onto empty air is not an available landing point. No unsupported fall, rope physics or new flight mode is authorized. Decide whether fixed bars are breakable now and whether their opening admits the intended projectile/cover rule; opening every style is not a prerequisite for the aperture query.

## Targeting, spatial conditions and ground state

The shared target origin carries support geometry from the actor or device that actually emits the action. Target identity resolves the target's current support; targeted ground actions carry an explicit support. Same XY is no longer distance zero between storeys. Reach and melee candidate enumeration must stop merging actors in the column. A closed slab can block an otherwise in-range target; range and line of effect remain separate checks.

Ground-owned effects name receiving support IDs: Tile blood/ash, ground traps, pressure plates and surface Web contacts must not affect every matching XY. Their handlers still bind to real Step/SpatialChange/condition events. Update the existing spatial index in `dnd/spatial/transitions.py` and EventQueue's spatial subscription boundary along with GridMap membership. Updating only `affected_positions` on a condition would leave event dispatch aliased.

For non-ground areas, support membership comes from the shape's selected vertical semantics and propagation. Current `Sphere` is a 2D circle calculation; this is existing scope, not proof that vertical volume already works. We need an explicit first policy for spheres/cones/cylinders and ground-targeted patches before claiming general upstairs spell support. Recommended first proof: one existing area owner, such as Silence, on both levels where the agreed volume and an opening admit it, with a closed slab blocking its chosen propagation. Preserve overlap ownership and actual entry/exit/removal facts. Do not add `if upstairs` paths to individual spell implementations.

Preserve each existing shape owner's propagation behavior. Silence already uses the Sphere route; `Cylinder.compute_objective` deliberately bypasses horizontal wall filtering and already stores a height. The shared slab/panel helpers must not replace these distinct rules with one universal LOS check. New vertical origin/extent and slab-crossing meaning still need explicit reasoning where existing two-dimensional behavior does not settle them.

Migrate and verify representative **shared shape families**, not a per-spell cross-floor allowlist. Keep the minimal multi-Z proof world a development fixture until its admitted action/shape consumers are coherent. Do not expose a supposedly complete house with silent same-floor fallbacks or an infinitely tall interpretation for every field. Existing single-floor outcomes remain regression references.

There are behavioral consumers beyond the area index. The selected Silence
proof must include `SilenceZone._create_spell_block_handler`
(`dnd/spells/illusion.py:1285`): it separately captures `affected_positions` and
tests the caster's XY. Updating Deafened membership alone could still leave an
incorrect verbal-cast cancellation on another floor. Route that existing
handler's spatial membership test through the support-aware owner and test real
verbal casting on included/excluded supports, plus removal. This changes the
meaning of its location reference, not Silence's rules or a per-spell floor flag.

Residue deposition uses the real resolved receiving surface and existing damage/material handler. An upstairs wound stains the upstairs support; it does not color the lower Tile at the same XY. Existing splat endpoint geometry can be extended with support identity without making particle trajectories the backend authority. Falling splashes through a stairwell, ceiling stains and material transport are not required here.

## Observation and complete-lineage records

The current observer rules are preserved. This migration changes **where** a fact refers to, not **who is entitled to know** it.

- Visible/seen supports, light/hazard maps, entity/object contacts, spatial footprints and subscriber candidates distinguish support identities. Entity identification, position knowledge and merely hearing an event remain their existing meanings.
- Step source and destination coordinate grants retain independent before/after witnesses, now at support granularity. `position_evidence_key(XY)` cannot identify both B_lower and B_upper. Update the event-time grant producer and corresponding projector together.
- Event participant/affected-position candidate searches in `dnd/encounter.py:70` and `:94` need support/physical query context. An upper-floor event must neither broadcast to all same-XY lower-floor observers nor lose an observer legitimately looking through the stairwell.
- World/object placement facts record the support and physical slab/panel data actually admitted at that point. Movement retains its historical endpoints; the renderer never asks the latest native map which floor an old Step used.
- Large-object changes invalidate their actual footprint, but observing one end must not disclose hidden adjacent rooms/floors. The public object record needs only the footprint geometry permitted by the current projection contract; objective diagnostics remain local.
- The existing `_object_observed`, `_observed_object` and `_world_update` paths in `game/player_projection.py` all use incident XY today. Upgrade admission, remembered-face refresh and removal filtering together. A hidden upper-floor mutation must not refresh or delete remembered upstairs state merely because its lower same-XY support is visible.
- Existing complete parent/child lineages still reduce and bind before playback. Native event progression and presentation clocks remain independent. There is no extra event bus, floor tick or renderer callback into a live engine.

### Existing saved inputs

Use the existing explicit versioned record boundary. Do not create a universal serializer or re-run the game to make an old clip readable.

Native old single-support histories can resolve many old XY references from their recorded initialization and **preceding** world modifications. Do that in event order, never against final-world geometry: Tile replacement and elevation changes may occur during a history. Required current fields should remain required in new producer records.

Old **public** histories are subtler: a coordinate grant can reveal a movement position without ever disclosing that Tile's complete geometry/UUID. The old public record cannot safely invent a support identity from future/private native facts. Recommended compatibility boundary: keep the old version's single-support addressing readable by a passive legacy adapter, using a received UUID only when that archive actually establishes it. Retain its existing coordinate-only presentation where identity was not supplied. Do not synthesize a hidden storey or silently zero an unknown height.

Before finalizing exact schema changes, inspect representative current saved inputs for this case and choose the smallest adapter that preserves their already-approved output. The design decision is **preserve unavailable information as unavailable**; the exact adapter shape is intentionally not asserted without those archive witnesses. New multilevel public histories supply the proper support identity when the existing disclosure rule permits the location fact, without disclosing all properties of that support. An ID reference and a full world Tile record are different grants.

## Passive reduction, picking and drawing

`dnd/world_facts.py`, `game/player_facts.py` and their reducers retain distinct support entries and observed placements. Presentation consumes those facts. It does not rebuild objective floors from a prefab definition or bootstrap a live Game.

The existing isometric projection already accepts elevation. Supply the actual historical support and retain the rendered body's interrupted position independently of legal grid origin, as in the approved opportunity-attack behavior. The movement timeline continues interpolating the admitted endpoints/trajectory, not selecting a fresh floor halfway through playback.

The compositor must distinguish earth columns from finite slabs. An upper floor occludes the appropriate body portions while leaving a lower room's empty volume intact. Use the new received physical slab facts in the existing terrain/fixture depth ordering; do not make an upstairs texture into a giant opaque downward column. Existing actor/door depth, projectile/area boundaries and below-ground portal masking remain regression cases. One body on its own support must not be clipped by that support's top face.

Concrete consumers are `game/app.py:420–490` (raised terrain currently generates earth bed/cliffs), its `_stair_runs` matcher at lines 157–195 (current EARTH/XY terrain pattern), and own-floor depth treatment around line 589. Preserve existing terrain stairs while consuming explicit support/run geometry for a raised floor. `game/area_media.py` also masks against full boundary intervals and a receiving plane today: feed actual received aperture/slab geometry into that existing projection seam so Fireball/other authored area recipes keep their boundary behavior. Camera-facing sprite alpha can remain a visual occlusion aid; it never becomes native aperture authority. No global “upper floor draws last” rule or replacement scene graph is proposed.

Picking consumes only currently permitted/selected support candidates. Explicit roof/upper-floor cutaway can make already disclosed lower surfaces selectable, but does not grant a private downstairs actor or delete native floor collision. The first proof can use manual selected-level/cutaway controls. Automatic smart house cutaway is not required. Distinct same-XY supports must be selectable unambiguously; a click through an opaque shown slab must not silently select the hidden lower tile.

Camera rotation changes projection and visible geometry, not mechanical location or authorization. Review each recorded subjective history at all four existing cameras. No new screenshot-testing framework is necessary; use the existing capture/replay/gallery and focused ad hoc image comparisons where a shared compositor change risks approved output.

## Bounded implementation order, if approved

These units are a connected implementation sequence. Completing a unit does not justify exposing unfinished multilevel worlds as fully supported gameplay, and normal checkpoints are not requests to make the user restart the work.

| Unit | Owned change | Acceptance before advancing |
| --- | --- | --- |
| A — support contract and saved facts | Direct Tile lookup/column index, explicit placement support, passive world/movement/contact facts and identified legacy compatibility case. Preserve current single-support callers through deliberate admission adapters. | Independent actors/items/conditions on B_lower/B_upper; cold native record and public replay retain their identities without live lookup. Same-XY support commit is not skipped. |
| B — ordinary routes and occupancy | Support paths/diagonals/reach, progressive stairs, object footprint indexing, shared relocation commit and selected contact handlers. | Real A→L→S→U→B movement both ways; blocked doorway; interrupted stair Step; jump landing only on its actual support; no cross-floor ground trigger. |
| C — bounded physical queries and usable aperture | Finite slabs, selected panel geometry, agreed mechanical samples, native optical/light/target consumers and incremental invalidation. | Closed slab separates same-XY actors; clear stairwell ray works; window ray clears opening but fails at sill/frame; bar/body behavior and selected shot rule correct. |
| D — observation/effect integration | Support-aware sensory deltas, subscriptions/event-time grants, target origins/range and selected area membership. Preserve subjectivity and complete lineages. | Both observer histories distinguish private floors; existing overlapping condition owners remain correct; target/range/area tests use actual action execution. |
| E — presentation and review | Passive reducer/picker/finite-floor depth; reuse existing motion, asset identities and four-view extraction. | Small scene saved once, replayed in a fresh process without native world; two subjective perspectives × four cameras; no invented upper/lower geometry. |
| F — chosen furnished layout | Intake actual physical floors, openings, footprint/parent relations, existing door/loot/light/destruction systems from interiors plan. | Real navigation/interaction narrative in the selected building. No flattening of a multilevel layout and no hidden skipped floors. |

The first proving scene needs two Medium actors, two levels, the short staircase, one full wall and one selected window, one fixture, one ground trap/residue and one two-cell object. It is deliberately smaller than a house. Add a third fixture/actor only if a named accepted test needs it; do not create a catalogue of micro-features before this spatial contract works.

## Meaningful acceptance cases

Read `HOW_TO_TEST.md` before implementation/tests. These are proposed cases, not tests run in this study.

1. **Independent same-XY supports:** lower and upper each hold a different actor, light result, item and residue. Removing an item/condition above leaves the lower state unchanged. Query by actor/Tile identity returns the correct support; ambiguous XY admission is not silently resolved.
2. **Ordinary staircase:** paid native A→B walking both directions, actual Step ancestry and costs; closed door changes the route; a source-exit reaction can stop the mover at the accepted step. All four camera recordings preserve the interrupt position.
3. **Ground contact:** walk/jump/Misty Step to selected supports; no trap under an airborne leg or on a different floor; landing/teleporting onto the real trap has the existing trigger result. Test the already-supported mechanics, not a new flight action.
4. **Slab and opening:** standing actors at the same XY are separated by a closed slab. An unobstructed ray through the authored stairwell permits the selected sight/attack. Ray below an upstairs slab remains in the lower room; walking connectivity around stairs is not substituted for optical visibility.
5. **Window:** actual discovered target/attack through opening, blocked neighboring wall/sill/frame, light change on fixture toggle, barred body exclusion, and selected supported crossing/closure only if its variant is approved. Tests use physical query geometry independent of camera and sprite.
6. **Footprint and parent support:** a two-cell upper object blocks both upper supports, not their lower counterparts. Its one destruction releases the authored footprint and resolves an exposed child's selected aftermath in the same lineage. Physical floors and their conditions survive.
7. **Spatial membership:** upper-only ground effect; selected cross-floor area under its agreed volume/propagation; actual entry/exit and overlap removal through current handlers. For Silence, actually cast a verbal spell from included and excluded same-XY supports, then remove the zone and cast again; checking Deafened state alone is insufficient. No all-XY-floor broadcast.
8. **Disclosure:** one observer briefly sees the other through a window/stair opening, loses sight, then sees a changed actor again. Source/destination grants do not alias same-XY floors. Never-observed upper content stays private in the lower observer's saved bytes; hidden upper mutation does not refresh/remove remembered upper content through visibility of the lower support.
9. **Replay/picking:** native recording once, both projected histories, fresh-process load/reduce/render; same-XY support picking and manual cutaway; no native execution during replay and no private geometry supplied by importer. Compare approved single-floor height/door/portal/jump reference cases when shared drawing changes.

Keep runtime measurements proportionate: compare representative movement and sensory query counts/timings against the same small single-floor scene. The column index and segment tests must not cause all-world scans or repeated serialization. This is a focused regression check, not a new profiling/hash/audit project or an invented millisecond threshold.

## Discussion choices and bounded recommendations

1. **Order:** small two-level/window native proof before a complete furnished house, or one-floor furnished play first with its required aperture work? Recommendation now favors the small shared geometry proof if simultaneous storeys are the immediate objective. No answer has been assumed.
2. **Window interaction rules:** fixed bars' shot/cover treatment; whether an unbarred supported crossing and a breakable/openable closure belong to the first unit. Using windows for sight/attacks is already required. Delivered fixed bars must not be portrayed as an operable shutter.
3. **Mechanical height/cover sampling:** recommend a stated standing-Medium mechanical sample profile for the first proof. Reason about body-span/cover and short/prone targets before broadening that claim; keep it independent from appearance sockets and preserve existing special senses. This is a bounded design recommendation, not a demand for the user to choose implementation constants.
4. **Vertical area meaning:** preserve existing tactical range and shape-owner propagation rules. Work out only genuinely new vertical origin/extent and slab-crossing semantics, using representative shared shapes. Do not reopen existing rules or invent per-spell floor switches.
5. **Supported child aftermath / structural boundary:** use the interiors plan's proposed tableware-to-floor broken aftermath as the concrete example for discussion. Do not require another permission checkpoint for every content row. Floors remain indestructible here; unsupported falling and collapse stay outside this unit.

Schema names, lookup storage choice, art paths and ordinary implementation details do not require separate user approvals. These are discussion points for the requested dedicated design task, not five mandatory approval gates. Explain recommendations and ask only where a genuinely unsettled gameplay meaning matters.

## Review record

- **Native/ECS design author:** `/root/backend_ecs_review`, grounded in current owner/code inspection. This authorship is not independent approval of its own proposal.
- **Independent anti-slop reviewer:** `/root/presentation_antislop_review`, approved the architecture with bounded amendments. Existing tactical range and each shared area's propagation owner must survive; preserve Cylinder's distinct horizontal-wall behavior. Avoid per-spell floor exceptions and unnecessary approval gates. These amendments are incorporated above.
- **Independent anti-OOP/ECS reviewer:** `/root/spell_orientation_antislop`, approved the design proposal with two amendments. Sparse XYZ indexing is distinct from voxel occupancy and compatible with UUID identity; Silence's independent verbal-casting handler needs actual behavior tests, not only membership assertions. Both amendments are incorporated above.
- **Root integration review:** retains stable support identity as a recommendation, not a decision made by the user. Source geometry, indexes and durable identities are separate questions. The user will discuss alternatives in a dedicated task; backend semantics are the priority.
- **Limits of review:** no approval here settles new vertical AoE semantics, exact mechanical height sampling or legacy-public adapter shape without the stated evidence. No production code, generated assets or tests were added. No flight/falling framework, source-hash audit, event bus or general serializer is proposed.
