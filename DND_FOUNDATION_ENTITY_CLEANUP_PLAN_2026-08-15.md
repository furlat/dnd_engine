# D&D Foundation and Entity Cleanup Plan

Date: 2026-08-15

Status: Phase 1 type-package hard cut completed; Phases 2-5 have not started.

## Overall objective

Build a clean, in-process engine foundation in which one Python process can:

1. create any entity, whether it is a player character, an authored monster,
   or a monster with class levels;
2. run gameplay through the existing engine event boundary;
3. feed those events directly into perspective filtering and the subjective
   reducer;
4. render the resulting subjective state in an in-process client such as
   Pygame;
5. add a server, generated SDK, database, or distributed runtime later as
   optional adapters rather than requirements of the engine.

The engine must not require the deprecated content system, a content registry,
`ContentRef`, recipes, contract hashes, server DTOs, database rows, or frontend
asset identifiers in order to construct and play a game.

The event stream remains the intended source of truth. Python construction
functions are authoring operations that produce engine state and its admission
events; they are not a second persistent representation and will not be
serialized as recipes or operation graphs.

## Why this first step exists

The current engine cannot be cleaned safely by porting all monsters, classes,
items, actions, and conditions simultaneously. The first cut establishes a
small trustworthy foundation:

- one dependency-leaf location for domain types;
- generic base classes that know nothing about content packaging;
- an Entity that owns its actual identity and progression facts directly;
- a direct item identity and construction seam;
- no expansion into action, condition, spell, animation, server, database, or
  frontend-rendering redesign.

This step deliberately creates the stable floor on which later creature,
leveling, event-admission, and Pygame work can be migrated vertically.

## Hard architectural rules

1. No compatibility facades for removed type modules or `ContentRef` fields.
   Imports are updated to the new location and the obsolete definitions are
   deleted.
2. No optional `ContentRef`, dormant content flags, no-op binding gateways, or
   recipe fallback paths are retained in the foundation.
3. Types in `dnd/types/` must be dependency leaves. They may depend on Python,
   Pydantic where a validated value object is genuinely useful, and other
   `dnd/types` modules. They must not import Entity, blocks, actions,
   conditions, content registries, server code, or concrete gameplay code.
4. Entity identity is game data, not packaging metadata.
5. Species, species variant, background, class, subclass, item identity, and
   similar closed authored identities use direct enums or small domain value
   objects, not content references.
6. Player characters and monsters use the same Entity type and the same
   construction seam.
7. Inventory and equipped items remain first-class runtime objects. They are
   not converted into recipe payloads or anonymous Entity components.
8. Concrete actions, conditions, spells, traits, animations, and spatial-effect
   behavior are outside this first cut.
9. The server and database are outside the construction path.
10. Existing user changes and deprecated source directories are preserved.

## Scope A: consolidate domain types under `dnd/types/`

Create one explicit package:

```text
dnd/types/
    __init__.py
    abilities.py
    actions.py
    conditions.py
    creatures.py
    damage.py
    effects.py
    encounter.py
    equipment.py
    items.py
    languages.py
    life.py
    proficiency.py
    progression.py
    rolls.py
    saving_throws.py
    senses.py
    spatial_effects.py
    world.py
```

The starting input is the current set of scattered leaf modules:

```text
dnd/core/action_types.py
dnd/core/condition_types.py
dnd/core/creature_types.py
dnd/core/effect_types.py
dnd/core/equipment_types.py
dnd/core/item_types.py
dnd/core/language_types.py
dnd/core/life_types.py
dnd/core/proficiency_types.py
dnd/core/roll_types.py
dnd/core/saving_throw_types.py
dnd/core/spatial_effect_types.py
```

Pure root-level lifecycle enums such as `EncounterState`, `TurnState`, and
`ControllerExecutionMode` should move when doing so does not pull concrete
Encounter or Controller dependencies into the type package.

The move is not permission to centralize every class whose name contains
"type". Runtime models, actions, conditions, blocks, controllers, and
transform protocols that depend on engine objects stay with their behavior.

`dnd/types/__init__.py` must remain intentionally small. It must not eagerly
import the whole package and recreate import cycles.

### Phase 1 implementation record

Completed on 2026-08-15.

The move was implemented as an ownership correction rather than a directory
rename:

- all twelve retired `dnd/core/*_types.py` module paths plus
  `dnd/core/senses.py` were deleted, with no compatibility modules or
  re-export facades;
- every active production and test import was rewritten to the canonical
  owner;
- `AbilityName`, `SkillName`, and `SavingThrowName` now have one owner in
  `dnd/types/abilities.py` instead of parallel event, block, and durable-content
  vocabularies;
