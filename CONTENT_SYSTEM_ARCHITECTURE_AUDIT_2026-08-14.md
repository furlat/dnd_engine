# Content System Architecture Audit

Date: 2026-08-14

Scope: executable Python source, JSON/TOML data discovered from code, runtime
introspection, and tests. No existing Markdown document was opened or used.
This is an architecture study only; no production or test code was changed.

## Executive verdict

Yes, the content system is substantially over-engineered.

The core mistake is not that the game has authored content. The mistake is that
`content_system` has become an umbrella for at least six different systems:

1. Stable identities and factories for reconstructing game objects.
2. A third-party Python plugin loader and pack authentication system.
3. Runtime attribution of actions, conditions, handlers, and their causal owners.
4. Persistent character creation, progression, loadout, and feature installation.
5. Encounter, roster, deployment, battlefield, and scenario composition.
6. Frontend asset selection and presentation catalog transport.

Only the first responsibility is the irreducible content kernel. Responsibilities
four and five are legitimate product domains, but they do not belong inside a
generic content framework. Responsibilities two, three, and six contain the
largest amount of speculative or duplicated architecture.

My rough engineering judgment is that more than half of the current content
surface can be deleted or moved out of the content kernel without reducing the
rules engine's capabilities. That is a judgment about responsibilities, not a
mechanical LOC target.

The correct direction is a hard cut, not an incremental attempt to make every
current abstraction cleaner.

## Quantitative shape

The directly identified production surface is:

- 80 Python files.
- 31,148 Python lines in `dnd/content_system`, `dnd/core/content`, and the two
  direct server content endpoints.
- 37 directly named content/character/encounter test files containing 16,576
  lines.
- 328 Python files directly import `dnd.content_system` or `dnd.core.content`:
  169 production files and 159 tests.

The frozen built-in registry currently contains:

- 712 declarations.
- 205 recipe presets.
- 2 authored sources.
- 0 external packs installed or present in the configured default pack root.
- 404 behavior-identity declarations.
- 221 factories.
- 87 typed definitions.

Declarations by major kind:

| Kind | Count |
| --- | ---: |
| Spell | 118 |
| Condition | 113 |
| Item | 112 |
| Action | 84 |
| Trait | 70 |
| Creature | 63 |
| Class feature | 62 |
| Spatial effect | 31 |
| Environment object | 15 |
| Starting equipment package | 14 |
| Species and variants | 13 |
| Reaction | 8 |
| Class, subclass, background, feat | 9 |

The registry contains 856 dependency edges. The largest edge families are
`grants_action`, `applies_condition`, `equips_item`, `grants_feature`, and
`grants_spell`. Only 46 declarations have general `related_content_refs`, so
the dependency model is driven primarily by validation and presentation
metadata rather than by a broadly used executable dependency graph.

Important code clusters include:

| Cluster | Direct Python lines | Architectural reading |
| --- | ---: | --- |
| Character domain and related definitions | about 14,053 | Mostly real domain complexity, badly located and too concentrated |
| Backend presentation/catalog glue | about 3,955 | Primarily frontend responsibility |
| Effect-profile mirrors | about 2,726 | Duplicates executable rules for catalog consumers |
| External pack extension layer | 2,382 production; 4,760 including direct tests | Speculative infrastructure with zero installed external packs |
| Scenario/encounter content contracts | about 1,594 | Real game-setup domain, not generic content infrastructure |
| Runtime behavior binding | 1,085 | Cross-cutting metadata authority embedded in engine execution |

These categories overlap slightly at their boundaries; they are intended to
show the shape, not serve as a deletion ledger.

## What the system currently does

### Declaration model

`ContentRef` carries:

- pack ID;
- definition kind;
- content ID;
- integer content version;
- a 64-character definition contract hash.

Definitions use three modes:

- `factory`: a Pydantic parameter model plus a Python callable;
- `behavior_identity`: metadata attached to an action, condition, spell,
  handler, trait, or feature class;
