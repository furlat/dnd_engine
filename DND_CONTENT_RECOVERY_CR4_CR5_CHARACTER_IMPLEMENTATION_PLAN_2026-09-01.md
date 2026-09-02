# CR-4/CR-5 direct character recovery implementation plan

Date: 2026-09-01  
Status: `ACCEPTED_FOR_CHECKPOINTED_IMPLEMENTATION`

## 1. Outcome

This plan performs the character half of the broader content recovery as one
coherent hard cut:

- **CR-4:** direct, reversible origin and class progression over the current
  Entity/component owners; and
- **CR-5:** one direct custom-character construction path used unchanged by
  all four maintained premades.

The result is plain authored character data, cold direct definitions,
stateless procedural composition, Entity-owned semantic progression state,
typed data-only runtime receipts, and ordinary concrete Event facts. It removes
the generic framework from the migrated character closure; it does not claim
to delete unrelated legacy content families before their owning later cuts.

CR-4 and CR-5 are planned together because neither is an honest accepted
boundary alone. CR-4 needs a real initial-construction consumer to prove that
initial levels are part of one unpublished aggregate. CR-5 needs CR-4's exact
reversible owner operations rather than a second special premade materializer.

This plan does **not** authorize CR-6 monsters, CR-7 scenarios, CR-8 renderer
bindings, CR-9 residual behavior recovery, server/SDK/transport work, Pygame,
or source-content expansion. One classed monster is only a CR-4 proof that the
level system composes over an ordinary Entity; it does not migrate monster
construction.

## 2. Governing authority and starting checkpoint

| Authority | Frozen identity |
|---|---|
| Checkout HEAD | `ab56a24bf77fc79251e6505718119c38c4f32c8f` |
| Master recovery plan | `3e6a38a534331f0cdf92127fe5d9b765bf7e81a7d44baee08876bfd1613bec7b` |
| CR-0 completion ledger | `b04eb0ed05d8e8d17a3c2136f9454aa9d08c22712c0ed63da551832eec1f09ef` |
| Direct-item completion ledger | `45b2f4e1ed14cecfdbc3a1ef22994df0ed55931888e22697fdfc99783d91a2f2` |
| Primitive behavior-fact sequence amendment | `8300f661bfc629de52f4aa3316ab935d9129d20dae549510277c0c1a9bd5d0de` |
| Primitive behavior-fact implementation ledger | `0f7e3a6271f8b7a5fe7528b48a8a85ad8af6d28fd3e9630e9d6c28c60c6b2817` |
| `AGENTS.md` | `296ce0a99c52fab93261a15e193258b928c0b56c161b91ef8e412f5d27897668` |
| `HOW_TO_TEST.MD` | `96ba573eb50504f9e2c9c8676acc2f352ae198466d79f46e75c57d3f29995013` |
| Behavioral/value evidence only | accepted checkpoint `513dd97` |

The starting worktree is clean. The inherited maintained union is the exact
933-node direct-item completion union, normalized SHA-256
`969416b9c090911d88eba558d532c92c6eae9614992ba758ea64aac27cbac5d8`.
Slice 0 must rederive this rather than trusting prose.

The current branch is implementation authority. Commit `513dd97` is evidence
for definitions, values, outcomes, and test scenarios only. Its later
`dnd/entities` split, `EntityTransform`/`Undo` closure graph, reflective access,
and residual generic materialization are explicitly rejected.

## 3. Exact capability boundary

Slice 0 must freeze the exact rows and successor proofs before production work.
The bounded target is:

### 3.1 Origins

- 9 species;
- 4 species variants;
- 2 backgrounds;
- every authored origin choice currently reconciled by CR-0;
- all 18 mechanical origin feature families named by the master plan; and
- all reconciled origin trait rows, including data-only traits that share one
  mechanic family.

The ledger must distinguish authored definition rows from mechanics families.
The currently observed 42 trait rows must not be mislabeled as 42 independent
mechanics, and the master plan's 18 mechanics must not be used to omit cold
trait definitions.

Required mechanics include total-level-dependent origin effects, Dragonborn
ancestry/breath behavior, High Elf innate spellcasting, Dwarf toughness,
Halfling and Half-Orc behavior, proficiencies, senses, languages, size, speed,
resistances/immunities, and exact structural/body facts represented by current
or accepted evidence.

### 3.2 Class progression

- Fighter / Champion, levels 1 through 20;
- Barbarian / Berserker, levels 1 through 20;
- Sorcerer / Draconic, levels 1 through 20;
- every authored choice vocabulary, ASI/feat alternative, multiclass
  prerequisite, and structural feature on those rows;
- single-class and multiclass semantics;
- direct add-level and remove-last-level;
- proficiency bonus, hit dice/hit points, features, actions, handlers,
  resources and recovery, formulas, attack multiplicity, spell sources,
  known spells, source-keyed prepared spells, slot capacity, affinities, and
  replacement rules;
- total-level origin reconciliation after level addition/removal; and
- silent hydration that rebuilds runtime handles from semantic selections.

### 3.3 Character authoring

- one custom direct character input;
- one neutral player-character body path;
- background/class starting loadouts through the already accepted direct item
  builders and `ItemLoadoutEntry` values;
- at least one nonempty prepared-spell source row;
- at least one supported enabled feature toggle, one supported disabled state,
  and one rejected unsupported toggle; and
- the four maintained premades:
  - `hero.barbarian_l5_berserker_torch`;
  - `hero.fighter_l5_shield_torch`;
  - `hero.sorcerer_l5_standard_torch`;
  - `hero.fighter_2_sorcerer_3_spellblade`.

