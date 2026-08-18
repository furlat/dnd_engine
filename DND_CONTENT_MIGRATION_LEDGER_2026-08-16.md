# DND content migration plan and preservation ledger

Date: 2026-08-16  
Status: living migration ledger; entity foundation, all 18 origin features, direct progression/premades, monster convergence, direct scenario deployment, and 126 of 127 frozen baseline item identities are implemented; the oil-barrel spatial transition, deferred action/condition/spell/spatial content, and static presentation cleanup remain  
Basis: direct inspection of active and deprecated Python/JSON source, followed by a live-tree re-evaluation after the entity foundation and first direct-item cut; no other Markdown report is treated as evidence

## 1. Objective

Remove the generic content-system architecture without losing the authored game, character creation, reversible levelling, premade characters, monsters, items, possessions, maps, encounters, or manually authored frontend bindings buried inside it.

The target deliberately separates three different concerns that are currently fused:

```text
A. Construction/composition
   explicit domain Python functions and reversible entity transforms

B. Backend content ledger
   small read-only per-domain definitions keyed by stable domain IDs/enums

C. Frontend binding contract
   client-owned mapping from semantic IDs/properties to actual assets/rendering
```

These concerns may share stable semantic identifiers. They must not share a universal registry/runtime, authenticated `ContentRef`, package graph, provider gateway, renderer schema, or generic JSON invocation protocol.

## 2. Desired gameplay boundary

The content migration serves the same serverless vertical slice as the entity/encounter plan:

```text
plain authored build or scenario definition
    -> direct domain construction functions
    -> one base Entity creation path
    -> ordered reversible entity/item operations
    -> Game / Encounter
    -> terminal Event stream (completion or cancellation)
    -> subjective reducer / summary / Pygame
```

Premade characters are ordinary build definitions. They do not require a database. Monsters and player characters are the same runtime entity kind. Levelling is independent of entity birth and can be applied to an authored monster base.

## 3. Non-negotiable constraints

- No import cycles, local/late imports, `TYPE_CHECKING` graph, unnecessary `getattr`, or compatibility facades.
- Core and BaseBlock ownership are not redesigned in this migration unless separately approved.
- Full action/condition mechanics and presentation redesign remains deferred. Phase 6A is a narrow prerequisite that removes the deleted global content-runtime requirement from behavior admission without redesigning action dispatch, conditions, or controllers.
- One process, one game is sufficient.
- No server, database, SDK, package/plugin, external provider, AI, Codex, or multiprocessing dependency.
- No universal new “content object” replacing `ContentRef` under another name.
- No generic JSON recipe executor.
- Domain IDs are simple enums or validated strings with direct meaning inside their domain.
- Species, ancestry/variant, background, creature kind, class levels, items, equipment, and semantic appearance are ordinary game data.
- Static visual semantics may be authored on entity/item/tile state as enums, IDs, and descriptions.
- The backend must not name sprites, VFX, asset paths, icon files, renderer layers, or frontend animation clips.
- Frontend manual binding data must be preserved before backend presentation fields are removed.
- Terminal completion/cancellation versions remain the authoritative transition facts; content construction must enter that stream as committed creation facts.
- Character levelling must be reversible by exact source-owned receipts.
- Tests are classified by capability, not by obsolete import path.

## 4. Current scale and damage

| Area | Python files | Lines | Finding |
|---|---:|---:|---|
| active `dnd/core/content` | 17 | 6,662 | 15-module frozen generic identity/declaration/presentation closure plus the still-active visual recipe-preset module and package boundary |
| active `dnd/content` | 34 | 14,806 | direct character/item/monster/scenario definitions and builders plus still-legacy spatial recipes/materializers |
| deprecated `content_system_deprecated` | 48 | 18,447 | migration-source runtime and grant implementations; no direct construction path depends on it |
| combined active content surface | 51 | 21,468 | direct domain content now owns construction; the smaller generic closure remains imported by deferred authored behavior |

Additional indicators:

- two imports of the removed `dnd.content_system` path remain across two active Python modules: Sorcerer structural-feature declarations and legacy environment declarations.
- no active production call to `Entity.create` remains; the classmethod is deleted.
- the sole character and monster construction paths both call `compose_entity`; every authored monster reaches the same committed creation transaction.
- 35 active modules outside `dnd/core/content` still import that frozen package.
- 126 of the frozen 127 item identities have direct definitions/builders; the direct catalog contains 146 identities after including 20 explicit semantic wardrobe/loadout variants. Only `environment.blocker.oil_barrel` remains blocked on the deferred spatial-transition cut.
- all nine species, four variants, two backgrounds, and all 18 authored origin feature IDs execute directly or through their owned level/item composition path. Dragonborn ancestry is cold direct data and its breath event carries typed ancestry, damage, geometry, save, and scaling facts without `ContentRef`.
- 85 retained test files still contain the removed `dnd.content_system` path; many exercise valid gameplay capabilities through dead setup infrastructure. Dragonborn, Half-Orc Relentless Endurance, Halfling Lucky/Nimbleness/Naturally Stealthy, and declaration-time item-state regressions now run through direct composition instead of the deleted setup runtime.
- the focused direct migration surface is green, but the complete suite deliberately does not collect yet: 1,124 tests collect and 112 modules error. The largest exact roots are 61 removed `dnd.content_system` imports, 18 deprecated `server` imports, 13 tests importing the deleted legacy class-definition island, and the smaller explicitly deprecated monster/presentation/registry paths. These remain test-port work; no production compatibility module will be restored to make collection appear green.
- the active item visual loader points at a JSON location that was moved to `deprecated/content_data_deprecated`.
- manually authored asset bindings are mirrored into thousands of backend Python lines.

## 5. Root architectural finding

`ContentDeclaration` currently fuses:

- construction callable/parameter schema;
- universal identity and version/hash;
- catalog descriptor and sorting;
- dependency/provenance edges;
- presentation metadata and actual frontend bindings.

This is why deleting a registry breaks character creation, why an item builder knows about renderer variants, why action discovery asks a global behavior gateway who authored it, and why serving a catalog appears to require installing the whole product.

The migration must preserve the authored facts and operations while deleting this universal shell.

## 6. The capability that must be rescued first: reversible composition

The strongest part of the deprecated implementation is receipt-based structural grants.

`CharacterGrantReceipt` records exact installed handles for:

- modifiers and constraints;
- proficiencies;
- hit dice;
- spellcasting sources;
- spell-slot capacity sources;
- spell damage affinities;
- registered actions;
- event handlers;
- learned reaction spells;
- action-economy resources and recovery contributions;
- armor-class formula sources;
- attack multiplicity grants;
- condition immunities;
- senses;
- structural size;
- origin capabilities;
- transient conditions requiring cleanup.

`CharacterGrantInstallation` installs a set of source-owned mutations transactionally and rolls back its partial work in reverse order on exception. `remove_character_grant_receipt(s)` removes committed grants using the same handles. `CharacterCompositionReceipt` groups the ordered origin/class/equipment composition receipts for whole-build removal.

This is the correct foundation for the desired authoring model. The clean formal contract is conceptually:

```python
AppliedEntityStep = apply(entity, authored_step)

# AppliedEntityStep carries:
# - the same mutable Entity
# - an exact receipt describing everything installed

entity = undo(entity, applied_step.receipt)
```

The engine is currently mutable and globally registered, so claiming a pure immutable Haskell value transform would be false. The useful functional property is composability and invertibility at the boundary:

```text
Entity --apply species--> Entity + receipt A
       --apply background--> Entity + receipt B
       --apply class level 1--> Entity + receipt C
       --apply class level 2--> Entity + receipt D
       --apply loadout--> Entity + receipt E

undo E, D, C, B, A -> base Entity
```

The receipt machinery must be extracted from:

- `ContentRef`;
- `ContentSystemRuntime`;
- behavior gateways;
- package hashes;
- server/client authority concepts;
- character-only naming where the handles are valid for any Entity.

Target ownership: neutral receipt/transaction primitives belong with entity creation/composition under `dnd/entities`; authored species/class/monster/item steps belong under `dnd/content`.

## 7. Character creation and levelling preservation contract

The following are acceptance requirements, not optional salvage:

1. Every player, monster, NPC, summon, and premade starts from the same low-level entity creation function.
2. A neutral player body remains constructible before species/background/class composition.
3. Species and optional species variant are actual serialized entity data.
4. Background is actual serialized entity data.
5. Concrete creature identity is distinct from broad `CreatureType` and is actual serialized entity data.
6. Ordered class levels are actual entity progression data.
7. Applying a class level is independent of initial entity creation.
8. A monster base can receive the same class-level operation as a player character.
9. Every species/background/class/subclass/level operation returns an exact reversible receipt.
10. Removing levels occurs in a validated order and cannot leave source-owned handles behind.
11. Rebuilding from the ordered level ledger produces equivalent mechanics.
12. First-class and multiclass proficiency packages remain distinct.
13. Multiclass prerequisites and ordered levels remain validated.
14. Subclass choice is stable after selection.
15. Hit dice, spell sources, known spells, reaction spells, slots, resources, ASIs, feats, metamagic, and affinities remain source-owned.
16. Starting equipment is direct item construction followed by entity-owned construction-only silent placement before the birth commit; ordinary event-publishing inventory/equipment operations begin only after the Entity exists in the event stream.
17. Premades are named build plans using the exact same operations.
18. No DB, server, runtime content installation, or package bootstrap is required.

## 8. Identity model to replace content refs

Current `Entity` fields `content_ref`, `character_species_ref`, `character_species_variant_ref`, and `character_background_ref` are excluded from serialization. There is no class/subclass/level identity ledger.

The replacement should be narrow and domain-native:

```text
Entity
├── entity_kind_id                 # concrete authored root: goblin, human body, wolf, etc.
├── creature_type                 # existing broad rules enum
├── species                       # optional Species enum/domain ID
├── species_variant               # optional compatible variant enum/domain ID
├── background                    # optional Background enum/domain ID
├── applied_origin_state          # optional persisted construction inputs
│   ├── base ability-score allocation
│   ├── flexible ancestry ability bonuses
│   └── immutable origin choice selections
├── semantic body/appearance state # separate mutable Entity game data
└── progression
    └── ordered class levels
        ├── stable level-step ID
        ├── class ID
        ├── resulting class level
        ├── optional subclass ID
        └── formal choices
```

Rules:

- built-in closed sets should prefer enums already available or new dependency-leaf enums;
- open authored families may use one simple namespaced semantic string, not a five-part authenticated reference;
- IDs must serialize without a registry;
- renderer IDs are forbidden;
- definition version hashes do not belong on the live Entity;
- save migrations, if later needed, are save-format concerns, not universal content identity.

Ownership is critical:

- persisted entity identity and the applied progression ledger belong in dependency-leaf `dnd/types` models (extend `dnd/types/creatures.py`, `dnd/types/progression.py`, and `dnd/types/items.py` where appropriate);
- Entity and core events may import those leaf values;
- authored species/class/item definitions and grant schedules belong under `dnd/content` and import the leaf values;
- Entity, blocks, and core events never import `dnd/content` merely to represent their own persisted state.

The live applied-level row is smaller than an authored class definition: stable step ID, class/subclass IDs, resulting levels, and normalized selected values. `AppliedOriginState` contains exactly the base score allocation, flexible bonuses, and immutable origin choices required to reconstruct origin mechanics. Species/variant/background and semantic body/appearance are separate Entity fields because they are game state in their own right. Choice requirements, grant maps, descriptions, and builders remain authored content above the engine.

## 9. Authored character content that must survive

### 9.1 Species

The deprecated origin source contains nine species:

1. dragonborn;
2. dwarf;
3. elf;
4. gnome;
5. half-elf;
6. half-orc;
7. halfling;
8. human;
9. tiefling.

### 9.2 Species variants

Four variants exist:

1. hill dwarf;
2. high elf;
3. rock gnome;
4. lightfoot halfling.

### 9.3 Backgrounds

Two backgrounds exist:

1. acolyte;
2. adventurer.

### 9.4 Class and subclass definitions

Active progression definitions cover:

- Fighter with Champion;
- Barbarian with Berserker;
- Sorcerer with Draconic Bloodline.

The active files retain definitions and choice schedules, but the actual grant appliers remain in the deprecated folder. Definitions without appliers are not a preserved levelling system.

### 9.5 Origin/class choices at risk

The existing source includes real choices and grants that must not be flattened away:

- Dragonborn elemental ancestry and breath/resistance behavior;
- Dwarf tool choice;
- High Elf cantrip choice;
- Human additional language;
- Half-Elf skills/languages;
- Tiefling level-gated innate spells;
- Acolyte and Adventurer proficiencies/holdings;
- class skill choices;
- starting proficiency choices;
- fighting style;
- subclass;
- cantrips and spells known;
- spell replacement;
- metamagic;
- ASI or feat;
- starting equipment and apparel package choices.

### 9.6 Premade builds

Four full premade definitions exist in deprecated source:

| ID | Composition | Important holdings/choices |
|---|---|---|
| `hero.barbarian_l5_berserker_torch` | Barbarian 5 / Berserker | greataxe, STR ASI, pit-fighter wrap, boots, torch |
| `hero.fighter_l5_shield_torch` | Fighter 5 / Champion | sword/shield, dueling, STR ASI, longbow, torch |
| `hero.sorcerer_l5_standard_torch` | Sorcerer 5 / Draconic Bloodline | dagger, CHA ASI, quickened/twinned metamagic, authored spells, torch |
| `hero.fighter_2_sorcerer_3_spellblade` | Fighter 2 + Sorcerer 3 | sword/shield, dueling, metamagic/spells, spellblade crown, torch |

Active `dnd/premade_characters.py` declares all four IDs but exposes factory wrappers for only three. The multiclass Spellblade is therefore particularly easy to lose during a superficial port.

