# Content, tests and retained archive audit — September 12, 2026

Read-only audit of `codex/recovery-design`, checkpoint `14b27f7`, including the
pending working-tree changes. No production/test edits or execution in this
audit. Recommendations below are dispositions for review, not an implementation
plan or permission to resume work.

## Coverage and evidence

The content scope is all 59 Python files / 27,030 lines in `dnd/content_system`,
`dnd/core/content` and `dnd/content`. Every file was text-scanned and AST-parsed;
module definitions, imports and suspicious-operation locations were inventoried.
Targeted semantic reads followed construction, installation, materialization,
identity, effect-metadata and character-composition owners and their consumers.
This is not a claim that every line of every grant table was independently
verified against D&D rules.

The repository-wide scan also covers all 378 files / 177,253 lines under `tests`
and 181 files / 87,512 lines under `to_archive`. Tests and archive received
exhaustive static scanning, with targeted test-owner reading below; they did not
receive exhaustive behavioral review or execution. The source ledger is
[SOURCE_SCAN_2026-09-12.csv](SOURCE_SCAN_2026-09-12.csv). Python parses had no errors.

Forty-nine of the 59 content files are unchanged against `16a6bfe`; the ten
changed files include pending removals and new item/behavior entries. The
content machinery described here largely survived July reconstruction.
Historical attribution does not justify its retention.

## C1 — Engine source authentication ran during built-in import

At checkpoint `14b27f7`, `dnd/content_system/builtin.py` imported the source-closure
resolver, walked Python dependencies and hashed their files, as well as checking
a reference document. This ran merely to import built-in content for the game.
The prior instrumented native startup measured 6.825s in the closure walk;
2,209 candidate searches led to 4,418 `is_file` calls. The unprofiled native
import was 10.789s total. These are distinct measurements, not additive timings.

**Purpose versus implementation:** explicit authored definitions and stable
behavior IDs are useful. Recursively proving the identity of locally shipped
Python before each process can construct an encounter is not required by the
in-process game or the user's record-once playback contract.

**Disposition:** the user already requested removal. Pending edits remove the
built-in source walk/hash and dead consumers instead of caching or deferring it.
Those edits remain uncommitted and incompletely validated. The retained static
closure helper still serves the separate external-pack audit; its presence must
not be confused with the removed built-in call path.

## C2 — Whole installed content identity still includes presentation metadata

`pack_loader.py::_content_set_digest` serializes every declaration's complete
`descriptor`, provenance and effect profile. `core/content/descriptors.py`
defines presentation fields for icons, portraits, sprites, tint, VFX, audio, UI
and equipped sprite layers. Descriptor text and those presentation fields
therefore participate in the same identity used by:

- `content_system/runtime.py::ContentSystemRuntime.install`;
- `core/content/runtime.py::install_runtime_behavior_binding_gateway`;
- `content_system/creature_bindings.py::CreatureRuntimeBinding`;
- retained server catalog/handshake and durable content consumers.

Changing descriptor presentation can change which installed content set the
runtime considers equivalent. Removing source hashing does not remove this
coupling. Conversely, changing a PNG that is not in this payload does **not**
automatically change this digest after source-hash removal.

**Disposition:** review the scope and need of this whole-set identity before
retaining it as mechanical compatibility. Explicit public appearance and active
equipment facts are necessary state; this finding does not argue for stripping
them from events. Renderer asset identity, mechanical definition identity and
replay input identity need not be one indivisible admission rule. No replacement
identity framework has been designed or implemented in this audit.

**Cost:** unisolated and not the remaining multi-second import source. Total
bootstrap execution after imports was about 0.018s in the prior native sample.
This is primarily a coupling and maintenance finding.

## C3 — Built-in bootstrap enters external-pack rollback machinery

`pack_loader.py::load_content_system` has no external modules to import when
`packs` is empty, yet unconditionally snapshots pack modules and engine globals,
removes pack modules, invalidates import caches, freezes the registry, compares
runtime-state tokens and invalidates caches again. `_snapshot_engine_runtime`,
`_clone_runtime_state`, `_runtime_state_token` and restore helpers know the engine's
private registries, ContextVars and GridMap internals through reflection.

