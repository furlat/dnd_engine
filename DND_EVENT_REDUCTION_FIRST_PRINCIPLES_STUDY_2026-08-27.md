# First-principles event reduction study

Date: 2026-08-27  
Status: study candidate; no implementation is authorized by this document  
Consumer plan: `DND_PYGAME_SCRIPTED_ENCOUNTER_MVP_IMPLEMENTATION_PLAN_2026-08-27.md`

## 1. Conclusion

The reduced stream should be a censorship morphism over one canonical,
immutable event-view space.

```text
mechanics Event stream
    -> explicit normalization into canonical full-knowledge views
    -> the same canonical view space
         -> full-knowledge views for privileged diagnostics
         -> censored views for a controlled observer set
    -> presentation
```

Objective and subjective output must not have parallel concrete model
families. There is no `ObjectiveAttackView` beside a
`SubjectiveAttackView`. Both are `CanonicalEventView` values with the same
event kind, fact vocabulary, formatter, and presentation dispatch. The
subjective value simply contains fewer authorized facts.

The canonical view must not literally be a mechanics `Event`. Mechanics event
classes have required authoritative fields, live behavior, mutable queue-owned
graph lists, arbitrary context, and domain objects that must not cross the
presentation boundary. Replacing their fields with `None` or redaction
sentinels would make invalid mechanics objects and invite accidental authority
leaks.

The field-level censorship operation is simple. The complete stream reducer is
necessarily stateful. A tile may change while unseen, remain represented by
its last-seen state, and disclose its current state only when sight returns.
Likewise, `WorldInitializedEvent` occurs before actors exist and
`EntityCreatedEvent` contains a full private character build, while later
`SensoryUpdateEvent` values authorize contacts without repeating all intrinsic
presentation facts. Therefore the complete reducer is a small causal
transducer:

```text
(projection memory, next closed objective batch)
    -> (new projection memory, zero or more canonical censored views)
```

This state does not duplicate the game world. It retains only normalized cold
facts and observer knowledge needed to replay censorship without consulting
live `GridMap`, `Entity`, `Encounter`, registries, controllers, or renderer
state.

## 2. Scope and non-goals

This study defines the reduction boundary required by the scripted
`pygame-ce` encounter MVP. It covers:

- objective capture and lifecycle collapse;
- one canonical view representation;
- event-time identity, location, coordinate, ownership, and sensory evidence;
- late disclosure and last-seen memory;
- two controlled observers and their party knowledge join;
- tile, tile-content, wall, lighting, invisibility, and special-sense facts;
- movement paths and elevation facts;
- hidden event ordering and presentation acknowledgement;
- structured combat-log reduction;
- failure behavior and proof obligations.

It does not authorize implementation. It does not design networking, a
server, an SDK, TypeScript contracts, replay persistence, save files, a
general UI, a renderer plugin system, or Phase 7 of the earlier migration.
Future transport becomes simpler because it can serialize the already-reduced
canonical view without inventing a second subjective schema.

## 3. What the engine currently provides

### 3.1 Event lifecycle and storage

`EventQueue` stores every lifecycle version in one append-only generation:

- `DECLARATION`, `EXECUTION`, and `EFFECT` are handler-visible;
- `COMPLETION` is the terminal committed fact and does not dispatch handlers;
- `CANCEL` terminates an aborted lineage;
- every repost has a new UUID while retaining `lineage_uuid`;
- an outer `batch_on_event_callbacks()` boundary preserves storage order
  across nested actions, reactions, damage, spatial changes, sensory updates,
  death checks, and encounter termination.

Stored mechanics events are not immutable snapshots. When a child is stored,
the queue mutates parent child lists, including earlier versions in the parent
lineage. Passive callback failures are isolated and logged. The coordinator
must therefore capture a closed source range explicitly after the mechanics
boundary, deep-freeze the required values, validate the before/after cursors,
and rebuild semantic causality from source metadata. It must not retain live
`Event` references or treat mutable `children_events` lists as archival truth.

### 3.2 Event-time observer evidence

Before each event version is stored, `SpatialSensesSystem` records:

- `identified_entity_observer_uuids`: participant identity grants accumulated
  across the lineage;
- `located_entity_observer_uuids`: observers with a current exact contact for
  a participant at that event version;
- `located_position_observer_uuids`: independent grants for explicit carried
  coordinates, frozen where an event family defines that rule.

Participant identity and current location are deliberately separate. A
participant also identifies itself. `ActionEvent` adds all declared entity
targets to the base source/target participant set. Other event families often
rely on their factories setting source and target correctly; arbitrary UUID
fields such as encounter rosters, owners, killers, contents, or trigger
identities are not automatically safe.

This evidence is necessary but not a generic authorization to dump an event.
Every canonical fact still needs an explicit disclosure rule.

### 3.3 Observer-specific sensory facts

`SensoryUpdateEvent` is already a replayable observer-local delta. It carries:

- the observer and optional new observer position;
- currently visible cells added and removed;
- explored cells added;
- observer-effective light after-values;
- entity and object contact after-values and removals;
- sense-mode, passive-perception, visual-access, and path-dirty changes.

`Senses.apply_sensory_update()` proves that these deltas can reproduce the
observer's perception without querying the live map. Contacts distinguish
visual access from blindsight/tremorsense and other special-sense evidence.

The delta does not repeat the tile, object, equipment, or entity presentation
facts that become newly authorized. Those facts must come from an objective
event-built catalog.

### 3.4 Cold intrinsic facts

`WorldInitializedEvent` contains the renderer-neutral initial world:

- tile positions, surfaces, elevation, structural flags, movement costs, and
  objective light;
- world-object placement and complete item state;
- traversal connectors.

It is published before actors are created. It cannot itself be copied to the
party view.

`EntityCreatedEvent` contains a complete composed entity, including private
ability scores, HP, proficiencies, resources, spells, actions, conditions,
inventory, equipment, and public-looking identity/appearance facts. It also
cannot be copied wholesale for a non-owned entity.

Later world, item, entity, progression, condition, and life-state events
provide enough objective after-values to maintain the small catalog needed by
the MVP. Spatial-effect lifecycle events provide identity, content, layer, and
footprint, but currently omit the concealment after-value needed for safe late
disclosure; section 21.5 freezes the one required engine-event enrichment. A
missing after-value must fail closed; the reducer must not repair it with a
registry read.

### 3.5 Combat logs

Top-level completion logs are created during completion preparation, before
the terminal event version is stored. Their canonical identity is therefore
the objective combat-log index, not an event index. Source lineage and a
terminal event index resolved after the batch are optional provenance.
Standalone log entries legitimately have no event-stream index.

`CombatLogEntry` contains free prose, a loosely typed data mapping, nested
subentries, and excluded observer-evidence maps. The deprecated projector had
to recursively scrub arbitrary strings and rebuild aggregates after hiding
children. That behavior is valuable evidence, but string replacement is not a
safe future reduction boundary.

## 4. Why a pointwise copy/filter is insufficient

A pure function of one raw event cannot produce the correct subjective
stream:

1. world initialization precedes every observer;
2. entity creation carries private and public intrinsic facts together;
3. a later sensory update authorizes presentation facts originating in an
   earlier event;
4. hidden world changes must update objective catalog state but not player
   memory;
5. a later reveal must disclose the current objective state, not the original
   bootstrap value and not a live-registry value;
6. party state must retain a cell/contact when one controlled observer loses
   it but the other retains it;
7. a visible descendant may survive a hidden parent;
8. movement presentation must be rebuilt from authorized committed steps, not
   from a hidden root path;
9. a log aggregate must be recomputed after its children are censored.

The correct model is therefore a causal stream transducer whose output values
all inhabit one canonical view space.

## 5. Canonical view space

### 5.1 One structural event view

The recommended conceptual value is:

```text
CanonicalEventView
    view_id
    event_kind
    semantic_phase
    causal_parent_view_id?
    facts: ordered immutable FactAtom[]
```

The concrete Python module and class spelling are implementation-plan work,
but the semantic schema and admission envelope are fixed here:

- `view_id` is projection-native and carries no raw engine UUID;
- `event_kind` is a reviewed `CanonicalKind` chosen by the explicit concrete
  source-class normalizer. `EventType` is not sufficient dispatch identity:
  `MovementEvent`, `JumpEvent`, and `TraverseConnectorEvent` can all use
  `EventType.MOVEMENT` while requiring different geometry and cues;
- `semantic_phase` is terminal completion, cancellation, or an explicitly
  reviewed nonterminal presentation fact;
- the parent relation is a closed player-safe graph;
- facts are immutable, canonically ordered, renderer-neutral values;
- no `BaseObject`, mechanics `Event`, callable, live registry object, mutable
  list/dict, arbitrary `context`, handler object, or private evidence map may
  be a fact value.

Objective and subjective views are instances of this same structure. Raw
source index, raw UUID, raw lineage, source batch range, and projection reasons
belong to a privileged `ProjectionAudit`, not the ordinary view.

### 5.2 Atomize facts before censorship

Normalization must split large authoritative objects into independent semantic
facts. For example, an entity creation record should not contain one nested
`EntityCreatedEvent` dump. It should provide separate atoms such as:

```text
entity.identity
entity.appearance
equipment.state
entity.life_state
entity.hp.current
entity.hp.maximum
entity.hp.temporary
```

Ability scores, spell lists, and other mechanics-only creation fields do not
enter the MVP canonical presentation space at all. Controlled ownership does
not justify copying irrelevant mechanics state into a renderer stream.

Likewise, a world object must separate visible appearance and placement from
charges, value, hidden contents, mechanical damage, and owner-private state.

This makes censorship a filter over facts instead of a fragile recursive
mutation of domain models. Aggregate facts whose truth depends on a collection
must be recomputed from retained child facts; an objective count may not
survive after hidden elements are removed.

