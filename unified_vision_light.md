# Unified Vision, Light, and Subjective Observation

Status: design study and migration plan; no implementation is authorized by this document.

Date: 2026-08-22

## 1. Purpose

This document defines a clean destination for vision and lighting before the
larger Tile, WorldItem, and GridMap migration begins.

The central question is not whether light and vision are identical. They are
not. The useful unification is narrower:

1. ordinary sight and ordinary light use the same physical optical topology;
2. objective illumination remains world state;
3. fog, magical darkness, invisibility, darkvision, truesight, blindsight, and
   similar rules are resolved for one observer after the objective world state
   is known;
4. one observer authority produces both live `Senses` state and the observer
   evidence attached to events and combat logs;
5. the event stream remains the replay boundary.

The model stays two-dimensional. Tile elevation and vertical placement bands
remain important for movement, placement, and rendering, but this migration
does not introduce three-dimensional rays, eye heights, or volumetric light.
“Optical” in this document means gameplay transmission across the XY map. It
does not imply reflection, bounce lighting, physically based rendering, or a
continuous optics simulation.

## 2. Executive decision

The destination has three distinct layers of fact:

| Layer | Authoritative owner | Meaning |
|---|---|---|
| Physical optical topology | `GridMap`, Tiles, placed boundary/world objects | Whether an ordinary optical ray can cross a cell or boundary |
| Objective illumination | Tile-owned, source-keyed light contributions managed through `GridMap` | How much ordinary light is present at a cell before considering an observer |
| Subjective observation | One indexed observer projection authority using Entity `Senses` | What one observer can see, perceive, locate, and identify |

The word **visible** must be reserved for the result of the third layer. A Tile
or wall does not own an observer-independent `visible` result. It owns optical
properties. A cell becoming illuminated also does not automatically make its
contents visible: an observer still needs optical access and the relevant
perception capability.

The target relation is:

```text
observer-visible surface/cell
    = observer has visual access
    + an observer-valid optical route exists
    + the observer can interpret the destination illumination

observer-perceived entity/object
    = observer-visible destination OR a valid nonvisual sense reaches it
    + the subject is perceivable to that sense
```

This is a composition of existing domain facts. It is not another content
registry, renderer contract, state store, or generic rules framework.

## 3. Vocabulary

### 3.1 Optical topology

Optical topology is the physical answer to questions such as:

- can a ray cross this wall edge;
- can a ray cross this closed door;
- does an opaque world object stop the ray;
- does a heavily obscuring spatial condition stop or qualify the ray;
- is the opaque boundary itself the terminal surface reached by the ray.

For ordinary authored structures, the answer is shared by sight and light.
There should not be separately authored “vision wall” and “light wall” facts
for the same stone wall.

### 3.2 Illumination

Illumination is the objective light level at a Tile after combining:

- the Tile's base light;
- light-source contributions;
- source-owned light caps or suppressions such as magical darkness.

Illumination is not observer visibility. It is an input to observer vision.

### 3.3 Optical obscurement

Optical obscurement is a spatial rule that changes sight through an area.
Fog, smoke, magical darkness, and total visual concealment belong here.

This must not be represented only by lowering `LightLevel`. Low light and fog
are different rules:

- darkvision helps with low illumination;
- darkvision does not see through heavy fog;
- Devil's Sight helps with magical darkness, not fog;
- truesight handles darkness and invisibility within range, but does not imply
  sight through a stone wall or every cloud.

A single spatial condition may contribute both objective illumination state
and observer-relative optical obscurement. The existing spatial-condition
owner remains the source of both contributions.

### 3.4 Subjective observation

Subjective observation is the reduction of objective world facts for one
observer. Its durable outputs are already recognizable in `Senses`:

- visible cells/surfaces;
- explored cells;
- perceived entity contacts;
- perceived world-object contacts;
- effective light values for visible cells;
- the sense mode by which a contact is known;

`Senses` currently also contains subjective navigation caches: walkability,
paths, costs, safe paths, and collision memory. Those caches are consumed by
movement and action discovery, but they are not part of the visual/light replay
projection defined here. Section 8.6 gives their exact boundary.

The visual part and the nonvisual-contact part must remain distinguishable.
Blindsight or tremorsense can reveal a contact without pretending that the
Tile is brightly lit or visually rendered.

### 3.5 Event-time observer evidence

An event may be perceivable even if the final state after that event no longer
contains the actor at its old location. Event-time evidence therefore means
the observer grants frozen onto the event lineage:

- which observers perceived the occurrence;
- which observers could locate a referenced position;
- which observers could locate a participating entity;
- which observers identified that entity rather than seeing an anonymous
  contact.

These are event facts, not later queries against mutable `Senses`.

## 4. Current live system

### 4.1 Current dependency and data flow

```text
Tile / placed blocks / directional borders
    -> GridMap.compute_fov()
    -> Entity._filter_visible_positions_by_light()
    -> Entity.update_entity_visibility()/update_entity_senses()
    -> Senses live materialized state
    -> SpatialSensesSystem pre-completion callback
    -> SensoryUpdateEvent children

GridMap light sources
    -> GridMap.compute_light_fov()
    -> Tile illumination dictionaries
    -> resolved Tile light
    -> SpatialChangeEvent.light_changed()
    -> SpatialSensesSystem

Event completion
    -> Encounter-owned perceiver/identity callbacks
    -> event observer-evidence fields
    -> CombatLogEntry observer-evidence fields
```

The first two paths are substantially connected. The third path is a second,
ad hoc subjective projection path owned by `Encounter`.

### 4.2 Current Tile state

`dnd/core/base_tiles.py::Tile` currently carries:

- `visible`: a scalar cell-transparency flag;
- `default_light`;
- source-keyed private `_illuminations`;
- source-keyed private `_obscurements`;
- four intrinsic directional channels;
- four object-derived directional channels;
- direct conditions and UUID references to independently owned spatial
  conditions.

`resolved_light_level` first chooses the brightest illumination, then clamps
it to the darkest obscurement. This source-owned combination is useful, but
the `_obscurements` dictionary currently combines two different meanings:

1. a cap on objective light;
2. a visual obstruction such as fog.

That semantic collapse is the core model defect.

### 4.3 Current physical FOV

`dnd/core/gridmap.py::compute_fov()` uses symmetric shadowcasting when there
are no directional blockers. When directional blockers exist, it uses a
supercover line per candidate cell and checks the `vision` edge channel.

Opaque cells are deliberately included as visible endpoints by the
shadowcasting primitive. This is correct and must be preserved: a wall surface
can be seen while it stops the cells behind it.

The current directional path instead answers whether the complete transition
to a target cell is clear. With boundary objects, the endpoint rule must be
stated explicitly so a boundary wall is itself observable from the near side
while the far cell and its contents remain hidden.

The separate physical-propagation query has its own directional edge channel,
but its center-cell predicate still reuses two visual inputs: a Tile blocks
when `visible` is false, and a center object blocks when `blocks_vision()` is
true. Thus a transparent total-cover object and an opaque non-cover object
cannot be represented independently, and center-door visual mutations also
change propagation only indirectly through cache invalidation.

### 4.4 Current light propagation

`GridMap.compute_light_fov()` repeats the FOV shape with the `light` edge
channel. `LightSourceData` then assigns bright/dim values by distance. Each
Tile retains source-keyed contributions, and light-source movement applies a
delta over old and new footprints.

This is already local in the useful sense: moving a light does not rebuild all
world illumination. The duplicated `vision` and `light` topology remains a
drift risk. The code contains an optimization which reuses vision FOV only
when directional channels happen to be equivalent; that optimization exposes
the duplicated authority rather than solving it.

### 4.5 Current subjective light

`Tile.get_effective_light_for(observer_uuid, observer_position)` is the last
subjective light step today. Its actual order is:

1. truesight or blindsight in range raises the cell to at least bright light;
2. Devil's Sight in range turns natural or magical darkness into bright light;
3. darkvision in range shifts darkness to dim and dim to bright;
4. natural darkness at Chebyshev distance zero or one becomes dim.

`Entity._filter_visible_positions_by_light()` removes geometric-FOV cells
whose resulting light is not above darkness.

This implementation proves that subjectivity already exists, but it is in the
wrong owner and conflates outputs:

- blindsight becomes visual illumination;
- truesight and darkvision operate on fog because fog is encoded as a light
  level;
- `visual_access` and `has_ordinary_sight` do not gate the main FOV pipeline;
- `can_pierce_magical_darkness()` is a range-free boolean used in the FOV
  cache key even though the sense modes themselves have ranges;
- `can_bypass_invisibility()` is also range-free.

### 4.6 Current entity/object perception

After cells are light-filtered, `Entity.compute_senses_from_position()` scans
entities and objects in those cells and calls `is_perceivable_by(observer)`.
That check reads shared `is_invisible` and `stealth_dc` state and broad
range-free observer bypass booleans.

The current `Senses.entities` and `Senses.objects` are therefore visual-contact
stores in most paths, despite the class also carrying blindsight and
tremorsense. The model does not consistently state whether these are “seen”
or “perceived by any sense.”

Perceivability changes publish `SPATIAL_PERCEIVABILITY_CHANGED`. The hint is
entity-shaped: it names `perceivability_entity`. This updates entity contacts,
but an invisible or hidden world object can leave `Senses.objects` stale.

### 4.7 Current reactive observer projection

`dnd/blocks/sensory.py::SpatialSensesSystem` is a useful foundation:

- it is indexed by event type;
- it stores one callback per observer;
- it uses reverse indexes for known positions, visible entities, and visible
  objects;
- it computes before/after `SensesSnapshot` values;
- it publishes `SensoryUpdateEvent` children before the causal parent event
  completes;
- it batches simultaneous observer updates with
  `EventQueue.register_completion_sequence()`;
- it defers expensive path recomputation by marking paths dirty.

This system is not a frontend facade. It is the active in-process subjective
state reducer and is the right owner to improve.

The current limitations are concrete:

- direct full `update_entity_senses()` calls mutate the materialized cache and
  do not inherently emit a sensory event;
- supported Entity deployment does establish an empty-to-full boundary: it
  registers the observer before publishing the Entity's own
  `SPATIAL_ENTITY_ENTERED`, which selects that observer and emits a sensory
  delta. Bare observer registration has no such guarantee;
- a `SpatialEffectChangeEvent` generally considers every registered observer,
  then filters in each callback;
- `effective_light_levels` is rebuilt as a full map for every sensory delta;
- `visual_access` participates in snapshot comparison but its resulting value
  is absent from `SensoryUpdateEvent`;
- optical topology, illumination, contact perception, and path knowledge are
  coordinated in one callback but have partially duplicated predicates.

Some full refreshes occur after their nominal causal parent is already a
completed event: movement refreshes in `Move` and `Jump`, and the turn-start
refresh in `Encounter`. A late sensory event can be stored, but it cannot be
added to the already frozen parent child list. Query-time refreshes in spells
and action discovery also mix perception mutation with navigation-cache
materialization.

### 4.8 Current event/combat-log projection

Event observer evidence is currently captured at three different times:

1. `EventQueue._store_event()` calls the installed entity-observer computer on
   every stored phase. The current location grant replaces the prior phase's
   grant, while identity grants accumulate and inherit through the lineage.
2. Movement explicitly freezes endpoint-position subscribers before the Entity
   position mutates and carries those grants on the step event.
3. `Event._completion_updates()` runs pre-completion systems, recomputes final
   entity-location grants, freezes children, and then builds the combat log.

This ordering is important. An identity learned during declaration or effect
must survive a lethal, hiding, or movement mutation that changes final Senses.
A completion-only lookup would lose that evidence.

However, the policy callbacks are installed only while an `Encounter` is
active:

- `_compute_perceivers()` unions raw GridMap subscribers at affected and
  participant positions;
- `_compute_identified_entity_observers()` checks final `Senses.entities` for
  participants;
- `_compute_revealed_entities()` scans completed child logs and then queries
  mutable final Entity stealth/invisibility state;
- all three functions are removed when the encounter ends.

Raw GridMap subscribers represent geometric FOV subscriptions, including dark
or otherwise unperceived cells. Therefore “receives a combat log” and “has a
subjective sensory contact” can diverge.

Movement's endpoint evidence is necessary, but it currently uses raw
subscribers and is not produced by the same observer authority as sensory
deltas. Also, final `perceiver_uuids` and `revealed_entity_uuids` exist only on
`CombatLogEntry`; the completed Event does not carry those two final facts.

## 5. The exact current stride points

| Stride | Current consequence | Target correction |
|---|---|---|
| Tile `visible` is named as a result but used as optical transparency | World input and observer output share vocabulary | Replace the input meaning with explicit optical opacity/transmission; reserve visible for subjective output |
| Vision and light have separate authored boundary channels | Ordinary walls can accidentally block one but not the other | Ordinary structures contribute one optical boundary fact |
| Center propagation borrows Tile/object vision opacity | Total cover cannot differ from optical opacity and door changes lack exact propagation facts | Give Tile/BaseItem explicit propagation inputs and extend the existing committed blocker-change event |
| Fog and darkness are both stored as `LightLevel` clamps | Darkvision/truesight can treat fog as low light | Separate illumination contributions from optical-obscurement rules |
| Magical darkness participates in FOV through a range-free boolean | Sense range is lost in geometry and cache identity | Resolve conditional obscurement using exact observer modes and ranges |
| Blindsight brightens Tiles | A nonvisual contact sense becomes rendered visual geometry | Keep visual cells and nonvisual contacts separate |
| `visual_access` is not the front gate of FOV | Blinded/unconscious state can leave visual facts alive | Apply the gate before visual projection and emit the resulting delta |
| `has_ordinary_sight` is not part of main visual projection | A creature without ordinary sight can still get ordinary FOV | Make it an explicit input to the observer resolver |
| Perceivability bypass methods ignore range | Truesight/blindsight/tremorsense can reveal distant targets | Resolve bypass per target position and exact `SenseMode.range_feet` |
| Object perceivability changes are entity-shaped | `Senses.objects` can become stale | Carry the changed block UUID and recheck the matching contact family |
| Subjective movement rederives blockers but visual FOV uses objective directional blockers | Hidden directional blockers may leak or visual/path knowledge may disagree | Use one observer-valid optical query for visual reduction; keep subjective movement policy separate |
| Direct Tile light mutation bypasses GridMap revisions | Cached FOV/light can remain stale | Make GridMap the public mutation owner for light and optical contributions |
| Encounter owns event perceiver projection | Observer evidence disappears outside combat and duplicates Senses policy | Move event-time evidence queries to the active observer authority |
| Raw FOV subscribers are treated as final perceivers | Dark/hidden occurrences can leak logs | Use subscriptions only as a candidate index, then apply subjective rules |
| Full sensory refresh is not always evented | Live state can diverge from replayed subjective state | Every committed observer transition emits an existing sensory delta |
| `effective_light_levels` is emitted as a full map per delta | Small changes scale with total visible area | Emit changed after-values only, alongside existing visible removals |
| Entity position exists in both Entity and GridMap indexes | Observer queries can see inconsistent occupancy during mutations | Follow the separate placement plan: Entity owns position; GridMap owns synchronized lookup indexes |
| Natural darkness is promoted to dim at distance zero and one | Renderer convenience is encoded as false illumination/visibility | Self identity remains known, but darkness is not promoted without a rule or sense |
| Any directional blocker selects a per-target supercover FOV scan | One wall changes the cost class of every viewer/light query | Preserve bounded-radius behavior and add a measured directional-FOV budget before migration |

## 6. Target objective world model

### 6.1 One physical optical topology

The ordinary topology query answers whether optical information can travel
through the XY map. It reads:

- Tile intrinsic optical transmission;
- placed center objects that are optically opaque;
- placed boundary structures such as walls and closed doors;
- active spatial conditions that contribute physical optical obstruction.

The legacy Tile `visible` boolean is split into two explicit intrinsic
Pydantic inputs rather than silently reused:

- `blocks_optics: bool` controls ordinary XY optical transmission;
- `blocks_propagation_field: bool` is returned by
  `Tile.blocks_propagation()` for physical propagation through the cell.

Missing Tiles block both. Ordinary floor/water Tiles set both to `False`;
solid wall Tiles set both to `True`. Authored exceptions set each fact
deliberately. These are intrinsic Tile inputs, not observer-visible results and
not a second condition system.