All four premades are ordinary frozen character-build values consumed by the
same public function as a custom build. They receive no private factory,
subclass, override, post-construction patch, or special Entity constructor.

### 3.4 Explicitly deferred

- general monster identities and construction (CR-6);
- scenario declarations and direct deployment (CR-7). CR-4/CR-5 removes only
  the obsolete persistence-snapshot character branch from the current
  assembler so it no longer imports the old character materializer; it does
  not translate deployment revisions into direct builds;
- appearance assets, sprite layers, portraits, icons, wardrobe resolution, and
  renderer bindings (CR-8);
- server-side character revisions, editable plans, schema digests, deployment
  records, persistence APIs, and live Entity serialization. The existing
  `dnd/core/content/durable_characters.py` and
  `dnd/core/content/character_deployment.py` remain a quarantined deferred DTO
  island until CR-7; CR-4/CR-5 adds no consumer, adapter, or direct-gameplay
  import of either module; and
- missing SRD content or new classes, subclasses, species, backgrounds,
  spells, feats, and toggles.

## 4. Architectural laws

### 4.1 ECS ownership

Entity remains a data structure and system composer. The progression system is
a group of stateless functions. Existing blocks remain the sole owners of
their mutations and cleanup operations:

- `AbilityScores`, `SkillSet`, `SavingThrowSet`, and
  `CreatureProficiencies` own their source contributions;
- `Health` owns hit dice and hit-point consequences;
- `ActionEconomy` owns resources, recoveries, slots, and attack multiplicity;
- `SpellcastingBlock` owns casting sources, learned spells, and affinities;
- `Equipment` owns armor-class formulas;
- `Senses` owns sense contributions;
- Entity owns its registered actions/handlers, size sources, origin
  capabilities, semantic character ledger, and receipt store; and
- specific actions/conditions/effects own any runtime children they create.

Content functions select and sequence these owner operations. They do not
become component owners.

### 4.2 Import DAG

The intended dependency direction is:

```text
dnd/types/abilities + dnd/types/character_progression
                    |
                    v
core / blocks / Entity / concrete mechanics
                    |
                    v
dnd/content/characters cold definitions
                    |
                    v
dnd/content/characters procedural composition + builds
                    |
                    v
scenario/application callers
```

Core, blocks, Entity, and Events may import dependency-leaf value types. They
must not import `dnd.content`. Cold definitions may import leaf values but not
Entity or live blocks. Composition modules may import definitions plus concrete
owners. There are no local/late imports, `TYPE_CHECKING` exceptions, circular
edges, `getattr`, `isinstance` dispatch, or reflection-based adapters.

Existing dependency-neutral calculations in `dnd/core/progression.py` remain
the one authority for caster progression, proficiency, point buy, and spell
slots. This cut must not duplicate them in a new content or types module.
`CHARACTER_RULESET_SCHEMA_VERSION` and `character_ruleset_digest` are generic
revision-contract residue, not progression rules; Slice 6 removes them with
their obsolete callers/tests.

### 4.3 Direct semantic values

Introduce only the dependency-leaf values required below current mechanics:

- `AbilityName`, `SkillName`, and `SavingThrowName` in
  `dnd/types/abilities.py`;
- species, variant, background, class, subclass, origin/class choices,
  applied origin state, applied class-level state, and supported feature-toggle
  identities in `dnd/types/character_progression.py`; and
- `PreparedSpellSelection(source_id, spell_ids)` and
  `FeatureToggleSelection(feature_id, enabled)` in that same semantic leaf;
- `RitualPreparationPolicy` and `OriginCapability` in a dependency-neutral
  existing or focused leaf rather than under `dnd.core.content`; and
- closed data-only origin/Fighter/Barbarian/Sorcerer receipt rows in
  `dnd/types/character_receipts.py`, containing only their actual owner handles.

The Ability/Skill aliases currently housed in `dnd/core/events.py` and the
saving-throw alias currently housed in `dnd/blocks/saving_throws.py` must move
atomically with every active importer. Events and blocks do not remain
accidental type catalogs. Existing `Size`, `CreatureType`, `DamageType`,
equipment, spell, and progression values remain in their current leaf owners;
do not duplicate them.

CR-4 also owns the atomic migration of shared component schemas required by
its mechanics:

- `SpellcastingSource.provider_ref` becomes direct `provider_id`;
- `LearnedReactionSpellOwnership.spell_ref` becomes direct `spell_id`;
- `AttackMultiplicityGrant.provider_ref` becomes direct `provider_id`;
- spell-source ritual policy and Entity origin capability use the leaf values;
  and
- Entity birth/level fact projection reads those direct values.

Slice 0 must enumerate and mechanically migrate every active consumer and test
of those shared fields in one owner-schema cut, including current monsters and
spells that hold them. This is not monster/content migration: their existing
construction may continue, but the shared component can no longer store a
character-required `ContentRef`. Of the required owner surfaces, only creature
`Entity.content_ref` remains deferred to CR-6.

The leaves contain values and concrete receipt data, not definitions, level
tables, catalogs, builders, Entity methods, behavior classes, generic handle
languages, or resolver functions.

### 4.4 Entity-owned state

Entity directly owns:

- optional semantic species, variant, and background values;
- optional applied origin state;
- ordered applied class-level rows;
- a source-owned runtime feature contribution map
  (`feature_id -> exact source IDs`) regenerated from installed grants;
- prepared spell selections keyed by exact semantic spellcasting source as
  `(source_id, ordered spell IDs)` rows;
