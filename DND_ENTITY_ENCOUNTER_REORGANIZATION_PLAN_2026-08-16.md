# DND entity and encounter reorganization plan

Date: 2026-08-16  
Status: planning only; no implementation is authorized by this document  
Basis: direct inspection of the current Python source tree; existing Markdown reports were not consulted

## 1. Objective

Reorganize the entity and encounter portions of `dnd` around a clean, single-process game runtime that can be driven directly by an in-process client such as Pygame.

The immediate path is:

```text
authored content
    -> one entity construction/composition path
    -> one in-process Game
    -> Encounter stepping
    -> EventQueue terminal events (completion or cancellation)
    -> subjective reducer / combat-log projection / game summary
    -> Pygame renderer
```

The server, HTTP API, generated SDK, database, multiprocessing, multi-game hosting, and TypeScript boundary are not prerequisites for this path. They can later adapt to the same `Game` boundary.

This is an ownership and dependency cleanup. It is not permission to redesign `BaseBlock`, split every large class, invent a second event representation, or migrate actions and conditions while moving files.

## 2. Non-negotiable constraints

### 2.1 Dependency constraints

- No import cycles.
- No local or late imports used to conceal cycles.
- No `TYPE_CHECKING` import graph.
- No reflection-based compatibility through `getattr` where a formal field or method can exist.
- No old-path compatibility modules, re-export facades, deprecated aliases, or optional duplicate fields.
- Package `__init__.py` files remain empty or docstring-only; they must not become aggregate import surfaces.
- Avoid duplicate Python basenames across different packages. A duplicate is allowed only if the project deliberately adopts that convention everywhere.
- `dnd/core` remains the foundation layer.
- `BaseBlock`, `BaseObject`, `GridMap`, `EventQueue`, and the core event machinery keep their current names and foundational ownership during this migration.
- Authored characters, monsters, rosters, premades, maps, and encounters belong under `dnd/content`, not under the entity runtime package.

### 2.2 Event constraints

- The existing event is the reaction context while it advances through declaration, execution, and effect phases.
- Handlers may modify event-carried values before completion.
- A terminal event version—`COMPLETION` or `CANCEL`—is the cold outcome fact.
- The terminal event view is the reducer/source-of-truth view; canonical persistence retains the whole ordered raw phase stream so lineage is not lost.
- Combat logs are structured projections/serializations of events, not an independent truth stream.
- There must be one authoritative game-global EventQueue observer/perceiver evidence callback set; the existing per-entity sensory pre-completion callbacks remain a distinct lower-level mechanism.
- No presentation envelope, replication DTO, semantic event wrapper, or parallel state-change type may be added over the events.

The one EventQueue stream has two useful views, not two representations:

- the **raw causal batch** is every stored declaration/execution/effect/completion/cancel version in storage order;
- the **reducer view** selects terminal `COMPLETION` or `CANCEL` facts from that same cursor range.

`EventQueue.batch_on_event_callbacks()` batches every stored phase, not only completions, and currently returns no captured tuple. Encounter records the EventQueue cursor and opens the batch before **any** event-producing step/lifecycle work, then records the end cursor only after settlement. `EncounterStepResult` carries that range. Game uses the existing cursor/range operations to retrieve the exact raw causal range and feeds its terminal versions to the subjective reducer. No new batch envelope is required.

### 2.3 Scope constraints

- One process, one active game, one global event stream is acceptable for now.
- Do not solve multi-world or multi-game isolation.
- Do not deglobalize all foundational registries in this cut.
- Do not redesign actions or conditions in this cut.
- Do not solve animation authoring in this cut.
- Do not move frontend asset names, VFX names, sprite names, renderer layers, or palettes as part of the package-only phase. Their removal is coordinated by the separate content migration.
- Keep game summaries and legitimate event analytics.

## 3. Current source snapshot

The current entity/encounter runtime is concentrated in four root files plus scenario and reset helpers:

```text
dnd/
├── entity.py                         7,325 lines
│   [-> core, core.events, blocks, types, creature_transforms]
│   [-> core.content: problematic upward dependency]
│   [<- actions, conditions, classes, items, monsters, origins,
│       spatial, spells, scenarios, controller, encounter]
│
├── creature_transforms.py             371 lines
│   [-> core, blocks, types]
│   [<- entity, conditions, spells]
│
├── controller.py                       281 lines
│   [-> core.base_actions, core.base_object, core.events, entity, types]
│   [<- encounter, runtime_reset, scenario assembly]
│
├── encounter.py                      1,320 lines
│   [-> actions.operations, blocks.sensory, controller, core,
│       core.events, entity, types]
│   [<- runtime_reset, scenario assembly]
│
├── player_character_body.py            157 lines
│   [-> entity, actions, block configs, core.content]
│   [<- no active static importer]
│
├── premade_characters.py               241 lines
│   [-> entity, class content factory, core.content]
│   [-> removed dnd.content_system: broken]
│   [<- no active static importer]
│
├── runtime_reset.py                      73 lines
│   [-> every important process-global registry]
│   [-> removed content binding registries: broken]
│   [<- scenario assembly]
│
└── scenarios/
    └── encounter_assembler.py           485 lines
        [-> authored catalogs/materializers, maps, actions, items, spells,
            runtime_reset, entity, controller, encounter]
        [<- callers assembling authored scenarios]
```

The current core event package is already in the intended foundational area:

```text
dnd/core/events/
├── events_registry.py
│   [-> core.base_object, core.combat_log, core values/types]
│   [-> core.content.runtime: temporary legacy contamination]
│   [<- all typed event families, Entity, Encounter, actions, blocks]
│   EventType, EventPhase, Event, Trigger, BaseHandler,
│   EventHandler, SpatialHandler, EventQueue
│
├── action_events.py
├── check_events.py
├── encounter_events.py
├── item_events.py
├── resolution_events.py
└── world_events.py
```

The registry/queue/handler machinery deliberately stays together. Splitting it into tiny `event.py`, `handlers.py`, and `queue.py` files would create new mutual dependencies without clarifying an affordance boundary.

Not every typed event is in this package yet. The following definitions are deliberately left beside tightly coupled action/condition implementation until those domains are cleaned:

- `MovementEvent` in `dnd/actions/standard.py`;
- `AttackEvent` in `dnd/actions/standard.py`;
- `SpellEvent` in `dnd/actions/standard.py`;
- `ConditionApplicationEvent` in `dnd/core/base_conditions.py`;
- `ConditionRemovalEvent` in `dnd/core/base_conditions.py`.

This is known deferred debt, not a claim that event placement is complete. Encounter lifecycle events are already safely under `core/events`; action- and condition-coupled events should move only when their owning implementation can be cleaned without cycles.

Legacy `dnd/core/content` contamination also exists in `core/base_actions.py`, `core/base_block.py`, `core/base_conditions.py`, `core/feature_grants.py`, `core/spatial_effect_runtime.py`, `core/spell_execution.py`, `core/traversal_connectors.py`, `core/events/action_events.py`, `core/events/check_events.py`, `core/events/world_events.py`, `blocks/base_item.py`, `blocks/creature_proficiencies.py`, and `blocks/spellcasting.py`. In this document, “authored `dnd/content`” means the future high-level authoring package; the legacy `dnd/core/content` package is an existing foundation leak handled by the coordinated content migration.

## 4. What `Entity` currently owns

`dnd/entity.py` is not merely an entity record. Its approximate internal regions are:

| Region | Current lines | Responsibility |
|---|---:|---|
| `EntityConfig` | 213-295 | Configuration for all composed blocks plus identity/presentation flags |
| composed entity state | 296-501 | Block references, life flags, identity, spatial and action caches |
| content identity/source ledgers | 503-552 | Content refs and origin-source accounting |
| publication and rollback | 593-830 | Registry insertion, map registration, sensory callback, construction, cleanup |
| structural grants/spatial relation | 833-1023 | Block/capability changes and spatial helpers |
| conditions/rest/life/turn | 1024-1889 | Conditions, rests, death state, saves, turn hooks |
| checks/combat/spell calculations | 1891-4100 | Rolls, attacks, damage, healing, spell math |
| inventory/equipment | 4102-4366 | Item movement, equip and unequip coordination |
| perception/FOV | 4369-4772 | Sensory state, visibility, reveal behavior |
| action registry/discovery/targets | 4774-7313 | Available actions, target generation, paths, AoE, previews |
| equippable projection | 7315-7324 | Presentation-facing item view |

This class is simultaneously:

1. the aggregate root over blocks;
2. the low-level object constructor;
3. a process-global registry;
4. a position index;
5. a life-state and condition coordinator;
6. a combat and check façade;
7. a perception service;
8. an inventory/equipment coordinator;
9. an action discovery engine.

That is too much ownership, but moving the file is not the moment to split all nine responsibilities. In particular, action discovery is entangled with the behavior/content runtime and must be left in place until that dependency is removed. The first cut should make ownership visible without moving corrupt dependencies into several new files.

## 5. What `Encounter` and `Controller` currently own

### 5.1 Encounter

`dnd/encounter.py` contains:

| Region | Current lines | Responsibility |
|---|---:|---|
| projection helpers | 50-122 | event perceivers, reveal evidence, identified observers |
| `AdvanceResult` | 125-153 | advancement result value, currently a registered object |
| `CombatantState` | 156-225 | initiative, surprise, controller/entity references |
| `Encounter` state/registries | 228-327 | active/global encounter and combat-log listeners |
| roster/controllers/initiative | 329-437 | combatant assignment and initiative mutation |
| encounter/round/turn lifecycle | 439-826 | start/end, turns, environmental step, senses |
| combat-log cache/listeners | 828-880 | derived structured-log retention |
| death/end detection | 882-965 | combat terminal conditions |
| controller advancement | 967-1274 | three overlapping stepping/boundary APIs |
| indexed action execution | 1287-1319 | server-shaped action submission |

The lifecycle, initiative, combatants, end detection, and one-decision event batching are legitimate encounter behavior. Global game projection callback lifetime, runtime reset, content construction, and HTTP-shaped action selection are not.

### 5.2 Controller

`dnd/controller.py` contains:

- `TurnContext`;
- `ControllerStepResult`;
- global controller registration;
- the base controller API;
- `PassController`;
- `HumanController`.

The neutral controller seam is valuable. The current seam is not neutral enough:

- controllers receive the live mutable `Entity`;
- controllers can directly call `BaseAction.apply()`;
- controllers register globally;
- `HumanController` is documented as an HTTP/external API boundary;
- server advancement modes leak into Encounter;
- ephemeral `TurnContext` and advance results inherit globally registered `BaseObject`.

Production only needs manual/external input and a trivial deterministic pass controller. The clean direction is context in, decision out, with one validated dispatch owner.

## 6. Architectural breaks to fix

### 6.1 Construction publishes before composition is complete

`Entity.create` constructs every child block and instantiates `Entity`. `Entity.model_post_init` immediately registers the entity in global indexes, registers it with the map, attaches the sensory callback, reconciles life state, and snapshots perception.

Character and monster factories then add actions, features, senses, items, equipment, class grants, and possessions to an already published entity. A failed factory therefore needs the large `discard_unpublished_runtime` inverse cleanup.

This explains why “materialization” grew into a special subsystem: there is no cold entity that can be composed and then atomically published.

Important limit: `BaseBlock` also automatically registers itself. A genuinely cold construction transaction cannot be honestly implemented solely inside the entity package while `BaseBlock` keeps that lifecycle. The plan must preserve current rollback until a later, explicitly approved foundational publication change. It must not pretend that renaming `Entity.create` solves atomic publication.

### 6.2 One low-level constructor, many composition pipelines

There are ten active direct calls to `Entity.create`:

- seven hand-built bestiary constructors;
- one Circus Fighter constructor;
- one generic SRD constructor;
- one class-neutral player body constructor.

Above those ten calls sit additional wrappers:

- legacy bestiary functions wrapped as content factories;
- configured SRD creatures wrapped over SRD constructors;
- class roots routed into the removed schema-2 character materializer;
- premades routed into the class-root materializer;
- encounter assembly routed into the removed generic creature materializer.

The problem is not ten fundamentally different entity classes. The problem is several authored composition protocols layered over the same side-effecting constructor.

### 6.3 Entity depends upward on content runtime

`Entity` imports content identities, origin capability definitions, content-specific saving-throw context, behavior bindings, and behavior attribution. This contaminates:

- authored creature identity;
- species/variant/background identity;
- condition attribution;
- proficiency decisions;
- action registration and discovery.

The package move can preserve these imports temporarily, but the final dependency direction must be reversed:

```text
entity runtime <- authored content
```

Never:

```text
entity runtime -> generic content registry/runtime
```

`BaseBlock` also imports part of the content runtime today, so removing all content influence from the foundation requires the coordinated content migration. It must not be hidden inside a nominal file relocation.

### 6.4 Authored identity is not ordinary serializable entity state

`content_ref`, `character_species_ref`, `character_species_variant_ref`, and `character_background_ref` are excluded from normal entity serialization. There is no ordinary class/subclass/level identity ledger on `Entity`.

This loses the facts that are essential for:

- saving and restoring a character;
- deterministic rebuild;
- semantic visual authoring;
- distinguishing concrete creature kinds beyond a broad creature type;
- applying/removing levels;
- event replay.

The separate content plan replaces these refs with domain-native identity and progression data. The entity move must not entrench them.

### 6.5 Encounter contains server-shaped stepping

Encounter currently exposes three overlapping advancement methods and status values organized around external/human/autonomous server boundaries. It also exposes an action executor described as HTTP-based and addressed by a template name plus positional index.

The useful primitive hidden here is smaller: execute or settle one controller decision and return exactly the causal event batch produced by that decision. That primitive works equally well for Pygame, tests, replay, or a future server adapter.

### 6.6 Controller can bypass action dispatch

A controller can receive a live entity and execute `BaseAction.apply()` directly. This creates more than one authority for validation and dispatch.

The target must be:

```text
TurnContext + immutable action affordances
    -> Controller.decide()
    -> ActionDecision
    -> resolve against the same discovery result
    -> one action dispatcher
```

No neutral `Decision` type exists today, and current `TurnContext` does not contain selectable action affordances. `dispatch_available_action` also requires the exact in-memory `AvailableActionInfo` instance. Therefore this controller cut needs one small formal boundary addition: dependency-leaf immutable affordance rows plus an `ActionDecision` that selects one row and formal target input. Encounter must resolve that choice against the same fresh discovery result before passing the exact runtime object to the existing dispatcher; Game only forwards a submitted decision into `Encounter.step`. This is not permission to redesign action mechanics.

The dispatcher and event machinery execute the resolved decision. Controllers do not mutate entities or apply actions.

### 6.7 Ephemeral values pollute global object registries

`TurnContext` and `AdvanceResult` inherit `BaseObject`, whose post-init registers instances. A new turn context or step result should not become a UUID-addressable engine object. These are immutable values and should become dependency-leaf Pydantic/dataclass values under `dnd/types`.

### 6.8 Global event evidence/log projection has encounter lifetime instead of game lifetime

Encounter start installs EventQueue callbacks for:

- combat-log collection;
- perceiver computation;
- revealed-entity computation;
- identified-entity observers.

Encounter end removes them. Event-time identity/location evidence and global combat-log filtering/collection therefore have encounter lifetime even though they are game/world concerns.

More precisely, the global EventQueue callbacks that compute event-time identity/location evidence and filter/collect combat logs have encounter lifetime. Entity/SensoryBlock already attaches a separate sensory pre-completion callback during entity creation, and that observer-local sensory machinery exists independently. The migration must preserve that pre-completion ordering while moving only the one global EventQueue callback set to Game lifetime.

There must still be only one callback installation. In the target it is owned by the one in-process `Game` for the game lifetime. Encounter supplies combat lifecycle facts; it does not own global perception truth.

### 6.9 Some combat logs bypass event history

`EventQueue.push_combat_log` synthesizes a condition-shaped event and invokes the combat-log callback directly. Five active paths use it: condition-immunity rejection in `Entity`, a second Entity spotting path, two SensoryBlock spotting/perception paths, and hazard detection. Those records never enter the event history.

This violates the intended contract. The typed sensory events already carry observer-specific deltas. Spotting, reveal, and hazard logs should be generated by those events at completion. The condition-immunity message should be generated from the canceled `ConditionApplicationEvent`. Direct log injection should disappear only after all five callers are converted.

### 6.10 Subjective evidence is not serialized

Event-time fields for identified observers, located-entity observers, and located-position observers are excluded from serialization. A live reducer can consume them, but a reducer replaying serialized events cannot.

The eventual event closure must choose one formal rule:

1. serialize the terminal event's observer evidence; or
2. guarantee it is fully derivable from prior serialized sensory events.