Walls and doors do not carry separate ordinary vision/light choices. Their
single optical contribution is consumed by both viewer-ray and light-source
geometry.

The GridMap placement plan may still retain vertical placement bands for
collision, structure occupancy, renderer binding, and movement support. The
optical query does not perform height-interval ray intersection. Elevation is
not an optical input in this migration. A cliff, wall, balcony edge, or other
structure blocks optics only when its authored mechanical policy says it
does; the engine does not infer optical occlusion from Z height.

### 6.2 Boundary visibility

An opaque boundary has two different answers:

- the boundary object itself is observable from a visible adjacent side;
- the ray cannot cross it to disclose the far Tile or contents.

The subjective reducer therefore adds a perceivable boundary object when its
near-side cell is visible and the boundary lies on that cell's exposed side.
It does not add the far cell merely to make the wall renderable.

This supplies the frontend with the actual object and placement fact. The
frontend chooses the asset and draws the wall. The backend never emits a wall
sprite or VFX name.

### 6.3 Objective illumination remains separate

Tile remains the storage unit for objective illumination, with source-owned
contributions. GridMap remains the public authority which installs, moves,
removes, and batches those contributions.

The clean objective value is ordinary illumination intensity. Magical
darkness is not a fifth brightness intensity that explains every rule. Its
spatial condition owns:

- the source-owned cap which leaves affected cells objectively dark;
- the conditional optical obscurement which ordinary sight cannot cross;
- the exact bypass policy for Devil's Sight or truesight;
- its event and concentration lifecycle.

Fog owns optical obscurement but does not masquerade as natural darkness.
Darkvision therefore cannot transform fog into dim vision. A content-specific
condition may also affect light transport, but ordinary walls remain governed
by the shared physical optical topology.

### 6.4 Spatial conditions are contributors, not a parallel map

The recovered `SpatialCondition` system already provides:

- independent condition ownership;
- GridMap footprint indexing;
- Tile condition visibility through UUID references;
- activation/deactivation lifecycle;
- concentration links;
- typed spatial-effect events.

Optical and illumination contributions belong on those conditions. GridMap
queries the active indexed conditions at a position. The Tile does not copy
condition state, and the condition does not create another visibility map.

## 7. Target observer reduction

### 7.1 One authority, several exact calculations

`SpatialSensesSystem` should become the single in-process observer projection
authority. It may keep its existing name during this migration. The important
change is ownership, not a naming exercise.

It owns these operations for every deployed observer:

1. candidate-observer selection from event positions and reverse indexes;
2. exact visual-cell reduction;
3. exact entity/object contact reduction;
4. before/after Senses snapshots;
5. `SensoryUpdateEvent` emission;
6. event-time perceiver, location, and identity evidence queries.

These are coordinated operations, not one generic reducer callback. Optical
FOV, light interpretation, stealth, and event modalities retain explicit
functions with explicit inputs. The system continues depending on neutral
`BaseBlock`, GridMap, and `dnd.types` capabilities; it does not import Entity
or authored content. Entity installs the existing observer callback, so the
current dependency direction remains acyclic.

One missing neutral capability is added to `BaseBlock`:
`has_ordinary_visual_sight() -> bool`. Its default is the neutral non-Entity
behavior; Entity overrides it by returning its existing
`has_ordinary_sight` field. `SpatialSensesSystem` resolves the owner through
`BaseBlock.get()` and calls this method. The state is neither copied into
`Senses` nor passed through `getattr`. Other required inputs already have
neutral surfaces: `BaseBlock.get_sense_modes()`,
`BaseBlock.get_passive_perception()`, raw source-owned `is_invisible` and
`stealth_dc` facts, and the owner's Senses `visual_access`.

Entity registration supplies only the observer UUID and its existing Senses
block. The current stored `update_senses_func` and `update_visibility_func`
bound callbacks are deleted when the authority takes over exact perception
reduction; retaining them would preserve Entity as a second calculation owner.

### 7.2 Visual-cell reduction

For one observer and destination cell:

1. check `visual_access`;
2. check that the observer has ordinary sight or a genuinely visual special
   sense;
3. resolve physical optical topology;
4. apply observer-relative optical conditions along the route, using exact
   ranges and bypass rules;
5. resolve effective illumination at the destination for the observer;
6. retain the destination when its effective illumination permits visual
   perception.

The result populates `Senses.visible` and expands `Senses.seen`.

### 7.3 Exact sense semantics

| Sense | Physical wall/closed door | Low light | Magical darkness | Fog/heavy obscurement | Invisible contact | Output |
|---|---|---|---|---|---|---|
| Ordinary sight | blocked | requires usable light | blocked | blocked | no contact | identified visual contacts |
| Darkvision | blocked | shifts light within exact range | blocked | blocked | unchanged | visual cells and contacts |
| Devil's Sight | blocked | sees normally in natural darkness within exact range | bypasses within exact range | blocked | unchanged | visual cells and contacts |
| Truesight | blocked | usable within exact range | bypasses within exact range | blocked unless content explicitly says otherwise | bypasses within exact range | visual cells and contacts |
| See Invisible | blocked | still requires ordinary visual conditions | still blocked | still blocked | bypasses within exact range | visual contacts only |
| Blindsight | blocked by the corrected physical-propagation/total-cover query | ignores illumination within exact range | ignores visual darkness within range | can perceive contacts within range | perceives within range | identified nonvisual contacts, not bright Tiles |
| Tremorsense | corrected physical-propagation reach | irrelevant | irrelevant | irrelevant | can perceive contacts within range | identified nonvisual contacts only |

This table is the target contract, not a claim that the current code already
implements every row.

### 7.4 Contact identity

`Senses.entities` and `Senses.objects` become maps to one dependency-neutral
Pydantic value defined in `dnd/types/senses.py`:

```python
from pydantic import BaseModel, ConfigDict


class PerceivedContact(BaseModel):
    model_config = ConfigDict(frozen=True)

    position: tuple[int, int]
    visual: bool
    special_senses: tuple[SensesType, ...] = ()
```

There is no second contact registry and no compatibility mirror. The map value
is the authority for position, whether any visual route established the
contact, and which special senses also establish it. A change of mode at the
same position is a real subjective delta. `special_senses` is stored in
canonical `SensesType.value` order so event payloads are deterministic.

This cut preserves the engine's existing identity granularity: a contact is
inserted under the real entity/object UUID only after that observer identifies
the game object. Blindsight and tremorsense produce identity-known nonvisual
contacts. A hidden or invisible subject which the observer cannot identify is
absent rather than represented by a true UUID plus `identified=False`. The
event/client boundary therefore never exposes a supposedly anonymous contact
under its stable backend identity.

The entity and object dictionaries remain the authoritative hashmaps and use
the same `PerceivedContact` value. A contact exists when
`contacts.get(uuid)` is not `None`; it is seen when that value also has
`visual=True`. Positions and special-sense modes are read from that same value.
Only the sensory reducer mutates the dictionaries. No boolean/get/iterator
wrapper API is added.

All current production membership callers must be classified and migrated
atomically because today's maps mean visual-only contact. Existing tuple value
iterations update to the typed value directly. Targeting a perceived location,
gaze/line-of-sight rules, unseen-attacker rules, protection/reaction features,
fear, class traits, AoE previews, and identity projection do not all use the
same fact. After the cut, contact existence is a valid perceived/identified
gate, `contact.visual` is the visual gate, and external hashmap mutation is an
architecture-test failure.

Stealth and invisibility remain condition-owned mechanics. Their application
and removal must derive final perceivability from all surviving source-owned
conditions. Removing one `Invisible` or `Hidden` instance must not clear the
state contributed by another instance.

The exact contact resolver does not call `BaseBlock.is_perceivable_by()`. That
method delegates to the range-free `can_bypass_invisibility()` hook and would
preserve a second subjective policy. Entity/object contact callers migrate to
the authority's exact raw-fact resolver; subjective movement/path callers use
the observer's materialized typed contact maps through the neutral
`SensesView`. Once those
callers and Tile filtering migrate, `BaseBlock.is_perceivable_by()`,
`can_bypass_invisibility()`, `can_pierce_magical_darkness()`, and their Entity
overrides are deleted together.

