# Spatial Effect Architecture

Status: the bounded architecture and first new-content tranche are implemented.
Ground, cloud, and field owners; exact indexing; anchors; typed lifecycle and
interaction events; material transformations; observer-safe player/AI facts;
presentation cues; combat logs; replay transport; direct spike traps; oil and
fire; all migrated spell zones; same-material overlap arbitration; and
source-owned aura memberships now use one runtime path. Exact condition-family
arbitration retains independent leases, never lets a weaker source reduce an
active DC/caster-level-derived effect, and promotes the strongest remaining
lease. Entangle and Evard's Black Tentacles are the first newly enabled spells.
The maintained spatial, restraint, complete spell-family, bootstrap, condition
effect, action-identity, typed-AI policy, and AI runtime/performance suites are
green. Generated Python/TypeScript contracts and the five public
Entangle/Black-Tentacles icon bindings are frozen and checked. The only
remaining release operation is downstream normal-port validation and the
coordinated server restart after NeuroClient accepts the handoff. Moonbeam and
the broader surface/wall content backlog remain intentionally future content,
not parallel architecture.

This document owns the cleanup that began when the subjective projector was
found serializing arbitrary placed `BaseBlock` attributes.  The immediate
symptom was duck typing.  The underlying problem is larger: persistent spatial
phenomena currently have no domain owner.

The target is one exact runtime path for surfaces, clouds, and magical fields.
It must preserve the existing event/condition engine, spatial-handler
performance, subjective-information boundary, and content identity system.  It
must not turn non-items into `BaseItem`, hide imports, or leave the current zone
and trap paths running in parallel.

## 1. Findings in the current source

### 1.1 `SpatialRegionController` is useful machinery attached to the wrong owner

`dnd/tile_conditions.py::SpatialRegionController` already implements much of the
required runtime:

- one position-indexed handler per effect trigger, not one handler per tile;
- delta updates when a region moves;
- terrain-cost modifiers;
- illumination and obscurement modifiers;
- linked tile marker conditions;
- entry, exit, and turn-start effects;
- cleanup through the condition lifecycle.

Every spell zone is nevertheless installed as an active condition on its
caster.  The caster is the source and may control the duration, but the caster
is not the spatial phenomenon.  This creates several consequences:

- zone lookup scans entities and condition names/types;
- moving and transforming a zone mutates a condition stored on an unrelated
  creature;
- an ownerless physical surface such as spilled oil has nowhere honest to live;
- a tile marker is asked to represent both observed footprint and runtime
  identity;
- environment duration advances through caster turns or per-tile markers
  instead of one world-owned effect lifecycle.

Concentration is a lifetime dependency.  It is not spatial ownership.

### 1.2 The spike trap is a second runtime path

`dnd/tiles.py::create_spike_zone` manually creates tiles, a shared spatial
handler, and `SpikeTrapCondition` markers.  `PullLeverAction` then stores and
removes raw handler and tile UUIDs.  This duplicates the zone machinery and
lets an interaction know internal registration details.

The lever should identify and deactivate one spatial effect.  The effect should
own its handler, footprint, markers, reveal state, and cleanup.

### 1.3 Environmental interactions are fragmented

The engine currently has three separate event families:

- `FireExposureEvent`;
- `ExposedFlameEvent`;
- `WindExposureEvent`.

`WebZone` and cloud zones listen with global `EventHandler` registrations and
then inspect positions themselves.  `SleetStormZone` separately scans floor
objects and carried/equipped items to douse exposed flames.

`FireExposureEvent` has no production constructor.  Its only producer is a
synthetic test.  Consequently the implemented Web-burning branch is unreachable
in normal gameplay.

The queue already has an O(1) spatial index, but it only uses it for a closed
set of `SpatialChangeEvent` types.  Environmental interactions carrying
positions therefore bypass the index and force each effect to perform its own
geometry filtering.

### 1.4 Oil Barrel behavior was lost behind false coverage

The current authored Oil Barrel is a normal destructible environment item with
12 HP.  Destruction only removes it.

The archived lifecycle test contained an `OilBarrel` that applied a three-round
`Oily` condition to its cell and four orthogonal neighbors.  The maintained
coverage ledger maps both oil-specific historical cases to
`test_destroy_hook_can_use_floor_context_before_cleanup`, which does not create
an Oil Barrel, oil, or any tile condition.  The ledger therefore claims
behavioral coverage that does not exist.

The replacement must be a real engine regression:

1. damage destroys the physical barrel;
2. destruction causally creates an oil ground effect;
3. the oil has exact authored identity, geometry, duration, and attribution;
4. later fire can transform the oil into fire;
5. the whole result is present in objective events, subjective state, combat
   log, replay, AI knowledge, and presentation.

### 1.5 `BaseItem` currently conflates physical possessions and world objects

Physical barrels, doors, chests, and fixtures are currently represented by
non-pickable `BaseItem` instances.  That is an existing broader ontology issue,
but it does not justify making a flame, cloud, wall of fire, or puddle an item.

The current temporary conversion of `ContinualFlameObject` to `BaseItem` is not
the intended design.  Continual Flame is the first migration target for the
spatial-effect authority.

Useful classification rule:

- inventory/equipment or tangible interactive/destructible object:
  item/world object;
- targetable body with HP, movement, turns, or actions: entity/creature;
- persistent region whose mechanics are membership, terrain, visibility,
  light, or environmental transformation: spatial effect.

Examples:

- Heroes' Feast remains an interactable usable world item;
- an Oil Barrel remains a physical destructible object;
- oil spilled by that barrel is a ground effect;
- Wall of Fire is a field;
- Wall of Stone is a collection of destructible blocking objects;
- Flaming Sphere is a creature/entity;
- Guardian of Faith is not an inventory item and should be assessed as a
  non-targetable blocking spatial construct plus field;
