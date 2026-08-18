# Spatial-condition ownership and environmental-reaction recovery plan

Status: approved by two independent reviewers and three independent anti-slop
passes.

Date: 2026-08-18

This document supersedes the earlier wrapper-preserving version of the clean
spatial-reaction plan. It is based on the live code and on the committed
history immediately before and after the independent `SpatialEffect` owner was
introduced.

## 1. Objective

Recover the complete spatial-condition architecture as one condition system:

- one independently owned `SpatialCondition` instance carries identity,
  duration, mechanics, handlers, footprint, concealment, and cleanup;
- `GridMap` owns the active spatial-condition collection and its positional
  indexes;
- each covered `Tile` can enumerate the same condition instances through
  condition UUID references;
- concrete environmental surfaces, spell zones, auras, clouds, fields, and
  traps are authored subclasses of `SpatialCondition` or its area-condition
  bases;
- every engine object introduced by this cut remains a Pydantic model in the
  existing `BaseCondition` family; no dataclass state mirror or custom
  serialization layer is introduced;
- the existing position-indexed spatial-handler machinery remains the event
  dispatch mechanism; and
- the existing typed environmental-interaction rows remain the reaction
  authority after the deprecated global gateway is removed.

The migration collapses the current runtime pair:

```text
SpatialEffect(BaseBlock)
└── SpatialEffectController(BaseCondition)
```

into one independently owned condition:

```text
SpatialCondition(BaseCondition)
```

The independent owner capability is retained. The duplicate host object is
removed.

## 2. Historical baseline that must be preserved

### 2.1 Tile conditions and zone ownership

Commit `3fe2098` introduced the original zone model:

```text
caster condition
└── ZoneControlCondition
    ├── TileEffectCondition on tile A
    ├── TileEffectCondition on tile B
    └── TileEffectCondition on tile C
```

`ZoneControlCondition` was a `BaseCondition`. It owned the affected positions
and the linked Tile conditions. `BaseCondition.terrain_conditions` recorded the
exact `(tile_uuid, condition_uuid)` pairs so removing the controlling condition
removed the complete zone.

### 2.2 Position-indexed spatial handlers

Commit `26d6cd6` introduced the spatial-handler index. Its purpose was to
replace one handler per Tile with one handler per zone:

```text
(event type, event phase, position) -> handler
handler UUID -> indexed positions
```

The preserved APIs are:

```python
EventQueue.add_spatial_handler(...)
EventQueue.update_spatial_handler_positions(...)
EventQueue.remove_spatial_handler(...)
```

This gives position-local dispatch and delta footprint updates without scanning
all handlers or installing one handler for every Tile.

### 2.3 Mature pre-wrapper condition owner

At commit `4ebe523`, immediately before the wrapper architecture was added,
`ZoneControlCondition(BaseCondition)` already owned:

- geometry and affected positions;
- entry, exit, turn-start, and turn-end handlers;
- difficult-terrain modifiers;
- illumination and obscurement modifiers;
- Tile marker conditions for hazard, perception, and observation;
- duration and concentration linkage;
- movement of the complete zone; and
- cleanup of every modifier, handler, light, and Tile marker.

This is the condition-owned mechanics foundation to retain.

### 2.4 The physical spike-trap ownership gap

The pre-wrapper physical spike-trap factory did not have a complete owner. It
returned:

```python
tiles, shared_handler
```

A linked lever stored both `trap_handler_uuid` and `trap_tile_uuids`, removed
the handler, traversed the Tiles, and removed each marker independently.

That path had a real architectural gap: the trap network had no one UUID that
owned its footprint, handler, reveal state, and deactivation.

### 2.5 Independent `SpatialEffect` owner

Commit `e745f38` fixed independent ownership by introducing one
`SpatialEffect(BaseBlock)` per phenomenon. A trap lever could then retain one
owner UUID and retire that exact owner.

The same change moved the old zone condition into the new owner as its primary
controller. The owner and controller now duplicate positions, triggers,
lifecycle state, registries, and removal paths.

The target keeps the exact independent UUID and lifecycle introduced by this
commit while making the condition itself that owner.

## 3. Existing capability ledger

The migration must preserve all of the following live capabilities.

### 3.1 Generic condition capabilities

`BaseCondition` already owns:

- behavior identity and source attribution;
- effect origin;
- duration and expiration;
- modifiers on `ModifiableValue` instances;
- ordinary event handlers;
- position-indexed spatial handlers;
- subconditions and cross-block linked conditions;
- hazard filters and concealment DC;
- application and removal event lifecycles;
- provisional cleanup after rejected application; and
- cleanup of modifiers, handlers, child conditions, and registry identities.

### 3.2 Spatial owner capabilities

The live wrapper/controller pair additionally provides:

- one UUID for an independent spatial phenomenon;
- a multi-cell footprint;
- ground, cloud, and field occupancy;
- exclusive-transforming and overlapping admission;
- anchor policies for fixed, entity-attached, object-attached, and independently
  movable conditions;
- optional traversal blocking;
- APPEAR, ENTER, LEAVE, turn, movement, interaction, and removal triggers;
- first-per-turn trigger admission;
- difficult terrain, light, obscurement, memberships, damage, saves, and
  restraint mechanics;
- footprint movement and partial shrinkage;
- concealment and one-way reveal;
- complete retirement;
- same-condition arbitration by potency;
- typed environmental transitions; and
- recorded creation, footprint, reveal, transform, and removal facts.

### 3.3 Environmental-reaction capabilities

The live definitions contain:

- six typed interaction operations;
- three typed transition actions;
- fourteen authored transition rows;
- intensity admission with strongest applicable row selection;
- partial-cell transitions;
- exact replacement materialization;
- secondary cloud creation;
- delayed dispersal; and
- handler reindexing after footprint changes.

