# July reconstruction: broader content recovery audit and migration plan

Date: 2026-08-30  
Status: DOCUMENTATION COMPLETE — independently approved; implementation is not authorized by this document

## 1. Executive conclusion

The July reconstruction has recovered the engine foundation that content needs,
but it has not yet recovered the later direct-content architecture.

The current checkpoint, `205fd67`, still uses the July generic content system:

- 48 Python modules under `dnd/content_system`;
- 26 Python modules under `dnd/core/content`;
- no tracked Python source under `dnd/content`;
- 673 built-in declarations loaded into one frozen registry even with no
  external pack roots;
- 17 production modules outside `dnd/content_system` importing that package;
- 67 production modules outside the two content packages importing
  `dnd.core.content`; and
- 133 production modules in the complete union, including content-package
  internals, importing either generic content package;
- 64 production modules mentioning `ContentRef`; and
- no installed external content packs in the repository's normal cold
  bootstrap.

This is working legacy content, not the desired in-process content boundary.

The accepted post-July checkpoint, `513dd97`, is strong behavioral evidence.
It proved direct characters, progression, premades, items, monsters, and
scenarios. It is not safe whole-file implementation
authority: it uses different later package owners, contains forbidden
reflective access, retains generic spatial recipes and presentation debt, and
never completed the final action/condition/spell content hard cut.

The recovery target is therefore:

> Preserve every accepted gameplay capability and authored value through the
> current ECS owners, while deleting the universal registry/runtime,
> `ContentRef`, recipe/pack authority, generic materializers, backend renderer
> bindings, and server-shaped persistence shell.

This track ends with direct built-in Python content suitable for the first
in-process Pygame encounter. It does not build Pygame, a server, mod loading, a
marketplace, or persistence storage.

## 2. Scope and authority

### 2.1 This document authorizes no implementation

This pass is audit and planning only. It must not change production code,
tests, content data, generated files, assets, server code, SDKs, or renderer
code. Each future migration cut requires its own bounded implementation plan
and the correctness, anti-slop, and anti-OOP reviews required by `AGENTS.md`.

### 2.2 Evidence precedence

| Rank | Evidence | Use |
|---:|---|---|
| 1 | Current checkpoint `205fd67` | Implementation owners, import DAG, event/world/Game contracts |
| 2 | Accepted checkpoint `513dd97` | Accepted gameplay behavior, inventories, direct construction outcomes, public proofs |
| 3 | July reference `4ebe523` | Original authored data and legacy behavior when later evidence is absent |
| 4 | Broken tip `1f2e525` and `dnd_engine_broken` | Forensics and preservation documentation only; never implementation authority |

Historical files are mined by capability and value. No whole file is copied
merely because it existed in the accepted branch.

### 2.3 In scope

- semantic identity and cold authored definitions;
- items, equipment, loadouts, possessions, and environment objects;
- species, variants, backgrounds, origin choices, and origin mechanics;
- Fighter/Champion, Barbarian/Berserker, and Sorcerer/Draconic progression;
- all four maintained premade characters;
- hand-built, SRD, and configured monsters;
- actions, reactions, conditions, spells, traits, feats, class features, and
  their authored metadata/ownership;
- battlefields, rosters, deployments, encounters, and setup effects;
- source attribution and exact preservation ledgers;
- saveable authored character selections, without a storage service;
- extraction of renderer bindings to the future Pygame-owned binding domain;
- removal of the generic content-system/runtime closure; and
- capability, dependency, and hard-cut proof.

### 2.4 Out of scope

- external or hot-loaded content packs;
- pack installation, manifests, plugin validation, CLI, or marketplace work;
- server/database character repositories, leases, revisions, or deployment
  records;
- transport, SDK, TypeScript, worker, gateway, or hosted-session recovery;
- Pygame rendering, input, animation, VFX, or asset loading;
- a general save-file format or save storage implementation;
- a new event, replay, controller, manager, service, repository, or registry
  framework; and
- recovery of the rejected event-reduction/knowledge experiment.

If third-party runtime-installable packs become a real product goal, they must
receive a separate design after the in-process game works. They are not a
constraint on built-in content recovery.

## 3. Starting truth at `205fd67`

### 3.1 Engine owners already recovered

These boundaries are current authority and must not be recreated inside
content:

| Capability | Current owner/result |
|---|---|
| Provisional Entity construction | `Entity.create`, initial validation, one `Entity.compose_entity` birth fact, and `discard_uncommitted` failure cleanup |
| Complete birth evidence | `EntityCreatedEvent` contains the committed aggregate; its current fields are proven against a rich authored character |
| World ownership | one in-process `Game`, explicit deployment, Tile occupancy |
| Cold world initialization | one `WorldInitializedEvent` per maintained battlefield |
| Scenario chronology | cold world, then dynamic hazards/lights, then births, then deployments |
| Spatial mechanics | current `SpatialCondition`, transitions, optical/light owners, and per-step sensory settlement |
| Geometry | directional structures, containers, elevation, connectors, traps, torches, and support state |
| Oil Barrel | destruction spills Oil and fire replaces Oil through the direct material transition owner |
| Subjective evidence | objective Events plus owner-local sensory deltas and same-model subjective combat-log projection |

Content builders call these owners. Content does not duplicate them, wrap them
in a second lifecycle, or teach `Entity`, `Game`, `GridMap`, Events, actions,
conditions, or blocks how to discover authored content.

### 3.2 Current generic declaration inventory

With `bootstrap_content_system(pack_roots=())`, the current built-ins load 673
declarations:

| Kind | Count |
|---|---:|
| action | 80 |
| background | 2 |
| class | 3 |
| class feature | 63 |
| condition | 109 |
| creature | 63 |
| environment object | 16 |
| feat | 1 |
| item | 112 |
| reaction | 8 |
| species | 9 |
| species variant | 4 |
| spell | 116 |
| starting equipment package | 14 |
| subclass | 3 |
| trait | 70 |
| **Total** | **673** |

The declarations are owned by three pack IDs:

| Pack ID | Count |
|---|---:|
| `content.neurodragon` | 147 |
| `content.srd_5_1_cc` | 490 |
| `core.rules` | 36 |

The registry also contains 205 recipe presets and two source records. These
counts are preservation evidence. They are not target registry requirements.

The current composition additionally exposes:

- 191 materializable factory roots;
- 395 behavior identities;
- 87 typed structural definitions; and
- 38 authored encounters over 9 battlefields.

This is substantial functioning content. Recovery must not treat the current
system as an empty shell or delete it before row/capability proofs exist.

### 3.3 Current architectural debt

The current tree still has all of the following:

- process-global installed content runtime;
- pack/bootstrap/import-validation machinery;
- universal content identities with kind, pack, version, and hashes;
- generic declarations, construction wrappers, recipes, and materializers;
- behavior admission coupled to runtime content bindings;
- `ContentRef` values in engine-facing state;
- character composition coupled to content-runtime contexts;
- generic item/creature/scenario materialization;
- backend item/entity appearance and icon/visual vocabulary; and
- server/persistence-shaped durable-character values mixed into authored
  character definitions.

This debt crosses core rules, actions, conditions, spellcasting, items,
classes, monsters, scenarios, spatial effects, and runtime reset. It cannot be
removed by deleting one package.

Specific ownership faults already identified are:

- `ITEM_RUNTIME_BINDINGS` and `CREATURE_RUNTIME_BINDINGS` keep authored runtime
  facts parallel to the item/Entity that owns the gameplay state;
- convenience materializers silently bootstrap a server-named global content
  runtime;
- character composition removal scans the global Entity registry to discover
  linked transient conditions rather than following explicit source-owned
  state;
- pack-loader rollback snapshots still know obsolete Entity-position indexes;
- decorator-attached declarations use reflective metadata access; and
- legacy direct builders coexist with generic declaration/materializer paths.

The current audit reasonably observed that a frozen startup catalog is a
coherent authoring index. This plan retains that useful capability as
domain-local cold catalogs, not as a cross-domain aggregate. It does not retain
the universal catalog as construction, materialization, behavior-admission,
pack, or runtime-state authority. That distinction resolves the audit
disagreement without discarding the current inventory.

### 3.4 Current content/regression health

A broad read-only audit of the current checkpoint reported:

- all 305 `test_*.py` modules are nominally active under `pyproject.toml`, with
  no configured deprecated/server exclusion;
- 2,527 tests discovered;
- 81 collection errors across 5 engine, 66 manual, and 10 progression modules:
  77 stale server/transport imports of removed `dnd.core.senses`, 2 legacy
  `dnd.tiles` imports, and 2 stale armor-content imports;
- content dependency architecture: 13 passed, 2 failed, both from the stale
  server import;
- complete architecture lane: 54 passed, 3 failed, all three caused by
  deprecated-server cold imports;
- server-independent content selection: 115 passed, 30 failed;
- progression selection: 314 passed, 10 failed; and
- engine/content/scenario selection: 233 passed, 6 failed.

Known failure groups include:

- tests expecting removed legacy armor/weapon/consumable/spell-item lookup
  maps;
- pack-loader tests expecting obsolete Entity-position registries;
- battlefield tests encountering a nonempty GridMap after reset;
- Sleet Storm allowing a mounted WallTorch to relight;
- spell action-economy, Halfling traversal/stealth, Tiefling reaction spell,
  magical-sleep immunity, Quickened Spell, Counterspell source selection, and
  spell-damage-affinity failures.

Additional bounded evidence:

- the runtime identity/reset selection produced 65 passes and 6 failures, all
  from a tutorial's private reset helper reading removed
  `Entity._entity_by_position`; it must use `reset_engine_runtime`, never
  restore the mirror;
- an 87-test maintained creature lane passed; a legacy skeleton module then
  failed specialized-arena, Eldritch Blast, and acid-flask cases and stalled,
  so that module is characterization debt rather than proof; and
- a 91-test maintained scenario lane covers the 38 current assemblies,
  catalog closure, roster duels, and mechanics scenarios.

These are a separate visible regression ledger. Architecture-shaped lookup-map
or obsolete-position tests should be rewritten/deleted with their owning cut,
not satisfied by restoring aliases. Gameplay failures must be characterized
and repaired by their legitimate mechanics owner before or during the cut
that depends on them; they may not be hidden as migration fallout.

The default pytest lane is not currently an acceptance lane. CR-0 must declare
the maintained in-process file/node list and rescue semantic cases from mixed
server modules. A final claim of completion requires either zero default
collection errors or an explicit intentional deprecated-server lane; accidental
import errors are not quarantine.

### 3.5 Current inventory gaps requiring explicit classification

- 116 canonical spell identities exist, while the character/spell catalog has
  114 rows. Both unmatched identities need an explicit intentional-private,
  missing, or obsolete disposition.
- Circus Fighter items and several traits/conditions are declared, but its
  `create_warrior` creature root remains direct and unregistered.
- Four durable premade builds exist, while only three are creature roots. The
  accepted direct boundary settles the target: all four remain ordinary public
  character builds, without requiring each to be a scenario creature root.
- The large static built-in inventory is a valid upper DAG composition point
  today but is fragile and must be mined, not expanded.

## 4. Historical capability inventory to recover

### 4.1 Direct origins

Recover the accepted public behavior for:

- 9 species: Dragonborn, Dwarf, Elf, Gnome, Half-Elf, Half-Orc, Halfling,
  Human, and Tiefling;
- 4 variants: Hill Dwarf, High Elf, Rock Gnome, and Lightfoot Halfling;
- 2 backgrounds: Acolyte and Adventurer;
- all 18 authored origin feature IDs;
- exact ancestry, language, tool, skill, flexible ability, and High Elf
  cantrip choices;
- level-dependent Hill Dwarf toughness, Dragonborn breath scaling, High Elf
  spell scaling, and Tiefling innate spells; and
- exact source-owned installation and removal.