- Continual Flame is a persistent light-emitting spatial effect.

### 1.6 Runtime duplication is broader than the common zone base

The current census contains:

- fourteen subclasses of `SpatialRegionController`;
- `GlobeZone`, which independently computes geometry, installs global spell and
  condition blockers, and uses `SpellProtectionRegistry`;
- `AntimagicFieldZone`, which independently computes/moves geometry, installs
  four global handlers, and owns its own suppression membership bookkeeping;
- `create_spike_zone`, which independently creates the footprint and handler;
- `GuardianOfFaithObject`, which independently owns one spatial aura handler.

Several common-zone subclasses then add bespoke global handlers on top:

- Web fire and one-round burning aftermath;
- Cloudkill and Incendiary Cloud movement;
- Spirit Guardians following/membership cleanup;
- Stinking Cloud wind dispersal;
- Sleet Storm item/flame scanning;
- Silence spell blocking and membership cleanup;
- Gust of Wind persistent wind publication.

This is not merely subclass customization.  Geometry ownership, membership,
movement, environmental interaction, and cleanup are each reimplemented in
multiple ways.

### 1.7 The missing world owner has encouraged rules shortcuts

`Grease` is marked concentration despite its own SRD-facing documentation
stating that it is non-concentration.  `Daylight` likewise says it uses
concentration only “for cleanup convenience.”  These are lifecycle hacks:
caster-owned concentration is being used because no independent timed world
effect exists.

The migration must restore the intended authored lifetime for each effect.
Fixed/permanent effects live independently; only genuinely concentrating spells
link their controller to `Concentrating`.

Additional measured inconsistencies to close during migration:

- initial occupants are processed manually by individual spell actions instead
  of one effect-creation trigger;
- Fog Cloud, Darkness, and Daylight modify light but do not all expose an exact
  tile/effect identity;
- Daylight finds overlapping Darkness by scanning every entity and narrowing a
  caster-owned condition class;
- turn-start/turn-end semantics vary by implementation and Grease currently
  implements turn start despite its own description requiring turn end;
- moving fields and clouds use global movement/turn handlers rather than one
  effect-owned movement policy;
- per-tile duration ticking is available even though shared-zone markers should
  not own the region lifetime.

## 2. External-system requirements

The research comparison used Larian's official Divinity Engine documentation
and official DOS2 material, plus the game-data-backed BG3 community wiki where
no equivalent official mechanics manual exists.

Both BG3 and DOS2 require at least three independently occupiable categories:

1. ground surfaces: oil, grease, fire, ice, water, webs;
2. clouds/volumes: fog, steam, poison gas;
3. freely overlapping fields: Moonbeam, Hunger of Hadar, Silence, Darkness,
   Wall of Fire, Globe of Invulnerability.

The architecture must therefore support:

- ground and cloud material layers with explicit overlap/replace/transform
  policy;
- multiple freely overlapping fields;
- exact cell footprints and delta movement;
- fixed, permanent, concentration-linked, and explicitly removed lifetimes;
- create, enter, leave, start-turn, end-turn, distance-travelled, periodic,
  transform, and removal hooks;
- per-target throttle/re-entry state;
- movement cost and hazard valuation with movement-mode/immunity bypass;
- independent vision, projectile, propagation, illumination, and obscurement
  effects;
- typed ignite, douse, freeze, melt, electrify, vaporize, disperse, and cleanse
  operations;
- cell-local attribution or region splitting when transformed/merged cells
  have different creators;
- interaction with both creatures and physical world objects;
- exact observed/remembered subjective facts for players and AI.

Not required now:

- fluid simulation;
- continuous gas physics;
- voxel volumes;
- every blessed/cursed DOS2 surface combination;
- a concrete subclass for every authored surface or spell.

## 3. Chosen domain model

### 3.1 Dependency-neutral types

Add `dnd/core/spatial_effect_types.py` as a cold leaf.  It may contain only
enums and immutable value models:

- `SpatialEffectLayer`: `GROUND_SURFACE`, `CLOUD`, `FIELD`;
- `SpatialEffectOccupancyPolicy`: `EXCLUSIVE_TRANSFORMING`, `OVERLAPPING`;
- `SpatialEffectTriggerKind`: create, enter, leave, turn start, turn end,
  movement interval, round tick, interaction, removal;
- `SpatialEffectOperation`: ignite, douse, freeze, melt, electrify, vaporize,
  disperse, cleanse, deactivate;
- `SpatialEffectRemovalReason`;
- typed attribution, potency, movement, visibility, light, duration, and
  presentation state;
- a closed observer-safe spatial-effect snapshot.

This module must not import `Entity`, concrete conditions, content registries,
runtime services, or server DTOs.

### 3.2 Runtime identity and layer classes

Add a high-level runtime module whose ownership is explicit:

```text
BaseBlock
  SpatialEffect
    GroundEffect       (GROUND_SURFACE)
    CloudEffect        (CLOUD)
    FieldEffect        (FIELD)
```

These are layer authorities, not one class per spell/material.  Authored
definitions and registered behavior supply the rules.

One effect owns:

- encounter-local UUID;
- exact `ContentRef`;
- current definition/material state;
- layer and occupancy policy;
- occupied positions;
- creator/source attribution and originating event/action lineage;
- potency/save provenance;
- duration/lifetime state;
- presentation revision;
- controller condition;
- trigger registrations;
- cleanup and transformation state.

`source_entity_uuid` remains causal attribution where the existing `BaseBlock`
contract requires it.  It does not mean the source owns the effect.  Static map
effects may use an authored environment source; a barrel-created effect retains
the barrel/destruction attribution even though the barrel no longer exists.

### 3.3 Anchors and auras

`SpatialEffectAnchorKind` is a cold mechanical policy, not a new world layer:

- `FIXED_POSITION`: the footprint remains at its authored world coordinates;
- `ENTITY`: the footprint follows one exact entity UUID;
- `WORLD_OBJECT`: the footprint follows one exact physical object UUID;
- `INDEPENDENT_MOVABLE`: an action or autonomous rule moves the effect without
  attaching it to another runtime block.

The runtime owner stores both the authenticated anchor kind and, for attached
effects, its exact anchor UUID.  Attached movement is observed from the
authoritative spatial event and routed to the controller's typed
`relocate_anchor()` capability.  The effect owns this one movement handler,
publishes one causal footprint delta, and removes the handler on retirement.
Spell and feature controllers never install their own follow-caster handler.

This deliberately follows the already-proven carried-light design:

```text
anchor movement event
  -> attached emitter/effect owner
  -> delta footprint/light update
  -> causal spatial fact
  -> observer recomputation and effect-specific occupant mechanics
```

An aura is therefore an entity-anchored `FieldEffect`, not a fourth layer and
not a special `Aura` base class.  Different aura rules remain different
controllers:

- emitter-only auras such as carried light update sensory state;
- membership auras such as Spirit Guardians and Antimagic Field apply
  enter/leave/retained-occupant mechanics;
- query auras such as Leadership and Draconic Presence affect later rolls or
  turn starts within their current footprint.

Spirit Guardians is the first acceptance case.  This engine intentionally uses
the requested BG3-style moving-aura rule: moving the field onto a hostile
creature is an explicit `EFFECT_ENTERS_OCCUPANT` moment.  That moment, ordinary
creature entry, and turn start share one effect/target/turn admission fence, so
one sweep may affect many creatures but never damages the same creature twice
in one turn.  Antimagic Field uses the same generic attached movement owner but
retains its suppression-specific membership delta.

Completed aura/anchor acceptance:

- Spirit Guardians is an entity-anchored field with exact per-aura membership,
  effect-movement enter/leave semantics, and one damage admission per
  effect/target/turn;
- Leadership and Draconic Presence use entity-anchored field owners;
- Guardian of Faith is a fixed blocking field rather than a fake item;
- Continual Flame proves the world-object anchor and retires with its exact
  focus;
- Cloudkill and Incendiary Cloud prove independently movable effects.

Future Paladin and monster auras reuse this contract. They do not require a new
runtime category.

### 3.4 Reuse the condition engine through a controller

Rename and move `SpatialRegionController` to a spatial-effect controller authority.
It remains a `BaseCondition`, but is applied to the `SpatialEffect` block, never
the caster.

This deliberately reuses:

- modifier ownership;
- handler ownership;
- linked tile-condition cleanup;
- duration semantics;
- content behavior binding;
- causal condition application/removal events.

A spell's `Concentrating` condition links to the controller condition hosted by
the effect.  Removing concentration removes that controller through the current
cross-block condition tree.  Removing the primary controller destroys the
effect host.  Removing the effect independently removes the controller, whose
reverse link can apply the existing parent `child_removal_policy`.

This needs one explicit `SpatialEffect` override/hook around condition removal;
it must not use registry inspection, condition-name matching, or imports from a
lower-level component back into `SpatialEffect`.

Ownerless oil simply hosts its own duration controller.  It has no
concentration parent.

### 3.5 Spatial indexing

Introduce one effect-region index keyed by layer and position:

```text
(layer, position) -> effect UUID(s)
effect UUID -> layer + positions
```

Ground/cloud exclusive layers admit one material effect per cell after
transition resolution.  Fields admit multiple effect UUIDs.

The effect/controller performs one synchronized footprint update that owns:

- effect-region index delta;
- EventQueue spatial-handler delta;
- tile modifier delta;
- illumination/obscurement delta;
- spatial/senses invalidation;
- one causal lifecycle event.

No gameplay consumer may separately mutate `affected_positions` or raw handler
positions.  The existing `move_zone()` and `_remove_position_effects()` become
this one transaction boundary.

### 3.6 The effect index owns footprints; conditions own actual conditions

The first audit draft considered retaining `ZoneMarkerCondition` as a projected
footprint.  Deeper inspection rejects that design:

- `BaseBlock.active_conditions` is keyed by condition name, so two same-named
  overlapping effects replace each other;
- field overlap cannot be represented honestly by one marker per name;
- effect duration and identity are duplicated across every tile;
- marker application/removal creates condition lifecycle noise;
- a generic marker identity is not the authored effect identity;
- partial transform/splitting would require mutating many condition trees.

The effect-region index therefore owns:

- cell membership;
- exact effect UUID/content identity/layer/state;
- hazard relationship and stealth/discovery facts;
- observer-safe cell projection;
- movement/path hazard contribution.

`GridMap` stores only dependency-neutral indexed effect state and UUIDs.  It
does not import concrete effect behavior.  High-level producers/projectors
resolve a UUID to `SpatialEffect` with explicit `isinstance` narrowing.

Tile modifiers remain ordinary modifier leases owned by the controller.
Creature conditions remain the authority for actual ongoing creature rules.
`TileEffectCondition` remains available when a rule genuinely conditions a
tile, but generic `ZoneMarkerCondition` and `SpikeTrapCondition` cease to be the
canonical spatial-effect footprint.

Creature membership in an effect is also explicit.  A controller tracks the
exact condition UUID it applied to each affected creature:

```text
effect appears / creature enters / attached effect moves onto creature
  -> admit membership
  -> apply one effect-owned creature condition

creature leaves / attached effect moves away / effect retires
  -> remove that exact condition UUID
  -> normal condition cleanup restores modifiers and handlers
```

The membership condition owns persistent modifiers, immunities, action denial,
or roll interception.  It is distinct from an outcome caused by a trigger:

- Silence Deafened, Spirit Guardians Slowed, Antimagic suppression, Leadership,
  Draconic Presence exposure, and future Paladin auras are membership state and
  end when membership ends;