`FactAtom` is not permission to replace types with `Dict[str, Any]`. Fact paths
form a closed reviewed vocabulary, and every path has one validated immutable
value shape. A normalizer cannot emit an undeclared path or a value that fails
that path's contract. This retains schema safety while avoiding duplicated
objective/subjective event classes.

Every field inside one frozen record has the same authorization boundary.
Facts with different disclosure policy are different atoms: public roll
outcome versus owned roll detail, damage amount versus damage type, equipment
appearance versus item identity, and entity life state versus HP. Censorship
never walks record members recursively. The only reviewed aggregate-projection
exception is `SpatialEffectStateFact.positions`: each cell is independently
authorized, and the tuple is rebuilt in canonical order from retained cells.
This exception is implemented by that one path-specific rule; it does not
permit generic record walking, arbitrary collection filtering, or rewriting
any other record member.

### 5.2.1 Frozen MVP dispatch and value envelope

The MVP uses this closed `CanonicalKind` vocabulary:

```text
WORLD_BOOTSTRAP   ENTITY_DISCLOSURE   SENSORY_DELTA
ENCOUNTER_BOUNDARY   ROUND_BOUNDARY   TURN_BOUNDARY
MOVE_ROOT   JUMP_ROOT   CONNECTOR_TRANSFER   MOVE_STEP   FORCED_MOVE
ATTACK   SPELL_CAST   ROLL   DAMAGE   RECOVERY
LIFE_STATE   CONDITION   EQUIPMENT   WORLD_DELTA
```

These are semantic presentation kinds, not aliases for `EventType`. Concrete
source class is consulted only by the normalizer and retained only in the
privileged audit. Ordinary dispatch sees `CanonicalKind`.

`FactAtom.value` is exactly one member of this closed immutable union:

```text
bool | int | DisplayText | SemanticId | SpellSchool | RemovalKind | ProjectionRef |
GridPosition | GridBounds | tuple[GridPosition, ...] |
tuple[SemanticId, ...] | TileSurfaceVisualFact | TileVisualFact | WorldObjectVisualFact |
ConnectorVisualFact | WorldRemovalFact | EntityAppearanceFact |
EquipmentAppearanceFact | ContactFact | PositionedLightFact |
tuple[SenseModeFact, ...] | RollResultFact | RollDetailFact |
AreaGeometryFact | SpatialEffectStateFact | SpatialEffectTransitionFact |
SpatialInteractionFact
```

The named scalar aliases are validated strings with distinct meanings;
`ProjectionRef` is projection-native and cannot contain an engine UUID.
`SpellSchool` is exactly one of `abjuration`, `conjuration`, `divination`,
`enchantment`, `evocation`, `illusion`, `necromancy`, or `transmutation`.
`RemovalKind` is exactly `world_object` or `connector`.
`GridPosition` is exactly two integers and `GridBounds` exactly four. The
remaining frozen records have these fields and no extras:

| Record | Exact fields |
|---|---|
| `TileSurfaceVisualFact` | `base_material: SemanticId`, `layers: tuple[tuple[SemanticId, DisplayText], ...]` |
| `TileVisualFact` | `position: GridPosition`, `surface: TileSurfaceVisualFact`, `display_name: DisplayText`, `elevation_steps: int`, `surface_kind: SemanticId`, `slope_axis: SemanticId?` |
| `WorldObjectVisualFact` | `projection_ref: ProjectionRef`, `content_id: SemanticId`, `display_name: DisplayText`, `position: GridPosition`, `placement_kind: SemanticId`, `boundary_direction: SemanticId?`, `base_height_steps: int`, `top_height_steps: int`, `orientation: SemanticId?`, `boundary_kind: SemanticId?`, `material_id: SemanticId?`, `is_open: bool?` |
| `ConnectorVisualFact` | `projection_ref: ProjectionRef`, `authored_id: SemanticId`, `kind: SemanticId`, `endpoints: tuple[GridPosition, GridPosition]`, `endpoint_elevations_feet: tuple[int, int]`, `enabled: bool`, `bidirectional: bool` |
| `WorldRemovalFact` | `subject_kind: RemovalKind`, `subject_ref: ProjectionRef`, `positions: tuple[GridPosition, ...]` |
| `AppearanceSemanticsFact` | optional fields only: `anatomy`, `build`, `stature`, `hair_style`, `skin_palette`, `hair_palette`, `beard_presence`, `beard_palette`, `lineage`, `role`; each value is validated against the frozen MVP sets below |
| `EntityAppearanceFact` | `projection_ref: ProjectionRef`, `entity_kind_id: SemanticId`, `display_name: DisplayText?`, `size: SemanticId`, `semantics: AppearanceSemanticsFact` |
| `EquipmentAppearanceFact` | `slot: SemanticId`, `content_id: SemanticId?`, `operation: SemanticId` |
| `ContactFact` | `subject_ref: ProjectionRef`, `position: GridPosition`, `visual: bool`, `special_senses: tuple[SemanticId, ...]` |
| `PositionedLightFact` | `position: GridPosition`, `level: int` constrained to a `LightLevel` value |
| `SenseModeFact` | `sense_type: SemanticId` from `SensesType`, `range_feet: int` |
| `RollResultFact` | `roll_kind: SemanticId` from `RollType`, `total: int` |
| `RollDetailFact` | `die_size: int?`, `effective_dice_count: int?`, `random_faces_rolled: int?`, `die_results: tuple[int, ...]`, `bonus: int`, `advantage_status: SemanticId`, `critical_status: SemanticId`, `auto_hit_status: SemanticId` |
| `SphereAreaFact` | `shape: "sphere"`, `center: GridPosition`, `radius_feet: int` |
| `ConeAreaFact` | `shape: "cone"`, `origin: GridPosition`, `direction: GridPosition`, `length_feet: int`, `angle_degrees: int` |
| `LineAreaFact` | `shape: "line"`, `origin: GridPosition`, `direction: GridPosition`, `length_feet: int`, `width_feet: int` |
| `CubeAreaFact` | `shape: "cube"`, `origin: GridPosition`, `direction: GridPosition?`, `size_feet: int`, `centered: bool` |
| `CylinderAreaFact` | `shape: "cylinder"`, `center: GridPosition`, `radius_feet: int`, `height_feet: int` |
| `SpatialEffectStateFact` | `effect_ref: ProjectionRef`, `content_id: SemanticId`, `layer: SemanticId` from `SpatialEffectLayer`, `positions: tuple[GridPosition, ...]` |
| `SpatialEffectTransitionFact` | `effect_ref: ProjectionRef`, `operation: SemanticId` from `SpatialEffectChangeOperation` |
| `SpatialInteractionFact` | `operation: SemanticId` from `SpatialEffectInteractionOperation`, `positions: tuple[GridPosition, ...]`, `intensity: SemanticId` from `SpatialEffectInteractionIntensity`, `source_content_id: SemanticId?` |

`AreaGeometryFact` is the closed discriminated union of the five area records;
it is not a generic shape record.

`SpatialEffectStateFact.positions` is an operation-neutral current snapshot,
not the footprint from a historical transition. In a full view it contains
the current full footprint. Censorship recomputes the tuple from independently
authorized current cells, so seeing one cell cannot reveal the hidden rest of
an area. Its other fields are copied unchanged. The resulting subjective state
is required to be the canonical ordered cell-subset of the matching full state;
this is the sole exception to literal atom equality in full-view dominance.
An empty retained tuple emits no state atom, but it is never used as an
implicit deletion: the explicit `spatial.effect_reset` rule below clears prior
projection state.

`AppearanceSemanticsFact` is not a property bag. For this one fixed encounter,
the only admitted fields and values are:

| Field | Admitted values |
|---|---|
| `anatomy` | `humanoid` |
| `build` | `average`, `broad`, `slender` |
| `stature` | `average`, `tall`, `short`, `small` |
| `hair_style` | `hair_10`, `hair_17`, `hair_22` |
| `skin_palette` | `light_tan`, `warm_tan`, `green` |
| `hair_palette` | `auburn`, `sand` |
| `beard_presence` | `present`, `absent` |
| `beard_palette` | `auburn`, `sand`, `none` |
| `lineage` | `goblinoid` |
| `role` | `archer`, `arcane_caster` |

The source-key mapping is exact: `body.form`/`anatomy -> anatomy`,
`body.build -> build`, `body.stature`/`stature -> stature`,
`head.hair_style -> hair_style`, `palette.skin`/`skin_palette -> skin_palette`,
`palette.hair -> hair_palette`, `beard.presence -> beard_presence`,
`palette.beard -> beard_palette`, and `lineage`/`role` retain their names.
Unknown keys or values fail closed. Consequently the fixture preflight may
choose only the current barbarian/fighter/spellblade/sorcerer presets and
goblin/goblin-archer/goblin-caster definitions represented by this vocabulary;
choosing other content requires a reviewed vocabulary amendment, not a regex
escape hatch. These are renderer-independent semantic appearance tokens, not
asset paths or layer bindings.

Strings, dictionaries, source Pydantic models, and arbitrary nested tuples are
not alternative union members. A path further narrows the allowed union
member. The closed path contracts for the MVP are:

| Path set | Exact value contract |
|---|---|
| `world.battlefield_id` | `SemanticId` |
| `world.battlefield_name` | `DisplayText` |
| `world.bounds` | `GridBounds` |
| `world.tile` | `TileVisualFact` |
| `world.object` | `WorldObjectVisualFact` |
| `world.connector` | `ConnectorVisualFact` |
| `world.removed` | `WorldRemovalFact` |
| `actor.role`, `target.role` | one of `actor`, `source`, `target`, `affected`, `observer`, `anonymous_source` |
| `actor.identity`, `target.identity`, `entity.identity` | `ProjectionRef` |
| `actor.name`, `target.name` | `DisplayText` |
| `actor.position`, `target.position`, `entity.position` | `GridPosition` |
| `entity.appearance` | `EntityAppearanceFact` |
| `entity.life_state` | reviewed `SemanticId` life-state token |
| `entity.hp.current`, `entity.hp.maximum`, `entity.hp.temporary` | `int` |
| `observer.identity` | `ProjectionRef` |
| `observer.position` | `GridPosition` |
| `observer.visible.added`, `observer.visible.removed`, `observer.explored.added` | `tuple[GridPosition, ...]` |
| `observer.light.level` | `PositionedLightFact` |
| `observer.contact.changed` | `ContactFact` |
| `observer.contact.removed` | `ProjectionRef` |
| `observer.sense_modes` | `tuple[SenseModeFact, ...]` |
| `observer.visual_access` | `int` |
| `boundary.operation` | one of `start`, `end`, `cancel` |
| `action.operation` | one of `move`, `jump`, `connector_transfer`, `attack`, `cast_spell`, `save`, `check`, `take_damage`, `heal`, `temporary_hit_points`, `apply_condition`, `remove_condition`, `equip`, `unequip`, `collision` |
| `action.outcome` | one of `completed`, `canceled`, `hit`, `miss`, `critical`, `critical_miss`, `success`, `failure`, `blocked`, `interrupted`, `stabilized`, `died`, `revived` |
| `round.number`, `turn.number` | `int` |
| `movement.from`, `movement.to` | `GridPosition` |
| `movement.from_elevation_feet`, `movement.to_elevation_feet` | `int` |
| `movement.trajectory`, `movement.termination` | reviewed `SemanticId` token |
| `movement.disclosed_path` | `tuple[GridPosition, ...]` |
| `attack.weapon_id`, `attack.outcome`, `spell.id` | `SemanticId` |
| `spell.school` | `SpellSchool` |
| `spell.level`, `spell.cast_level` | `int` |
| `spell.area` | `AreaGeometryFact` |
| `roll.result` | `RollResultFact` |
| `roll.detail` | `RollDetailFact` |
| `damage.amount` | `int` |
| `damage.type` | `SemanticId` from `DamageType` |
| `recovery.amount` | `int` |
| `condition.id` | catalog/authored `SemanticId` |
| `condition.operation` | one of `applied`, `removed` |
| `equipment.state` | `EquipmentAppearanceFact` |
| `equipment.item_identity` | `ProjectionRef` |
| `spatial.effect_state` | `SpatialEffectStateFact` |
| `spatial.effect_reset` | `ProjectionRef`; ordinary retention requires that reference to be previously disclosed in the same projection |
| `spatial.effect_transition` | `SpatialEffectTransitionFact` |
| `spatial.interaction` | `SpatialInteractionFact` |

The repeated light atoms are canonically ordered by position; they are not a
dictionary. A `SemanticId` is either a catalog/authored ID validated by the
current engine identity contract, or the serialized member of the exact
source enum named by the record field (`Material`, `ElevationSurfaceKind`,
`SlopeAxis`, `WorldPlacementKind`, `CardinalDirection`,
`BoundaryStructureKind`, `TraversalConnectorKind`,
`TraversalConnectorChangeOperation`, `Size`, `SensesType`, `LifeState`,
`WeaponSlot`, `BodyPart`, `RingSlot`, `ItemLocation`,
`ConditionApplicationDisposition`, `MovementTrajectory`,
`MovementTerminationReason`, `DamageType`, `SpatialChangeType`,
`SpatialEffectChangeOperation`, `SpatialEffectInteractionOperation`,
`SpatialEffectInteractionIntensity`, `SpatialEffectLayer`, `RollType`,
`AdvantageStatus`, `CriticalStatus`, `AutoHitStatus`, `AttackOutcome`, or their
explicitly admitted condition/equipment operation enums). `LightLevel` is the
closed integer set `{0, 1, 2, 3}` rather than a semantic string.
Other enum-valued paths take only the corresponding source enum member.
Equipment state operation is exactly `present`, `equipped`, `unequipped`, or
`removed`. Adding a literal, path, record field, or union member requires
explicit study/plan revalidation; a normalizer cannot widen the schema to
`str -> Any`.

### 5.2.2 Exact MVP source admission

Only these concrete source-class groups are admitted. A subclass or sibling
not named here is unknown and fails before enqueue. If public action discovery
selects a spell that emits another concrete class, preflight must stop and
amend/revalidate this contract rather than silently register it.

In the table, `world.*`, `entity.*`, and similar notation is only shorthand
for the exact paths already enumerated in section 5.2.1. It does not admit a
namespace wildcard.

| Concrete source class | `CanonicalKind` | Allowed path groups |
|---|---|---|
| `WorldInitializedEvent` | `WORLD_BOOTSTRAP` | `world.*` |
| `EntityCreatedEvent` | `ENTITY_DISCLOSURE` | presentation-relevant `entity.*`, initial `equipment.state` |
| `EntityLevelAddedEvent`, `EntityLevelRemovedEvent` | `ENTITY_DISCLOSURE` | presentation-relevant `entity.*`; mechanics-only progression/equipment fields are discarded because item-location facts own later equipment state |
| `SensoryUpdateEvent` | `SENSORY_DELTA` | `observer.*`, catalog-backed `world.*`/`entity.*` disclosures, and catalog-backed operation-neutral `spatial.effect_state`/`spatial.effect_reset` |
| `EncounterStartEvent`, `EncounterEndEvent` | `ENCOUNTER_BOUNDARY` | `boundary.*`, authorized actor facts |
| `RoundStartEvent`, `RoundEndEvent` | `ROUND_BOUNDARY` | `boundary.*`, `round.number` |
| `TurnStartEvent`, `TurnEndEvent` | `TURN_BOUNDARY` | `boundary.*`, `turn.number`, authorized actor facts |
| `MovementEvent` | `MOVE_ROOT` | actor facts, `action.*`, authorized `movement.*` |
| `JumpEvent` | `JUMP_ROOT` | actor facts, `action.*`, authorized `movement.*` |
| `TraverseConnectorEvent` | `CONNECTOR_TRANSFER` | actor facts, `action.*`, authorized `movement.*`, `world.connector` |
| `StepMovementEvent` | `MOVE_STEP` | actor facts, committed `movement.*` |
| `ForcedMovementEvent` | `FORCED_MOVE` | actor/target facts, committed `movement.*` |
| `AttackEvent` | `ATTACK` | actor/target facts, `attack.*`, `action.*` |
| `SpellEvent` | `SPELL_CAST` | actor/target facts, `spell.*`, `action.*` |
| `AttackD20RollResultEvent`, `SavingThrowD20RollResultEvent`, `AbilityCheckD20RollResultEvent`, `SkillCheckD20RollResultEvent`, `DamageRollResultEvent`, `HealRollResultEvent` | `ROLL` | authorized actor/target facts, admitted `roll.result`, owned `roll.detail`; their action/outcome-shaped fields never own semantic outcome |
| `SavingThrowEvent`, `AbilityCheckEvent`, `SkillCheckEvent` | `ROLL` | authorized actor/target facts and parent-owned `action.outcome`; typed result children exclusively own roll atoms |
| `TakeDamageEvent` | `DAMAGE` | authorized actor/target facts plus interruptible attempt/cancellation `action.*`; it never owns applied-damage atoms |
| `DamageAppliedEvent` | `DAMAGE` | authoritative separately authorized `damage.amount`, `damage.type`, and owned resulting HP facts |
| `HealEvent`, `TemporaryHitPointsEvent` | `RECOVERY` | authorized actor/target facts, `recovery.amount`, authorized life/HP facts |
| `LifeStateChangeEvent`, `DeathEvent`, `InstantDeathEvent`, `ReviveEvent`, `DeathSaveEvent` | `LIFE_STATE` | authorized actor/target facts, `entity.life_state`, owned HP/death-save outcome facts; typed result children exclusively own roll atoms |
| `ConditionApplicationEvent`, `ConditionRemovalEvent` | `CONDITION` | authorized actor/target facts, `condition.*` |
| `WeaponEquipEvent`, `WeaponUnequipEvent`, `ArmorEquipEvent`, `ArmorUnequipEvent`, `ShieldEquipEvent`, `ShieldUnequipEvent` | `EQUIPMENT` | authorized actor facts and action cue only; `ItemLocationStateEvent` owns equipment state |
| `SpatialChangeEvent`, `TileElevationChangeEvent`, `TraversalConnectorChangeEvent` | `WORLD_DELTA` | separately authorized `world.*` and entity/object position facts |
| `SpatialEffectChangeEvent` | `WORLD_DELTA` | separately authorized `spatial.effect_state`, `spatial.effect_reset`, and `spatial.effect_transition` |
| `SpatialEffectInteractionEvent` | `WORLD_DELTA` | separately authorized `spatial.interaction` |
| `ItemLocationStateEvent` | `WORLD_DELTA` | separately authorized `world.object`, `world.removed`, `equipment.state`, and `equipment.item_identity`; inventory-only changes emit no ordinary scene atom |

`WORLD_DELTA` operations are not wildcard DTO copies. Their exact treatment is:

| Source operation | Catalog effect | Possible ordinary atom |
|---|---|---|
| `SpatialChangeType.ENTITY_ENTERED` / `ENTITY_LEFT` | update current entity placement | none by default; admitted movement/sensory facts carry presentation |
| `TILE_CHANGED` and `TileElevationChangeEvent` completion | replace current tile visual/elevation fact | authorized `world.tile` |
| non-item `OBJECT_PLACED` / `OBJECT_CHANGED` | replace current object visual/placement fact | authorized `world.object` |
| non-item `OBJECT_REMOVED` | delete current object fact | authorized `world.removed` tombstone |
| item `OBJECT_PLACED` / `OBJECT_CHANGED` / `OBJECT_REMOVED` | update committed geometry and sensory inputs only; the catalog identifies an item from earlier `WorldInitializedEvent`, `EntityCreatedEvent`, or `ItemLocationStateEvent` facts | none; the corresponding `ItemLocationStateEvent` exclusively owns the item floor visual transition |
| `PERCEIVABILITY_CHANGED` / `LIGHT_CHANGED` | update objective inputs only | none; resulting controlled `SENSORY_DELTA` carries presentation |
| `MOVEMENT_COLLISION` | no world snapshot | controlled/authorized `action.outcome` only |
| connector `REGISTER` / `REPLACE` / `ENABLE` / `DISABLE` | replace connector fact | authorized `world.connector` |
| connector `REMOVE` | delete connector fact | authorized `world.removed` tombstone |
| floor `ItemLocationStateEvent` placement | replace the item's current object visual/placement fact | authorized `world.object` |
| transition from floor in `ItemLocationStateEvent` | delete the cataloged floor object fact using its prior placement and projection reference | authorized `world.removed` tombstone |
| equipment/non-equipment `ItemLocationStateEvent` | update/remove the owner's slot or private item location | authorized `equipment.state` plus separately authorized `equipment.item_identity`; inventory-only changes emit no ordinary scene state |
| spatial-effect create/footprint-change/reveal/transform | replace the exact operation-neutral current effect instance keyed by `effect_ref` | if the party-projected authorized cell set changes: `spatial.effect_reset` for an already disclosed reference followed by the nonempty authorized `spatial.effect_state`; plus the separately authorized transient `spatial.effect_transition` cue |
| spatial-effect removal | delete the exact current effect instance keyed by `effect_ref` | `spatial.effect_reset` for a previously disclosed reference, plus an authorized `spatial.effect_transition` cue; hidden never-disclosed removal emits neither ordinary atom |
| spatial-effect interaction | no direct catalog mutation; resulting lifecycle events separately own any state change | authorized transient `spatial.interaction` cue only |

`SpatialChangeType.TILE_CREATED` and `TILE_REMOVED` are enum members without an
active typed presentation snapshot/tombstone constructor in the admitted MVP;
encounter preflight must fail if either appears. They are not silently accepted
through the class-level row.

Canonical fact ownership is singular:

- typed D20/damage/heal result children exclusively emit repeated
  `roll.result` atoms and, when owned, matching `roll.detail` atoms. Their
  `result`, `success`, and `attack_outcome` fields do not emit semantic outcome;
  saving/check parents exclusively own success/failure `action.outcome`,
  `AttackEvent` owns `attack.outcome`, and the recovery/life-state parents own
  their semantic outcomes;
- `DamageAppliedEvent` exclusively emits positive applied amount/type and
  resulting owned HP, while `TakeDamageEvent` emits only the interruptible
  attempt or cancellation outcome;
- `EntityCreatedEvent` emits initial `equipment.state` records with operation
  `present`; later `ItemLocationStateEvent` completions exclusively update or
  remove slot state, while concrete equip/unequip events are action cues;
- `ItemLocationStateEvent` exclusively owns item floor appearance/removal;
  spatial item placement events own geometry and sensory timing but emit no
  duplicate `world.object` or `world.removed` atom. Spatial changes for
  non-item objects retain their ordinary world-state authority;
- `SpatialEffectChangeEvent` exclusively owns identity-bearing persistent
  effect state and a separate transition cue. The catalog stores only the
  operation-neutral state record, never a historical transition.
  `SpatialEffectInteractionEvent` is a source-optional transient cue and
  cannot create, replace, or remove catalog state by itself;
- `spatial.effect_reset` is projection control, not an objective removal. It
  names only a previously disclosed projection reference, clears all currently
  presented cells for that reference, and is immediately followed by the
  nonempty current authorized state when any cells remain. Reset alone is the
  exact all-cells-cleared representation;
- a `world.removed` tombstone is emitted only for a previously disclosed
  `ProjectionRef`. Hidden removal updates the private catalog and emits no
  ordinary atom; deletion by kind/position alone is forbidden.

These rules prevent parent/child result duplication and state reconciliation
by guesswork. Combat-log trees remain independently normalized, but their
atoms follow the same disclosure boundaries.

`EventType` may be copied to privileged audit diagnostics, but it never chooses
ordinary presentation dispatch.

Combat logs have a separate closed `CanonicalLogKind` because their journal is
independently indexed. The mapping is exact:

| `CombatLogEntryType` | `CanonicalLogKind` | Allowed fact groups |
|---|---|---|
| `ATTACK` | `ATTACK` | actor/target, attack, roll, damage |
| `MOVEMENT` | `MOVEMENT` | actor, authorized movement |
| `ACTION`, `MULTI_ENTITY_ACTION` | `ACTION` | actor/target, action, spell area if present; aggregates recomputed |
| `SAVING_THROW`, `DEATH_SAVE`, `ABILITY_CHECK`, `SKILL_CHECK`, `ROLL_MODIFICATION` | `ROLL` | actor/target, roll, owned/admitted outcome |
| `CONDITION_APPLIED`, `CONDITION_REMOVED` | `CONDITION` | actor/target, condition |
| `DAMAGE_TAKEN`, `SPELL_DAMAGE` | `DAMAGE` | actor/target, damage; aggregates recomputed |
| `HEAL`, `TEMPORARY_HIT_POINTS` | `RECOVERY` | actor/target, recovery, owned HP |
| `DEATH` | `LIFE_STATE` | actor/target, life state |
| `TURN_START`, `TURN_END` | `BOUNDARY` | boundary, authorized actor |
| `SPELL_SAVE`, `SPELL_INTERRUPTION` | `SPELL` | actor/target, spell, roll/outcome if admitted |
| `ENTITY_SPOTTED`, `HAZARD_DETECTED` | `DISCOVERY` | authorized identity/position or anonymous occurrence |
| `SPATIAL_EFFECT` | `WORLD_DELTA` | spatial presentation |

There is no generic log-data dictionary normalization. Each listed log kind
reads only its typed current log-data model or explicitly named scalar fields;
unknown keys and unknown `CombatLogEntryType` values fail closed.

### 5.3 Do not wrap every scalar in a knowledge class

The ordinary presentation value does not need pervasive
`Known/Unknown/Redacted/Absent` wrappers:

- fact present means that exact fact is known;
- fact absent means the view makes no assertion;
- event absent means event existence is not disclosed;
- a meaningful known absence uses an explicit semantic fact only when the
  event contract requires it;
- anonymous participation is derived from an authorized occurrence/role fact
  with the identity fact absent.

This avoids sentinel propagation and prevents a redaction marker from leaking
that a hidden optional value exists. The privileged comparison audit may say
`REDACTED` or `HIDDEN` because it already has objective authority. Those
markers never enter the presentation payload.

### 5.4 References

A known entity, object, tile, item, condition, or effect uses only a
projection-native `ProjectionRef`. Its private audit mapping may point to a
stable engine UUID, but that UUID never crosses the ordinary boundary. A
generic “an unseen creature” role is safe when event occurrence is known but
identity is not. It must not contain a stable anonymous token that accidentally
correlates hidden actions across time unless the engine supplies evidence for
that correlation; a scope-limited contact reference is retired and reissued
when such correlation is not authorized.

Exact positions are atomic `(x, y)` facts. Elevation belongs to the same
authorized endpoint/tile fact. A path is an ordered compound fact and is not
authorized merely because one endpoint is known.

## 6. Formal reduction model

Let:

- `E*` be closed objective event batches in source order;
- `V*` be sequences of canonical event views;
- `F` be the objective fact catalog built only from earlier objective events;
- `N_F` normalize explicit mechanics event families and enrich referenced
  facts into full-knowledge views at their causal after-state;
- `K` be observer projection memory built only from controlled sensory deltas
  and facts previously disclosed from `F`;
- `C_K` censor one full view under knowledge/evidence `K`, yielding the same
  view space or no view;
- `R_P` be the causal reducer for controlled observer set `P`.

Normalization first produces the single full view that both branches use:

```text
(F', full_views) = N_F(F, batch)
O(batch) = full_views
```

The subjective projection is:

```text
(K', output) = R_P(K, full_views)
```

No subjective path/value may be absent from the matching full view at its
delivery boundary. Catalog-backed late disclosure and candidate effect resets
are enrichment of that full view before branching, followed by ordinary
censorship; they are not subjective-only synthetic payloads. For every path
except `spatial.effect_state`, the subjective value is literally a full-view
value. For that one path, define `s <=effect f` when `effect_ref`, `content_id`,
and `layer` are identical and `s.positions` is the canonically ordered subset
of `f.positions`. Full-view dominance permits exactly that relation and no
other value rewriting.

For a fully authorized knowledge state, censorship is identity on normalized
views:

```text
C_top(v) = v
```

For a fixed knowledge state, censorship is idempotent:

```text
C_K(C_K(v)) = C_K(v)
```

For two party observers, ordinary event facts use a field-wise join:

```text
C_party(v) = C_K1(v) join C_K2(v)
```

This is not whole-event union. A source identity learned by one observer and a
target location learned by the other may coexist only when both atoms are
independently authorized. Observer-relative facts such as effective light are
keyed to their observer and are not incorrectly collapsed into one objective
value.

Closed-batch composition is:

```text
R(M, A ++ B) = output_A ++ output_B
where (M_A, output_A) = R(M, A)
  and (M_B, output_B) = R(M_A, B)
```

Arbitrary splitting inside an unfinished mechanics lineage is not a supported
law. Capture and reduction occur at accepted decision/batch boundaries.

## 7. Projection memory

The minimum justified memory is:

### 7.1 Objective catalog

- current normalized tile visual/elevation facts by position;
- current public appearance, placement, and presentation-state facts for
  world objects and non-owned entities;