- feature-toggle selections as `(feature_id, enabled)` rows, with unsupported
  toggle IDs rejected by the cold definition rather than silently dropped;
- the character-body semantic ID needed by the character birth fact; and
- private, excluded, ephemeral origin/level receipt rows keyed by semantic
  step identity.

The current `ContentRef` character fields and opaque tuple schemas are removed
in the same cut. Creature `content_ref` is not broadened or migrated here; it
remains CR-6 debt. A character must not carry both a direct character-body
identity and a creature `ContentRef`. Birth-fact projection uses the direct
character-body ID for characters and the current creature identity for
unmigrated creatures. This is a disjoint staged boundary, not a dual write.

Event `feature_ids` are a sorted projection of currently nonempty feature
source sets. They are not a second durable feature tuple beside origin/level
selections. Receipts name the exact source contribution so removal cannot erase
a sibling provider of the same feature.

Entity receives no `add_level`, `remove_level`, materialization, validation, or
rollback methods. Small source-contribution, receipt-store, and birth-fact
projection helpers are allowed only when they contain no progression rules.

### 4.5 Cold definitions and resolution

Definitions are frozen dataclasses plus read-only maps/tuples. Origins and
classes remain separate authored domains. Level rows contain semantic grant
IDs and choice requirements—not factories, callbacks, `ContentRef`s, Python
paths, runtime UUIDs, or component instances.

Resolution is pure:

1. validate direct IDs and choices against cold definitions;
2. validate append-only level order, subclass timing, total-level cap,
   multiclass policy, prepared spells, toggles, and loadouts;
3. calculate the applied semantic origin/level rows using the existing shared
   progression rules; and
4. return frozen resolved character data without mutating or constructing an
   Entity, registering a block, publishing an Event, or creating an item.

A small domain-local map from a semantic grant ID to a concrete procedural
installer is allowed. It is not stored in definitions or receipts and cannot
be a generic cross-domain registry. A direct `match` is equally acceptable.
There is no operation list, transform object, command hierarchy, resolver
service, or callable payload in resolved data.

### 4.6 Typed receipts and cleanup

Receipts are frozen data that name exactly what one grant installed. The
receipt schema is closed and concrete for the four actual grant families. Its
fields name real owner handles directly: for example an ability plus modifier
UUID, a proficiency subject plus source UUID, a hit-die UUID, spell-source or
slot-contribution UUID, action/handler UUID, resource name plus contribution
UUID, formula UUID, feature ID plus source UUID, or exact replacement state.
It never encodes an extensible `(surface, kind, target, id)` record and there is
no generic receipt interpreter. Receipts never contain:

- callbacks, closures, `Undo` objects, commands, context managers, or bound
  methods;
- Entity, block, action, condition, or other live object references;
- `ContentRef`, registry/runtime context, provider declarations, factory
  paths, or package digests;
- a global block UUID that must be resolved through `BaseBlock` merely to find
  a component already owned by the Entity; or
- a semantic condition name that triggers a global Entity scan.

Each semantic grant has an explicit procedural cleanup function consuming its
concrete receipt row. That function obtains the known surface from the same
Entity and invokes the owner's existing removal operation in reverse
application order. Tiny shared loops over identical concrete handle fields are
allowed; a dispatch-by-handle-kind engine is not. Repeated or out-of-order
cleanup must fail clearly; it must not silently search for something resembling
the receipt.

Active runtime children are not flattened into character receipts. Rage,
Frenzy, Metamagic, Dragon Wings, auras, and similar behaviors must have their
specific action/condition/effect owner retain exact child ownership and clean
those children before its structural grant is removed. If a current behavior
lacks such an owner edge, repair that concrete family locally and record the
exact child handle. Do not add a generic condition sweeper, lifecycle manager,
global receipt lookup, Entity scan, or `transient_condition_refs_to_remove`.

Before Slice 2, the Slice 0 ledger must inventory every such eventful child
cleanup and establish its chronology through the **existing** Event/sub-event
machinery: direct semantic cause, parent identity, preparation/effect/completion
order, and the point after which rollback is no longer lawful. The level change
must neither silently delete a committed condition nor leave committed child
removal facts whose parent level change failed. If existing causal seams cannot
express that sequence without a new lifecycle path, implementation stops for a
narrow plan amendment.

Replacement mechanics such as Frenzy replacing Rage or Sorcerer spell
replacement store the exact replaced semantic/contribution data in a typed
feature-specific receipt field and restore it explicitly. They do not capture
an undo closure.

### 4.7 Behavior identity prerequisite

Any origin/class action, handler, condition, reaction, or spell admitted by
this cut must carry the already established immutable `BehaviorBinding`
primitive directly and must not call the installed content runtime. To preserve
the accepted primitive-behavior and direct-item bytes, this cut narrowly
retains the value class in `dnd.core.content.runtime` as a temporary leaf
exception. Character code may import **only** `BehaviorBinding` from that
module. It may not import or call `bind_runtime_behavior_child`, any admission
gateway, provider lookup, declaration installer, or content runtime. Slice 0
freezes the exact import allowlist. Moving the shared primitive for every
domain is CR-9 work unless a proven import cycle forces a separate amendment.

Slice 0 must derive the complete behavior closure from each migrated grant to
every behavior it constructs or can activate, including child
conditions/effects and replacement paths. That exact closure is the bounded
CR-2C prerequisite. It removes only exact character-required families frozen
in Slice 0 and preserves the already accepted direct-item behavior bytes. For
each family in that closure, the same slice that constructs/propagates direct
primitive binding must remove its legacy declaration/decorator/provider
admission path and migrate all active callers. The shared gateway and unrelated
unmigrated behavior declarations remain until CR-9; character code simply no
longer reaches them.

