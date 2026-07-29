# Unified Creature Pipeline and SRD 5.1 CR 0–5 Program

**Date:** 2026-07-28  
**Status:** Audited; immediate Goblin Caster visual-identity regression fixed;
pipeline hard cut and SRD expansion pending.

## 1. Why this plan exists

The content registry and canonical `materialize_creature(ContentRecipe, ...)`
path are real and useful, but the creature cut is incomplete:

- creature factories still build their default equipment ad hoc;
- evaluation scenarios add apparel after creature construction;
- the evaluation assembler still branches between player-class, bestiary, and
  SRD actor blueprint families;
- SRD creature declarations do not authenticate the items their factories
  equip;
- client preview catalogs describe blueprints but cannot provide production
  `APIEntitySummary` and `EntityVisualLoadout` rows;
- player-character composition can add and remove ordered class grants, but it
  also owns player-origin ability scores and therefore cannot be applied
  unchanged to an existing monster stat block.

The goal is not another generalized framework. The goal is to finish the
existing content architecture with one creature construction path and the
smallest reusable seams needed by real content.

## 2. Measured current state

### 2.1 Hero premades

All four current hero premades are complete through raw materialization,
objective projection, subjective safe visual loadout, and the current
NeuroClient renderer:

1. Berserker
2. Fighter
3. Sorcerer
4. Fighter 2 / Sorcerer 3 Spellblade

Their authored appearance, body equipment, footwear, head equipment, weapons,
and exact runtime item bindings are already covered by maintained regressions.
They are not part of the immediate fix.

### 2.2 Layered creature visual ownership

There are 25 active layered-humanoid creature roots:

- Goblin Caster now owns its Hedge Wizard robe and Dark Cloth shoes.
- Twenty-four roots still rely on scenario wrappers for footwear.
- Six of those twenty-four also rely on scenario wrappers for body clothing:
  Generic Caster, Commoner, Kobold, Acolyte, Spy, and Mage.
- All twenty-one layered SRD humanoid declarations currently omit item
  dependencies even though their factories equip mechanical weapons and armor.
- `head_category=None` currently conflates an intentional creature-specific
  presentation with unfinished population. A content audit must classify that
  explicitly; the backend must not assign arbitrary human hair to goblins,
  kobolds, gnolls, or other creature identities.

The immediate Goblin Caster closure is measured below the scenario layer:
raw `materialize_creature()` must equip the exact full robe and shoe recipes.
The Goblin Water Cell additionally proves the real composed scenario preserves
that wardrobe.

### 2.3 SRD 5.1 CR 0–5 scope

The pinned official SRD 5.1 CC PDF and the checked-in 317-row creature/NPC
coverage ledger have a bijective name/order match. Every stat block has exactly
one parseable Challenge row.

| CR | Canonical today | Official total |
|---|---:|---:|
| 0 | 1 | 29 |
| 1/8 | 5 | 18 |
| 1/4 | 5 | 32 |
| 1/2 | 5 | 29 |
| 1 | 4 | 25 |
| 2 | 6 | 41 |
| 3 | 2 | 20 |
| 4 | 0 | 11 |
| 5 | 0 | 25 |
| **Total** | **28** | **230** |

The current Mage root is CR 6 and is outside this bounded program.

The 202 missing roots include 81 beasts, 6 beast swarms, 25 monstrosities,
16 humanoids, 13 elementals, 11 dragons, 11 undead, and 10 fiends. Measured
overlapping mechanics include:

- 51 Multiattack blocks;
- 78 save-driven effects;
- 26 recharge actions;
- 18 breath weapons;
- 12 shape/form swaps;
- 9 spellcasters;
- 5 reaction sections;
- one Legendary Actions section.

The nine missing spellcasters require 44 unique spells. Fifteen are already
playable and twenty-nine are missing.

## 3. Non-negotiable boundaries

1. One canonical `ContentRecipe -> materialize_creature` entry point.
2. No display-name, Python-path, race-name, or renderer fallback identity.
3. A creature root owns its structural stats, traits, intrinsic body mechanics,
   default possessions, equipped wardrobe, and exact creature `ContentRef`.