With actual external packs, directory contents are hashed at discovery, again
before import, and after import; a static import-policy walker and process-state
rollback mechanism surround import. The rollback is infrastructure for that
optional loading mechanism, not a D&D rule. It should not determine the ordinary
built-in-only boot path. Registry construction through `builder.freeze` still
serves the built-in game and is distinct from this detour. Its knowledge of engine internals is already stale:
pre-stop tests encountered a missing `_entity_by_position` attribute in the cold
runtime check.

**Disposition:** remove the empty-pack detour when implementation resumes;
separately decide whether the retained external-pack product is still intended.
Do not repair its obsolete internals merely to turn old tests green. Do not
replace this machinery with another general-purpose guard. This audit has not
established the necessity of the external feature itself.

**Cost:** actual branch work is confirmed; its isolated time was not measured.
The earlier 0.018s bootstrap sample bounds its relevance in that small cold
scenario. It can traverse existing global container state, but no scaling
benchmark was run here.

## C4 — Data constructed internally is repeatedly serialized and revalidated

`core/content/recipes.py::ContentRecipe.create` hashes ref+parameters, then its
model validator immediately hashes them again. Creature materialization calls
`resolve_creature_recipe` (verify), then `runtime.materialize` → registry
`materialize` (verify), then `CreatureRuntimeBindingRegistry.bind` (verify).
Passing the recipe through a nested Pydantic model can also trigger its model
validator. These are explicit repeated checks of the same already-held recipe.

The declared frozen recipe still contains a mutable parameter dictionary.
Repeated verification compensates for that representation choice. Keeping exact
construction data is useful; hashing it at each internal handoff is a different
claim. External decode and mutation ownership should be assessed before keeping
these repeated checks. No synthetic tampering scenario was promoted to a game
requirement during this review.

`registration.py::compute_definition_contract_hash` generates model schemas for
factory/typed definitions; `_validate_bound_contract` recomputes their hashes.
Behavior-only hashes cover mode/kind/runtime-kind, not individual executable
spell semantics. The name "definition contract hash" must not be interpreted as
proof that the actual rule code is unchanged.

`descriptors.py::ContentDescriptor.from_spec`, for exact built-in icon bindings,
dumps an existing specification, constructs/validates a presentation model, reconstructs/validates a specification,
then dumps/validates the final descriptor. `condition_effect_population.py`
model-copies modified declarations and validates them again during cold admission.

**Disposition:** consolidation/removal candidates at internal construction
boundaries. Keep validation where a real input enters and where game legality is
owned. Do not hide repeated work with a cache. The prior profile measured 968
contract-hash calls at 0.050s cumulative, 126 schema generations at 0.040s and
557 declaration validators at 0.029s. These nested measurements are not additive
and do not explain the much larger Pydantic class-construction cost.

## C5 — Fixed catalog counts and a parallel description of condition mechanics

`builtin_inventory.py` requires exactly 312 behavior classes/IDs in multiple
import-time assertions. Mapping completeness/uniqueness and "must still contain
312" are different conditions. The latter is a historical census that makes
ordinary content additions require unrelated edits. Recent recovery changed the
count too; faithfully updating it perpetuated the premise.

`condition_effect_population.py` contains 2,060 lines describing condition
applications, removals, save/attack gates and dispositions alongside concrete
rule implementations. It imports the full behavior catalog, requires exhaustive
classification, patches declarations and supplies condition dependencies.
Searches found its profile consumers in registry validation, content-set digest
and retained server catalog; current game execution and presentation do not use
this table to execute or reduce conditions. Actual events remain the runtime
result. It is parallel static descriptive data, **not a second executing rules
engine**.

**Disposition:** fixed counts are removal candidates. The parallel profile table
needs a concrete current consumer/purpose before more ongoing synchronization
work is accepted. Authoring a useful catalog can warrant descriptive metadata;
its existence does not justify forcing all of its audit work into game boot.
Do not replace actual event reductions with predictions from this table.

## C6 — Retained durable character schema and unused materializer

`core/content/durable_characters.py` still defines the older 1,613-line durable
character/progression model, hashing item, holdings, character definition and
loadout revisions and checking nested integrity repeatedly. Current player
creation instead uses `content/characters/builds.py`, passive authored builds and
direct native grant composers. Imports of the durable model are in retained
server/directory/deployment code, not current `game/session.py` character creation.
Its presence alone does not prove a cost in current native startup.