- Prone caused by Grease, Restrained caused by Web, damage, and failed-save
  effects are outcomes and follow their own rules even after the target leaves;
- difficult terrain, obscurement, and illumination remain cell/effect state,
  not creature conditions.

This makes entity-following auras a generic way to convey ordinary static or
contextual modifiers through the existing condition system.  For example, a
Paladin Aura of Protection field applies an exact membership condition whose
saving-throw modifier derives from the owning Paladin's Charisma; Aura of
Courage applies a membership condition that denies Frightened while the Paladin
is conscious.  The field owns range and membership.  The condition owns the
modifier.  The Paladin class does not inject distance checks into every saving
throw.

Hidden hazard discovery queries the effect index through an exact typed grid
method.  It no longer scans arbitrary tile conditions or mutates a shared
`condition_stealth_dc` to reveal the hazard globally.

### 3.7 Condition reapplication is arbitration, not newer-wins replacement

The current `BaseBlock.add_condition()` implementation applies an incoming
condition first and then removes any existing condition with the same display
name.  That behavior is unsuitable for overlapping spells and auras:

- a weaker incoming effect can lower an already active bonus or save DC;
- leaving the stronger of two overlapping auras removes the condition instead
  of revealing the still-valid weaker effect;
- the replaced source duration and concentration relationship are destroyed;
- condition names are presentation, not an exact stacking-family identity;
- applying the incoming condition before arbitration briefly installs both
  artifact sets and can fire handlers or side effects in the wrong order.

The hard cut introduces an exact application family and a typed policy.  The
family is owned by the condition definition/content identity, never inferred
from its display name.  Every source application becomes a lease with:

- exact condition family/content identity;
- exact source entity and causal effect identity;
- source-specific lifetime and cleanup parent;
- condition-authored potency tuple and explanatory values such as spell level,
  save DC, caster level, or modifier magnitude;
- acquisition order used only as a deterministic equal-potency tie-break;
- the exact condition runtime recipe to manifest if the lease wins.

The initial closed policy set is:

- `REPLACE_EXISTING`: explicitly discard the previous source and install the
  new source; this preserves only rules that genuinely say replacement;
- `REJECT_WHILE_ACTIVE`: retain the incumbent and reject the incoming
  application;
- `REFRESH_DURATION`: retain the same source/effect and reset its remaining
  duration to the authored value;
- `EXTEND_DURATION`: retain the same effect and add an explicitly bounded
  duration increment;
- `MOST_POTENT_ACTIVE`: retain every independently valid source lease but
  manifest only the condition-authored strongest lease;
- `STACK_INDEPENDENT`: retain and manifest independent instances only for rules
  that explicitly stack and expose an aggregation contract.

`MOST_POTENT_ACTIVE` is the normal overlap policy for aura membership and for
same-named effects governed by the D&D most-potent-effect rule.  Its invariants
are:

1. arbitration happens before any incoming modifier/handler/action is applied;
2. a weaker lease never lowers an active DC, caster-level-derived value, bonus,
   radius consequence, or other condition-owned potency;
3. equal potency keeps the incumbent to avoid lifecycle churn;
4. every suppressed lease continues its own lifetime and parent cleanup;
5. removing or expiring the winner promotes the strongest remaining valid
   lease atomically;
6. removing one field membership UUID removes only that field's lease;
7. cleansing/removing the logical condition removes every lease only when the
   cleanse rule targets the entire condition family;
8. promotion does not replay application saves or charge costs; it changes
   which already-admitted source governs the shared effect;
9. source-end consequences remain attached to the source lease and are not
   fired merely because another lease temporarily wins;
10. projection exposes one effective condition plus exact source/potency
    transition facts, not several visually duplicated conditions.

Potency ordering is condition-authored.  There is no global assumption that
spell level always outranks save DC, or that the latest caster wins.  Examples:

- Aura of Protection ranks by the actual Charisma saving-throw bonus.  A +3
  aura entering a creature already covered by +5 is retained but dormant; when
  the +5 lease leaves, +3 becomes effective;
- a save-driven recurring spell may rank first by its authored effect level and
  then by save DC;
- a fixed numerical field ranks by its exact modifier magnitude;
- boolean memberships such as immunity to Frightened have equal potency and
  use stable incumbent selection.

Duration combination is likewise explicit.  Refresh and extension are not
side effects of “same condition applied again,” and neither may reduce a
remaining duration.  An extension contract owns its cap.  A weaker application
cannot overwrite the duration, DC, spell level, or caster level of a stronger
lease.

The runtime representation must keep leases separate from the manifested
`BaseCondition`.  Merely storing several fully applied same-name conditions is
incorrect because their numerical modifiers and handlers would stack.  Merely
calling `cleanup_own_state()` to suppress a loser is also incorrect because
condition-end behavior such as Haste lethargy belongs to source lifetime, not
temporary arbitration.  A lease arbiter therefore admits/ages/removes sources;
the selected manifestation owns ordinary modifiers and handlers.  This is a
condition-engine primitive used by spatial fields, not a registry in the spell
or class layer.

Every arbitration result is an evented fact with a closed disposition:
`applied`, `rejected`, `refreshed`, `extended`, `retained_stronger`,
`promoted`, or `removed`.  It is a child of the applying/removing causal event
and can produce a concise combat-log entry when player-visible.  The frontend
never compares DCs or chooses a source.

## 4. Content system

Add `ContentDefinitionKind.SPATIAL_EFFECT` and
`RuntimeBehaviorKind.SPATIAL_EFFECT`.

Add one typed `SpatialEffectDefinition` and a `spatial_effect_factory`
registration wrapper consistent with item and creature factories.  Content
packs may define effects near the spells, creatures, or objects that create
them.  There is no centralized Python switch over all effects.