### 3.4 Spatial-handler capabilities

The EventQueue already provides:

- O(1) position-indexed lookup;
- one handler invocation per effect UUID for a multi-cell interaction;
- handler UUID deduplication;
- footprint delta updates; and
- removal from every positional index by handler UUID.

These APIs and their dispatch implementation remain the spatial execution
foundation.

## 4. Current duplication to remove

One live fire surface currently has two Pydantic engine objects:

```text
FireGroundEffect
└── FireSurfaceController
```

| State or behavior | `SpatialEffect` host | controller condition |
|---|---:|---:|
| runtime UUID | yes | yes |
| source identity | yes | yes |
| affected positions | yes | yes |
| trigger set | yes | yes |
| active registry | effect registry | condition registry |
| lifecycle | created/changed/retired | applied/removed/expired |
| duration | retirement countdown | condition duration |
| handler cleanup | host handlers | owned condition handlers |
| removal | `retire()` | condition removal |

`SpatialEffect.install_controller()` assigns the host UUID to the controller's
`target_entity_uuid`, applies the controller as a condition on the host, and
retires the host when that condition is removed. The target is not an entity;
the host exists mainly to satisfy the single-BaseBlock condition-ownership
shape.

The migration removes this duplication rather than adding a third facade.

## 5. Target ownership model

### 5.1 One independent spatial condition

Add one base in the active spatial package:

```python
class SpatialCondition(BaseCondition):
    content_ref: ContentRef
    faction: str | None
    position: tuple[int, int]
    affected_positions: set[tuple[int, int]]
    layer: SpatialEffectLayer
    occupancy_policy: SpatialEffectOccupancyPolicy
    anchor_kind: SpatialEffectAnchorKind
    anchor_uuid: UUID | None
    blocking_policy: SpatialEffectBlockingPolicy
    trigger_kinds: frozenset[SpatialEffectTriggerKind]
    first_per_turn_trigger_kinds: frozenset[SpatialEffectTriggerKind]
    arbitration_potency: int
```

The existing enum vocabulary is retained for this migration so this ownership
cut does not become a protocol-wide naming rewrite.

The wrapper-era `SpatialEffectLifetimePolicy` is not part of that retained
vocabulary. The inherited Pydantic `Duration` is the single lifetime value:
`DurationType.PERMANENT` represents explicit removal, while the existing timed
duration variants represent expiry.

`SpatialCondition` is independently owned. It is not inserted as an active
condition on an artificial `BaseBlock`. Its inherited condition fields own its
duration, modifiers, handler UUIDs, linked conditions, source, origin, hazard,
concealment, application state, and cleanup.

The spatial subclass adds only the information required to attach the condition
to world positions, retain the existing authored identity/faction, and arbitrate
two exact matching exclusive surfaces. Its arbitration rank remains the
existing `(arbitration_potency, effective_spell_level)` tuple; it is not a new
priority system.

The condition also directly implements the three world queries previously
inherited by the deleted `BaseBlock` host:

```python
condition.blocks_walking_at(position, requesting_entity_uuid, mode)
condition.is_hazardous_for(entity_uuid)
condition.is_perceivable_by(observer_uuid)
```

These methods use the existing blocking policy, `hazard_filter`,
`condition_stealth_dc`, faction/source rules, and observer passive perception.
GridMap calls them on the exact indexed condition. No generic capability probe
or copied hazard/perception state is introduced.

### 5.2 GridMap owns the collection and indexes

`GridMap` owns the active collection by condition UUID:

```python
_spatial_conditions: dict[UUID, BaseCondition]
_spatial_condition_positions: dict[UUID, set[tuple[int, int]]]
_spatial_condition_layers: dict[UUID, SpatialEffectLayer]
```

The position-to-condition index is stored on the actual Tile, described below.
GridMap therefore retains only the collection and the reverse mapping required
to remove, move, and advance one complete condition efficiently.

GridMap remains type-unaware. Its low-level methods accept the condition UUID,
layer, occupancy policy, and positions. It does not import concrete spatial
conditions or authored content.

The inherited `BaseObject` registry remains UUID identity lookup. It does not
mean that a condition is active in the world. GridMap collection membership is
the sole authority that an independent spatial condition is active, and the
Tile memberships are its positional index. No second active-effect registry is
kept.

### 5.3 Tile exposes one condition concept

Each Tile stores spatial-condition membership UUIDs grouped by the existing
spatial layer:

```python
_spatial_condition_uuids: dict[
    SpatialEffectLayer,
    set[UUID],
]
```

GridMap is the only writer of this index.

Tile exposes one public condition query that resolves:

- conditions directly owned by the Tile; and
- independently owned spatial conditions whose footprint includes the Tile.

The public result is UUID-keyed so two independently owned conditions with the
same display name remain distinguishable:

```python
def get_conditions(self) -> dict[UUID, BaseCondition]: ...
```

`tile.active_conditions` continues to mean conditions whose lifecycle is
directly owned by the Tile. `tile.get_conditions()` is the complete set of
conditions currently affecting that cell.

The query resolves UUIDs to the existing Pydantic condition instances; it does
not build a condition-state DTO or copy. A Tile reference that cannot resolve
to the exact condition in GridMap's active collection is an invariant failure,
not an entry to silently skip.

No cached `tile.is_wet` or `tile.on_fire` booleans are introduced. Wetness,
fire, clouds, fields, traps, and spell areas are exact conditions returned by
this query.

### 5.4 One write path for a footprint

`SpatialCondition` calls one GridMap operation when its footprint is installed
or changed:

```python
grid.set_spatial_condition_positions(
    condition_uuid=self.uuid,
    layer=self.layer,
    occupancy_policy=self.occupancy_policy,
    positions=positions,
)
```