Definitions are cold values. Mechanics remain in the existing origin, action,
spell, modifier, resource, health, proficiency, and event owners.

### 4.2 Direct progression

Recover:

- Fighter/Champion 1–20;
- Barbarian/Berserker 1–20;
- Sorcerer/Draconic Bloodline 1–20;
- first-class versus multiclass proficiency differences;
- subclass/choice/prerequisite validation;
- add-level and remove-last-level behavior;
- source-owned hit dice, ASIs/feats, actions, handlers, resources, spell
  sources, known/prepared/reaction spells, slots, formulas, and features;
- aggregate reconciliation after addition/removal;
- total-level-dependent origin reconciliation;
- one ordinary class level applied to a monster; and
- silent hydration from semantic selections without duplicate birth/level
  facts.

The current checkpoint has class-level data on `Entity` but no direct
post-birth progression operation equivalent to the accepted add/remove path.
This is real missing capability.

### 4.3 Four premades

Recover all four as plain authored selections over the ordinary character
path:

- level-5 Berserker;
- level-5 Champion Fighter;
- level-5 Draconic Sorcerer; and
- Fighter 2 / Sorcerer 3 Spellblade.

No premade may own a private materializer or special Entity constructor.

### 4.4 Items and environment content

Freeze the original 127 mechanical item identities:

| Family | Count |
|---|---:|
| weapons | 45 |
| apparel | 24 |
| armor | 17 |
| environment objects | 15 |
| spell items | 9 |
| consumables | 8 |
| gear | 6 |
| shields | 2 |
| equipment | 1 |
| **Total** | **127** |

The accepted direct catalog contained 146 identities: 126 of the frozen 127
plus 20 newly semantic wardrobe/loadout variants. Its missing baseline item was
the Oil Barrel. The current checkpoint now supplies the barrel's real spatial
transition, so the likely reconciled union is 147 identities. That number is a
hypothesis until an exact semantic-ID collision/variant audit proves it.

For every retained item preserve:

- exact semantic mechanical identity;
- runtime UUID and instance state;
- quantity, stack policy, charges, durability, and consumed/broken state;
- inventory, equipped, intrinsic, contained, and world placement;
- exact equipment/body/weapon slots and collision rules;
- direct behavior ownership for use, spell, reaction, coating, destruction,
  container, light, or spatial transition behavior; and
- rollback of partial loadout/possession construction.

Do not turn `ItemPresentationState`, `ItemContentRefSnapshot`, an icon key, or a
visual recipe into the new mechanical item model.

### 4.5 Monsters

Recover:

- 8 hand-built bestiary roots;
- Circus Fighter;
- all 27 SRD roots;
- all 21 configured-SRD wardrobe compositions;
- intrinsic/body equipment versus optional possessions;
- default-possession opt-out;
- traits, actions, attacks, multiattacks, spells, reactions, senses,
  immunities, affinities, and semantic body state; and
- ordinary post-birth class progression.

All monster families use the same current Entity construction/commit boundary.
Monster/NPC is authored identity and deployment/presentation policy, not a
second construction architecture.

### 4.6 Scenarios

Recover the accepted authored surface:

| Family | Accepted count |
|---|---:|
| rosters | 58 |
| roster members | 141 |
| deployments | 10 |
| encounters | 39 |
| encounter roster slots | 78 |
| item grants | 43 |
| spell grants | 23 |
| behavior grants | 19 |
| starting-damage applications | 10 |
| affinity grants | 2 |
| starting-condition applications | 2 |

The current source data retains the 58 rosters, 141 members, and setup-effect
counts, but only 9 deployments, 38 encounters, and 76 roster slots. The
accepted-only authored rows are the elevation proving-ground deployment and
encounter. The current battlefield builder already has that battlefield; the
missing work is direct authored deployment/encounter data.

Retain:

- current cold-world and dynamic-setup chronology;
- current caller-owned `Game`;
- two-pass roster construction for cross-member references;
- opportunity attacks, senses, controllers, fixed opening, and optional
  prepare-without-start behavior;
- named member and notable-position lookups;
- setup ordering and actual gameplay compatibility checks; and
- failure cleanup without process reset or partial published scenario.

### 4.7 Behaviors outside the headline character lines

Do not lose content because it is outside the three primary classes:

- Paladin Divine Smite processing and handler behavior;
- Aegis Spark spell and condition/effect behavior;
- Field Kit item/action mechanics;
- reaction-spell identities and outcomes;
- environment/spatial transitions;
- authored condition effects;
- monster/private behaviors; and
- current action/spell/condition/trait/feat inventories.

The seven legacy authored-source inventories below remain forensic inputs until
every row has a disposition:

- `action_definitions.py`;
- `behavior_bindings.py`;
- `condition_definitions.py`;
- `condition_effect_population.py`;
- `reaction_definitions.py`;
- the legacy spatial transition inventory; and
- `spell_catalog_composition.py`.

They are not target runtime modules.

### 4.8 Saveable character selections

Preserve plain semantic values for:

- species, variant, background, origin choices, and body semantics;
- ordered class/subclass levels and level choices;
- starting equipment/loadout selections;
- prepared spells keyed by exact spell source;
- feature toggles and support status; and
- item instance state that is genuinely durable.

Runtime UUID handles and removal receipts are regenerated when a character is
hydrated in-process. Package digests, contract hashes, database revisions,
leases, server deployment records, and live Entity serialization are not
preserved.

At least one direct nonempty prepared-spell selection and one supported feature
toggle must be proven. Empty current premades are not sufficient coverage.

### 4.9 Recovery completeness versus SRD expansion

`content_data/ledgers/srd_5_1_source_coverage.json` contains 925 source rows:

| Domain | Playable | Partial | Missing |
|---|---:|---:|---:|
| armor | 13 | 0 | 0 |
| creatures | 29 | 0 | 288 |
| magic items | 0 | 5 | 234 |
| spells | 110 | 0 | 209 |
| weapons | 25 | 0 | 12 |
| **Total** | **177** | **5** | **743** |