- `typed_definition`: structural Pydantic data such as a class, species,
  background, or feature definition.

Decorators attach declarations to Python objects using the private
`__dnd_content_declaration__` attribute. A hand-composed built-in inventory then
imports and concatenates definitions from many engine modules.

The idea of a stable content ID plus a construction recipe is sound. Treating
nearly every live rule behavior as a content declaration is where the boundary
begins to expand beyond what persistence requires.

### Startup and registry

Startup performs much more than registration:

1. It imports and assembles built-in declarations and presets.
2. It applies population passes that replace immutable declarations with
   additional condition/spatial-effect metadata.
3. It validates backend-owned icon bindings against a frontend asset index and
   ledger.
4. It computes a static Python import closure from one root module.
5. It hashes that closure plus data artifacts.
6. It discovers and validates external pack manifests.
7. It analyzes pack Python source through the AST and executes accepted packs
   inside a large cold-start transaction.
8. It validates content sources, dependencies, construction cycles, condition
   closure, spatial transitions, related references, and presets.
9. It freezes the registry and installs global runtime gateways.

The measured built-in artifact closure contains 205 Python files, approximately
131,140 Python lines, plus 6 data artifacts. A clean bootstrap measurement took
approximately 16.2 seconds and reached approximately 246 MB maximum resident
memory in this workspace.

This means a content bootstrap authenticates a large portion of the engine, not
just content data. The content set digest has effectively become a second engine
build identity.

### Runtime materialization

`ContentRecipe` is a content reference plus JSON parameters and a digest.
Factories validate the parameter object and construct items, creatures, or
spatial effects. This is the useful center of the design: durable state can
refer to a stable constructor without serializing a Python object graph.

The useful mechanism is surrounded by type-specific wrappers and global state:

- item materialization and `ITEM_RUNTIME_BINDINGS`;
- creature materialization and `CREATURE_RUNTIME_BINDINGS`;
- spatial-effect materialization wrappers;
- the process-global `SERVER_CONTENT_SYSTEM_RUNTIME`;
- process-global engine gateways installed when the content runtime starts.

Runtime binding records keep content references, recipe information, origins,
and durable lineage outside objects in global registries. Some related identity
also lives on the object itself. This splits ownership and makes isolation,
cleanup, tests, and multiple games in one process harder than necessary.

### Runtime behavior attribution

Actions, conditions, and handlers can receive a four-part `BehaviorBinding`:

- their own definition reference;
- the definition that provided them;
- an optional durable root reference;
- the runtime owner UUID.

The binding system uses global and context-local gateways to infer causal
providers while actions and event handlers create child behaviors. It validates
provider reachability through the content dependency graph and captures handler
evidence for later presentation.

This is sophisticated, but it is sophisticated in the engine's hottest and most
central path. Action registration/discovery and handler admission can now depend
on a frozen content registry being installed. Content metadata has become an
execution precondition rather than optional attribution.

### Character domain

The character subsystem includes:

- immutable definition, holdings, and loadout revisions;
- per-record integrity digests;
- species, variants, backgrounds, classes, subclasses, levels, choices,
  prerequisites, spell entitlements, and appearance selections;
- a 2,742-line build validator;
- a deterministic grant schedule;
- class/origin-specific grant appliers;
- reversible installation receipts for modifiers, proficiencies, actions,
  handlers, resources, senses, immunities, spellcasting, and other structure;
- cold materialization into an engine `Entity` followed by durable inventory
  hydration.

Most of this is not fake complexity. A persistent character builder with
multiclassing, respec/recomposition, and exact loadout reconstruction genuinely
needs a domain model and validation. The architectural problem is that it is
implemented as content infrastructure and tightly coupled to the global content
runtime.

There is also excessive integrity ceremony: nested immutable Pydantic records
frequently store a digest of their own serialized fields and revalidate it on
construction. When the database, application, and worker all operate within one
trusted product boundary, these digests provide much less protection than their
cost and terminology imply.