That operation:

1. validates every target Tile;
2. validates occupancy against the affected Tiles;
3. removes the condition UUID from Tiles no longer covered;
4. adds the UUID to newly covered Tiles;
5. replaces the reverse `condition UUID -> positions` entry; and
6. leaves retained Tile references untouched.

Removal performs the inverse through one GridMap call.

### 5.5 Independent-condition removal linkage

`BaseCondition.linked_conditions` already owns cross-object child cleanup. Its
first UUID is broadened from "target BaseBlock UUID" to "runtime owner UUID".

The existing `BaseBlock._discard_uncommitted_condition_tree()` and
`BaseBlock._remove_condition_tree()` algorithms stay in place for every
ordinary block-owned condition. Their linked-child branch gains one narrow
fallback: when the first UUID does not resolve to a BaseBlock, resolve the exact
child condition and call its independently-owned committed or uncommitted
removal hook. `SpatialCondition` implements those two hooks through its own
GridMap/Tile ownership.

`SpatialCondition` locally performs the same finite cleanup inventory for its
own tree: same-owner subconditions, linked conditions, reverse parent
notification, owned actions, its GridMap/Tile membership, and registry
identity. Its ordinary removal calls `cleanup_own_state()` exactly once, so
modifiers and ordinary/spatial handlers are not removed a second time. Its
uncommitted path calls `discard_uncommitted_runtime_state()` exactly once before
discarding the remaining tree. No general condition traversal is rewritten,
and no owner protocol, global resolver, registry, or event path is added.

This allows concentration and other parent conditions to own a spatial
condition directly:

```python
concentration.add_linked_condition(zone.uuid, zone.uuid)
```

It uses the existing condition dependency tree and does not create a parallel
spatial-lifetime registry.

An independently removed spatial condition retains the existing parent-link
notification rules where those rules are authored.

`Concentrating.drop_slot()` is an explicit caller of the same linked-child
operation. It no longer stops after a failed `BaseBlock.get(owner_uuid)` lookup,
so dropping one slot can remove its exact independently owned spatial condition
without affecting another concentration slot.

## 6. Target runtime lifecycle

### 6.1 Construction

Content construction creates the final concrete `SpatialCondition` directly.
There is no separately materialized host and no controller installation call.

Construction sets:

- source identity;
- behavior/content identity retained by the current content migration;
- position and authored geometry;
- layer and occupancy;
- anchor policy;
- duration;
- trigger sets;
- condition-specific mechanics; and
- the frozen authored environmental-transition rows.

### 6.2 Activation

One `SpatialCondition.activate(parent_event=...)` path performs:

1. reject a second activation of the same instance;
2. compute or validate the intended footprint;
3. preflight Tile existence and resolve exclusive-layer admission through
   GridMap;
4. retain stronger same-identity incumbents and identify exact cells displaced
   from weaker or equal same-identity incumbents;
5. reject a different exclusive identity unless an authored transition selected
   that replacement;
6. enter the inherited condition application lifecycle over the admitted final
   footprint;
7. inside the condition's `_apply()` boundary, install its mechanics, perform
   the validated GridMap swap, and apply the incumbent footprint delta before
   returning the application EFFECT event;
8. register the environmental-interaction spatial handler inside that same
   `_apply()` boundary when transition rows exist;
9. register anchor-following behavior inside that same boundary when an anchor
   exists;
10. allow `BaseCondition.apply()` to publish the completed condition
   application only after the world swap and mechanics have succeeded;
11. publish the existing incumbent transformation and spatial creation facts;
   and
12. run the authored APPEAR behavior once against occupants of the committed
   footprint.

The spatial condition's local uncommitted-tree path is responsible for
modifiers, ordinary handlers, spatial handlers, subconditions, linked
conditions, owned actions, any provisional GridMap membership, and registry
identities when condition application is rejected or raises.

GridMap completes all occupancy and displacement validation before condition
mechanics are installed. The admitted footprint is final before `_apply()` can
install positional mechanics. Invalid or completely rejected footprints
therefore do not require an EventQueue transaction or event rollback mechanism.

An incoming condition does not change an installed incumbent before entering
its accepted `_apply()` work. Inside that existing application boundary,
GridMap performs the already validated index swap and the incumbent condition
applies the corresponding footprint delta. An exception restores the captured
incumbent footprints and positional mechanics and invokes the incoming
condition's local uncommitted-tree cleanup. Because `_apply()` has not returned
an EFFECT event, `BaseCondition.apply()` cannot publish a false completed
application. This is local restoration of the two condition footprints; it is
not an EventQueue transaction or general rollback framework.

### 6.3 Footprint change

One condition owns the mechanics and indexed footprint. A change computes:

```text
removed = old - new
retained = old & new
added = new - old
```

The condition then:

1. validates the new footprint;
2. removes terrain, light, membership, and other positional state from removed
   cells;
3. updates existing spatial handlers through
   `EventQueue.update_spatial_handler_positions`;
4. commits Tile membership and the reverse index through GridMap;
5. adds positional mechanics to added cells;
6. applies effect-leaves-occupant and effect-enters-occupant behavior where
   authored; and
7. publishes the existing footprint-change fact.

There is no second controller footprint to synchronize.

### 6.4 Duration advancement

Encounter's existing environment step obtains each active spatial condition
once from GridMap. It advances the inherited `Duration` once per completed
round. An expired condition follows the same deactivation path as explicit
removal.

The existing shortest admitted delayed retirement rule remains condition-owned.
`DISPERSE` shortens the condition's remaining `Duration` to four or one round
only when that deadline is earlier than its current expiry. It does not install
a second countdown condition or add a parallel timer state.