The five partial magic-item rows are Potion of Healing, Potion of Speed, Spell
Scroll, Wand of Magic Missiles, and Weapon +1/+2/+3.

Content recovery means preserving and directly proving the implemented current
and accepted capabilities while keeping missing/partial source statuses honest.
It does not silently authorize implementation of 743 new SRD rows. Full SRD
expansion is a later content-authoring program.

The current exhaustive SRD measuring test is uncollectible and every ledger row
points to that one dead node. CR-0 must add collectible evidence for the 177
implemented and 5 partial rows that recovery actually claims. The 743 missing
rows remain hash-exact documentary inputs for later SRD expansion and do not
require new recovery tests. Non-SRD families—origins, classes, subclasses,
features, traits, actions, reactions, and conditions—need explicit inventories
of currently implemented/accepted capabilities because no equivalent recovery
ledger exists.

Counts such as 63 built-in creature declarations must not be presented as SRD
coverage: configured and NeuroDragon roots are included while 288 SRD creatures
remain intentionally missing.

## 5. Asset, binding, and source evidence

### 5.1 Current evidence hashes

| Artifact | SHA-256 |
|---|---|
| `content_data/ledgers/content_icon_bindings.json` | `2129a753a0ad13d5fa472ad9dd9a3b354ae0f73299b753d12ef520ac17736ec8` |
| `content_data/ledgers/neuroclient_authored_item_visuals.json` | `7850493fb83395a363110e0c5e99d9da69a287a7b1f663c4906715af41ce7a4a` |
| `content_data/ledgers/neuroclient_game_icon_asset_index.json` | `da24829f890902b37e79ea4e31fff2893ff184db2fc6eea36877c22081b2ed8f` |
| `content_data/ledgers/srd_5_1_source_coverage.json` | `cb5c78be958636b158c0b9ce2a7005f76d6db6a7e795c609f8829124400879be` |
| `content_data/sources/neurodragon_original_b2b3930.json` | `14afc6255cd0353ce0e3005253e9f21eb8b6d52eec8fe3fa943c66f44e2cc7cb` |
| `content_data/sources/neurodragon_original_b2b3930.txt` | `5d5b9fd982162ffeb960166665ac4bf464f260fea7cb8cfe453039366874a2f9` |
| `content_data/sources/srd_5_1_cc.json` | `5a00ce5121a3aaa24cb6f6521b25868ef601925377cf91fccb4f72701dd5e578` |

### 5.2 Accepted evidence hashes

| Accepted artifact | SHA-256 |
|---|---|
| deprecated icon bindings | `308d849b8e6e930409a611ace81fe86f819d9b370979882f7d3c0543252c7bbd` |
| deprecated authored item visuals | `267ef479048dfd2fc52d78037e29becbd74d7ccc8939194a94dc44fa49118f08` |
| deprecated game icon asset index | `1cf4d2620016b27e94591c1a757401e49a1e195fdc9b5b831d3abf84f71a7da4` |
| deprecated SRD coverage | `64aecb5cb2c253b9b236b1dba437a49986997afa2ce3a110a809b5f31955a18f` |
| deprecated NeuroDragon JSON source | `198d9284aca94910fc5bd4717e94d1bdd3712f2657341265f8b564ce373a948e` |
| deprecated NeuroDragon text source | `5d5b9fd982162ffeb960166665ac4bf464f260fea7cb8cfe453039366874a2f9` |
| deprecated SRD JSON source | `6b49392e563bc274162d9f065f6f8721e905f847bdabe97be880aa96bd462d89` |

The current and accepted artifacts are not byte-equivalent. Neither set may
overwrite the other before row-level reconciliation.

### 5.3 Known binding scale and differences

- 77 authored item visual categories;
- 205 authored item visual variants;
- 1 recorded source-ID collision;
- 925 SRD source-coverage rows;
- 205 recipe-preset icon bindings;
- 669 current versus 671 accepted icon definition bindings; and
- 515 current versus 521 accepted game-icon asset-index rows.

The 671/669 difference is not simple growth: accepted evidence added seven
bindings and dropped five older bindings. Every row needs an explicit
mechanics, renderer-binding, source-only, or obsolete disposition.

### 5.4 Python-authored bindings to extract before editing owners

Freeze exact source locations and values for:

- species/variant/background appearance choices;
- all four premade appearance selections;
- bestiary appearance constants and wardrobe keys;
- all 21 configured-SRD mappings;
- SRD icon, variant, and tint choices;
- Tile sprite bindings;
- traversal presentation keys and `gap.png`;
- item/environment presentation literals;
- spatial VFX profiles; and
- Field Kit bindings.

Semantic IDs must be stable before these rows move. The future Pygame package
owns asset paths, sprite layers, tints, animation clips, icons, and VFX. Engine
content retains only mechanical and authored semantic state.

Static legal/source attribution remains a checked-in data/documentation
ledger; it does not travel on every runtime Entity, item, Event, or condition.

## 6. Target architecture

### 6.1 ECS ownership law

Content is authored data plus explicit composition functions over the existing
ECS. It does not own engine mechanics.

- Entities remain data structures and system composers.
- Blocks/components own their mutations and exact removal handles.
- Actions own validation/execution/cost semantics.
- Conditions and `SpatialCondition` own their lifecycles.
- `GridMap` owns topology and world admission.
- `Game` owns deployed Entities.
- `Encounter` owns turn/action orchestration.
- Events report committed facts from those owners.
- Content definitions choose and compose those capabilities.

### 6.2 Dependency direction

```text
                         dnd/types
                         /       \
                        v         v
    core / blocks / Entity / rules   content/<domain>/definitions
                        \         /
                         v       v
             content/<domain>/builders + composition
                              |
                              v
               content/scenarios + application/Pygame
```

Additional laws:

- core, blocks, Entity, Game, actions, conditions, and Events do not import
  `dnd.content`;
- cold definitions import dependency-leaf values, never builders or live
  Entity/component classes unless the value is genuinely an engine leaf;
