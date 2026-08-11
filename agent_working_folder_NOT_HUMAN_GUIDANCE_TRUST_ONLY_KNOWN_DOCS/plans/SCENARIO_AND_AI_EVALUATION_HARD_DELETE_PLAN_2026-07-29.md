# Scenario and AI Evaluation Hard-Delete Plan

**Date:** 2026-07-29  
**Status:** complete; frozen schema-3 backend/frontend pair restored and all
retained cleanup, architecture, policy, and latency gates are green  
**Decision owner:** project architect  
**Decision:** abandon the Elo, tournament, gauntlet, promotion, config-ladder,
dashboard, and evaluation-artifact platform. Preserve authored encounter
content and focused AI gameplay tests only.

## 1. Outcome

There will be one encounter construction path:

```text
authored or saved roster selections
              +
    battlefield and deployment
              ↓
       exact EncounterRecipe
              ↓
 canonical compatibility validation
              ↓
   assemble_encounter_recipe(...)
              ↓
           Encounter
```

AI gameplay validation will be normal test code under `tests/ai/`. It will
start games through the same compose/start/runtime path as the product. It will
not own an alternate arena model, direct entity factories, a ratings database,
an experiment scheduler, or production HTTP watcher routes.

## 2. Why this deletion is safe

The public game-creation path has already been hard-cut to canonical encounter
recipes. The old evaluator is not the product runtime.

The evaluator still contains useful authored *data*, but its infrastructure is
not required to play, host, replay, inspect, or persist a game:

- `ai/evaluation/` contains roughly 55 Python files and 18.6 KLOC. The
  rating/evaluation modules have no product/server consumer outside the
  evaluator itself. Two non-rating concerns—live agent-observer projection and
  Direct Codex evidence—are currently misplaced there and must be separated
  before the package is deleted.
- `dnd/scenarios/ai_validation_arenas.py` contains a second direct construction
  path for 38 arenas.
- `dnd/scenarios/evaluation/` contains an obsolete intermediate ontology that
  is converted to canonical recipes during import.
- server gauntlet routes expose the abandoned evaluator rather than game
  runtime behavior.
- the Elo, promotion, gauntlet, and evaluator evidence directories are not
  game replays or player-profile data.

The migration must preserve intentional scenario mechanics. It must not
preserve the abandoned infrastructure merely because tests currently import
it.

## 3. Exact retain/delete boundary

### 3.1 Retain

Retain these product/gameplay facts:

1. All 58 selectable `EncounterRosterRecipe` records.
   - Nine are not referenced by the 38 current preset encounters, but remain
     useful selectable content.
2. All 38 authored `EncounterRecipe` records and their stable product IDs.
3. Nine battlefield definitions and their runtime builders.
4. Nine reusable neutral deployment formations.
5. The 38 encounter-specific deployment formations, owned by their encounters
   rather than advertised as generic formations.
6. Exact roster member order, creature `ContentRef`s, recipe parameters,
   deployment roles, controller-independent identities, and faction placement.
7. Deliberate `EncounterSetupEffect` facts:
   - starting damage and resources;
   - conditions and affinities;
   - extra actions, spells, reactions, items, and equipment;
   - scenario-specific object or environmental state.
8. Canonical encounter compatibility and assembly.
9. Current native and registered-provider AI policy/runtime architecture.
10. Replays, replication, combat logs, summaries, profile history, and normal
    game-directory persistence.
11. Focused AI gameplay and server lifecycle tests.

### 3.2 Delete

Delete these concepts and their implementations:

- `ValidationArena` and `ValidationArenaSpec`;
- all 38 direct arena builder functions;
- `ActorBlueprint` and its subclasses;
- `SideConfigurationSpec`;
- old `DeploymentSpec`;
- `LegacyScenarioRecipe`;
- rating/portability/source-arena metadata;
- evaluator-specific apparel repair;
- arena manifests;
- tournament and Elo models, schedules, ledgers, summaries, reports, and
  dashboards;
- config-ladder and promotion workers;
- gauntlet runners, watchers, artifacts, routes, and SSE streams;
- rating/evaluation artifact capture/read models;
- evaluation-only CLI entry points;
- conversion/parity tests whose only owner is the retired ontology.

Delete the following runtime surfaces after their retained facts have canonical
owners:

- the rating/evaluation contents of `ai/evaluation/**`, after the active
  agent-observer and Direct Codex boundaries are relocated or separately
  retired;