### 6.5 Deactivation

One `SpatialCondition.deactivate(...)` path:

1. runs `cleanup_own_state()` once, including the existing condition-removal
   lifecycle, subclass `_remove()`, modifiers, light state, and ordinary and
   spatial handlers;
2. removes same-owner subconditions, occupant memberships, linked conditions,
   reverse parent links, and condition-owned actions through the local tree
   path;
3. removes the condition UUID from every covered Tile and GridMap reverse
   index;
4. publishes the existing spatial removal fact with the previous footprint;
5. removes the condition from the GridMap collection; and
6. removes its condition registry identity.

Lever deactivation, concentration loss, duration expiry, environmental
transformation, anchor destruction, and explicit removal all call this path.

## 7. Condition hierarchy after migration

```text
BaseCondition
└── SpatialCondition
    ├── AreaCondition
    │   ├── MembershipAreaCondition
    │   └── RestrainingAreaCondition
    ├── WetSurface
    ├── FireSurface
    ├── IceSurface
    ├── ElectrifiedWater
    ├── SteamCloud
    ├── OilSurface
    ├── BurningWeb
    └── SpikeTrap
```

Concrete spell zones, auras, clouds, and fields subclass the smallest relevant
area-condition base. Their existing mechanics move from controller subclasses
without behavioral redesign.

The current `GroundEffect`, `CloudEffect`, and `FieldEffect` host classes are
replaced by the condition's existing `layer` and `occupancy_policy` fields.

## 8. Complete authored spatial-condition inventory

All 31 current spatial definitions receive an explicit migration disposition.

### 8.1 Environmental and physical conditions

| Current authored identity | Target condition |
|---|---|
| `spatial_effect.material.fire` | `FireSurface` |
| `spatial_effect.material.steam` | `SteamCloud` |
| `spatial_effect.material.ice` | `IceSurface` |
| `spatial_effect.material.electrified_water` | `ElectrifiedWater` |
| `spatial_effect.material.water_surface` | `WetSurface` |
| `spatial_effect.spell.web.burning` | `BurningWeb` |
| `spatial_effect.material.oil` | `OilSurface` |
| `spatial_effect.environment.spike_trap` | `SpikeTrap` |

### 8.2 Ground and restraint spell conditions

| Current authored identity | Target condition |
|---|---|
| `spatial_effect.spell.grease` | `GreaseZone` |
| `spatial_effect.spell.web` | `WebZone` |
| `spatial_effect.spell.spike_growth` | `SpikeGrowthZone` |
| `spatial_effect.spell.ice_storm` | `IceStormTerrain` |
| `spatial_effect.spell.entangle` | `EntangleZone` |
| `spatial_effect.spell.evards_black_tentacles` | `BlackTentaclesZone` |

### 8.3 Cloud conditions

| Current authored identity | Target condition |
|---|---|
| `spatial_effect.spell.fog_cloud` | `FogCloudZone` |
| `spatial_effect.spell.cloudkill` | `CloudkillZone` |
| `spatial_effect.spell.incendiary_cloud` | `IncendiaryCloudZone` |
| `spatial_effect.spell.stinking_cloud` | `StinkingCloudZone` |

### 8.4 Fields and auras

| Current authored identity | Target condition |
|---|---|
| `spatial_effect.spell.spirit_guardians` | `SpiritGuardiansZone` |
| `spatial_effect.spell.guardian_of_faith` | `GuardianOfFaithZone` |
| `spatial_effect.trait.leadership` | `LeadershipAura` |
| `spatial_effect.class_feature.draconic_presence` | `DraconicPresenceAura` |
| `spatial_effect.spell.darkness` | `DarknessZone` |
| `spatial_effect.spell.daylight` | `DaylightZone` |
| `spatial_effect.spell.insect_plague` | `InsectPlagueZone` |
| `spatial_effect.spell.sleet_storm` | `SleetStormZone` |
| `spatial_effect.spell.silence` | `SilenceZone` |
| `spatial_effect.spell.gust_of_wind` | `GustOfWindZone` |
| `spatial_effect.spell.globe_of_invulnerability` | `GlobeZone` |
| `spatial_effect.spell.antimagic_field` | `AntimagicFieldZone` |
| `spatial_effect.spell.continual_flame` | `ContinualFlame` |

No definition is silently dropped when the wrapper hierarchy is deleted.

## 9. Spike trap as the first vertical slice

Spike trap proves the independent owner without relying on caster ownership.

Replace:

```text
SpikeTrapGroundEffect
└── SpikeTrapController
```

with:

```text
SpikeTrap(SpatialCondition)
```

The condition directly owns:

- the complete trap-network footprint;
- one entry handler covering all trap cells;
- `2d4` piercing damage per committed entered cell;
- hazard policy;
- concealment DC;
- one-way complete-network reveal;
- footprint extension;
- the interaction handler when authored;
- deactivation; and
- cleanup.

The trap lever stores `trap_condition_uuid` and calls the ordinary independent
condition removal path. The authored arena record stores
`spike_condition_uuid`. Tile queries return the same trap condition at every
covered position. The old `trap_effect_uuid` and `spike_effect_uuid` field names
are removed in the same cut without aliases.

The vertical-slice gate preserves:

- one owner UUID;
- one shared entry handler;
- damage for every committed movement step;
- lethal-step movement termination;
- hidden-hazard perception;
- exactly one complete-network reveal;
- footprint extension;
- exact lever linkage; and
- complete handler and Tile-reference cleanup.

## 10. Occupant memberships remain conditions

The existing source-owned membership idea remains, but its owner is the spatial
condition UUID rather than a wrapper UUID.

For Wet:

```text
WetSurface spatial condition
└── exact source membership on occupant
    └── public Wet condition on occupant
```