The definition owns cold data where practical:

- layer and occupancy policy;
- duration policy;
- movement/hazard/light/visibility capabilities;
- trigger specifications;
- transition profile;
- presentation keys;
- dependencies on applied creature conditions.

Complex effect processors remain registered authored behavior, just as complex
actions and conditions do today.  They emit normal save, damage, condition, and
movement events; they do not mutate creatures directly through a parallel
effect engine.

Add an exact content dependency relation for “creates spatial effect.”  A spell,
action, item destruction behavior, or environment fixture can then expose its
effect identity to tools and the frontend without Python-path or display-name
inference.

## 5. Events, transformations, and combat logs

### 5.1 Spatially indexed event base

Create a typed spatial-event base that returns one or more dispatch positions.
`SpatialChangeEvent`, environmental interaction events, and effect lifecycle
events use it.

`EventQueue` dispatches spatial handlers for every affected position and
deduplicates handlers before execution.  Trigger-indexed global handlers still
run where authored, but Web/oil/cloud interactions no longer scan every active
effect.

No `hasattr`, protocol-by-convention, or arbitrary `get_affected_positions`
duck typing is allowed.  Dispatch narrows against the explicit event base.

### 5.2 One environmental operation event

Replace the parallel Fire/Wind/ExposedFlame paths with one closed
`SpatialEffectInteractionEvent` carrying:

- operation;
- affected positions;
- causal source and parent event;
- optional intensity/duration;
- optional damage/energy provenance;
- optional source content attribution.

Existing fire, wind, cold, lightning, water, and dispel producers publish this
event from their authoritative action/effect path.

### 5.3 Table-driven transitions

A frozen transition registry resolves:

```text
current exact effect definition/state
+ incoming typed operation/context
-> preserve / remove / replace / split / create secondary layer
```

Examples:

- oil + ignite -> fire;
- web + ignite -> remove web cells + temporary fire;
- water + freeze -> ice;
- water + electrify -> electrified water;
- water + vaporize -> steam cloud;
- cloud + disperse -> remove or decrement duration;
- exposed flame + douse -> inactive flame state.

The registry is populated by content declarations at cold startup and frozen
with the rest of the content set.  Runtime code does not compare names or
concrete spell classes.

### 5.4 Causal event tree

Required ordering:

```text
source action / damage / destruction
  spatial-effect create or interaction
    spatial-effect transform/remove/create
      save
      damage
      condition application/removal
```

Entering or starting a turn in an effect instead uses:

```text
movement / turn event
  spatial-effect trigger
    save
    damage
    condition application/removal
```

Create, meaningful transform, trigger consequence, and removal may produce
typed combat-log entries.  Internal tile marker application/removal does not.
The subjective presentation mapper receives exact effect create/transform/
remove/trigger cues or an equally exact reducer/presentation transaction; the
frontend must never infer a surface from a damage type, item name, or combat-log
text.

## 6. Physical objects and the oil-barrel slice

The physical barrel remains a destructible environment object.

`BaseItem.destroy()` must pass its causal event to the exact destruction hook;
the current parameterless `_on_destroy()` cannot attach aftermath to the damage
tree.  All existing overrides will be migrated to the typed signature in one
hard cut.

Oil Barrel acceptance sequence:

1. damage is resolved through the item-damage event path;
2. zero HP produces an exact item-destroyed fact;
3. barrel destruction behavior creates authenticated Oil GroundEffect cells;
4. floor-object removal and effect creation share the destruction parent;
5. oil changes path hazard/presentation but does not block ordinary movement;
6. fire interaction transforms affected oil cells to Fire GroundEffect;
7. transformation preserves creator/transformer attribution;
8. fire emits light and normal damage/condition events;
9. douse/removal cleans only fire-owned state;
10. objective event history, subjective replay, combat log, AI observation, and
    renderer facts agree.

Destruction by fire may resolve directly to the authored explosion/fire branch,
but that is a content rule layered on the same events—not a special case in
`BaseItem`.

## 7. Existing content migration

### Ground surfaces

- static spike traps;
- Spike Growth;
- Grease;
- Web;
- Ice Storm temporary terrain;
- Oil and Fire acceptance effects.

### Clouds/volumes

- Fog Cloud;
- Cloudkill;
- Incendiary Cloud;
- Stinking Cloud.

### Freely overlapping fields

- Spirit Guardians;
- Darkness;
- Daylight;
- Silence;
- Gust of Wind;
- Sleet Storm;
- Globe of Invulnerability;
- Antimagic Field;
- Continual Flame light field.

Some effects combine capabilities without occupying multiple material layers.
For example Sleet Storm is a field that changes ground movement and obscures
volume; it does not need to pretend to be a material cloud.

### Reclassification audit

- Guardian of Faith: migrate away from `BaseItem` unless the final rules audit
  makes it independently targetable/destructible; represent its blocking
  footprint and aura through one spatial construct.
- Heroes' Feast: retain as a usable physical world object.
- future Wall of Fire: field.
- future Wall of Stone/Ice solid segments: destructible obstacles; Wall of Ice
  destruction may spawn a cloud effect.
- future Flaming Sphere: creature/entity with light/aura, not a surface.

## 8. Projection and privacy

### Player replication

Add a closed spatial-effect fact/patch family with:

- runtime UUID;
- safe exact content/presentation ref;
- layer;
- currently disclosed positions;
- current presentation state/revision;
- known hazard/movement/light/visibility capabilities;
- lifecycle operation and causal presentation identity.

Hidden trap cells remain hidden until observer evidence authorizes them.
Remembered effect cells preserve the last observed state; current off-screen
transformations must not leak.

Physical `SubjectiveFloorObject` remains item/world-object projection.
Spatial effects do not enter that union as fake items.

### AI observation