- `ai/external_selfplay.py`;
- `ai/validation_harness.py`, after any generally useful test helper is moved
  beneath `tests/`;
- `dnd/scenarios/ai_validation_arenas.py`;
- `dnd/scenarios/evaluation/**`;
- `server/agent_protocol/gauntlet.py`;
- `server/gauntlet_event_stream.py`;
- `/ai/gauntlets/**` routes and related proxy allowlisting;
- dead rating repository/contracts/tables;
- evaluation-only generated SDK models.

`dnd/scenarios/__init__.py` remains only as an empty/light package marker. It
must not eagerly import authored content, builders, `Entity`, server modules, or
the content bootstrap.

### 3.3 Delete immediately during the first safe tranche

These have no retained semantics and can be removed before the larger content
migration:

- `dnd/scenarios/evaluation/compatibility.py`, after its lone old test is
  replaced with canonical compatibility coverage;
- the six unused helpers in `server/arena_mode.py`:
  `entity_by_name`, `floor_object_names`, `action_template_names`,
  `inventory_item_names`, `equipped_item_name`, and `normalize_uuid`;
- unused `get_legacy_recipe()`;
- unused `AUTHORED_ROSTER_CATALOG_METADATA`;
- the duplicated `kind` declaration on `OwnedCharacterRosterSource`.

### 3.4 Do not conflate with this work

- `server/agent_protocol/observation_legacy.py` belongs to Direct Codex artifact
  migration, not the gameplay evaluator. Remove it only if the old artifacts
  are also deliberately abandoned.
- `ai/evaluation/agent_observer_projection.py` and
  `ai/AI_AGENT_OBSERVER.html` are active debugging/telemetry surfaces, not Elo.
  Move the Python projection to a neutral `ai/telemetry/` owner and preserve
  its focused tests.
- `ai/evaluation/direct_codex_artifacts.py` is not part of Elo. Move it under
  the Codex-tooling/telemetry owner if current artifact capture remains useful;
  retiring its historical artifacts is a separate explicit decision.
- Historical SQLite migration files are immutable history. Add a forward
  migration that drops unused rating tables; do not rewrite old migrations.
- Content-system migration ledgers are not alternate gameplay construction
  paths.
- Book/tutorial artifacts are explicitly outside this task.

## 4. Canonical authored-content shape

### 4.1 Battlefield contract

Move the cold public battlefield contract out of the evaluation package into a
dependency-neutral leaf:

`dnd/core/content/battlefields.py`

It owns a `BattlefieldDefinition` containing only product facts:

- `battlefield_id`;
- title;
- width and height;
- ambient light;
- typed cold preview cells/objects;
- capabilities needed for compose/preview validation;
- mechanical revision and authenticated content digest.

The public SDK must not expose:

- Python builder IDs;
- source arena IDs;
- rating portability;
- reverse deployment lists;
- evaluator ancestry.

Runtime grid/item builders move to ordinary scenario modules and are held in a
private registry keyed by exact battlefield ID. A definition must have exactly
one builder, and a builder must have exactly one definition.

### 4.2 Authored rosters

Author the existing roster inventory directly as
`EncounterRosterRecipe` values. A helper may construct canonical records, but
there must be no intermediate Pydantic blueprint hierarchy.

Suggested owner:

`dnd/scenarios/authored_rosters.py`

Each member directly owns:

- stable member ID;
- exact `ContentRecipe`;
- deployment role;
- ordered scenario setup effects.

Hero/monster side kinds, rating exclusions, source arenas, and warnings are not
carried forward.

### 4.3 Deployments

Suggested owner:

`dnd/scenarios/authored_deployments.py`

Publish only the nine genuinely reusable neutral deployments. Keep exact zones,
ordered slots, role constraints, and battlefield identity.

An encounter-specific formation belongs inside its `EncounterRecipe`; it is
not made public as a reusable deployment merely because the old evaluator gave
it an ID.

### 4.4 Authored encounters

Suggested owner:

`dnd/scenarios/authored_encounters.py`

Author all 38 encounters directly as canonical `EncounterRecipe` records.
`dnd/scenarios/encounter_catalog.py` becomes a small aggregator/index over
already-canonical records. It performs no conversion and imports no evaluator
model.

### 4.5 Wardrobe and visual identity

Ordinary creature appearance belongs to creature/build content:

- bestiary content owns bestiary wardrobes;
- configured SRD creatures own their wardrobes;
- class build content owns default apparel/holdings.