- attack outcomes, roll kinds, advantage, critical, auto-hit, resistance, die
  size, and hit-die size now have explicit leaf owners;
- `EncounterState`, `TurnState`, `ControllerExecutionMode`, and the formerly
  free-text encounter advance result were moved into the type boundary;
- movement mode, light level, cardinal direction, and world-edge channel now
  have one world vocabulary;
- caster progression policy moved out of the progression implementation;
- Dragonborn save and damage aliases were collapsed onto `AbilityName` and
  `DamageType`, with Dragonborn-specific subset validation retained;
- direct callers use enum members rather than leaving string literals behind
  a nominal enum annotation.

The move deliberately split polluted files instead of legitimizing their
pollution:

- `ActionPresentationKind`, visual loadout slots, equipment render layers,
  equipped-visual policy, and the mixed item presentation snapshot live in
  `dnd/presentation.py`, not `dnd/types`;
- their original docstrings, field descriptions, validation, and frontend
  binding information were preserved so the later visual cut does not lose
  authored knowledge;
- `SavingThrowEffectTag` is a neutral leaf, while the `ContentRef`-bearing
  `SavingThrowContext` remains explicitly quarantined at
  `dnd/core/content/saving_throws.py` until the foundation content cut;
- `dnd/types/__init__.py` performs no eager re-exports.

Architecture enforcement now discovers every `dnd.types.*` module, requires a
literal public export surface, proves each exported symbol has one definition,
forbids the retired module paths and former owner re-exports, and constrains
both `dnd.types` and `dnd.presentation` to cold leaf dependencies. A fresh
process imports the complete boundary and verifies that it does not initialize
Entity, blocks, actions, conditions, Encounter, Controller, content, or server
layers.

The detailed audits identified several real inconsistencies that are recorded
but intentionally not changed in Phase 1 because they require mechanical
behavior migration:

- `CostType`, `ActionEconomyCostType`, and connector action-cost subsets;
- the unsound `EquipmentSlot` union, `BodyPart.RING`, and concrete ring slots;
- `WeaponProperty.SIMPLE` and `MARTIAL` acting as categories rather than
  properties;
- `UnarmoredAc` competing with the newer source-owned AC formula mechanism;
- mixed display labels and stable identifiers in enum wire values;
- duplicate action/content effect-disposition enums;
- the authored-content `ConditionSaveAbility` subset, retained until the
  action/condition content pass;
- the shared draconic ancestry vocabulary used by Dragonborn and Sorcerer;
- the lowercase Sorcerer draconic damage subset;
- entity-owned species, variant, background, class, subclass, and level
  identities, which belong to Phase 3 rather than being copied out of the
  durable-content schema prematurely.

Verification for this ownership-only cut:

- 21 dependency-boundary and canonical-ownership tests pass;
- 176 focused engine, event, block, encounter, action-discovery, progression,
  and manual runtime tests pass;
- the complete suite still has the same 182 collection errors caused by the
  already-removed deprecated content system, server, ledgers, and devtools
  modules; this phase introduced no new collection-error category;
- Pyright reports no new argument, assignment, return, undefined-name, or
  unused-import failures in `dnd`; its remaining import failures are the same
  deprecated-content-system breakage, plus one unrelated optional-member
  diagnostic.

### Type cleanup performed during the move

- Keep mechanical enums and validated domain value objects.
- Add direct identity enums needed by Entity and items.
- Do not bless frontend-only renderer types as general engine vocabulary.
- Renderer-only types that cannot yet be removed are quarantined explicitly
  and marked for the later visual-boundary cut; they are not mixed into
  creature, equipment, or item mechanics.
- Update imports atomically. Do not leave the former modules as re-export
  shims.

### Initial identity types

The exact enum members will be derived from the currently authored entities
and premades before editing their callers. The required foundation is:

```python
Species
SpeciesVariant
Background
ClassId
SubclassId
ItemId
ClassLevel
```

`CreatureType` remains a separate rules taxonomy. It does not replace species:
for example, HUMANOID and UNDEAD are broad creature types, while human, goblin,
and orc are authored species identities. We will not invent a false species
for an entity whose body/form semantics have not yet been modeled.

## Scope B: clean the generic engine foundation below Entity

The generic foundation must not know about content definitions, packages,
registries, recipes, behavior bindings, or contract hashes.

Primary files in this boundary:

```text
dnd/core/base_object.py
dnd/core/base_block.py
dnd/core/values.py
dnd/core/events.py
dnd/core/base_actions.py       # content metadata removal only
dnd/core/base_conditions.py    # content metadata removal only
```

Required changes:

- Remove content-runtime imports and binding calls from `BaseBlock`.
- Remove generic `BehaviorBinding`, `RuntimeBehaviorKind`, and `ContentRef`
  storage from foundational action, condition, handler, and event models.