- builders may import cold definitions and concrete mechanics owners;
- scenario/application code may import content builders plus Game/Encounter;
- Pygame may import content/application seams; engine mechanics never import
  Pygame or asset mappings; and
- no function-local imports, circularity, `TYPE_CHECKING`, `getattr`, or
  runtime type inspection may hide a forbidden edge.

### 6.3 Identity

Use direct domain-native semantic IDs:

- species, variant, background, class, subclass, feature, spell, action,
  reaction, condition, trait, item, monster, battlefield, roster, deployment,
  and encounter IDs;
- runtime UUIDs only for runtime instances/owners; and
- explicit provider/source/root IDs where actual behavior ownership requires
  them.

There is no universal replacement for `ContentRef`. Any ID stored by an engine
component, action, condition, handler, spell source, or Event is either a
validated primitive or a focused dependency-leaf value owned above both
mechanics and authored content, such as an existing module under `dnd/types`.
Content-domain enums/types never leak downward. Content-only IDs may remain in
cold definitions; builders translate them into the leaf values understood by
mechanics. No ID carries pack, version, contract hash, factory path, icon path,
or recipe payload.

Distinct domains may lawfully reuse the same textual ID. No global namespace
or cross-domain identity object is introduced.

### 6.4 Definitions and builders

- Definitions are frozen plain data.
- A domain-local catalog is a read-only map/tuple of those values.
- A builder is an explicit function for that domain.
- A small domain-local dispatch map is allowed only when it directly selects
  concrete builders and remains separate from cold definitions.
- There is no generic materializer, JSON invocation language, factory-string
  loader, construction descriptor, polymorphic content base class, or
  cross-domain registry.

### 6.5 Reversible composition

Preserve the useful part of the legacy character grant system: exact
source-owned component mutation receipts.

The target is procedural ECS composition:

1. resolve authored values and choices without mutating an Entity;
2. apply typed component operations in an explicit order;
3. each component owner returns exact data handles for its mutation;
4. the existing Entity-owned character/progression state—or one explicitly
   justified data-only progression component—stores the ordered semantic step
   plus ephemeral runtime handles;
5. on failure/removal, call the matching owner cleanup operations in reverse;
6. commit initial construction once through current `Entity.compose_entity`;
   and
7. regenerate ephemeral handles during silent hydration.

Do not implement this as callbacks of callbacks, an `Undo` closure graph, a
polymorphic command hierarchy, a transaction/context-manager object, a
content manager, or a second Entity lifecycle. Receipts are typed data naming
installed component state; systems perform the cleanup.

The composition/progression systems are stateless orchestrators of existing
component operations. They do not become large Entity methods. There is no
global receipt registry, receipt lookup service, content runtime, manager, or
Entity scan: cleanup follows only handles owned by the character/progression
state and invokes the actual component owners in reverse order.

### 6.6 Behavior identity and metadata

Live actions, conditions, handlers, reactions, spells, traits, and their Events
carry direct semantic behavior/source IDs. Admission validates those local
values and does not consult an installed content runtime.

Player-facing names/descriptions/tags remain authored data in domain-local cold
catalogs. Renderer icons/animations/VFX are Pygame/client bindings keyed by the
same semantic IDs. Neither is an execution registry.

## 7. Rejected architecture and bytes

### 7.1 Do not recover from July/current generic content

- external pack loader/CLI/manifest/plugin simulation;
- universal registry and installed runtime;
- `ContentRef` pack/version/hash authority;
- `ContentRecipe` and generic JSON/factory invocation;
- artifact/content-set/contract digest runtime authority;
- behavior provider gateway;
- generic character/item/creature/scenario materializers;
- server/database character revisions and deployment records;
- backend icon/sprite/VFX ownership; or
- registry/package/reset tests whose only capability is the deleted shell.

### 7.2 Do not transplant from accepted `513dd97`

- its later split `dnd/entities` package ownership;
- reflective `getattr` access in direct character grants;
- its still-generic spatial recipe/materialization modules;
- incomplete static presentation migration;
- residual `ContentRef`/decorator closure; or
- any helper whose only purpose is adapting to those later packages.

### 7.3 Reject from broken `1f2e525`

- `dnd/event_reduction.py`;
- `Known`/`Unknown` path values;
- `CanonicalEventView` or generic Event clones;
- exhaustive reducer manifests;
- Event-owned traversal of Entity/components/conditions;
- `resolve_sub_events` / `finalize_terminal` lifecycle control;
- consumer receipts/acknowledgements;
- generic condition-cleanup ownership replacing specific owners;
- late imports and allowlists hiding inverted dependencies; and
- the three content-adjacent broken changes to Sorcerer Metamagic cleanup,
  battlefield lifecycle publication, and LeadershipAura cleanup.

Retain the gameplay laws those files touched. Reimplement them only through the
legitimate current owner when a future capability proof requires it.

## 8. Migration method

Every cut follows the same hard-cut loop:

1. freeze the exact capability, authored rows, callers, and accepted proofs;
2. classify current, accepted, July, and broken evidence per row;
3. add/choose direct dependency-leaf semantic values;
4. implement through existing component/system owners;
5. migrate every active caller in the bounded family;
6. prove mechanics, rollback, committed Events, import locality, and absence of
   the replaced path;
7. delete the replaced declarations/materializer/refs/tests in the same cut;
8. rerun affected proof lanes and update the recovery ledger; and
9. receive correctness, anti-slop, and anti-OOP approval before the next cut.

No cut may leave a compatibility facade, optional legacy field, dual write,
fallback to Python class paths, or second construction authority.

## 9. Ordered migration program

The names below use `CR` to avoid confusion with the completed Tile/world
phases and the historical content plan's phase numbers.

### CR-0 — evidence freeze and executable recovery ledger

Documentation/data/test work only; no production behavior change.

- Declare the exact maintained in-process test file/node list before citing a
  baseline; the current default collection is invalid.