Add exact observer-relative spatial-effect facts.  AI pathing consumes known
hazard/movement consequences from this contract.  It does not query the
objective effect registry or inspect arbitrary item/condition fields.

The current closed `ItemObservationState` work remains valid for actual items,
doors, fixtures, and physical objects.  It must not become the projection type
for effects.

### Objective diagnostics, replay, and editor

Objective state and replay retain complete exact effect identity, attribution,
positions, state, and transitions.  The future map editor authors effect
definitions/placements, not raw handler UUIDs or arbitrary active-condition
dictionaries.

## 9. Performance invariants

- one effect handler per trigger kind, not per tile;
- O(changed positions) footprint moves/transforms;
- O(affected spatial handlers) interaction dispatch;
- one environment duration tick per effect, never per marker cell;
- no global scan of every entity condition for overlapping zones;
- no global scan of every effect for fire/wind at one cell;
- no repeated content lookup or schema validation in hot trigger paths;
- no player/AI projector reflection over runtime objects.

Focused performance tests will compare large overlapping regions and repeated
movement/interaction dispatch against the current handler index.

## 10. Regression-first implementation order

### Current implementation ledger

Completed in the first owner/index slice:

- dependency-neutral ground/cloud/field layer and occupancy enums;
- independent `SpatialEffect`, `GroundEffect`, `CloudEffect`, and
  `FieldEffect` blocks;
- a typed `SpatialEffectController` installation boundary that preflights the
  whole footprint before handlers/modifiers are admitted and rolls back an
  exceptional partial installation;
- a grid-owned layer/position effect index with exclusive-material validation;
- one environment-round duration tick per indexed effect;
- exact `SPATIAL_EFFECT` authored definitions, recipes, construction dependency
  edges, one registry-backed materializer, and cold contract validation;
- condition/hazard projection from indexed effects without tile marker
  duplication;
- exact observer-safe spatial-effect facts on `APITile`, preserving the
  observer's last-seen cell state instead of leaking current off-screen state;
- typed create/footprint/remove lifecycle events with exact effect identity,
  causal parentage, and objective combat-log entries;
- Grease as a 10-round independent ground effect;
- Grease entry and correct turn-end saves;
- Daylight as a 600-round independent field effect;
- Spirit Guardians, Darkness, Insect Plague, Sleet Storm, Silence, Gust of
  Wind, Globe of Invulnerability, and Antimagic Field as independently owned
  `FieldEffect` instances;
- caster-following field movement now moves the effect owner and its index,
  while immobile fields remain anchored independently of their caster;
- Darkness overlap cleanup now resolves indexed effect owners instead of
  scanning entity conditions;
- removal of both false concentration flags from runtime and cold spell
  catalog metadata;
- Continual Flame migrated from a fake `BaseItem` floor object to a permanent
  independently owned light field;
- regressions proving unrelated concentration cannot remove either effect,
  expiration clears modifiers/light/indexes, and the player tile projection
  sees the exact authored controller while the tile owns no copied marker.
- typed `APPEAR`, `ENTER`, `LEAVE`, `TURN_START`, `TURN_END`,
  `MOVEMENT_INTERVAL`, `ROUND_TICK`, `INTERACTION`, and `REMOVAL` trigger
  identities frozen in each exact spatial-effect definition;
- installation-time equality between the cold definition and runtime
  controller trigger/admission declarations;
- one shared effect/target/turn admission fence, keyed by the encounter's
  opaque turn-execution identity rather than marker conditions or condition
  names;
- removal of the bespoke `SpiritGuardiansTriggered` condition and its cleanup
  handler;
- correction of appearance timing: Grease, Insect Plague, and Incendiary Cloud
  process existing occupants, while Web, Cloudkill, Spirit Guardians, and Sleet
  Storm do not treat effect creation as creature entry;
- correction of Insect Plague and Incendiary Cloud to their authored turn-end
  timing;
- typed `SpatialEffectInteractionEvent` dispatch through the spatial index;
- frozen authenticated transition definitions for ignite, douse, and disperse
  behavior;
- Oil Barrel destruction -> Oil GroundEffect -> Fire GroundEffect, including
  cell-local partial replacement and dousing;
- Web -> one-round Burning Web fire through the same transition authority;
- removal of the parallel fire/wind/exposed-flame event families and global
  effect geometry scans;
- Cloudkill, Fog Cloud, Incendiary Cloud, and Stinking Cloud as independently
  owned `CloudEffect` instances;
- Web, Spike Growth, and Ice Storm as independently owned material surfaces;
- exact AI-observation spatial-effect facts derived from observer knowledge,
  without objective registry access in policy code;
- explicit fixed, entity, world-object, and independently-movable anchor
  identities, with fixed and entity-following production acceptance;
- Light, Darkvision, and Jump corrected to their non-concentration SRD
  lifetimes in both runtime behavior and the cold spell catalog;
- exact repeated-condition policy/disposition vocabulary and a constrained
  `MostPotentCondition` lease arbiter that never applies a losing source;
- independently aged source leases, deterministic equal-potency incumbency,
  exact-UUID removal, no-downgrade replacement, fallback promotion, typed
  promotion events, and combat-log evidence;
- Leadership migrated from one global owner-side distance-query handler to an
  entity-anchored `FieldEffect` granting exact ally membership conditions;
- overlapping Leadership fields proven to install one roll modifier, retain
  both source leases, promote the remaining source after movement, and clean
  up on expiry.

Closed since the first owner/index slice:

- the legacy controller/marker/direct-spike paths were deleted rather than
  retained as aliases;
- subjective lifecycle cues and observer-local reducer facts use the typed
  effect identity;
- world-object, entity-following, and independently movable anchors all have
  production consumers;
- same-material overlap uses atomic potency arbitration and exact footprint
  splitting, with rollback after staged failures;