- current connector, spatial-effect, condition, equipment, and life-state
  presentation facts that can be disclosed later;
- controlled-entity private HP facts only when an admitted scene or log fact
  needs them.

The catalog does not retain non-owned private ability scores, resources,
spells, inventory internals, item charges/value/contents, rules handlers, or
other facts that cannot become authorized in this fixed two-character MVP.

Each private spatial-effect catalog entry contains its operation-neutral
`SpatialEffectStateFact` plus the required
`condition_stealth_dc_after` authorization input. The latter never enters an
ordinary view. Historical lifecycle operations are audit provenance, not
catalog state.

The catalog is populated and updated only by the renderer-neutral cold and
incremental facts made replay-sufficient by the accepted Tile/world-item
migration. It is a detached value projection, not a second live mechanics
world: it has no rules behavior, handlers, queries back into mechanics,
registries, or command surface. It is private to reduction and is never
exposed as a renderer-readable objective world.

### 7.2 Per controlled observer

- replayed visible cells, explored cells, effective light, and current entity
  and object contacts;
- observer position and current sense/visual-access modes;
- the current authorization/access facts required to interpret event-time
  evidence.

Before the first controlled sensory delta, each observer replay state uses the
same cold seed as `Senses`: position `(0, 0)`; empty visible, explored, light,
contact, and sense-mode state; passive perception `0`; and visual access `1`.
This seed is part of the reduction contract, not inferred from a missing first
delta. A future engine seed change requires a matching reviewed contract
change or an explicit bootstrap after-value.

`observer.visual_access` is the exact normalized integer after-value from a
controlled `SensoryUpdateEvent`. When `visual_access_changed` is true,
`visual_access` must be present and the reducer replaces the stored value and
emits that atom. When the flag is false, the field emits no atom and does not
change memory. A changed flag with no value is fatal. This is access state,
not a renderer guess and not a duplicate visibility set.

The reducer additionally retains one narrow party-projection control value:
the last delivered authorized cell set for each disclosed spatial-effect
`ProjectionRef`. Current per-observer sets are recomputed from the objective
effect catalog plus each observer's replayed visibility and passive perception;
their union is compared with that delivered set to decide whether an explicit
reset/replacement is required. No other scene snapshot is retained. This is
the minimum memory needed to revoke a previously disclosed reference without
leaking a never-disclosed one and to preserve observer B's contribution when
observer A loses access.

Current access is non-monotone: visibility and exact location may be lost.
Exploration is monotone until a future explicit forgetting rule exists. These
must not be conflated.

For the MVP, the presentation scene—not the reducer—retains the last disclosed
terrain/elevation value in fog. On reacquisition the reducer emits the current
catalog snapshot. It does not keep a second per-observer copy of last-seen
terrain or owned private state. Dynamic entity and object sprites require a
current contact, and persistent effect cells require current visual
authorization; their last-known existence must not be rendered as current
truth. A future last-known-marker feature would be a separate explicit fact.

### 7.3 Audit state

- objective source range to opaque presentation batch ID;
- raw origin to canonical objective view;
- raw origin to zero or more censored views;
- hidden/lifecycle-collapsed/intentionally-silent reason codes;
- player-safe graph reparenting;
- objective log index/source provenance to opaque projection-native log view
  IDs and player-safe parent IDs;
- proof/canary and error records.

Audit state is privileged and must not be reachable by scene reduction.

No additional manager, service graph, mirror `EventQueue`, or second world
model is justified.

### 7.4 Rejected duplicate-snapshot alternative

Do not solve late disclosure by copying tile/entity/object intrinsic snapshots
into every `SensoryUpdateEvent`. The accepted Phase 5/6 boundary deliberately
made `WorldInitializedEvent` plus incremental committed facts replay-sufficient,
kept senses responsible for observer perception, and removed presentation
state from Tile/world-item mechanics. Repeating intrinsic world state per
observer would create the double representation this reducer is meant to
avoid.

The canonical normalizer instead joins the existing detached objective fact
projection with the sensory authorization at the reduction boundary, then
branches into full and censored views. A future sensory-event enrichment is
justified only for genuinely observer-derived facts that no objective event can
reconstruct, such as the missing per-cell establishing visual mode; it must not
duplicate intrinsic world or asset state.

## 8. Capture and lifecycle reduction

### 8.1 Capture one closed range

For every mechanics decision boundary:

1. record generation and source cursor before execution;
2. execute the complete accepted mechanics boundary;
3. record the source cursor after the outer event batch closes;
4. retrieve exactly that contiguous range;
5. deep-freeze explicit normalized values;
6. capture objective log slots created by the boundary;
7. verify generation, contiguity, and no duplicate source slot;
8. reduce and enqueue one immutable presentation batch.

The batch callback may be used as a diagnostic cross-check, but correctness
must not depend on an exception-swallowing passive callback.

### 8.2 Lifecycle quotient

The objective debug rail may display every raw phase after normalization. The
ordinary presentation stream should not animate each mechanics phase.

For each lineage, the semantic reducer normally emits:

- one completion view if the lineage completed;
- one cancellation view if it canceled;
- explicitly reviewed direct-completion facts such as sensory updates;
- explicitly reviewed step completions where each committed step is a
  presentation fact.

Declaration/execution/effect rows are marked `LIFECYCLE_COLLAPSED` in the
privileged coverage audit. They are not “unmapped” presentation events.
Family-specific nonterminal facts require a reviewed exception.

### 8.3 Safe causality

Raw parent UUIDs and lineages do not cross the boundary. After hidden and
technical nodes are removed, each visible descendant is attached to its
nearest surviving visible ancestor. If none exists, it becomes a root in the
current player-safe forest. This is a graph quotient, not a dangling pointer
to a hidden parent.

Objective/subjective correlation uses the private audit mapping. Presentation
does not need raw source identities to prove completion.

## 9. Evidence dimensions and default policy

Authorization is fact-specific. At minimum the policy distinguishes:

| Dimension | Evidence | What it can authorize |
|---|---|---|
| Controlled ownership | Entity is one of the two controlled actors | Every admitted private canonical presentation/log fact for that actor; it does not widen the schema to a character sheet |
| Event occurrence | Controlled participant, authorized position/effect, or reviewed public event | That something of the safe semantic kind happened |
| Participant identity | Event-time identity grant for that participant or controlled self | Projection-native reference, name, and admitted public identity atoms; raw UUID stays audit-only |
| Participant current location | Event-time located-participant grant | Exact participant position carried by the event |
| Independent coordinate | Explicit position grant for that coordinate | The exact coordinate, not nearby or related coordinates |
| Current visual cell | Replayed controlled sensory state | Current terrain/light access at that cell |
| Explored cell | Replayed `seen_cells_added` memory | Last disclosed terrain/elevation, not current contents |
| Entity/object contact | Replayed typed contact | Current presence and contact position; appearance only when visual |
| Direct private consequence | Controlled actor is the affected participant | Own admitted HP/save/result facts even if the cause is anonymous |
| Public visual intrinsic | Visual contact plus explicit intrinsic allowlist | Archetype, visible equipment, visible object/structure appearance |

Default deny is mandatory. Event names, source/target names, free-form status,
arbitrary context, behavior provenance, complete item/entity/condition models,
handler presentations, requested paths, hidden target lists, and objective
aggregates are not safe merely because they serialize.

`revealed_entity_uuids` on a log is not a global identity grant. A sensory
contact or event-time identity grant is the authority. Likewise, coarse log
`perceiver_uuids` can authorize that an occurrence is perceivable but cannot
authorize every nested field.

## 10. Party semantics for two controlled characters

The controlled set is fixed for the encounter. Selecting a character must not
change the party perspective.

### 10.1 Event facts

For ordinary event facts, party authorization is “at least one controlled
observer has the required evidence” independently per fact. The reducer must
prove that direct party reduction equals joining the two individual
reductions. For `spatial.effect_state`, the join is the canonical union of the
two independently authorized cell subsets. `spatial.effect_reset` is then
derived only by comparing that joined current set with the last delivered
party set; it is projection control rather than an additional knowledge fact.

### 10.2 Sensory deltas

Do not collapse the two `SensoryUpdateEvent` streams into a bespoke party event
type. Deliver only the sensory views belonging to the two controlled
observers, using the same canonical event-view shape. The presentation scene
reducer maintains both observer projections and derives the party viewport:

- visible cells are the union of current visible cells;
- explored terrain is the union of remembered cells;
- contacts are the union keyed by authorized identity;
- current persistent-effect cells are the union of the two observer-authorized
  operation-neutral effect states;
- removal from one observer does not remove a fact retained by the other;
- a contact is visual if either observer currently has a visual contact;
- special-sense modes are the union of contributing contact modes;
- effective party brightness uses the highest effective `LightLevel` supplied
  by a currently visual controlled observer for that cell.

The maximum-light rule is the most informative shared-player view supported by
current engine facts. It does not claim to model color perception.

Effect reset/replacement is party-global: if A loses eligibility while B still
authorizes cells, the reducer resets the prior party state and immediately
installs the recomputed nonempty union. If the union becomes empty it emits the
reset alone. Thus a sensory view belonging to A cannot accidentally remove B's
contribution.

### 10.3 Perfect sharing assumption

The MVP assumes the player controlling both characters has immediate access to
the union of their perceptions. Delayed communication, charm-induced
perspective separation, split-screen secrecy, and observer selection are later
product rules, not reducer abstractions to add now.

## 11. Bootstrap and late disclosure

### 11.1 World initialization

The objective catalog ingests all `WorldInitializedEvent` facts. The party
view may receive safe battlefield identity and bounds for camera/grid setup,
but no hidden tile contents, objects, connectors, objective light, or movement
costs.

This study recommends treating map bounds as public for the local MVP. If map
size itself must later be secret, that is a product-rule change.

