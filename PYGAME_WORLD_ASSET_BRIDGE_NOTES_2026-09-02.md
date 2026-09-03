# Pygame world and asset bridge notes

Status: **working study notes; not an implementation plan**

These notes record the current agreement for the first pygame-ce battlefield
renderer. They intentionally preserve the existing ECS-adapted D&D runtime and
do not introduce a parallel world model.

## Immediate objective

The first visual milestone is deliberately narrow:

1. Load one already-authored engine battlefield.
2. Render its 2.5D isometric terrain, boundaries, and a small object subset
   using real MapEditor assets.
3. Preserve exact engine `(x, y)` coordinates and support elevation while
   applying height only as a client-side projection offset.
4. Provide strong mouse-to-grid diagnostics, including the selected support
   height.
5. Defer full layered actor animation and spell VFX until the map projection,
   ordering, and picking are trustworthy.

That deferral is ordered scope, not cancellation. After the map seam is
trustworthy, the next renderer phase must recover NeuroClient's complete
entity-sprite system: semantic engine-to-rig bindings, body/equipment layers,
direction and clip selection, shared animation timing, shadows, visual status
overlays, and movement/attack/reaction/death transitions. The following phase
then recovers action and spell VFX on the same event/presentation seam. P0 must
leave exact asset identities, anchors, async terminals, and diagnostics ready
for both phases.

## Authoritative source repositories

Primary sources are the live WSL repositories, not the deprecated Windows-side
copies:

- `/home/tommaso/Dev/NeuroMapEditor`
- `/home/tommaso/Dev/MapEditor`
- `/home/tommaso/Dev/NeuroClient`

`NeuroMapEditor` contains the clean XYZ/lattice/projection, visual-tilemap,
ordering, transformed-sprite, and alpha-picking contracts. `MapEditor` retains
the older authoring workflow and asset evidence. `NeuroClient` retains the
actor layering and animation implementation.

## MapEditor code that is relevant

The runtime needs only the authored-map presentation contracts:

- `macro128`: 128 x 64 pixel isometric cell footprint.
- Optional `fine64`: four 64 x 32 child cells per macro cell.
- Explicit `(x, y, zGridId)` placement.
- Explicit pixel projection offset per Z-grid.
- Sprite asset identity, pivot, scale, affine/occurrence offset, tint, alpha,
  orientation, and visual layer.
- Explicit planar/spatial painter ordering.
- Inverse projection for cell picking.
- Transformed bounds plus alpha-mask narrow-phase picking for sprites.

The runtime must **not** port reconstruction machinery used to infer a map from
Unity or images:

- causal-height inference;
- automatic enclosure repair;
- filename-driven cliff or stair deduction;
- image-to-map analysis;
- Unity evidence compilation;
- automatic plateau or boundary completion.

The game receives an authored map. It renders facts; it does not reconstruct
them.

## Geometry and height

The engine remains spatially two-dimensional. A position is `(x, y)` and the
support `Tile` owns an integer elevation in five-foot steps. Rendering maps an
engine support height to an authored Z-grid projection offset. It must not
rewrite engine positions into pixel or pseudo-3D coordinates.

The current MapEditor macro projection is based on quarter-macro contacts:

```text
qx = 4x
qy = 4y
screen_x = (qx - qy) * 16 + z_grid_offset_x
screen_y = (qx + qy) * 8  + z_grid_offset_y
```

At macro scale this is the usual 128 x 64 isometric projection. The first
renderer may use one macro asset per engine cell. Later work may explicitly map
one macro asset to four fine cells; this must not be smuggled into the first
implementation.

Mouse picking must use the explicit projection context for candidate Z-grids,
then select the visually foremost valid authored contact. The debug view should
show engine `(x, y)`, support height in steps and feet, Z-grid identity/offset,
screen contact, candidate contacts, and the final selected cell.

### Authored structural hints versus MapEditor inference

The game renderer should first consume structural facts already authored by the
engine instead of porting MapEditor's attempts to reconstruct those facts from
Unity or pixels:

| Positioning question | Existing engine fact |
|---|---|
| Which support owns a visual? | Tile UUID and exact `(x, y)` |
| At what gameplay height is it supported? | `Tile.height` / `WorldTileState.elevation_steps` in five-foot steps |
| Is the support ordinary, stairs, or a ramp? | `ElevationSurfaceKind` |
| Along which cardinal axis does it progress? | `SlopeAxis` |
| On which side of a Tile is a wall or door owned? | `WorldObjectPlacement.boundary_direction` |
| Which way does an independently oriented object face? | `WorldObjectPlacement.orientation` |
| What vertical interval does an object occupy? | `base_height_steps` and `top_height_steps` |
| Which supports and elevations does a special vertical route join? | Traversal connector endpoints and endpoint elevations |
| Which semantic connector presentation is requested? | Traversal connector `presentation_key` |

For ordinary placed objects, GridMap defaults the base height to the support
Tile height. Walls and doors therefore already carry their support side,
orientation, base, and vertical extent. The renderer should map those authored
steps to Z-grid pixel offsets and use catalog pivots/contact points; pixels and
asset-specific lift values do not belong in the engine.

For progressive elevation, the current facts name an axis rather than a
cardinal uphill direction. The first hypothesis is that uphill direction is a
deterministic reduction of neighboring authored support heights along that
axis. This is acceptable world-state reduction, unlike guessing height from an
image. The elevated slice must prove that the reduction is unambiguous for its
selected assets before any new authored hint is proposed.

Known deliberate limit: the engine has one support Tile per `(x, y)` and models
tactical space as 2D plus support height. It does not describe independently
walkable stacked floors at the same XY coordinate. The pygame milestone should
not reintroduce a general 3D world to match art that exceeds that model.

## Existing engine world objects

The engine already has the runtime objects and most required mechanics.

| Existing object | Current authority |
|---|---|
| `Tile(BaseBlock)` | Terrain surface, movement costs, center optics and propagation, light, support elevation, stairs/ramp kind, and slope axis |
| `DirectionalWall(BaseItem)` | Reusable boundary-wall mechanics and item lifecycle |
| `DirectionalDoor(UsableItem)` | Boundary mechanics plus open/close behavior and use actions |
| Other `BaseItem` / `UsableItem` instances | Chests, torches, barrels, levers, devices, loot, and other world objects |
| `WorldObjectPlacement` | GridMap-owned tile position, boundary side, independent orientation, base height, and top height |
| `BoundaryStructure` | Cold current contribution returned by a boundary provider; it is not the owning wall object |
| `ItemPresentationState` | Cold item state emitted for initialization, events, and replay |
| `WorldTileState` / `WorldObjectState` | Renderer-neutral initial-world facts |

Walls are currently world items, not new entity aggregates. Their concrete
instances already reuse:

- independent directional side placement on either incident tile;
- vertical occupancy bands;
- movement, optical, and propagation channels;
- targetability and optional health;
- damage and destruction lifecycle;
- item conditions and event handlers;
- stable `item_id`, name, description, and state;
- placement/removal/change events;
- cache invalidation, light recomputation, and observer sensory updates.

`BaseItem` already supports generic destructibility through `is_targetable`, an
optional `Health` block, damage events, zero-HP destruction, GridMap removal,
and an `_on_destroy` specialization hook. The oil barrel is an existing example
of special destruction behavior. A destructible wall does not require a new
destruction system.

## Instance-first content law

Configured instances of the current classes are sufficient for most geometry
and world building:

- different Tile materials, descriptions, elevations, movement costs, and
  light values are ordinary `Tile` instance data;
- different wall descriptions, channels, targetability, durability, and
  placement are ordinary `DirectionalWall` instance data;
- doors reuse `DirectionalDoor` and its existing state transition;
- environmental overlays and hazards reuse existing spatial conditions.

Subclassing remains useful when it makes recurring authored content clearer or
provides genuinely distinct behavior. It should remain shallow and
domain-polymorphic. A concrete wall or Tile subtype may provide reviewed
defaults or specialized lifecycle behavior; it must not introduce managers,
controllers, generic interpreters, or a second spatial system.

The decision rule is:

```text
authored variation                       -> configured instance
repeated semantic content/defaults       -> optional concrete content subtype
genuinely distinct mechanics/lifecycle   -> concrete subtype at the existing Tile/world-item level
placement and occupancy                  -> GridMap
cold event/replay projection             -> existing event value models
concrete PNG selection                   -> client-side data
```

No speculative taxonomy should be added before a real authored battlefield or
asset binding proves that the current instance data cannot distinguish two
required semantic choices.