Remove `evaluation/wardrobes.py`, `ApparelGrant`, and wrappers that repair
ordinary apparel after creature construction.

Encounter setup effects may still grant genuinely scenario-specific equipment
or consumables. They must not repair a creature's normal visual identity.

## 5. AI validation becomes tests

### 5.1 No production self-play framework

Do not retain or rename `external_selfplay.py` as another production framework.
Extract only the smallest reusable fixtures required by tests, under
`tests/ai/support/`.

The tests must use:

- canonical catalog/compose;
- the exact normalized `EncounterRecipe` returned by compose;
- normal start/join/activate semantics;
- normal server-native or registered-provider policy assignment;
- normal replication, combat-log, and terminal summary surfaces.

### 5.2 Maintained AI test matrix

Keep the matrix small and meaningful:

1. native versus native;
2. native versus registered external provider;
3. registered external versus registered external;
4. multiple characters controlled by distinct policy assignments;
5. Human, Codex, and AI controller ownership remains per member;
6. no Human actor is autonomously executed or ended;
7. AI reaches a legal action or a typed terminal/no-action result;
8. an actual match advances and reaches a terminal result within a bounded
   action/turn budget;
9. subjective replication and combat logs cover executed AI actions;
10. provider capacity, registration, fencing, timeout, and teardown remain
    focused protocol tests.

These are tests of AI gameplay and provider integration. They do not calculate
ratings or produce long-lived experiment artifacts.

### 5.3 Preserve unique mechanics assertions

Before deleting the large arena suites, inventory each explicit assertion and
move every unique gameplay assertion to a canonical owner. Examples include:

- terrain and traversal;
- environmental objects and interactions;
- starting positions and initiative/opening policy;
- equipment, inventory, class resources, actions, spells, and reactions;
- conditions, affinities, resistances, and vulnerabilities;
- hazards, light, doors, and special scenario setup.

Do not preserve accidental object snapshots or obsolete defaults. The direct
and canonical constructors have already drifted—for example, an old standard
Sorcerer received spells not present in the canonical selected build. The
source of truth is the intended semantic assertion, not byte-for-byte parity
with the retired constructor.

## 6. Implementation tranches

### Tranche A — Freeze the retained behavior

1. Build a ledger of the 58 rosters, 38 encounters, nine battlefields, and
   retained deployment formations.
2. Replace old-model comparison tests with direct canonical semantic tests.
3. Move every unique arena mechanic assertion onto canonical assembly.
4. Add cold-preview-versus-built-battlefield parity.
5. Add import-boundary and forbidden-dependency tests before deleting modules.

No production contract changes occur in this tranche.

### Tranche B — Remove immediate dead code

1. Make `dnd.scenarios` imports light.
2. Delete old compatibility and update its test owner.
3. Delete unused arena-mode helpers, metadata, lookup functions, and duplicate
   construction statements.
4. Verify focused scenario and architecture tests.

### Tranche C — Direct-author canonical content

1. Add the neutral battlefield leaf and private runtime builder registry.
2. Direct-author canonical rosters.
3. Direct-author reusable deployments.
4. Direct-author the 38 encounters.
5. Move wardrobe ownership to creature/build content.
6. Change the encounter catalog to indexing only.
7. Prove all retained content assembles and previews.

### Tranche D — Delete the parallel scenario runtime

1. Migrate remaining tests and fixtures from `create_ai_validation_arena`.
2. Delete all direct arena builders.
3. Delete the old evaluation ontology and converters.
4. Delete evaluation wardrobes and legacy compatibility.
5. Add a static rejection gate for every retired model/import.

### Tranche E — Delete the evaluator platform

1. Move the few retained AI gameplay cases into `tests/ai/`.
2. Move active agent-observer and retained Direct Codex evidence code to their
   neutral owners, then delete the remaining `ai/evaluation/**` tree,
   `ai/external_selfplay.py`, and the unused production validation harness.
3. Delete gauntlet HTTP/SSE/contracts and proxy allowances.
4. Delete rating repository/contracts and add a forward SQLite migration that
   removes rating tables.
5. Delete rating/Elo/gauntlet/promotion/config-ladder tests, CLIs, reports, and
   tracked generated dashboards.
6. Add OpenAPI and source scans proving these surfaces are absent.

### Tranche F — One generated-contract hard cut

After Python models and population are closed:

1. bump the game-creation catalog schema for `BattlefieldDefinition`;
2. remove evaluation-only public DTOs and fields;
3. regenerate Python and TypeScript contracts once;
4. run generator check, SDK build/tests, and exact source/hash gates;
5. notify NeuroClient with one frozen handoff;
6. restart the backend only after frontend adaptation is green.

No aliases, V2 routes, compatibility fields, or dual model families are added.

### Tranche G — Remove disposable local evidence

Only after implementation gates are green, remove ignored local evaluator
evidence:

- roughly 4.8 GB of Elo evidence;
- roughly 261 MB of promotion evidence;
- roughly 303 MB of generic evaluator runs;
- roughly 3.2 MB of gauntlet evidence.

This data is not profile SQLite state and not game replay data. Report exact
paths and sizes immediately before deletion. Treat the approximately 976 MB of
Direct Codex artifact evidence as a separate explicit decision.

## 7. Required regression gates

### 7.1 Content and mechanics

- exact roster/member ledger;
- all 58 rosters materialize;
- all 38 encounters assemble;
- all nine battlefield definitions have exact builders;
- preview matches built terrain/light/objects/hazards;
- retained setup effects are asserted explicitly;
- every creature projects exact content identity and safe visual loadout;
- every reusable deployment has valid distinct zones and walkable slots;
- encounter-specific formations remain owned by their encounter.

### 7.2 Product/runtime

- standalone catalog → compose → preview → start;
- hosted catalog → compose → preview → start;
- owned-character rosters and saved rosters;
- ordered 1..N member controller assignment;
- game summary, replay, combat log, and subjective replication;
- lifecycle/reset/teardown.

### 7.3 AI

- native/native;
- native/external;
- external/external;
- per-character external policies and isolation;
- Human/Codex/AI ownership;
- bounded match progress and terminal outcome;
- action/presentation/combat-log delivery;
- provider fencing, capacity, timeout, and teardown.

### 7.4 Architecture

Reject these imports/tokens outside immutable migration notes:

- `ai.evaluation`;
- `ai.external_selfplay`;
- `dnd.scenarios.evaluation`;
- `ai_validation_arenas`;
- `ValidationArena`;
- `ActorBlueprint`;
- `SideConfigurationSpec`;
- `LegacyScenarioRecipe`;
- old `DeploymentSpec`;
- `hero_configuration_id`;
- `monster_configuration_id`;
- gauntlet/Elo/promotion public DTOs and routes.

Also prove:

- no function-local import or `TYPE_CHECKING` workaround was added;
- `import dnd.scenarios` does not import entities, runtime builders, server
  modules, or the content bootstrap;
- cold scenario/content model imports remain under a deterministic time/RSS
  budget.

### 7.5 Tooling

Following repository guidance, run test files individually rather than invoking
unbounded `pytest`:

- focused scenario/content tests;
- focused game creation and hosted gateway tests;
- focused replay/replication tests;
- all maintained files under `tests/ai/`;
- architecture tests;
- Pyright;
- generator `--check`;
- TypeScript SDK build and tests;
- diff check.

Every discovered open defect receives a deterministic regression and
`KNOWN_ISSUES.md` entry before it remains open.

## 8. Test deletion policy

Delete a test if its only subject is:

- Elo/rating math or persistence;
- experiment scheduling/resume;
- gauntlet watchers;
- dashboards/reports;
- abandoned rating/evaluation artifact schemas;
- old conversion parity;
- exact incidental collection counts.

Before deleting a test, move any unique gameplay, privacy, lifecycle,
performance, protocol, or content assertion to a maintained canonical test.

Tests that merely use an old arena helper for setup are migrated, not deleted.

## 9. Exit criteria

The tranche is complete only when:

1. there is one encounter assembly path;
2. no old scenario/evaluation ontology remains;
3. no direct validation-arena constructor remains;
4. no evaluator/Elo/gauntlet/promotion runtime or public route remains;
5. all 58 rosters and 38 encounters retain their intended gameplay semantics;
6. AI gameplay validation lives under `tests/ai/` and uses product composition;
7. scenario imports are cold and bounded;
8. generated SDK exposes only canonical product models;
9. standalone and hosted game creation are green;
10. replay, replication, history, summaries, and profile persistence remain
    green;
11. the maintained backend and frontend gates pass on one frozen contract.

## 10. Explicit non-goals