Sorcerer spell entitlements are semantic references to already existing direct
spell behaviors. They do not automatically pull the whole spell catalog into
CR-2C. Slice 0 must classify each entitled spell as already directly admissible
or as an exact character-required behavior family. If that closure expands
into a large unrelated spell-domain migration, the stop condition fires before
production work.

There is no new behavior catalog, resolver, global switch, fallback, or second
admission path. If completing a character family would require migrating a
large unrelated behavior domain, stop and amend this plan rather than widening
scope implicitly.

### 4.8 Progression operations and causal facts

The public post-birth operations are ordinary functions:

- `add_class_level(entity, selection)`; and
- `remove_last_class_level(entity)`.

Addition performs pure validation first, applies concrete owner operations,
stores the semantic row and receipt, reconciles total-level origin effects,
and then publishes one concrete `EntityLevelAddedEvent` describing committed
progression state. Removal is last-in-first-out: clean the exact receipt,
remove the semantic row, reconcile origin effects, and publish one concrete
`EntityLevelRemovedEvent` describing the resulting committed progression
state, subject to the eventful-child chronology frozen in Slice 0.

The two level events are proper `Event` subclasses and receive two explicit
`EventType` members. They share one narrow typed level-fact base (or one narrow
shared progression-fact value) containing only facts needed to observe and
replay progression: entity, previous/new total, applied/removed step, resulting
class totals, origin/level selections, source-keyed prepared spells,
enabled/disabled toggles, and terminal progression-derived mechanics that
actually changed. They must not copy the full `EntityCreatedEvent` schema into
both subclasses as `513dd97` did. There is no generic event view, reducer
switch, `operation` envelope, event clone, callback completion chain, or
generic event-driven mutation. Events report what the owners committed.

If addition publication fails, the same direct procedural owners remove the
new step and restore the exact prior state without publishing a compensating
fact. If removal publication can fail before its causal boundary commits, the
owners must restore the same already-observable runtime identities and values,
not merely equivalent new objects: action UUID/order; handler UUID, enabled
state, and indexes; contribution/source UUIDs; resource current/maximum and
recovery state; spell ownership; feature sources; receipt keys; and global
registry membership. Family-specific stable IDs and plain local restoration
data may be used. There is no generic serializer/snapshot, stored live object,
closure, command, callback, or `Undo` graph. Hydration, which may legitimately
recreate receipts/owners from semantic state, is a different operation and is
never used to excuse changed identity during failed removal.

If the existing Event/sub-event seam makes such rollback impossible after an
active child emitted committed removal facts, Slice 0 must choose the valid
earlier failure boundary or stop for amendment. The plan does not authorize
rewinding Event history or silently suppressing causal child facts.

The valid existing publication seam is `EventQueue.publish_completed_fact`,
not an `EFFECT -> COMPLETION` phase walk. Declaration and execution are pure
unregistered proposals evaluated through `EventQueue.preflight`. After
addition (or removal with no eventful active child) mutates owners, one
unregistered terminal `COMPLETION` value runs pre-completion work before it is
stored; failure therefore leaves no level fact and the direct owners can
restore prior state. Removal with an eventful active child first publishes its
accepted `EXECUTION` parent, then commits the exact child-removal graph. That
child commit is the irreversible causal boundary: subsequent owner operations
are prevalidated/no-fail, and a later observation-system exception is an
engine failure over already-committed facts, never a rollback request. Level
operations publish no `EFFECT` version and introduce no new Event lifecycle
API.

Initial levels use the same internal resolution/application laws while the
Entity is unpublished, but they do not call the public post-birth API and do
not publish level facts. They are present only in the single existing
`EntityCreatedEvent`. Hydration likewise rebuilds ephemeral receipts silently
on an unpublished Entity from semantic save values; it does not replay birth
or level Events.

### 4.9 Direct build path

Use one small frozen authored input and one frozen resolved value. The authored
input contains only:

- character body ID, name, and direct body configuration values;
- point-buy/base ability scores, the exact flexible origin bonuses, and other
  ordinary body selections;
- origin selections;
- ordered class-level selections;
- direct `ItemLoadoutEntry` rows;
- prepared spell selections as exact source-keyed ordered rows;
- feature-toggle selections retaining both feature ID and enabled state, with
  explicit cold support/unsupported disposition; and
- the already authored mechanical appearance values required by current
  Entity construction, without asset paths or a runtime appearance resolver.

The public boundary is one procedural `create_character(build, ...)` function:

1. resolve the whole build without Entity mutation;
2. create one provisional neutral current `Entity`;
3. apply body, intrinsic standard actions, origin, ordered initial levels,
   prepared/toggle state, and direct items to that unpublished aggregate;
4. on any failure, clean exact installed owners and discard the provisional
   aggregate through the existing unpublished cleanup seam; and
5. call `Entity.compose_entity` exactly once, producing one birth fact.

`create_premade_character(premade_id, ...)` may be a thin lookup of a frozen
build followed immediately by `create_character`. It may not alter, patch, or
recompose the result.

Do not create `CharacterBuildDraft`, revision objects, creation plans, schema
digests, content-set hashes, leases, repositories, deployment DTOs, generic
materializers, or a universal content ID wrapper. Plain saveable selections
are enough for the future two-character Pygame application.

### 4.10 Appearance boundary

CR-5 must preserve the exact current and accepted appearance values for the
four premades and origin choices as read-only CR-8 evidence. It may copy the
resolved mechanical `AppearanceConfig` values into direct character build
definitions so construction no longer calls the legacy `ContentRef` resolver.