- Split/migrate genuine engine/progression/spell/content cases out of mixed
  deprecated-server modules without reviving server, `dnd.core.senses`,
  `dnd.tiles`, `_entity_by_position`, or removed lookup maps.
- Freeze current and accepted artifact hashes and produce row-level binding
  and source-ledger diffs.
- Freeze exact implemented/accepted origin, class, premade, item, monster,
  scenario, action, reaction, condition, spell, trait, and feature inventories.
- Preserve all 925 SRD rows hash-exact. Add live measuring evidence only for
  the 177 implemented and 5 partial rows affected by recovery; leave the 743
  missing rows to the later SRD expansion program.
- Re-derive the 127 item baseline and accepted semantic variants.
- Record source location, semantic ID, capability, current owner, accepted
  proof, target disposition, and blocker for every migration-relevant row.
- Freeze all importers of `dnd.content_system`, `dnd.core.content`, and
  `ContentRef`, and classify tests by gameplay capability versus obsolete
  architecture shape.
- Freeze the following action-discovery/source guarantees:
  - `tests/engine/test_action_discovery.py::test_eb_09_003_execute_by_index_instantiates_and_applies_costs`;
  - `tests/engine/test_action_discovery.py::test_eb_09_007_action_overrides_change_cost_display_and_consumption`;
  - the accepted typed connector discovery/execution proof
    `test_connector_discovery_and_atomic_execution_share_one_typed_variant`;
  - all five selectors in
    `tests/architecture/test_action_discovery_requirements.py`; and
  - `tests/progression/test_spellcasting_source_action_propagation.py::test_spell_variants_and_executable_clones_preserve_exact_source`.
- Add no runtime registry or migration abstraction.

Gate: every retained/partial content row and every old importer has one
disposition; both evidence sets remain available and hash-exact; every claimed
implemented/partial status names a collectible semantic proof; and the
maintained in-process baseline is explicit and reproducible. The 673 legacy
declarations require dispositions, not 673 target declarations or objects.

### CR-1 — direct behavior-free items and placements

- Introduce direct item IDs and renderer-neutral instance values inside this
  owning family cut, not in a cross-domain semantic-state phase.
- Port mundane weapons, armor, shields, apparel, gear, and pure blockers to
  cold definitions and direct builders.
- Establish silent initial inventory/equipment placement using the same
  validation and mechanics as runtime placement, without construction Events.
- Preserve quantities, slots, stack/charge/durability state, containers, and
  rollback.
- Migrate starting packages/loadouts as cold semantic plans, not recipes.
- Migrate all mechanical producers/consumers/Event fields and delete the
  family's `ContentRef`, declarations, presets, recipes, and materializer
  callers in the same bounded cut.
- Freeze existing visual fields and their exact consumers as read-only binding
  migration inputs until CR-8. They are not mechanical authority, are not dual
  written, and receive no new consumers.

Gate: direct construction and round-trip semantic item/Event facts for every
migrated ID; no registry bootstrap is required; no migrated item has two
mechanical identities or construction paths.

### CR-2 — family-atomic behavior admission cuts

Migrate only the behavior families required by the next item and character
cuts. For each bounded family, the same cut must:

- choose a validated primitive or dependency-leaf behavior/source ID;
- add its domain-local cold metadata row;
- migrate actions, conditions, handlers, reactions, discovery rows, Events,
  and all consumers;
- remove the family's attached declaration decorator/reflection and old
  runtime binding/admission authority; and
- preserve execution, action economy, condition ownership/cleanup, reactions,
  discovery, typed targets/variants, overrides, and exact source ownership.

Unmigrated families remain wholly legacy and frozen. A concrete behavior class
must never expose both a direct identity and attached legacy declaration
identity, and there is no fallback between the two paths. The remaining whole
families are migrated in CR-9.

Acceptance includes:

- the two `test_action_discovery.py` selectors frozen in CR-0;
- typed connector discovery and atomic execution sharing one variant;
- all five action-discovery architecture selectors;
- spell variants and executable clones preserving exact source;
- representative standard/class/item/spell/reaction/condition installation
  and execution in a fresh process; and
- zero content-runtime admission for every migrated family.

This is not permission to redesign Events, action dispatch, conditions,
controllers, or spells.

### CR-3 — behavior-bearing items and complete direct item inventory

- Port consumables, spell items, Field Kit, hook-bearing weapons/equipment,
  interactive environment objects, lights, containers, and destruction/spatial
  behaviors through their existing owners and already-migrated behavior
  families.
- Introduce/delete their direct semantic values and old refs within each item
  family cut; keep visual inputs frozen until CR-8.
- Reuse the current direct Oil Barrel material transition; do not resurrect the
  accepted generic spatial recipe.
- Reconcile all baseline and variant IDs and resolve collisions explicitly.
- Preserve item-authored behavior ownership and immutable declaration-time
  mechanical item facts on relevant Events.

Gate: exact final direct-item inventory, expected likely 147 but mechanically
derived; all retained baseline IDs construct and exercise their real behavior.

### CR-4 — reversible character/origin/progression composition

- Introduce dependency-leaf origin/class/level/save values and remove their
  legacy refs within this owning family cut.
- Port typed source-owned receipt data and owner cleanup operations from the
  legacy grants without their runtime/registry context.
- The existing Entity-owned character/progression state, or one justified
  data-only progression component, owns ordered semantic steps and ephemeral
  handles. Stateless progression functions orchestrate actual component
  owners; no global receipt lookup, Entity scan, or large progression methods
  on Entity are allowed.
- Port all origin definitions, choices, and 18 feature mechanics.
- Port all three class/subclass lines for all 20 authored levels.
- Add direct add-level/remove-last-level system operations over the current
  Entity data.
- Reconcile proficiency, hit dice, origin scaling, actions/handlers/resources,
  spell sources/spells/slots, features, formulas, and attack multiplicity.
- Initial levels remain inside one unpublished construction and one existing
  birth fact; post-birth changes publish direct committed level facts.
- Silent hydration rebuilds handles from semantic selections without duplicate
  facts.