`content_system/installed_creature_materialization.py` duplicates much of the
current creature materializer and documents its former structural-character
composition purpose. A search of current executable callers found none outside
the module. It survived the removal of its former owner. This is a concrete
orphan candidate; archive/test string references are not runtime consumers.

Encounter recipe and battlefield models have active scenario consumers as well
as retained server consumers. They cannot be classified wholesale as dead simply
because the durable character code is retained nearby. In particular,
`BattlefieldDefinition.content_digest` is a computed property that serializes and
hashes the whole definition including preview/title when accessed; unlike
`ContentRecipe`, it is not a stored field verified on construction. Its exact
call cadence and consumer purpose must determine any later change.

**Disposition:** keep retired durable/server paths outside current authority;
consider deletion of the unused duplicate adapter in a separately reviewed
cleanup. Retain authored battlefield/roster data while reviewing their
self-authentication machinery and identity granularity.

## C7 — Real composition and rule ownership worth preserving

Direct character builds own point buy, multiclass requirements, legal choices,
known/prepared spells, slots and actual native composition. Class/origin grant
receipts remember exactly which actions, modifiers, handlers and resources were
installed so removing a level or source does not erase unrelated grants. These
are game capabilities, not evidence of redundant state merely because they have
many lines or perform ownership checks.

`BehaviorBinding` carries primitive behavior/provider/root/owner facts frozen
into events. Handler/event lineage and provider identity have actual current
consumers. The current binder's tables and gateway can be reviewed as an
implementation, but the primitive causal identity contract must not be lost.
No runtime source hashing was found inside ordinary behavior binding.

Large grant files received static/purpose review, not a promise that every
helper or ownership check is optimal. No recommendation to replace them with a
new generic DSL or broad OOP framework follows from this audit.

## Tests can preserve the wrong premise

`HOW_TO_TEST.md` explicitly distinguishes observable behavior from private layout
and incidental serialization. Two sources of misleading test pressure and coupling
are visible in the retained testing structure:

1. `tests/conftest.py` imports full content bootstrap at collection and installs
   it in a session-autouse fixture. Even a pure projection or saved-byte replay
   test under this tree pays that import and receives installed global content.
   This is test-only coupling; it does not prove live replay secretly boots the
   engine. Fresh subprocess replay checks previously established its passive
   boundary independently.
2. `tests/architecture/test_content_recovery_cr0_evidence.py` tests exact counts,
   hashes of plan documents, historical source artifacts, and even a fixed digest
   of the maintained-node list. It is a historical evidence audit, not a test of
   gameplay. `test_178_authored_item_visual_inventory.py` pins exact source hashes
   and counts (77 categories / 205 variants); `test_183_content_icon_bindings.py`
   exercises exact digest and source-layout expectations. Such artifact checks
   may serve one-time provenance verification, but cannot justify doing the
   same work during play or block legitimate replacement of an old mechanism.
   These suites also contain useful behavior tests; for example, test_183
   checks actual declaration/binding behavior as well as artifact machinery.

Import direction tests express an explicit repository policy and can remain
architecture tests. Replayed subjective outcomes, event-only reconstruction,
interruption timing, native rule outcomes and visible gear changes are actual
behavior tests. Neither group makes runtime source attestation necessary.

No blanket deletion of tests is proposed. Review tests alongside the mechanism
whose purpose is being reconsidered, retaining the user's observable contracts.
The exhaustive scan did not classify the semantics of every individual test.

## Archive and non-code scope

No current production `to_archive` imports were found by the explicit reference
search. Its source remains tracked despite an ignore entry; ignored status does
not remove already tracked files. It is historical reference, not a template to
restore to make old server imports pass.

The remaining tracked executable suffix outside the Python/TS/JS ledger is one
archived shell API test; it was read, not run. The two HTML files and gallery CSS
are covered by the AI/presentation reviewers. Root also read `pyproject.toml`,
requirements and ignore configuration. Dependencies still combine game and
retained server libraries, but installation breadth alone is not proof those
libraries execute on each native turn.

Binary sprites, lockfile package metadata, 1,162 Markdown documents and every
JSON data row are not claimed as individually semantically audited. Their source
loaders, execution boundaries and relevant authored-data roles are covered.
The whole-source scan is a risk inventory, not a mathematical proof that every
unnecessary operation has been found.