- Preserve ordinary UUID ownership, semantic keys, event handlers, event
  lifecycle, conditions, modifiers, and cleanup mechanics.
- Handler diagnostics may retain neutral facts such as handler UUID, semantic
  key, name, event lineage, and outcome. They must not require authenticated
  content attribution.
- Where an event genuinely needs a stable rule identity, use a direct domain
  enum or semantic identifier rather than `ContentRef`.

### Boundary around actions and conditions

This cut may remove content metadata and binding calls from the generic
`BaseAction` and `BaseCondition` models because they are part of the polluted
foundation.

It must not refactor:

- concrete action behavior in `dnd/actions.py`;
- concrete conditions in `dnd/conditions.py`;
- action discovery or execution semantics;
- condition application/removal semantics;
- reactions, spells, traits, or their gameplay rules;
- action/condition presentation design beyond removing the foundation's hard
  content dependency.

If a concrete action or condition cannot yet be detached without redesigning
its mechanics, record it as a subsequent migration dependency rather than
expanding this phase.

Specialized blocks such as spellcasting may temporarily retain their own
content contamination if removing it would require the deferred spell/action
rewrite. They may not force generic `BaseBlock` or Entity construction to
accept content-system objects.

## Scope C: repair Entity identity and creation

Primary file:

```text
dnd/entity.py
```

Delete from Entity and `Entity.create()`:

```text
content_ref
character_species_ref
character_species_variant_ref
character_background_ref
ContentDefinitionKind validation
content-runtime root/action binding calls
```

Replace the character-only reference fields with ordinary entity-owned data:

```python
species: Species | None
species_variant: SpeciesVariant | None
background: Background | None
class_levels: list[ClassLevel]
```

These fields apply to every Entity. A monster may have no background and no
class levels. A monster may later gain class levels through the same ledger as
a player character.

`Entity.create()` must be sufficient to construct the complete neutral entity
aggregate without a registry or server context. It may continue to accept a
low-level `EntityConfig`, but the config must describe actual initial engine
facts rather than content packaging.

This first cut establishes the data and construction seam; it does not port
all SRD class feature installers. Full `gain_level()` / `lose_level()` behavior
is the next vertical progression slice. The ledger is added now so the Entity,
not an external durable-character object, owns its progression truth.

### Construction/admission boundary

The intended boundary is:

```text
construct provisional Entity
    -> apply ordinary Python Entity -> Entity operations
    -> validate the complete graph
    -> admit it atomically to Encounter/Game authority
    -> publish formal engine facts
```

The current eager registration performed by Pydantic `model_post_init()` is a
known problem because it exposes partial entities to the map, senses, and
global registries. This phase should separate provisional construction from
world/map/senses admission as narrowly as possible while retaining the current
one-process/one-game assumption. It must not become a general multi-world or
dependency-injection framework.

The event-stream completion of entity admission will be designed against the
existing event lifecycle. No parallel entity seed, content projection, or
serialization layer will be introduced.

### Temporarily deferred Entity visual fields

`Appearance`, `sprite_name`, and related renderer-facing fields are known
frontend leaks. They are not expanded or relied upon by the new construction
API. Their full removal is deferred because it belongs to the later static
visual-semantics migration and may require preserving authored information.

## Scope D: minimal item foundation cleanup

Primary files:

```text
dnd/blocks/base_item.py
dnd/blocks/inventory.py
dnd/blocks/equipment.py
dnd/types/items.py
selected direct item constructors needed by the first entity tests
```

Required changes:

- Remove `content_ref` and `content_kind` from `BaseItem`.
- Replace content identity fallback with explicit `ItemId` or an equally
  direct mechanical semantic identifier.
- Remove `ItemContentRefSnapshot` from item event/state payloads.
- Remove frontend catalog keys such as `visual_item_name` and
  `visual_variant_id` from the foundational item contract where this can be
  done without beginning the full visual-authoring migration.
- Preserve item UUID, name, description, rarity, weight, stack state, charges,
  mechanical weapon/armor facts, inventory location, equipment location,
  ownership, equip hooks, and condition/action behavior.
- Preserve inventory stacking/capacity and equipment slot/conflict mechanics.
- Establish a direct item-construction seam using `ItemId` or explicit Python
  constructors. Do not rebuild `ContentRecipe` under another name.

This phase does not port every authored item. It ports the minimal standard
weapons, armor, and loadout fixtures needed to prove direct entity construction
and preserve core inventory/equipment tests. The remaining authored items are
later mechanical migration slices.

Natural attacks and natural armor may temporarily remain intrinsic equipment
so their mechanics are not lost. Moving them into a future body/anatomy block
is explicitly deferred.

## Explicit non-goals for this first cut