Every object in this chain is a condition. The source membership preserves the
existing rule that leaving one wet source does not remove Wet while another
wet source still applies.

The same ownership pattern remains for restraint, aura, protection, and other
occupant-facing manifestations.

Rename source fields that explicitly encode the deleted host concept, such as
`source_effect_uuid`, to `source_spatial_condition_uuid` in the same hard cut.

## 11. Tile materials and spatial conditions

Tile material composition and spatial conditions are related but not parallel
state systems.

The Tile owns durable physical composition:

```text
base material + ordered material layers
```

The Tile condition query exposes active mechanics such as Wet Surface, Fire,
Steam, Darkness, Web, or a trap.

An environmental interaction can therefore:

1. read the Tile's durable material layers;
2. read the exact spatial conditions covering that Tile;
3. mutate durable material layers through the GridMap Tile-mutation path when
   an authored rule changes the physical surface; and
4. add, replace, shrink, or remove spatial conditions through the spatial
   condition lifecycle.

The fourteen currently authored rows operate on spatial conditions. Material
layer reactions such as grass becoming charred are added only when their exact
Tile material rules are authored; they use the same interaction event and do
not introduce a second effect system.

## 12. Existing event and handler boundary

The existing EventQueue remains the event-phase and handler-dispatch authority.
This migration does not introduce an EventQueue transaction, callback rewrite,
late-child mechanism, condition-event replacement, or reducer framework.

The existing event shapes remain the recorded boundary during this ownership
cut:

```text
SpatialEffectInteractionEvent DECLARATION
  -> EXECUTION
  -> EFFECT
       -> condition mechanics and existing spatial change facts
  -> COMPLETION
```

`SpatialEffectChangeEvent` continues to record creation, footprint change,
reveal, transformation, and removal. Its `spatial_effect_uuid` identifies the
single `SpatialCondition` runtime owner after migration. Event vocabulary can
be renamed only with the later external API/client contract migration; no
alias, parallel event, or compatibility facade is added here.

Condition application/removal events retain their existing role in condition
mechanics. Spatial change events retain their existing role in recording world
footprint state. Both refer to the same condition UUID and remain causally
linked through the existing parent event.

## 13. Environmental transition ledger

Intensity order remains `MINOR < MODERATE < STRONG`. For one operation, the
admitted row with the greatest minimum intensity wins.

| Existing condition | Operation | Minimum | Action | Result |
|---|---|---|---|---|
| Fire Surface | `DOUSE` | `MINOR` | `REMOVE_AFFECTED` | affected fire cells disappear |
| Ice Surface | `VAPORIZE` | `MINOR` | `REMOVE_AFFECTED_AND_CREATE_SECONDARY` | Steam Cloud |
| Electrified Water | `FREEZE` | `MINOR` | `REPLACE_AFFECTED` | Ice Surface |
| Electrified Water | `VAPORIZE` | `MINOR` | `REMOVE_AFFECTED_AND_CREATE_SECONDARY` | Steam Cloud |
| Wet Surface | `FREEZE` | `MINOR` | `REPLACE_AFFECTED` | Ice Surface |
| Wet Surface | `ELECTRIFY` | `MINOR` | `REPLACE_AFFECTED` | Electrified Water |
| Wet Surface | `VAPORIZE` | `MINOR` | `REMOVE_AFFECTED_AND_CREATE_SECONDARY` | Steam Cloud |
| Burning Web | `DOUSE` | `MINOR` | `REMOVE_AFFECTED` | affected fire cells disappear |
| Oil Surface | `IGNITE` | `MINOR` | `REPLACE_AFFECTED` | Fire Surface |
| Web Surface | `IGNITE` | `MINOR` | `REPLACE_AFFECTED` | Burning Web |
| Fog Cloud | `DISPERSE` | `MODERATE` | `REMOVE_AFFECTED` | affected fog cells disappear |
| Cloudkill | `DISPERSE` | `STRONG` | `REMOVE_AFFECTED` | affected cloud cells disappear |
| Stinking Cloud | `DISPERSE` | `MODERATE` | `REMOVE_AFFECTED` | removal after 4 rounds |
| Stinking Cloud | `DISPERSE` | `STRONG` | `REMOVE_AFFECTED` | removal after 1 round |

All six operations remain typed and tested: `IGNITE`, `DOUSE`, `FREEZE`,
`ELECTRIFY`, `VAPORIZE`, and `DISPERSE`.

## 14. Direct reaction binding

Each concrete spatial condition receives its authored frozen transition tuple
at direct construction. The condition installs one interaction handler over
its footprint when that tuple is nonempty.

The handler receives the live `SpatialEffectInteractionEvent` and calls one
stateless transition function directly:

```python
def apply_spatial_interaction(
    *,
    condition: SpatialCondition,
    event: SpatialEffectInteractionEvent,
    transitions: tuple[SpatialEffectTransitionDefinition, ...],
    build_replacement: Callable[..., SpatialCondition],
) -> None: ...
```

The function:

1. intersects event positions with the condition footprint;
2. selects rows matching the operation;
3. admits rows at or below the event intensity;
4. selects the greatest admitted minimum intensity;
5. returns when no cells or rows are admitted;
6. applies the shortest delayed removal when a row specifies a delay;
7. retains untouched cells on a partial transition;
8. directly constructs the replacement condition when required;
9. activates that replacement on the exact intersected cells while naming the
   original condition as the authorized incumbent it replaces;
10. lets the activation path shrink or deactivate the original only after the
    incoming condition applies successfully; and
11. parents existing spatial change facts to the interaction EFFECT event.

The function receives the real event. It does not copy it into another context
model and does not call a process-installed gateway.