`SpatialCondition.is_perceivable_by()` is not retained under that overloaded
name. Its independent passive-perception hazard check becomes the explicitly
named `is_hazard_perceived_by()` navigation input; it does not decide
entity/object contacts or special-sense bypass.

### 7.5 Nonvisual topology and subscriptions

Blindsight reuses the existing physical-propagation interface; it does not
reuse illuminated visual FOV. Before relying on that interface, the center-cell
predicate is corrected to call one neutral `BaseBlock.blocks_propagation()`
capability rather than treating `blocks_vision()` as total cover. The neutral
default is `False`; `BaseItem` exposes an explicit Pydantic
`blocks_propagation_field`, and active authored center blockers are reviewed and
set deliberately. Directional edges continue using their existing propagation
channel.

Tremorsense uses the same bounded propagation query. In the current 2D engine,
every deployed Entity occupies and contacts its support Tile; there is no
persisted airborne state. That existing support-contact rule is the exact
grounding contract for this cut. Both nonvisual senses are keyed by the current
global propagation revision and exact sense range.

An observer's GridMap subscription footprint is the union of:

- ordinary optical candidate cells;
- bounded blindsight propagation cells;
- bounded tremorsense propagation/support cells.

The reverse subscription index remains only a candidate selector. The exact
contact resolver checks range, visual access where applicable, the exact
optical/propagation route, obscurement, invisibility, stealth, and identity
before updating a
`PerceivedContact`.

## 8. The shared subjective boundary with events

### 8.1 What can be shared

Sensory reduction and event propagation can share exactly two things:

1. the indexed candidate-observer selection substrate;
2. the authoritative query of what an observer could perceive, locate, and
   identify at the event boundary.

This removes the current split where `SpatialSensesSystem` produces one answer
and `Encounter._compute_perceivers()` produces another.

### 8.2 What remains domain-specific

An event is not automatically visual. A sword impact, spoken phrase, magical
pulse, and creature movement can expose different information. The observer
authority therefore applies an explicit modality rule for the concrete event
using the event's existing participants, affected positions, and evidence.

The first migration only needs existing visual/spatial semantics. Future sound
or other propagation can use the same candidate indexes and evidence fields,
while supplying its own propagation calculation. EventQueue does not become a
vision engine, and `SpatialSensesSystem` does not become an event dispatcher.

### 8.3 Required lifecycle order

The observer authority attaches to the existing event lifecycle at three exact
seams. It does not move action mutations or invent a new transaction layer.

```text
A. EVERY STORED PHASE
   EventQueue stores declaration/execution/effect versions
   -> installed observer query captures current entity location/identity
   -> located grants replace for this phase
   -> identified grants accumulate through the lineage

B. BEFORE A MUTATION DESTROYS POSITION EVIDENCE
   movement/teleport/forced-move code asks the same observer authority for
   exact observer grants at previous and destination positions
   -> the objective event carries those frozen grants through completion

C. PRE-COMPLETION
   authoritative mutation and GridMap indexes/revisions are already committed
   -> affected light-source footprints are current
   -> observer authority snapshots selected observers before/after reduction
   -> SensoryUpdateEvent children are stored as one completion sequence
   -> final location evidence is frozen on the Event
   -> CombatLogEntry derives terminal perceiver/reveal sets from frozen Event
      grants and already recorded sensory/child facts
```

The event stream then contains the objective fact and its causally attached
subjective deltas. A client does not recompute FOV or query mutable backend
objects to explain what changed.

### 8.4 Event-time evidence is not final-state lookup

Movement demonstrates why this matters. An observer may witness a creature
leave one cell even when the creature is no longer in its final visible set.
The observer authority must capture before/after evidence at the causative
boundary and preserve the relevant union or endpoint-specific grants on the
event.

The existing Event fields remain the contract:

- `identified_entity_observer_uuids` for durable identity learned in a
  lineage;
- `located_entity_observer_uuids` for event-time exact entity location;
- `located_position_observer_uuids` for event-time coordinate evidence.

The three grant matrices remain `exclude=True` on the generic objective-event
wire because they expose cross-observer privacy information. Observer-specific
`SensoryUpdateEvent` payloads and the filtered combat-log boundary are the
public subjective streams.

`perceiver_uuids` and `revealed_entity_uuids` remain solely on
`CombatLogEntry`; they are not duplicated onto every base Event. At completion,
the observer authority computes the local terminal sets from the Event's frozen
grant maps plus already recorded sensory/child facts—never from mutable final
Senses. The existing combat-log child fold then unions child identity,
perceiver, and reveal evidence. Child-local entity/position grants remain on
their own Events. This preserves the combat log as the completed causal-tree
serialization of events without adding another Event schema or fold.

Movement's manually frozen endpoint evidence should be produced through this
same authority. The event continues carrying the data; no wrapper type is
introduced above it.

Perceivability-change spatial facts also carry the changed block UUID and the
final source-derived `is_invisible`/`stealth_dc` values. During pre-completion,
the observer authority derives reveal evidence from those facts plus actual
contact additions. This replaces the Encounter callback which scans child logs
and then queries mutable Entity state.

### 8.5 Remove Encounter ownership

The observer authority is part of the in-process game world, not Encounter.
It is active during game initialization, exploration, encounter play, and
post-encounter state. Encounter can consume subjective facts but does not
install global observer policy callbacks.

EventQueue remains dependency-neutral. It retains narrow callback slots and
the pre-completion seam; the game/observer layer installs the authority's
phase-store, pre-completion, and completion-evidence callables. Encounter's
perceiver, identity, and reveal callback installations are deleted together.
No base-Event schema, EventQueue, reducer framework, or second child-fold is
added.

### 8.6 Perception projection versus navigation caches

The replay boundary in this plan is the visual/contact projection:

- observer position;
- visible and explored cells;
- entity/object `PerceivedContact` maps;
- effective-light values for visible cells;
- current sense modes, passive perception, and visual access.

The following current `Senses` fields remain ephemeral derived navigation
caches in this migration: `walkable`, paths, path costs, safe paths, safe path
costs, `_paths_dirty`, and collision memories. They are recomputed from the
objective world plus reduced observer knowledge. Exact replay of navigation
knowledge is a later movement/action-discovery cut and is not a completion
claim here.

To make this boundary honest, the current combined full refresh is split by
responsibility:

- committed objective events maintain visual/contact projection before their
  parent completes;
- query-time and turn-boundary code may materialize navigation caches without
  mutating visual/contact projection;
- `Move`, `Jump`, turn start, teleport, and every other direct full-refresh
  caller are ledgered. Any visual/contact difference must be moved before the
  causal parent completion; navigation-only refresh may remain late and is not
  emitted as a visual delta.

## 9. Cache and invalidation contract

### 9.1 Cache families

| Cache/index | Key authority | Invalidated by |
|---|---|---|
| Physical optical geometry | existing origin/radius/global optical revision key | Any optical-topology change clears the cache lazily; selected observers recompute on demand |
| Objective light-source footprint | existing `LightSourceData` and `affected_tiles` | Source change, or radius-filtered recomputation after an optical change |
| Objective Tile illumination | source-owned contributions | light add/move/remove/toggle or light cap change |
| Observer visual projection | existing live `Senses`, `SensesSnapshot`, and `ObserverFootprint` | Observer move/capability change or an indexed local optical/illumination event |
| Observer contact indexes | observer projection/contact result | contact move, perceivability change, sense change |
| Blindsight/tremorsense reach | origin, exact range, current global propagation revision | Any physical-propagation change clears this cache lazily; it does not eagerly recompute observers |
| Subjective navigation caches | movement revision plus observer knowledge signature | Movement topology, occupancy knowledge, observer perception change |

The physical optical cache keeps the current simple revision-keyed/global-clear
shape. Clearing it does not eagerly recompute every observer: the existing
spatial subscription indexes select affected observers, and other origins
recompute only when next queried. This cut adds no per-ray dependency records
or reverse position-to-cache-key index.

Light invalidation also keeps the current direct mechanism.
`GridMap.recompute_lights_at_position()` scans active `_light_sources`, rejects
sources whose radius cannot reach the changed position, and footprint-diffs
only qualifying sources against `affected_tiles`. It scans neither Tiles nor
map area and needs no second influence-region index. Source-count benchmarks
remain a gate before any later indexing work is justified.