### Encounter and battlefield domain

`dnd/core/content/encounters.py` defines rosters, owned-character sources,
authored creature sources, grants, starting damage and conditions, deployment
zones, initiative opening policy, and encounter recipes. Battlefields have
their own definition and digest model.

These are game creation/scenario composition contracts. They belong close to a
future `Game`/`Encounter` owner. Calling them content obscures the architectural
boundary and allows the generic registry to become the dependency hub for game
creation.

## Where the architecture breaks apart

### 1. The external pack loader is a product with no current customer

The pack subsystem implements manifest discovery, semantic versions, dependency
ordering, static import analysis, restrictions on dynamic code and imports,
filesystem hashing, `sys.path`/`sys.modules` management, and snapshot/restore of
many engine registries. It requires a cold runtime and attempts to prove that a
pack did not mutate the repository while loading.

That is a trusted Python plugin platform and partial sandbox simulator. It is
not a normal content loader.

There are no installed external packs. All current content is trusted built-in
Python. Keeping this infrastructure today charges every content change and test
for a hypothetical extension ecosystem.

Verdict: delete now. Reintroduce an extension format later only when a concrete
external authoring use case exists. At that point, prefer declarative data or a
separate process over importing third-party Python into the engine.

### 2. The backend owns renderer assets

Backend content presentation includes icon, portrait, sprite, visual variant,
tint, VFX profile, audio, UI group, and equipment render-layer keys. The backend
also contains a 2,699-line generated icon binding table and validates a checked-in
NeuroClient asset index, asset paths, asset hashes, decisions, and evidence.

World/player replication sends hashed `SafeContentPresentationRef` values. The
frontend must resolve those hashes against a server catalog. The catalog repeats
presentation in declaration entries, recipe presets, and a hash-addressed safe
presentation table.

The measured serialized catalog is approximately 2.27 MB for 671 exposed
entries, 205 presets, and 868 safe-presentation rows. The compact manifest is
only approximately 2 KB.

This is a direct frontend-responsibility leak. It couples backend startup,
content identity, server DTOs, and engine digests to the current renderer asset
library.

Verdict: hard-delete backend asset bindings, ledgers, generated mappings, asset
hash validation, and safe-presentation hash indirection. Replicate stable
semantic IDs. Let the frontend map those IDs to icons, sprites, audio, and other
presentation. A small rules-facing display name or description may remain if it
is useful outside the renderer.

### 3. Effect profiles are a second rules engine for presentation

`condition_effect_population.py` manually describes what spells, actions, and
reactions apply which conditions, to which targets, behind which gates and
branches. `spatial_effect_population.py` does the same for spatial effects.

The current registry has 143 condition-effect profiles, 148 lifecycle records,
and 194 `applies_condition` edges. The non-validation runtime consumer of the
condition-effect profile is the content catalog; actual mechanics still execute
inside actions, spells, handlers, and conditions.

Therefore the backend maintains two descriptions of a rule:

1. executable mechanics;
2. a manually synchronized static forecast for catalog/tooling presentation.

The population passes even rebuild immutable declarations during cold startup
to attach this mirror.

Verdict: delete the static forecast layer unless one specific engine mechanic
requires a small part of it. Preserve only semantic condition IDs/tags needed by
actual rule operations such as immunity, cleansing, or lifecycle behavior.
Generate player-visible explanations from frontend copy or from deliberately
small rule DTOs, not an attempted declarative replica of execution.

### 4. Contract hashes authenticate shape, not behavior

`definition_contract_hash` hashes declaration mode, kind, runtime behavior kind,
and a Pydantic schema when applicable. It does not hash the implementation of a
factory, action, spell, condition, or handler. It also does not authenticate most
descriptor metadata.

Runtime inspection found only 70 unique definition contract hashes for 712
declarations:

- 404 behavior declarations share only 9 hashes;
- 221 factories share 52 hashes;
- 87 typed definitions share 9 hashes.

For example, many distinct spells share one hash because they have the same
behavior family and declaration shape. The hash can detect an API-schema change,
but not a mechanics change. Calling every reference an "authenticated contract"
overstates the guarantee.

Separately, the built-in artifact digest hashes 131,000+ lines of transitive
Python. That detects implementation changes far outside the narrow definition
contract, but at the cost of coupling content identity to a broad engine source
closure.

These two hash layers do not form a clean versioning model. One is too weak to
identify behavior and the other is too broad to identify content.

Verdict: replace both with ordinary explicit versioning:

- a stable semantic content ID and content revision for persisted recipes;
- one explicit ruleset/engine build version for worker compatibility;
- migrations when a persisted schema or semantic rule actually changes.

Canonical hashes may still be useful for cache keys or corruption detection,
but they should not be embedded into every domain identity and described as the
authority for semantic compatibility.

### 5. Runtime attribution has invaded engine execution

The behavior-binding system solves real presentation/diagnostic questions:
which feature granted an action, which item produced a handler, and what reaction
changed an event. The solution is too global and too strict.

The engine now contains content-specific gateways, context variables, provider
reachability validation, binding at action/handler admission, and fail-closed
paths when an authored behavior lacks the correct content environment. This
makes the rules engine unable to remain a simple executor of already-constructed
objects.

The distinction among `definition_ref`, `provided_by_ref`, `origin_root_ref`,
and `runtime_owner_uuid` is useful in some diagnostics, but it should be data
owned by the game or action source—not a global authority required by every
engine behavior.

Verdict: reduce the engine-facing surface to optional stable semantic identity
and direct source ownership. Capture richer attribution in `Game`/`Encounter`
when commands, grants, or events are created. Engine action execution and event
dispatch must remain valid without a content catalog installed.

### 6. Process-global state conflicts with multiple games

The system installs one `SERVER_CONTENT_SYSTEM_RUNTIME` per process generation,
one engine behavior gateway, one spatial-effect gateway, and global item and
creature runtime-binding registries.

That ownership model is the opposite of the intended future server: a server
that creates games and coordinates gameplay while each game owns its runtime
state. Process-global content makes parallel games implicitly share authority,
forces reset machinery into tests, and prevents different game/ruleset instances
from being isolated naturally.

Verdict: `Game` should own its content registry/reference and runtime lineage.
`Encounter` should own encounter-local bindings and objects. The server should
own a collection of games, not the content mechanics used by every game.

### 7. Character and scenario domains are hidden inside infrastructure

The 14,000-line character cluster and roughly 1,600-line scenario cluster make
the content system appear irreducibly huge. They are not generic registry code;
they are product domains.

This misplacement has two effects:

- domain code must speak in generic content declarations, hashes, packs, and
  registries even where a direct typed dependency would be clearer;
- every consumer imports the content system because the content system has
  become the only route to characters, encounters, and battlefields.

Verdict: move them, do not blindly delete them. Character revisions, choices,
validation, and grant application belong in a character domain. Rosters,
deployment, battlefields, and opening policy belong in a scenario/game-creation
domain.

### 8. Presets duplicate identity and metadata

A recipe preset has its own pack ID, preset ID, version, contract hash,
descriptor, provenance, and embedded self-digesting recipe. There are 205
presets. This is a second catalog layer around exact recipes.

Named built-in recipes are useful. A fully authenticated parallel identity
hierarchy is not necessary while all content is built-in and trusted.

Verdict: make presets a simple map from a semantic preset ID to a recipe and
optional label. Do not give them a second contract protocol.

## What is worth keeping

The hard cut should preserve these capabilities:

1. Stable semantic IDs for definitions that appear in persisted data or network
   commands.
2. Typed parameter validation for factories.
3. Recipes for reconstructing items, creatures, spatial effects, and character
   possessions.