- Freeze appearance bindings as read-only CR-8 inputs; do not delete them
  before their external mapping is installed and validated.

Gate: exact apply/remove rollback for every handle family, all authored levels,
multiclass behavior, total-level origin changes, nonempty prepared/toggle
examples, and a classed monster.

### CR-5 — direct character authoring and all premades

- Resolve body, origin, ordered levels, starting items, prepared spells, and
  toggles without mutating an Entity.
- Apply the resolved operations once to a provisional current Entity and
  commit once through current `Entity.compose_entity`.
- Rebuild all four premades through the same public character path.
- Expose plain authored inputs suitable for the future two-character Pygame
  encounter.

Gate: direct custom character plus all four premades match accepted mechanics,
selections, inventory/equipment, birth facts, and failure cleanup.

### CR-6 — direct monsters

- Introduce/delete monster-domain semantic values and old refs inside the
  monster cut; freeze visual bindings until CR-8.
- Port the 8 bestiary roots, Circus Fighter, 27 SRD roots, and 21 configured
  compositions to cold definitions and direct construction.
- Preserve intrinsic equipment versus possessions and possession opt-out.
- Preserve every trait/action/attack/multiattack/spell/reaction/sense/immunity/
  affinity through behavior families already migrated in CR-2.
- Use the same current Entity composition/commit boundary as characters.
- Delete generic creature declarations/materializers and parallel factory
  switches per migrated family.

Gate: exact monster construction/state/behavior, one birth fact, explicit Game
deployment, and post-birth class application.

### CR-7 — direct scenarios and deployments

- Introduce/delete scenario-domain semantic values and old refs within this
  family cut; freeze map bindings until CR-8.
- Port roster/deployment/encounter/battlefield authored values to direct domain
  definitions and explicit build plans.
- Preserve current world chronology, battlefield builders, dynamic trap/light
  owners, caller-owned Game, and failure cleanup.
- Restore the accepted elevation proving-ground deployment and encounter.
- Preserve all accepted counts and setup behaviors from section 4.6.
- Delete generic encounter recipes/materializer and obsolete package/runtime
  compatibility assertions.

Gate: all maintained encounters prepare in-process without content runtime or
global reset; scenario chronology and gameplay setup remain exact.

### CR-8 — static binding extraction and presentation hard cut

- Reconcile both artifact sets row by row.
- Install static item/entity/map visual bindings in future `/game`
  Pygame-owned binding data and validate complete coverage before deleting any
  corresponding backend visual field or consumer.
- Keep semantic names/descriptions/tags in domain cold metadata where useful.
- Replace backend visual/portrait/sprite state with actual semantic state and
  update Events to report mechanical/semantic after-values.
- Delete static generated backend binding consumers after exact coverage.
- Freeze still-live action/condition/spell/spatial binding rows and importers
  for CR-9; do not partially hollow their modules.

Gate: static item/entity/map engine content contains no asset authority; every
static binding has one Pygame/client disposition, and every deferred behavior
binding has an explicit CR-9 disposition.

### CR-9 — remaining family-atomic behavior and binding migration

- Migrate every remaining action, reaction, condition, spell, trait, feat,
  class feature, condition effect, and spatial transition as a whole family
  using the CR-2 law: direct leaf ID, cold metadata, all consumers, decorator/
  reflection removal, and old runtime binding deletion in the same cut.
- Preserve private owner-local behaviors without making them globally
  constructible.
- Preserve spell catalog/search metadata as a direct spell-domain cold map.
- Preserve Paladin Divine Smite, Aegis Spark, Field Kit, reaction spells,
  spatial VFX semantic cues, source-owned cleanup, discovery/variant/override
  behavior, and exact executable source propagation.
- Install frozen behavior visual bindings in the Pygame/client domain before
  deleting backend binding consumers.
- Eliminate remaining declaration population, generic effects definitions,
  and spatial recipes.

Gate: all 673 legacy rows have dispositions; fresh-process behaviors work
without content bootstrap; zero gameplay importers of the generic closure and
zero backend renderer asset authority remain.

One-to-one disposition does not require one target object. Private behaviors
may remain private, duplicate metadata may collapse, and architecture-only rows
may be deleted, but every gameplay capability and authored value has an
explicit disposition.

### CR-10 — generic runtime deletion and final certification

Only after all previous gates:

- delete `dnd/content_system` and the remaining generic `dnd/core/content`;
- delete pack bootstrap/configuration/CLI/import validation;
- delete universal registry, recipes, declarations, materializers, digests,
  and `ContentRef`;
- delete stale reset hooks and obsolete architecture-shaped tests;
- retain source/legal ledgers outside runtime authority;
- prove import DAG, no cycles/late imports/reflection, and no server/SDK/renderer
  dependency; and
- run complete maintained gameplay/content/progression/scenario/architecture
  lanes plus the final default-collection gate.

Gate: direct built-in content and all accepted gameplay capabilities work from
one fresh in-process Python runtime with no generic content system present.

## 10. Capability proof matrix

| Domain | Required behavioral proof | Accepted/current evidence to mine |
|---|---|---|
| Entity birth | one complete committed fact, no partial birth, cleanup on failure | current `test_world_entity_initialization.py` and rich-Entity parity proofs |
| Items | every retained ID constructs; instance state, placement, behavior, rollback | accepted `tests/engine/test_direct_item_content.py`; current Oil Barrel tests |
| Origins | all definitions/choices/features and level reconciliation | accepted direct character tests plus current origin behavior tests |
| Progression | all authored levels, multiclass, add/remove, hydration, classed monster | accepted `test_direct_class_progression.py` and entity progression core proofs |
| Premades | all four use ordinary direct character composition | accepted `test_direct_premade_characters.py` |
| Monsters | all maintained roots/configurations, possessions, behaviors | accepted `test_direct_monster_creation.py` plus current monster gameplay tests |
| Scenarios | exact catalog counts, setup effects, Game/world chronology | accepted `test_direct_scenario_deployment.py` plus current world initialization proofs |
| Behavior identity | action/condition/handler/spell install and execute without runtime gateway | accepted direct behavior identity proofs plus current gameplay suites |
| Bindings | every old row classified, no backend asset ownership | both frozen artifact sets and Python crosswalk inventory |
| Hard cut | zero forbidden imports/types/runtime paths | new architecture scans plus fresh-import probes |

