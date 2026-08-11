# Unified Content System and Persistent Characters

**Status:** Public content identity/transport, persistent-character deployment,
and atomic terminal settlement implemented; measured SRD expansion and neutral
ownership of the remaining cold evaluation metadata remain

**Date:** 2026-07-25

**Scope:** Characters, item and creature factories, installed content packs,
player-facing content metadata, persistent holdings, and the engine/content
event boundary.

## Implementation checkpoint — 2026-07-25

The current implementation establishes the architecture without claiming that
the full SRD/content program is complete:

- Dependency-neutral identities, recipes, descriptors, provenance,
  registrations, immutable registries, pack manifests, startup loading, and
  content-set identity are implemented.
- Built-in content and administrator-installed external packs use the same
  frozen registry. External Python packs are validated and imported only at a
  provably cold startup boundary; they are trusted deployment code, not a
  Python security sandbox or a hot-reload mechanism.
- The supported item, creature, and environment roots have canonical
  factory-backed recipes and migration ledgers. Item/environment map-editor
  and scenario construction, premades, persistent-character composition, and
  canonical creature materialization use exact recipes. The former evaluation
  runtime assembler has been deleted: rating and promotion workers now consume
  exact roster recipes through the canonical encounter assembler. Historical
  `ActorBlueprint` rows remain cold catalog/rating inputs only until that
  metadata receives a neutral owner.
- The player-facing manifest/catalog, runtime behavior attribution,
  presentation-cue `ContentRef` attribution, exact spell catalog references,
  and generated TypeScript models are implemented. Spell catalog rows come
  from one explicit typed authored inventory; runtime construction, source
  inspection, regular-expression extraction, name normalization, and alias
  joins are not metadata authorities.
- Every active player-visible condition leaf has an exact authored
  declaration, and persistent entity/tile condition rows carry the required
  `ContentRef`. `semantic_key` remains a mechanics/diagnostic fact and is not a
  presentation join.
- Every concrete action has one explicit authored definition (apart from the
  three intentionally abstract composition mechanisms). Player action and
  toggleable-handler affordances carry one required fail-closed authored
  attribution. Execution tokens and AI semantic keys remain separate from
  catalog identity.
- Controlled item rows carry exact definition and recipe/preset identity.
  Visible equipment and floor objects carry only an authenticated,
  mechanics-free safe-presentation reference, preserving subjective privacy.
- The authored NeuroClient item-visual inventory contains 205 measured rows,
  all backed by exact shared mechanical factories and pack-owned visual recipe
  presets. The former 43-row gap was closed with 16 mechanical roots; recolors
  remain recipes rather than duplicate item definitions.
- Persistent character definition/holdings revisions, leases, deterministic
  reconstruction, deployment linkage, exact reads, game history, and atomic
  terminal holdings settlement are implemented. Broader post-game reward and
  economy design remains future content/product work rather than a missing
  persistence boundary.
- The currently public spell set has one authored identity and metadata
  inventory. Full
  SRD 5.1 item, creature, and spell expansion remains ledger-driven content
  work; source rows marked missing, partial, or blocked are not being reported
  as complete.

The remaining work below is intentionally split into bounded phases so content
authoring can resume without reopening the registry, transport, or persistence
architecture.

## 1. Executive decision

Build one engine-owned `ContentSystem` with:

1. Dependency-neutral content identities, recipes, descriptors, and
   registration protocols.
2. Trusted Python content packs discovered from a dedicated
   `content_packs/` directory at process startup.
3. Pure marker decorators for declaring content beside its implementation.
4. Immutable registries assembled and frozen before profiles, games, workers,
   replays, or AI controllers are opened.
5. Factory-backed content for items and creatures first.
6. Descriptor-backed content for actions, conditions, spells, reactions,
   traits, feats, class features, and environment interactions.
7. A closed engine event kernel. Content packs may compose mechanics from the
   kernel but may not silently extend reducer-critical wire event types.
8. A dynamic, server-authored content catalog for NeuroClient so icons,
   ordering, descriptions, visual routing, and grouping do not depend on
   display-name heuristics or manually duplicated lists.
9. Persistent characters split into immutable structural revisions, immutable
   holdings revisions, and ephemeral encounter state.
10. Atomic terminal settlement that advances holdings only after a clean,
    replay-backed game end.
11. An exact SRD 5.1 CC-BY-4.0 source ledger and dependency graph used to
    preserve current implementations and drive complete item/creature coverage.
12. Explicit provenance separating faithful SRD 5.1 content, reviewed
    adaptations from later open SRDs, NeuroDragon-original content, other
    licensed/open packs, and fixtures/internal mechanics.

The content system is a registry and metadata service, not a CRUD database for
arbitrary Python code. External packs are trusted, deployment-installed code.
They are never uploaded or executed through a public HTTP endpoint.

## 2. Goals

- Let an item or creature be declared in the module that implements it.
- Let an external pack add content without editing a central switch or union.
- Preserve strict dependency direction and remove circular/late-import hacks.
- Give every durable or player-visible content object a stable namespaced
  identity and version.
- Reconstruct character structure and possessions without serializing live
  `Entity`, `BaseItem`, `BaseCondition`, `BaseAction`, handler, or callback
  objects.
- Make installed content identity explicit across standalone, gateway, worker,
  replay, SDK, AI-provider, and frontend boundaries.
- Replace current source-code inspection, class-path fallback identities, and
  frontend name normalization with authored metadata.
- Keep replay files portable and content-addressed while storing profile and
  hosted history in SQL.
- Preserve every currently implemented item, creature, spell, action,
  condition, trait, and handler behavior through a checked-in keyed migration
  inventory and deterministic lifecycle probes.
- Complete the chosen SRD 5.1 item and creature scope, including transitive
  spell/trait/action dependencies, without silently approximating missing
  mechanics.
- Finish each migration phase with one canonical path and delete the replaced
  path in the same phase.

## 3. Non-goals for this tranche

- A full character creator UI.
- Arbitrary client-authored Python or factory parameter JSON.
- Hot-reloading packs while games are active.
- Downloading or installing dependencies automatically.
- Marketplace, trading, shared stash, crafting, or cross-character item
  transfer.
- Persistent HP, position, initiative, action economy, temporary conditions,
  or other encounter state.
- Full campaign progression, XP balancing, level-up UI, or permanent injury
  rules.
- A public pack upload/enable/disable administration API.
- Allowing a content pack to add a new reducer-critical event family without
  an engine protocol release.
- Migrating every spell, action, and condition factory in the first registry
  phase merely for symmetry.
- Treating SRD 5.2/5.2.1 mechanics as implicit upgrades to the SRD 5.1
  ruleset.
- Copying or labeling content from proprietary books that is not covered by an
  applicable license.

## 4. Current-state findings

### 4.1 Characters

The hosted directory already persists:

- `CharacterRecord`: character UUID, owning principal, display name, one
  `preset_configuration_id`, lifecycle status, timestamps, and row version.
- `CharacterDeploymentRecord`: character, game, membership, and runtime entity
  UUID.

This is a useful identity/deployment skeleton, but it is not yet authoritative
construction data. The client separately supplies
`hero_configuration_id`. The gateway compares the two strings and forwards the
ordinary game-creation request. The worker then reconstructs the hero from the
current mutable catalog.

Consequences:

- The stored character does not construct the runtime entity.
- Catalog changes under the same preset ID silently alter a character.
- The character display name is not the authoritative actor name.
- The creation manifest does not pin the character definition.

The current workspace directory DB has six character records and fifteen
deployments. Every character uses one of the three currently supported
premades, so a deterministic hard migration is possible.

### 4.2 Items

Item construction is distributed in implementation modules, which is desirable,
but lookup is duplicated in several central or ad hoc paths:

- `dnd/items/__init__.py`: `WEAPONS`, `ARMORS`, and `SHIELDS`.
- `dnd/scenarios/evaluation/assembler.py`: item and equipment grant switches.
- `dnd/scenarios/evaluation/wardrobes.py`: `APPAREL_FACTORIES`.
- `server/mapeditor_support.py`: a separate loot-factory switch.
- Individual creature/class factories directly instantiate equipment.

`BaseItem.semantic_key` defaults to its Python class identity. That is not a
reconstruction identity: many different weapons are the same `Weapon` class,
armor variants share classes, and potion/scroll/wand variants can share the
same subclass.

`ItemPresentationState` is intentionally a renderer/replay projection. It does
not contain all mechanical factory parameters, action templates, slot policy,
stack key, potion strength, scroll spell/cast level, wand recipe, item hooks,
or durable damage. It must not become a persistence format.

The NeuroClient visual inventory is also real authored content, not disposable
renderer trivia. The 2026-07-25 audit found 205 named sub-items across 64 base
categories in `defaultItemVisualMap.json`. These include recolors and alternate
silhouettes that intentionally share mechanics. A visual ID is an asset key,
not a durable semantic identity.

Use a separate pack-owned `ContentRecipePreset` for these rows:

- Stable namespaced/versioned preset identity.
- Exact authenticated `ContentRecipe` targeting the shared factory.
- Explicit display descriptor, visual/palette key, tags, order, and provenance.
- One preset per exact recipe; no aliases with or without duplicated display
  parameters.
- No duplicate item subclasses merely to represent a color.

The first hard-cut slice owned the 20 visual identities already used by
wardrobes and premades. The complete 205-row source inventory is now
factory-backed and materialization-tested; any future authored row must either
resolve to one shared mechanical root or remain explicitly red in the item
coverage ledger, never silently disappear.

### 4.3 Creatures

Creature construction also has parallel closed paths:

- `SRD_MONSTER_SPECS` and `SRD_MONSTER_FACTORIES` are maintained separately.
- `create_srd_monster()` dispatches through the central dictionary.
- The evaluation assembler hard-codes player-class, bestiary, and SRD
  `isinstance` branches.
- `ActorBlueprint` is a closed discriminated union.
- `SideConfigurationSpec.members` is consequently closed to external actor
  families.
- AI-validation helpers wrap or directly call the same factories through
  additional paths.

Monster versus NPC is not a construction distinction. It is presentation,
deployment role, faction, controller, and catalog metadata. The canonical
factory family should be `creature` or `actor`.

### 4.4 Actions, conditions, spells, traits, and events

Items and creatures legitimately define private actions, conditions, handlers,
and traits beside their factory. Examples include:

- Potions attaching use-action templates.
- Scrolls wrapping spell actions.
- Weapon coatings applying item-specific conditions.
- Creature traits registering handlers and reaction actions.
- Spell modules defining spell actions, effect conditions, zone conditions,
  escape actions, and internal markers together.

It would be incorrect to require every private helper to be independently
persisted or globally constructible.

However, player-visible metadata is currently fragmented:

- Action and condition semantic keys may fall back to Python class paths.
- The backend spell catalog maintains manual overrides and inspects Python
  source text to infer saving throws and attack behavior.
- NeuroClient maintains manual item aliases, item-action semantic-key maps,
  condition icon aliases, environment-object name sets, fixed action ordering,
  grouped-action special cases, and name normalization.

The generated objective event contract discovers imported `Event` subclasses
and produces a closed TypeScript union. Dynamically adding arbitrary event
subclasses from installed packs would make gateway/worker/frontend protocol
identity nondeterministic and would require the frontend reducer to understand
unknown state transitions.

### 4.5 Multi-process startup

- `custom_ai` is explicitly imported; it is not discovered.
- The standalone server and gateway have distinct composition roots.
- Hosted workers are independent `uvicorn server.event_server:app` processes
  with inherited environment and working directory.
- Warm-worker readiness currently checks only that `/game/status` returns 200.
- `GameRecord.content_digest` currently contains a digest of the creation
  request rather than the exact installed content set.

Content-pack loading and content identity therefore must be shared by all
composition roots and verified during worker readiness.

### 4.6 Exact old/new coexistence audit at `b2b3930`

The committed AI managed-service hard cut is mechanically clean:

- The deleted `ai.external_agent`, embedded/subprocess/local-game service
  modules, `server.agent_protocol.service`, and
  `server.agent_runtime.{service,service_manager,subprocess_service}` have no
  remaining source imports.
- The former managed-service and simulation-start aliases are absent and their
  absence is tested.
- Native and registered-provider gameplay AI use `dnd.ai`; engine and server
  source are statically forbidden from importing the top-level `ai` package.
- Top-level `ai/` still owns Codex clients, advanced subjective-policy
  experiments, evaluation, and evidence tooling. It is isolated from the
  production server rather than being a second embedded server controller.
- `server.agent_protocol.observation_legacy` remains as an isolated old-artifact
  migration reader. Delete it only if support for reading those retained
  artifacts is deliberately dropped.

Two cleanup items remain around that cut:

1. Session/Codex and `/action/execute` commands still call
   `execute_available_action` through an older server wrapper, while native and
   registered-provider AI call the new `dnd.action_dispatch` bridge. This is
   one live dispatch bypass, not a second AI service. A dedicated red-first
   architecture/behavior regression must prove all authoritative callers use
   the same dispatcher before removing the wrapper.
2. Several AI design documents still name moved or deleted modules. Update or
   explicitly archive them; they are stale text, not executable paths.

The content side is not cleanly cut because the new content system does not
exist yet. Current live parallel paths are:

| Area | Current live paths | Required hard cut |
|---|---|---|
| Scenarios | The composed evaluation assembler and 38 direct builders in `dnd/scenarios/ai_validation_arenas.py` both construct arenas. | Move neutral arena metadata, migrate evaluation callers to composition, delete direct builders/dispatcher and their parity scaffolding. |
| Items | `WEAPONS`/`ARMORS`/`SHIELDS`, assembler grant switches, wardrobe factories, and map-editor catalogs/reverse-name dispatch all construct or identify items. | Route all callers through the frozen item registry, then delete every closed switch/map. |
| Creatures | SRD factory/spec maps, a closed actor union, and class/bestiary/SRD assembler branches coexist. | Replace with generic creature recipes and one registry materializer, then delete maps/branches. |
| Conditions | `CONDITION_MAP/create_condition` appears dead; the scenario starting-condition adapter is live and closed. | Delete the dead map with an absence test; migrate the live adapter only when a condition registration path exists. |
| Spells/actions | `ALL_SPELLS`, spell-catalog overrides/source inference, and standard-action composition are live. | Keep standard ruleset composition; replace discovery/metadata duplication in the descriptor phase. |

`legacy_recipes.py` is presently preset data over the composed scenario path,
not duplicate construction. If preset IDs remain part of the product, rename
that module to the canonical preset catalog during the scenario hard cut. If
they do not, delete the preset DTO/route branches rather than preserving a
compatibility name.

### 4.7 Current action, spell, condition, and handler accounting

There is meaningful runtime tracking today, but only spells have a reasonably
complete static public registry:

- Actions are runtime templates on `Entity.registered_actions`. There are 44
  direct `register_action` call sites across 14 engine modules. The standard
  setup installs 12 fixed templates and dynamic weapon-slot attacks; class
  features, creature traits, conditions, and spells add/remove more templates
  later.
- Usable items are a second legitimate discovery source rather than entity
  templates. At least 25 constructor sites attach `use_action_templates`, and
  inventory/adjacent objects synthesize use rows through `get_use_actions()`.
- Spell-slot, restricted-action, and target variants are derived during
  discovery. They are runtime variants of one definition, not additional
  content definitions.
- `ALL_SPELLS` contains exactly 109 public spells in level counts
  `[12, 21, 23, 16, 9, 8, 10, 4, 4, 2]`. `AegisSpark` is an
  independently authored extension, `AcidFlaskSpell` is private item behavior,
  and `TestBless` is a fixture; each needs explicit classification rather than
  accidental inclusion/exclusion by import order.
- A complete import currently reveals about 178 concrete
  `BaseCondition` subclasses: 167 public and 11 internal. There is no
  authoritative condition definition registry. Active condition instances are
  indexed by runtime UUID/source and, critically, by display name; independently
  addressable cross-pack conditions therefore need a namespaced definition
  reference rather than relying on current name lookup.
- There are 120 `EventHandler` construction sites across 22 `dnd` modules.
  Only seven explicitly set semantic identity and content kind, while the
  evaluator catalog hard-codes six independent handlers. Eleven construction
  sites are player-toggleable.
- Handler runtime lifecycle is real: `EventQueue` owns trigger/spatial/source
  indexes, blocks own local indexes, conditions retain owned handler UUIDs for
  cleanup, and dispatch observers emit opportunity/effect evidence.
- Handler content accounting is incomplete: direct item/creature/system
  handlers often fall back to processor module paths and `UNCLASSIFIED`.
  Condition-owned ordinary handlers derive an identity after construction, but
  spatial handlers do not.
- No content currently constructs native `SpatialHandler`; spatial mechanics
  use the legacy `EventHandler` compatibility branch. Duplicate admission of
  the same handler is not intrinsically rejected and can append duplicate
  indexes/invocations.

The evaluator-only subclass catalog is useful discovery evidence, not an
authoritative registry. It produces 382 rows in one clean import sequence and
398 after importing all `dnd` modules, includes bases/private/test content,
omits extensions depending on import order, and assigns Python-path fallback
keys to almost everything. The new content system must replace—not promote—
that mechanism.

### 4.8 Initial SRD 5.1 CC source-gap audit

The initial read-only comparison used the official 403-page SRD 5.1 Creative
Commons PDF as authority and extracted named source rows from the document,
not from archived repository book prose. Phase 0 must check in the extraction
rules, reviewed ledger, source digest, and corrections so these numbers become
repeatable project artifacts rather than prose estimates.

| Family | Official SRD 5.1 source rows | Current repository evidence | Initial gap/risk |
|---|---:|---|---|
| Creature/NPC stat blocks | 317 total: 201 Monsters A–Z, 95 miscellaneous creatures, 21 NPCs | 27 roots in `SRD_MONSTER_FACTORIES`/`SPECS`; exact-name Goblin and Skeleton exist outside it, for 29 named roots | 288 named roots absent from the current unified SRD roster. Existing roots still require full stat-block parity review. |
| NPC appendix | 21 | 16 current exact-name roots | Archmage, Assassin, Druid, Gladiator, and Noble are missing. |
| Weapons | 37 | 19 in the closed `WEAPONS` map; Arcane Staff is exported separately and is not an SRD-map row | 18 source weapons are missing; custom weapons must remain separately attributed. |
| Armor and shield | 12 armor suits plus 1 shield | All 13 mechanically named roots appear to exist, alongside custom apparel and Wooden Shield | Presence is promising, but recipe, cost/weight, presentation, and behavior fidelity still need row-level verification. |
| Magic items A–Z | 239 named entries in the source ledger | A small mixed subset exists in `test_items.py` and related modules; there is no authoritative magic-item registry | Do not infer completion from class names. Classify every current row and then implement dependency-complete families. |
| Spells | 319 named spells | `ALL_SPELLS` has 109 entries; the initial audit identifies Necrotic Bless as custom and 108 candidates for SRD verification | Approximately 211 SRD spells remain after exact provenance reconciliation. Required creature/item spells become typed blocking dependencies. |
| Mundane gear, tools, mounts, vehicles, trade goods | Several source tables | No unified registry | Build reviewed source rows and mark purely economic/table entries `not_applicable` only when they are not meaningful runtime roots. |