- the public repeated-condition enum contains only the two implemented
  policies (`replace_existing`, `most_potent_active`);
- exact hidden memberships are distinct from the one public manifested
  condition, so three simultaneous sources can be removed/promoted without
  modifier stacking or downgrade;
- continuous membership maintenance happens before first-per-turn consequence
  admission. Re-entering Spirit Guardians in the same turn restores the slow
  but cannot deal its damage twice;
- raw Strength/Dexterity escape checks are typed child events with ability-check
  combat-log entries.

Operational closure completed:

- event and TypeScript SDK generators are current and pass `--check`;
- the TypeScript SDK build and 81-test package suite are green;
- focused player projection, mapper, journal, replay, architecture, and source
  hygiene gates are green;
- exact public icon bindings exist for Entangle, Evard's Black Tentacles, and
  their three escape actions; the imported manifest is authenticated and
  passes `--check`;
- the typed AI policy suite is 97/97 green and the AI runtime/performance suite
  is 58/58 green;
- AoE candidate compaction now queries a pure target-specific footprint key
  instead of cloning a shape per candidate cell;
- the frozen handoff hashes are SDK
  `fa789d0ceaba411b26c39b7e7a811f04da0b80246bda84e3600af9551f3740b7`,
  player replication
  `7a991b0ca4808e788893d2f8ceece46791a984f912e9236f53e09c121881fab3`,
  and event
  `2e7e98cc04b8dee0c8217a7c49d3b0ef78c818f42cff4d59834e27152577ae68`.

The coordinated normal-port restart remains intentionally held until the
frontend reports that it has adapted to this frozen handoff. Broader authored
material combinations and Moonbeam are deliberately separate content work.

### Liquid terrain, wet surfaces, and movement protection

The current engine already has a real but deliberately narrow swimming path:

- `MovementMode.SWIMMING` is distinct from walking, flying, and burrowing;
- `Swim` discovers and executes water-only paths;
- a natural/granted swimming speed avoids the ordinary doubled swimming cost;
- the canonical `water_factory` produces non-walkable, swimmable terrain;
- maintained regressions prove land/water path separation, swimming cost, and
  Freedom of Movement's underwater bypass.

That does **not** make a Water tile the same object as a reactive wet surface.
The hard-cut design keeps structural terrain and transient material separate:

- a Water tile is authored battlefield terrain, navigable through the existing
  swimming mode and `Swim` action;
- swimming is a movement mode, not a spatial effect;
- the `Underwater` entity condition owns underwater-combat penalties; it is
  neither the Water tile nor the wet surface;
- a finite water/wet surface over a navigable tile is a `GroundEffect` with exact identity,
  footprint, attribution, duration, and material transitions;
- standing in a wet surface may maintain a `Wet` manifestation, but `Wet` is
  not equivalent to swimming or being underwater;
- electrified water remains a surface consequence; steam is a `CloudEffect`;
- freezing a puddle replaces that surface with ice;
- a future ice overlay on a Water tile may temporarily permit walking, but
  removing it reveals the unchanged swimmable Water tile beneath it;
- vaporizing a finite wet surface may remove it, while an interaction cannot
  silently erase an authored Water tile.

This requires one exact movement override/contribution seam only when the ice
bridge behavior is implemented. It must not be implemented by changing tile
names, by treating a Water tile as a puddle, or by letting a `GroundEffect`
replace the underlying battlefield definition.

`FreedomOfMovementEffect` already covers the intended categories:
difficult-terrain cost, magical speed reduction, underwater penalties,
magical paralysis/restraint prevention, and a five-foot escape action for
nonmagical Grappled/Restrained sources. Before water transformations are
authored, its three direct booleans must become source-owned capability leases
so overlapping spell/item/class sources cannot remove one another. The
condition-immunity boundary must also match its declared rule: environmental
secondary consequences such as ice slipping, electrified-water damage, Wet,
fire, poison, and visibility are not movement penalties and remain active.

Required focused acceptance:

1. Water tiles are reachable through `Swim` and remain unavailable to ordinary
   walking unless an explicit surface overlay permits it;
2. swimming speed and Freedom of Movement affect swimming cost without turning
   a water cell into walking terrain;
3. `Underwater` remains an explicit entity condition and is not inferred from
   the wet-surface condition;
4. a wet surface applies/removes its exact membership independently of terrain;
5. wet -> ice, wet -> electrified water, and wet -> steam use typed
   interactions and preserve parent/child event causality;
6. freezing a surface never rewrites the underlying Water tile; any future
   walkable ice bridge must use an explicit source-owned traversal override;
7. Freedom of Movement ignores added difficult-terrain cost but still admits
   slipping, Wet, and elemental damage;
8. two independent Freedom-of-Movement-like sources survive removal in either
   order without losing the remaining source's protections;
9. player observation, presentation, combat log, replay, and AI knowledge
   distinguish the terrain medium from the transient material state.

### Newly enabled spell tranche

The independent spell audit found three high-value acceptance consumers:

1. **Entangle — implemented**: overlapping fixed `FieldEffect`, exact 20-foot
   square, difficult terrain, `APPEAR` Strength save, source-owned Restrained
   lease, and raw Strength escape action.
2. **Evard's Black Tentacles — implemented**: overlapping fixed `FieldEffect`,
   exact 20-foot square, difficult terrain, shared first-entry/start-turn
   admission, damage plus source-owned Restrained, and raw Strength-or-Dexterity
   escape actions.
3. **Moonbeam** — independently movable `FieldEffect` with dim light and an
   action-owned move operation. It is deliberately held until movable anchors
   and shapechanger/reversion mechanics are explicit.

No equally clean fourth spell should be forced into this tranche. The tabletop
form of Dancing Lights requires grouped multi-anchors, while the BG3 form is a
stationary concentration light already expressible by the implemented fixed
field/light path. It is optional content, not a reason to add a new runtime
category. Plant Growth requires selected excluded cells and fourfold movement
cost, and wall spells require typed line/ring/panel geometry.