It must not delete the source/binding evidence, install asset paths in the
engine, create a renderer catalog, or introduce a new appearance service. The
Slice 0 ledger must map every migrated appearance row to (a) the direct plain
value used now and (b) the frozen CR-8 evidence row retained for later external
binding. Runtime legacy appearance resolvers may be deleted only after this
mapping is exact and all active callers are migrated.

## 5. Intended module ownership

Slice 0 freezes the exact file manifest. The intended shape is deliberately
small and domain-aligned:

| Area | Responsibility |
|---|---|
| `dnd/types/abilities.py` | dependency-leaf ability/skill/save names |
| `dnd/types/character_progression.py` | semantic origin/level/prepared/toggle selections and applied rows |
| `dnd/types/character_receipts.py` | closed data-only origin/Fighter/Barbarian/Sorcerer owner-handle rows; no generic handle language |
| `dnd/content/characters/origin_definitions.py` | cold species/variant/background/origin rows |
| `dnd/content/characters/class_definitions.py` | cold Fighter, Barbarian, Sorcerer level rows and choices |
| `dnd/content/characters/origin_grants.py` | direct origin installers/reconciliation/cleanup |
| `dnd/content/characters/fighter_grants.py` | direct Fighter/Champion installers and cleanup |
| `dnd/content/characters/barbarian_grants.py` | direct Barbarian/Berserker installers and cleanup |
| `dnd/content/characters/sorcerer_grants.py` | direct Sorcerer/Draconic installers and cleanup |
| `dnd/content/characters/progression.py` | stateless add/remove/hydrate orchestration |
| `dnd/content/characters/builds.py` | pure resolution and single direct create path |
| `dnd/content/characters/premades.py` | four frozen ordinary build values |

These are ownership boundaries, not mandatory empty wrappers. Slice 0 may
co-locate genuinely short adjacent modules or keep concrete mechanics in their
existing `dnd/origins`/`dnd/classes` files when that produces a cleaner DAG.
It may not introduce additional layers named manager, service, controller,
repository, runtime, registry, gateway, adapter, transaction, command, or
materializer. No file should become a generic grant language or a multi-thousand
line grab bag merely to reduce the file count.

The following current generic authorities are replacement targets, not source
architecture:

- `dnd/core/content/durable_characters.py`;
- `dnd/core/content/premade_characters.py`;
- relevant character/origin definitions under `dnd/core/content`;
- relevant character modules under `dnd/content_system`;
- `dnd/classes/content_factories.py` character factory path;
- `dnd/premade_characters.py` generic declarations; and
- the character materialization callers in scenario/content code.

`dnd/core/content/durable_characters.py` is a replacement target in the final
program but is not deleted in this cut: the explicitly deferred persistence
snapshot still imports its revision DTOs, and the accepted direct-item cut
currently owns `CharacterItemV2` there. Keeping those exact bytes until CR-7
is smaller and safer than a compatibility adapter or a second DTO module. No
new direct character code may import it. The active assembler's old
owned-character deployment branch is removed rather than adapted; CR-7 later
introduces the direct scenario/deployment boundary.

Slice 0 must enumerate the exact owning files and distinguish files deleted in
full from mixed files receiving bounded deletions. No broad package deletion is
authorized by this candidate plan.

## 6. Ordered implementation slices

Slices 1 through 7 form one unreleased CR-4/CR-5 candidate. Intermediate
checkpoints may temporarily leave unrelated old character tests red, but no
checkpoint is an accepted architecture and no migrated family may have a
runtime fallback to the old path.

### Slice 0 — preflight ledger only

No production or test edits.

Create one CR-4/CR-5 implementation ledger that freezes:

- governing hashes and clean HEAD;
- exact CR-0 origin/class/trait/premade rows and dispositions;
- the 9/4/2 origin definitions, 18 mechanic-family mapping, 3/3 class lines,
  every level row 1–20, all choice vocabularies, and all four premades;
- current/accepted value differences and the exact accepted evidence paths;
- all active production/test callers and import edges;
- the exact CR-2C behavior closure and its legacy declarations;
- every Sorcerer-entitled spell's already-direct versus CR-2C disposition and
  the exact temporary `BehaviorBinding`-only import allowlist;
- every `ContentRef`-bearing required owner schema and all active consumers;
- every receipt handle family and its legitimate current owner cleanup API;
- every runtime-child family and its exact owner edge;
- every eventful child-removal chronology through the existing parent/sub-event
  seam, including the lawful failure boundary;
- exact source-keyed prepared rows and enabled/disabled/supported toggle rows;
- current appearance rows and their CR-8 evidence disposition;
- the inherited 933-node union plus exact obsolete-node/successor mapping;
- the authorized production/test file envelope; and
- hard-cut, dependency, import-locality, and stop-condition searches.

Production work starts only after coordinator review of this ledger.

### Slice 1 — dependency leaves and semantic state substrate

- Move ability/skill/save names out of Events and migrate all active importers
  atomically.
- Add the minimal character semantic values and the four closed concrete
  receipt rows; add no generic handle vocabulary.
- Migrate spell-source provider, learned reaction spell, attack-multiplicity
  provider, ritual-policy, and origin-capability owner schemas to direct/leaf
  values with every active consumer in one atomic shared-owner change.
- Replace Entity's character `ContentRef`/tuple fields with typed semantic
  state and excluded ephemeral receipt storage.
- Replace the flat feature tuple with exact Entity-owned source contributions;
  store source-keyed prepared and enabled/disabled toggle selections.