The current hybrid is not replay-equivalent. This document recommends serializing facts that were authoritatively resolved at event time unless deterministic replay from earlier events is proven.

### 6.11 Encounter initialization is not replay-complete

Initiative rolling mutates `CombatantState` with natural roll, bonus, and total. `EncounterStartEvent` carries combatant UUIDs and final order, but omits:

- controller assignment;
- combatant addition/removal history;
- surprised state;
- natural initiative roll;
- initiative bonus;
- initiative total;

The final initiative order is already carried by `EncounterStartEvent`. Scenario fixed-opening policy is applied before that event, so the authored reason for the order is not required to replay Encounter state and must not be copied into a core event unless a concrete gameplay rule later consumes that provenance.

The current event stream cannot reconstruct encounter state from its own facts.

### 6.12 Turn completion can expose a different live state than replay

Encounter turn methods currently permit `encounter_uuid=None` and substitute the entity UUID as a fake encounter identity. In addition, `Entity.on_turn_end` stores/completes `TurnEndEvent` before setting `is_my_turn` to false. Completion callbacks can therefore observe a different terminal entity state from replay.

Encounter turn events must require the real encounter identity, and local turn-state mutation must occur on the correct side of event completion so terminal callbacks and serialized replay agree.

### 6.13 One unnecessary reflective access remains

`Entity.distance_to_object` accepts `BaseBlock` but uses `getattr(obj, "position", None)`. `BaseBlock` formally owns `position`; this should become direct `obj.position` access during the entity cleanup. No compatibility reflection is needed.

### 6.14 Entity creation is absent from event history

There is no completed creation/spawn fact containing the committed initial entity state. `Entity.create` and subsequent authored composition silently publish state. `game_summary` compensates by accepting separate initial and final entity snapshots in addition to event history and combat logs.

The summary capability should be preserved. The need for boundary snapshots is evidence that the event-ground-truth invariant is incomplete, not a reason to create another permanent truth channel.

## 7. Minimal target structure

The target deliberately avoids one-file-per-class over-splitting:

```text
dnd/
├── core/                              # foundation; names stay unchanged
│   ├── base_block.py
│   ├── base_object.py
│   ├── gridmap.py
│   └── events/
│       ├── events_registry.py        # Event + handlers + EventQueue stay together
│       ├── action_events.py
│       ├── check_events.py
│       ├── entity_events.py           # added in Phase 6 for birth/progression facts
│       ├── encounter_events.py
│       ├── item_events.py
│       ├── resolution_events.py
│       └── world_events.py
│
├── types/
│   └── encounter_state.py
│       [-> enum/Pydantic only]
│       [<- encounters/controllers.py, encounters/encounter.py, game.py]
│       EncounterState, TurnState, ControllerMode,
│       TurnContext, EncounterStepStatus, EncounterStepResult
│
├── entities/
│   ├── __init__.py                   # docstring only; no re-exports
│   ├── entity.py
│   │   [-> core, core.events, blocks, types, creature_transforms]
│   │   [<- actions, conditions, items, spells, encounters, content, game]
│   │   EntityConfig, Entity
│   │
│   ├── entity_creation.py
│   │   [-> entity.py, entity_progression.py, creature_transforms.py,
│   │       blocks, core/events/entity_events.py, types]
│   │   [<- all authored character/monster/entity recipes, game bootstrap]
│   │   create_entity, compose_entity, silent initial placement,
│   │   committed creation and complete rollback boundary
│   │
│   ├── entity_progression.py
│   │   [-> entity.py, creature_transforms.py, core/events/entity_events.py,
│   │       types/progression.py]
│   │   [<- authored class/origin build coordinators]
│   │   apply_level, remove_last_level, hydrate_progression;
│   │   ordered applied-level ledger and runtime receipts
│   │
│   └── creature_transforms.py
│       [-> core, blocks, types]
│       [<- entity.py, entity_creation.py, entity_progression.py,
│           conditions, spells, authored content]
│       EntityTransform/receipt protocol plus generic structural transforms
│
├── encounters/
│   ├── __init__.py                   # docstring only; no re-exports
│   ├── controllers.py
│   │   [-> types/encounter_state.py, types/actions.py]
│   │   [<- encounter.py, game.py, authored encounter setup]
│   │   Controller, PassController, HumanController
│   │
│   └── encounter.py
│       [-> entities/entity.py, controllers.py, actions/dispatch.py,
│           core/events, core/gridmap, types/encounter_state.py]
│       [<- game.py, authored encounter assembly]
│       CombatantState, Encounter
│
└── game.py
    [-> core registries/events/gridmap, entities, encounters]
    [<- in-process client now; future server/API adapter later]
    Game, process-runtime reset/bootstrap, one event projector installation,
    synchronous step/submit-decision boundary
```

Why this is deliberately compact:

- `EntityConfig` remains next to `Entity`; there is no need for a configuration file yet.
- `CombatantState` remains next to `Encounter`; it is encounter state, not a reusable subsystem.
- projection callbacks remain private helpers in `game.py`; there is only one projector and no reason to create a service package.
- reset/bootstrap remains with `Game`; a separate runtime package would recreate infrastructure before a second runtime exists.
- action discovery remains in `Entity` temporarily despite its size, because moving its content-runtime dependency now would only spread the corruption.

### 7.1 Entity owns the verbs; content owns the authored meanings

The later content migration depends on a strict ownership decision now. Generic entity lifecycle operations are engine behavior, not authored content behavior. Therefore `dnd/entities` owns:

- construction of the universal undeployed entity aggregate;
- ordered composition of already-resolved entity transforms;
- construction-only silent item placement, final validation, commit, and rollback;
- application of one already-resolved level step;
- validated removal of the most recently applied level;
- deterministic save hydration of the applied-level ledger while an Entity is unpublished;
- the persisted ordered progression state and the live receipts needed to undo installed mutations;
- terminal creation, level-added, and level-removed event publication.

Authored `dnd/content` owns the specific nouns and rule choices: Human, Goblin, Fighter level 3, Berserker, a flaming sword, or a named premade. It validates authored choices and resolves each choice into dependency-leaf identity values plus an ordered sequence of concrete `EntityTransform` operations. It then calls the entity-owned verbs. An entity module never looks up a Fighter definition, imports a monster catalog, resolves a premade ID, or asks a content registry what to do.

The intended boundary is:

```text
content definition + selected choices
    -> content resolves a ResolvedLevelStep / ordered EntityTransform values
    -> entities.compose_entity(...) or entities.apply_level(...)
    -> Entity mutates through generic transforms and records exact receipts
    -> entity-owned terminal event records the resulting semantic state
```

`EntityTransform` is an operation protocol, not another universal content schema. Concrete authored transforms may be implemented in content or stable rule modules and passed downward. The entity layer knows only how to apply, undo, order, validate, and account for them.

Persisted progression and runtime undo state are deliberately different:

- `AppliedOriginState` is dependency-leaf serialized build state containing exactly base ability allocation, flexible ability bonuses, and immutable origin choices; species/variant/background and semantic body/appearance remain separate Entity fields;
- `AppliedClassLevel` is a dependency-leaf serialized row containing semantic class/subclass/source-step identity and selected values;
- runtime receipts contain concrete UUID handles for installed modifiers, actions, handlers, resources, spells, and similar mutable registrations;
- receipt UUIDs are ephemeral and are regenerated by rebuilding from the persisted ordered level rows after load;
- a later content implementation resolves the saved origin state and level rows into concrete transforms, including total-level-dependent origin changes; Entity owns unpublished hydration ordering and invariants, not the authored lookup table;
- `hydrate_progression` is legal only on an unpublished/undeployed Entity while reconstructing runtime mechanics for an already-persisted save and emits no events; new birth uses `compose_entity`, while a committed Entity changes semantic levels only through `apply_level`/`remove_last_level` and their terminal facts.

## 8. Target dependency graph

In this diagram `A -> B` means **A imports/depends on B**:

```text
dnd/entities
    -> dnd/core + dnd/blocks + dnd/types

actions / conditions / item rules / spells
    -> dnd/entities + dnd/core + dnd/blocks + dnd/types

dnd/encounters
    -> dnd/actions + dnd/entities + dnd/core + dnd/types

dnd/game.py
    -> dnd/encounters + dnd/entities + dnd/core

authored dnd/content character/creature/item definitions
    -> dnd/entities + stable rules implementations

authored content level/build resolver
    -> dependency-leaf definition values + dnd/entities progression/composition verbs

authored dnd/content scenario deployment
    -> dnd/game.py + dnd/encounters + authored domain definitions

Pygame now / future server adapter
    -> dnd/game.py + optional read-only authored content ledger
```