Tests must assert mechanics, exact owner state, rollback, committed Event facts,
and dependency direction. Registry hashes, package manifests, server projections,
and wrapper object shapes are not substitute capability proofs.

Minimum acceptance for a claimed playable content row/family is:

1. exact source row, direct domain ID, and static legal/source attribution;
2. unique cold domain definition/catalog membership;
3. direct construction into the existing ECS components;
4. no deployment during construction;
5. cancellation/exception leaves no component, binding, registry, occupancy,
   spatial, Event, or provisional-identity residue;
6. runtime reset retires mutable identity/state without deleting cold authored
   definitions;
7. at least one observable gameplay outcome through public action/Event
   boundaries;
8. one caller-owned Game scenario when the capability is deployable;
9. a named measuring node that collects and passes; and
10. the strict import/DAG gates remain clean.

During staged migration an unchanged legacy family may still use its old cold
definition source. A migrated family must satisfy these requirements through
the direct target seam and delete its old construction authority in the same
cut.

## 11. Deletion gates

### 11.1 Generic character materialization may be deleted only when

- every origin/class/premade path is direct;
- all choices and authored levels are present;
- exact source-owned removal works;
- prepared/toggle selections survive hydration;
- initial and post-birth Event facts are complete; and
- no active caller imports the old character runtime.

### 11.2 Generic item materialization may be deleted only when

- every retained baseline/variant ID has a disposition and direct proof;
- starting holdings/loadouts/possessions are direct;
- behavior-bearing items preserve real mechanics;
- Oil Barrel uses the current direct transition;
- world/inventory/equipment/container placement is exact; and
- visual rows are preserved outside mechanics.

### 11.3 Generic creature/scenario construction may be deleted only when

- every maintained monster/scenario is direct;
- exact accepted catalog/setup counts are restored or explicitly rejected by
  the human;
- current Game/world chronology and cleanup remain; and
- no caller resolves a declaration/recipe or bootstraps content.

### 11.4 Generic behavior closure may be deleted only when

- all action/condition/reaction/spell/trait/feat/class-feature/spatial rows are
  classified;
- live admission uses only direct semantic IDs;
- every remaining decorator/population consumer has migrated;
- source-owned cleanup and event behavior are preserved; and
- frontend binding coverage is complete.

### 11.5 Backend presentation ownership may be deleted only when

- both frozen binding sets have a row-level reconciliation;
- Python-only crosswalks are frozen;
- every retained semantic ID has an explicit binding disposition;
- engine Events carry semantic/mechanical facts sufficient for later Pygame;
  and
- mechanics do not import the client binding data.

## 12. Risks and stop conditions

Stop the relevant cut rather than inventing a bridge when:

1. a retained row has no direct semantic ID or its current/accepted mechanics
   disagree;
2. an item is behavior-bearing and its real behavior is not yet direct;
3. removal receipts cannot name exact still-owned component state;
4. a progression fact would require the reducer/renderer to import authored
   definitions to understand the result;
5. a scenario count or setup row disappears without explicit disposition;
6. a binding exists only in Python and has not been frozen;
7. deleting a module would leave a hidden transitive importer;
8. a proposed fix requires a late import, `TYPE_CHECKING`, `getattr`, type
   switch, compatibility alias, dual write, or global registry;
9. a content function begins owning Entity/Game/Event/condition lifecycle; or
10. a product decision about third-party packs or persistence storage becomes
    necessary.

The response to a stop condition is a bounded evidence/plan amendment and
human decision where required, not a facade.

## 13. Definition of done

Broader content recovery is complete when all of the following are true:

- all retained current/accepted/July authored rows have explicit dispositions;
- direct content covers the complete reconciled item, origin, progression,
  premade, monster, scenario, and behavior inventories;
- every content path uses the current Entity/Game/world/spatial/event owners;
- initial construction is atomic and post-birth progression is exactly
  reversible;
- all four premades and the full maintained scenario catalog run in-process;
- the future Pygame caller can select direct authored content and consume
  renderer-neutral Event/item/entity/world state without a server;
- visual bindings are preserved but owned outside engine mechanics;
- `dnd/content_system`, generic `dnd/core/content`, `ContentRef`, recipes,
  registries, pack/runtime bootstrap, and generic materializers are gone;
- no compatibility facade, dual write, fallback path, manager/service/
  controller, OOP content hierarchy, callback rollback chain, late import,
  circularity, reflection, server dependency, or renderer dependency remains;
- gameplay, progression, items, monsters, scenarios, world initialization,
  events, subjective projection, architecture, and fresh-import lanes pass;
  and
- independent correctness, anti-slop, and anti-OOP reviewers accept the exact
  final candidate.

## 14. Review record

The substantive candidate ending at SHA-256
`e91cee3f452dd5520aa0de49549f066d3fca9560d4fcc25f0b254fa74b848cbe`
received three independent exact-byte approvals:

- correctness/completeness: **APPROVE** — no remaining count, sequencing,
  scope, authority, capability, or copy-risk error;
- anti-slop: **APPROVE** — no renamed cross-domain registry/materializer,
  standalone semantic layer, proof program for out-of-scope missing SRD rows,
  or excessive migration abstraction; and
- anti-OOP/ECS/import-DAG: **APPROVE** — dependency-leaf cross-boundary IDs,
  family-atomic behavior cuts, Entity-owned progression data, stateless systems,
  and no manager/service/callback/reflection/cycle workaround or second domain
  ontology.

Those reviews followed three independent documentation-only audits of the
current content tree, historical/accepted/broken evidence, and live proof/
dependency health. The status and review record above are metadata only and do
not alter the approved substantive plan.