4. A small registry mapping IDs to factories or typed rule definitions.
5. Uniqueness checks and clear failure for an unknown ID or invalid parameters.
6. Persistent character definitions, holdings, loadouts, build validation, and
   deterministic materialization.
7. Encounter/scenario recipes, but under game creation rather than generic
   content infrastructure.
8. Licensing/source metadata where legally or operationally useful, stored as
   cold authoring/catalog data rather than carried through hot runtime objects.
9. One explicit engine/ruleset compatibility version where persistence or
   worker coordination truly requires it.

The important distinction is that stable identity and deterministic
reconstruction are valuable. Cryptographic ceremony, plugin simulation,
presentation ownership, and global runtime authority are not prerequisites for
those properties.

## Proposed target architecture

```text
dnd/content/
    ids.py            # stable ContentId(kind, key, revision)
    recipes.py        # Recipe(content_id, parameters)
    registry.py       # ContentId -> factory or typed definition
    builtins.py       # explicit trusted built-in registration

dnd/characters/
    contracts.py      # definition, holdings, loadout revisions
    definitions.py    # class/species/background/feature data
    validation.py     # build validation and preview
    grants.py         # install/remove source-owned character structure
    materialize.py    # character -> Entity + possessions

dnd/scenarios/
    rosters.py
    battlefields.py
    deployment.py
    recipes.py

dnd/game.py
    owns registry reference, entities, recipes, runtime lineage, encounters

server/
    creates and stores Game instances
    authenticates players and routes commands
    coordinates game lifecycle and replication
    does not own renderer assets or game mechanics

frontend/
    maps semantic IDs to icons, sprites, audio, VFX, grouping, and copy
```

The future-proofing cost of retaining a namespace in `ContentId` is small. It
does not require retaining the external pack runtime. A possible identity is:

```python
ContentId(kind="item", key="srd.long_sword", revision=1)
```

The built-in registry can be ordinary explicit registration:

```python
registry.register(LONG_SWORD_ID, LongSwordParameters, create_long_sword)
```

Materialization should be game-owned:

```python
item = game.content.create(recipe, ItemContext(owner_id=character.id))
```

The created object can retain its recipe/content ID directly when persistence
needs it. Encounter-local correlation and source lineage should live in the
game/encounter, not process-global registries.

## Recommended hard-cut order

### Cut 1: Remove the unused extension platform

Delete external pack discovery, manifest/API contracts, CLI/configuration,
AST/import policing, repository mutation checks, and cold snapshot/restore
logic. Bootstrap trusted built-ins directly.

Why first: this removes a self-contained speculative branch and dramatically
simplifies the meaning of startup without changing game rules.

### Cut 2: Remove frontend presentation from the backend

Delete generated icon bindings, frontend asset indexes and ledgers, asset paths
and hashes, presentation-safe hash references, and renderer keys from backend
content contracts. Change replication to stable semantic content IDs.

Why second: this establishes the desired backend/frontend boundary and removes
presentation data from content identity before other refactors.

### Cut 3: Remove duplicated effect forecasts

Delete condition/spatial population passes and catalog-only effect profiles.
Keep only executable mechanics and the minimal semantic tags used by rules.

Why third: this eliminates the largest duplicated rule description and removes
many dependency edges before registry simplification.

### Cut 4: Collapse identity and digest layers

Replace definition hashes, preset hashes, source-closure artifact hashes, and
most nested record hashes with semantic IDs, explicit revisions, and an engine
ruleset version. Preserve a hash only where there is a demonstrated cache or
corruption-detection need.

Why fourth: doing this after the first three cuts avoids designing a new version
scheme for systems that should disappear.

### Cut 5: Move ownership into `Game`/`Encounter`

Remove process-global content/runtime binding ownership. A game receives a
registry and owns materialization lineage. An encounter owns its live objects
and attribution. Server lifecycle code creates and coordinates games.

Why fifth: the remaining registry will be small enough to inject explicitly,
and the ownership change can be tested with two isolated games in one process.