Game and Encounter never import authored content. Authored scenario deployment is the caller that imports Game/Encounter, builds domain definitions, and deploys them. This direction prevents the Game/content cycle.

Forbidden reverse edges:

- `core -> entities`
- `blocks -> entities`
- `entities -> encounters`
- `entities -> game`
- `entities -> authored content`
- `encounters -> game`
- any engine layer `-> server`, SDK, database, provider, renderer, or asset registry

Temporary exception to remove during content migration:

- `entities/entity.py -> legacy core/content/*`;
- existing `core/base_actions.py`, `core/base_block.py`, and
  `core/base_conditions.py -> legacy core/content/*`;
- existing `core/events/events_registry.py`, `action_events.py`,
  `check_events.py`, and `world_events.py -> legacy core/content/*`;
- existing `core/feature_grants.py`, `core/spatial_effect_runtime.py`,
  `core/spell_execution.py`, and `core/traversal_connectors.py -> legacy
  core/content/*`;
- existing `blocks/base_item.py` and `blocks/spellcasting.py -> legacy
  core/content/*`;
- existing `blocks/creature_proficiencies.py -> legacy core/content/*`.

No new module may copy these exceptions. The content migration removes them; this package move does not disguise them.

There is also an existing `core/aoe.py -> blocks/sensory.py` edge. Freeze it during this migration rather than claiming the live core/blocks graph is already strictly layered or widening that edge.

## 9. Exact current-to-target ownership ledger

| Current symbol/file | Target | Migration rule |
|---|---|---|
| `dnd/entity.py::EntityConfig` | `dnd/entities/entity.py` | Mechanical move with `Entity`; do not create a one-class file. |
| `dnd/entity.py::Entity` | `dnd/entities/entity.py` | Preserve class and behavior during relocation. |
| `Entity.create` | `dnd/entities/entity_creation.py::create_entity` | Replace only after all ten active callers and tests are inventoried; delete classmethod, no facade. |
| authored whole-build materialization | `dnd/entities/entity_creation.py::compose_entity` plus content-supplied transforms | Entity owns ordering/commit/rollback; content owns specific transforms and choices. |
| character-only grant transactions/receipts | `dnd/entities/creature_transforms.py` | Generalize apply/undo receipt mechanics for every Entity; do not import authored definitions. |
| class-level mutation and ordered progression accounting | `dnd/entities/entity_progression.py` | Entity owns `apply_level`, `remove_last_level`, and save-only unpublished `hydrate_progression`; content resolves specific class-level/origin-dependent plans before calling them. |
| persisted origin/build state and applied class-level rows | `dnd/types/progression.py` | Dependency-leaf base scores, flexible bonuses, immutable origin choices, semantic origin selections, and ordered level rows; no live transform, runtime UUID receipt, ContentRef, or catalog object. |
| committed birth/progression schemas | `dnd/core/events/entity_events.py` | `EntityCreatedEvent`, `EntityLevelAddedEvent`, and `EntityLevelRemovedEvent`; scalar/leaf payloads only. |
| Entity global registries and lookups | initially stay on `Entity` | One-process constraint makes this acceptable; Game owns lifecycle/reset, not necessarily storage yet. |
| `Entity.discard_unpublished_runtime` | retain initially | Required while BaseBlock/Entity publish during construction. |
| entity structural/source ledgers | `entities/entity.py` | Retain; content plan replaces ContentRefs with formal identity/source IDs. |
| entity condition/life/turn methods | `entities/entity.py` | Coherent entity behavior; no split in package phase. |
| entity combat/check methods | `entities/entity.py` | Defer extraction until import graph is stable. |
| entity inventory/equipment methods | `entities/entity.py` | Keep during move; item cleanup is coordinated separately. |
| entity perception/FOV methods | `entities/entity.py` initially | Later reconcile with `blocks/sensory.py`; do not duplicate perception authority. |
| entity action discovery/targeting | `entities/entity.py` initially | Later move authority into existing `dnd/actions`; only after behavior-binding removal. |
| `dnd/creature_transforms.py` | `dnd/entities/creature_transforms.py` | Safe mechanical relocation. |
| `dnd/controller.py::TurnContext` | `dnd/types/encounter_state.py` | Frozen non-registered value. |
| `ControllerStepResult` | `EncounterStepResult` or delete | One formal step result only; do not preserve redundant controller wrapper. |
| `Controller` | `dnd/encounters/controllers.py` | Context in, decision out; remove global registration/direct action execution. |
| `PassController` | `dnd/encounters/controllers.py` | Keep trivial deterministic controller. |
| `HumanController` | `dnd/encounters/controllers.py` | Keep manual-input boundary; remove HTTP/server assumptions. |
| `dnd/types/encounter.py` | `dnd/types/encounter_state.py` | Rename to avoid duplicate `encounter.py` basename. |
| `AdvanceStatus` | smaller step status in `encounter_state.py` | Remove server-only external/autonomous vocabulary. |
| encounter `_compute_*` observer helpers | private helpers in `dnd/game.py` | Exactly one game-lifetime projector installation. |
| `AdvanceResult` | `EncounterStepResult` | Frozen value; no BaseObject registration. |
| `CombatantState` | `dnd/encounters/encounter.py` | Keep next to Encounter; remove Controller registry lookup during controller cut. |
| `Encounter` | `dnd/encounters/encounter.py` | Retain initiative/turn/round/combat authority. |
| three `advance_*` methods | one `Encounter.step()` | Preserve one-decision causal batch semantics. |
| `Encounter.execute_action` | remove; `Encounter.step(decision=...)` resolves and calls existing `dnd/actions/dispatch.py` | Game coordinates only; Encounter is the single dispatch authority and owns no HTTP/index API. |
| `Encounter.combat_log` | derived cache in `Game` or Encounter during transition | Never a second truth stream; generated from terminal events. |
| `dnd/runtime_reset.py` | private Game bootstrap/reset operation | Remove broken content registry resets; no compatibility file. |
| `dnd/scenarios/encounter_assembler.py` | authored content migration | It deploys into Game and must not reset process globals itself. |
| `dnd/player_character_body.py` | `dnd/content` character recipe | Authored content, not entity infrastructure. |
| `dnd/premade_characters.py` | `dnd/content` premade definitions | Plain compositions, no DB/server/materializer special path. |

## 10. Migration phases

Each phase is a hard cut. Old import paths and duplicate behavior are deleted in the same change that updates their callers.

### Phase 0 — record gates before moving code

Add or update architecture checks to enforce:

- no import cycles;
- no late imports;
- no `TYPE_CHECKING` imports;
- no unexpected reflection;
- no package re-exports;
- no duplicate basenames in the migrated families;
- no imports from `server`, deprecated SDK, database, AI/provider packages, or frontend asset registries;
- `dnd/core` and `dnd/blocks` never import `dnd.entities`, `dnd.encounters`, or `dnd.game`;
- `dnd.entities` never imports `dnd.encounters`, `dnd.game`, or authored `dnd.content`.

Capture focused capabilities rather than old module paths:

- create one neutral entity with every block wired;
- position/register/remove an entity;
- run life/condition/turn behavior;
- inventory and equipment transition behavior;
- perception and observer evidence;
- start encounter, order initiative, step rounds/turns, and terminate combat;
- PassController and manual-input boundary;
- one action decision produces one ordered causal event batch;
- structured combat log generated from event completion;
- game summary over known event history.

### Phase 1 — mechanical package relocation

Move atomically, without behavior edits:

1. `dnd/entity.py` -> `dnd/entities/entity.py`.
2. `dnd/creature_transforms.py` -> `dnd/entities/creature_transforms.py`.
3. `dnd/controller.py` -> `dnd/encounters/controllers.py`.
4. `dnd/encounter.py` -> `dnd/encounters/encounter.py`.
5. `dnd/types/encounter.py` -> `dnd/types/encounter_state.py`.

Update every production and retained-test import atomically. Delete the old files. Do not add re-export aliases.

Phase gate:

- zero old import strings;
- zero newly introduced import cycles;
- identical public model schemas except for module-qualified paths;
- focused entity/encounter/event/sensory/action tests pass or have only already-known deprecated-content blockers;
- every active importable `dnd` module outside known content blockers imports successfully.

### Phase 2 — remove ephemeral global registration

Convert `TurnContext`, advancement status, and step result into frozen dependency-leaf values. They must not inherit `BaseObject`, have UUID identity, or enter the global object registry.