All four must become plain named build plans over the same base-body, origin, class-level, and holdings operations.

### 9.7 Prepared spells and feature toggles

`durable_characters.py` also persists mutable-between-games character loadout selections separately from structural build state:

- prepared spells grouped by exact spellcasting source;
- feature enabled/disabled selections.

The validator checks that prepared-spell sources exist and are active, spells are entitled and rank-accessible, rows are unique/ordered, and feature IDs resolve. Runtime application of every toggle/prepared-loadout behavior is not complete today, but the authoring data and validation surface are real.

Preserve them as plain dependency-leaf loadout selections using direct spellcasting-source, spell, and feature IDs. Delete loadout revision/digest/server authority fields. Explicitly mark runtime application gaps as unimplemented rather than silently deleting the selections. Add them to premade/build validation and save/hydration gates.

## 10. Single construction and composition model

### 10.1 Base birth

`dnd/entities/entity_creation.py::create_entity` creates the universal undeployed block aggregate. `compose_entity` owns ordered transform application, silent initial item placement, final validation, the committed creation event, and complete rollback. Neither function knows a character class, species definition registry, monster catalog, premade, or renderer.

### 10.2 Ownership of creation, transformation, and progression

The entity package owns the generic verbs and their invariants:

```text
dnd/entities/entity_creation.py
    create_entity
    compose_entity
    construction-only silent item placement
    validate / commit / rollback

dnd/entities/entity_progression.py
    apply_level
    remove_last_level
    hydrate_progression              # unpublished save hydration only
    ordered applied-level ledger and live receipt accounting

dnd/entities/creature_transforms.py
    EntityTransform / applied-transform receipt protocol
    generic structural transforms shared by every Entity
```

The content package owns the specific meanings:

```text
Human / Goblin / Fighter level 3 / Berserker / flaming sword / premade
    -> validate authored choices
    -> choose dependency-leaf semantic IDs and applied-level row
    -> resolve an ordered sequence of concrete EntityTransform operations
    -> call the entity-owned composition or progression verb
```

This is not merely file placement. Entity creation, levelling, unlevelling, unpublished save hydration ordering, rollback, and event publication remain usable without importing any authored catalog. Conversely, content does not mutate Entity ledgers or emit progression events itself. It resolves authored definitions into inputs for those methods.

`apply_level` accepts an already-resolved applied-level row and concrete transforms. It does not accept a class ID and perform a content lookup. This allows the same operation to level a player or an authored monster without creating an `entities -> content` dependency.

### 10.3 Authored steps

Each authored operation has an explicit input and receipt:

```text
apply entity identity
apply species
apply species variant
apply background
apply one class level
apply monster base mechanics
apply one possession/loadout
apply semantic appearance/body facts
```

Authored functions may call rule implementations from `dnd/classes`, `dnd/origins`, `dnd/items`, actions, spells, or blocks. They do not install a generic construction/catalog runtime. Until the later behavior migration, action/condition admission may still cross the explicitly frozen legacy behavior-identity substrate; no new content concern may use it.

### 10.4 Ordered composition

One coordinator accepts a build plan and applies steps in a deterministic order:

1. create an undeployed base entity (object/block identity may register, but no position index, GridMap entry, spatial-enter event, or spatial sensory observer exists yet);
2. install concrete entity identity/body facts;
3. install species;
4. install optional species variant;
5. install background;
6. install monster-base mechanics if this is a monster definition;
7. apply ordered class levels, if any;
8. materialize direct item builders;
9. add holdings/intrinsic items;
10. equip requested slots;
11. apply current charges, stack count, and durability;
12. validate final aggregate;
13. commit `dnd/core/events/entity_events.py::EntityCreatedEvent` with event-native renderer-agnostic values, never a live Entity/ContentRef payload;
14. retain the ordered live composition receipt for exact in-process removal; saves persist semantic origin/level selections and regenerate receipts during hydration;
15. let Game deploy the committed entity to a position, attach spatial sensing, and emit the existing spatial-enter fact.

This is one composition protocol. A monster normally uses steps 2, 6, 8-10. A player normally uses 2-5, 7-10. A classed monster uses all relevant steps. A premade is only a stored selection of steps.

### 10.5 Rollback

If any step fails:

- remove installed item/equipment state in reverse order;
- remove class grants in reverse level order;
- remove background/variant/species receipts;
- clean base entity publication using the existing entity rollback;
- verify no global action, handler, modifier, block, entity, map, or sensory residue remains.

Until BaseBlock supports cold construction, this rollback is a real required feature.

Object rollback alone is not enough because current inventory/equipment operations permanently store event phase versions before final build validation. Initial composition needs an explicit unpublished-construction event boundary:

- dedicated construction-only silent item placement/equipment APIs reuse the ordinary pure validation and mechanical attachment rules but invoke no event handlers/callbacks and store no event phases;
- rollback uses matching silent removal/unregistration and does not call the event-publishing item-destroy path;
- successful commit emits one terminal EntityCreated fact containing the final initial item/inventory/equipment state;
- later gameplay item/equipment changes use the ordinary typed events;
- spatial deployment follows as its own typed event after creation commit.

No EventQueue transaction is introduced: current batching does not delay immediate handlers/callbacks and cannot roll them back. This is a bounded construction API change using the same mechanics without gameplay event delivery. Until it exists, the plan must not claim event-atomic entity creation.

### 10.6 Exact active low-level creation-call ledger

| Call site | Current authored path | Target |
|---|---|---|
| `dnd/player_character_body.py:109` | neutral player body | direct `create_entity` called by `content/characters/player_body.py` |
| `dnd/monsters/bestiary.py:207` | goblin | direct monster definition/composition |
| `dnd/monsters/bestiary.py:336` | skeleton | direct monster definition/composition |
| `dnd/monsters/bestiary.py:463` | goblin archer | direct monster definition/composition |
| `dnd/monsters/bestiary.py:583` | generic caster base used by goblin caster | direct monster definition/composition or retain only as an explicit reusable caster step |
| `dnd/monsters/bestiary.py:739` | skeleton warrior | direct monster definition/composition |
| `dnd/monsters/bestiary.py:857` | skeleton archer | direct monster definition/composition |
| `dnd/monsters/bestiary.py:987` | skeleton warlock | direct monster definition/composition |
| `dnd/monsters/circus_fighter.py:113` | Circus Fighter warrior | direct monster definition/composition |
| `dnd/monsters/srd_roster.py:1694` | generic SRD creature aggregate | one shared SRD base composition operation |

The wrapper/materializer layers above these calls are:

| Wrapper | Current role | Target disposition |
|---|---|---|
| `dnd/monsters/bestiary_content.py` | universal declarations around legacy bestiary constructors | delete after direct monster maps exist |
| `dnd/monsters/configured_srd_creatures.py` | presentation/wardrobe declarations over SRD roots | export and preserve all 21 exact mappings; keep classified semantic state backend-side, move classified asset bindings client-side, then delete wrapper shell |
| `dnd/classes/content_factories.py` | class-root declaration -> deprecated character materializer | delete after direct character composition |
| `dnd/premade_characters.py` | premade declaration -> class-root materializer | replace with plain premade maps |
| `dnd/scenarios/encounter_assembler.py` | generic creature materializer -> deployment | call direct definitions through Game deployment |

No new “unified materializer” should sit above this target. The unification is the shared base creator plus ordinary typed composition functions.

## 11. Levelling and unlevelling model

The useful `ClassLevelEntry` concept should survive but lose `ContentRef` and revision-server vocabulary.

A class-level step should contain:

- stable step ID;
- resulting total character level;
- class enum/ID;
- resulting level in that class;
- optional subclass enum/ID;
- validated choices;
- a stable authored source/step ID stored in save state.

The current deprecated receipts do **not** already provide incremental levelling. `CharacterCompositionReceipt` is a flat whole-build receipt; proficiency bonus, spell sources/provider levels, known spells, and slot capacity are installed from aggregate final-build calculations. Only some handle families, such as hit dice, are visibly level-granular. `CharacterGrantReceipt` also has no durable level-step ownership field.

Therefore Phases 2 and 6 are partly a redesign, not a mechanical extraction:

- split direct grants into per-step source-owned deltas where that is honest;
- model aggregate derived values such as proficiency bonus, multiclass slots, and spell-source provider level as reconciliation from the persisted ordered progression ledger;
- keep runtime UUID handles only on the live process receipt—they are ephemeral undo handles and never save-stable identity;
- persist semantic source/step IDs and selected values;
- after load, restore the original persisted event history, resolve `AppliedOriginState` plus ordered level rows, and regenerate runtime handles through entity-owned unpublished `hydrate_progression` without publishing duplicate birth/level facts;
- total-level-dependent origin grants are resolved together with each level step, so adding/removing a class level updates them within the same receipt transaction;
- removing the last level uses the entity-owned live receipt plus aggregate reconciliation; arbitrary edits to a committed Entity are expressed as ordered removals/additions and never call silent hydration.

Authored resolution in `class_level_content.py`:

1. validate class/subclass/choice existence and multiclass prerequisites against the current semantic ledger;
2. resolve entry proficiency mode and exact automatic/selected grants from direct authored maps;
3. produce one dependency-leaf `AppliedClassLevel` plus ordered concrete `EntityTransform` operations;
4. pass those values to entity-owned `apply_level`.

Generic application in `dnd/entities/entity_progression.py`:

1. validate contiguous total level, resulting per-class level, and subclass continuity in the ordered ledger;
2. apply the resolved transforms transactionally;
3. reconcile aggregate proficiency/spell/slot mechanics;
4. append the semantic class-level row and runtime receipt only after success;
5. publish non-cancelable post-commit `EntityLevelAddedEvent` with resulting facts for a committed Entity; if fact publication fails, undo the mutation and ledger append.

Removal algorithm:

1. only remove the last level by default;
2. resolve its live receipt from entity-owned progression state and remove it in reverse dependency order; content/application callers never supply or retain the receipt;
3. update class/subclass/spell-slot/level facts;
4. publish non-cancelable post-commit `EntityLevelRemovedEvent`, rebuilding/reapplying the removed step if fact publication fails;
5. for an arbitrary committed edit, remove back to the chosen boundary and reapply resolved steps as ordinary fact-producing level operations.

No character build coordinator or content materializer owns levelling. The same entity-owned function accepts any Entity satisfying the prerequisites; content supplies only the resolved authored step.

## 12. Monster creation preservation

### 12.1 Current overlapping paths

Current authored monster construction is spread across:

- eight hand-built NeuroDragon bestiary roots;
- content-declaration wrappers around those roots;
- 27 SRD creature configurations;
- configured NeuroDragon visual/wardrobe wrappers over SRD creatures;
- an independent Circus Fighter constructor;
- generic removed creature materialization;
- scenario roster materialization.

### 12.2 Hand-built roots

The live bestiary has:

- goblin;
- skeleton;
- goblin archer;
- generic caster;
- goblin caster;
- skeleton warrior;
- skeleton archer;
- skeleton warlock.

Circus Fighter has a separate warrior path.

### 12.3 SRD roster

The 27 SRD configurations are:

1. commoner;
2. bandit;
3. cultist;
4. guard;
5. tribal warrior;
6. kobold;
7. acolyte;
8. scout;
9. thug;
10. spy;
11. berserker;
12. bandit captain;
13. priest;
14. cult fanatic;
15. knight;
16. veteran;
17. mage;
18. orc;
19. hobgoblin;
20. bugbear;
21. gnoll;
22. ogre;
23. wolf;
24. dire wolf;
25. zombie;
26. ogre zombie;
27. ghoul.

The useful existing distinction in `construct_srd_creature` is intrinsic creature structure versus default possessions. Preserve that distinction.

### 12.4 Target model

Each monster definition contains:

- concrete semantic creature ID;
- name and authored description;
- broad creature type, size, anatomy/body semantics, and movement/senses;
- base ability/health/proficiency facts;
- intrinsic traits/actions/attacks;
- optional default possession/loadout plan;
- optional static visual semantics, never client asset names.

Construction is:

```text
create_entity
    -> apply monster base receipt
    -> apply intrinsic traits/actions
    -> construct/add/equip default possessions
    -> optionally apply ordinary class levels
```

Remove duplicate wrapper layers such as legacy `create_*` plus content declaration plus generic materializer. Cold definition maps contain no build function. A separate builder dispatch map may point directly to the one build function and is never imported by the aggregate ledger; it must not require universal recipe serialization.

## 13. Item, inventory, and equipment preservation

### 13.1 Mechanics to keep

Keep the real mechanics in:

- `dnd/blocks/base_item.py`;
- `dnd/blocks/inventory.py`;
- `dnd/blocks/equipment.py`;
- authored item construction modules;
- possession placement and rollback;
- character holding restoration.

Preserve:

- intrinsic, equipped, or inventory placement;
- slot compatibility;
- multi-slot collision detection;
- stack count and compatibility;
- charges;
- durability;
- persisted item instance identity where saves need it;
- exact cleanup on partial construction failure.

### 13.2 Generic item materialization to remove

The deprecated generic item materializer mostly resolves a universal recipe through a registry and invokes the stored factory. Replace it with direct typed builders and a small item placement operation.

Starting equipment and monster possessions become ordered data containing:

- item domain ID or direct builder selection;
- builder parameters when genuinely variable;
- quantity/stack/charges/durability;
- inventory/equipment/intrinsic disposition;
- exact equipment slot when equipped.

### 13.3 Backend visual fields to remove after binding preservation

Current `BaseItem`/presentation contracts include renderer-facing fields such as:

- visual item name;
- visual variant ID;
- equipped visual policy;
- render/loadout slot and layer;
- map character;
- icon/presentation kind.

These do not belong in mechanical item construction.