None of the current 27 SRD-roster factories should yet be labeled mechanically
`complete`: present tests establish construction and selected behavior, not
full source-stat-block parity. Conversely, unregistered Goblin, Skeleton,
Arcane Staff, gameplay content located in `test_items.py`, custom apparel, and
extension content must enter the legacy migration ledger so the SRD cleanup
does not delete them.

This audit makes full SRD completion a substantial content program, not a
single registry refactor. The foundation/hard-cut milestones remain small and
reviewable; SRD definitions then land in dependency-closed batches without
reopening the architecture.

## 5. Architectural boundaries

### 5.1 Engine kernel

The kernel owns:

- Event lifecycle and phases.
- Reducer-critical `EventType` values and event payload families.
- Entity/block/action/condition/item lifecycle mechanisms.
- Dependency-neutral enums and immutable transport-independent value objects.
- Content registration protocols and stable identity value objects.

The kernel does not import:

- Concrete items, creatures, actions, conditions, or spells.
- External pack modules.
- Server DTOs, SQL repositories, profile state, or worker services.

### 5.2 Content definitions

Content modules own:

- Concrete implementation classes and functions.
- Factory parameter models.
- Factory declarations.
- Player-facing descriptors and presentation metadata.
- Private actions, conditions, handlers, and traits needed to construct the
  content.

Content modules import only the neutral registration and engine mechanisms they
need. The content registry never imports concrete modules.

### 5.3 Composition roots

One audited startup loader is allowed to import configured external pack entry
modules dynamically. This is deliberate plugin composition, not a
function-local import used to hide a cycle.

The loader:

- Is the only production location allowed to use dynamic imports for project
  content.
- Runs before application state becomes available.
- Builds temporary registries.
- Validates the complete set.
- Publishes immutable registries only after all validation succeeds.

The static dependency test must contain a narrow, documented exception for this
single loader and continue to reject all other dynamic/function-local imports.

### 5.4 Runtime versus persistence

Runtime objects always receive fresh UUIDs and may contain callbacks, handlers,
conditions, and mutable engine state.

Persistence contains only:

- Content references and versions.
- Validated factory parameters.
- Canonical digests.
- Persistent character/item identities.
- Explicit durable mutable fields.
- Provenance and revision metadata.

No persistence model contains a callable, class object, Python module path,
live engine object, runtime registry UUID, or serialized handler.

## 6. Core content contracts

The repository already owns `dnd/core/content.py` for runtime content-kind and
handler-dispatch evidence. Atomically move that leaf module into a package;
never leave both a module and package or add an import alias:

```text
dnd/core/content/
├── __init__.py
├── identities.py
├── provenance.py
├── descriptors.py
├── recipes.py
├── registration.py
├── dependencies.py
├── inventory.py
└── pack_contracts.py
```

Move the existing runtime evidence contracts into the package, update all
imports in the same cut, delete `dnd/core/content.py`, and add an exact
import-boundary test.

The package must not import `Entity`, `BaseItem`, concrete content, or server
code.

Keep two classifications separate:

- `ContentDefinitionKind`: independently defined content such as item,
  creature, action, spell, condition, trait, or environment object.
- `RuntimeBehaviorKind`: the role of emitted runtime behavior/evidence, evolved
  from the existing `ContentKind`.

A creature is a content definition even though it is not a handler-dispatch
behavior. Conversely, a private condition handler is runtime behavior even
when it has no independently constructible factory.

### 6.1 Content identity

```text
ContentRef
├── pack_id
├── definition_kind
├── content_id
├── content_version
└── definition_contract_hash
```

Rules:

- `pack_id` and `content_id` are normalized, namespaced, and immutable.
- A `(pack_id, kind, content_id, content_version)` tuple identifies one
  immutable contract.
- Changing parameter schema or construction semantics requires a new content
  version.
- Re-registering the same identity with a different hash is a startup error.
- Display names are never identities.

### 6.2 Content recipe

```text
ContentRecipe
├── ref: ContentRef
├── parameters: canonical JSON object
└── recipe_digest
```

The JSON object is not untyped at execution time. The resolved registration
validates it through the registration's Pydantic parameter model before calling
the factory.

Dynamic pack parameter models are deliberately not added to one generated
closed TypeScript union. The catalog may expose their JSON Schema for trusted
editors, while normal gameplay clients consume already-authored recipes.

### 6.3 Content descriptor

```text
ContentDescriptor
├── ref
├── display_name
├── description
├── tags
├── visibility
├── presentation
├── ordering
└── related_content_refs
```

Presentation metadata initially supports:

- `icon_key`
- `portrait_key`
- `sprite_key`
- `visual_variant_key`
- `projectile/vfx profile`
- `audio_key`
- UI grouping
- stable sort group and sort order
- optional localization keys

Mechanics and presentation remain distinct. A descriptor may describe private
factory-owned behavior without making that behavior independently
constructible.

### 6.4 Registration declaration

A pure marker decorator attaches an immutable declaration to a function or
class. It does not mutate a process-global registry at import time.

```python
@item_factory(
    content_id="potion.healing",
    version=1,
    parameters=HealingPotionParameters,
    descriptor=...,
)
def create_healing_potion(
    context: ItemBuildContext,
    parameters: HealingPotionParameters,
) -> HealingPotion:
    ...
```

The loader scans only declarations:

- Found in modules beneath the pack's declared Python package.
- Defined in the scanned module, not merely imported into it.
- Using supported signatures and return families.

This avoids import-cache-dependent registration and makes isolated registry
tests deterministic.

### 6.5 Built-in content is a pack too

The engine's shipped content is exposed as an explicit trusted built-in pack,
for example `core.rules`, through the same declaration, registry-builder,
descriptor, recipe, and digest contracts as external packs.

The built-in pack may be imported statically by the application composition
root; it does not need to be copied under `content_packs/` or dynamically
loaded from disk. The `ContentSystem` then merges:

1. the statically declared built-in pack; and
2. validated external packs discovered by the pack manager.

There must not be a privileged second runtime lookup path for built-in items or
creatures. A built-in and an external recipe resolve through the same frozen
typed registry after bootstrap.

### 6.6 Rules-source and license provenance

The primary rules baseline is the Creative Commons release of SRD 5.1. Treat
later SRDs as separate sources, not silent errata or upgrades.