### 11.2 Controlled entity creation

A controlled actor receives every admitted private canonical
presentation/log creation fact in section 5.2.
A non-owned entity creation view is hidden unless an independently authorized
public fact exists. Full stats, resources, actions, spell lists, conditions,
inventory, and hidden equipment never follow from visual identity.

### 11.3 Sensory disclosure enrichment

When a controlled `SensoryUpdateEvent` adds access, its normalized canonical
view is enriched from the objective event-built catalog:

- newly visible/explored cells carry their current allowed tile visual and
  elevation facts;
- a visual entity contact carries allowed identity, archetype, visible layers,
  visible equipment, life-state presentation, and its contact position;
- a nonvisual contact carries only the contact/identity facts justified by the
  typed contact, not visual appearance;
- a visual object contact carries allowed appearance, placement, boundary
  structure, and open/closed presentation state;
- every persistent spatial effect overlapping currently visible cells carries
  an operation-neutral `spatial.effect_state` whose positions are restricted
  to currently authorized cells. It is eligible only when its private catalog
  concealment after-value is absent or the observer's replayed passive
  perception is strictly greater than that DC;
- an observer-effective light after-value accompanies current visual access.

The same view also carries `observer.visual_access` on its exact changed
boundary even when no visible-cell delta accompanies it. Replaying that atom
must reproduce the gate used by subsequent controlled sensory facts; current
visible/contact after-values remain authoritative for what was actually
perceived at each boundary.

This effect-state enrichment also runs when passive perception changes while a
cell remains visible, and on reacquisition after hidden effect changes. It
never replays `created`, `transformed`, or another historical operation.
Lifecycle transition cues occur only at their original authorized boundary.

Before branching, a spatial lifecycle full view carries a reset candidate and
the current full state for that effect. A controlled sensory full view carries
the same candidates for catalog effects intersecting added/removed visible
cells; when passive perception changes it carries candidates for all current
catalog effects. Censorship computes each observer's authorized subset, joins
the party union, and compares it with the last delivered party set:

- unchanged union: emit neither reset nor replacement state;
- first nonempty disclosure: allocate/disclose the projection reference and
  emit the nonempty state without a reset;
- changed nonempty union: emit reset, then the replacement state;
- changed-to-empty union: emit reset alone;
- never-disclosed and still empty: emit nothing and allocate no reference.

Within one canonical view, scene reduction applies retained effect resets before
installing retained effect states, independent of serialized atom ordering.
The pair is one atomic projection replacement at that view boundary.

These reset candidates therefore exist in the matching full view; the reducer
does not synthesize an unrepresented negative fact after censorship.

The intrinsic fact may have originated many batches earlier. The delivered
view is ordered at the authorization/delivery boundary; its historical origin
is private audit provenance. Presentation never rewinds its acknowledgement
cursor.

Sensory updates are emitted before their causative parent completion is stored.
Closed-batch normalization must therefore resolve each update through its
`cause_event_uuid`/parent lineage and sample the causative committed
after-state. It may stage that view until the matching terminal fact is known.
It must not sample the final state of an unrelated later change in the same
batch. If the causal after-state cannot be proven from the closed event batch,
normalization fails closed.

### 11.4 Hidden changes

An unseen tile/object/entity change updates the objective catalog only. It
does not mutate the observer's remembered terrain or current scene. When
access returns, the reducer discloses the current authorized snapshot. This is
why a live registry read and a stateless mapper are both wrong.

## 12. Tile, contents, walls, vision, and light

Tile visibility and tile-content visibility are separate facts.

- A visible cell authorizes its allowed terrain/elevation presentation.
- It does not authorize every entity or object stored on that cell.
- Entities and center objects require typed contacts.
- Boundary structures require their own object contact and placement facts.
- A wall or blocking boundary may be visible from the observing side while it
  blocks cells beyond it. The blocker is disclosed; the occluded cells remain
  absent.
- Two adjacent tiles may each own separate wall-like content. Reduction must
  preserve each actual tile/object identity and must not reinterpret them as a
  single between-cell wall.
- Objective walkability, movement costs, optical blocking, propagation
  blocking, resolved light, and visible material appearance are distinct
  atoms. Only facts required and authorized for the subjective presentation
  are disclosed.

Objective `resolved_light` is catalog state, not player perception. Ordinary
presentation uses observer-effective light emitted by the sensory reducer:

- ordinary sight requires non-dark objective light and an unblocked optical
  route;
- darkvision upgrades darkness to dim and dim to bright within its rule;
- magical darkness defeats ordinary sight and darkvision;
- Devil's Sight and Truesight can produce effective bright access through
  darkness where current rules allow;
- heavy optical obscurement still blocks those visual modes;
- invisibility removes ordinary visual contact unless Truesight or See
  Invisible bypasses it;
- blindsight/tremorsense may create a nonvisual contact without making the tile
  visually accessible.

The scene must not draw a normal visible sprite for a purely nonvisual
contact. A minimal sense-contact marker is sufficient.

### 12.1 Current sensory fidelity gaps

The current event stream is sufficient for a brightness-based MVP, but it does
not carry every fact needed for richer perception styling:

- per-cell effective light is present, but the establishing visual mode is
  not;
- a contact records visual/special senses, but See Invisible is not currently
  retained as the explicit reason an invisible target became visual;
- darkvision grayscale versus ordinary color is therefore not replayable from
  the event stream.

Do not work around this by querying live senses or guessing in the renderer.
The MVP may render effective brightness only. If richer styling becomes a
requirement, enrich `SensoryUpdateEvent` with typed after-values at the engine
boundary and then normalize them into the same canonical fact space.

## 13. Event-family reduction policy

This table fixes disclosure policy for the exact concrete admission and fact
contracts in section 5.2. It does not authorize additional normalizers.

| Family | Occurrence gate | Candidate disclosed facts | Always restricted facts |
|---|---|---|---|
| World initialization | Public bounds or later controlled sensory access | Battlefield/bounds; disclosed tile/object/connector presentation snapshots | Hidden cells/contents, movement costs, objective light, undisclosed structures |
| Entity creation/progression | Controlled ownership; later visual/contact disclosure for public atoms | Owned presentation state; non-owned identity/appearance/life presentation only as authorized | Mechanics-only stats/resources/actions/spells/proficiencies; non-owned HP and inventory internals |
| Sensory update | Observer is controlled | That observer's replay delta plus catalog-backed authorized disclosures | Other observers' deltas, undisclosed catalog facts |
| Spatial/world delta | Controlled current cell/contact or direct controlled consequence | Authorized changed placement/surface/light/contact presentation after-values | Hidden positions, objective topology/costs, invisible contents |
| Step/forced movement | Controlled actor or event-time participant/coordinate evidence | Authorized committed endpoints, elevation, trajectory presentation | Requested/objective paths, uncommitted steps, ungranted endpoints, obstacle identity without evidence |
| Root movement/jump/connector | Controlled actor or reconstructable authorized committed motion | Safe action identity, termination visible to participant, path derived from disclosed committed steps | Copied objective path, hidden arc geometry, controller revalidation internals |
| Attack/spell/action | Controlled participant or perceivable actor/target/effect | Safe occurrence, separately authorized identities, public presentation kind, authorized outcome/effect | Hidden target list/count, private item state, behavior provenance, hidden origin/area, undisclosed DC/bonus |
| Checks/rolls | Controlled participant or parent occurrence policy | Public result required by the admitted combat presentation; owned details | Hidden actor/target, private modifiers/DCs unless explicitly admitted |
| Damage/heal/temp HP | Controlled affected actor or perceived affected contact | Applied amount and visible/owned consequence; authorized damage type/source | Non-owned resulting HP totals, defenses/resolution internals, anonymous source identity |
| Life/death/revive | Controlled affected actor or current perceived contact | Authorized identity, visible life-state transition, known killer only with identity grant | Hidden killer, non-owned private death-save counters/HP |
| Item/equipment | Controlled owner or current visual object/entity contact | Admitted equipment appearance and separately authorized item identity; non-owned visible placement/appearance change | Charges, value, hidden contents, hidden inventory, mechanical item stats |
| Condition/spatial effect | Controlled affected actor or perceived presentation effect/position | Reviewed public condition/effect presentation identity and authorized area | Complete condition object, handler state, hidden caster/source, undisclosed mechanics |
| Encounter/round/turn | Reviewed public boundary or authorized active actor | Encounter/round state; controlled or identified turn actor | Hidden roster members, hidden initiative positions, hidden autonomous decision details |

Unknown event kinds, unknown fact paths, arbitrary nested values, or missing
evidence fail closed and are fatal to the MVP reduction run. They do not copy
objective payload as a badge fallback.

## 14. Movement and elevation

Movement presentation is based on committed spatial facts.

- Controlled movement may disclose its own committed steps.
- A non-owned `StepMovementEvent` may disclose exact motion only when identity
  and both endpoint coordinates are independently authorized at completion.
- If only contact appearance/disappearance is known, sensory updates drive
  disappearance/reappearance; the reducer must not invent the hidden segment.
- A root `MovementEvent.path` is never copied for a non-owned actor. A visible
  path is reconstructed from retained committed steps.
- Direct arcs and jumps require every disclosed route coordinate/elevation
  needed by that trajectory. Otherwise they degrade to authorized endpoint
  state changes, not fabricated continuous motion.
- Opportunity attacks remain child events generated by mechanics. A visible
  opportunity-attack child may survive a hidden movement parent through the
  player-safe graph quotient.
- `from_elevation_feet` and `to_elevation_feet` are disclosed with their
  corresponding authorized endpoints. Tile elevation comes from disclosed
  terrain snapshots.

Elevation remains an engine spatial fact and a renderer pixel offset. This
study does not add 3D line-of-sight calculations. Mouse/grid debugging may
show elevation only for an authorized/disclosed tile.