- no new Elo system;
- no replacement tournament framework;
- no experiment orchestration;
- no broad encounter-content rewrite;
- no new AI policy logic;
- no changes to replay file ownership;
- no book/tutorial cleanup;
- no compatibility aliases;
- no preservation of old architecture merely for museum tests.

## 11. Implementation record

The hard delete is implemented in the current working tree.

### 11.1 Canonical runtime

- `dnd/scenarios/__init__.py` is an inert package boundary.
- Battlefield contracts live in `dnd/core/content/battlefields.py`.
- The only scenario construction path is the canonical battlefield/roster/
  deployment catalog followed by `assemble_encounter_recipe(...)`.
- The checked-in authored catalog contains 58 public rosters, 38 encounters,
  nine battlefields, and nine reusable deployments.
- An exhaustive authored-spell regression verifies that scenario-only spell
  grants are preserved as typed `RosterSpellGrant` records instead of being
  repaired by a direct entity factory.

### 11.2 Deleted runtime

- `dnd/scenarios/ai_validation_arenas.py` and
  `dnd/scenarios/evaluation/**`;
- `ai/evaluation/**`, `ai/external_selfplay.py`, and
  `ai/validation_harness.py`;
- gauntlet contracts, SSE, routes, dashboards, Elo/rating repositories,
  promotion/config-ladder workers, tournament code, and evaluator CLIs;
- obsolete arena-mode helpers and the retired scenario model families.

The retained observer projection now lives under `ai/telemetry/`. Retained
Direct Codex artifacts and helpers live under `ai/codex_tools/`.

### 11.3 Tests and deprecated book wrapper

- All 43 genuine behavior-test modules formerly under `tests/engine_book/`
  were moved to `tests/engine/`; the `tests/engine_book/` package no longer
  exists.
- Deprecated book prose remains outside maintained test collection under the
  ignored archive boundary.
- The maintained sweep completed with:
  - 502 engine cases;
  - 391 progression cases;
  - 51 AI cases;
  - 1,334 manual cases across the first two shards;
  - every maintained file in the final manual shard, including all 58
    latency/runtime performance cases;
  - 56 architecture cases;
  - 81 TypeScript SDK cases;
  - Pyright with zero errors and zero warnings.

### 11.4 Generated-contract handoff

- `GameCreationCatalogResponse.schema_version = 3`;
- SDK contract hash:
  `18a05b309ef4609eada5c2dcfe2cfad5ee18e91975a0545ea4f4448712624f38`;
- player replication contract hash:
  `f9156c74db78d67150dbd9c084a3ad7ad7bd120952606a786d7eaf221dcaf3f6`;
- event contract hash:
  `9463e028e1452b2b972a696c7b09664889676b8cc4596bfde2db8d36dc64d4a5`;
- content-set digest:
  `83c16b7a65267125449208aa092a96be1fb66dc301802094bb5cf1c984a7b03b`.

The frontend received this exact frozen handoff before the final cleanup
validation continued.

### 11.5 Local evidence deletion

The following ignored, unrecoverable evaluator evidence was deleted after its
retain/delete boundary was verified:

- `ai/evidence/elo_gauntlets` (approximately 4.8 GB);
- `ai/evidence/promotion` (approximately 261 MB);
- `ai/evidence/runs` (approximately 303 MB);
- `ai/evidence/gauntlets` (approximately 3.2 MB);
- `ai/evidence/tournaments`;
- `ai/evidence/promotion-spool`.

The approximately 976 MB under `ai/evidence/direct_codex` and
`ai/evidence/direct_codex_runs` remains because maintained performance and
semantic regressions consume it.

### 11.6 Retained latency regression closure

`test_v222_high_cardinality_spell_epoch_keeps_median_under_five_ms` initially
measured approximately 5.48 ms median against its unchanged 5.0 ms limit.
Profiling localized the avoidable work to quadratic rescans of already
dominated control and area-damage seeds.

Both reducers now maintain an incremental non-dominated frontier while
preserving original result order and exact dominance semantics. Because the
accepted V31 source identity is immutable, this was not silently repinned in
place: the old executable module was replaced by the single accepted
`policy.v32.accepted` generation, whose implementation hash is
`4bbaf11b48c0bbebdaded8bdf9e144d4e148a24cb3c8c5f4b31e601afb591de5`.

The original V222 limit now passes without weakening, the complete performance
file is 58/58 green, and the complete related policy files are green:

- typed policy: 97/97;
- policy host: 54/54;
- candidate generation: 16/16;
- candidate commitments: 9/9.