4. A scenario owns deployment, faction, controller, starting damage/conditions,
   and explicitly scenario-specific augmentations. It does not repair an
   incomplete creature definition.
5. Exact appearance recipes remain full `ContentRecipe` values. A base item
   `ContentRef` is insufficient because authored apparel variants share item
   definitions.
6. NeuroClient owns how an exact creature identity maps to current/future art.
   The backend must not encode Pixi-specific aspect ratios or creature-name
   rendering exceptions.
7. Additive character levels preserve the base creature stat block. They do
   not reapply player-origin base scores or flexible `+2/+1` bonuses.
8. No late imports, `TYPE_CHECKING` dependency escapes, parallel registries,
   compatibility aliases, or function-local dynamic dispatch.
9. Every known defect or incomplete admitted behavior has a deterministic
   measuring test before it is classified open or closed.

## 4. Smallest canonical possession model

Introduce one immutable content-side possession definition, not a new global
modifier registry:

```text
CreaturePossessionGrant
├── recipe: ContentRecipe
├── disposition: intrinsic | equipped | inventory
├── equipped_slot: EquipmentSlot | null
├── quantity: positive integer
└── runtime_origin: intrinsic | starter
```

Keep the dependency-neutral facts in a low content leaf. The runtime applicator
lives above Entity/items and performs:

1. exact installed recipe validation;
2. materialization with an `ItemRuntimeBinding`;
3. inventory/equipment placement;
4. slot-conflict validation;
5. rollback on any failed grant.

The same tuple is the single source for:

- declaration `EQUIPS_ITEM` and `CREATES_ITEM` dependencies;
- runtime construction;
- catalog closure;
- raw materialization regressions;
- preview projection.

Do not maintain separate declaration, factory, and scenario wardrobe tables.

## 5. Creature authoring model

Continue to use existing `ContentDeclaration(kind=creature)` and
`ContentRecipe`. Do not create a second monster registry.

Each authored creature root supplies:

```text
Creature definition/factory
├── exact ContentRef and provenance
├── typed parameter model
├── structural EntityConfig/stat-block construction
├── intrinsic mechanics and traits
├── exact default possession grants
├── exact appearance facts
└── exact behavior/item/condition/spell dependencies
```

Creature-specific Python remains legitimate. A wolf bite rider, ooze split, or
dragon breath does not need to be forced into a universal data interpreter.
Data-driven families should share a builder when their mechanics are genuinely
the same:

- ordinary beasts with stats, senses, movement, and attacks;
- humanoid equipment loadouts;
- common save-and-condition riders;
- breath weapons with typed recharge/area/damage/save facts;
- typed Multiattack configurations.

Special mechanics stay beside their creature definition and use the same
behavior/content binding system.

## 6. Configured variants

Generic Caster proves that one root may have legitimate authored variants:
arcane, dark, divine, and necromancer wardrobes.

Represent those as exact recipe parameters or named content recipe presets.
The chosen preset must authenticate:

- full body recipe;
- feet recipe;
- optional head recipe;
- presentation contract;
- runtime recipe digest.

Do not hardcode one wardrobe into Generic Caster, and do not let a scenario
silently add it afterward.

## 7. Additive class levels on creatures

The current character composer already has the important removable-grant
mechanism: `CharacterGrantReceipt` plus reverse-order cleanup. Reuse it after
separating two responsibilities.

### 7.1 Extract

Split current character materialization into:

1. **Player origin grants**
   - six chosen base ability scores;
   - flexible `+2/+1`;
   - player ancestry/origin grants;
   - player starting-class assumptions.

2. **Ordered progression grants**
   - class/subclass feature schedule;
   - selected ASIs/feats;
   - class hit dice;
   - proficiencies;
   - attack multiplicity;
   - actions, reactions, resources, handlers, conditions;
   - spellcasting sources, known/prepared spells, and slot capacity;
   - removable grant receipt.