Conditional spatial obscurement is applied in the observer reduction and
keyed by the exact relevant sense signature and range. Its activation,
movement, transformation, and removal select observers from subscriptions over
the union of `previous_positions` and `affected_positions`; they do not iterate
every registered observer.

The current propagation cache is an explicit bounded exception to regional
eviction. A propagation change increments the global propagation revision and
clears cached blindsight/tremorsense reach; observers are recomputed only when
selected or queried. This cut does not add a second reverse-dependency index
for these nonvisual senses.

### 9.2 Mutation ownership

Public mutation goes through GridMap or the owning domain transaction:

- boundary/world object placement or state change;
- Tile optical-property change;
- light-source add/move/remove/toggle;
- spatial-condition activation, footprint change, and deactivation;
- Entity movement and perceivability change.

Direct public Tile light mutation is removed from ordinary callers. Internal
Tile contribution methods may remain as GridMap implementation details.

Intrinsic Tile optics/propagation changes and mutable center-object blocker
changes use one committed mutation contract:

1. capture the previous movement/optical/propagation values;
2. commit the owning Tile or BaseItem fields;
3. increment and lazily clear the existing changed-channel caches; no observer
   is eagerly recomputed solely because a global revision changed;
4. publish the corresponding existing Tile/object created, removed, or changed
   lifecycle with complete final facts;
5. let `SpatialSensesSystem` reduce affected observers at pre-completion.

`SpatialChangeEvent` therefore replaces `tile_visible` with final
`tile_blocks_optics` and adds final `tile_blocks_propagation` and
`object_blocks_propagation` facts. Mutation code compares previous and final
values locally to invalidate caches and set the existing
`requires_propagation_recompute` hint. Previous values and a persisted
`blocks_propagation_changed` flag are not added to the event: `change_type`,
the reducer's prior state, and the complete final fact already provide the
replay contract. These are fields on existing event families, not new event
types.

`BaseItem._notify_blocking_changed()` accepts the previous propagation value in
the same call as previous movement/optical values. `DoorObject` open/close
captures all three previous facts, toggles its
`blocks_propagation_field` with its closed state, and publishes once. The
directional door already changes the propagation edge channel in its bulk
directional transaction and retains that single event path. An open/closed
door test verifies visual, light, and nonvisual propagation invalidation
together.

### 9.3 Locality

Eager work is bounded to existing candidate sets and affected footprints. It
may scan active light-source count, but it must not scan total Tiles or map
area:

- a one-cell light change looks up subscribers to that cell;
- a moved local light diffs its old/new footprint;
- a changed wall scans active light sources and recomputes only those whose
  bounded radius can reach the changed edge;
- a spatial-condition footprint change uses the union of previous and current
  positions;
- observer callbacks are selected by reverse indexes before exact reduction;
- path recomputation remains deferred until required.

The directional optical implementation has its own performance gate. Today a
single directional blocker switches the query from symmetric shadowcasting to
a bounded-square scan with one supercover path per candidate destination. The
migration may retain or replace that algorithm, but representative cold and
warm timings must be measured with zero, one, and many boundary blockers. Work
must remain bounded by the configured sight/light radius rather than total map
size, and one wall must not cause an unmeasured whole-map regression.

The `SensoryUpdateEvent` light payload becomes an actual delta: changed
after-values for newly visible or still-visible cells whose effective light
changed. Existing visible-cell removals delete obsolete values. It does not
copy the observer's entire visible light map for an unrelated contact change.

The locality claim applies to eager observer selection, light footprint work,
spatial-condition candidate selection, and sensory deltas. Optical and
physical-propagation query caches use explicit global lazy invalidation; they
do not cause eager world/observer recomputation.

## 10. Event payload contract

### 10.1 Objective spatial events

The existing objective event families remain. Their payload must carry final
domain facts and complete affected positions. `SensesUpdateHint` remains an
acceleration hint; replay correctness cannot depend on the hint.

During the hard cut, `vision` and `light` topology hints become one optical
topology change. Illumination changes remain distinct because changing a
light's intensity does not necessarily change physical geometry.

`WorldInitializedEvent` uses the same cold objective vocabulary: every Tile
row carries final `blocks_optics` and `blocks_propagation`, and every placed
center-object row carries final optical/propagation policy. Bootstrap does not
retain `tile_visible` as an alias.

### 10.2 SensoryUpdateEvent

The existing event remains the subjective delta. It must be sufficient to
reduce the perception projection named in Section 8.6 without querying the
live engine. Its final contract
includes:

- observer UUID and position;
- visible cell additions/removals;
- explored cell additions;
- `entity_contacts_changed` and `object_contacts_changed`, each keyed by UUID
  to the complete final `PerceivedContact`. The same after-value represents an
  add, move, visual/nonvisual-mode change, or identity change;
- `entity_contacts_removed` and `object_contacts_removed`, each a UUID set;
- changed effective-light after-values;
- final sense modes when they change;
- final passive perception when it changes;
- final `visual_access` when it changes.

The current `visible_entities_added/removed/moved` and object equivalents are
replaced atomically by the changed/removed fields; they do not remain as
aliases. This avoids a second delta model and keeps each event value as the
complete cold fact needed by replay. The current `paths_dirty` notification may
remain for navigation invalidation during the later movement cut, but it is
not part of visual/contact replay parity.

No separate visibility event, light-visibility event, or frontend projection
DTO is added.

### 10.3 Bootstrap and replay

World bootstrap remains an objective `WorldInitializedEvent`. Entity birth and
deployment remain objective facts. Supported deployment already registers the
observer before publishing its own `SPATIAL_ENTITY_ENTERED`; that event reduces
from the empty contact/visibility baseline and emits the initial sensory delta.
This path is preserved and tested as exactly one delta. Bare observer
registration becomes internal to Entity deployment and cannot create a second
bootstrap path.

Battlefield construction retains its existing event-disabled GridMap
transaction. Arena base-light assignment goes through the GridMap-owned build
mutation inside that transaction, emits no per-Tile light facts, and is captured
only in the final `WorldInitializedEvent`. This avoids a second bootstrap event
stream while preserving final objective light state.

Replay order is therefore:

```text
WorldInitializedEvent
EntityCreated/deployment and later objective events
SensoryUpdateEvent children in their recorded causal order
```

An in-process renderer applies the same sensory events as a future network
client. A client-facing stream includes only the
`SensoryUpdateEvent.observer_uuid` projections that client is authorized to
observe; it never broadcasts every observer's subjective delta. The renderer
does not need GridMap internals or Python rule types.

Replay parity compares only the Section 8.6 perception fields. Navigation
caches are recomputed and are verified separately against objective world plus
observer knowledge.

## 11. Integration with the Tile/WorldItem/GridMap plan

The live code does not yet have a `WorldItem` type or Tile-owned center and
boundary placement indexes. Phases 1–5 of this document therefore operate on
the current `BaseItem`/Tile/GridMap placement interfaces. They do not create a
temporary WorldItem facade or adapter.

Phase 6 has one explicit external prerequisite:
`DND_TILE_WORLD_ITEM_PLACEMENT_CLEAN_PLAN_2026-08-17.md` must land first. That
plan owns the exact placement types, Tile dictionaries, reverse indexes,
placement mutation order, Item location facts, wall/door/torch behavior, and
Entity/GridMap position synchronization. This document owns only the optical,
illumination, observer, and event-evidence behavior which that placement cut
must preserve.

After that prerequisite, these target boundaries apply:

- Tile owns center/boundary placement indexes;
- GridMap owns reverse object-placement indexes;
- WorldItem declares placement shape and mechanical occupancy;
- Entity owns its position while GridMap maintains synchronized spatial lookup;
- boundary structures are actual placed objects;
- spatial conditions remain independently owned and Tile-indexed by UUID.

The placement implementation then receives these visibility-specific
requirements:

1. ordinary boundary structures own one optical contribution instead of
   separately authored vision and light contributions;
2. elevation bands do not drive sight/light ray intersection;
3. world-edge output exposes the placed structure and its optical policy, not
   duplicated rendered wall facts;
4. optical topology mutation invalidates both viewer geometry and affected
   objective light footprints;