`EncounterStepResult` contains scalar status, `event_generation_id: UUID`, `event_start_cursor`, and `event_end_cursor`; it does not embed `Event` objects and therefore keeps `dnd/types` dependency-neutral. Game rejects results whose generation differs from `EventQueue.generation_id()`, then resolves the cursor interval to the actual raw EventQueue objects and selects terminal versions for the reducer.

Keep model fields only when they are used by the in-process control loop. Remove server-coordinator fields rather than making them optional.

Phase gate:

- repeated encounter stepping does not grow `BaseObject` registry counts because of contexts/results;
- values serialize deterministically;
- controller and encounter import only the leaf types.

### Phase 3 — controller hard cut

First formalize the missing immutable selection boundary. No neutral decision type exists in the current source, current `TurnContext` does not expose action affordances, and the existing dispatcher intentionally validates exact `AvailableActionInfo` object identity. Add dependency-leaf rows sufficient to show/select one freshly discovered action and its formal target inputs, then define the neutral seam:

```python
class Controller:
    def decide(self, turn: TurnContext) -> ActionDecision | None:
        ...
```

`TurnContext` carries the immutable action affordance rows, or carries a separately referenced immutable affordance tuple supplied in the same call. `ActionDecision` is a scalar/value contract containing the actor UUID, discovery/turn revision token, stable action selector, optional target entity UUID or target position, formal extras, and path preference where the selected action supports it. It never embeds `AvailableActionInfo`, `AvailableTarget`, Entity, or an execution template. Encounter retains the matching fresh discovery result, rejects actor/revision/selector/target mismatches and stale input, resolves the values to the exact runtime `AvailableActionInfo` and `AvailableTarget`, and then calls the existing dispatcher. Keep this boundary minimal and under dependency-leaf action types; do not create a controller-only parallel action system.

Rules:

- controller receives immutable context, not the live Entity;
- controller never calls `BaseAction.apply()`;
- Encounter is the single dispatch authority and invokes the one existing dispatcher after resolution;
- Encounter directly owns an in-memory `controllers_by_entity_uuid: dict[UUID, Controller]` (or equivalent) and does not resolve controllers globally;
- `CombatantState` retains only serializable controller mode/assignment facts when saved-game resume actually needs them;
- remove `Controller._controller_registry` and BaseObject inheritance if no durable identity remains necessary;
- keep `PassController` and manual `HumanController` only;
- remove AI/provider/takeover concepts, if any residue remains;
- `None` or the existing formal end-turn decision has one unambiguous meaning.
- delete the generic controller lifecycle hooks and autonomous-selection modes unless a desired production contract explicitly requires one; the only live production subclasses are PassController and HumanController.

Phase gate:

- no controller source imports `Entity` or `BaseAction`;
- all decisions pass through one dispatcher;
- manual input can wait without polling/spinning;
- PassController deterministically ends a turn;
- no controller global registry exists.

### Phase 4 — simplify Encounter to one stepping seam

Collapse the three advancement functions into one deterministic boundary:

1. record `event_generation_id` and `event_start_cursor`, then open the existing batch before any lifecycle work;
2. establish/start/skip the current turn if necessary, including its TurnStart and sensory facts;
3. build immutable `TurnContext`;
4. accept a manual `decision=` argument, return a manual-input wait state, or obtain a deterministic controller decision;
5. Encounter resolves, validates, and dispatches at most one decision;
6. settle death/end-turn/end-encounter consequences;
7. close the batch and record `event_end_cursor` after every event-producing consequence;
8. return one frozen `EncounterStepResult` covering the whole ordered raw range.

Boundary rules:

- manual-input wait returns the lifecycle events already produced, or an empty range if no lifecycle work occurred;
- surprised/dead combatant skips return the full skip/turn-transition range even though no action dispatch occurs;
- round/turn lifecycle-only advancement returns its facts in the same range;
- one step dispatches zero or one decisions but never omits events emitted before decision discovery.
- a cursor range is valid only while its generation ID matches EventQueue; reset/another Game generation is rejected rather than reading same-numbered events from different history.

Remove `Encounter.execute_action`. `Game.submit_decision` only coordinates by calling `Encounter.step(decision=...)`; Game never invokes action dispatch itself. Both manual input and controller output therefore enter the one Encounter resolution/dispatch path.

Preserve until proven unused:

- turn execution IDs;
- source event cursor per turn;
- surprise behavior;
- death-save behavior;
- environment step per round;
- only lifecycle notifications proven necessary by the new production controller contract.

Phase gate:

- deterministic test controllers and manual decisions produce the same dispatcher path;
- a submitted decision is never split across step ranges; its raw range also truthfully includes lifecycle facts emitted before/after it, and lifecycle-only steps are allowed;
- the raw batch preserves all stored phases in order, while reducer input selects terminal completion/cancel versions from that same cursor range;
- no method or enum refers to HTTP, server coordination, autonomous boundary, or external provider;
- the same loop can be driven synchronously by a test with no server.

### Phase 5 — introduce the minimal one-process `Game`

Create `dnd/game.py` as the only orchestration layer. It owns:

- lifecycle/reset of existing process-global registries;
- active map and entities at the orchestration level;
- active Encounter;
- one installation of EventQueue combat-log/perceiver/reveal/identified-observer callbacks;
- capture of raw EventQueue cursor ranges and subscription of their terminal completion/cancel versions to a subjective reducer;
- synchronous `step()` and `submit_decision()` entry points;
- save/event-history/summary access at the game boundary.

It does not own:

- rules calculations;
- block behavior;
- action implementations;
- authored content declarations;
- rendering/assets;
- HTTP or database behavior;
- multiple independent games in one process.

Move the valid parts of `runtime_reset.py` into private Game lifecycle code. Remove resets for the deleted content registries. Delete `runtime_reset.py` once its sole caller migrates.

Remove `Encounter._active_encounter` and its get/set authority in the same phase. Game is the only owner of which Encounter is active. The broader Encounter UUID registry may remain temporarily under the one-process constraint, but it cannot be a second current-encounter authority.

Move callback installation from Encounter start/end to Game start/close. Encounter remains responsible for emitting combat lifecycle events.

Phase gate:

- a fresh `Game` can initialize, create/deploy entities, start/step/end one encounter, and close/reset without server imports;
- event projection exists outside combat as well as inside it;
- exactly one set of EventQueue callbacks is installed;
- a second Game in the same process is explicitly rejected or requires closing/resetting the first; no fake isolation.

### Phase 6 — unify low-level entity birth

This is the joint foundation that the later authored-content phases consume. It is blocked only on these lower-level milestones:

- domain-native concrete entity/species/variant/background/class-level identity exists;
- neutral reversible entity-grant receipts and rollback exist;
- enough direct item construction exists to prove construction-only silent inventory/equipment placement.

Direct character origins/classes, all four premades, monster catalogs, and scenario members are **not** prerequisites. They are downstream clients of this phase. Requiring them first would create a migration deadlock.

Do not begin the authored hard cut by reinstalling ContentRef or compatibility materializers in the new package.

Introduce `dnd/entities/entity_creation.py::create_entity` as the only low-level birth operation and `compose_entity` as the generic ordered-transform/commit boundary. Update all ten active direct call sites and every retained test/support fixture in one cut. Delete `Entity.create`; do not preserve a delegating classmethod.

This operation constructs the same block aggregate for every player, monster, NPC, summon, and premade. Differences are authored composition steps, not separate runtime constructors.

The current `Entity.model_post_init` publishes a partial entity into Entity's position index, GridMap, spatial-enter events, and sensory observation before authored composition is complete. A minimal construction/deployment separation is required now even though full cold BaseBlock construction remains deferred:

- base blocks and Entity object identity may retain their current process registries for now;
- the newly constructed aggregate is explicitly **undeployed**;
- it is not inserted into Entity's position index or GridMap;
- no spatial-enter event fires and no spatial sensory observer is attached;
- authored identity, species/class/monster mechanics, items, and equipment compose while undeployed;
- initial inventory/equipment state is installed through dedicated construction-only silent placement APIs, not the ordinary event-publishing `loot_item`, equip transaction, or `BaseItem.destroy` path;
- it owns complete rollback on failure;
- after successful composition/validation, emit one terminal entity-created fact;
- `Game.deploy_entity` then installs the position index, GridMap entry, and sensory observer and emits the existing typed spatial-enter fact.