## 15. Replacement order

A replacement-producing transition uses this order:

1. resolve the existing authored replacement row;
2. construct the concrete replacement with source from the interaction event,
   faction from the replaced condition, anchor policy from the replacement's
   authored definition, duration from the interaction, exact intersected cells,
   and the interaction EFFECT event as causal parent;
3. validate its intended exact cells and occupancy;
4. activate the replacement once while passing the original condition UUID as
   the exact admitted replacement owner;
5. let that activation shrink or deactivate the original condition inside the
   application boundary described in Section 6.2; and
6. allow that condition's ordinary activation to register handlers, publish its
   creation fact, and run APPEAR behavior.

Construction failure removes only the unactivated replacement condition from
the condition registry. Rejected or failed incoming application uses the
spatial condition's local uncommitted-tree cleanup and leaves the original
installed.
Failure during the validated footprint swap restores the original footprint
and mechanics before spatial change facts publish.

This local preparation does not add an EventQueue rollback or transaction
layer.

## 16. Dependency map

```text
dnd/types/spatial_effects.py
  [-> enum]
  [<- GridMap, events, spatial conditions, authored definitions]
  existing spatial enum vocabulary

dnd/core/base_conditions.py
  [-> core values/events, dnd/types]
  [<- BaseBlock, spatial conditions, authored conditions]
  generic mechanics, duration, cleanup
  narrow independent-owner removal hook

dnd/core/base_tiles.py
  [-> BaseBlock, BaseCondition registry, dnd/types]
  [<- GridMap and map construction]
  direct Tile conditions
  spatial-condition UUID membership
  complete condition query

dnd/core/gridmap.py
  [-> Tile, BaseBlock/BaseCondition, events, dnd/types]
  [<- spatial conditions, encounter, actions, senses]
  active spatial-condition collection
  condition UUID -> positions/layer
  Tile membership writes and positional queries

dnd/core/events/world_events.py
  [-> event registry, dnd/types, current content identity leaf]
  [<- EventQueue, spatial conditions, actions, items, spells, reducers]
  existing spatial interaction and change facts

dnd/spatial/area_conditions.py                    NEW
  [-> BaseCondition, GridMap, EventQueue, geometry, dnd/types]
  [<- environmental conditions, spell zones, auras]
  SpatialCondition
  AreaCondition
  activation, movement, deactivation
  terrain/light/handler ownership

dnd/spatial/memberships.py                        MIGRATED
  [-> area_conditions, BaseCondition, Entity]
  [<- wet surfaces, auras, restraint conditions]
  exact source memberships

dnd/spatial/restraints.py                         MIGRATED
  [-> memberships, actions, Entity]
  [<- Web, Entangle, Black Tentacles]
  restraint and escape ownership

dnd/spatial/environmental_conditions.py           NEW
  [-> area_conditions, memberships, core events/types]
  [<- direct authored builders]
  Wet, Fire, Ice, Oil, Steam, Electrified Water, Burning Web, Spike Trap

dnd/spatial/transitions.py                        NEW
  [-> area_conditions, world event, transition definitions]
  [<- direct authored construction]
  stateless fourteen-row transition execution

dnd/content/spatial_effect_recipes.py             CURRENT AUTHORED DEFINITIONS
  [-> current authored definitions, concrete conditions]
  [<- direct condition construction]
  31 authored definitions and fourteen transition rows

dnd/content/spatial_effect_materialization.py     MIGRATED
  [-> authored definitions, concrete spatial conditions]
  [<- spells, items, scenarios, tests]
  direct condition construction and transition binding
```

Core modules do not import `dnd.spatial` or authored content. Spatial modules
depend downward on core. Authored content depends on spatial implementations.

No late imports, `TYPE_CHECKING` cycle masks, `getattr` capability probes, or
compatibility re-export modules are part of the target.

## 17. Production caller migration ledger

| Current caller family | Direct target |
|---|---|
| spell casts constructing host + controller | construct and activate one concrete spatial condition |
| environmental materializers | construct and activate one environmental condition |
| spike-trap materializer | construct and activate `SpikeTrap` |
| trap lever and arena record | rename the owner fields to `trap_condition_uuid` / `spike_condition_uuid`, then retain and deactivate the spatial condition UUID |
| Oil Barrel destruction | publish `IGNITE` against indexed conditions |
| torch/flame behavior | publish `IGNITE` against indexed conditions |
| wind spells | publish `DISPERSE` against indexed conditions |
| Sleet Storm | publish/consume the existing dousing interaction |
| concentration | link directly to independently owned condition UUID |
| `Concentrating.drop_slot()` | remove the exact linked BaseBlock-owned or independently owned condition through the shared linked-child operation |
| anchored auras and fields | move the condition footprint from authoritative anchor movement events |
| GridMap hazard queries | inspect Tile's complete condition set |
| GridMap movement/blocker queries | call indexed conditions' direct per-position blocking and perceivability methods |
| senses and perception | inspect condition hazard/concealment through Tile query |
| Encounter environment step | advance each GridMap spatial condition once |
| combat log and subjective projection | consume existing interaction/change facts |
| runtime reset | clear GridMap condition collection, Tile references, condition registry, and handlers |

Every active `materialize_spatial_effect`, `install_controller`,
`install_default_controller`, `SpatialEffect.get_effect`,
`get_spatial_effect_uuids_at`, and `get_spatial_effect_blocks_at` caller is
removed or migrated before the old symbols are deleted.

## 18. Implementation sequence

### Phase 0 — Freeze the capability ledger

1. pin the 31 authored definitions;
2. pin the fourteen transition rows and six operations;
3. inventory every wrapper/controller class and construction caller;
4. inventory every direct `SpatialEffect` lookup and GridMap effect query;
5. pin canonical interaction/change event JSON;
6. pin the spatial-handler add/update/remove behavior;
7. pin Tile-owned condition duration and hazard behavior from the historical
   and current tests; and