5. Tile replacement/removal continues to reject or safely tear down active
   light and condition ownership according to the placement plan;
6. boundary-object observability uses the near-side endpoint rule;
7. spatial conditions may contribute illumination, optical obscurement, or
   both through their existing lifecycle.

## 12. Migration phases

### Phase 0: freeze current behavior with focused tests

Before changing production code, characterize the current red baseline at
`tests/engine/test_senses_light_stealth.py:154`, where the existing
natural-darkness expectation currently fails. Diagnose that failure separately
from the explicit adjacent-cell promotion asserted on the following line. The
migration must not mistake either false visibility path for a protected
capability.

Record current and intended behavior for:

- ordinary bright/dim/dark cells;
- wall and closed/open door topology;
- visible opaque endpoint and hidden far cell/content;
- darkvision range boundary;
- Devil's Sight and truesight range boundaries;
- fog versus natural darkness versus magical darkness;
- invisibility and See Invisible range;
- blindsight contact without visual-cell illumination;
- self identity remaining known without making an unilluminated cell visually
  visible;
- object perceivability changes;
- light-source movement and wall/door light recomputation;
- event-time movement endpoint evidence;
- exactly one empty-to-full sensory delta on supported Entity deployment;
- sensory-delta replay parity for perception fields only;
- cold/warm directional FOV timings with zero, one, and many blockers.

Inventory every direct `Senses.entities` and `Senses.objects` caller named in
Section 14. Do not infer that current membership always means the same thing:
each call site must be classified as contact existence or visual contact from
the rule it implements. Every retained contact is already identity-known.

### Phase 1: separate optical topology from illumination

- replace legacy Tile `visible` with explicit intrinsic `blocks_optics` and
  `blocks_propagation_field` inputs and migrate every Tile factory in the same
  cut;
- replace ordinary vision/light structure duplication with one optical
  contribution;
- replace the center-object propagation fallback to `blocks_vision()` with
  `BaseBlock.blocks_propagation()` and explicitly author the corresponding
  BaseItem field at every active global blocker construction site;
- keep illumination as source-owned Tile state;
- move fog/smoke concealment out of the `LightLevel` scalar;
- make magical darkness an explicit condition contribution to darkness and
  conditional optical obscurement.

### Phase 2: centralize world mutation and revisions

- route Tile illumination and optical contributions through GridMap;
- retain the existing global lazy optical/propagation cache invalidation;
- retain the existing active-light-source radius scan and `affected_tiles`
  footprint diff;
- make optical changes recompute affected light sources before observer
  reduction;
- extend Tile/object blocker mutation and the existing spatial event payload
  with final propagation state and the exact changed hint computed locally;
  migrate center-door open/close in the same cut;
- publish complete affected-position events from runtime committed mutations;
  the existing event-disabled battlefield build remains summarized solely by
  `WorldInitializedEvent`.

### Phase 3: correct the observer resolver

- add the dependency-leaf Pydantic `PerceivedContact` value and change both
  contact maps atomically;
- apply `visual_access` and `has_ordinary_sight` at the visual front gate;
- resolve every sense against exact range;
- separate visual-cell results from nonvisual contacts;
- make fog, magical darkness, invisibility, and ordinary darkness obey the
  explicit sense table;
- make entity and object perceivability use the same contact resolver;
- derive shared invisibility/stealth flags from surviving source owners;
- migrate every current membership gate to either typed contact existence or
  `contact.visual`, as selected in Phase 0, and update position/mode readers to
  the same typed value;
- delete the range-free `is_perceivable_by`, invisibility-bypass, and
  magical-darkness-bypass hooks after all perception/navigation/Tile callers
  in Section 14 migrate; rename only the independent spatial-hazard passive
  check to `is_hazard_perceived_by`.

### Phase 4: make SpatialSensesSystem the sole observer authority

- retain its reverse indexes and pre-completion lifecycle;
- install its evidence query at every stored event phase so current location
  is replaced while identity accumulates through the lineage;
- use that same authority before movement, teleport, or forced movement mutates
  away endpoint evidence;
- freeze final location evidence after pre-completion sensory reduction;
- compute terminal perceiver/reveal sets directly on `CombatLogEntry` from the
  existing frozen Event grants and recorded sensory/child facts, preserving the
  current combat-log child union and never querying mutable final Senses;
- move the perceiver, identity, and reveal callback installations out of
  Encounter together;
- use subscriptions only for candidate selection;
- remove the stored Entity-bound full-senses/visibility callbacks from the
  sensory callback registration surface;
- replace movement's direct subscriber evidence helper with the same authority;
- make perceivability-change facts name the changed block and carry final
  source-derived invisibility/stealth state;
- preserve Event fields as the ground-truth evidence carrier.

### Phase 5: close sensory replay

- preserve the existing supported deployment path as exactly one initial
  empty-to-full sensory delta and make bare observer registration internal;
- split visual/contact projection refresh from navigation-cache materialization;
- move visual/contact changes in direct `Entity.move`, `Move`, `Jump`, turn
  start, teleport, scenario deployment, and the ledgered query-time refreshes
  into the relevant objective event's pre-completion boundary;
- include changed visual access, contact modes, and light after-values;
- reduce the recorded stream into a fresh perception projection and compare
  only the Section 8.6 fields after every tested boundary;
- recompute navigation caches separately from objective world plus observer
  knowledge and make no replay-completeness claim for them in this cut.

### Phase 6: integrate the placement migration

- begin only after the external placement plan named in Section 11 lands;
- migrate walls, doors, cliffs, center blockers, torches, and other world
  objects onto the new Tile placement indexes;
- preserve optical, illumination, event, and observer-reduction behavior;
- remove legacy directional Tile/object mirrors only after parity tests pass.

## 13. Verification gates

### 13.1 Semantic gates

1. A darkvision observer sees natural darkness within range but not beyond it.
2. Darkvision does not see through Fog Cloud.
3. Devil's Sight sees through magical darkness within range but not through a
   wall or Fog Cloud.
4. Truesight handles magical darkness and invisibility within range but not a
   wall or generic heavy fog.
5. Blindsight produces a contact in darkness/fog without marking the Tile
   brightly lit or visually visible.
6. Blinded or otherwise zero `visual_access` removes visual cells and ordinary
   visual contacts through a `SensoryUpdateEvent`.
7. A creature with no ordinary sight does not receive ordinary visual FOV.
8. Removing one of multiple invisibility/stealth sources preserves the
   surviving source's result.
9. Hidden/invisible world-object changes update `Senses.objects`.
10. A near-side wall is perceived as an object while the far Tile and its
    contents remain undisclosed.
11. The observer knows itself without the engine promoting the observer's dark
    Tile or adjacent dark Tiles to visible/dim illumination.
12. A contact established only by blindsight or tremorsense satisfies
    contact existence but has `visual=False`; each targeting, gaze, reaction,
    and event identity rule reads the fact selected from its actual semantics.
13. Blindsight and tremorsense respect the corrected propagation query, whose
    center objects expose an explicit neutral propagation-blocking capability;
    every deployed Entity is support-contacting in the current 2D model.
14. A transparent total-cover object can block propagation without becoming
    optically opaque, while an optically opaque non-cover object does not block
    propagation unless its explicit policy says so.
15. Opening and closing a center door changes its objective movement,
    optical, and propagation facts in one spatial lifecycle; blindsight and
    tremorsense reach update from the propagation change without a full
    observer sweep.
16. Floor, water, solid-wall, and missing-Tile cases exercise the independent
    intrinsic optics/propagation truth table after legacy `Tile.visible` is
    removed.

### 13.2 Event gates

1. Every observation-affecting objective event is followed by zero or more
   causal `SensoryUpdateEvent` children before parent completion.
2. All observers changed by one objective fact are stored as one completion
   sequence.
3. Event/combat-log perceivers match the observer authority, not raw GridMap
   subscribers.
4. Movement preserves exact from/to event-time evidence even when final
   `Senses` no longer contains one endpoint.
5. Observer evidence exists outside an active Encounter.
6. Identity learned at declaration or effect remains on the lineage after a
   lethal, hiding, or movement mutation changes final observer state.
7. Every stored phase refreshes current location evidence while identity
   evidence is cumulative; pre-completion then freezes final Event location
   evidence.