- No concrete action rewrite.
- No concrete condition rewrite.
- No spell-catalog or spellcasting redesign.
- No trait rewrite.
- No spatial-effect redesign.
- No animation work.
- No final body/appearance semantic model.
- No frontend asset binding work.
- No server reconstruction.
- No API or SDK generation.
- No database or persistence schema.
- No multi-game, multi-world, multiprocessing, or concurrency abstraction.
- No complete port of all monsters, classes, premades, or items.
- No generic plugin, registry, recipe, materializer, or operation-graph system.

## Implementation sequence

### Phase 1: type package

1. Create `dnd/types/`.
2. Move and clean dependency-leaf domain types.
3. Update imports throughout active Python code.
4. Delete the old type modules without compatibility shims.
5. Verify that importing `dnd.types.*` does not initialize gameplay or content
   systems.

### Phase 2: generic foundation decoupling

1. Remove content-runtime binding from generic blocks and handlers.
2. Remove content attribution fields from foundational action, condition, and
   event models without changing their behavior.
3. Preserve semantic keys and runtime UUID ownership where useful.
4. Verify base imports without content-system bootstrap.

### Phase 3: Entity repair

1. Introduce direct species/background/progression fields.
2. Remove Entity content references and validators.
3. Remove content binding from Entity action/condition admission calls while
   leaving the underlying gameplay mechanics unchanged.
4. Separate provisional construction from world admission narrowly.
5. Construct a neutral Entity and at least one authored creature without a
   content runtime.

### Phase 4: minimal items

1. Introduce direct item identity.
2. Clean the BaseItem contract and item state payload.
3. Add direct constructors for the minimal weapon/armor fixture set.
4. Attach starting inventory/equipment without recipes.
5. Verify normal runtime loot/equip/unequip behavior remains evented.

### Phase 5: coverage recovery and stopping point

1. Recover core base, Entity, inventory, equipment, and selected monster tests.
2. Rewrite only tests whose assertions are valuable but whose fixtures use the
   removed content runtime.
3. Drop only assertions about content refs, recipes, bindings, registries,
   digests, or renderer asset keys.
4. Stop before porting the full action, condition, spell, trait, or progression
   catalogs.

Before writing or changing tests, read and follow `HOW_TO_TEST.MD` as required
by the repository instructions.

## Acceptance criteria

The first cut is complete only when all of the following are true:

1. `dnd/types/` is the sole active home for the migrated domain type modules.
2. No compatibility re-export files preserve the old type-module paths.
3. `BaseObject`, `BaseBlock`, `ModifiableValue`, and their generic lifecycle do
   not import `dnd.core.content` or `dnd.content_system`.
4. Generic event/handler infrastructure does not require behavior bindings or
   content references.
5. `Entity` has no `content_ref` or `character_*_ref` fields.
6. `Entity.create()` accepts direct domain facts and works without content
   bootstrap, server, or database state.
7. Species, optional variant, optional background, and class-level ledger are
   owned directly by Entity.
8. A monster and a player-capable entity are constructed through the same
   Entity seam.
9. `BaseItem` has no content reference or content-runtime kind.
10. A standard item can be directly created, stored, equipped, unequipped, and
    observed through engine events without a recipe/materializer.
11. Existing inventory/equipment validation and hooks remain intact.
12. No concrete action, condition, spell, trait, animation, server, database,
    or frontend asset redesign has entered the change set.
13. Tests distinguish import/collection failures from actual gameplay failures,
    and no valuable gameplay coverage is deleted merely because its old fixture
    used content materialization.

## Immediate proof cases

The smallest useful proof after the foundation is changed is:

1. create a neutral Entity with direct species/background fields;
2. create a Goblin through direct Python operations;
3. directly create a scimitar and leather armor;
4. attach those items through inventory/equipment mechanics;
5. verify the Entity can enter an Encounter without server or content runtime;
6. verify emitted item/equipment facts contain engine identity and mechanics,
   not `ContentRef` or frontend asset identifiers.

Fighter levels and a Goblin-with-Fighter-level proof follow in the next
progression slice after this foundation is stable.

## Later migration sequence retained for context

After this first cut, the planned vertical work remains:

1. direct, reversible SRD leveling on Entity;
2. one shared creation path proven by Human Fighter and Goblin Fighter;
3. remaining SRD monsters and bestiary mechanics;
4. pure-Python premade character compositions;
5. direct Encounter/Game assembly without materializers;
6. entity admission and replay completeness through the event stream;
7. in-process subjective reducer and Pygame client;
8. static visual semantics and frontend asset matching;
9. optional server/API/SDK adapters only after the in-process boundary is
   stable.

This sequence is context, not authorization to implement those later phases as
part of the present hard cut.