Pin the initial source record to the official Wizards of the Coast
[`SRD_CC_v5.1.pdf`](https://media.wizards.com/2023/downloads/dnd/SRD_CC_v5.1.pdf),
its computed deployment-time document digest, and CC-BY-4.0 attribution. A
future source refresh is a reviewed source-version change, not an invisible
web fetch during startup.

```text
ContentSource
├── source_id
├── title
├── source_version
├── ruleset_id
├── license_id
├── canonical_uri
├── document_digest
├── attribution_text
└── notices

ContentProvenance
├── primary_source_id
├── source_anchor
├── relation
├── fidelity
└── review_status
```

Initial source/relation vocabulary:

- `srd_5_1_cc`: verified content from SRD 5.1 under CC-BY-4.0.
- `srd_5_2_1_cc`: verified content from SRD 5.2.1, only through an explicit
  compatible adaptation or separate ruleset pack.
- `neurodragon_original`: original project content.
- `third_party_open`: another work with exact source, version, license, and
  attribution.
- `fixture_internal`: tests, tutorials, diagnostics, and non-shipping markers.
- `provenance_unverified`: retained existing content awaiting source review;
  playable during migration but never advertised as SRD.

`relation` distinguishes faithful implementation, compatible adaptation,
derived content, and original content. `fidelity` is `complete`, `partial`, or
`blocked`. A partial current implementation remains available during migration
but exposes its missing dependency/mechanic ledger; it is not mislabeled as
complete.

Pack manifests declare default sources and required attribution. Individual
definitions may override provenance because current modules mix SRD,
NeuroDragon-original, and fixture content. Provenance is authored data, never
inferred from module names, class paths, display names, or archived local
notes.

Keep this separate from `EffectOrigin`: source provenance answers where a rule
definition came from, while effect origin answers which runtime spell/action/
item causally produced a particular effect.

Recommended built-in pack split:

```text
engine.rules                 closed mechanics and standard system behavior
content.srd_5_1_cc           verified SRD 5.1 definitions
content.neurodragon          original/adapted NeuroDragon content
content.fixture_internal     enabled only in tests/development
```

An explicitly reviewed 5.2.1 adaptation belongs in
`content.neurodragon` with `adapted_from=srd_5_2_1_cc`, unless and until a
separate compatible SRD 5.2.1 ruleset pack exists.

### 6.7 Typed dependency and behavior closure

Every root or independently addressable definition declares typed edges:

```text
ContentDependency
├── relation
├── target_ref
├── required
└── notes
```

Initial relations:

- `grants_action`
- `grants_spell`
- `applies_condition`
- `installs_handler`
- `creates_zone`
- `creates_object`
- `creates_item`
- `equips_item`
- `summons_creature`
- `requires_primitive`

The frozen registry validates the complete transitive graph:

- Every target resolves.
- Every cross-pack edge has a manifest dependency.
- Cycles are allowed only for explicitly modeled non-construction references.
- Construction cycles fail startup.
- Missing required dependencies make the root `blocked`; they never degrade to
  a different spell, item, action, trait, or generic stat bonus.
- Private behaviors still have descriptors and dependency edges but are not
  factory-resolvable unless independently selected or persisted.

### 6.8 Checked-in migration and source coverage ledgers

Create two distinct ledgers:

1. `LegacyContentMigrationLedger`: every currently implemented root and
   derived behavior, keyed by stable reviewed identity.
2. `SourceCoverageLedger`: every item, creature/NPC, trait, action, reaction,
   and required spell named by the chosen SRD 5.1 source corpus.

Each source-coverage row includes:

```text
source_entry_id
definition_kind
source_name
source_anchor
implementation_status
content_ref
dependency_refs
mechanical_notes
measuring_test_nodeids
```

Status is one of `complete`, `partial`, `missing`, `blocked`,
`not_applicable`, or `fixture_only`. The implementation program ends with zero
`missing`, `partial`, or `blocked` rows in the agreed SRD 5.1 item/creature
scope.

The migration ledger is not a count-only golden. It preserves exact identities
and normalized behavioral closures for:

- Every existing item/creature/premade factory and meaningful parameter
  variant.
- All 109 current public spells and their exact levels.
- Every shipped action and condition classification.
- Every player-visible or state-affecting handler definition.
- Aegis Spark, Acid Flask behavior, Test Bless, Field Focus, circus/skeleton
  content, and item reactions with explicit production/private/fixture
  classification.

Tests fail if a concrete built-in definition or handler creation site is
unaccounted. Import order cannot change the inventory. No legacy entry is
deleted until its new root/behavior mapping and focused semantic tests pass.

## 7. External content-pack management

### 7.1 Filesystem layout

Add a repository/deployment-level trusted pack root:

```text
content_packs/
├── README.md
└── example_pack/
    ├── content-pack.toml
    ├── src/
    │   └── example_pack/
    │       ├── __init__.py
    │       ├── items.py
    │       ├── creatures.py
    │       └── behaviors.py
    └── assets/
```

The default root is the repository's `content_packs/`. Additional absolute
roots may be configured through `DND_CONTENT_PACK_ROOTS`.

Only immediate child directories containing `content-pack.toml` are packs.
Hidden directories, caches, loose Python files, directories without manifests,
and paths escaping the configured root are ignored or rejected as appropriate.

### 7.2 Manifest

Initial manifest:

```toml
schema_version = 1
pack_id = "example.goblin_expansion"
pack_version = "1.0.0"
engine_content_api = 2
python_root = "src"
python_package = "example_pack"
assets_root = "assets"

[[dependencies]]
pack_id = "core.rules"
version = "1"

[[sources]]
source_id = "publisher.work_version"
title = "Exact source title"
source_version = "1.0"
license_id = "CC-BY-4.0"
canonical_uri = "https://example.invalid/canonical-source"
attribution_text = "Exact attribution required by the source license."
```

The manifest never contains executable expressions. Source document digests
and any license/notice files participate in the pack digest.

### 7.3 Discovery and loading

Startup order:

1. Resolve and validate configured pack roots.
2. Discover manifests in deterministic path order.
3. Parse and validate every manifest without importing pack code.
4. Reject duplicate pack IDs, incompatible engine API versions, invalid paths,
   duplicate Python package names, and malformed dependency constraints.
5. Build and topologically sort the pack dependency graph.
6. Reject dependency cycles and missing dependencies.
7. Hash the canonical manifest plus every included source/asset file by sorted
   relative path before executing pack code.
8. Discover every Python module below the declared `python_package`.
9. Load those modules in sorted fully-qualified-name order under the pack's
   isolated package namespace.
10. Scan pure decorator declarations.
11. Build temporary per-kind registries and descriptor indexes.
12. Validate references, factory signatures, schemas, content-key uniqueness,
    assets, and cross-pack dependencies.
13. Re-hash the included files and reject a pack that changed during
    bootstrap.
14. Compute the frozen content-set identity from the canonical manifest,
    sorted file hashes, and sorted canonical descriptors.
15. Atomically publish the immutable `ContentSystem`.

Recursive module discovery is intentional inside a validated trusted pack. It
lets a pack author add a decorated factory in any ordinary `.py` module without
editing another central registration list. Directory/file names do not assign
content kind; decorators do. Cache files are excluded, imports are sorted, and
the entire pack fails atomically if any module fails.

Any failure aborts application startup. A broken pack is never silently
skipped, because that could make persisted characters or replays load with
different mechanics.

### 7.4 Trust and security

- Packs are trusted server-installed Python code with the same authority as the
  engine process.
- Pack directories are never populated through gameplay HTTP endpoints.
- Autodiscovery is disabled or rooted in an administrator-controlled directory
  in hosted deployments.
- No automatic `pip install`, dependency download, or arbitrary archive
  extraction occurs.
- Manifest and asset paths are normalized and checked for traversal.
- Symlink policy is explicit and defaults to rejecting links that escape the
  pack root.
- The manager logs and reports exact loaded pack identities and digests.

### 7.5 Freeze and lifecycle

- Registries are immutable after startup.
- Adding/removing/changing a pack requires process restart.
- A gateway loads and freezes packs before prewarming workers.
- Workers receive absolute pack roots and the gateway's expected
  content-set digest.
- Worker readiness returns the loaded content-set identity.
- A mismatch terminates the worker before it can enter the warm pool.

### 7.6 Management surfaces

Provide:

- A CLI `list`, `validate`, and `digest` command for configured packs.
- A read-only `/content/manifest` endpoint.
- A read-only `/content/catalog` endpoint.
- Immutable digest-addressed asset serving if/when pack assets are enabled.

Do not provide install, upload, enable, disable, or delete mutations over the
public game API in this tranche.

## 8. Item registry

### 8.1 Item factory declaration

An item registration owns:

- `ContentRef`
- Typed factory parameter model
- Immutable `ItemDefinition`
- Player-facing descriptor
- Builder callable
- Persistence policy
- Stack compatibility identity
- Optional declared behavior/content dependencies

Persistence policies:

- `possession`: may enter character holdings.
- `intrinsic`: structural body/natural equipment rebuilt with the creature and
  never stored as loot.
- `encounter_only`: valid runtime object but never settled to a character.
- `environment`: map fixture, never a character possession.

`is_pickable` remains a gameplay capability and is not a persistence policy.

### 8.2 Durable item state

```text
CharacterItemV1
├── character_item_id
├── recipe: ContentRecipe
├── quantity
├── remaining_charges
├── durability_damage
├── durable_augmentations
└── equipped_slot
```

Definition-owned fields include:

- Max stack
- Charge capacity
- Maximum durability
- Mechanics and actions
- Slot compatibility and occupied footprint
- Visual metadata
- Merge compatibility

Instance-owned durable fields include:

- Quantity
- Current active-copy charges
- Durability damage
- Explicit permanent item augmentations
- Inventory versus selected equipment slot

Excluded:

- Runtime item UUID
- Owner/container/tile UUID
- Grid position
- Runtime conditions/handlers/modifiers
- Temporary weapon coating
- Temporary light state
- Action templates as serialized objects

Multi-slot equipment is serialized once under its selected slot. Occupied
footprint is derived from the definition.

An effect that is meant to survive encounters cannot live only as an active
entity/item condition. Represent it as:

```text
ItemAugmentationRecord
├── content_ref
├── validated parameters
└── durable mutable state
```

Materializing or equipping the item rebuilds the corresponding runtime
condition, modifier, or handler through domain APIs. Temporary coatings and
buffs do not create augmentation records. This prevents permanent affixes from
disappearing without serializing a live condition graph.

### 8.3 Runtime binding

Every item built through the registry receives a deployment-local binding:

```text
runtime item UUID
→ item recipe/digest
→ optional persistent character-item ID
→ origin (starter, persisted, loot, reward, intrinsic, encounter-only)
```

The binding may live in a high-level runtime service rather than making
`BaseItem` import persistence code.

Rules:

- Persisted items receive fresh runtime UUIDs on each deployment.
- Existing persistent item IDs survive deployments.
- New loot receives a deterministic persistent ID during settlement.
- Stack merge lineage follows `ItemLocationStateEvent.merged_into_item_uuid`.
- Existing persistent identity wins when new loot merges into an existing
  stack.
- Stack compatibility must converge on equal item recipe/definition digest,
  not a display name or class identity.
- Final enumeration is authoritative for state; the event ledger supplies
  provenance and anti-duplication evidence.

### 8.4 Initial migration scope

Register and hard-cut all:

- Equipment and apparel reachable from the three persistent premades.
- Pickable loot reachable from supported scenarios/maps.
- Item factories used by the map editor.
- Server-authored reward items once rewards exist.

Do not register doors, chests, cannons, directional structures, or other
environment fixtures as possessions.

## 9. Creature registry

### 9.1 Unified creature recipe

Replace monster/NPC-specific lookup with:

```text
CreatureRecipe
├── actor_id / deployment_role
└── recipe: ContentRecipe(kind=creature)
```

Runtime context remains separate:

```text
CreatureBuildContext
├── runtime entity UUID/source
├── display name
├── faction
├── position
├── deployment role
└── content/item materializer
```

The same factory family covers:

- Player-class bodies
- Bestiary actors
- SRD monsters
- Humanoid NPCs
- External-pack creatures

Tags and catalog metadata distinguish monster, NPC, player-capable, summon,
boss, civilian, and other roles.

### 9.2 Body, intrinsic content, and possessions

Creature construction must separate:

1. Structural body and mechanics.
2. Intrinsic attacks/body equipment.
3. Default or starter possessions.
4. Runtime deployment context.

A registration may declare a structural builder and a deterministic default
holdings recipe. This prevents character reload from regranting starter gear.

- Ephemeral scenario creature: build body, intrinsic content, and declared
  default possessions.
- New persistent character: build/validate the definition and mint starter
  holdings once.
- Reloaded character: build body/intrinsic content and hydrate exact persisted
  holdings, without default possession grants.

### 9.3 Hard-cut targets

Migrate and remove:

- `SRD_MONSTER_FACTORIES`
- Parallel SRD spec/factory identity lists
- `create_srd_monster()` as a second lookup API
- Bestiary `if/elif` construction dispatch
- Closed actor-family dispatch in `build_actor()`
- Closed `ActorBlueprint` family union as the authoritative external boundary
- Scenario item/equipment/apparel switches

All callers, tests, scenario recipes, and AI validation use `CreatureRecipe`
through the frozen registry.

## 10. Actions, conditions, spells, traits, and private behavior

### 10.1 Ownership rule

An item or creature factory may own private behavior classes directly.

Private factory-owned behavior:

- Is reconstructed when the parent factory runs.
- Is not persisted independently.
- Is not independently selectable by clients.
- May directly use local helper classes within the same pack.
- Still carries stable content attribution when player-visible.

Examples:

- A potion's drink action.
- A weapon's attack rider handler.
- A ghoul's claw paralysis condition.
- A creature's internal once-per-turn marker.

Do not register every internal marker or closure as a global factory merely to
make the registry look uniform.

Factory registration and semantic behavior identity answer different
questions:

- Factory registration answers **how an independently durable root is
  reconstructed**.
- Semantic behavior identity answers **what a runtime rule means to UI, AI,
  analytics, replay, and diagnostics**.

Use a metadata-only declaration such as `@behavior_identity(...)` for a
factory-private action/condition/handler that must be externally described.
This does not make that behavior independently constructible or persistable.

### 10.2 When independent registration is required

An action, condition, spell, trait, or reaction needs an independent content
registration when any of these are true:

- Another pack references it by identity.
- A character definition or holdings recipe persists it independently.
- It is directly selectable or authorable in a UI.
- It is granted dynamically without reconstructing its owning item/creature.
- It requires an independent migration/version lifecycle.

The generic content system must support these kinds, but the first factory
migration only needs item and creature builders. Other kinds may initially be
descriptor-only while their existing engine construction remains owned by the
parent factory.

### 10.3 Descriptor closure

Every player-visible action, condition, spell, reaction, trait, feat, and class
feature must resolve to a `ContentDescriptor`.

Internal markers may use `visibility=internal` and are omitted from the player
catalog. They still require stable, namespaced semantic identities for
diagnostics.

Factory registrations declare their provided/referenced content. Registry
validation rejects:

- Missing referenced descriptors.
- Cross-pack references without a manifest dependency.
- Player-visible behavior with only a class-path fallback.
- Duplicate semantic identities.
- Presentation references to missing assets.

Condition-owned handlers may derive child semantic identities from their
owning condition. Direct item/creature hook handlers must use an owner helper
or explicit namespaced identity. Python callback/module paths are never public
semantic identities.

### 10.4 Runtime behavior binding

Every derived runtime action, condition, handler, and spatial handler carries:

```text
BehaviorBinding
├── definition_ref
├── provided_by_ref
├── origin_root_ref
└── runtime_owner_uuid
```

- `definition_ref` answers what the behavior means.
- `provided_by_ref` identifies the item, creature, condition, spell, trait, or
  other definition that installed it.
- `origin_root_ref` links the behavior to the durable deployed root when
  applicable.
- `runtime_owner_uuid` remains ephemeral within one encounter.

Examples:

- Pack Tactics has one SRD trait definition while Wolf and Dire Wolf are
  separate providers.
- A healing potion's Drink behavior is private to the potion definition but
  still resolves a descriptor.
- A condition-owned wake-on-damage handler derives a child behavior ref from
  the condition.
- An external creature using a core spell retains the core spell's definition
  provenance and the external creature's provider provenance.

Bind ordinary and spatial handlers before queue admission so their first
dispatch is already attributable. Root helper APIs provide the binding; pack
code never mutates transport/evaluation registries.

Hard-cut runtime cleanup:

- Make event and spatial handler admission duplicate-safe.
- Move all live spatial mechanics from legacy `EventHandler` spatial indexing
  to native `SpatialHandler`.
- Ensure condition-owned spatial handlers inherit identity/kind/owner just like
  ordinary handlers.
- Ensure equip/unequip, apply/remove, concentration cleanup, and runtime reset
  remove every owned index exactly once.
- Carry behavior ref plus runtime instance ID in player-toggle DTOs; stop using
  display name as an unambiguous mutation key.

Only conditions independently selected by data—currently including scenario
starting conditions and tile-created traps—need a constructible condition
registration. Spell/item/trait effect conditions remain transitive behavior
unless another pack or persistence model addresses them directly.

### 10.5 Spell catalog migration

Replace:

- `ALL_SPELLS` as the only global discovery path.
- Manual spell catalog overrides.
- Source-text inspection for attack/save behavior.
- Name-normalized VFX inference.

Spell declarations explicitly author their mechanical and presentation
descriptor facts. Spell classes and their private effect conditions remain
co-located.

The hard cut preserves a keyed baseline for all 109 current public spells, not
only the count. Preserve exact level bucket counts during migration, then let
the registry derive level views. Explicitly classify:

- `AegisSpark` as NeuroDragon-original extension content.
- `AcidFlaskSpell` as item-private behavior provided by Acid Flask.
- `TestBless` as fixture-only and absent from production catalogs.

Spell behavior closure includes effect conditions, handlers, zones, tile
markers, created objects, summoned creatures, and granted actions. A spell is
not `complete` merely because its top-level class can be instantiated.

### 10.6 SRD 5.1 item and creature completion

Use the official SRD 5.1 CC source corpus—not archived repository prose—as the
authoritative source ledger. Preserve archived notes only as historical
implementation evidence until their unique tests/mappings are migrated.

Items are completed by source category:

1. Weapons, ammunition, armor, and shields.
2. Adventuring gear, containers, consumables, tools, kits, instruments,
   mounts/tack, and vehicles that the engine can represent as inventory roots.
3. SRD magic items, including charges, recharge, attunement requirements,
   equip/use behavior, destruction/consumption, and spell dependencies.
4. Source rows that are economic/table data rather than meaningful inventory
   roots are explicitly `not_applicable` with a reviewed reason; they are not
   silently omitted.

Creatures/NPCs are completed from the full SRD 5.1 source list, not the current
27-creature validation roster. A creature is `complete` only when its factory
and descriptor cover:

- Ability/skill/save/HP/AC/movement/senses/size/type facts.
- Damage and condition defenses.
- Equipment, natural attacks, and possessions.
- Actions, bonus actions, reactions, legendary behavior where present, traits,
  resources, recharge, multiattack, spellcasting, and summoned/created content.
- Appearance/presentation metadata or one explicit reviewed generic profile.
- Exact typed dependency closure and focused behavior tests.

Completion order is dependency-driven:

1. Import and classify every current implementation without semantic loss.
2. Implement data-only and existing-primitive items/creatures.
3. Implement reusable missing action/trait/condition/handler primitives.
4. Implement every missing spell required by an SRD item or creature.
5. Materialize dependent caster, summoner, zone, recharge, and complex-reaction
   creatures/items.
6. Run the source-ledger completeness gate and remove every remaining
   `missing`, `partial`, or `blocked` row in agreed scope.

Never replace an unavailable spell/trait with a similarly named action or
inflated statistic. A root stays explicitly blocked until the dependency is
implemented. This makes the missing-work list truthful and machine-readable.

Content inspired by SRD 5.2/5.2.1 is not folded into these SRD 5.1 identities.
It receives a NeuroDragon-owned definition and explicit `adapted_from`
provenance unless implemented later as part of a separate compatible ruleset
pack.

## 11. Events and content

### 11.1 Closed causal kernel

The following remain engine-versioned and closed:

- `EventType`
- Reducer-critical event payload families
- Event phases and queue semantics
- Objective replay event decoder
- Subjective patch and presentation-cue families

If content requires a genuinely new causal primitive or client reducer
behavior, that is an engine protocol change. It must update generated contracts
and clients explicitly.

### 11.2 Content attribution

Core events and presentation cues should carry stable content attribution where
relevant:

- `source_content_ref`
- `action_content_ref`
- `condition_content_ref`
- `item_content_ref`
- `spell_content_ref`
- `effect_content_ref`

Runtime UUIDs remain for causal correlation. Content refs identify semantics and
resolve presentation metadata.

Packs implement mechanics by composing existing event families. For example, a
custom condition still applies through `ConditionApplicationEvent`, damage
through the existing damage lifecycle, and movement through movement events.

### 11.3 Optional generic content signal

If a pack needs an observational event that does not alter reducer state, add
one generic, engine-owned `ContentSignalEvent` with:

- Content reference
- Namespaced signal key
- Primitive/JSON payload validated by the pack's registered schema
- Explicit observational-only semantics

Do not use this as an escape hatch for untyped state mutation. The frontend may
display it generically or through descriptor metadata, but reducers never infer
authoritative world changes from it.

### 11.4 Protocol identity

Keep separate:

- Engine event-contract hash.
- Player replication contract hash.
- Content-set digest.

Replays and game creation manifests pin all relevant identities. A content-only
metadata change does not masquerade as an event-protocol change, and an event
kernel change does not silently look like a content-pack upgrade.

### 11.5 Deferred stateful environment presentation

Environment mechanics stay with their authoritative runtime owner. A multi-cell
spike network therefore remains a tile/environment condition with spatial
handlers; it does not become a collection of ordinary inventory items merely
to obtain a sprite. Doors, torches, chests, levers, hazards, and similar
features should nevertheless share one typed presentation-state pattern:

- The content descriptor declares a closed set of safe visual state keys and
  their exact sprite/VFX/audio presentation.
- The authoritative mechanic exposes its current state through a typed
  environment-state fact such as `armed`, `triggered`, `disabled`, `open`,
  `closed`, `lit`, or `unlit`.
- A state-changing action commits an engine-owned environment-state event.
  Subjective world diffing emits the corresponding typed patch, and the
  presentation mapper emits an ordered transition cue when animation is
  knowable.
- The client selects only the delivered content reference plus typed state; it
  never infers state from display names, lever proximity, hazard flags, or
  filenames.

The temporary MapEditor save format may support one explicitly validated trap
network, but it does not define this final player transport. The reusable
stateful environment contract is a later bounded session/presentation task and
must land red-first with armed-to-disabled spike, door open/close, and
light-source transition regressions before the issue can be considered closed.

The first implementation keeps reducer ownership singular:

- Permanent spikes retain one safe tile marker after deactivation, changing
  from `armed` to `disabled`; disabling removes the shared spatial handler and
  hazard behavior, not the remembered presentation fact.
- Transient spell zones such as Spike Growth continue to apply and remove
  normally. They do not manufacture a persistent disabled fixture.
- Floor-object state continues through its authoritative object patch, while
  tile state continues through the complete tile/condition patch. Do not add a
  parallel generic state dictionary or a second reducer path.
- Replace the door-only animation cue with one closed environment-transition
  cue whose target is explicitly a safe floor object or an authorized tile
  region. A multi-cell trap transition is one causal event and one ordered cue,
  not one event per tile.
- Hidden or off-screen transitions update neither remembered facts nor
  presentation cues. Re-observation snaps to the current safe state without
  replaying an unseen transition.

This work deliberately starts after the schema-5 content/equipment freeze so it
can rotate the catalog and player contracts once, as a bounded schema-6
session, rather than destabilizing the playable cutover.

## 12. Frontend content catalog

### 12.1 API

Add a generated SDK surface for:

- `GET /content/manifest`
- `GET /content/catalog`
- Optional immutable asset URLs

The catalog is cacheable by content-set digest/ETag and contains safe
descriptors, not Python code or live factory objects.

### 12.2 NeuroClient migration

Use content refs/descriptors for:

- Action and reaction icons
- Condition icons and descriptions
- Item icons and variants
- Creature portraits/sprites
- Spell VFX routing
- Action grouping and stable ordering
- Search tags and categories
- Generic tooltips

Delete the corresponding manual aliases, class-path cases, display-name sets,
slug inference, and fixed ordering tables once descriptor parity tests pass.

Reducer and animation dispatch remains based on the closed presentation-cue
contract. Content descriptors choose assets and labels; they do not replace
causal validation.

### 12.3 Visibility

Descriptors declare visibility:

- `public`: safe installed-content reference data.
- `observed`: delivered only when the subjective game surface reveals the
  associated content.
- `developer`: objective/debug tooling.
- `internal`: never delivered to ordinary clients.

Server authorization and subjective projection remain authoritative. The
catalog must not leak hidden encounter state merely because a definition is
installed.

## 13. Persistent character model

### 13.1 Three layers

#### CharacterDefinitionRevision

Durable structural build:

- Character revision number
- Schema version
- Player-capable creature recipe
- Class, level, subclass, ability choices, proficiencies, feats, spells known,
  and other structural factory parameters
- Definition digest and provenance premade ID

Level-up or build changes create a new immutable definition revision.

#### CharacterHoldingsRevision

Durable possessions:

- Holdings revision number
- Ordered/deterministic `CharacterItemV1` records
- Equipped loadout
- Holdings digest

Loot, consumption, equipment changes, and rewards create a new immutable
holdings revision.

#### Encounter state

Never written into either durable revision:

- Current HP/damage
- Life state
- Temporary buffs, conditions, coatings, and concentration
- Spell slots and encounter resources spent during the match
- Action economy
- Position, movement, senses, initiative, and turn state
- Runtime entity/item UUIDs

### 13.2 Character record

```text
CharacterRecord
├── character_id
├── display_name
├── owner envelope
├── status
├── current_definition_revision/digest
├── current_holdings_revision/digest
├── timestamps
└── row_version
```

Ownership is outside the definition:

- Local profile DB: physical profile boundary owns the character.
- Hosted directory: principal/tenant relation owns the character.

### 13.3 Premade selection

For this tranche:

- Public clients submit display name plus approved premade content ref/ID.
- The server resolves the premade through the frozen content system.
- Character creation atomically stores definition revision 1 and mints holdings
  revision 1.
- Clients cannot submit arbitrary creature or item recipes.
- The existing three premades remain the only persistent-character choices
  until a creator is designed.

### 13.4 Deployment

Launching a saved character requires only `character_id`.

The profile/gateway:

1. Authenticates ownership.
2. Acquires an exclusive live-deployment lease.
3. Pins definition and holdings revisions/digests.
4. Sends a private resolved-character envelope to the worker.
5. Worker constructs the structural body and intrinsic content.
6. Worker materializes exact persisted holdings with fresh runtime UUIDs.
7. Deployment records character/entity/item lineage and opening digests.

The browser never supplies a resolved blueprint or holdings snapshot.

## 14. Terminal holdings settlement

### 14.1 Worker evidence

At a clean `EncounterEnd`, the worker captures:

- Deployment identity
- Runtime entity identity
- Opening character/holdings revisions and digests
- Exact final carried and equipped persistable holdings
- Runtime-to-persistent item lineage
- Item acquisition/removal audit delta
- Generation and terminal event/combat-log cursors
- Replay/content-set identities
- Settlement-evidence digest

Final enumeration is authoritative. Item events corroborate provenance and
ordering but are not the sole source because some low-level container paths are
not fully event-sourced and presentation snapshots lack reconstruction data.

### 14.2 Atomic commit

After replay bytes are durably content-addressed, one SQL transaction:

1. Verifies game is active and terminal evidence identities match.
2. Verifies the active character lease and base revisions.
3. Verifies final items resolve through the frozen content set.
4. Applies deterministic server-authored rewards, initially `none.v1`.
5. Writes immutable new holdings revisions.
6. Writes settlement audit records.
7. Advances character current-holdings pointers with compare-and-swap.
8. Persists replay/summary/artifact metadata.
9. Marks the game ended.
10. Marks deployments settled and releases leases.

Any failure rolls back the entire DB mutation. Exact retries return the
existing result. A retry with a different digest is a conflict.

Summary corrections never rerun settlement or rewards.

### 14.3 Initial policies

- One active deployment per persistent character.
- Clean ended games settle held/equipped items regardless of victory or final
  life state.
- Dropped, destroyed, or consumed items are absent/decremented.
- Failed or interrupted games release the lease without settlement.
- Replay playback/import never invokes settlement.
- Reward IDs derive deterministically from game, character, reward policy, and
  reward slot so retries cannot duplicate rewards.

### 14.4 Crash recovery

Terminal evidence must not remain only in worker memory.

Worker writes terminal components under its private runtime directory:

1. Atomic component files.
2. Fsync as required.
3. Final ready manifest written last.

Gateway restart reconciles ready manifests before declaring games interrupted.

- Crash after ready/before SQL commit: exact retry settles once.
- Crash before ready: interrupt game, preserve base revisions, grant nothing,
  release lease.
- Invalid/conflicting ready evidence: fail closed without partial settlement.

## 15. SQL and replay layout

### 15.1 Character tables

Target logical records:

- `character_definitions`
- `character_holdings_revisions`
- `characters`
- `character_deployments`
- `character_deployment_items` or equivalent launch-lineage evidence
- `character_deployment_leases`
- `character_settlements`

Definitions and holdings may initially use canonical JSON plus SHA-256 digests
instead of fully normalizing item rows. Trading/marketplace queries do not
justify normalization yet.

### 15.2 Local and hosted storage

- Local: one SQLite DB per physical profile, with profile-owned history and
  characters.
- Hosted: shared deployment directory DB with principal/tenant ownership.
- Shared repository/domain operations enforce identical revision, lease, and
  settlement semantics.
- Replay bytes remain files in a content-addressed artifact directory.
- SQL stores artifact metadata, digests, ownership/history links, and terminal
  transaction state.

### 15.3 Legacy migration

The character migration:

- Runs after the current replay-artifact migration.
- Inserts frozen definition/holdings payloads for the three approved premades.
- Backfills all known legacy rows deterministically.
- Adds definition/holdings digests to deployments.
- Removes `preset_configuration_id` as an authoritative column.
- Fails explicitly for unknown legacy presets.

Migration payloads must be frozen literals/digests owned by the migration.
They must not resolve through the mutable current content registry.

### 15.4 Replay identity

Creation manifest pins:

- Character ID
- Definition and holdings revisions/digests
- Exact character and item recipes used at launch
- Content-set digest
- Engine/ruleset/protocol identities

Terminal evidence pins settlement digest and final holdings. Replays reconstruct
the recorded match from replay seeds/events; they do not load the character's
latest state or re-award loot.

## 16. Gateway, worker, standalone, and AI integration

### 16.1 Shared bootstrap

Both standalone and gateway call the same content bootstrap.

- Standalone ephemeral game: resolves premades locally and uses the same
  creature/item materializers.
- Local profile composition: additionally opens one profile DB and settlement
  service.
- Gateway: freezes content before opening/prewarming workers.
- Worker: loads the same roots and verifies expected digest before readiness.

### 16.2 Worker handshake

Extend readiness/status with:

- Engine version
- Protocol hashes
- Content API version
- Content-set digest
- Loaded pack summary

Gateway rejects and terminates mismatched workers. Warm workers cannot be
advertised merely because they return HTTP 200.

`GameRecord.content_digest` becomes the actual installed content-set digest.
Store creation-request digest separately.

### 16.3 External AI

AI policy identity remains separate from content identity.

However:

- Action observations carry content refs.
- AI/provider handshake declares the content-set digest it expects or supports
  when policy logic relies on specific content.
- Generic policies may operate from descriptor/action facts without loading
  pack implementation code.
- A hosted provider is never advertised for content it cannot interpret when
  its descriptor declares hard content dependencies.

Do not couple pack loading to AI subprocess management.

## 17. Public API and SDK hard cut

Planned public changes:

- Content manifest/catalog SDK methods.
- Character creation accepts `premade_id`/content ref, not a blueprint.
- `CharacterRecord` exposes stable definition/holdings summaries and digests.
- Hosted/local launch accepts `character_id`; the client does not duplicate
  `hero_configuration_id`.
- Game/profile history exposes character deployment and replay links.

Planned private changes:

- Resolved-character worker launch envelope.
- Terminal settlement evidence endpoint/spool.
- Worker readiness content identity.

Private DTOs are not generated into the public TypeScript SDK.

No V2 aliases or parallel legacy routes remain after cutover.

## 18. Implementation phases

Each phase begins with deterministic regressions and ends with its replaced
path removed. Do not leave a long-lived old/new compatibility layer.

### Phase 0 — Baseline and exact legacy inventory

- Finish the old/new-system audit.
- Record every current factory/catalog/dispatch path.
- Add static tests that name the paths intended for deletion.
- Add a red-first dispatch-boundary regression, converge the live
  session/Codex/action endpoint adapter on `dnd.action_dispatch`, and delete
  the direct authoritative-action bypass.
- Make an explicit keep/delete decision for the isolated old-artifact
  observation migrator; do not leave it ambiguously named as a current
  protocol.
- Check in the keyed legacy migration ledger for every current item/creature/
  premade root and every action/spell/condition/handler classification.
- Capture exact normalized behavioral closures plus lifecycle probes for every
  current root; do not rely on counts or import-order subclass scanning.
- Build the authoritative SRD 5.1 CC source coverage ledger from the official
  document and record exact attribution/document digest.
- Preserve the proven absence of the deleted managed-AI service modules and
  routes.

Exit: exact migration/deletion table, zero unaccounted current behavior, exact
SRD 5.1 work queue, and green focused baseline.

### Phase 1 — Neutral content contracts and pack loader

- Atomically move the existing `dnd.core.content` leaf into the new package and
  add definition/behavior kinds, identities, provenance, recipes, descriptors,
  dependencies, manifests, inventory contracts, and decorator markers.
- Add `content_packs/README.md` and one test fixture pack.
- Implement deterministic discovery, dependency validation, loading, registry
  freeze, CLI validation, and content-set hashing.
- Add architecture-test exception only for the loader.
- Integrate shared bootstrap into standalone, gateway, and worker.
- Add readiness digest verification.

Exit: no gameplay factory migration yet, but one fixture item/creature pack can
load deterministically in all process modes.

### Phase 2 — Item registry hard cut

- Decorate/migrate every currently implemented player-persistable,
  environment, fixture-classified, and map-editor item factory.
- Add item recipes, runtime binding, persistence policies, and round-trip
  materializer.
- Preserve every existing embedded item action/condition/handler closure,
  including gameplay content currently located in `test_items.py`.
- Migrate scenario item/equipment/apparel grants and map-editor lookup.
- Migrate stack identity to recipe/definition digest where applicable.
- Delete central item/apparel/loot switches and class-path reconstruction
  fallbacks for player-visible items.

Exit: one item factory path and complete round-trip tests for supported items.

### Phase 3 — Creature registry hard cut

- Decorate every currently implemented player-class, bestiary, SRD, circus,
  skeleton, and extension creature factory with explicit provenance.
- Separate structural body, intrinsic content, and default possessions.
- Migrate side configurations to generic creature recipes.
- Migrate scenarios and AI-validation callers, including all 38 direct arena
  builders, to the composed recipe/materializer path.
- Delete central SRD factory dictionary, duplicate specs, wrapper lookup, and
  assembler family switches.
- Delete the retired direct arena dispatcher and parity scaffolding once every
  unique arena semantic assertion has a maintained composed-path owner.

Exit: one creature construction path and behavior-parity tests for all migrated
creatures.

### Phase 4 — Descriptor catalog and behavior attribution

- Register descriptors for all player-visible actions, conditions, spells,
  reactions, traits, feats, class features, items, and creatures.
- Classify internal markers.
- Add definition/provider/root bindings to actions, conditions, event handlers,
  and spatial handlers before runtime admission.
- Make handler admission duplicate-safe and migrate the legacy spatial-handler
  compatibility branch to native `SpatialHandler`.
- Preserve all 109 current public spells exactly and classify Aegis Spark,
  Acid Flask behavior, and Test Bless explicitly.
- Add content refs to relevant runtime projections/events/cues without opening
  the event kernel.
- Replace spell source inspection and manual overrides.
- Expose content catalog in SDK.

Exit: backend has no player-visible class-path fallback or source-code inference.

### Phase 5 — Complete SRD 5.1 items and creatures

- Implement every missing SRD 5.1 item root in source-ledger order.
- Implement every missing SRD 5.1 creature/NPC root.
- Implement reusable missing traits/actions/conditions/handlers rather than
  approximating them in individual stat blocks.
- Implement every missing spell or engine primitive required by an SRD item or
  creature.
- Add exact per-root dependency closures and focused semantic tests.
- Mark non-runtime table/economic rows `not_applicable` only with reviewed
  rationale.
- Finish with zero `missing`, `partial`, or `blocked` rows in agreed item/
  creature scope.

Exit: the registry and source coverage report prove full SRD 5.1 item/creature
coverage and exact provenance; NeuroDragon and fixture content remain clearly
separate.

### Phase 6 — Character definitions and initial holdings

- Add character definition/holdings revision models and tables.
- Resolve the three premades into revision 1 definitions and starter holdings.
- Add private definition-driven worker construction.
- Add exclusive deployment leases and lineage.
- Migrate existing six character rows/fifteen deployments.
- Remove duplicate hero preset authority.

Exit: a saved premade character reconstructs from stored definition and
holdings, with no regenerated starter possessions.

### Phase 7 — Settlement, replay, and profile history

- Add terminal holdings evidence and durable worker spool.
- Add atomic terminal evidence plus settlement transaction.
- Add restart reconciliation and idempotent retries.
- Add local per-profile DB composition using the same settlement operation.
- Expose history/replay/character links.

Exit: loot, consumption, dropping, equipment changes, and future reward slots
are durable exactly once after a clean end.

### Phase 8 — NeuroClient cutover and deletion gate

- Consume the dynamic content catalog.
- Replace manual icon/order/group/alias/name-inference tables.
- Keep causal rendering on the canonical player presentation contract.
- Add an exact source/boundary gate preventing reintroduction of removed
  heuristic lists.
- Regenerate SDK and pin content contract/hash.
- Run full focused backend, SDK, and frontend integration gates.

Exit: one backend-authored content identity/presentation path.

## 19. Required tests

### 19.1 Inventory, provenance, and dependency closure

- `test_every_builtin_behavior_is_accounted_for`: every imported production
  action, spell, condition, item, creature, trait, and handler construction
  site is classified as an independently constructible definition, root-owned
  behavior, internal runtime marker, abstract mechanism, or fixture-only
  content. No production row may rely on Python-path fallback identity.
- `test_builtin_catalog_is_import_order_invariant`: importing unrelated engine,
  server, extension, and fixture modules in different orders cannot add,
  remove, or mutate production catalog rows.
- `test_legacy_content_migration_ledger_is_complete`: every legacy item and
  creature construction root, action-registration site, item-use template,
  public spell, independently selected condition, and handler-registration
  site has exactly one retained registration, transitive owner, deliberate
  internal/fixture classification, or explicitly approved deletion.
- `test_production_spell_inventory_preserves_all_109_spells`: the exact current
  level distribution `12, 21, 23, 16, 9, 8, 10, 4, 4, 2`, semantic identities,
  and spell levels survive migration.
- `test_private_and_fixture_spells_are_explicitly_classified`: Aegis Spark is
  extension content, Acid Flask's spell behavior is item-owned, and Test Bless
  is fixture-only; none appears or disappears because of import order.
- Every descriptor and inherited pack source used by production content has an
  explicit source category, source/version reference, license identifier,
  attribution, and review status. Runtime `EffectOrigin` never substitutes for
  source/license provenance.
- Every SRD 5.1 claim resolves to the pinned official SRD 5.1 CC source and
  attribution. Every source-ledger row is classified as complete, partial,
  missing, blocked, not applicable, or fixture-only; a completed row links its
  content ref and focused tests.
- The reviewed extraction/ledger gate owns the initial official counts:
  317 creature/NPC stat blocks, 37 weapons, 12 armor suits plus one shield,
  239 named magic items, and 319 spells. Corrections require a reviewed ledger
  change with source anchors, not weakening a consumer assertion.
- The agreed final SRD 5.1 item/creature scope has zero missing, partial, or
  blocked rows. Content inspired by SRD 5.2/5.2.1 is explicitly marked as an
  adaptation and cannot silently satisfy an SRD 5.1 ledger row.
- Every typed dependency edge resolves through the frozen registry; cycles,
  kind mismatches, undeclared cross-pack references, missing transitive
  behavior, and references to disabled fixture packs fail before readiness.
- Root closure snapshots cover all current items and creatures and their
  actions, spells, conditions, traits, handlers, zones, created objects,
  possessions, and required engine primitives. Removing any dependency makes
  the focused gate fail even if the root can still perform a basic action.
- Full descriptor and closure inventories are deterministic artifacts whose
  hashes change for semantic content changes, not module import order.

### 19.2 Pack loader

- Deterministic discovery independent of filesystem enumeration order.
- Missing/malformed manifest.
- Duplicate pack ID.
- Duplicate content key/version.
- Same key/version with differing contract hash.
- Missing dependency and dependency cycle.
- Invalid engine content API version.
- Entry-module import failure leaves no partially published registry.
- Imported-but-not-locally-declared decorators are not double registered.
- Importing a pack creates no `BaseObject`, `Entity`, `EventQueue`, handler, or
  other gameplay-runtime state.
- Path traversal and escaping symlink rejection.
- Registry mutation after freeze rejected.
- Identical roots produce identical content-set digest.
- Pack or asset change changes digest.
- Helper-source behavior change changes the pack digest even when descriptor
  schemas are unchanged.
- File mutation between pre-import and post-import hashing aborts bootstrap.
- Missing required persisted pack fails with exact diagnostic.

### 19.3 Worker and gateway

- Gateway and worker matching content digest enter ready pool.
- Mismatch terminates worker.
- Warm worker cannot be claimed after pack-set mismatch.
- Game manifest and DB store exact content-set digest.
- Standalone and hosted resolve the same recipe identically.

### 19.4 Items

- Every supported item recipe round-trips mechanically.
- Healing amount, scroll spell/cast level, wand capacities/actions, weapon-coat
  variant, visual variant, charges, quantity, durability, and selected slot.
- Two-handed item serialized once.
- Intrinsic/environment/encounter-only items cannot enter holdings.
- Declared possession that cannot serialize/materialize fails closed.
- Full/partial stack merge preserves deterministic lineage.
- Runtime UUID changes while persistent identity survives.
- Permanent item augmentation rebuilds its runtime behavior exactly once.
- Temporary coating/condition does not enter durable augmentations.
- A hook-bearing equipped item reconstructs with exactly one handler/modifier;
  hydration followed by equip cannot double-register its behavior.
- Every currently playable item root and variant has an exact migration-ledger
  row and behavior-closure snapshot before the legacy construction path is
  deleted.
- A migrated item-owned use action that applies a condition which installs a
  handler behaves identically after runtime reset and hydration; only the item
  is a durable reconstruction root.
- Every SRD 5.1 item category and variant in the agreed source ledger has a
  constructible recipe, round-trip test, and provenance assertion. Unsupported
  mechanics remain red/blocked ledger rows rather than approximate items.

### 19.5 Creatures and behavior

- All SRD/bestiary/player factories have unique recipes and descriptors; all
  27 current SRD roster roots retain exact dependency closures before the
  expanded SRD 5.1 ledger is completed.
- Every migrated creature preserves abilities, HP configuration, size, senses,
  actions, conditions/immunities, handlers, traits, spells, equipment, and
  appearance.
- Monster/NPC role does not alter factory identity.
- Factory-private actions/conditions reconstruct with the parent.
- A fixture external item that owns an action which applies a condition which
  installs a handler round-trips after an engine-runtime reset; only the item
  is a reconstruction root.
- Renaming or moving a private helper class does not change authored semantic
  content references.
- Nested lootable possessions created by a creature are registered,
  provenance-bound item recipes rather than anonymous runtime objects.
- Cross-pack references require declared dependencies.
- Player-visible behavior without a descriptor fails validation.
- Internal marker remains absent from public catalog.
- Full SRD 5.1 creature completion validates every source-ledger row, including
  dependent spells, actions, conditions, traits, handlers, equipment, and
  summoned/created content; a creature cannot be marked complete merely
  because its factory constructs.
- Handler binding is assigned before queue admission and contains definition,
  provider, root-origin, and runtime-owner identity. Ordinary and spatial
  handlers preserve it through dispatch evidence and cleanup.
- Re-admitting the same handler cannot duplicate trigger/source/spatial
  indexes or invocation. Conflicting duplicate admission fails loudly.
- All content spatial behavior uses the native spatial-handler path after the
  hard cut; the legacy ordinary-handler compatibility branch has an exact
  absence gate.
- Removing a condition/item/creature clears every locally and globally indexed
  handler exactly once.
- Player-toggleable behavior exposes semantic identity in its DTO and toggle
  request; name and runtime UUID remain presentation/runtime facts, not durable
  content identity.
- Moving or renaming a handler processor helper does not change a declared
  semantic behavior ref.

### 19.6 Event boundary

- External pack cannot register a new reducer-critical `EventType`.
- Pack mechanics emit existing causal event families.
- Content refs survive objective and subjective projection without exposing
  hidden state.
- Content-signal payload cannot mutate reducer state.
- Event protocol hash and content-set digest change independently.

### 19.7 Characters and holdings

- Character creation atomically stores definition and starter holdings.
- Starter equipment appears exactly once.
- Two no-op deployments do not duplicate equipment, apparel, potions, or
  augmentations.
- Stored character name becomes runtime display name.
- Catalog mutation cannot alter a stored definition.
- Deployment pins definition and holdings revisions/digests.
- Same character cannot enter two live games.
- Different characters can play concurrently.
- Fresh runtime entity/item UUIDs with exact persistent lineage.
- Runtime HP, position, action economy, light, temporary conditions, and
  coatings do not persist.

### 19.8 Settlement

- Held loot persists.
- Consumed quantity/charges stay consumed.
- Dropped or destroyed items do not persist.
- Equipped loadout persists.
- Dead character settles items but starts later with fresh ephemeral state.
- Failed/interrupted game changes no holdings and releases lease.
- Injected DB failure rolls back game end and all character changes.
- Multi-character settlement is all-or-nothing.
- Exact retry writes one revision/reward.
- Conflicting retry rejected.
- Stale base revision rejected.
- Crash-after-ready restart settles once.
- Crash-before-ready grants nothing.
- Artifact-write/DB-failure retry succeeds exactly.
- Summary correction does not settle again.
- Replay playback/import cannot settle or grant rewards.

### 19.9 Frontend

- Catalog resolves every visible action/condition/item/creature/spell ref.
- No required icon/order/grouping decision depends on display-name
  normalization.
- Unknown optional descriptor uses one explicit generic presentation, while
  missing required visible content fails a development/contract gate.
- Subjective visibility prevents hidden descriptor/state leakage.
- Existing renderer/presentation transaction tests remain green.

## 20. Performance requirements

- Pack discovery/import happens once per process before readiness.
- Frozen registry lookup is O(1).
- No filesystem access or dynamic import occurs during item/creature
  construction or turns.
- Materialization overhead is measured separately from factory mechanics.
- Content catalog is precomputed/cacheable by digest.
- Worker prewarming absorbs pack import time.
- Settlement operates on final character holdings, not the entire global item
  registry or replay.
- Add startup, lookup, materialization, and settlement timing assertions with
  generous deterministic regression thresholds rather than flaky wall-clock
  microbenchmarks.

## 21. Documentation and operational deliverables

- Update `AGENTS.md` dependency rules with the single startup-loader exception.
- Document trusted-code status and restart requirement in
  `content_packs/README.md`.
- Document pack authoring, decorators, parameter models, dependencies,
  descriptors, assets, and validation CLI.
- Check in the legacy-content migration ledger and the SRD 5.1 source-coverage
  ledger, including the pinned official source reference, license, attribution,
  review status, implementation status, content refs, and focused test owners.
- Generate deployment attribution/notices from enabled pack provenance. Keep
  SRD 5.1 CC, explicit SRD 5.2/5.2.1 adaptations, NeuroDragon originals,
  third-party open content, fixtures, and unverified legacy provenance
  distinguishable in both tooling and exported metadata.
- Document character structural/holdings/encounter boundaries.
- Document terminal settlement and crash policy.
- Update multi-game gateway docs with content handshake and profile/history
  composition.
- Add an example external pack used by tests, not an unmaintained tutorial
  golden.

## 22. Decisions intentionally deferred

- Whether pack assets are copied into a deployment cache or served in place.
- Localization bundle format.
- Content-version migration decorators versus explicit offline migration tools.
- Cross-character trading transaction model.
- Persistent campaign resources beyond holdings.
- Custom character parameter-authoring schema/UI.
- Pack signatures and sandboxing for third-party distribution.
- Hot reload in a development-only process.
- Independently factory-registering every action/condition/spell.

These decisions must not weaken the initial invariants: exact identities,
immutable versions, frozen registries, closed causal events, durable revision
history, and one canonical construction path.

## 23. Final acceptance criteria

The tranche is complete only when:

1. External manifested packs auto-load deterministically at startup.
2. Standalone, gateway, warm workers, replays, and SDK agree on content
   identity.
3. Supported items and creatures have one decorator/registry construction
   path.
4. Replaced central dictionaries, switches, unions, wrappers, and aliases are
   removed.
5. Player-visible actions/conditions/spells/items/creatures resolve through the
   content catalog.
6. The frontend no longer owns duplicated semantic lookup tables covered by
   descriptors.
7. Stored characters, holdings, deployments, and terminal settlement work
   across restart.
8. Loot is committed exactly once only after a clean terminal result.
9. Replays remain portable files and never mutate current character state.
10. No circular dependency, function-local import, hidden compatibility path,
    or unmeasured open defect remains.
11. Every pre-migration production content root and derived behavior has one
    measured destination or an explicit approved deletion; arbitrary import
    order cannot change the frozen inventory.
12. Every agreed SRD 5.1 item and creature source-ledger row is complete with
    exact provenance, constructible dependencies, and focused behavior tests.
    SRD 5.2/5.2.1 inspirations are labeled adaptations rather than silently
    changing the 5.1 rules baseline.
13. Actions, spells, conditions, traits, and handlers used by content have
    stable semantic identities and typed ownership/dependency edges; display
    names and Python paths are not authoritative identities.