8. map every current spatial test to a target capability rather than an old
   class shape.

Gate: every current spatial owner, caller, event consumer, and valuable test has
one recorded target.

### Phase 1 — Independent spatial-condition foundation

1. add `SpatialCondition` and `AreaCondition` without migrating authored
   consumers;
2. add GridMap's condition collection and reverse position/layer indexes;
3. add Tile's spatial-condition UUID memberships and complete condition query;
4. add the one-write GridMap footprint operation;
5. add the narrow independent condition removal hook used by existing linked
   condition cleanup;
6. add the narrow independent-child fallback to BaseBlock's existing linked
   cleanup branches without moving its tree algorithms;
7. add SpatialCondition's explicit committed and uncommitted local tree
   cleanup, removing every artifact exactly once;
8. migrate `Concentrating.drop_slot()` to the same linked-child fallback;
9. add direct condition activation, footprint change, duration advancement,
   and deactivation;
10. use the existing EventQueue spatial-handler APIs; and
11. add architecture tests for the dependency arrows in Section 16.

Gate: a minimal test spatial condition can activate across multiple Tiles,
appear in every Tile query, use one spatial handler, move by delta, expire, and
fully disappear without a `SpatialEffect` host.

### Phase 2 — Spike-trap vertical slice

1. migrate `SpikeTrapGroundEffect + SpikeTrapController` into one
   `SpikeTrap(SpatialCondition)`;
2. migrate direct spike-trap construction;
3. preserve one shared entry handler;
4. preserve hidden hazard and one-way whole-network reveal;
5. preserve footprint extension;
6. migrate lever linkage to the condition UUID;
7. change Tile assertions from absent `active_conditions` to present complete
   Tile condition queries; and
8. preserve existing spatial change and combat-log facts.

Gate: the complete spike-trap capability ledger in Section 9 passes through the
single-condition path and uses no wrapper/controller object.

### Phase 3 — Shared area mechanics

1. move geometry, trigger admission, terrain modifiers, illumination,
   obscurement, spatial-handler ownership, and footprint movement from
   `AreaSpatialEffectController` into `AreaCondition`;
2. remove the host lookup and controller footprint copy;
3. migrate source-owned memberships;
4. migrate restraint and escape ownership;
5. migrate attached anchor movement; and
6. verify condition cleanup for partial movement, early removal, and expiry.

Gate: shared area behavior has one condition owner and no reference to a
primary controller or effect host.

### Phase 4 — Environmental conditions and reactions

1. migrate Wet Surface, Fire, Ice, Electrified Water, Steam, Oil, and Burning
   Web into direct conditions;
2. preserve Wet source arbitration and occupant manifestations;
3. bind the fourteen existing transition rows directly to constructed
   conditions;
4. add the stateless direct transition function;
5. preserve partial, complete, replacement, secondary, and delayed reactions;
6. preserve APPEAR behavior for Ice, Electrified Water, and Steam;
7. preserve handler footprint reindexing; and
8. migrate active interaction producers without changing EventQueue dispatch.

Gate: every transition row executes through direct condition binding with the
live interaction event and no gateway.

### Phase 5 — Spell zones, clouds, fields, and auras

Migrate all remaining definitions in Section 8 in bounded families:

1. ground and restraint spells;
2. clouds;
3. fixed fields;
4. entity-anchored auras;
5. object-anchored and independently movable conditions; and
6. protection/suppression fields.

For each family:

1. construct one concrete spatial condition;
2. activate it directly;
3. link concentration or other lifetime owners directly to its condition UUID;
4. preserve exact triggers, first-per-turn fences, memberships, actions,
   modifiers, movement, and cleanup;
5. replace wrapper registry lookups with condition registry/GridMap queries;
6. run the family's focused tests before beginning the next family; and
7. remove the migrated wrapper/controller construction path immediately.

Gate: all 31 authored definitions use direct spatial conditions.

### Phase 6 — Runtime hard cut

After every caller and test is migrated:

1. delete `SpatialEffect`;
2. delete `GroundEffect`, `CloudEffect`, and `FieldEffect`;
3. delete `SpatialEffectController`;
4. delete the primary-controller UUID and effect registry;
5. delete host/controller footprint synchronization;
6. delete `install_controller` and `install_default_controller`;
7. delete GridMap's old effect indexes and queries;
8. delete the process-installed spatial interaction gateway and copied context;
9. delete `SpatialEffectLifetimePolicy`,
   `SpatialEffectDefinition.lifetime_policy`, and every recipe assignment to
   that dead wrapper/controller policy;
10. rename `trap_effect_uuid` and `spike_effect_uuid` directly to their
    condition-owner names with no aliases;
11. delete deprecated registry transition executors/materializers; and
12. remove all active imports of the deleted symbols.

Gate: repository symbol search finds no active runtime wrapper/controller path.

### Phase 7 — Verification and architecture closure

1. run focused condition, GridMap, spatial-handler, trap, reaction, restraint,
   zone-spell, aura, light, hazard, event, projection, and reset tests;
2. run the exact collect-only gate described by `HOW_TO_TEST.md`;
3. run the broader suite allowed by the current repository migration state;
4. assert fresh-process construction without deprecated bootstrap;
5. assert no forbidden core-to-spatial/content imports;
6. assert all 31 definitions and fourteen rows remain enumerated; and
7. assert deleted symbols cannot be imported.

Gate: behavior and dependency tests pass with one condition concept.

## 19. Capability test ledger

### 19.1 Condition ownership and Tile visibility