### Cut 6: Reduce behavior binding to direct optional attribution

Remove registry-required gateways and provider-context inference from engine
admission/dispatch. Store semantic definition/source IDs directly on actions,
conditions, grants, or commands when needed. Collect diagnostic evidence in the
game layer.

Why sixth: it touches engine execution broadly, so it is safer after presentation
and registry consumers have already been removed.

### Cut 7: Relocate character and scenario domains

Move character and scenario contracts out of `core/content` and
`content_system`. Split the character validator by concern, but preserve its
behavior. Move encounter/battlefield construction next to `Game` creation.

Why last: this is mainly a boundary and maintainability refactor. Doing it after
the hard deletions prevents mechanically moving obsolete infrastructure.

## Testing surface after the cut

Tests should be deleted when their asserted product no longer exists, not
rewritten to preserve dead architecture.

Delete tests whose only purpose is:

- external pack manifests, loader transactions, import policing, pack CLI, or
  pack API compatibility;
- backend icon ledgers, exact frontend asset hashes, safe presentation catalogs,
  or presentation-reference joins;
- condition/spatial effect forecast completeness and catalog mirroring;
- definition/preset/source-closure hash exactness;
- global runtime singleton installation and reset behavior;
- dependency-graph reachability used only for behavior attribution.

Preserve or rewrite tests around actual product behavior:

- stable IDs are unique and unknown IDs fail clearly;
- recipe parameters validate and round-trip through persistence;
- item, creature, and spatial-effect factories construct the expected engine
  objects;
- character definitions/holdings/loadouts round-trip and reject invalid builds;
- feature grants install and remove exact modifiers/actions/resources;
- persisted possessions rehydrate with correct state and equipment placement;
- scenario recipes create the intended roster, battlefield, deployment, and
  opening state;
- two games in one process do not share objects, bindings, registries, or
  mutable runtime state;
- frontend-facing replication exposes stable semantic IDs and no renderer asset
  requirements;
- engine rules execute correctly without a global content catalog installed.

The test strategy should move from proving infrastructure invariants to proving
construction, persistence, isolation, and gameplay outcomes.

## Risks and cautions

### Persistence compatibility

Content refs and digests are stored in game records, character revisions,
holdings, loadouts, encounter recipes, and worker compatibility contracts. A
hard cut needs an explicit one-time migration or a deliberate database reset.
Do not keep compatibility facades indefinitely; translate old records at the
storage boundary or declare them obsolete.

### Character grants

Do not delete reversible character grant receipts merely because they are
verbose. They solve real removal/recomposition problems. Simplify their types
and ownership only after preserving rollback behavior with tests.

### Rules versus presentation metadata

Some apparent presentation data may participate in rules—for example equipment
slot identity or a condition category used by immunity/cleansing. Keep semantic
rules data. Remove renderer-specific assets, ordering, color, icon, audio, VFX,
and frontend grouping.

### Licensing and provenance

The SRD/Neurodragon source records may have legitimate attribution value. The
recommendation is not to discard legal/source metadata; it is to remove it from
hot content identity, runtime bindings, and duplicated transport payloads.

## Final assessment

The content system began with a good need—stable authored identity and reliable
reconstruction—but accumulated solutions for hypothetical third-party plugins,
cryptographic-style authenticity, frontend asset delivery, semantic diagnostics,
and multiple product domains. The abstractions reinforce each other, which makes
the whole system look indivisible. It is divisible.

The clean center is small:

```text
semantic ID + typed parameters + factory/definition + explicit revision
```

Characters and scenarios should remain as first-class domains around that
center. Plugins, renderer assets, effect mirrors, global binding authority, and
layered contract hashes should not.

The proposed hard cuts align with the broader server direction: the server
creates games and coordinates access; a `Game` owns gameplay state and content
construction; an `Encounter` owns live encounter state; the frontend owns
presentation.