## Runtime world-change cascade

There is currently no world-level `WorldModifiedEvent`. Runtime changes use
precise existing facts:

- spatial entity entered/left;
- spatial Tile changed and `TileElevationChangeEvent`;
- spatial object placed/removed/changed;
- spatial light changed;
- spatial perceivability changed;
- `SpatialEffectChangeEvent`;
- `TraversalConnectorChangeEvent`.

GridMap mutations invalidate the relevant spatial revisions and caches. Optical
changes settle light before spatial completion. `SpatialSensesSystem` reduces
the indexed affected observers at the existing pre-completion system boundary
and emits observer-specific `SensoryUpdateEvent` deltas before the causal event
completes. Committed movement steps therefore update perception dynamically.

One known bridge gap is that initial `WorldTileState` includes the complete
`TileSurface`, while runtime Tile-change payloads currently focus on mechanics
(costs, optics, propagation, light, and elevation). A future runtime mutation
of graphic-agnostic surface identity would need to publish that semantic
after-value through the existing typed Tile mutation path. This does not justify
a generic world-modified event.

### Interactive world authoring and a semantic world-modification root

The previous sentence rejects an untyped catch-all notification, not the
semantic concept of a world modification. A carefully bounded
`WorldModifiedEvent` would be useful for live GM editing, an in-process map
editor, and an LLM authoring a battlefield through a sequence of inspectable
operations.

It should sit above the existing mutation facts rather than replace them:

```text
WorldModifiedEvent declaration: one requested authoring gesture
  -> existing Tile/object/connector mutation lifecycle
    -> existing cache and revision invalidation
    -> existing light/propagation settlement
    -> existing observer-specific SensoryUpdateEvent children
  -> WorldModifiedEvent completion with exact committed before/after values
```

The spatial and mechanics events remain the only causes of rules
recomputation. The world-level event provides causal grouping, detached
materialization values, authoring history, and one semantic success/cancel
boundary. Consuming its completion must never trigger the same sensory or light
cascade again.

The event should reuse the renderer-neutral state values already owned by the
engine:

- `WorldTileState` for an added, replaced, or removed support;
- `WorldObjectState` and `ItemPresentationState` for placed, moved, changed, or
  removed world items;
- `WorldConnectorState` for connector registration, replacement, enablement,
  or removal; and
- explicit before/after absence for creation and deletion rather than sentinel
  dictionaries or stringly typed payloads.

An editor history can therefore be represented narrowly as one
`WorldInitializedEvent` snapshot followed by ordered, completed
`WorldModifiedEvent` values. This is not authority to archive or clone every
engine Event. The persistent authoring log contains only these passive world
values; the ordinary objective queue remains the detailed causal/debug rail.

The first implementation should make one world modification exactly one
already-atomic domain mutation. Multi-edit transactions, rollback managers,
undo stacks, branches, collaboration, and network persistence are separate
future needs. A larger authoring gesture may be admitted only after its entire
batch can be prevalidated and committed atomically; it must not claim one
successful terminal after a partial edit.

Current runtime support is mechanically close but not yet complete enough for
this authoring log:

- `GridMap.set_tile()` publishes movement/optics/propagation/light facts but
  omits complete Tile UUID, surface, name, elevation kind, and slope state; a
  surface-only edit may currently publish no spatial event at all.
- `GridMap.place_object()` and `move_object()` publish exact placement and
  blocking geometry, while complete `ItemPresentationState` is guaranteed only
  by explicit item-location publication paths. The world-level terminal must
  contain the complete object after-value for every authoring entry point.
- connector mutation already has typed old/new mechanics, but the authoring
  terminal should expose the corresponding cold `WorldConnectorState` values.
- Tile replacement/removal must reject live references from placed world
  objects and connectors in addition to its current Entity/spatial-condition
  protections, unless a future explicitly atomic coordinated edit owns those
  removals. Silent dangling support UUIDs are unacceptable.
- the Tile mutation entry points need causal parent lineage so their detailed
  events can remain children of the world modification root.

These are bounded completeness and referential-integrity repairs. They do not
require an editor controller, generic command interpreter, mutable world DTO,
event-sourcing framework, or second spatial system.

## Engine-to-asset boundary

The engine owns world meaning and mechanics. It must remain usable by a text
client or narrator without any asset library.

For the first renderer, existing facts should be tried before adding data:

### Tiles

- `Tile.name`
- `Tile.surface.base_material`
- ordered `Tile.surface.layers`
- `Tile.surface.description`
- movement-mode costs
- support elevation
- ordinary/stairs/ramp surface kind
- slope axis
- light and optical/propagation state

### World items and boundaries

- stable `item_id`
- name and description
- exact item class/behavior family in the engine
- current `BoundaryStructureKind`, material, and blocked channels
- targetability, health, open/lit state, and other existing item state
- GridMap placement side, orientation, and vertical extent

The current `DirectionalWall.get_boundary_structure()` hardcodes stone and the
current `DirectionalDoor.get_boundary_structure()` hardcodes wood. If the asset
audit and first battlefield require authored material distinctions, the owner
must be the existing concrete item instance or content subtype; the cold
`BoundaryStructure` should merely project that current state.

## Client-side data

Concrete files, pivots, visual layers, orientations, and variant selection are
client concerns. The intended reusable data is plain JSON consumable by both
pygame/Python and a later TypeScript client.

The study currently anticipates two distinct records, subject to the external
asset audit:

1. An asset catalog containing concrete file and presentation metadata.
2. Semantic bindings from existing engine facts—preferably stable content IDs
   and existing Tile surface facts—to asset families.

For explicitly decorated MapEditor maps, a client-only presentation companion
may record exact authored asset occurrences. The engine loads the semantic
battlefield; clients load the optional presentation companion and asset data.
An exact authored occurrence should take priority over generic semantic
materialization. Missing mappings must produce a visible debug marker and log,
not silent omission.

The new bridge must not expand the legacy direct-asset leakage represented by
fields such as `Tile.sprite_name`. Concrete asset filenames stay outside the
gameplay model.

## External asset audit

The image-heavy audit is intentionally running in a separate Codex task so the
main implementation context does not accumulate thousands of asset images. It
was instructed to:

- start from existing MapEditor/NeuroMapEditor JSON categorization;
- inspect representative art to validate categories;
- select a minimal ground/wall/door/water/prop subset;
- record exact paths, orientations, native dimensions, pivots, and layers;
- distinguish engine semantic facts from client selectors and concrete files;
- avoid causal-height, enclosure-repair, Unity reconstruction, and image-to-map
  inference;
- recommend a small JSON structure reusable by pygame and TypeScript.

The audit output must be reconciled with the existing runtime objects above.
It does not have authority to invent new engine schemas.

## First authored maps as capability maps

The first maps should be redesigned deliberately around the asset library
rather than treating the art as interchangeable decoration. They should still
be valid graphic-agnostic engine battlefields, but each map should be a small
authored capability case that makes a coherent subset of the available art and
runtime mechanics observable.

The initial implementation slice is intentionally much smaller than the full
capability-map set. Its entire required visual vocabulary is:

- one ordinary ground Tile family;
- one coherent wall family;
- the corresponding door presentation;
- one water Tile family; and
- one freestanding light-bearing visual family, provisionally cataloged as
  `standing_torch`.

The first map is flat. It should use only enough occurrences to prove
isometric placement, boundary ownership, the door's layered/composite
presentation where required, water ordering, and ordinary mouse-to-XY picking.
It does not need multiple Z-grids.

The immediately following slice reuses this same tiny visual vocabulary and
adds support elevations, per-Z-grid projection offsets, ordering across those
grids, and mouse diagnostics that resolve both `(x, y)` and support height.
Keeping the assets constant isolates height/projection bugs from asset-binding
and composition bugs.

Additional materials, props, windows, outdoor dressing, and broad catalog
coverage are not part of either initial slice. Missing families remain visible
follow-up candidates, not reasons to generalize the initial bridge.

### Objective facts, subjective reduction, and the async renderer

The July reconstruction deliberately retained one event algebra rather than
creating parallel objective and subjective Event class hierarchies. Current
subjectivity is expressed at three existing seams:

1. The ordinary concrete Events remain the authoritative objective causal
   stream. The privileged debug rail and missing-visual inventory may inspect
   that stream directly.
2. `SpatialSensesSystem` reduces committed spatial, light, condition, life,
   perceivability, and turn-start causes before their completion. It emits one
   observer-owned `SensoryUpdateEvent` containing complete subjective
   after-value deltas for visible/seen cells, effective light, perceived
   entity/object contacts, sense modes, passive perception, visual access, and
   path dirtiness. `Senses.apply_sensory_update()` can replay those values
   without reading the later live world.