8. `CombatLogEntry` terminal perceiver/reveal sets derive from frozen Event and
   recorded sensory/child facts, preserve the existing child-log union, never
   query mutable final Senses, and are not duplicated on base Event.
9. Supported Entity deployment emits exactly one empty-to-full
   `SensoryUpdateEvent`, not zero and not a second registration event.
10. Visual/contact deltas caused by `Move`, `Jump`, turn start, and teleport are
    children of the relevant causal event before that parent freezes its child
    lineage.
11. Replaying objective and sensory events reproduces visible cells, explored
    cells, typed contacts, effective-light values, sense modes, passive
    perception, and visual access without live-engine queries. Navigation
    caches are explicitly excluded.

### 13.3 Cache and locality gates

1. Repeated unchanged physical-optical queries hit their cache.
2. An illumination-only change does not invalidate unrelated movement or
   physical-propagation caches.
3. One changed optical boundary invalidates viewer geometry and recomputes only
   light sources whose radius can reach it.
4. A one-cell illumination change evaluates only observers subscribed to the
   affected region.
5. A local spatial-condition footprint delta selects candidates from the union
   of `previous_positions` and `affected_positions` and does not iterate every
   observer or Tile.
6. A small contact-only sensory update does not serialize the complete visible
   light map.
7. A global optical revision clears cached queries lazily without eagerly
   recomputing unrelated observers.
8. Active-light-source timing/counters confirm an optical change scans source
   count rather than map area and recomputes only sources within radius.
9. Fixed-radius cold and warm timing/counter tests compare zero, one, and many
   directional blockers; work is independent of total map size and the
   one-blocker cost-class change is measured rather than hidden.
10. A propagation change may clear the global lazy propagation cache, but does
   not eagerly recompute every blindsight/tremorsense observer.

### 13.4 Architecture gates

1. `dnd/core/events` imports no Entity, GridMap, Senses, content, or renderer
   module.
2. GridMap imports only neutral block/Tile/type capabilities, not authored
   spells or concrete spatial-condition classes.
3. Spatial conditions do not import frontend assets or renderer identifiers.
4. Encounter does not install global observer-perception policy.
5. No late imports, `TYPE_CHECKING` cycle masks, dynamic `getattr` contracts,
   compatibility facade, parallel visibility registry, or custom serialization
   layer is introduced.
6. All new persisted/event contracts remain Pydantic models consistent with
   the engine's existing validation and API boundary.
7. `PerceivedContact` is a dependency-leaf Pydantic value; only the sensory
   reducer mutates the contact maps. Production rules read contact existence or
   `contact.visual` directly; no wrapper layer is introduced.
8. Internal hot-path records such as `VisibilityComputationCache`,
   `SensesSnapshot`, and `ObserverFootprint` remain frozen dataclasses; they are
   neither persisted nor wire contracts.
9. The observer authority remains dependent only on neutral BaseBlock,
   GridMap, event, and `dnd.types` contracts; it imports neither concrete
   Entity nor authored content.
10. No range-free `BaseBlock.is_perceivable_by`,
    `can_bypass_invisibility`, or `can_pierce_magical_darkness` subjective hook
    remains; navigation consumes typed materialized contacts and the observer
    authority consumes raw source-owned facts plus exact ranges/routes.

## 14. File and symbol migration ledger

| Current owner | Current responsibility | Target responsibility |
|---|---|---|
| `dnd/core/base_tiles.py::Tile` | `visible` conflates intrinsic optical and propagation blocking; also owns objective/subjective light methods | Explicit `blocks_optics`/`blocks_propagation_field`, private source-owned objective illumination, no observer method |
| `dnd/core/gridmap.py` | Vision/light/propagation geometry, light sources, revisions, range-free subjective filters | Physical optical geometry, objective light, exact mutations, existing revision-cleared caches, and active-light radius scan; subjective navigation reads materialized contacts |
| `dnd/core/shadowcast.py` | Symmetric cell FOV | Retained geometric primitive with explicit opaque-endpoint contract |
| `dnd/core/world_edges.py` | Four-channel edge view | Movement, physical optical, and physical-propagation structural facts without renderer data |
| `dnd/types/world.py` | Movement, LightLevel, four edge channels | Movement, ordinary illumination levels, and the reduced structural vocabulary |
| `dnd/types/senses.py` | Dependency-leaf `SensesType`, `SenseMode`, and `SensesView` | Add frozen Pydantic `PerceivedContact` and update `SensesView` to typed contact values |
| `dnd/core/base_block.py` | Neutral senses plus range-free perceivability/bypass surfaces; propagation center blockers borrow vision | Add `has_ordinary_visual_sight()` and `blocks_propagation()`; delete range-free subjective hooks; no Entity/content dependency |
| `dnd/blocks/base_item.py` | Global/directional vision and light flags; no explicit center propagation flag | Explicit `blocks_propagation_field` plus one movement/optical/propagation mutation notification |
| `dnd/items/environment.py` | Wall/door duplicated channel authoring | Concrete structure state using neutral optical/movement/propagation capabilities |
| `dnd/items/environment_interactables.py` | Center door open/close changes movement/vision only | Toggle movement/optics/propagation together and publish one complete existing spatial lifecycle |
| `dnd/items/environment_content.py`, `dnd/content/items/authored_item_definitions.py`, `dnd/content/items/authored_item_builders.py` | Active center blockers author only movement/vision | Explicitly author center propagation for every blocker definition/build path; no inference from optical opacity |
| `dnd/content/items/environment_item_builders.py::build_door` | Direct `DoorObject` construction authors movement/vision only | Author `blocks_propagation_field=not is_open` in the same direct builder; authored-item callers continue using this one path |
| `dnd/maps/arena_layout.py::darken_arena` | Directly mutates every Tile `default_light` | Route base-light assignment through the GridMap-owned mutation inside the existing event-disabled battlefield build; emit no separate light fact because `WorldInitializedEvent` is the sole bootstrap fact |
| `dnd/content/scenarios/battlefield_builders.py` | Authors legacy `visible=` Tiles, calls arena darkening, and captures `WorldTileState.visible` | Author final Tile optics/propagation fields, call the GridMap light batch, and serialize final `blocks_optics`/`blocks_propagation` bootstrap facts with no `visible` alias |
| `dnd/spatial/area_conditions.py` | Light and obscurement both represented as light modifiers; generic-named hazard perception helper | Spatial illumination/optical-obscurement contributions and explicit `is_hazard_perceived_by` navigation helper |
| `dnd/blocks/sensory.py::Senses` | Mixed visual/contact/path cache | Materialized observer result with visual cells and typed perceived contacts |
| `dnd/blocks/sensory.py::SpatialSensesSystem` | Reactive Senses deltas | Sole observer projection and event-evidence authority |
| `dnd/entities/entity.py` | Full/partial senses algorithms and broad bypass booleans | Entity state/capabilities; observer calculations move behind the sensory authority |
| `dnd/core/events/world_events.py` | Spatial hints, legacy Tile visibility, no center-object propagation fact, and sensory deltas | Same event families with optical/propagation final facts and hints plus perception-replay-complete sensory deltas |
| `dnd/core/events/events_registry.py::Event` | Lifecycle, phase evidence, excluded location/identity grants | Retain the existing fields and callback seams unchanged; install the neutral observer authority without new base fields or child fold |
| `dnd/encounters/encounter.py` | Installs perceiver, identity, and reveal policy | Consumes observer facts; installs none of the three global policies |
| `dnd/core/combat_log.py` | Owns terminal perceiver/reveal sets and child-log union | Retain that ownership; compute locally from frozen Event grants and recorded sensory/child facts rather than mutable Senses |

### 14.1 Direct contact-map caller ledger

The following active production files directly read or mutate
`Senses.entities`/`Senses.objects` today and must be reviewed during Phase 0.
The target column is deliberately not prefilled with one blanket answer:
classification must follow the concrete game rule at each call site.