The publication split must migrate consumers at the same time as the creator; changing only the ten constructors would strand current callers because `Entity.model_post_init` performs deployment today. The complete active consumer disposition is:

| Consumer family | Joint Phase-6 change |
|---|---|
| `dnd/scenarios/encounter_assembler.py` | Keep its authored schemas temporarily, but after each committed materialization call `Game.deploy_entity(entity, roster_position)` explicitly. Do not wait for the later scenario-schema move. |
| `dnd/monsters/bestiary_content.py` and `dnd/monsters/configured_srd_creatures.py` | Remain temporary authored builder wrappers only; stop treating `position` as construction and return committed undeployed entities to the application/deployment caller. |
| deprecated creature/character materializer paths still used by retained capabilities | Port their retained caller to `compose_entity`; return an undeployed committed Entity. The later content phases replace their schemas, not their deployment behavior. |
| direct bestiary/SRD/player-body users in tests, manual helpers, and transition scripts | Replace implicit spatial publication with a shared explicit Game/create-then-deploy test boundary when the capability needs map presence; keep construction-only tests undeployed. |
| future summon/conjuration/application creation | Compose first, then ask the owning Game to deploy; a content builder never inserts itself into a map. |

Phase-6 inventory gates are therefore broader than `rg 'Entity.create('`: enumerate every production, test, and tool call of the ten containing factory functions and every materializer wrapper that forwards a position. After the cut, no authored constructor accepts a world position as a side-effecting deployment instruction; position belongs to `Game.deploy_entity` or a scenario deployment row.

The causal order is therefore:

```text
base aggregate identity registration
    -> authored composition while spatially invisible
    -> validate and commit EntityCreated terminal fact
    -> Game.deploy_entity(position)
    -> spatial-enter terminal fact
```

Phase 6 owns the new event module and schemas:

- `dnd/core/events/entity_events.py::EntityCreatedEvent` carries final concrete entity identity, species/variant/background, the exact `AppliedOriginState`, applied class levels, separate semantic body/appearance state, reducer-required initial mechanics, item instances, inventory, and equipment. It does not carry world position; deployment owns position.
- `EntityLevelAddedEvent` carries entity UUID, previous/new total level, the dependency-leaf applied-level row, resulting per-class levels, stable source-step ID, and direct renderer-agnostic mechanical/semantic delta/result fields described below.
- `EntityLevelRemovedEvent` carries entity UUID, previous/new total level, the removed dependency-leaf level row, resulting per-class levels, stable source-step ID, and the inverse/removal plus resulting mechanical/semantic fields described below.

The level facts must be reducible without importing a class/origin catalog or rerunning authored transforms. Direct event fields therefore cover every grant family the transaction can change:

- ability-score and constraint/modifier changes required by ASIs/features;
- proficiency bonus plus added/removed skill, save, weapon, armor, shield, tool, and language proficiencies;
- hit-die pool changes;
- spellcasting-source/provider-level, known/prepared/reaction spell, and spell-slot capacity/current-state changes;
- damage affinity/resistance/immunity changes;
- added/removed action, handler, feat, trait, feature, and resource semantic IDs with resulting resource values/recovery facts;
- armor-class formula/source changes, attack-multiplicity changes, condition immunities, senses, structural size, and origin-capability changes;
- any semantic body/appearance changes caused by the level transaction;
- resulting aggregate proficiency, caster/slot, per-class-level, and total-level facts after reconciliation.

These are fields on the two event schemas, using dependency-leaf scalar/enum/tuple rows from `dnd/types`; there is no `ProgressionPayload`, live receipt, transform callable, ContentRef, or catalog-backed envelope. The fields are produced from the committed transaction/receipt and resulting Entity state, not inferred later. Total-level-dependent origin additions/removals are included in the same event. If a migrated level cannot express one of its actual changes without deferred behavior identity work, that level port remains blocked rather than emitting an incomplete fact.

These terminal schemas import no live Entity, block, authored content, transform callable, runtime receipt, ContentRef, or renderer type. In this migration they are deliberately **non-cancelable post-commit facts**: they have no declaration/execution/effect lineage and no reaction handlers. If a future rule genuinely needs to prevent or alter levelling, that is a separately designed command/reaction event before this fact, not an implicit capability claimed here.

The first substep of Phase 6 extracts the existing completion-field calculation inside `Event.phase_to(COMPLETION)` into one private routine that remains in `events_registry.py`. Both ordinary completion and a new `EventQueue.publish_completed_fact(...)` call that same routine. The latter accepts an unregistered event, finalizes lineage/observer/combat-log fields, and registers exactly one `COMPLETION` version without handler dispatch. It never creates an externally visible declaration for an entity or level that may still roll back. All three entity facts use this path only after their exact mutation transaction succeeds. This is a bounded reuse of existing core event machinery, not an events-registry split or a general event redesign; Phase 8 still owns full cancellation finalization for reactive lineages.

Introduce `dnd/entities/entity_progression.py` in the same foundation cut. It owns:

```text
apply_level(entity, applied_level, transforms) -> LevelReceipt
remove_last_level(entity, expected_step_id=None) -> removed AppliedClassLevel
hydrate_progression(unpublished_entity, applied_origin, resolved_steps) -> ordered receipts
```

`apply_level` never resolves a class ID. It receives a content-resolved `AppliedClassLevel` plus concrete transforms, including any total-level-dependent origin reconciliation, validates ledger ordering, applies them transactionally, records the semantic row and its live receipt inside entity progression state, and publishes `EntityLevelAddedEvent`. If completed-fact publication fails, it undoes the receipt and ledger append before re-raising. Removal resolves the last receipt internally, optionally rejects a stale `expected_step_id`, undoes the exact receipt, reconciles aggregate mechanics, removes the row, and publishes `EntityLevelRemovedEvent`; the live resolved step is retained until publication succeeds so a failure can restore the prior mechanics. Content/application code never owns or supplies a live receipt.

`hydrate_progression` is save hydration only, not new birth and not a silent mutation API for a committed Entity. It requires an unpublished/undeployed aggregate, installs externally resolved origin and ordered-level transforms through the same private transaction, regenerates live receipts, and emits no events. Save loading restores the already persisted original raw event history; hydration publishes neither a second `EntityCreatedEvent` nor duplicate level facts. New construction instead reaches the private install transaction through `compose_entity`, which publishes the one original `EntityCreatedEvent` after success. Seeding a new history from a snapshot would require a separate future history-generation contract and is not disguised as hydration here.

Initial levels applied inside an unpublished `compose_entity` use the same internal progression transaction and receipt logic but emit no standalone level events: a failed birth must have no externally visible progression history. The single successful `EntityCreatedEvent` carries the complete initial ordered-level ledger. Only post-birth `apply_level`/`remove_last_level` publish the dedicated progression events.

A failed composition produces neither creation nor spatial-enter fact and cleans all registered base/aggregate handles.

The silent construction APIs must reuse/extract the same pure inventory capacity, stack, equipment-slot, collision, and mechanical attachment validation used by ordinary gameplay, then perform the required state/modifier hookups without declaration/execution/completion events, reaction handlers, global callbacks, or observer delivery. Rollback uses matching silent removal/unregistration and never calls the event-publishing destroy path. Successful commit carries the final initial item/inventory/equipment state in `EntityCreated`; ordinary typed item/equipment events begin after publication. No EventQueue transaction is introduced, because the current batch helper does not delay immediate callbacks/handlers and cannot roll them back.

Full cold-publication is still a separate approved change:

```text
construct detached blocks/entity
    -> apply authored composition transaction
    -> validate final aggregate
    -> publish entity/block identity once
    -> deploy spatially through Game
```

That stronger extension touches BaseBlock lifecycle and is deferred. The spatial deployment separation above does not require redesigning BaseBlock.

Phase gate:

- exactly one production call site is allowed to instantiate the complete Entity aggregate;
- all character/monster factories call `create_entity` plus ordered transforms;
- all ten formerly direct `Entity.create` production call sites have migrated and the classmethod is deleted;
- generic composition and progression are tested with trivial deterministic transforms, without importing a Fighter, species, monster, premade, or content ledger;
- a content-supplied resolved level can be applied to either a neutral player body or a monster base through the same `apply_level` operation;
- level removal is last-in, receipt-exact, and leaves no source-owned handle behind;
- hydrating an unpublished Entity from persisted origin/build state and applied-level rows regenerates runtime receipts and equivalent mechanics, including total-level-gated origin grants, while restoring its original event history without publishing duplicate birth/progression facts;
- completed level operations produce the same terminal facts for live reduction and replay; failed transactions produce no level fact and leave state unchanged;
- failed birth leaves no Entity, BaseBlock, map, sensory, handler, or action residue;
- partially composed entities cannot be found by position, occupy a tile, trigger spatial-enter, or receive spatial perception callbacks;
- failed composition leaves no permanently indexed item/equipment/destroy transition facts for the unpublished entity;
- construction-only silent placement passes the same mechanical validation as ordinary placement but invokes no event handlers/callbacks;
- committed entity creation always precedes spatial deployment in the raw event stream;
- every consumer that previously relied on constructor-time position publication explicitly calls `Game.deploy_entity`, including the live scenario assembler before its later schema migration;
- no authored constructor or content builder owns GridMap insertion, spatial indexing, or sensory subscription;
- no entity runtime module imports authored content.