After those consumers, the wall-content order is Wall of Fire, Blade Barrier,
Wind Wall, Wall of Force, Wall of Ice, and Wall of Stone. Wall of Ice is the
important hybrid acceptance case because destruction of a physical segment
causally creates a spatial cold effect.

### Phase 0: measure current gaps

Add deterministic focused regressions that initially fail for the exact current
defects:

- authored Oil Barrel destruction creates no oil;
- the maintained coverage ledger does not measure oil behavior;
- production spell fire cannot reach Web's fire branch;
- spike lever cleanup depends on raw handler/tile UUIDs;
- Continual Flame has no legitimate non-item projection identity;
- effect overlap/removal currently requires caster-condition scans.

Do not xfail them unless they must remain open across a committed boundary.

### Phase 1: core authority

Implement:

- dependency-neutral types;
- spatially indexed event base;
- effect-region index;
- `SpatialEffect`/`GroundEffect`/`CloudEffect`/`FieldEffect`;
- controller-condition ownership;
- effect lifecycle events and cleanup;
- content declaration/factory;
- typed objective, subjective, and AI facts.

Prove dependency direction and zero cycles before content migration.

### Phase 2: migrate existing single-path behavior

Migrate all current zone classes, Spike Trap, and Continual Flame.  Remove
`SpatialRegionController`, direct spike-handler construction, raw lever handler
fields, and the temporary Continual-Flame item declaration.  Do not retain
aliases.

Run focused zone, spell, pathfinding, senses, projection, mapper, replay, and
content tests after each family.

### Phase 3: environmental transformations

Implement the interaction event and frozen transition registry.  Migrate:

- Web fire;
- wind/cloud dispersal;
- Sleet Storm/exposed flame;
- Oil Barrel -> Oil -> Fire.

Add exact event-tree, combat-log, replay, and presentation assertions.

### Phase 4: expressiveness closure

Prove the architecture can represent, without new runtime categories:

1. structural navigable Water tiles plus independent wet surface ->
   ice/electrified water/steam cloud transitions;
2. simultaneous water ground + steam cloud + magical field;
3. moving Moonbeam-like field preserving concentration and DC;
4. different start/end-turn effects;
5. Spike Growth damage per distance travelled;
6. passable Wall of Fire versus destructible Wall of Stone;
7. hybrid wall destruction spawning a cloud;
8. creature summon with aura/light leaving a surface;
9. hidden trap reveal and observer-local memory;
10. AI path revision after create/transform/move/remove.

Only the Oil/Web/spike/current-spell slice needs authored production content in
this tranche.  The remaining cases may be focused test definitions until their
spells are implemented.

### Phase 5: hard-cut cleanup and generation

- delete obsolete projector duck typing;
- delete old environmental event families and global geometry filters;
- delete old zone/condition catalog rows replaced by spatial-effect definitions;
- delete false oil coverage mappings;
- update architecture docs;
- regenerate Python/TypeScript contracts once after the model freezes;
- run focused generators, SDK build/tests, player/objective replay gates, and
  selected engine files;
- coordinate one frontend SDK handoff and one server restart only after green.

### 2026-07-30 water/material closure checkpoint

Implemented source state now enforces the terrain/effect split:

- `water_factory()` remains structural Water terrain. Its swimming cost and
  `Swim` action path are unchanged; no spatial transition rewrites a tile.
- `spatial_effect.material.water_surface` is an independent ground effect
  manifesting source-arbitrated `Wet`.
- typed `FREEZE`, `ELECTRIFY`, and `VAPORIZE` transitions produce exact Ice,
  Electrified Water, and Steam definitions.
- same-layer replacement and cross-layer creation are separate closed
  transition actions. Vaporization removes affected ground cells and creates
  a secondary cloud without relaxing same-layer collision validation.
- Ice owns difficult terrain and a Dexterity slip consequence. Electrified
  Water owns Wet plus first-per-turn lightning damage. Steam owns Wet plus
  cloud-layer obscurement.
- overlapping ground/cloud Wet sources use `MostPotentCondition` leases, so
  retiring either source preserves the other.
- Freedom of Movement contributions and condition immunities are keyed by the
  exact condition UUID. Nonmagical Grappled/Restrained remain present and use
  the authored five-foot escape action; magical forms are rejected. Wet,
  slipping, and elemental damage remain admissible.

The focused regressions own these distinctions. Final generator/SDK gates wait
only for the exact public `condition.environment.wet` asset ledger row and the
remaining projection/contract sweep.

## 11. Required focused gates

At minimum:

- dependency/cycle/source-model architecture tests;
- BaseBlock/condition lifecycle;
- EventQueue spatial handler semantics;
- grid pathfinding/hazard/light/senses;
- item destruction and environment-object content identity;
- spike-zone movement;
- spell-family Web/Grease/Fog/Darkness/Daylight/Silence/Cloud tests;
- subjective observation;
- player world projection, mapper, journal, replay;
- combat-log projection;
- content bootstrap/generator checks;
- TypeScript SDK build/tests.

No full repository pytest invocation is part of this work.

## 12. Decisions that are now closed

- A persistent magical/environmental region is not a `BaseItem`.
- Concentration is a dependency edge, not ownership.
- Oil persists without a creature owner.
- Conditions remain the authority for creature/tile modifiers and cleanup.
- Spatial effects own region identity, indexing, lifecycle, and transformation.
- Effects are classified by gameplay affordance, not by how they look.
- Ground, cloud, and overlapping field layers are distinct.
- Environmental transformations are typed and table-driven.
- Physical objects create/interact with effects through events.
- No name switches, reflection-based projection, late imports, circular
  imports, raw-handler persistence, or client inference.