## 15. Combat-log reduction

Event and log reduction must use one disclosure/evidence policy.

### 15.1 Same view principle

Objective and subjective logs use one `CanonicalCombatLogView` structure.
Keeping a separate log view from an event view is justified because the
engine already has an independently indexed log journal and standalone logs.
It is not objective/subjective model duplication.

Each canonical log node contains a safe entry kind, immutable structured
facts, child nodes, a projection-native opaque `log_view_id`, and an optional
player-safe `parent_log_view_id`. Objective and subjective formatters are the
same. Raw objective log index, source event UUID/index, source lineage, and
terminal source provenance are privileged audit facts and never appear in the
ordinary log node or presentation batch.

### 15.2 Format after censorship

The objective diagnostic may retain the engine's original compact/verbose/
detailed prose as privileged evidence. The subjective log must not start with
that prose and string-replace hidden names or UUIDs.

Instead:

1. normalize known entry kinds into explicit fact atoms;
2. apply the same participant, position, ownership, and occurrence policy as
   the corresponding event;
3. censor/reparent child nodes;
4. recompute aggregates from retained children;
5. render compact/verbose text from the censored structured facts.

This prevents leaks through arbitrary dict keys, nested values, prose,
counts, damage totals, save summaries, and hidden child cardinality.

### 15.3 Tree rules

- a fully hidden tree produces no subjective log node;
- a visible child under a hidden parent is promoted to the nearest safe
  grouping/root;
- a retained multi-target parent recomputes counts, damage, save totals, and
  text from retained children;
- location evidence never implies identity;
- a controlled participant receives its direct private consequence even when
  the counterparty remains anonymous;
- root movement geometry is reconstructed from retained committed step child
  facts;
- standalone entries require an explicit entry-kind normalizer and may have no
  event provenance.

Objective log indices remain the private alignment key. The reducer privately
maps each objective index to zero or one retained opaque log view and reparents
visible descendants through projection-native IDs. The subjective ordinary
payload never reveals objective slots, skipped slots, source lineage, or
terminal source-event provenance.

## 16. Hidden ordering, batches, and acknowledgement

### 16.1 Do not send one placeholder per hidden event

A hidden event maps to no ordinary view. Sending a redacted placeholder would
leak event existence and count. The private audit records the hidden source
slot and reason.

### 16.2 Opaque presentation batches

The mechanics coordinator retains:

```text
generation + exact source range <-> opaque presentation batch_id
```

The presentation payload needs only:

```text
batch_id + canonical censored event/log views
```

The presentation engine acknowledges `batch_id`. The coordinator then advances
its private contiguous source cursor. Privileged debug panels may show source
ranges and cursor gaps; ordinary scene, cue, badge, and log code cannot read
them.

An entirely hidden mechanics batch produces no renderer payload. The private
source-coverage ledger marks it as zero presentation work. Its source slots
become contiguous/acknowledged only after all earlier delivered work has a
terminal receipt. This preserves player decision gating without revealing a
hidden event count, hidden batch count, or hidden decision timing.

This is safer and simpler for a future SDK than exposing objective source
indices as part of every subjective view.

### 16.3 Coverage receipts

There are two related ledgers:

- private source coverage: every objective slot becomes semantic, lifecycle
  collapsed, hidden, or otherwise intentionally excluded;
- presentation coverage: every delivered canonical view becomes animated,
  state-applied, badge-fallback, or intentionally silent.

The coordinator acknowledges the source range only after every delivered view
has a terminal presentation receipt. Hidden and lifecycle-collapsed source
slots are resolved privately and never become visible fallback badges.

## 17. Presentation boundary

Presentation receives only censored canonical views and opaque batch identity.
It may build its own cursor-bounded scene model, animation cues, text, and
receipts. It may not import or query:

- `Entity`, `GridMap`, `Encounter`, controllers, or mechanics actions;
- `EventQueue` or raw `Event` subclasses;
- live `Senses` or spatial registries;
- objective catalogs, source captures, or objective logs;
- projection evidence or audit mappings.

The same event/log formatters can render full-knowledge views in the
privileged diagnostics rail and censored views in the party rail. The scene
consumer receives only the latter instance set.

A missing presentation mapper is not a privacy failure because its fallback
badge is built from already-reduced facts. A missing reduction policy is a
privacy failure and must stop the run.

## 18. Laws and proof obligations

The implementation must prove:

### 18.1 Structural laws

- **Full identity:** full-knowledge censorship leaves a normalized view
  unchanged.
- **Idempotence:** applying the same censorship twice changes nothing.
- **Determinism:** the same generation, objective batches, controlled IDs, and
  policy produce byte-identical views and audit decisions.
- **Closed-batch causality:** output through a batch depends only on objective
  facts through that batch.
- **Closed-batch composition:** reducing consecutive closed batches equals
  sequential reducer composition with carried memory.
- **Ordering:** emitted views retain semantic source order; delayed disclosure
  is ordered at authorization, not historical origin.
- **Graph closure:** every parent ID names a delivered view in the same retained
  graph; there are no hidden/dangling parents or cycles.
- **Full-view dominance:** every subjective path/value exists in the matching
  full-knowledge canonical view at the same delivery boundary, except that a
  subjective `SpatialEffectStateFact` may be the exact `<=effect` ordered
  cell-subset defined in section 6; its identity/content/layer are unchanged.
- **Effect projection replacement:** a changed previously delivered effect set
  emits one reset followed by its nonempty current party union, or reset alone
  when empty; a never-disclosed empty set emits nothing.
- **No invention:** every disclosed value is an explicit objective fact or a
  deterministic function of disclosed facts.

### 18.2 Privacy laws

- **Default deny:** an unregistered event kind or fact path emits no payload
  and fails the run.
- **Noninterference modulo reviewed declassification:** compare two executions
  with identical admitted public inputs and identical authorized
  evidence/declassification outputs at every delivery boundary. Changing only
  still-hidden objective internals cannot change subjective bytes, output
  cardinality within an opaque batch, text, cue choice, timing class, or asset
  selection. A hidden mechanic may legitimately change later output only
  through an explicit reviewed release such as a controlled
  `SensoryUpdateEvent`, authorized occurrence fact, or direct controlled
  consequence; the released fact and its authorization boundary then differ,
  so the executions are outside the equal-declassification premise.
- **No hidden cardinality:** censored collections and aggregates reveal only
  retained elements.
- **Identity/location separation:** identity grants never grant coordinates,
  and coordinate grants never grant identity.
- **No live recovery:** presentation and reduction replay succeed with live
  registries made inaccessible after capture.
- **No objective fallback:** errors never substitute full objective values.

### 18.3 Party laws

- direct party reduction equals a field-wise join of individual observer
  reductions;
- removal from observer A cannot remove a current fact retained by observer B;
- observer-relative effective light remains attributed until the scene derives
  the reviewed party rule;
- selected-character changes do not alter the party stream.

### 18.4 Memory laws

- hidden objective changes do not mutate player memory unless and until an
  admitted declassification event releases a resulting fact;
- the presentation scene's explored terrain retains the last disclosed value
  outside vision without duplicating that value in reducer observer state;
- current contact/location is revoked when the sensory delta removes it;
- current persistent-effect cells are revoked when their visual-cell authority
  or passive-perception eligibility is removed, using reset/replacement of the
  joined party set so the other controlled observer's contribution survives;
- visual-access replay replaces the stored normalized integer exactly on a
  changed flag and leaves it untouched otherwise;
- reacquisition discloses the then-current catalog fact;
- later disclosure never rewinds presentation acknowledgement.

## 19. Required test scenarios

The minimum proof suite should include:

1. full-knowledge identity and censorship idempotence for every admitted event
   family;
2. unauthorized-value canaries in names, UUIDs, descriptions, context, nested
   item/entity/condition data, status text, behavior IDs, and log dictionaries;
3. cold world event before actors, followed by incremental tile disclosure;
4. a tile changed unseen, retained old fog memory, then current value disclosed
   on reacquisition;
5. visible tile with hidden contents;
6. visible wall/boundary contact that blocks the cells beyond it;
7. two adjacent tile-owned wall objects remaining distinct;
8. invisible entity contact removal and Truesight/See-Invisible reacquisition;
9. magical darkness with ordinary sight, darkvision, Devil's Sight, and
   Truesight;
10. blindsight/tremorsense contact rendered without visual appearance;
11. observer A loses a cell/contact while observer B retains it;
12. controlled target damaged by an unidentified source;
13. hidden nonparticipant combat with no subjective view or badge;
14. non-owned committed movement with both endpoints authorized, one endpoint
    missing, and a hidden middle segment;
15. jump/direct-arc geometry with incomplete position evidence;
16. visible opportunity attack under a hidden movement ancestor;
17. hidden parent log with visible child and aggregate recomputation;
18. arbitrary nested log canaries and no objective prose reuse;
19. standalone log with no event index;
20. completely hidden batch producing no renderer delivery while private
    coverage still advances contiguously after earlier work;
21. registry access patched to raise during reduction replay and presentation;
22. a deliberately unknown event/fact failing closed before enqueue;
23. future wire encode/decode, when introduced, preserving the exact canonical
    censored view without objective/subjective conversion families.
24. `MovementEvent`, `JumpEvent`, and `TraverseConnectorEvent` sharing
    `EventType.MOVEMENT` while dispatching to three different canonical kinds;
25. every admitted path accepting only its frozen value member, with unknown
    paths, extra record fields, arbitrary dictionaries, and wrong union members
    failing before enqueue; plus roll result retained while owned roll detail
    is removed, damage amount/type authorized independently, and equipment
    appearance retained without item identity;
26. paired noninterference executions with equal declassification producing
    identical bytes/cardinality, plus a hidden cause that changes output only
    through a later admitted sensory release;