Player characters apply both. A leveled creature applies only the ordered
progression grants over its already-materialized stat block.

### 7.2 Authored leveled-creature recipe

```text
LeveledCreatureDefinition
├── exact base_creature_recipe
├── ordered class level ledger
├── exact class/subclass/choice refs
├── explicit proficiency policy
├── explicit added-hit-die policy
├── spellcasting-source combination policy
├── additional possession grants
└── its own exact configured creature ContentRef
```

The runtime entity keeps the configured/champion identity. The base creature
root remains an authenticated dependency. This supports authored Goblin
Champions, NPC Druids, or enemy spellblades without pretending they are player
profiles.

### 7.3 Policies that must be explicit

- **Proficiency bonus:** recommended default is the greater of the base
  stat-block proficiency and the class-level-derived proficiency. Never add the
  two bonuses.
- **Hit dice/HP:** preserve base creature hit dice and add one class die per
  granted class level. Whether the first added class level receives maximum HP
  is an authored policy, not inferred player behavior.
- **Starting-class proficiencies:** adding a class to an existing stat block
  follows multiclass-style proficiency grants unless an authored champion root
  explicitly says otherwise.
- **Spell slots:** combine explicit spellcasting sources through the existing
  caster-contribution and slot-capacity system. Do not overwrite innate or
  stat-block casting with the player ledger.
- **Removal/respec:** remove only class-level receipt-owned grants and leave the
  original creature object, stat block, possessions, runtime UUID, and
  independent conditions intact.

## 8. Production-renderer preview

There is currently no exact materialized creature/group preview route.
`GameCreationComposedScenario` only combines existing configuration,
battlefield, and deployment IDs.

Do not materialize a preview inside a live game process on demand: Entity,
BaseObject, GridMap, and EventQueue use process-global mutable registries.

Add a cold, isolated preview catalog builder:

1. run in a dedicated isolated runtime before admitting games, or in a small
   dedicated preview worker;
2. materialize exact creature/configuration recipes;
3. use production `project_entity_summary()` and
   `build_entity_visual_loadout()`;
4. store immutable preview DTOs keyed by exact content/configuration digest;
5. reset/retire the isolated runtime completely;
6. serve read-only preview rows without game/session mutation.

The smallest initial route supports an existing creature recipe or existing
`SideConfigurationSpec` ID. Arbitrary durable encounter/side authoring is a
separate later API; the preview route must not imply that arbitrary submitted
Python or unauthenticated recipes are accepted.

## 9. Execution phases

### Phase A — Visual/loadout ownership hard cut

1. Keep the completed Goblin Caster regression.
2. Move Goblin and Goblin Archer footwear into their creature grants.
3. Make Generic Caster wardrobe an exact recipe parameter/preset.
4. Move all twenty-one SRD humanoid scenario wardrobes into creature-owned
   possession grants.
5. Add exact dependencies for every existing SRD mechanical possession.
6. Delete `BESTIARY_WARDROBES`, `SRD_WARDROBES`, and automatic scenario
   wardrobe injection once no caller depends on them.
7. Keep only genuinely scenario-specific `ApparelGrant` use, if any.
8. Add an explicit authored presentation disposition for layered roots whose
   null head is intentional; do not assign arbitrary hair.

Exit:

- raw creature materialization is visually complete;
- declaration dependencies equal runtime grants;
- composed scenarios add no default creature wardrobe;
- all current scenario and subjective projection gates pass.

### Phase B — One current-creature materializer

1. Move current bestiary and SRD factories to the common possession applicator.
2. Replace closed scenario class/bestiary/SRD construction branches with exact
   creature recipes plus typed scenario augmentations.
3. Delete obsolete SRD factory/spec lookup APIs only after every caller is
   migrated.
4. Preserve bespoke factory functions as implementation details where they own
   real creature mechanics; callers must not dispatch through them.

Exit:

- one public creature recipe/materializer path;
- no scenario repair layer;
- no parallel identity maps;
- construction/performance gates prove no material slowdown.