3. Subjective combat-log projection accepts and returns the same
   `CombatLogEntry` model. An entirely hidden tree becomes `None`; a visible
   tree is recursively sanitized using event-time evidence. It does not query
   later live perception and it does not introduce a second log ontology.

The AI additionally materializes a retained `SubjectiveWorldState` from the
controlled observers' `Senses` values for decision epochs. That is a current
knowledge-state projection, not a generic censored clone of every Event.

Consequently the pygame client should not invent a `SubjectiveEvent` wrapper
or field-mask language. Its first player view can be reconstructed from the
cold world and Entity facts, the two controlled observers' independent sensory
deltas, and same-model subjective combat logs. The objective queue remains
available beside it for an omniscient diagnostic view and to report concrete
Event kinds for which no visual representation exists yet.

The renderer is asynchronous with respect to mechanics. Synchronous engine
dispatch and its causal child Events must finish without waiting for sprite
timing. A narrow in-process bridge then copies only committed renderer-safe
facts into ordered queues:

- the enemy/AI loop may resolve a complete turn while pygame consumes the
  resulting presentation work at human speed;
- presentation must preserve objective order and causal lineage even when it
  lags behind the live engine;
- the player-command side waits at an explicit presentation boundary before
  accepting the next player-authored action, reproducing the interaction
  rhythm of the later server/client system without blocking enemy mechanics;
- no pygame callback, animation completion, or queue acknowledgement may
  mutate mechanics or complete an engine Event; and
- every committed objective Event remains visible to the coverage diagnostic,
  even when its initial representation is only text or an `UNREPRESENTED`
  badge.

The exact detachment payload is intentionally decided against the first real
consumer, event family by event family. The queue is an asynchronous ownership
boundary, not a reason to duplicate the event type system or serialize live
components blindly.

### First light correctness case

The selected body/flame art depicts a freestanding torch rather than a
wall-mounted torch. Catalog it honestly as the client-side semantic role
`standing_torch`; do not force it onto the current `WallTorch` merely because
that is the first nearby engine mechanic.

The immediate workflow remains asset-first. Continue classifying coherent
visual families, then bind an existing backend object only when its authored
meaning and placement genuinely match. If no exact counterpart exists, leave
the visual family explicitly unbound and revisit it after the initial catalog
is useful. No production rename or new backend class is authorized by these
study notes.

The current engine still proves that the eventual light bridge can remain
small: `WallTorch` already owns `is_lit`, its three light radii, exposed-flame
semantics, light/extinguish actions, attached light-source identity, and
complete `ItemPresentationState` after-values. The current campfire builder
owns rest/cook actions only and must not be treated as a light source without
real mechanics.

Authored battlefield construction already provides the desired chronology:

```text
WorldInitializedEvent
  contains placed light-bearing item with is_lit = false
    -> ExposedFlameEvent ignition through that item's ordinary lifecycle
      -> objective batched SPATIAL_LIGHT_CHANGED after-values
        -> observer-specific SensoryUpdateEvent effective-light/FOV deltas
      -> complete floor ItemLocationStateEvent with is_lit = true
```

This lets the first pygame scene test five distinct responsibilities without a
new mechanic: cold object materialization, visible lit/unlit asset state,
objective illumination, observer-subjective light/visibility, and asynchronous
animation/log ordering once an exact backend counterpart is chosen. The asset
side is already concrete: retain the selected body, its 16-frame flame, and
the frame-zero-first minimal animation policy.

Door state follows the same owner/event principle. One `DirectionalDoor`
owns `is_open`; its open/close actions update the GridMap boundary and publish
`SPATIAL_OBJECT_CHANGED` with the new open state. The client keeps the doorway
frame and selects the open or closed leaf for that same object UUID.

### Evidence-backed flat starter subset

The external catalog/occurrence audit narrowed the first flat map to this exact
coherent subset:

| Role | Asset | Catalog presentation |
|---|---|---|
| Ordinary dirt ground | `fantasy.ground.a1.e` / `environment/ground-a1-e.png` | 256 x 256; pivot `(128, 207.36)`; scale `128/127` |
| Dressed-stone straight wall family | `fantasy.wall.d2.{e,n,s,w}` / `environment/wall-d2-{pose}.png` | 256 x 256; pivot `(128, 207.36)`; scale `128/127` |
| East-boundary stone doorway frame | `fantasy.wall.d6.s` / `environment/wall-d6-s.png` | 256 x 256; pivot `(128, 207.36)`; scale `128/127` |
| Closed wooden door leaf | `fantasy.door.a1.s` / `environment/door-a1-s.png` | 256 x 256; pivot `(128, 209.92)`; scale `128/127` |
| Open wooden door leaf | `fantasy.door.a2.s` / `environment/door-a2-s.png` | 256 x 256; pivot `(128, 209.92)`; scale `128/127` |
| Water mask | `unity.6ccb6893c0aa9974091d5318779c1e76` / `unity-reference/sprites/6ccb6893c0aa9974091d5318779c1e76.png` | 256 x 256 diamond; pivot `(128, 207.36)`; scale `1`; material tinted |
| Standing-torch body | `unity.fa27919a4e81577468f97c3b668cffa2` / `unity-reference/sprites/fa27919a4e81577468f97c3b668cffa2.png` | 256 x 256; pivot `(128, 209.92)`; scale `128/127`; orientation-neutral |
| Standing-torch flame | `unity.f52dea0b72342b246a1216e289dc5168` / `unity-reference/sprites/f52dea0b72342b246a1216e289dc5168.png` | 256 x 256; pivot `(128, 209.92)`; scale `128/127`; 16 frames at 10 fps |

`Ground A1 E` is a high-evidence ordinary dirt choice with 22,421 active
authored occurrences. Its other poses are optional visual variation, not
different gameplay terrain. The selected water mask has 4,508 active
water-role occurrences. Its historical source name is `Shadow2_N`; clients
must expose it through a meaningful water-style ID rather than leaking that
misleading source label into authored game semantics.

The water mask is a binary gray diamond (4,096 opaque pixels; the rest
transparent), not a painted ground tile. Across all active water occurrences,
1,958 have no ground occurrence at the same position; overlapping ground in
the other cases is authored shoreline/coverage composition, not a required
earth substrate. The first map should therefore author a `WATER` base-material
Tile and render the water style alone, rather than falsely encoding it as
`EARTH + WATER` or always drawing `Ground A1` underneath.

The evidence-backed simplified pygame fallback is ordinary tint plus alpha:

```text
asset: unity.6ccb6893c0aa9974091d5318779c1e76
tint:  #126797
alpha: 0.812
role:  water
```

Source ordering places Water above the basement/background and below Foam and
Ground/shoreline occurrences. The source-faithful water additionally uses an
animated world-space shader and `One / OneMinusSrcAlpha` blending; neither is
required for the deliberately static first slice.

Fantasy-pack pose suffixes are artist-space poses, not engine cardinal
directions. The observed pack conversion is:

```text
engine north -> asset w
engine east  -> asset s
engine south -> asset e
engine west  -> asset n
```

### Four-corner camera rotation

Quarter-turn camera rotation should be supported by the client projection from
the beginning. It does not change engine `(x, y)`, boundary ownership,
orientation, movement, perception, or event facts. The client rotates the
logical grid around a camera pivot before projection and selects a different
authored pose; it never rotates a raster image.

For clockwise quarter turns in the grid convention where `x` points right and
`y` points south:

```text
R0   (x', y') = ( x,  y)
R90  (x', y') = (-y,  x)
R180 (x', y') = (-x, -y)
R270 (x', y') = ( y, -x)
```

Applying the established pack conversion after that client rotation gives:

| Engine direction | 0 degrees | 90 degrees | 180 degrees | 270 degrees |
|---|---:|---:|---:|---:|
| north | `w` | `s` | `e` | `n` |
| east | `s` | `e` | `n` | `w` |
| south | `e` | `n` | `w` | `s` |
| west | `n` | `w` | `s` | `e` |

The D2 straight walls and D6 doorway frames have all four exact source poses
with the same pivot and scale. The A1/A2 door leaves are not source-complete:
A1 has exact E/N/S evidence but no W; A2 has exact E/S evidence but no N/W.
The four-view projection is still correct, but an unsupported door view must
remain a visible missing-asset diagnostic until the extra catalog PNGs are
visually reviewed. It must not silently mirror or rotate a known leaf.