### Phase 7 — migrate scenario deployment onto Game

Before the first migrated scenario can be considered replay-grounded, Phase 7 adds the renderer-agnostic `WorldInitializedEvent` terminal schema and publication at the end of silent GridMap/tile bootstrap. It contains the base map/tile facts required by the subjective reducer. `GridMap.create_rectangle()` currently suppresses tile events; scenario deployment cannot wait for Phase 8 to close this gap because the content plan's scenario phase already requires the fact. The event uses the non-cancelable completed-fact path introduced in Phase 6.

Split the current scenario assembler by responsibility without creating generic infrastructure:

- authored roster, encounter, battlefield, and loadout definitions move under `dnd/content` in the separate content migration;
- map construction stays with the map/world domain;
- entity recipes call the one construction/composition path;
- deployment places committed entities into the Game;
- Encounter construction assigns combatants/controllers and optionally starts combat;
- scenario assembly no longer resets the process behind the caller's back.

The existing `AssembledEncounter` result should be reviewed against actual Pygame needs. Retain only concrete useful values: Game/Encounter, map, named entity lookup, and notable positions. Do not preserve content-system compatibility diagnostics as runtime state.

Scenario capability preservation ledger:

| Current assembler capability | Disposition |
|---|---|
| static definition compatibility check | preserve only checks that express real engine support; call before construction |
| built-runtime compatibility check | preserve only checks that validate actual constructed mechanics; call after construction |
| member materialization | rewrite through direct character/monster definitions and the one composition path |
| faction assignment and authored positions | preserve; faction composes before commit, position is applied only by `Game.deploy_entity` |
| item grants and placement | preserve through direct item builders and receipt-based loadouts |
| spell grants | preserve; block affected scenarios until direct spell grant identity exists rather than silently dropping them |
| behavior/action grants | preserve; explicitly block affected scenarios on the deferred action-content migration rather than retaining the generic gateway |
| damage affinities/resistances/resources | preserve as source-owned entity receipts |
| starting damage | preserve the post-construction application order and its typed events |
| starting conditions and cross-member sources | preserve the existing deferred/two-pass resolution; final hard cut is blocked on condition-content cleanup |
| opportunity handlers | preserve runtime installation and exact cleanup |
| initial senses/perception update | preserve after spatial deployment, not during partial construction |
| fixed-roster opening reorder | preserve as scenario policy applied before Encounter start; only final order is a replay fact |
| prepare without starting Encounter | preserve as a first-class in-process use case |
| result entity maps, controllers, notable positions | preserve concrete lookup values; delete package/runtime compatibility payloads |

Phase gate:

- authored scenario assembly has no removed `dnd.content_system` imports;
- every silently bootstrapped map emits `WorldInitializedEvent` before entity spatial-deployment facts;
- it accepts/returns Game-owned objects;
- it never calls global reset itself;
- the same deployment functions can be used without starting an Encounter.
- every capability row above has a focused preserve/rewrite/defer test and no affected authored scenario is silently weakened;
- all four premade character definitions, including the multiclass Spellblade, can appear as scenario members without DB/server/content-runtime setup.

### Phase 8 — close entity and encounter event gaps

This is a bounded event-schema extension, not a new representation layer and not a general action/condition rewrite.

Add or complete typed facts for:

1. entity removal/despawn if it can occur independently of death;
2. combatant addition/removal and controller mode/assignment where replay-relevant;
3. initiative natural roll, bonus, total, surprise, and final order;
4. a real encounter UUID for every encounter turn event;
5. local `is_my_turn` mutation ordered so terminal callbacks and replay see the same state;
6. observer evidence required by in-process subjective reduction and eventual serialized replay.

`WorldInitializedEvent` is already introduced and accepted in Phase 7 because scenario deployment depends on it. Phase 8 consumes that fact but does not own or redefine it. One compact initialized-world fact is used rather than thousands of synthetic tile mutations.

`EntityCreatedEvent` and its payload are already introduced and accepted in Phase 6; Phase 8 consumes that fact but does not own or redefine it.

Scope boundary: do not emit a new event for every deterministic condition tick, resource reset, equipped-item turn hook, or other mutation already derivable from formal turn/action events and rules. This phase covers encounter-owned non-derivable facts, spatial deployment/world bootstrap, callback evidence, turn-state ordering, and the bounded log fixes below. Full action/condition event completeness remains deferred.

Combat-log cleanup:

- remove `push_combat_log` as an out-of-band truth path;
- migrate all five active callers: four spotting/perception/hazard paths generate logs from typed sensory completion facts, while condition-immunity rejection generates its log from the canceled condition-application fact;
- keep the event's `combat_log` as a derived projection/cache only;
- preserve the current summary capability during this phase; it still accepts raw events, structured logs, and initial/final snapshots and is not yet claimed as event-history-only.

Event completion contract:

- reaction phases retain mutable/modifiable values;
- after storage, terminal completion/cancel versions are treated and verified as immutable cold facts; implementation may later enforce technical freezing explicitly;
- terminal facts include every reducer fact that cannot be deterministically reconstructed from earlier terminal events;
- no frontend asset identifier enters these events.

`CANCEL` must become a fully finalized terminal fact, not merely another posted phase. Introduce one common terminal-finalization path used by both completion and cancellation that:

- freezes/stores stable parent-child lineage;
- computes required perceiver/identified/located observer evidence;
- derives and delivers the structured combat log exactly once when the event defines one;
- invokes passive terminal/log callbacks consistently;
- does not run completion-only state-changing sensory callbacks for a cancellation.

This is required for condition-immunity rejection to generate its log from the real canceled `ConditionApplicationEvent` and for reducers/summaries to treat completion and cancellation as equally authoritative outcomes.

Canonical persistence intent:

- save the entire ordered raw EventQueue phase stream, not only terminal versions;
- preserve concrete event subclass/schema identity and `parent_event` lineage for every stored version;
- reducers select terminal completion/cancel facts from that stored stream;
- summaries may continue resolving raw parent UUID lineage;
- a future terminal-only export is forbidden until stable lineage fields replace raw phase-parent assumptions in `game_summary`.
- replay parity concerns deterministic game/reducer state. Existing wall-clock encounter start/end timestamps are either retained as observed event facts or excluded from parity; they are never regenerated by consulting the clock during replay.

The live source does not yet have a polymorphic codec that reconstructs every concrete event subclass, and several deferred action/condition events embed live objects or read global registries while generating logs. Therefore full JSON/process-reset replay is **not** a Phase 8 claim. A later bounded event-codec/coldness phase must cover those action/condition event families before complete combat serialization is promised.

Phase gate:

- a fresh in-process subjective reducer can build world, entity, deployment, and encounter-start state from terminal event objects alone;
- initiative details and order match live execution;
- live callback reduction and replay of the same retained in-memory terminal event objects reach the same reducer state;
- every structured sensory/combat log points back to a real event in history.

### Phase 9 — prove the in-process vertical slice

The architectural acceptance sequence is:

1. construct one Game with no server;
2. create player and monster entities through the same birth/composition path;
3. deploy them on the map;
4. begin an Encounter;
5. drive manual and PassController turns synchronously;
6. capture raw causal event batches, including all stored phases in order;
7. select terminal completion/cancel facts from each same cursor range and feed those directly to a subjective reducer;
8. render reducer state through a minimal Pygame client;
9. replay retained in-memory terminal facts into a fresh reducer and compare state at every batch boundary;
10. generate structured combat logs from the actual terminal facts where the migrated event family supports it;
11. compute the existing game summary in-process from its current raw events/log/snapshot inputs.

The Pygame slice does not need HTTP, JSON-over-network contracts, TypeScript models, database persistence, multiprocessing, or multiple games.