27. retained and hidden nested log nodes proving ordinary log IDs/parents are
    projection-native and objective indices, lineage, and source provenance
    never enter presentation bytes.
28. visible object and connector removal tombstones deleting scene/catalog
    state, with tile create/remove enum operations failing because they are not
    admitted by the MVP contract.
29. one saving/check parent plus its typed roll-result child producing one roll
    presentation and one outcome, one positive `TakeDamageEvent` plus
    `DamageAppliedEvent` producing one applied-damage presentation, and a
    canceled take-damage parent producing only the cancellation cue;
30. entity creation equipment snapshot followed by item-location equip/unequip
    facts and redundant concrete equipment action cues, proving one slot-state
    authority and no nested stale equipment copy; plus drop, pickup,
    replacement/displacement, and equipment-overflow-to-floor transitions
    proving that each item floor transition produces exactly one visual state
    atom from `ItemLocationStateEvent` while spatial item placement remains
    geometry/sensory-only;
31. two overlapping same-content spatial-effect instances proving distinct
    lifecycle projection references and exact-instance removal, plus a
    source-less spatial interaction proving a valid transient cue with no
    fabricated layer, content, identity, or catalog mutation; plus a public
    effect created outside vision and later disclosed as operation-neutral
    current state on visibility/reacquisition, partial-footprint visibility
    revealing no hidden cells while proving `<=effect` identity/idempotence, a
    concealed effect withheld until the exact passive-perception or `REVEALED`
    boundary, passive perception later falling to/below the DC, a footprint
    moving wholly out of authorized cells, two-observer retention when only one
    loses access, explicit reset-only versus reset-plus-replacement behavior,
    and no historical operation replay;
32. visual access changing with no simultaneous visible-cell delta, then
    replaying subsequent sensory updates, proving exact replacement on a true
    changed flag, no mutation on a false flag, and fatal rejection of a true
    flag with no after-value; the ordinary first update at unchanged value `1`
    must also replay against the frozen cold seed without requiring an atom.

## 20. Minimal implementation shape implied by the study

The future implementation should need only these conceptual pieces:

1. an explicit family normalizer from frozen mechanics events to full
   canonical fact views;
2. one event-built objective fact catalog;
3. one replay state for each of the two controlled observers;
4. one fact-path disclosure policy shared by event and log reduction;
5. one stateful reducer producing censored canonical views;
6. one private projection audit/coverage ledger;
7. one reduced-batch queue using opaque batch IDs;
8. one presentation scene reducer consuming only reduced views.

This does not justify per-event objective/subjective classes, a subjective
`EventQueue`, a new event bus, a mapper hierarchy, a journal service, a
controller/service layer, a compatibility facade, or server-shaped transport
contracts.

## 21. Known gaps and their treatment

### 21.1 Missing explicit participant declarations

Several event families carry additional UUID fields not covered by base
source/target participation. Explicit normalizers must not assume those UUIDs
are authorized. The admitted MVP families can use reviewed field rules. A
later generic policy should add/validate typed participant declarations at the
engine event boundary rather than infer from arbitrary field names.

### 21.2 Free-form strings and context

`status_message`, descriptions, combat-log prose, and `context` may embed
hidden identities or mechanics. They are objective-only unless a family
normalizer constructs a safe semantic value from typed fields. Do not attempt
generic string sanitization.

### 21.3 Per-cell visual modality

Effective brightness is replayable; full darkvision/Truesight visual styling
is not. Brightness-only rendering is accepted for the MVP. A typed sensory
event enrichment is required before richer styling.

### 21.4 Appearance vocabulary

The engine provides semantic entity/item/tile facts, while the future
`game/` asset resolver maps those facts to Neuroclient/map-editor assets. The
reducer discloses semantic appearance facts; it does not contain asset paths or
renderer layer objects.

### 21.5 Spatial-effect concealment after-value

`SpatialEffectChangeEvent` does not currently carry `condition_stealth_dc`, so
the reducer cannot distinguish a public persistent effect from a concealed
hazard without a forbidden live condition lookup. Before the MVP reducer is
implemented, the event must gain one required frozen
`condition_stealth_dc_after: Optional[int]` field populated by the condition at
every lifecycle completion. `None` means no concealment; an integer uses the
existing strict rule `dc < observer_passive_perception`. The normalizer stores
this value only in the private objective effect-catalog entry beside the
operation-neutral `SpatialEffectStateFact`; it is never an ordinary atom.
`REVEALED` carries `None` after the one-way reveal. Removal deletes the entry.

Detection by passive perception is current and non-monotone, matching
`is_hazard_perceived_by`: if an observer's replayed passive perception falls to
or below the DC, that observer's cells are no longer authorized and the party
reset/replacement rule runs. The global `REVEALED -> None` transition is
one-way, so an effect revealed that way does not become concealed again.

This is an event sufficiency repair, not a renderer/reducer query seam. Without
it, encounter preflight must reject every scripted action able to create a
persistent spatial effect; content allowlists or guessed public-effect tables
are not acceptable substitutes.

## 22. Decisions recommended for the MVP

| Decision | Recommendation |
|---|---|
| Canonical representation | One immutable atomized event-view type; no literal censored mechanics Event |
| Objective/subjective types | Same event view and same log view structures |
| Unknown values | Omit unauthorized atoms; infer anonymous roles from safe occurrence atoms |
| Redaction markers | Privileged comparison audit only |
| Map bounds | Public for the local MVP |
| Terrain memory | Retain last disclosed terrain/elevation in fog |
| Dynamic contents outside contact | Do not render as current truth |
| Party sensory merge | Preserve both controlled sensory streams; derive union in scene state |
| Party effective light | Highest current observer-effective light for shared display |
| Nonvisual contact | Abstract contact marker; no visual appearance layers |
| Player roll detail | Disclose direct/public outcome and admitted roll result; keep hidden modifiers/DCs unless owned |
| Hidden enemy turn | No turn view unless actor/occurrence is authorized |
| Hidden batch | No renderer payload; private zero-work source disposition |
| Acknowledgement | Opaque batch ID publicly; source range privately |
| Log prose | Render after structured censorship; never sanitize objective prose |
| Missing policy | Fail closed and fatal |

## 23. Required amendments to the accepted MVP plan

If this study is accepted, the MVP plan should be amended and revalidated in
these reduction-specific places before implementation:

1. `ReducedPresentationBatch` should expose an opaque `batch_id`, not the
   objective source cursor range, to ordinary presentation code. The
   coordinator and privileged diagnostics retain the range mapping.
2. presentation receipts should key ordinary work by canonical `view_id` and
   `batch_id`; private source coverage maps those receipts back to source
   slots.
3. the canonical view should use atom presence/absence rather than carried
   redaction sentinels. Redaction labels stay in the objective comparison
   audit.
4. subjective bootstrap is incremental: world bounds first, then catalog-backed
   tile/object/entity/persistent-effect disclosure through controlled sensory
   events.
5. the two controlled `SensoryUpdateEvent` streams remain distinct canonical
   views; party union is derived from their replayed states.
6. subjective combat-log strings are formatted from censored structured log
   views, not copied from `CombatLogEntry` prose.
7. the reducer must explicitly admit event families and fact paths; unknown
   inputs fail before enqueue.
8. ordinary combat-log views use projection-native opaque IDs and player-safe
   parent IDs. Objective log indices, source event indices/UUIDs, lineage, and
   terminal source provenance remain solely in privileged audit mappings and
   are removed from `ReducedPresentationBatch`.
9. implementation uses the exact closed canonical kinds, atom paths, value
   records, source classes, operation variants, and appearance vocabulary in
   section 5.2. Scenario preflight must select only the admitted hero/goblin
   appearance definitions or stop for a reviewed amendment.
10. the presentation contract records singular fact ownership for typed roll
    children versus check parents, `DamageAppliedEvent` versus
    `TakeDamageEvent`, and `ItemLocationStateEvent` versus equipment action
    cues; object/connector removals use required previously disclosed
    projection-reference tombstones. The same contract makes
    `ItemLocationStateEvent` the sole item floor visual-state owner while
    spatial item placement remains geometry/sensory-only.
11. persistent spatial-effect lifecycle state uses an identity-bearing closed
    record, while source-optional interactions use a separate transient closed
    record and cannot mutate the effect catalog by themselves. Add the required
    `condition_stealth_dc_after` lifecycle after-value from section 21.5 and
    admit operation-neutral current effect state for exact visibility,
    passive-perception, and reacquisition disclosure. Freeze
    `SpatialEffectStateFact.positions` as the sole reviewed subset morphism and
    use projection-native `spatial.effect_reset` for explicit party-union
    replacement/revocation.
12. controlled visual-access changes are explicit canonical after-values with
    the exact changed-flag replay law and cold seed in sections 7.2 and 11.3.

These changes preserve the accepted authority, timing, queue, encounter,
geometry, rendering, diagnostics, and coverage goals. They narrow the
reduction boundary and remove future SDK duplication.

## 24. Acceptance boundary

This study is ready for review when reviewers can answer yes to all of the
following:

- Is objective/subjective duplication eliminated without weakening mechanics
  event invariants?
- Can the stream replay from cold events without live world queries?
- Are late revelation and hidden changes handled causally?
- Are two controlled observers joined per fact rather than per event?
- Are tile, contents, walls, light, contacts, identity, and position distinct?
- Can invisible and special-sense contacts be represented without inventing
  visual facts?
- Are paths derived from authorized committed steps?
- Are hidden parents and hidden batches handled without dangling causality or
  payload leakage?
- Are combat-log aggregates and prose produced only after censorship?
- Does every unknown policy fail closed?
- Is the design smaller than the deprecated server replication stack?
- Can a future SDK serialize the same censored view directly?

Until this study is accepted and the material plan amendments are revalidated,
the `game/` MVP implementation remains blocked.