- Add direct character-body birth identity without changing monster
  construction.
- Add the two concrete level Event subclasses and terminal fact fields.
- Preserve current birth-fact contents while changing character identities to
  direct values.

Checkpoint gates: compile/import DAG, event model construction, Entity birth
projection, no duplicate aliases, no required-owner `ContentRef`, no
core-to-content import except the exact temporary `BehaviorBinding` value
allowlist, no public progression operation yet.

### Slice 2 — origins and CR-2C origin behavior cut

- Port all cold origin definitions and choices.
- Implement direct origin application, exact typed receipts, removal, and
  total-level reconciliation.
- Migrate the exact Slice-0-frozen character origin behavior families to
  primitive direct binding without altering accepted direct-item families or
  deleting the shared gateway globally.
- Delete the corresponding origin declarations, runtime appliers, registry
  lookups, refs, and active callers in the same family cut.
- Prove every definition row and every one of the 18 mechanics families,
  including failure cleanup and active-child cleanup.

Checkpoint gates: all origin cases green through direct functions; zero active
origin materialization/runtime/declaration path; no global block or Entity scan.

### Slice 3A — Fighter / Champion levels 1–20

- Port the complete cold level/choice table.
- Implement concrete grant application/cleanup for every Fighter/Champion
  feature, proficiency, hit die, resource, recovery, formula, action/handler,
  and attack-multiplicity effect.
- Migrate its exact behavior closure and delete its legacy grant path.
- Prove sequential 1–20 application and exact 20–1 removal.

### Slice 3B — Barbarian / Berserker levels 1–20

- Port the complete cold level/choice table.
- Implement direct Rage/Frenzy and every structural grant with explicit owner
  cleanup, including replacement/restoration state.
- Migrate its exact behavior closure and delete its legacy grant path.
- Prove sequential 1–20 application/removal, active Rage/Frenzy removal, and
  no generic condition sweep.

### Slice 3C — Sorcerer / Draconic levels 1–20

- Port the complete cold level/choice/spell-entitlement table.
- Implement spell sources, known/replacement spells, slots, Metamagic,
  affinities, Draconic formulas/features, resources, and direct behavior
  ownership.
- Migrate its exact behavior closure and delete its legacy grant path.
- Prove sequential 1–20 application/removal, spell replacement/restoration,
  nonempty prepared selection, supported toggle, and active Metamagic/Draconic
  child cleanup.

Each 3A/3B/3C checkpoint is family-atomic. A migrated line cannot consult the
legacy registry while another not-yet-migrated line remains old. No public
generic fallback is added to bridge the work.

### Slice 4 — aggregate progression, causal Events, and hydration

- Complete the stateless add-level/remove-last-level boundary.
- Reconcile total character level, proficiency, origin scaling, and shared
  multiclass spell slots across the three direct lines.
- Enforce first-class versus multiclass proficiency packages and every authored
  multiclass ability prerequisite before mutation.
- Preserve ASI/feat alternatives at every authored choice level and keep
  starting-equipment ownership exclusive to initial first-class construction,
  never ordinary post-birth leveling or the classed-monster proof.
- Publish committed terminal level facts only after owner state is final.
- Implement exact identity-preserving publication-failure rollback without
  callbacks/closures, only at the causal boundary validated in Slice 0.
- Implement silent receipt hydration from semantic selections.
- Prove a mixed Fighter/Sorcerer build and one existing monster receiving and
  removing an ordinary direct class level.

Checkpoint gates: all 60 authored class rows reachable, reverse removal exact,
multiclass state exact, hydration emits no duplicate facts, classed-monster
construction remains CR-6-owned.

### Slice 5 — direct custom build and four premades

- Add the one plain authored build and pure resolver.
- Apply one resolved build to one provisional Entity and compose once.
- Install the current intrinsic standard-action set through its direct owner,
  not through a character-specific transform.
- Use accepted direct item builders/loadouts without an item adapter.
- Port exact plain appearance/body values while preserving CR-8 evidence.
- Define all four premades as ordinary build values.
- Migrate active character/premade callers. In
  `dnd/scenarios/encounter_assembler.py`, remove only the obsolete
  persistence-snapshot owned-character branch, its deployment argument, and
  its old materializer imports. Do not translate legacy revisions, add a
  temporary holder, or implement the CR-7 direct deployment path.
- Prove representative natural failures at each public construction boundary
  and zero birth/level facts on failure, without production fault hooks.

Checkpoint gates: custom + four premades exact; one birth fact each; no level
facts during birth; same public path; spellblade is not a special constructor.

### Slice 6 — generic character hard deletion and test succession

- Delete the replaced character `ContentRef`, `ContentRecipe`, definition,
  validation, materialization, build-plan, revision/digest, registry/runtime,
  and premade declaration paths from the active in-process closure.
- Retain `dnd/core/content/durable_characters.py` and
  `dnd/core/content/character_deployment.py` unchanged as the exact deferred
  persistence DTO island governed by CR-7. Their legacy revision contracts are
  excluded from the maintained CR-4/CR-5 closure; no active gameplay module
  may import them.
- Remove `CHARACTER_RULESET_SCHEMA_VERSION` and `character_ruleset_digest`
  from `dnd/core/progression.py` with their obsolete callers/tests; retain only
  actual shared progression calculations and live policy values.
- Delete or rewrite obsolete architecture/shape tests only with a node-by-node
  successor entry in the ledger.
- Preserve later CR-6/CR-7 evidence that still legitimately lives in mixed
  files without leaving a callable character compatibility facade.