### Phase C — Additive leveled-creature seam

1. Extract progression grants from player-origin grants.
2. Introduce one authored leveled-creature definition and receipt.
3. Add a deterministic Goblin or Veteran champion fixture.
4. Add/remove/reapply class levels on the same Entity and prove exact cleanup.
5. Exercise multiclass spell slots and Extra Attack-family uniqueness.

Exit:

- an existing creature can receive and lose authored class levels without
  reconstruction or base-stat damage;
- player character materialization remains behavior-identical.

### Phase D — Exact read-only preview

1. Build immutable preview DTOs from isolated production materialization.
2. Add creature and side-configuration preview lookup.
3. Generate exact TypeScript contracts/client methods.
4. Prove no live engine registry, game, directory, profile, or replay mutation.

Exit:

- NeuroClient can review every premade creature/group through the production
  renderer without fabricating wire entities.

### Phase E — SRD CR sidecar and work queue

1. Extend the pinned-PDF generator with pure Challenge extraction.
2. Check in a 317-row CR sidecar; do not change transport schemas.
3. Gate its bijection with the existing source ledger.
4. Gate the exact CR 0–5 total of 230 and current 28/202 split.
5. Classify every missing root by implementation tranche and blocking
   primitive.

Exit:

- the CR 0–5 work queue is exact, reviewable, and cannot drift silently.

### Phase F — Dependency-closed SRD batches

Recommended order:

1. ordinary beasts using existing attacks/movement/senses;
2. ordinary humanoids and NPCs using existing items/actions/spells;
3. simple save/condition riders and Multiattack families;
4. recharge and breath-weapon families;
5. flying/climbing/burrowing creatures after the common movement seam;
6. swarms and containment mechanics;
7. form-changing, incorporeal, possession, and equipment-damage families;
8. legendary-action content.

Each batch lands only when all transitive items, spells, conditions, actions,
handlers, and projection facts are implemented or explicitly classified
blocked.

## 10. Required regression matrix

### Identity and dependencies

- every creature recipe resolves in the frozen registry;
- runtime creature ref equals the requested authored ref;
- exact declaration possession dependencies equal exact runtime possession
  recipes;
- no display-name or Python-path identity;
- content digest is stable across repeated cold starts.

### Possessions and appearance

- both possession modes for every root;
- exact full recipe, preset, slot, quantity, and origin;
- no duplicate equipment on repeated deployment;
- slot conflicts fail closed and roll back;
- every layered root has body/feet or an explicit authored no-layer
  disposition;
- every head state is explicitly classified;
- subjective safe visual loadout equals objective equipment projection.

### Progression overlay

- base abilities and base proficiency are preserved;
- class grants apply exactly once;
- shared Extra Attack family does not stack illegally;
- caster contributions produce the intended combined slots;
- removal clears only receipt-owned modifiers/actions/handlers/resources/hit
  dice/spells;
- reapply after removal is deterministic;
- active combat conditions and runtime UUID survive.

### Preview

- exact production DTO equality with a real deployment of the same recipe;
- zero mutation of global registries and directory/game/profile state;
- invalid/unknown recipes fail closed;
- hosted and standalone expose the same preview facts for the same content set.

### SRD batches

- official source row and CR sidecar link;
- full stat-block fact snapshot;
- traits/actions/reactions/spells/conditions dependency closure;
- raw materialization and at least one deterministic mechanics scenario;
- projection/presentation coverage for every player-visible effect;
- explicit blocked status where an engine primitive remains missing.

## 11. Immediate next slice

The next bounded implementation slice is Phase A only:

- finish creature-owned visual/loadout closure for the current 25 layered
  roots;
- make dependencies match runtime possessions;
- remove automatic scenario wardrobe repair;
- keep the generated SDK shape unchanged;
- hand NeuroClient one content-digest restart only after all focused backend
  gates are green.

Do not begin 202 new monster implementations until this ownership cut is
complete. Otherwise every new root would be authored into the same split
factory/scenario system that this plan exists to remove.