The item itself may retain semantic game data such as:

- form/category;
- material;
- color or palette semantics;
- damage/elemental state;
- flame or glow semantic state;
- size/shape;
- worn location;
- authored natural-language description;
- stable semantic item ID.

The frontend decides which asset, sprite, shader, VFX, layer, and animation realizes those facts.

### 13.4 Exact active item-ID baseline

A source scan of active item factories and their statically authored spec tables yields **127 item IDs**. Reachability from current premades/scenarios is not a retention rule: all 127 mechanical identities are initially **RETAIN**. A later deletion requires an explicit per-ID decision and evidence that the gameplay item itself—not merely its registry/presentation wrapper—is obsolete. Behavior-bearing items may defer action/spell identity cleanup to Phase 13, and all renderer bindings follow Section 15, but neither disposition deletes the item.

| Family | Count | Default disposition |
|---|---:|---|
| weapon | 45 | retain mechanics/identity; defer behavior binding where applicable |
| apparel | 24 | retain item/loadout semantics; migrate renderer binding |
| armor | 17 | retain mechanics/identity; migrate renderer binding |
| environment | 15 | retain gameplay objects; defer action/spell binding where applicable |
| spell item | 9 | retain item mechanics; defer spell identity cleanup |
| consumable | 8 | retain mechanics/identity |
| gear | 6 | retain mechanics/identity; Field Kit action binding deferred |
| shield | 2 | retain mechanics/identity |
| equipment | 1 | retain mechanics/identity |

**Apparel (24; all RETAIN):** `apparel.armored_boots`, `apparel.bracers`, `apparel.chain_coif`, `apparel.cloth_hood`, `apparel.cloth_shoes`, `apparel.common_clothes`, `apparel.costume`, `apparel.crown`, `apparel.fine_clothes`, `apparel.gauntlets`, `apparel.great_helm`, `apparel.horned_helmet`, `apparel.iron_helmet`, `apparel.leather_boots`, `apparel.leather_gloves`, `apparel.leather_hood`, `apparel.leather_shoes`, `apparel.monster_hands`, `apparel.monster_helm`, `apparel.robes`, `apparel.sandals`, `apparel.spellblade_crown`, `apparel.travelers_clothes`, `apparel.wizard_hat`.

**Armor (17; all RETAIN):** `armor.armor_scraps`, `armor.breastplate`, `armor.chain_mail`, `armor.chain_shirt`, `armor.circus.performer_leather`, `armor.cloth`, `armor.creature.dire_wolf_natural`, `armor.creature.wolf_natural`, `armor.half_plate`, `armor.hide`, `armor.leather`, `armor.padded`, `armor.plate`, `armor.ring_mail`, `armor.scale_mail`, `armor.splint`, `armor.studded_leather`.

**Consumables (8; all RETAIN):** `consumable.acid_flask`, `consumable.healing_potion`, `consumable.potion_greater_invisibility`, `consumable.potion_haste`, `consumable.weapon_coat.concentration_fire`, `consumable.weapon_coat.fire`, `consumable.weapon_coat.lightning`, `consumable.weapon_coat.timed_fire`.

**Environment items (15; all RETAIN):** `environment.arcane_device`, `environment.arcane_machine_gun`, `environment.blocker.barricade`, `environment.blocker.boulder`, `environment.blocker.crate`, `environment.blocker.oil_barrel`, `environment.campfire`, `environment.directional_door`, `environment.directional_wall`, `environment.door`, `environment.fireball_cannon`, `environment.spell_object.heroes_feast`, `environment.storage_chest`, `environment.trap_lever`, `environment.wall_torch`.

**Equipment (1; RETAIN):** `equipment.portable_torch`.

**Gear (6; all RETAIN):** `gear.common_clothes`, `gear.field_kit`, `gear.holy_symbol`, `gear.incense`, `gear.prayer_book`, `gear.vestments`.

**Shields (2; all RETAIN):** `shield.shield`, `shield.wooden`.

**Spell items (9; all RETAIN):** `spell_item.scroll_fire_bolt`, `spell_item.scroll_fireball`, `spell_item.scroll_hold_person`, `spell_item.scroll_invisibility`, `spell_item.scroll_mage_armor`, `spell_item.scroll_magic_missile`, `spell_item.scroll_spike_growth`, `spell_item.wand_fire`, `spell_item.wand_magic_missiles`.

**Weapons (45; all RETAIN):** `weapon.arcane_staff`, `weapon.assassin_dagger`, `weapon.battleaxe`, `weapon.circus.flaming_scimitar`, `weapon.circus.longsword_plus_one`, `weapon.circus.rusty_dagger`, `weapon.circus.soul_draining_morningstar`, `weapon.club`, `weapon.creature.bandit_captain_thrown_dagger`, `weapon.creature.bugbear_morningstar`, `weapon.creature.dire_wolf_bite`, `weapon.creature.ghoul_bite`, `weapon.creature.ghoul_claws`, `weapon.creature.kobold_sling`, `weapon.creature.ogre_greatclub`, `weapon.creature.ogre_thrown_javelin`, `weapon.creature.ogre_zombie_morningstar`, `weapon.creature.spy_hand_crossbow`, `weapon.creature.thrown_javelin`, `weapon.creature.wolf_bite`, `weapon.creature.zombie_slam`, `weapon.dagger`, `weapon.dart`, `weapon.double_bladed_sword`, `weapon.greataxe`, `weapon.greatsword`, `weapon.handaxe`, `weapon.heavy_crossbow`, `weapon.javelin`, `weapon.light_crossbow`, `weapon.light_hammer`, `weapon.longbow`, `weapon.longsword`, `weapon.mace`, `weapon.morningstar`, `weapon.quarterstaff`, `weapon.rapier`, `weapon.scimitar`, `weapon.shortbow`, `weapon.shortsword`, `weapon.sickle`, `weapon.sling`, `weapon.spear`, `weapon.trident`, `weapon.warhammer`.

Phase 0 freezes this exact list and source location for each ID. Phase 3 must produce an explicit disposition for every row, even when no current premade or scenario reaches it. A direct-builder test is required when the item migrates. A behavior-bearing item may remain explicitly blocked until Phase 6A or Phase 13, but its identity, mechanics, source, bindings, and preservation test disposition cannot disappear. The count is re-derived mechanically after every item migration so newly discovered dynamic definitions cannot disappear outside the ledger.

## 14. Appearance and visual semantic boundary

`dnd/blocks/appearance.py` and `dnd/presentation.py` currently mix semantic game state with renderer vocabulary. The migration must not simply delete appearance: ancestry, body, equipment, and mutable visual traits are game data.

Backend-owned semantic examples:

- humanoid/goblin/skeleton/zombie body kind;
- ancestry/species/variant;
- body size and proportions relevant to rules/authorship;
- skin/hair/eye/color semantics;
- horns, tail, wings, scars, flame, frost, corruption, glow;
- equipped semantic item state;
- a sentence such as “the sword's red-orange flames grow on a critical hit.”

Frontend-owned binding examples:

- JPEG/PNG path;
- sprite sheet name;
- exact VFX prefab;
- renderer loadout layer;
- Unreal/Godot/Unity/Pygame resource;
- icon file;
- animation clip/state-machine key.

Animation/actions remain deferred. This phase only creates a clean static semantic/state boundary and preserves the existing manual asset ledger before removal.

## 15. Source, authored-catalog, and frontend-binding artifacts that must be preserved

The following JSON files contain substantial authored work:

| Artifact | Current location | Contents | Migration rule |
|---|---|---|---|
| authored item visuals | `deprecated/content_data_deprecated/ledgers/neuroclient_authored_item_visuals.json` | schema 3; 77 categories; 205 variants; 76 supported categories; 87 factory/slot bindings; 1 recorded source-ID collision | freeze/checksum, copy to client binding domain, preserve collision evidence, validate coverage |
| content icon bindings | `deprecated/content_data_deprecated/ledgers/content_icon_bindings.json` | 671 definition bindings; 205 recipe-preset bindings | preserve as migration input; remap to simple semantic IDs before backend deletion |
| game icon asset index | `deprecated/content_data_deprecated/ledgers/neuroclient_game_icon_asset_index.json` | 521 indexed assets | client-owned evidence/index; backend must stop importing it |
| SRD source coverage | `deprecated/content_data_deprecated/ledgers/srd_5_1_source_coverage.json` | 925 rows | preserve as audit/source data, not runtime content machinery |
| SRD source | `deprecated/content_data_deprecated/sources/srd_5_1_cc.json` | source rules data | retain for attribution/audit/authoring, not runtime registry installation |
| NeuroDragon source | `deprecated/content_data_deprecated/sources/neurodragon_original_b2b3930.json` and `.txt` | source authored data | retain for attribution/audit/authoring |
| authored scenario catalog | `dnd/scenarios/authored_catalog.json` | sole payload for 58 rosters/141 members, 10 deployments, 39 encounters/78 roster slots | checksum and preserve/migrate with scenario definitions; never regenerate from wrapper modules |

The JSON ledgers are not the complete frontend-binding inventory. Exact authored crosswalks also exist only in Python:

| Python source | Manual binding content to export before editing |
|---|---|
| `deprecated/content_system_deprecated/character_appearance.py` | character option-token -> renderer category/tint crosswalks plus three exact premade appearance selections |
| `deprecated/content_system_deprecated/character_origin_definitions.py` | species/variant/background visual-variant bindings embedded in authored origin definitions |
| `deprecated/content_system_deprecated/builtin_character_builds.py` | all four premade-to-appearance selections, including Spellblade's intentional reuse of the Fighter appearance |
| `dnd/monsters/bestiary.py` | semantic bestiary appearance constants |
| `dnd/monsters/bestiary_content.py` | seven exact bestiary wardrobe keys |
| `dnd/monsters/configured_srd_creatures.py` | 21 configured-SRD wardrobe maps |
| `dnd/monsters/srd_roster.py` | exact SRD creature icon/visual-variant keys and placeholder tint choices |
| `dnd/player_character_body.py` | neutral player-body visual variant default |
| `dnd/premade_characters.py` | premade portrait, icon, and exact visual-variant selections |
| `dnd/core/base_tiles.py` | tile-kind-to-sprite binding table |
| `dnd/scenarios/battlefield_catalog.py` | five traversal presentation keys plus the authored `gap.png` battlefield sprite binding |
| `dnd/content/spatial_effect_recipes.py` | authored spatial-effect VFX profile names; export now, migrate ownership only in the later spatial presentation cut |
| `dnd/extensions/field_focus.py` | Field Kit item identity/presentation plus its action content/binding choices |
| `dnd/items/authored_presentations.py`, `authored_variant_inventory.py`, `authored_variant_presets.py`, `apparel_presets.py` | authored item visual mappings/presets |
| item/environment builder modules (`weapons.py`, `armors.py`, `consumables.py`, `spell_items.py`, `torches.py`, `acolyte_gear.py`, `environment.py`, `environment_content.py`, `environment_interactables.py`, and monster item modules) | every literal visual/presentation field attached during construction |

Phase 0 must checksum these Python files and export a deterministic crosswalk ledger with source file/line, semantic definition ID, field, and exact value. No appearance, configured-creature, battlefield, or item wrapper may be deleted until every row is mechanically classified as backend semantic state, client asset binding, or intentionally obsolete with explicit approval.

Migration sequence for visual bindings:

1. record checksums and immutable copies;
2. enumerate every existing semantic definition/recipe ID referenced by the ledgers;
3. create an explicit old-ID -> new semantic-ID mapping;
4. preserve the single collision record rather than silently normalizing it;
5. install mappings in the client/Pygame binding domain;
6. verify all 205 authored variants and all expected icon bindings are addressable;
7. permit unbound semantic content to fail visibly in client authoring diagnostics, not backend mechanics;
8. prove every Python-only tile/body/premade/monster/spatial/extension crosswalk row is represented or explicitly dispositioned;
9. only then delete backend generated icon maps and renderer presentation fields that are not still part of the frozen deferred-behavior closure.

Do not regenerate these mappings from Python class or function names. That would discard manual authoring decisions.

## 16. Backend content ledger after the hard cut

The backend still needs to enumerate what it can create. That does not require the old registry.

Each domain owns a small immutable map of **cold plain definitions**:

```python
MONSTER_DEFINITIONS: Mapping[MonsterId, MonsterDefinition]
ITEM_DEFINITIONS: Mapping[ItemId, ItemDefinition]
SPECIES_DEFINITIONS: Mapping[Species, SpeciesDefinition]
CLASS_DEFINITIONS: Mapping[CharacterClass, ClassDefinition]
PREMADE_BUILDS: Mapping[PremadeId, CharacterBuild]
ENCOUNTER_DEFINITIONS: Mapping[EncounterId, EncounterDefinition]
```

A read-only `content_ledger.py` may project common catalog rows:

```text
domain kind
stable semantic ID
display name
description
semantic tags
availability/support status if it is a real gameplay fact
```

It must not own:

- construction callables;
- global runtime installation;
- arbitrary package imports;
- dependency graphs inferred at startup;
- provider behavior binding;
- frontend asset mappings;
- content contract hashes/digests;
- provenance workflow state;
- generic parameter schemas;
- save revisions;
- database identifiers.

Construction can use direct domain definition maps without going through the aggregate ledger. Serving a future API catalog is a projection over those maps, not the owner of them.

Coldness is transitive: a definition module imported by `content_ledger.py` may import only dependency-leaf IDs/value schemas and other cold metadata. It may not contain/import Entity, blocks, actions, runtime rule objects, or builder callables. Builder dispatch lives in separate modules/maps that import the cold definitions; the ledger never imports builder dispatch. This split prevents `ContentDeclaration` from being recreated as a “definition” that still carries construction.

## 17. Compact target content layout