## Content file coverage

Every row received source/AST scanning; findings above identify the semantic
owner reads. Lines describe the working tree at the audit stop.

| Source | Lines |
|---|---:|
| `dnd/content/__init__.py` | 1 |
| `dnd/content/characters/__init__.py` | 2 |
| `dnd/content/characters/barbarian_grants.py` | 1235 |
| `dnd/content/characters/builds.py` | 346 |
| `dnd/content/characters/class_definitions.py` | 1286 |
| `dnd/content/characters/fighter_grants.py` | 912 |
| `dnd/content/characters/origin_definitions.py` | 481 |
| `dnd/content/characters/origin_grants.py` | 1153 |
| `dnd/content/characters/premades.py` | 422 |
| `dnd/content/characters/progression.py` | 549 |
| `dnd/content/characters/sorcerer_grants.py` | 1324 |
| `dnd/content/items/__init__.py` | 1 |
| `dnd/content/items/authored_item_builders.py` | 745 |
| `dnd/content/items/authored_item_definitions.py` | 1142 |
| `dnd/content/items/environment_item_builders.py` | 324 |
| `dnd/content/items/item_loadouts.py` | 87 |
| `dnd/content_system/__init__.py` | 1 |
| `dnd/content_system/action_definitions.py` | 366 |
| `dnd/content_system/artifact_digest.py` | 210 |
| `dnd/content_system/behavior_bindings.py` | 291 |
| `dnd/content_system/bootstrap.py` | 51 |
| `dnd/content_system/builtin.py` | 56 |
| `dnd/content_system/builtin_inventory.py` | 155 |
| `dnd/content_system/cli.py` | 142 |
| `dnd/content_system/condition_definitions.py` | 564 |
| `dnd/content_system/condition_effect_population.py` | 2060 |
| `dnd/content_system/configuration.py` | 42 |
| `dnd/content_system/creature_bindings.py` | 88 |
| `dnd/content_system/creature_materialization.py` | 155 |
| `dnd/content_system/creature_possessions.py` | 84 |
| `dnd/content_system/icon_bindings.py` | 465 |
| `dnd/content_system/import_boundary.py` | 10 |
| `dnd/content_system/installed_creature_materialization.py` | 163 |
| `dnd/content_system/pack_loader.py` | 1790 |
| `dnd/content_system/reaction_definitions.py` | 256 |
| `dnd/content_system/runtime.py` | 126 |
| `dnd/content_system/spell_catalog_composition.py` | 202 |
| `dnd/core/content/__init__.py` | 6 |
| `dnd/core/content/battlefields.py` | 206 |
| `dnd/core/content/character_deployment.py` | 63 |
| `dnd/core/content/dependencies.py` | 48 |
| `dnd/core/content/descriptors.py` | 187 |
| `dnd/core/content/dragonborn.py` | 82 |
| `dnd/core/content/durable_characters.py` | 1613 |
| `dnd/core/content/effects.py` | 387 |
| `dnd/core/content/encounters.py` | 1075 |
| `dnd/core/content/icon_bindings_generated.py` | 3279 |
| `dnd/core/content/identities.py` | 91 |
| `dnd/core/content/inventory.py` | 219 |
| `dnd/core/content/materialization.py` | 81 |
| `dnd/core/content/origin_support.py` | 71 |
| `dnd/core/content/pack_contracts.py` | 163 |
| `dnd/core/content/provenance.py` | 129 |
| `dnd/core/content/recipe_presets.py` | 159 |
| `dnd/core/content/recipes.py` | 68 |
| `dnd/core/content/registration.py` | 613 |
| `dnd/core/content/registry.py` | 638 |
| `dnd/core/content/runtime.py` | 520 |
| `dnd/core/content/spatial_effect_definitions.py` | 45 |

## Independent conclusion review

The native anti-slop reviewer confirmed the recipe caller chain, orphaned
materializer and current direct character path. The report was corrected to
limit descriptor reconstruction to exact icon bindings and to criticize the
specific historical hash/count assertions instead of declaring whole test suites
invalid. The AI/server anti-OOP reviewer confirmed content identity coupling and
zero-pack work, with the explicit clarification that building the actual registry
is not part of the unnecessary external-pack detour. Neither review authorizes
implementation or establishes unmeasured timing.