- Run hard-cut and import-locality gates before final certification.

### Slice 7 — final certification and independent reviews

- Derive one sorted unique final maintained node union; record its normalized
  hash and execute it exactly.
- Run affected focused lanes, all architecture tests, compileall, diff-check,
  hard-cut searches, dependency/locality checks, caller scans, and collection
  diagnostics per `HOW_TO_TEST.MD`.
- Freeze an exact manifest of changed active production/tests and verify every
  member current and hash-exact.
- Obtain independent correctness/completeness, anti-slop, and anti-OOP/ECS-DAG
  review of the same frozen candidate.
- Any production/test repair invalidates the manifest, affected validation,
  and all three approvals.

## 7. Required proof matrix

### 7.1 Definitions and choices

- exact set equality for 9 species, 4 variants, 2 backgrounds;
- exact mapping of all reconciled trait rows to the 18 mechanic families;
- exact set equality for 3 classes, 3 subclasses, 20 levels each;
- exact choice requirements, defaults, replacement rules, and feature IDs;
- exact prepared-spell source rows and supported/unsupported plus
  enabled/disabled feature-toggle rows;
- definitions cold-import without Entity/block creation or registry mutation;
- invalid IDs, illegal variants/subclasses, missing/extra choices, invalid
  order, duplicate level, and level >20 fail before mutation.

### 7.2 Receipt/owner rollback

Exercise successful public apply/remove round trips that collectively cover
every handle family:

- numerical/constraint/advantage/critical/auto-hit/resistance modifier;
- skill/save/weapon/armor/shield/language/tool proficiency;
- hit die and hit-point consequence;
- spell source, known/reaction spell, slot capacity, and affinity;
- action and handler;
- resource maximum and recovery contribution;
- armor-class formula;
- attack multiplicity;
- condition immunity;
- sense, size, and origin capability;
- feature-specific runtime child; and
- replacement/restoration state.

Use representative **natural public-boundary failures** for origin validation,
each class family, direct build/item application, and Event publication. Do not
add production fault hooks or make tests depend on monkeypatching private helper
internals. For each failure, compare pre/post semantic state, owner
collections, Event queue, receipt store, and global live-object registries.
Prove sibling source contributions remain intact and cleanup removes only the
exact installed source. Removal-publication failure additionally proves exact
action/handler/contribution UUIDs, order/enabled state, resource current state,
spell ownership, feature sources, receipt keys, and registry membership.

### 7.3 Origins and progression

- each origin applies/removes exactly;
- Hill Dwarf/Dragonborn/other total-level scaling changes on add/remove and
  restores exactly;
- each class applies levels 1–20 sequentially and removes 20–1;
- subclass timing and choice validation;
- table-driven first-class versus multiclass proficiency packages for Fighter,
  Barbarian, and Sorcerer;
- every multiclass ability prerequisite accepted/rejected before mutation;
- ASI and feat alternatives at every authored choice level, with removal and
  hydration round trips;
- starting equipment belongs only to initial first-class construction, not
  post-birth levels, multiclass additions, or a classed monster;
- Fighter resources/formulas/extra attacks;
- Barbarian Rage/Frenzy/replacement and active-child cleanup;
- Sorcerer sources/spells/slots/Metamagic/Draconic features/replacements;
- every eventful active-child cleanup has a direct semantic cause, exact
  parent/sub-event chronology, and no orphaned/flattened/silently deleted fact;
- Fighter/Sorcerer multiclass proficiency, shared slots, spell sources, and
  reverse removal;
- add/remove publication failure restores complete state;
- hydration reconstructs exact owner state and fresh receipt data from the same
  semantic state, supports later exact removal, preserves sibling sources,
  emits no birth/level facts, and leaks no runtime residue; stable UUID5 source
  IDs are permitted and UUID inequality is not a contract;
- source-keyed prepared spells and enabled/disabled toggles round-trip through
  Entity state, hydration, and birth/level facts without cross-source leakage;
  and
- one current monster can receive/remove a direct ordinary level without
  becoming a character or using the character builder.

### 7.4 Construction and premades

- resolution has no Entity/block/item/Event side effects;
- custom character exact body/origin/levels/items/prepared/toggles;
- all four premades exact accepted mechanics and selections;
- equipment location/quantity and inventory identity through direct items;
- exactly one successful `EntityCreatedEvent`, containing terminal origin,
  levels, mechanics, selections, and item presentation state;
- zero `EntityLevelAddedEvent` during initial construction;
- representative natural failures at body/origin resolution, class
  application, item construction/equip, final validation, and birth
  publication leave no Entity/block/item/handler/Event residue; and
- premade lookup is a value lookup followed by the same public custom path.

### 7.5 Architecture and hard-cut gates

AST-backed gates, with narrow documented test-fixture exemptions only, reject:

- active character imports from generic `dnd.core.content` or
  `dnd.content_system` authorities, except the exact temporary immutable
  `BehaviorBinding`-only import frozen by Slice 0;
- character `ContentRef`, `ContentRecipe`, factory strings, pack/version/hash,
  registry/runtime/materializer/creation-plan/revision/digest vocabulary;
- `Entity.get_all_entities`, `BaseBlock.get` receipt cleanup, global receipt
  lookup, or behavior-provider lookup in the migrated closure;
- required owner fields named `provider_ref`/`spell_ref`, or non-leaf ritual
  policy/origin capability types;
- generic receipt surface/kind/target records or cleanup interpreters;
- `Undo`, `EntityTransform`, callbacks stored in receipts/resolved values,
  context-manager transactions, command objects, or generic operation lists;