This target avoids duplicate basenames and avoids creating a file for every class or creature:

```text
dnd/types/                              # existing dependency-leaf package
├── creatures.py                        # concrete entity/species/variant/background IDs and body semantics
├── progression.py                      # AppliedOriginState, applied class-level rows,
│                                       # and persisted selected values
└── items.py                            # item semantic state used by Entity/blocks/events

dnd/content/
├── __init__.py                         # docstring only; no re-exports
├── content_ledger.py
│   [-> cold domain definition maps only; transitive leaf boundary]
│   [<- Pygame selection/application code; future API adapter]
│   read-only aggregate listing; never construction authority
│
├── characters/
│   ├── __init__.py                     # docstring only
│   ├── character_definitions.py
│   │   [-> types and cold value schemas only]
│   │   [<- content_ledger, class-level resolver/build coordinator/premades]
│   │   cold choice requirements and species/class definition values; no builders
│   │
│   ├── character_grants.py
│   │   [-> character definitions, entities receipt primitives, blocks, rules modules]
│   │   [<- class_level_content.py, monster class-level composition]
│   │   direct grant plans/appliers; no ContentRef/runtime gateway
│   │
│   ├── class_level_content.py
│   │   [-> definitions, grants, core.progression, entities/entity_progression.py]
│   │   [<- character_builds.py, application/content commands]
│   │   validate class/subclass/choices and resolve specific authored levels
│   │   into AppliedClassLevel + EntityTransform inputs; calls entity-owned verbs
│   │
│   ├── origin_content.py
│   │   [-> definitions, grants, dnd/origins rule implementations]
│   │   [<- character_builds.py]
│   │   nine species, four variants, two backgrounds
│   │
│   ├── character_builds.py
│   │   [-> entity creation/composition, definitions, origins,
│   │       class_level_content.py, item loadouts]
│   │   [<- premade_builds.py, user/Pygame creation flow]
│   │   authored build resolution/coordinator; delegates generic ordering,
│   │   commit, and rollback to entities.compose_entity
│   │
│   ├── player_body.py
│   │   [-> entity creation, block configs, standard actions]
│   │   [<- character_builds.py]
│   │   neutral body recipe
│   │
│   └── premade_builds.py
│       [-> cold character definitions and cold item loadout IDs only]
│       [<- content_ledger.py, Pygame selection]
│       four cold plain premade build plans; character_builds executes them
│
├── creatures/
│   ├── __init__.py                     # docstring only
│   ├── monster_definitions.py
│   │   [-> types and cold value schemas only]
│   │   [<- content_ledger.py, monster_builders.py, scenarios]
│   │   cold hand-built monster metadata/mechanical definitions; no builders
│   │
│   ├── srd_monster_definitions.py
│   │   [-> types, monster_definitions.py, cold item/action IDs]
│   │   [<- content_ledger.py, monster_builders.py, scenarios]
│   │   27 cold SRD definitions
│   │
│   ├── monster_builders.py
│   │   [-> cold definitions, entity creation/transforms, blocks, monster rule modules]
│   │   [<- character builds/application commands/scenario deployment]
│   │   direct monster composition dispatch; never imported by content_ledger
│   │
│   └── monster_possessions.py
│       [-> direct item builders, inventory/equipment blocks]
│       [<- monster_builders.py and scenario deployment]
│       placement plus exact receipt/rollback
│
├── items/
│   ├── __init__.py                     # docstring only
│   ├── authored_item_definitions.py
│   │   [-> dependency-leaf item types only]
│   │   [<- content_ledger.py, builders, loadouts, scenarios]
│   │   cold item IDs/definitions/semantic facts; no builders
│   │
│   ├── authored_item_builders.py
│   │   [-> cold item definitions, item blocks and rule implementations]
│   │   [<- item placement, character/monster/scenario composition]
│   │   direct item construction dispatch; never imported by content_ledger
│   │
│   ├── item_loadouts.py
│   │   [-> cold item IDs/definitions only]
│   │   [<- content_ledger.py, item_placement.py, premades/scenarios]
│   │   cold starting equipment/apparel/holdings plans
│   │
│   └── item_placement.py
│       [-> item builders, inventory/equipment blocks, cold loadouts]
│       [<- characters, monsters, scenario deployment]
│       runtime placement plus exact receipt/rollback
│
├── scenarios/
│   ├── __init__.py                     # docstring only
│   ├── battlefield_definitions.py
│   │   [-> map/world definitions, authored items]
│   │   [<- scenario_deployment.py, content_ledger.py]
│   ├── encounter_definitions.py
│   │   [-> creature/item definitions, encounter types]
│   │   [<- scenario_deployment.py, content_ledger.py]
│   └── scenario_deployment.py
│       [-> Game, map builder, entity composition, Encounter]
│       deploys authored definitions; never resets global runtime itself
│
├── spatial_effect_materialization.py   # existing; temporary until direct port
├── spatial_effect_recipes.py           # existing authored data
└── spike_trap_materialization.py       # existing authored data/runtime bridge
```

This layout is a target, not permission to move everything at once. In particular, action/condition/spell authored identities and their minimal behavior-binding substrate remain where they are until their separate migration. Game never imports any of these content modules: Pygame/application code selects/composes content and then passes committed entities/scenarios into Game.

## 18. Target dependency direction

Here `A -> B` means **A imports/depends on B**:

```text
entities -> types + core + blocks

entity creation/progression/transform machinery -> entities + types + core + blocks

stable rules implementations -> entities + types + core + blocks

cold content definitions -> dependency-leaf types/cold schemas only

content builders/grants/resolvers -> cold definitions + entity-owned verbs + stable rule implementations

scenario deployment -> Game + Encounter + content builders/definitions + map builder

Pygame/application command layer -> content selection/composition + Game

Game -> Encounter + entities + core
```

Important nuance: authored content imports stable rules implementations. Rules foundations must not import authored content to discover what exists. Game does not import authored content; scenario/application code is the caller of both.

Forbidden edges:

- `entities -> content`;
- `blocks/core -> content runtime/registry`;
- `content -> server/database/SDK/frontend renderer`;
- `content_ledger -> construction runtime`;
- `item/entity state -> client asset index`;
- `frontend binding -> required gameplay construction path`.

## 19. Migration phases

### Phase 0 — freeze evidence and establish capability gates

Before deleting another content file:

- checksum the eight JSON/TXT files in the seven source/ledger/catalog artifact families listed above, plus the Python crosswalk sources;
- record all old IDs referenced by visual and icon bindings;
- export every Python-authored appearance/wardrobe/traversal/presentation crosswalk with source file/line and exact value before moving wrappers;
- freeze the 127-ID active item baseline in Section 13.4 with source location and per-ID retain/delete/defer disposition;
- inventory retained tests by capability;
- add architecture checks for forbidden imports and old content-system paths;
- capture output/mechanics for all four premades, nine species, four variants, two backgrounds, three authored progression lines, Paladin Divine Smite behavior, Aegis Spark spell/effect behavior, 27 SRD creatures, hand-built monsters, all 127 active item IDs, possessions, and scenario assembly.

This phase does not restore the old system. It makes loss visible.

Frozen deferred-behavior rule for Phases 1-12:

- standard actions, condition identity/effects, reaction spells, spell metadata, action events, origin traits, and spellcasting state still import the existing `core/content` behavior substrate;
- retain its **complete current transitive module closure**, not merely three headline modules: `canonical.py`, `dependencies.py`, `descriptors.py`, `durable_characters.py`, `effects.py`, `icon_bindings_generated.py`, `identities.py`, `item_definitions.py`, `materialization.py`, `origin_features.py`, `origin_support.py`, `provenance.py`, `recipes.py`, `registration.py`, and `spatial_effect_definitions.py`;
- this closure is a frozen legacy dependency, not a design endorsement: add no new consumer, declaration kind, recipe, renderer binding, or compatibility facade;
- migrate static character/monster/item/scenario consumers away from it, but do not delete or partially hollow a module while a deferred consumer still imports a symbol or one of its transitive imports;
- Phase 6A severs live action/handler admission from the installed global content gateway and migrates engine-facing behavior identity to direct semantic IDs. It does not authorize deletion of modules that untouched authored decorators or spell/condition/spatial consumers still import.
- only the later Phase 13 action/condition/spell authored-content migration may delete the remaining transitive closure atomically.

Phase 0 records exact imported symbols per remaining consumer. A fresh-import check over those consumers becomes the deletion gate. This prevents the false plan of “keeping registration” while deleting `canonical`, `dependencies`, `descriptors`, `effects`, `item_definitions`, `provenance`, or `spatial_effect_definitions`, all of which `registration.py` imports now.

Separately freeze these seven deprecated authored migration inputs through Phase 12: `action_definitions.py`, `behavior_bindings.py`, `condition_definitions.py`, `condition_effect_population.py`, `reaction_definitions.py`, `spatial_effect_transitions.py`, and `spell_catalog_composition.py`. They are not part of the 15-module active import closure, but Section 21 shows that they contain action/condition/reaction/spatial/spell behavior definitions that Phase 13 must classify and port. Phase 12 may delete deprecated construction/materialization files already mined; it may not delete these seven merely because no active import points to them.

### Phase 1 — add domain-native identity to Entity

Coordinate with the entity plan:

- add serializable concrete entity kind;
- add species/variant/background identity;
- add dependency-leaf `AppliedOriginState` carrying exactly base ability allocation, flexible ability bonuses, and immutable origin choices; keep species/variant/background and semantic body/appearance as separate Entity data;
- add ordered class-level state;
- define source IDs sufficient for exact receipt ownership;
- stop adding new ContentRef fields;
- preserve broad existing `CreatureType` separately.

Do not remove old refs until every creation path and event consumer has migrated. Do not keep both indefinitely; this is a staged hard cut with an explicit deletion phase.

### Phase 2 — extract neutral entity transforms and receipts

Port and rename the useful parts of:

- character grant receipt types;
- grant installation transaction;
- reverse cleanup;
- composition receipt.

Replace character/content-specific identifiers with simple source/step IDs. Keep exact handle coverage. Add no generic registry.

Do not claim the existing whole-build receipts are already level-granular. Introduce separate persisted semantic step ownership and live ephemeral UUID handles. Phase 6 must convert aggregate proficiency/spell/slot installation into ledger reconciliation or ordered remove/reapply before incremental unlevelling is accepted.

Prove apply/undo for each handle family independently before moving class definitions.

### Phase 3 — establish semantic item facts and port behavior-free construction

The 127-ID list is a preservation ledger, not one monolithic prerequisite for entity birth. Requiring every spell item, consumable, interactive environment object, and hook-bearing weapon before character composition would deadlock this migration on the deferred behavior system.

First establish one renderer-independent item-instance fact used by both ordinary item/equipment events and `EntityCreatedEvent`. It carries actual item game state: stable semantic item ID, runtime item UUID, name/description, form/material/color/elemental semantics where authored, mechanical family fields, quantity/stack, charges, durability, consumable state, inventory/equipment location, and exact equipment slot. It carries no `ContentRef`, icon, sprite, visual variant, renderer layer, VFX profile, or frontend presentation DTO. This is event/game state, not another universal content object.

Then migrate items by coherent capability family:

- create a stable domain ID and cold definition;
- keep the complete rules fields and a direct builder;
- eliminate generic `ContentRecipe` invocation for that migrated family;
- define cold starting-equipment/apparel/possession plans separately from builder dispatch;
- preserve quantity, stack, charges, durability, exact slots, and instance state;
- expose pure placement validation/mechanical attachment primitives that entity composition can call without gameplay events;
- delete the corresponding old declaration/recipe family in the same cut; add no compatibility constant or recipe facade.

Behavior-free mundane weapons, armor, apparel, shields, gear, and pure environment blockers may migrate now. Spell items, consumables, Field Kit, interactive environment objects, and hook-bearing equipment remain explicitly blocked when moving them would omit their real action/condition/spell/handler capability. Phase 6A unblocks behavior admission; Phase 13 owns the broader action/condition/spell authored-content cleanup.

Current checkpoint: the five fixed Acolyte gear identities are migrated into cold definitions, direct builders, and one ordered loadout. Their exact icon bindings remain preserved in `deprecated/content_data_deprecated/ledgers/content_icon_bindings.json`. `gear.field_kit` is intentionally not weakened into an actionless item.

This phase does not perform the final backend visual-field deletion. It freezes/copies the relevant binding rows and leaves them until Phase 11 coverage succeeds.

### Phase 4 — joint entity creation and progression foundation

Land the entity plan's Phase 6 now, before authored character and monster ports:

- introduce `dnd/entities/entity_creation.py::{create_entity, compose_entity}`;
- introduce entity-owned construction-only silent placement/rollback using the Phase 3 item mechanics;
- introduce `dnd/entities/entity_progression.py::{apply_level, remove_last_level, hydrate_progression}`;
- add `dnd/core/events/entity_events.py::{EntityCreatedEvent, EntityLevelAddedEvent, EntityLevelRemovedEvent}`;
- migrate all ten active direct `Entity.create` call sites and delete the classmethod with no facade;
- extract one shared completion-field finalizer inside `events_registry.py` and add the non-reactive `EventQueue.publish_completed_fact` path required to store exactly one finalized completion version after a successful entity transaction;
- migrate every current spatial-publication consumer in the entity plan's Phase-6 ledger: the live scenario assembler must call `Game.deploy_entity` now, temporary builder/materializer wrappers return undeployed committed entities, and spatial test/tool fixtures deploy explicitly;
- preserve undeployed construction, one atomic birth fact, later spatial deployment, and complete failed-build cleanup.

The entity package owns ordering, mutation transactions, ledger invariants, receipt accounting, commit/rollback, and event emission. It does not import authored content. Prove the APIs with trivial deterministic transforms before Fighter, Human, Goblin, or premade definitions exist in their target packages.