Map-centered rotation is:

```text
p' = R(cameraQuarterTurn, p - cameraPivot) + cameraPivot + cameraTranslation
```

Then project `p'` with the existing macro128 formula. Elevation remains a
vertical screen lift applied after horizontal grid rotation. Painter ordering
uses the transformed projected support contact, including its Z-grid/elevation
offset, followed by the draw-role band and authored tie-break. Door frame then
leaf, object body then flame, and water/ground/boundary role ordering therefore
remain stable at every view.

Mouse picking performs the inverse operations for every candidate support
height: remove camera/Z offsets, invert the isometric projection, then apply
the inverse quarter-turn to recover authoritative engine `(x, y)`. Sprite
narrow-phase picking uses the selected pose's own alpha mask; local pivots are
not rotated.

The selected standing-torch body/flame pair is orientation-neutral, so it avoids
the source's separate E/W-only torch supports and remains valid under all four
camera views. The body is always present. `is_lit=true` adds the flame; the
first implementation may hold frame zero while retaining the source's 16-frame
10-fps sequence for the immediate animation follow-up. Both layers use
ordinary source alpha. The flame follows the body in painter order; engine
light radii and effective illumination are never inferred from its pixels.

The first door is therefore deliberately placed on an engine east boundary and
uses the `.s` frame and leaf. The source evidence represents it with two visual
occurrences at the same boundary contact:

```text
Wall D6 S + Door A1 S  -> closed
Wall D6 S + Door A2 S  -> open
```

Both occurrences reference the same `DirectionalDoor` UUID. The frame remains;
the leaf selects its state asset and draws after the frame. They keep their own
pivots. This is one gameplay object with two client visuals, not a composite
engine object. A tiny historical `+0.128 px` leaf offset appears to be a source
layer tie-break and should be omitted unless the new rendering visibly proves
it necessary.

This starter set produced no missing structural fact:

- dirt and the water mask need no direction;
- wall and door contact/facing come from explicit boundary placement and the
  pack conversion above;
- wall/door base and top heights already match their authored vertical bands;
- elevated copies need only Tile support elevation and the client projection's
  calibrated pixel lift.

For a later ramp asset, `slope_axis` plus neighboring authored support heights
should determine uphill cardinal direction. An ambiguous or level neighborhood
must be an authoring diagnostic rather than a reason to infer topology from the
image.

After that vertical slice is trustworthy, prefer several small maps over one
overloaded showcase. Candidate later roles are:

1. **Ground and picking map** — contrasting floor/ground families, map edges,
   ramps or stairs, several support elevations, occluded cells, and exhaustive
   mouse-to-grid/Z-grid diagnostics.
2. **Interior boundary map** — adjacent walls owned by either incident tile,
   corners, doors, windows or openings where supported by current mechanics,
   wall visibility versus the obscured tile beyond, and destructible objects.
3. **Outdoor encounter map** — irregular terrain, water or difficult ground,
   vegetation/rocks/props, elevation transitions, lighting, and sight lines.
4. **Runtime-change map** — doors opening, an object being destroyed or moved,
   light and sensory recomputation, and visible fallback badges/logs for every
   event that lacks a richer representation.

These are not asset test sheets. Each should remain a plausible compact D&D
encounter space suitable for the later scripted two-player-character demo.
Together they should expose enough variation to validate projection, painter
ordering, semantic asset binding, exact authored occurrence overrides, runtime
world deltas, and missing-visual diagnostics.

The external asset audit should therefore report useful *combinations* of
families as well as isolated files: which ground, boundary, opening, prop, and
height assets form a visually coherent scene; which require family-specific
pivots or ordering; and which visual distinctions would demand engine facts
that do not currently exist. The maps may be shaped to exploit the current art,
but engine semantics must not be distorted merely to encode filenames or
artist-specific variant names.

## Next decision after the audit

Compare the proposed asset subsets against these first authored capability
maps and, where useful, one current authored battlefield.
For every requested visual distinction, ask in order:

1. Can an existing Tile/world-item instance already express it?
2. Is a reviewed builder default sufficient?
3. Would a shallow concrete Tile/world-item subtype make repeated content
   clearer?
4. Only if mechanics are genuinely absent: what is the smallest first-principles
   addition at the current Tile/world-item system level?

Only after that comparison should a reviewed implementation plan be written.