- large progression/materialization methods added to Entity;
- late/local imports, `TYPE_CHECKING`, `getattr`, runtime type inspection, or
  new import cycles;
- duplicate ability/skill/save aliases or duplicate shared progression rules;
- direct plus legacy definitions/builders/admission for one migrated family;
- imports of the quarantined durable-character/deployment DTO island from the
  maintained CR-4/CR-5 gameplay closure;
- premade-specific factories or post-build patches; and
- renderer paths/assets/VFX or server/transport dependencies in character
  mechanics.

## 8. Stop conditions

Stop and return for a plan amendment if:

1. Slice 0 cannot reconcile the 9/4/2 definitions, 18 mechanics families,
   60 class rows, four premades, or exact active callers.
2. A required character behavior closure reaches a large unrelated CR-9
   family or cannot be cut without a second admission path.
3. An existing component owner lacks a precise removal operation and the only
   proposed repair is global lookup, Entity scan, live-object receipt, or
   callback/transaction machinery.
4. A runtime child has no concrete owner relationship and cannot be repaired
   locally in its own feature family.
5. Existing Event/sub-event seams cannot give eventful child cleanup a direct
   causal parent and a lawful failure boundary without orphaned committed
   facts or Event-history rewind.
6. Direct character identity would require dual-writing or aliasing creature
   `ContentRef` rather than using the disjoint character-body boundary.
7. An accepted mechanic cannot be reproduced without copying rejected
   `EntityTransform`/`Undo`, reflective access, or generic materialization.
8. Appearance rows cannot be mapped exactly while preserving their CR-8
   evidence.
9. A premade requires a special construction path rather than plain authored
   input.
10. Any active production caller remains on the old character materializer at
   the hard-cut boundary.
11. A test failure exposes a genuine rules decision not fixed by current,
    accepted, July, or source evidence.

These conditions request a narrow amendment. They do not authorize a fallback,
compatibility facade, registry, or scope expansion.

## 9. Checkpoint protocol

At each slice checkpoint the implementer stops and reports:

- exact changed production/test paths;
- focused and affected test commands/results;
- current hard-cut/dependency/locality results;
- any intentionally red successor nodes within the unreleased candidate; and
- the next bounded slice requested.

Preflight and final candidate hashes are frozen. Intermediate hashes may be
recorded for coordination but are not correctness evidence. The coordinator
inspects shared checkout bytes and authorizes only the next slice. No reset,
checkout, clean, commit, server/SDK/renderer edit, CR-6 work, or unrelated
cleanup is authorized.

Final acceptance requires all three independent reviews on identical
production/test bytes:

1. correctness/completeness and recovery evidence;
2. anti-slop/minimality and absence of replacement infrastructure; and
3. anti-OOP/ECS ownership/import-DAG integrity.

## 10. Independent plan-review record

The first exact candidate, SHA-256
`6ebbdecbf6f4bdb5df910f8fc3c17bbfb7583860226ef105ff8b82d03d4603a0`,
received three independent `CHANGES_REQUESTED`/`REJECT` verdicts. This revision
incorporates every blocking finding:

- correctness: behavior-foundation authority/scope, source-keyed prepared
  state, enabled toggle state, child-removal Event chronology, hydration
  observables, and complete multiclass/ASI/equipment proofs;
- anti-slop: concrete family receipts rather than a handle language, narrow
  level facts, public-boundary failures, removal of ruleset digests, and
  source-projected features; and
- anti-OOP/ECS-DAG: atomic shared-owner direct-ID migration, the exact temporary
  `BehaviorBinding` value exception, identity-preserving removal rollback, and
  Entity-owned feature source contributions.

The same three reviewers must reconfirm the revised bytes. Their final verdicts
and the accepted hash are appended only after all three approve.

All three reviewers approved substantive SHA-256
`8803452cb39d4712f06ada065a506e8227497c3812b9a6d62b5b74c382e20431`:

| Review | Verdict | Exact conclusion |
|---|---|---|
| correctness/completeness | `APPROVE` | all five blockers resolved; Slice 0 owns exact closure/chronology/schema/caller freeze |
| anti-slop/minimality | `APPROVE` | no handle algebra, cloned Event schema, fault-hook testing, duplicated feature ledger, or replacement infrastructure |
| anti-OOP/ECS/import-DAG | `APPROVE` | direct owner schemas, source contributions, identity-preserving rollback, and the narrow binding exception preserve ECS/DAG ownership |

The status authorizes Slice 0 documentation/inventory only. Production and
test implementation still requires coordinator acceptance of the Slice 0
ledger.

## 11. Candidate decision

The plan was narrowly amended during Slice 0 after exact caller/DAG review:

- retain the existing durable-character/deployment revision DTOs as a
  quarantined CR-7 island instead of deleting or adapting them;
- remove, rather than translate, the obsolete owned-character persistence
  branch from the maintained encounter assembler; and
- use the existing completion-fact publication seam so no stored level
  `EFFECT` precedes fallible pre-completion work.

The amended plan at substantive SHA-256
`3ace123c57bb273aa2bb1c50933f8e82bcb9390de614254359dbc9469e2aba7e`
and the Slice-0 ledger at substantive SHA-256
`71cfedd09319f7c6e01c284005c028fef2eaa2cb34ebdfff8e1d0984eda7eaa5`
were independently approved for correctness/completeness,
anti-slop/minimality, and anti-OOP/ECS/import-DAG integrity. The coordinator
accepts Slice 0 and authorizes Slice 1 only; later slices remain checkpoint
gated.