Initial levels inside unpublished composition use the same internal progression transaction silently and are included in `EntityCreatedEvent`; they do not leak standalone level events. Post-birth additions/removals publish non-cancelable completed progression facts after mutation; publication failure rolls the exact transaction back.

Each progression event contains entity UUID, previous/new total level, the dependency-leaf applied/removed level row, resulting per-class levels, stable source-step ID, and direct dependency-leaf fields for every actual mechanical/semantic change: ability/modifier constraints; all proficiency families; hit dice; spell sources/provider levels, known/prepared/reaction spells, and slot capacity/current state; affinities; added/removed action, handler, feat, trait, feature, and resource semantic IDs plus resulting resource values/recovery facts; armor formulas; attack multiplicity; immunities; senses; size; origin capabilities; semantic body/appearance; and resulting aggregate proficiency/caster/slot facts. Total-level-dependent origin changes are included. The reducer never imports an authored class/origin catalog or reruns transforms to interpret a level fact.

These rows live directly on `EntityLevelAddedEvent`/`EntityLevelRemovedEvent`; there is no generic progression envelope. They carry no ContentRef, live transform, receipt UUID, or content definition object. If a class level cannot yet encode an action/condition/spell change because its identity work is deferred, that level's migration is blocked rather than emitting an incomplete terminal fact. A future rule that blocks levelling would require a separately designed command/reaction event rather than pretending these post-commit facts are cancelable.

Current checkpoint:

- `create_entity`, `compose_entity`, reversible transforms, ordered progression, save-only hydration, silent initial placement, and post-commit completed-fact publication exist;
- `Entity.create` is deleted and all ten production aggregate-construction call sites use `create_entity`;
- birth/level publication failure restores the exact previous entity state and emits no fact;
- `EntityCreatedEvent` now carries direct abilities, health, movement, senses, origin identity/state, semantic body/appearance, features, actions, resources, spell slots, renderer-independent item instances, inventory, and equipment;
- level events no longer expose transform implementation IDs; they carry direct terminal abilities, proficiencies, health, movement, senses, origin capabilities, semantic body/appearance, features, actions/handlers/conditions, attack multiplicity, resources/recovery, spell sources/known/reaction/prepared IDs, slots, armor formulas, item state, inventory, and equipment. Explicit previous-versus-result delta fields remain open where a reducer requires both sides;
- every migrated character, premade, hand-authored monster, Circus Fighter, and SRD creature commits through this path; the live scenario assembler remains the last spatial construction caller that has not migrated to explicit `Game.deploy_entity`;
- `dnd/entities/entity_creation.py` still accepts the excluded legacy `ContentRef` argument for remaining unmigrated callers, so final static ContentRef removal remains a Phase-12 gate rather than being hidden.

Therefore the Phase-4 transaction kernel and migrated entity domains are operational, but repository closure still depends on Phase 9 scenario deployment, remaining item consumers, the explicit delta audit, and removal of the legacy ContentRef entry parameter. No old materializer is allowed to regain authority as a bridge.

### Phase 5 — port origin definitions and grants

Move nine species, four variants, two backgrounds, their choices, and their grant appliers into `dnd/content/characters/origin_content.py`.

Reuse rule implementations in `dnd/origins`. Remove declaration/provenance/runtime-support wrappers that exist only for the old registry. Keep semantic descriptions and actual rules support gaps where honest.

Acceptance:

- every origin definition builds with direct IDs;
- every origin receipt removes cleanly;
- level-gated origin spells can update as total level changes;
- exact choice validation remains;
- base ability allocation, flexible bonuses, immutable origin choices, and semantic origin selections serialize and can be resolved after process load;
- origin identity serializes and appears in the entity-created/progression event facts.

Current checkpoint: cold definitions cover all nine species, four variants, and two backgrounds, including ordered choice vocabularies. Direct transforms implement all 18 authored origin feature IDs. This includes Dragonborn ancestry resistance and Breath Weapon, Dwarf combat training and poison resilience, Elf Fey Ancestry, Gnome Cunning, Half-Orc Savage Attacks and Relentless Endurance, Halfling Brave and Lucky, High Elf weapon training and selected wizard cantrip, Rock Gnome tool proficiency, Tiefling fire resistance and level-gated Infernal Legacy, and the complete five-item Acolyte holding plan. Hill Dwarf Dwarven Toughness, Dragonborn breath scaling, and the High Elf cantrip caster level reconcile on initial composition, post-birth levelling, and unlevelling without making Entity know authored content. Origin feature IDs are source-owned semantic Entity state and enter `EntityCreatedEvent`. The obsolete `dnd/core/content/dragonborn.py` declaration model and its registry tests were replaced by cold direct ancestry definitions plus runtime/event regressions; no compatibility export remains.

All origin capabilities passed through the Phase-6A direct behavior boundary. The later Phase 13 still owns removal of generic decorators and spell/condition presentation metadata; it does not own another origin materializer.

### Phase 6 — unblock behavior admission, then port class-level content

#### Phase 6A — narrow semantic behavior-admission hard cut

The live tree disproves the earlier assumption that action identity can remain wholly deferred until after classes. Fighter, Barbarian, and Sorcerer all reach an action, handler, or spell at level 1. `Entity.register_action` and `BaseBlock.add_event_handler` currently call the global runtime behavior-binding gateway, which raises when the deleted content system is not installed.

Perform one narrow atomic cut before class migration:

- replace engine-facing `BehaviorBinding`/`ContentRef` admission authority on `BaseAction`, `BaseCondition`, `EventHandler`, discovery rows, and their events with direct stable semantic behavior IDs and renderer-independent provider/source IDs where actual ownership requires them;
- remove the installed/scoped global behavior-binding gateway from live action and handler admission;
- make `Entity.register_action` and `BaseBlock.add_event_handler` validate and store the direct identity without consulting a content registry;
- preserve existing action classes, condition mechanics, handler execution, EventQueue dispatch, reactions, spells, and source-owned cleanup;
- leave Controller, Encounter action selection/dispatch, action economy, target discovery, and condition semantics unchanged;
- do not introduce a Python-path identity fallback, optional compatibility binding, late import, or second action type system.

Legacy authored decorators and their transitive `core/content` imports may remain frozen until Phase 13, but after Phase 6A they are no longer runtime admission authority. This cut unblocks standard actions, class features, origin handlers, hook-bearing items, and monsters without pretending the full action/condition/spell migration is complete.

Current checkpoint: the live engine admission boundary now uses direct validated `behavior_id`, `provided_by_id`, and `origin_root_id` values on actions, conditions, and handlers. `Entity.register_action` and `BaseBlock.add_event_handler` no longer consult the installed content-system gateway. Discovery and action/handler event contracts carry the same direct identities. The frozen decorators still exist only as deferred authored metadata and are not admission authority.

#### Phase 6B — direct class definitions and resolved level content

Move the valuable schemas from `durable_characters.py` into focused character definitions. Port active Fighter/Champion, Barbarian/Berserker, and Sorcerer/Draconic Bloodline definitions together with their deprecated appliers.

Do not port a class definition without its executable grant plan and inverse receipt behavior. `dnd/content/characters/class_level_content.py` validates a specific class/subclass/choice selection and resolves it into an `AppliedClassLevel` plus concrete entity transforms. Its resolution also receives persisted `AppliedOriginState` and includes total-level-dependent origin reconciliation transforms. It calls the entity-owned progression methods; it does not own another apply/remove/hydrate implementation.

Acceptance:

- levels 1-5 at minimum reproduce current premades and tests;
- all currently authored levels remain represented, not merely those used by premades;
- first-class versus multiclass proficiencies are correct;
- multiclass caster level and spell slots use `dnd/core/progression.py`;
- spell entitlements and sources are exactly owned;
- Extra Attack, resources, ASIs/feats, subclass and metamagic choices rollback correctly;
- aggregate proficiency bonus, multiclass slots, spell-provider levels, and level-gated origin grants reconcile correctly after adding/removing a level or hydrating an unpublished saved build;
- runtime receipt UUIDs are regenerated after load from persisted semantic step IDs;
- a monster can take a valid class level.

Current checkpoint: cold direct-ID definitions now contain all 20 levels of Fighter/Champion, Barbarian/Berserker, and Sorcerer/Draconic Bloodline. `class_level_content.py` validates ordered choices and resolves them to entity-owned reversible transforms. Direct mechanics include first-class/multiclass proficiency packages, hit dice, proficiency bonus, death saves, ASIs/Lucky, Fighting Styles, Fighter and Champion features, Barbarian and Berserker features, Extra Attack, Sorcerer spell sources/slots/learning/replacement, Sorcery Points/conversion actions, Metamagic, and Draconic Bloodline features. Focused tests prove Fighter 1-5, Barbarian/Berserker Rage-to-Frenzy rollback, Sorcerer spell-source/slot/replacement rollback, direct terminal level facts, all three authored 1-20 paths in process, an ordinary post-birth Fighter level added to and removed from a committed Goblin, and Hill Dwarf per-character-level toughness reconciliation. Remaining Phase-6 blockers are explicit previous-versus-result deltas where consumers require them and non-empty authored prepared-spell/feature-toggle examples; total-level-dependent origin reconciliation and the monster-plus-class proof are closed.

### Phase 7 — rebuild authored character composition and all premades

Port the useful authored resolution sequence from deprecated `character_materialization.py` without generic construction-runtime/registry/revision dependencies. Phase 6A has already removed the global behavior gateway from live admission; untouched authored decorators and their transitive legacy imports remain frozen through Phase 12:

1. validate build;
2. resolve the neutral-body configuration;
3. resolve semantic appearance/body selections into their separate Entity semantic state and transforms;
4. resolve origin and ordered class levels into transforms without mutating an Entity;
5. resolve direct item builders;
6. prepare item instance-state restoration values;
7. prepare silent inventory placement rows;
8. prepare exact equipment-slot rows;
9. pass the complete ordered transforms and silent starting-item plan once to entity-owned `compose_entity`, which creates, applies, commits, or rolls back the whole birth.

Steps 2-8 are planning/resolution only. They must not mutate a live Entity before step 9; otherwise the composition would double-apply grants and defeat atomic rollback.

Rebuild all four premades. Expose the currently unwrapped Spellblade.

Acceptance compares mechanics and authored selections, not old contract digests. It includes prepared-spell loadout validation, feature-toggle selection preservation, all holding instance state, and event-atomic rollback with no orphan construction events.

Current checkpoint: all four premades are now cold direct definitions and execute through `create_character`/`compose_entity`; the Fighter 2/Sorcerer 3 Spellblade is publicly constructible. Their exact five-level ledgers, human origin selections, semantic body/build/stature/head/palette/beard facts, class starting packages, curated holdings, quantities, and equipment slots are preserved. Direct mundane weapon/armor/apparel builders, healing/Haste potion builders, portable torch construction, and the Spellblade Crown's reversible +3 Charisma mechanic cover the premade surface without DB/server/content-runtime lookup. Character birth now installs the same standard movement/weapon action surface as monsters after silent equipment placement and before origin/class behaviors. One `EntityCreatedEvent` contains the complete committed premade state. Prepared-spell and feature-toggle selections remain empty in the current four source premades but now have explicit entity/event state rather than being silently discarded. The plain `create_character` API supports non-premade authored values; a higher-level interactive authoring interface remains future client/application work, not a second materializer.

### Phase 8 — converge monster creation

Port hand-built bestiary, Circus Fighter, SRD roster, and configured SRD variants into direct monster definitions using one entity creation/composition path.

Delete wrapper declarations and generic creature materializer calls in the same cut. Preserve intrinsic-vs-possession separation. Add class-level composition proof on at least one monster.

Current checkpoint: complete for the currently authored monster surface. The eight hand-built bestiary roots, Circus Fighter, all 27 SRD roots, and all 21 configured-SRD wardrobe compositions now resolve from cold renderer-independent definitions through `create_monster` and the universal `create_entity`/`compose_entity` transaction. Direct item definitions preserve the exact SRD weapon/armor profiles and keep wolf, dire-wolf, zombie, and ghoul body-owned equipment separate from optional possessions. Standard actions install only after silent equipment placement; direct spell IDs, reaction IDs, traits, multiattacks, senses, immunities, affinities, semantic body state, and one terminal `EntityCreatedEvent` are present at birth. A goblin can take and remove an ordinary Fighter level after creation. The obsolete bestiary, Circus, SRD roster, configured-SRD, possession-recipe, and multiattack-declaration wrappers have been deleted with no compatibility facade. The 16-test SRD trait suite now uses direct creation plus `Game.deploy_entity` and retains its gameplay assertions unchanged. Scenario callers and remaining obsolete factory-contract tests are intentionally handled in Phase 9/test disposition rather than restored through aliases.

### Phase 9 — migrate authored battlefields, encounters, and deployment

Move authored scenario schemas/data into `dnd/content/scenarios`. Replace creature/item recipes with direct domain IDs/build plans. Deploy into the one-process Game without global reset inside the assembler.

This phase is joint with entity-plan Phase 7, which owns introduction and finalization of `WorldInitializedEvent` before migrated scenario deployment. Battlefield construction must finish by emitting that renderer-agnostic terminal fact containing the base map/tile state required by the subjective reducer, before any entity spatial-deployment facts. Current rectangle/map bootstrap suppresses tile events; do not leave authored battlefield data as a second hidden replay truth.

Preserve current authored catalog volume:

- 58 rosters;
- 141 roster members;
- 10 deployments;
- 39 encounters;
- 78 encounter roster slots.

The following live assembler behavior is a normative preservation ledger, not incidental wrapper behavior:

- 43 authored item grants;
- 23 authored spell grants;
- 19 authored behavior grants;
- 10 starting-damage applications;
- 2 affinity grants;
- 2 starting-condition applications;
- two-pass roster construction so cross-member sources/targets resolve after every member exists;
- installation of opportunity-attack handlers and senses;
- fixed-roster opening behavior;
- optional preparation without immediately starting the encounter;
- controller assignment, named-entity lookup maps, and notable-position lookup maps.

Preserve application ordering and compatibility checks that express actual gameplay support. Remove diagnostics that only validate content package/install/runtime contracts. The entity/encounter plan's scenario capability table is also normative for this phase; a row may not disappear merely because its old schema or server-shaped test is deleted.

Current checkpoint: complete for the authored scenario surface. `dnd/content/scenarios` now owns cold direct-ID roster, deployment, encounter, and battlefield values plus runtime builders and deployment. The mechanically migrated schema preserves exactly 58 rosters, 141 members, 10 reusable deployments, 39 encounters, 78 encounter roster slots, 43 item grants, 23 spell grants covering 51 spell IDs, 19 behavior grants, 10 starting-damage applications, 2 affinity grants, and 2 starting-condition applications. All 39 encounters prepare through an explicit caller-owned `Game`; no scenario path resets process state, resolves a recipe, consults a package registry, or imports the server. The two-pass source/target setup, opportunity handlers, senses, fixed opening, prepared-without-start lifecycle, controllers, member maps, and notable positions are retained.

Each battlefield publishes one completed `WorldInitializedEvent` carrying all tile mechanics, initial floor-object state (including container contents), and connector mechanics before any `EntityCreatedEvent` or entity-deployment lineage. Static compatibility and built-map compatibility remain direct gameplay checks. The obsolete `dnd/scenarios` package, old schema-2 catalog JSON, generic encounter recipes/materializer, and old `dnd/core/content` battlefield/encounter contracts have been deleted with no compatibility facade. Valuable catalog, lifecycle, roster-duel, battlefield, spell-matrix, elevation, and mechanics tests now target the direct path; the obsolete digest-authentication and server projection assertions were removed rather than recreated.

### Phase 10 — establish the small read-only content ledger

After domain maps exist, build a simple aggregate listing. It may be consumed by Pygame selection and a future API adapter. It must remain optional for direct construction.

Architecture test: construct every definition through its domain API while the aggregate ledger module is never imported.

Inverse architecture test: importing `content_ledger.py` in a fresh process must not import Entity, blocks, actions, conditions, spells, builder modules, or Game. It exposes only cold rows.

Current checkpoint: complete for migrated content. `dnd/content/content_ledger.py` exposes 324 cold rows: 9 species, 4 species variants, 2 backgrounds, 3 classes, 3 subclasses, 4 premades, 36 monsters, 146 directly constructible items, 10 battlefields, 58 rosters, 10 deployments, and 39 encounters. It is keyed by `(ContentLedgerKind, content_id)` because three authored premade IDs intentionally also identify one-member scenario rosters; the ledger does not pretend those distinct domains have globally unique strings. A fresh-process architecture test proves that importing the ledger loads none of `dnd.entities`, `dnd.blocks`, `dnd.actions`, `dnd.conditions`, `dnd.spells`, or `dnd.game`, and source guards prove direct builders do not import the optional ledger.

The item count is deliberately honest: 146 direct identities exist today, including 20 newly semantic wardrobe/loadout variants. Against the frozen original 127-ID baseline, 126 are now directly constructible. The direct cut preserves both weapon coats, Arcane Device, Arcane Machine Gun, Campfire, Door, Heroes' Feast object, Field Kit, Fire Bolt and Mage Armor scrolls, Assassin's Dagger, and Double-Bladed Sword with explicit semantic behavior ownership and focused construction tests. The sole remaining baseline identity is `environment.blocker.oil_barrel`: its defining capability is a destruction-triggered spatial transition still coupled to the deferred spatial-effect materializer and `ContentRef`-bearing spatial events. It remains an explicit Phase-13 blocker rather than a fake inert barrel.

### Phase 11 — move static entity/item/map bindings and remove their backend presentation ownership

Use the frozen JSON and Python-crosswalk process in section 15. After one-to-one coverage succeeds for the static entity/item/map domains:

- remove static entity/item/map consumers of generated backend icon bindings; retain the frozen generated table itself only until its deferred `descriptors.py` importer migrates in Phase 13;
- remove static-domain asset/presentation mapping modules that have no deferred importer; frozen descriptor/icon/spatial/action bindings remain ledgered until Phase 13;
- replace item/entity appearance state with semantic state;
- update item/equipment/entity events to carry actual semantic state changes, not a duplicate frontend presentation DTO;
- leave animation/action presentation for the later dedicated design.

Do not claim all backend renderer names are gone in this phase. Deferred actions, conditions, class/spell feature definitions, spell metadata, and the frozen descriptor/icon closure still contain icon/visual IDs. Spatial-effect VFX names are exported and preserved here but their ownership migration is deferred with the later spatial/action presentation cut. The hard cut here is static characters/monsters/items/maps only, excluding deferred spatial VFX realization.

Current checkpoint: the duplicate item presentation event contract is deleted. `BaseAction` and `ActionEvent` now carry `source_item_state: ItemState`, captured from the item at declaration time; drink, scroll, and weapon actions therefore retain complete renderer-independent mechanics after the live item changes or disappears. `ItemPresentationState`, `ItemContentRefSnapshot`, `ItemPresentationProvider`, `ItemPresentationKind`, `EquippedVisualPolicy`, and every `to_item_presentation_state` method are removed without aliases. Focused tests prove immutable declaration-time item facts and reject missing or mismatched item state. Static object fields and authored client binding tables still require the separate copy/coverage gate above; this checkpoint does not claim that portion complete.

### Phase 12 — delete only the non-deferred generic construction shell

Only when import search and capability gates prove migration:

- delete universal creature/item/character/scenario registry entries, presets, construction declarations, and generic materializers that are outside the frozen behavior closure;
- delete migrated deprecated character/item/creature materialization and grant files;
- delete bootstrap/system/package/digest machinery outside the frozen behavior closure;
- remove all removed-path `dnd.content_system` imports from migrated static-content gameplay;
- remove ContentRef from Entity, item state, character/monster definitions, loadouts, and scenarios;
- remove stale runtime reset references;
- remove old tests whose asserted capability is the deleted shell itself.

Do **not** delete any module in the exact frozen 15-module transitive closure while untouched authored decorators, condition events, action events, reaction spells, spellcasting, origin traits, or deferred spell/condition/spatial definitions still import it. Phase 6A has already removed runtime admission authority from BaseAction, BaseCondition, BaseBlock handlers, and Entity action registration, but that does not prove the remaining authored import closure is dead. This explicitly retains `dependencies`, `descriptors`, `provenance`, recipes and materialization contexts used by spatial definitions, and the generated icon table where required transitively. Static construction no longer uses the closure, and the remaining imports are frozen authored-content debt.

Also retain the seven deprecated authored migration inputs frozen in Phase 0. The active 15-module runtime closure and those seven source inputs are distinct deletion gates: the former keeps current imports alive, while the latter prevents authored behavior from being lost before Phase 13.

Current checkpoint: `ContentRef` has been removed from `Entity` and from the single `create_entity` signature; direct character, monster, premade, scenario, event, and cold-ledger state therefore cannot carry the old creature ref. `ItemState`, character/monster definitions, loadouts, and scenario values are already direct semantic values. `BaseItem` still retains `ContentRef` only for the oil-barrel/spatial cut and frozen Phase-13 decorators. The obsolete class progression-definition island (`progression_definitions`, Barbarian/Sorcerer variants, helpers, and starting-equipment refs), generic premade contract, generic registry, generic starting-equipment contract, and old Dragonborn declaration module are deleted with no compatibility facade. The old battlefield, encounter, character-deployment, and inventory modules remain deleted. Full Phase-12 completion still waits on the static presentation cut and the oil-barrel spatial dependency.

### Phase 13 — later full action/condition/spell authored-content migration

Phase 6A has already made live behavior admission use direct semantic IDs without a global content gateway. Phase 13 migrates the remaining authored declarations, condition effect definitions, spell catalog composition, specialized identity fields, presentation bindings, and deferred spatial behavior so the frozen transitive closure can actually be deleted.

Do not broaden Phase 6A into this work incidentally while porting characters/items. Record blockers, prevent new dependencies, and handle them here using actual event/action/condition semantics. Include live extension content such as `dnd/extensions/aegis_spark.py` even when it has no current `core/content` import, and preserve `dnd/classes/paladin.py` Divine Smite processing/handler behavior while migrating its reaction identity: these mechanics and tests are authored capabilities, not disposable because they sit outside the main three progression lines. Only this later phase may replace/delete the frozen transitive authored-content closure, migrate its deferred presentation bindings, and collapse `dnd/core/content` completely.

## 20. Active `dnd/core/content` disposition ledger

| Module | Current responsibility | Disposition | Preserved result |
|---|---|---|---|
| `__init__.py` | package boundary | retain through Phase 12; delete with Phase 13 package collapse | none |
| `battlefields.py` | battlefield preview/definition schemas | move/rewrite under authored scenarios | battlefield semantics and preview cells, without generic content refs |
| `canonical.py` | canonical JSON bytes and SHA-256 | remove static construction use, but retain as a transitive registration/descriptor/durable dependency through Phase 12; delete in Phase 13 | retain only in a future save-format module if separately proven necessary |
| `character_deployment.py` | server/DB-shaped character snapshot | delete/replace | in-process character build input and event/save state |
| `dependencies.py` | universal content dependency graph | remove from static construction, retain in the frozen behavior/spell closure through Phase 12, delete in Phase 13 | direct Python imports and explicit composition order after deferred consumers migrate |
| `descriptors.py` | catalog text, ordering, visibility, equipment sprite presentation | migrate static semantic/catalog rows and bindings; retain old module in frozen action/condition/spell closure through Phase 12 | keep semantic name/description/tags; move renderer fields client-side during each domain cut |
| `dragonborn.py` | ancestry and breath geometry definitions | deleted after moving typed enums to `dnd/types/dragonborn.py`, cold rules to `dnd/content/characters/dragonborn_definitions.py`, and the event dependency to the leaf enum | direct ancestry enum/rules and `DragonbornBreathWeaponEvent` facts |
| `durable_characters.py` | item/holding revisions, choices, classes, origins, levels, prepared spells, feature toggles, character revisions, digests | mine and split aggressively; retain exact spellcasting import surface through Phase 12; delete old module in Phase 13 | build choices, applied ordered levels, definitions, prerequisites, holdings and loadout selections; delete revision/digest/ContentRef shell after deferred import migration |
| `effects.py` | authored condition effect branches/gates/outcomes | frozen through Phase 12; migrate/delete with conditions in Phase 13 | condition capability migrated with conditions/actions |
| `encounters.py` | roster, deployment, encounter recipe and compatibility schemas | rewrite under content scenarios | authored roster/setup facts without recipes/content refs |
| `icon_bindings_generated.py` | 2,699-line backend icon binding mirror | copy/validate static bindings in Phase 11; retain old file only because frozen `descriptors.py` imports it, then delete in Phase 13 | client-owned bindings validated against semantic IDs |
| `identities.py` | universal kind/pack/version/hash ContentRef | remove from static entity/item/character/scenario state in Phases 1-12; retain frozen deferred consumers, then delete in Phase 13 | domain enums/simple semantic IDs |
| `inventory.py` | SRD source implementation coverage ledger schema | remove from runtime | keep JSON audit data/tooling only if useful |
| `item_definitions.py` | persistence/stack policy definition | port item-domain rules in Phase 3; retain old transitive registration/spell surface through Phase 12; delete old module in Phase 13 | item-domain policy values |
| `materialization.py` | generic creature/item/spatial build contexts | remove creature/item/static callers, but retain the exact spatial build context imported by deferred active spatial modules through Phase 12; direct-port/delete old module in Phase 13 | typed domain inputs with no requested ContentRef |
| `origin_features.py` | origin capabilities and structural rules | preserve/move; retain old spell consumer surface through Phase 12; delete old module in Phase 13 | entity-owned capabilities and origin definitions |
| `origin_support.py` | migration/runtime support status metadata | retain as transitive `durable_characters.py` dependency through Phase 12, then delete | honest test/ledger support may remain as simple catalog fact if used |
| `premade_characters.py` | creation-plan/draft/server contract models | deleted | four plain premade build definitions |
| `provenance.py` | source/package/review workflow metadata | remove static construction use; retain frozen declaration consumers through Phase 12; delete in Phase 13 | static source attribution/legal data outside gameplay |
| `recipe_presets.py` | named universal recipes plus contract hash | replace | named direct domain build/loadout definitions |
| `recipes.py` | generic factory ID plus JSON parameters/digest | remove static character/item/scenario use; retain transitive spatial/durable dependencies through Phase 12; delete in Phase 13 | typed Python build specs/functions |
| `registration.py` | decorators, declaration, contract hash, construction wrapper | delete static construction/declaration use in Phase 12; retain exact deferred declarations and its complete transitive closure through Phase 12; delete in Phase 13 | explicit cold domain maps and separate direct builders |
| `registry.py` | frozen universal lookup/dependency validation | deleted | per-domain immutable maps only |
| `runtime.py` | global behavior binding/attribution gateway | deleted by Phase 6A after direct behavior admission replaced it | direct semantic behavior/provider IDs on engine objects and events; no installed gateway |
| `saving_throws.py` | content-specific saving-throw context | deleted after the surviving context moved to the dependency-leaf saving-throw types | event/rules context only where actually required |
| `spatial_effect_definitions.py` | authored spatial transition/lifetime definition | retain frozen registration closure and authored spatial behavior through Phase 12; direct-port/delete old dependency in Phase 13 spatial/behavior cut | direct spatial authored definitions |
| `starting_equipment.py` | ordered starting item/slot package | deleted after direct class loadout migration | direct item builders and slots |