- one condition UUID covers multiple Tiles;
- every covered Tile returns that exact instance from its complete condition
  query;
- directly Tile-owned and spatially referenced conditions coexist;
- two same-name overlapping conditions remain distinct by UUID;
- moving a condition updates removed/retained/added Tile references exactly;
- removing a condition clears every Tile reference;
- duration advances once per condition, not once per covered Tile; and
- linked parent condition removal deactivates the independent condition;
- full concentration removal, single-slot removal, multi-slot targeted removal,
  oldest-slot replacement, and reverse child removal preserve exact ownership;
- failed independent activation removes every provisional child and linked
  condition; and
- failed displacement/replacement leaves the complete incumbent state active.

### 19.2 Spatial handlers

- one entry handler covers a multi-cell zone;
- one event crossing one indexed cell invokes it once;
- one multi-cell interaction invokes one handler per condition UUID;
- footprint change reindexes by delta;
- removal clears all positional handler entries; and
- ordinary global handlers continue to receive spatial events as they do now.

### 19.3 Spike trap

- exact independent owner UUID;
- shared handler across the complete network;
- damage for each committed entered cell;
- lethal entry stops remaining movement;
- hazard filtering and concealment;
- whole-network reveal exactly once;
- reveal veto/retry and reentrancy behavior already covered by current tests;
- footprint extension;
- exact lever deactivation; and
- complete cleanup and reset.

### 19.4 GridMap condition capabilities

- blocking policies `NONE`, `ANCHOR`, and complete-footprint retain exact
  per-cell behavior;
- Guardian of Faith blocks only its authored anchor cell;
- hidden hazards are excluded from subjective safe-path avoidance until
  perceived;
- objective hazard queries remain exact for `ALL`, `NON_SOURCE`, and `ENEMIES`;
- blocker identification returns the condition's name; and
- reveal changes perceivability without copying state onto the Tile.

### 19.5 Environmental transitions

- all fourteen rows;
- strongest admitted intensity;
- unsupported operation;
- below-threshold intensity;
- partial intersection;
- complete removal;
- replacement and secondary creation;
- exact replacement source, anchor, faction, positions, duration, and parent;
- handler reindex after partial transition;
- Fog and Cloudkill intensity thresholds;
- Stinking Cloud shortest delayed removal;
- Ice, Electrified Water, and Steam APPEAR behavior;
- failed replacement construction preserving the installed original; and
- failed condition activation cleaning provisional mechanics.

### 19.6 Memberships and restraints

- Wet remains while any exact source membership remains;
- leaving one Wet source removes only that source;
- Freedom of Movement interactions remain unchanged;
- Web, Entangle, and Black Tentacles retain exact restraint source ownership;
- overlapping restraint strength arbitration remains unchanged;
- escape actions remain owned and cleaned by their exact condition; and
- effect movement applies entry/exit membership changes exactly once.

### 19.7 Spell zones and auras

Preserve focused behavior for:

- Grease;
- Cloudkill;
- Spirit Guardians;
- Spike Growth;
- Gust of Wind;
- Insect Plague;
- Incendiary Cloud;
- Web;
- Entangle;
- Black Tentacles;
- Fog Cloud;
- Stinking Cloud;
- Sleet Storm;
- Darkness and Daylight;
- Silence;
- Globe of Invulnerability;
- Antimagic Field;
- Guardian of Faith;
- Leadership;
- Draconic Presence; and
- Continual Flame.

### 19.8 Events and projection

- interaction event JSON remains canonical;
- creation, footprint, reveal, transform, and removal facts retain complete
  geometry;
- combat logs retain source, operation, condition identity, and positions;
- subjective projection receives the same observable world facts;
- parent UUIDs retain causal linkage to the producing action/interaction; and
- no state reconstruction requires a server-only registry or deprecated
  content gateway.

## 20. Scope fences

This plan changes the spatial owner model and directly related callers. Its
accepted implementation surface consists of:

- condition-owned spatial lifecycle;
- GridMap/Tile condition indexing;
- existing spatial-handler use;
- migration of the 31 authored spatial definitions;
- direct execution of the fourteen environmental rows;
- exact active caller migration; and
- deletion of the wrapper/controller/gateway path.

EventQueue dispatch algorithms, general reducers, action architecture,
condition application policy, material-layer authoring, server APIs, frontend
asset binding, and distributed runtime architecture are not redesigned by this
plan.

## 21. Completion criteria

1. Every active spatial phenomenon is one `SpatialCondition` instance.
2. GridMap owns every active spatial condition and its reverse footprint.
3. Every covered Tile can return the exact condition through one complete
   condition query.
4. Spatial handlers remain position-indexed and one-per-zone.
5. Duration advances once per condition.
6. Activation, movement, transformation, expiry, and deactivation have one
   condition-owned cleanup path.
7. Spike traps retain exact independent ownership, reveal, extension, damage,
   and lever deactivation.
8. All 31 authored definitions retain their mechanics.
9. All fourteen transition rows retain their behavior.
10. The live interaction event reaches each overlapping condition exactly once.
11. Wet, restraint, aura, and protection memberships retain exact source
    ownership.
12. Existing spatial interaction/change facts remain the replay and projection
    boundary.
13. No active `SpatialEffect` host/controller pair remains.
14. No active gateway/context or deprecated transition executor remains.
15. No wrapper-era lifetime policy or `*_effect_uuid` trap-owner field remains.
16. Core dependency arrows remain downward and cycle-free.
17. Focused, integration, architecture, fresh-process, and allowed broader
    tests pass.
18. Two independent reviewers approve the frozen revision.
19. Three independent anti-slop passes find no unnecessary subsystem rewrite,
    duplicate authority, compatibility facade, late import, cycle mask, or
    unowned capability.