| Caller family | Active files | Required migration decision |
|---|---|---|
| Core targeting and area queries | `dnd/core/base_actions.py`, `dnd/core/aoe.py` | Classify each gate as identity-known perceived contact or visual line of sight |
| Entity action discovery/navigation | `dnd/entities/entity.py` | Use typed contact positions for perception; keep navigation cache access separate |
| Standard actions and reactions | `dnd/actions/standard.py`, `dnd/items/weapons.py` | Preserve the exact “see”, “perceive”, and unseen-attacker wording per rule |
| Conditions | `dnd/conditions.py` | Classify fear, charm, invisibility, and attacker/target checks independently |
| Classes and features | `dnd/classes/barbarian.py`, `dnd/classes/fighter.py`, `dnd/classes/rage.py`, `dnd/extensions/aegis_spark.py` | Preserve each feature's visual or any-contact requirement |
| Monster rules | `dnd/monsters/skeleton_abilities.py`, `dnd/monsters/traits.py` | Preserve gaze/visual gates separately from awareness/contact gates |
| Spells | `dnd/spells/abjuration.py`, `dnd/spells/conjuration.py`, `dnd/spells/illusion.py`, `dnd/spells/infernal.py`, `dnd/spells/necromancy.py`, `dnd/spells/transmutation.py` | Preserve each spell's exact targeting, reaction, and identity semantics |
| Authored item mechanics | `dnd/content/items/authored_item_builders.py` | Keep authored behavior and read typed contact existence or `contact.visual`, according to the authored rule |
| Observer owner | `dnd/blocks/sensory.py` | Internally owns typed contact maps, reverse indexes, the exact resolver, and reducer-owned mutation |
| Temporary policy owner | `dnd/encounters/encounter.py` | Delete its direct contact lookup with the three observer-policy callbacks |
| Neutral object capability | `dnd/core/base_block.py` | Retain only the neutral “appears in object senses” capability; no direct subjective policy |

No compatibility dictionary preserving tuple-valued contact semantics remains
after this cut. Tests and fixtures which manually assign `(x, y)` values migrate
to `PerceivedContact` or exercise the real sensory event/reducer boundary.

The range-free helper cut has this complete active production disposition:

| Current caller | Required disposition |
|---|---|
| `dnd/blocks/sensory.py` | Replace every entity/object `is_perceivable_by` call with the authority's raw invisibility/stealth plus exact sense range/route resolver |
| `dnd/entities/entity.py` visual/full-refresh helpers | Delete the duplicate contact calculation as `SpatialSensesSystem` assumes ownership |
| `dnd/entities/entity.py::can_end_movement_at` | Test typed entity-contact existence for subjective known occupancy |
| `dnd/core/gridmap.py` subjective walkability/directional/path filters | Resolve the requesting observer's neutral `SensesView` and query typed entity/object contacts; never recalculate invisibility |
| `dnd/core/base_tiles.py` and `dnd/core/gridmap.py` magical-darkness/FOV cache helpers | Delete range-free bypass calls; the observer resolver applies exact `SenseMode.range_feet` |
| `dnd/spatial/area_conditions.py` hidden-hazard check | Rename the independent passive-perception rule to `is_hazard_perceived_by()` and use it only for navigation hazard knowledge |

After these rows migrate, repo-wide symbol gates require zero remaining calls
or definitions of the three range-free subjective hooks.

### 14.2 Existing full-refresh caller ledger

These calls currently mix perception projection with navigation-cache refresh:

| Boundary | Active caller | Required disposition |
|---|---|---|
| Direct Entity utility move | `dnd/entities/entity.py::Entity.move` | Route ordinary runtime movement through the objective spatial-event path; remove its global perception refresh. Setup/deployment uses the explicit bootstrap path |
| Move completion | `dnd/actions/standard.py::Move` | Perception delta before parent completion; navigation cache may materialize afterward or on demand |
| Jump completion | `dnd/actions/standard.py::Jump` | Same split as Move |
| Turn start | `dnd/encounters/encounter.py` | Objective turn fact may trigger navigation materialization, but cannot be the late owner of visual/contact truth |
| Teleport spell | `dnd/spells/conjuration.py` | Commit spatial move, reduce perception before spell completion, then materialize navigation if required |
| Infernal/necromancy/enchantment queries | `dnd/spells/infernal.py`, `dnd/spells/necromancy.py`, `dnd/spells/enchantment.py` | Remove query-time perception mutation; retain only explicit navigation refresh when truly required |
| Scenario post-deployment refresh | `dnd/content/scenarios/scenario_deployment.py` | Entity deployment events own perception; retain at most one navigation-only materialization after the full roster is present |
| Entity action discovery | `dnd/entities/entity.py` | Consume current perception projection; lazily materialize navigation caches only |

### 14.3 Active test preservation ledger

| Test module | Capability to preserve or add |
|---|---|
| `tests/engine/test_senses_light_stealth.py` | Ordinary/special-sense semantics, darkness baseline characterization, invisibility source ownership, contact modes, object perceivability, replay deltas |
| `tests/engine/test_grid_pathfinding.py` | Subjective movement reads typed contact knowledge; Tile/center-object propagation differs explicitly from optics; open/closed doors invalidate nonvisual reach |
| `tests/engine/test_event_lifecycle.py` | Phase-store identity accumulation, final-location replacement, pre-completion children, terminal combat-log evidence, and final propagation facts with the existing changed hint |
| `tests/engine/test_direct_scenario_deployment.py` | Exactly one empty-to-full sensory delta for supported deployment |
| `tests/engine/test_standard_conditions.py` and `tests/engine/test_life_state_ownership.py` | Blinded/invisible/dead-state projection changes and source-owned restoration |
| `tests/engine/test_objective_state.py` | Objective state remains distinct from typed subjective contacts |
| `tests/engine/test_world_edge_identity_and_elevation.py` | Near-side boundary observability and shared XY optical topology without 3D ray logic |
| `tests/engine/test_action_discovery.py`, `tests/engine/test_entity_composition.py`, `tests/engine/test_items_inventory_equipment.py`, `tests/engine/test_manual_10_standard_conditions.py` | Replace tuple-valued fixture writes/assertions with typed contacts or the real sensory event/reducer boundary without weakening their original capability assertions |
| `tests/engine/test_spell_families.py` | Extract its unique visual/contact cases into collecting active engine modules before removing stale server/content imports; do not use its currently blocked collection as a migration gate |
| `tests/manual/test_12_perception_light_stealth_and_invisibility.py` | Preserve its unique carried-light movement, subscription-before-light-filter, reactive illumination, and stacked stealth/invisibility cases in collecting engine coverage |
| `tests/manual/test_137_sense_buff_spell_legacy_contract.py` | Preserve Darkvision/See Invisible/True Seeing source lifecycles, range, concentration independence, reactive deltas, and action-discovery effects in collecting engine coverage |
| `tests/manual/test_97_event_wire_contract.py` | Regenerate intentional public sensory and Tile/object optics/propagation fields; prove excluded Event observer-grant fields do not enter the generic objective wire |
| New active engine coverage beside these modules | Event/combat-log privacy outside Encounter, replacing reliance on the absent legacy manual subjective-observation test |

The existing failing natural-darkness assertion at line 154 is recorded as a
red baseline to characterize before Phase 1. The separately asserted adjacent
promotion is also not accepted as target behavior.

## 15. Completion definition

This preparation is complete when:

- ordinary physical sight and ordinary light use one topology authority;
- objective illumination is no longer confused with observer visibility or
  heavy obscurement;
- special senses are range-correct and produce the correct visual/contact kind;
- Tile and center-object propagation are explicit facts with complete mutation
  events, rather than inferred from legacy visual opacity;
- no range-free perceivability/bypass policy remains beside the exact observer
  resolver;
- spatial conditions own fog/darkness/light contributions through their
  existing lifecycle;
- `SpatialSensesSystem` is the one observer source of truth for live Senses,
  sensory events, and event/combat-log evidence;
- every perception-projection transition can be replayed from objective and
  sensory events, while navigation caches remain explicitly derived;
- event-time identity/location evidence is captured at the exact phase-store,
  pre-mutation, and pre-completion seams; the combat log derives terminal
  perceiver/reveal projection from those frozen facts and recorded children;
- eager light, spatial-condition, and observer work is bounded to active
  sources/candidates; optical and propagation query caches retain simple global
  lazy invalidation;
- the existing BaseItem/Tile/GridMap surface is clean through Phases 1–5, and
  the separately approved Tile/WorldItem/GridMap placement plan can then land
  without retaining duplicated vision/light authority.