## 21. Deprecated content-system disposition ledger

| Module | Valuable content/capability | Disposition |
|---|---|---|
| `__init__.py` | none | delete |
| `acolyte_starting_holdings.py` | acolyte holding data | port into direct character loadout definitions |
| `action_definitions.py` | action behavior identity specs/declarations | defer with actions; do not restore generic declarations |
| `artifact_digest.py` | Python closure/package digesting | delete |
| `background_starting_holdings.py` | background-to-holdings selection | port as direct background loadout function |
| `barbarian_character_grant_appliers.py` | executable Barbarian/Berserker grants | port with receipts, strip runtime/content refs |
| `behavior_bindings.py` | generic behavior binder | delete after action/condition migration |
| `bootstrap.py` | installs universal built-in system | delete |
| `builtin.py` | aggregate built-in declarations | delete after domain ports |
| `builtin_character_builds.py` | four premades, build helpers, holdings/spells/appearance choices | preserve and simplify into plain premade definitions |
| `builtin_character_grant_appliers.py` | dispatch from definition to class/origin appliers | replace with direct typed grant-plan dispatch |
| `builtin_inventory.py` | aggregate built-in item inventory | replace with explicit item maps; delete shell |
| `character_appearance.py` | appearance choices, constraints, migration, apply | preserve semantic choices; delete asset vocabulary/revision migration shell after client binding migration |
| `character_build_validation.py` | deep character validation, grant schedule, preview | preserve capability, drastically split/simplify without LoadedContentSystem |
| `character_content_migrations.py` | ContentRef replacement table | delete after direct-ID migration; use only temporary old->new extraction map |
| `character_grant_applier_runtime.py` | transactional grant installation and helper operations | port to neutral entity receipt transaction |
| `character_grant_context.py` | entity/runtime/grant context wrapper | replace with small direct entity/level context; no runtime singleton |
| `character_grant_receipt_cleanup.py` | exact reverse cleanup | port and generalize to Entity receipts |
| `character_grant_types.py` | exact source-owned receipt handles | port and generalize; remove ContentRef fields |
| `character_materialization.py` | validate/create/compose/items/equip/rollback sequence | preserve sequence via one character/entity composition path; delete materializer shell |
| `character_origin_definitions.py` | 9 species, 4 variants, 2 backgrounds and choices | port authored definitions/grants |
| `condition_definitions.py` | condition behavior identity specs | defer with conditions |
| `condition_effect_population.py` | large condition effect authored population | defer and preserve capability ledger; do not delete blindly |
| `creature_bindings.py` | generic creature runtime factory registry | delete after direct monster definitions/builders |
| `creature_materialization.py` | universal creature recipe resolver | delete after direct builders |
| `creature_possessions.py` | placement modes, dependency list, apply/rollback | preserve as direct possession/loadout receipt operation |
| `dragonborn_character_grant_appliers.py` | dragonborn ancestry mechanics | port under origins/grants |
| `dragonborn_origin_definitions.py` | dragonborn authored feature declarations | merge into direct origin definitions |
| `extra_attack_character_grant_appliers.py` | source-owned Extra Attack grants | port with class grants |
| `fighter_character_grant_appliers.py` | executable Fighter/Champion grants | port with receipts |
| `icon_bindings.py` | icon ledger schemas/validation/loaders | use temporarily to migrate/validate JSON, then remove from backend |
| `item_bindings.py` | generic item runtime binding registry | delete after direct item builders |
| `item_materialization.py` | generic item recipe resolver | delete after direct item builders |
| `origin_character_grant_appliers.py` | structural origin feature installation | port to direct origin grants |
| `origin_feature_definitions.py` | authored origin feature declarations | port mechanics/data, remove wrappers |
| `origin_innate_spellcasting.py` | origin-owned innate spell installation | preserve with source-owned receipt |
| `origin_runtime_character_grant_appliers.py` | executable origin grants | port with origins |
| `reaction_definitions.py` | reaction behavior identity specs | defer with reactions/actions |
| `runtime.py` | process-global installed ContentSystemRuntime | delete |
| `sorcerer_character_grant_appliers.py` | executable Sorcerer/Draconic grants | port with receipts |
| `spatial_effect_materialization.py` | generic spatial resolver | replace with already-active direct spatial path, then delete |
| `spatial_effect_population.py` | built-in spatial dependency population | convert to direct authored imports/maps or delete |
| `spatial_effect_registry_materialization.py` | registry-backed spatial construction | delete after direct path |
| `spatial_effect_transitions.py` | frozen interaction gateway | inspect against current spatial controllers; port only real transition behavior |
| `spell_catalog_composition.py` | spell catalog/binding rows | defer with spell/action content migration |
| `starting_apparel_definitions.py` | authored apparel packages | port into direct item loadouts; visual bindings client-side |
| `starting_equipment_definitions.py` | authored starting equipment packages | port into direct item loadouts |
| `system.py` | LoadedContentSystem container | delete |

## 22. Active authored module ledger

### 22.1 Character rules and definitions

| Active module/family | Disposition |
|---|---|
| `dnd/classes/barbarian.py` | preserve runtime mechanics; authored grant selection moves to content |
| `dnd/classes/fighter.py` | preserve runtime mechanics; authored grant selection moves to content |
| `dnd/classes/paladin.py` | preserve implemented Divine Smite processing and handler creation; migrate its reaction/behavior identity in Phase 13 |
| `dnd/classes/rage.py` | preserve mechanics |
| `dnd/classes/sorcerer.py` | preserve runtime mechanics |
| `dnd/classes/feats.py` | preserve mechanics/choices; remove ContentRef wrappers when migrated |
| `dnd/classes/progression_definitions.py` | deleted after Fighter/Champion data moved to direct class definitions |
| `dnd/classes/barbarian_progression_definitions.py` | deleted after Barbarian/Berserker data moved to direct class definitions |
| `dnd/classes/sorcerer_progression_definitions.py` | deleted after Sorcerer/Draconic data and spell choices moved to direct class definitions |
| `dnd/classes/permanent_feature_definitions.py` | preserve authored feature facts, replace universal definitions |
| `dnd/classes/structural_feature_definitions.py` | preserve authored feature facts, replace universal definitions |
| `dnd/classes/sorcerer_structural_feature_definitions.py` | port valuable features; defer broken action identity dependency |
| `dnd/classes/starting_equipment_refs.py` | deleted after direct loadout IDs replaced refs |
| `dnd/classes/progression_definition_helpers.py` | deleted after all retained resolution moved to direct class content |
| `dnd/classes/content_factories.py` | delete wrappers after one composition path |
| `dnd/origins/dragonborn.py` | preserve runtime rules |
| `dnd/origins/half_orc.py` | preserve runtime rules |
| `dnd/origins/halfling.py` | preserve runtime rules |
| `dnd/player_character_body.py` | move neutral authored body recipe under content characters |
| `dnd/premade_characters.py` | replace declaration factories with four plain build definitions |

### 22.2 Monster content

| Active module | Disposition |
|---|---|
| `dnd/monsters/bestiary.py` | port eight direct monster roots; remove dead item materializer imports |
| `dnd/monsters/bestiary_content.py` | delete declaration wrappers after roots migrate |
| `dnd/monsters/srd_roster.py` | port 27 definitions/build steps and intrinsic/possession distinction |
| `dnd/monsters/configured_srd_creatures.py` | export/preserve all 21 exact maps, classify each field, retain semantic facts and migrate asset bindings, then delete wrapper declarations |
| `dnd/monsters/circus_fighter.py` | port independent warrior root into same monster path |
| `dnd/monsters/multiattack_definitions.py` | preserve mechanics/definitions; later remove content identity shell |
| `dnd/monsters/traits.py` | preserve runtime mechanics |
| `dnd/monsters/skeleton_abilities.py` | preserve runtime mechanics |
| `dnd/monsters/circus_fighter_conditions.py` | preserve behavior; defer condition definition migration |
| `dnd/monsters/bestiary_items.py` | move authored items to content item builders |
| `dnd/monsters/circus_fighter_items.py` | move authored items to content item builders |
| `dnd/monsters/srd_roster_items.py` | move authored items to content item builders |

### 22.3 Item content

| Active module | Disposition |
|---|---|
| `dnd/items/weapons.py` | preserve direct mechanics/builders, replace decorators/refs |
| `dnd/items/armors.py` | preserve direct mechanics/builders, replace decorators/refs |
| `dnd/items/consumables.py` | preserve direct mechanics/builders, replace decorators/refs |
| `dnd/items/spell_items.py` | preserve direct mechanics/builders; defer spell identity cleanup |
| `dnd/items/torches.py` | preserve item/environment mechanics, replace factory wrappers |
| `dnd/items/acolyte_gear.py` | preserve authored gear/builders |
| `dnd/items/environment.py` | preserve gameplay objects; remove renderer metadata later |
| `dnd/items/environment_interactables.py` | preserve interaction mechanics |
| `dnd/items/environment_content.py` | preserve authored objects; defer broken action-definition binding |
| `dnd/items/authored_presentations.py` | migrate binding decisions client-side, then delete backend module |
| `dnd/items/authored_variant_inventory.py` | use to validate/copy manual JSON, then delete backend loader |
| `dnd/items/authored_variant_presets.py` | preserve old->semantic-ID mapping until client migration, then delete backend visual presets |
| `dnd/items/apparel_presets.py` | split mechanical loadout from client visual preset; preserve both on correct sides |
| `dnd/items/visual_variants.py` | delete/replace with semantic item state after client binding migration |
| `dnd/extensions/field_focus.py` | preserve Field Kit item/action mechanics and export its exact bindings; split item construction in Phase 3 and defer action binding cleanup to Phase 13 |

### 22.4 Scenarios, maps, spatial, and spells

| Active module/family | Disposition |
|---|---|
| `dnd/maps/arena_layout.py` | preserve map semantics; replace dead item materializer |
| `dnd/scenarios/battlefield_catalog.py` | move authored definitions under content/scenarios; direct item IDs |
| `dnd/scenarios/encounter_catalog.py` | move authored definitions/data under content/scenarios |
| `dnd/scenarios/authored_catalog.json` | checksum and preserve as the sole authored roster/deployment/encounter payload; migrate IDs without regeneration |
| `dnd/scenarios/encounter_compatibility.py` | preserve real capability checks; remove package/runtime diagnostics |
| `dnd/scenarios/encounter_assembler.py` | rewrite as Game deployment over direct definitions |
| `dnd/content/spatial_effect_materialization.py` | preserve current direct bridge, remove old registry dependency |
| `dnd/content/spatial_effect_recipes.py` | preserve authored spatial data |
| `dnd/content/spike_trap_materialization.py` | preserve trap behavior/direct build path |
| `dnd/extensions/aegis_spark.py` | preserve live `AegisSpark` spell and `AegisSparkEffect` condition mechanics plus retained tests; migrate authored spell/condition identity in Phase 13 even though it does not currently import `core/content` |
| `dnd/spells/catalog_content.py` | preserve spell authored facts; defer generic identity cleanup |
| `dnd/spells/content_metadata.py` | preserve semantic spell metadata, remove renderer/content registry shell |
| `dnd/spells/reaction_spell_content.py` | preserve reaction-spell capability; defer binding cleanup |
| `dnd/spells/conjuration.py` | replace dead item materializer with direct builders |
| other runtime spell-family modules | preserve mechanics |

## 23. Live broken-import ledger

Do not repair these with a facade. Remove each edge through its domain phase.

| Active file | Dead dependency responsibility | Removal phase |
|---|---|---|
| `dnd/classes/content_factories.py` | premades, appearance, character materialization, creature bindings/runtime | character composition/premades |
| `dnd/classes/sorcerer_structural_feature_definitions.py` | action behavior definitions | later action migration |
| `dnd/items/environment_content.py` | action behavior definitions | later action migration |
| `dnd/maps/arena_layout.py` | item binding/materialization/runtime | direct items/maps |
| `dnd/monsters/bestiary.py` | item binding/materialization | monster possessions/items |
| `dnd/monsters/bestiary_content.py` | action definitions/creature possessions | monster migration plus later actions |
| `dnd/monsters/circus_fighter.py` | item binding/materialization | monster possessions/items |
| `dnd/monsters/configured_srd_creatures.py` | creature possessions | monster migration |
| `dnd/monsters/srd_roster.py` | item/action/possession/materialization | monster/items plus later actions |
| `dnd/premade_characters.py` | builtin character builds | premade migration |
| `dnd/runtime_reset.py` | creature/item binding registries | Game lifecycle migration |
| `dnd/scenarios/battlefield_catalog.py` | item binding/materialization | scenarios/items |
| `dnd/scenarios/encounter_assembler.py` | creature/item/spell materialization | scenario deployment after domain ports |
| `dnd/spells/conjuration.py` | item binding/materialization | direct item construction |

## 24. Event and replay blockers created by content

The content cleanup cannot declare success if the event stream loses authored facts.

Current inconsistencies:

- action events carry a `BehaviorBinding` but exclude it from serialization;
- specialized action events sometimes duplicate identity as strings;
- world spatial-effect events embed ContentRef;
- item location events embed `ItemPresentationState`, which carries renderer vocabulary;
- `EntityCreatedEvent` now exists but carries only identity/origin/level rows, not the complete reducer-required initial mechanics, semantic body/appearance, item instances, inventory, or equipment;
- entity level events carry transform IDs rather than the actual direct mechanical/semantic deltas and resulting aggregate facts;
- entity origin identity is now domain-native and serialized, but the general Entity `content_ref` remains because legacy behavior admission still reads it before Phase 6A.