Later serialized-replay gate, explicitly blocked on the deferred event codec/coldness work:

1. serialize every raw phase version with concrete subclass identity and lineage;
2. reset the process;
3. deserialize concrete event subclasses;
4. select terminal facts;
5. rebuild the subjective reducer, including world bootstrap, at every batch boundary;
6. regenerate logs without live Entity-registry reads;
7. port summary boundary inputs to state derived from the canonical event/reducer history and structured logs derived from the real events;
8. prove parity with the current raw-event/log/initial-final-snapshot summary before removing those separate snapshot inputs.

## 11. Verification and test-preservation matrix

| Capability | Preserve/port | Obsolete shape to remove |
|---|---|---|
| Entity block construction | one creator builds complete aggregate | tests tied only to `Entity.create` path name |
| Registry and rollback | no residue after failed construction | content bootstrap/runtime singleton setup |
| Entity identity | serialized domain identity and progression | excluded ContentRef identity fields |
| Combat/check/life behavior | focused engine tests | server route wrappers |
| Inventory/equipment | item events and state transitions | backend visual-presentation snapshots |
| Perception | typed sensory events and subjective evidence | direct `push_combat_log` assertions |
| Encounter lifecycle | start/round/turn/end semantics | three server-shaped advancement functions |
| Initiative | complete typed facts and deterministic replay | snapshot-only CombatantState assertions |
| Controller | context-in/decision-out and Pass/manual behavior | live Entity mutation and global registry |
| Action execution | one dispatcher, one causal batch | controller direct `BaseAction.apply()` |
| Combat log | derived from terminal completion/cancel facts | standalone synthetic log injection |
| Summary | preserve current raw-event/log/snapshot capability now; later prove an event/reducer-derived boundary-state port against it | server store/database tests |
| Subjective replay | live callback and retained in-memory terminal-event parity now; serialized parity after codec/coldness work | transport-specific replication contracts |
| Game lifecycle | one process/one active Game | subprocess/multi-game orchestration |

Test handling rule: a test is not obsolete merely because it imports the old server or content system. Preserve the capability when it belongs to the in-process engine; replace only its setup and boundary. Delete tests only when the asserted behavior itself is removed.

## 12. Known risks and rollback boundaries

### Highest risk

1. `Entity.model_post_init` publication and its inverse cleanup.
2. BaseBlock's independent global registration during construction.
3. separating identity construction from GridMap/spatial deployment without losing sensory ordering.
4. action discovery's dependency on behavior/content bindings.
5. perception callback timing before terminal completion/cancellation.
6. maintaining one-decision EventQueue raw causal batch boundaries.
7. controller subclasses in retained tests that rely on a live Entity.
8. scenario assembly's implicit reset and deleted materializers.
9. observer evidence excluded from serialization.
10. summary behavior dependent on standalone combat logs, raw parent UUID lineage, and boundary snapshots.
11. absence of a polymorphic cold-event codec for deferred action/condition families.

### Safe rollback units

- Phase 1 is one atomic import/file move.
- Phase 2 is a value-model ownership cut.
- Phase 3 is one controller protocol cut.
- Phase 4 is one encounter stepping cut.
- Phase 5 is one Game orchestration introduction and callback-lifetime move.
- Phase 6 is the coordinated constructor call-site, generic entity composition/progression, undeployed/silent initial composition, and entity birth/level-event hard cut.
- Phase 7 is scenario deployment rewiring.
- Phase 8 is bounded remaining encounter terminal-event closure after Phase 6 birth facts and Phase 7 world bootstrap, deliberately isolated from mechanical relocation.

Do not mix Phase 8 event-schema expansion into the initial file move. Doing so would make failures impossible to classify as import, behavior, or replay regressions.

## 13. Explicit deferrals

- No BaseBlock redesign yet.
- No complete removal of foundational globals yet.
- No multi-game/process isolation.
- No action-discovery extraction until behavior/content binding is removed.
- No condition architecture rewrite.
- No animation schema.
- No frontend asset-binding migration in this document.
- No server, API, SDK, database, or generated transport models.
- No immutable Entity rewrite; the current engine is a mutable registered aggregate.
- No claim of full serialized combat replay until creation/world/initiative/observer facts and the deferred action/condition event codec/coldness work pass the replay proof.

## 14. Completion definition

The entity/encounter reorganization is complete only when all of the following are true:

- root `entity.py`, `creature_transforms.py`, `controller.py`, `encounter.py`, and `runtime_reset.py` are gone;
- their target modules have the dependency directions documented above;
- there is one low-level entity birth path for every creature and character;
- authored content consumes the entity runtime, never the reverse;
- controllers return decisions and cannot mutate/apply actions;
- Encounter owns combat lifecycle but not game-global projection lifetime;
- Game provides the synchronous one-process boundary used directly by Pygame;
- terminal completion/cancel facts, not server snapshots or combat-log side channels, carry replay-relevant entity/encounter facts;
- live callback reduction and replay of retained in-memory terminal facts agree for the migrated boundary;
- full process-reset serialized replay remains explicitly gated on the later action/condition codec/coldness phase rather than being falsely claimed;
- game summaries remain available from the clean boundary;
- no compatibility facade, import cycle, late import, `TYPE_CHECKING` workaround, or unnecessary reflection was introduced.

## 15. Review record

Two independent reviewers validated this document against the live Python source. Neither reviewer edited the document.

### Reviewer A — entity/encounter/event implementation audit

Corrections required and incorporated:

- distinguished game-global evidence/log callbacks from per-entity sensory pre-completion callbacks;
- inventoried all five out-of-band combat-log callers;
- formalized the missing scalar action-decision/affordance boundary;
- assigned concrete controller storage to Encounter;
- distinguished raw phase ranges from terminal reducer facts;
- removed fixed-opening authoring provenance from required core replay facts;
- added real encounter UUID/turn-state completion ordering and unnecessary reflection cleanup;
- ledgered deferred scattered events and legacy core-content edges;
- removed unused controller lifecycle hooks from the preservation default;
- assigned `EntityCreatedEvent` specifically to Phase 6;
- assigned entity-owned levelling/unlevelling and `EntityLevelAddedEvent`/`EntityLevelRemovedEvent` to Phase 6 while keeping class definitions in content;
- chose silent unpublished item/equipment construction instead of a fictional EventQueue transaction;
- moved the step cursor/batch boundary before all lifecycle work and defined wait/skip ranges.

Final verdict: **APPROVED**.

### Reviewer B — content/construction/scenario/replay boundary audit

Corrections required and incorporated:

- separated entity composition from GridMap/spatial deployment;
- made completion and cancellation terminal truth and added common terminal finalization;
- narrowed immediate replay to in-process facts and exposed the missing later polymorphic codec/coldness work;
- chose Encounter as the sole dispatch authority;
- made concrete content milestones prerequisites for entity/scenario hard cuts;
- defined an event-native, renderer-agnostic creation payload without Entity/ContentRef imports;
- added the complete scenario-assembler capability ledger and all four premades;
- added world initialization for silent map bootstrap;
- constrained event closure away from a general BaseBlock/action/condition rewrite;
- removed duplicate active-Encounter authority;
- completed the frozen legacy-content dependency inventory;
- corrected authored-content/Game dependency direction;
- preserved the full raw phase stream and summary lineage;
- added EventQueue generation identity to cursor ranges;
- split current summary preservation from its later event-derived port.

Final verdict: **APPROVED**.

### Final cross-document ownership revalidation

After the content ledger and entity progression ownership were expanded, both reviewers independently re-read the latest versions of both documents against live source. The final pass required and verified:

- entities own generic create/compose/apply/remove/hydrate verbs, receipts, rollback, and fact publication; content owns definitions, choices, and resolved transforms;
- all constructor-time spatial-publication consumers migrate to explicit `Game.deploy_entity` in the same cut;
- entity birth and progression use one non-reactive, finalized completed-fact path within the existing event machinery;
- progression receipts remain internal to Entity and save hydration regenerates them without duplicating persisted birth/level history;
- `AppliedOriginState` preserves base scores, flexible bonuses, and immutable origin choices separately from Entity species/body/appearance state;
- level events directly carry every reducer-required mechanical/semantic delta/result, including prepared spells, feats, resource recovery, and total-level-dependent origin changes;
- `WorldInitializedEvent` lands before scenario deployment rather than creating a phase cycle;
- the frozen legacy closure includes all 18 currently required modules.

Final verdicts on the revised documents: **Reviewer A — APPROVED; Reviewer B — APPROVED**.