Immediate rule while full actions/conditions migration is deferred:

- add no new ContentRef or renderer fields;
- preserve current behavior while Phase 6A replaces only the global admission/identity dependency;
- define entity/item semantic state on the objects themselves;
- make actual item/entity/equipment events carry the changed semantic/mechanical facts;
- avoid a new “content event” wrapper.

Required eventual creation/progression facts:

- concrete entity kind;
- species/variant/background;
- ordered class-level addition/removal;
- semantic body/appearance state;
- constructed item identity and mechanical instance state;
- inventory/equipment placement;
- monster base and intrinsic trait identity where required for replay.

For post-birth levels, “ordered class-level addition/removal” is not sufficient by itself. The event must directly carry the resulting renderer-agnostic mechanical/semantic deltas and aggregate facts enumerated in Phase 4, including level-gated origin changes. The subjective reducer must not import authored catalogs. Save hydration restores original history and runtime receipts silently; it never emits a second creation or level fact.

## 25. Verification ledger: capabilities to preserve or port

### Character creation/progression

- neutral player-character body;
- point buy and flexible ability bonuses;
- species, variant, background choice validation;
- origin integration matrix;
- Dragonborn ancestry/breath/resistance;
- Half-Orc runtime traits;
- Halfling runtime traits;
- Fighter/Champion progression;
- Barbarian/Berserker progression;
- Sorcerer/Draconic progression;
- first-class and multiclass proficiency behavior;
- multiclass composition and caster progression;
- spell source ownership and known/reaction spell cleanup;
- prepared-spell selections by casting source, entitlement/rank validation, and save/hydration preservation;
- feature-toggle selections and explicit runtime-support status;
- Aegis Spark spell/effect behavior and extension-scene coverage;
- Paladin Divine Smite processing/handler behavior and its retained canonical-presentation test capability;
- ASI/feat/metamagic/subclass choices;
- level application/removal plus unpublished save hydration with no duplicate event facts;
- grant transaction rollback and receipt cleanup;
- all four premades, including Spellblade.

### Items/equipment

- direct construction for every retained item definition;
- stack/charge/durability restoration;
- inventory addition/removal;
- exact equipment slot placement;
- multi-slot conflict validation;
- starting equipment/apparel/background holdings;
- monster intrinsic/inventory/equipped possessions;
- rollback on partial loadout failure;
- item/equipment terminal-event replay.

### Monsters/scenarios

- eight bestiary roots and Circus Fighter;
- all 27 SRD roster mechanics;
- all 21 configured-SRD exact wardrobe mappings preserved until each field is classified and migrated;
- traits, multiattack, intrinsic actions, senses, immunities, affinities;
- monster plus ordinary class-level composition;
- 58 rosters / 141 members;
- 10 deployments;
- 39 encounters / 78 roster slots;
- battlefield construction;
- encounter compatibility and assembly into Game.

### Binding/data preservation

- 77 authored item visual categories;
- 205 authored variants;
- 87 factory/slot bindings;
- one recorded source-ID collision;
- 671 definition icon bindings;
- 205 recipe-preset icon bindings;
- 521 asset-index rows;
- 925 SRD coverage rows;
- character option-token/tint crosswalks and three exact premade appearance selections;
- bestiary appearance constants and seven exact wardrobe keys;
- all 21 configured-SRD wardrobe maps;
- five traversal presentation keys;
- tile sprite bindings, neutral player-body variant, and every premade portrait/icon/variant selection;
- SRD creature icon/variant/tint choices;
- spatial-effect VFX bindings preserved as explicit deferred migration rows;
- Field Kit item/action binding rows;
- every literal item/environment presentation binding exported with source evidence;
- old semantic ID -> new semantic ID mapping with no silent drops.

### Replay/summary

- creation and progression event facts;
- semantic item/entity state in events;
- live callback versus retained in-memory terminal-event reducer parity for migrated static content; full serialized parity follows the separate event codec/coldness work;
- structured combat log generated from actual events;
- game summary retained without server/database storage.

## 26. Tests whose shape is obsolete but whose capability may not be

Delete or rewrite tests of the following obsolete mechanisms:

- universal bootstrap/install order;
- package/artifact digests;
- content-set digest authority;
- registry freeze and generic dependency graph;
- generic extension/package loading;
- generic ContentRecipe JSON invocation;
- contract-hash equality;
- server-owned public catalog routes;
- backend icon/presentation mapper behavior after client migration;
- global item/creature behavior binding registry bookkeeping;
- database character revisions/deployment snapshots.

Before deleting any test importing `dnd.content_system`, classify the asserted capability. If it asserts class features, origin traits, item placement, monster mechanics, encounter assembly, event facts, replay, or summary, port it to direct construction. An obsolete fixture/import is not evidence that the capability is obsolete.

## 27. Hard deletion gates

### Delete generic character materialization only when

- all four premades use the direct path;
- all origin/class appliers and receipts are ported;
- multiclass and rollback tests pass;
- no active or retained-test importer remains.

### Delete generic item materialization only when

- maps, monsters, conjuration, character loadouts, and scenarios use direct builders;
- placement and rollback are covered;
- visual bindings are safely copied/client-validated where relevant.

### Delete the non-behavior universal construction registry only when

- direct construction works without importing aggregate content ledger;
- all live `dnd.content_system` paths are gone;
- Entity/item/character/monster/scenario construction no longer imports generic registry/recipes/materializers;
- the exact behavior-identity substrate required by deferred actions/conditions/spells is separately frozen and enumerated.

### Delete the remaining behavior identity/runtime only when

- Phase 6A has already removed the global gateway from BaseBlock/BaseAction/BaseCondition/Entity admission and replaced excluded `BehaviorBinding` authority with direct semantic IDs;
- Phase 13 has migrated the remaining authored action/condition/spell declarations, condition effects, reaction spells, deferred spatial build contexts, presentation bindings, and every import in the frozen 15-module transitive closure;
- BaseBlock, BaseAction, BaseCondition, core events, Entity action registration, authored decorators, and grant appliers no longer import it;
- no renderer/content/provider compatibility field is retained as an optional facade.

### Delete backend presentation modules only when

- every manual binding artifact is frozen and copied;
- old->new semantic IDs are complete;
- client coverage validation passes;
- mechanical and event schemas no longer require renderer vocabulary.

## 28. Main risks

1. Porting active progression definitions but forgetting deprecated executable appliers.
2. Losing the unexposed multiclass Spellblade premade.
3. Replacing ContentRef with another generic universal ID object instead of domain types.
4. Treating receipts as character-only and preventing classed monsters.
5. Removing item/entity/map presentation fields before copying 205 manual variants, icon bindings, and every Python-authored appearance/wardrobe/traversal crosswalk.
6. Preserving generic materializers as “temporary” facades and never reversing dependency direction.
7. Letting the aggregate content ledger become the new construction registry.
8. Either mixing the full action/condition redesign into the character/item cut or, conversely, trying to port classes before the narrow Phase-6A admission prerequisite.
9. Claiming event-source completeness while entity creation and semantic identity remain silent/excluded.
10. Emitting item/equipment/destroy events for a composition that later rolls back and never commits an EntityCreated fact.
11. Treating whole-build ephemeral receipt UUIDs as already level-granular or save-stable.
12. Testing old factories instead of the preserved gameplay results.
13. Treating all 127 items as one prerequisite and deadlocking static item/entity progress on spell-, action-, or condition-bearing items.
14. Patching the nine provisional monster builders to call `compose_entity` around their current event-producing mutations, thereby publishing incomplete or non-atomic birth facts.

## 29. Completion definitions

### 29.1 Static character/monster/item/map migration and shell deletion (Phases 1-12)

- no active gameplay module imports `dnd.content_system` or `deprecated`;
- ContentRef is absent from entity, item, character, monster, and scenario runtime state;
- every entity is born through one low-level path and composed through ordered receipt-producing operations;
- species/variant/background/concrete creature identity/class levels are serialized game data;
- levelling and unlevelling work for both player and monster entities;
- all four premades are ordinary build definitions and require no DB/server;
- all retained monsters/items/scenarios use direct domain builders;
- the backend content ledger is read-only and optional for construction;
- manual frontend bindings have been preserved and validated client-side;
- static entity/item/map mechanics and events contain semantic state but no asset or renderer names;
- creation/progression/item/equipment facts enter the actual event stream;
- live action/condition/handler admission uses direct semantic IDs and no installed global content gateway, while the remaining authored declaration closure is explicitly frozen for Phase 13;
- failed unpublished composition leaves no permanently indexed item/equipment/destroy event residue;
- prepared-spell and feature-toggle selections/validation are preserved with honest runtime-support status;
- valuable capability tests have been recovered and obsolete shell tests removed;
- universal static construction registry entries, materializers, presets, package/bootstrap, and digest infrastructure outside the frozen deferred closure are deleted rather than hidden behind facades;
- the exact remaining 15-module action/condition/spell/spatial transitive runtime closure, its presentation fields, and the separately ledgered deprecated authored migration inputs are frozen and carried into Phase 13.

### 29.2 Full content-system deletion after the deferred Phase 13

- no entity, block, action, condition, event, spell, or grant module imports `dnd/core/content`;
- the remaining universal identities, behavior registration/runtime gateway, condition-effect content, and content-specific saving-throw substrate are deleted;
- deferred action/condition/spell presentation fields have been migrated through their own semantic/client-binding plan;
- `dnd/core/content` is removed completely;
- no compatibility facade, optional ContentRef field, provider gateway, or dormant registration decorator remains.

## 30. Final source ledger summary

### Preserve directly

- entity/block/item/inventory/equipment mechanics;
- `dnd/core/progression.py` calculations;
- nine species, four variants, two backgrounds;
- Fighter/Champion, Barbarian/Berserker, Sorcerer/Draconic progression;
- reversible grant receipts, transactional install, reverse cleanup;
- four premade builds;
- prepared-spell loadout selections and feature-toggle selections/validation;
- eight bestiary roots, Circus Fighter, 27 SRD creatures;
- direct item families, possessions, holdings, loadouts;
- battlefield/roster/encounter authored data and useful compatibility rules;
- spatial authored recipes/direct materialization already moved under content;
- summary/replay capabilities;
- all eight JSON/TXT files across seven manual/source/catalog artifact families, plus the exported Python-authored visual crosswalk ledger.

### Rewrite without generic shell

- character build validation;
- entity/character/monster composition;
- class/origin grant dispatch;
- starting equipment and apparel;
- creature possessions;
- scenario deployment;
- backend catalog enumeration;
- identity and serialization;
- item/entity visual semantic state;
- creation/progression/item event facts.

### Migrate to frontend then delete from backend

- item visual inventory loader;
- authored presentation mapping;
- visual recipe presets;
- icon binding generated module;
- character option-token/category/tint crosswalks and premade appearance selections;
- bestiary and configured-SRD wardrobe maps;
- battlefield traversal presentation keys;
- renderer slot/layer/policy/presentation state;
- asset index and actual resource names.

### Delete

- ContentRef contract-hash/version/package identity;
- universal content dependencies and frozen registry;
- global content runtime and behavior provider gateway after deferred consumers migrate;
- generic recipes, recipe presets, declarations, decorators, and materializers;
- bootstrap/installed-system/singleton infrastructure;
- artifact/content-set digest authority;
- runtime provenance/review/packaging graph;
- server/DB character deployment and revision contracts;
- compatibility facades and old import paths.

### Defer deliberately

- full action behavior identity cleanup;
- full condition definition/effect cleanup;
- spell catalog identity cleanup;
- Aegis Spark spell/condition authored identity cleanup while preserving its mechanics/tests;
- the seven frozen deprecated action/condition/reaction/spatial/spell authored migration inputs;
- saving-throw context reassessment;
- animation/action presentation semantics;
- BaseBlock cold publication;
- multi-game/multi-process runtime isolation;
- future server/API/SDK adapters.

## 31. Review record

Three read-only adversarial passes validated this ledger against live active and deprecated source; no reviewer edited the document.

The specialized content-ledger review required and verified:

- exact preservation of all four premades, nine species, four variants, two backgrounds, the three progression lines, Paladin Divine Smite, and Aegis Spark;
- an explicit 127-ID active item baseline rather than fixture-reachability guesses;
- the complete Python-only frontend crosswalk inventory, including origin variants, all four premade selections, `gap.png`, tile/player/SRD/spatial/Field Kit bindings;
- separate deletion gates for the 15-module active runtime closure and seven deprecated authored behavior migration inputs;
- the complete scenario counts, setup-effect counts, and two-pass/runtime assembly behaviors;
- cold definition maps remain transitive dependency leaves and never contain/import builder dispatch.

The two independent entity/encounter reviewers also validated the cross-document phase order, dependency arrows, entity/content ownership, event atomicity, reducer-complete progression facts, spatial deployment cut, and save hydration semantics.

Final verdicts: **specialized content review — APPROVED; cross-document Reviewer A — APPROVED; cross-document Reviewer B — APPROVED**.

Post-implementation re-evaluation after the entity foundation and first direct-item hard cut changed the executable order without weakening the preservation ledger:

- the 127 item IDs remain mandatory preservation rows, but behavior-bearing items are no longer a monolithic prerequisite for entity birth;
- semantic item-instance facts and reducer-complete `EntityCreatedEvent` state now precede starting-loadout integration;
- Phase 4 is recorded as a working transaction kernel, not a completed repository migration;
- origin definitions are complete as cold authored rows; executable support has advanced to 15 of 18 feature IDs, with the exact three behavior-heavy blockers named above;
- the narrow Phase-6A behavior-admission cut now precedes class content because all three supported class lines reach actions/handlers/spells at level 1;
- the full action/condition/spell authored-content and presentation migration remains Phase 13;
- Controller and Encounter dispatch remain outside this content correction.
