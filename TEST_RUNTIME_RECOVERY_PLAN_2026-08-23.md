# Runnable Test-Surface Recovery Plan — 2026-08-23

## Objective

Restore the currently runnable in-process test surface before the tile/world-item
refactor. Fix the two demonstrated production regressions, port tests that only
use stale public construction or world APIs, correct two expectations changed by
the accepted unified vision/light semantics, and remove nine assertions that
only inspect deleted repository topology.

This cut does not restore `server`, `dnd.content_system`, retired registries,
deprecated presentation types, or missing authored visual ledgers. Collection-
blocked tests remain a separate content/server migration ledger.

## Baseline

The read-only Luna audit established:

- 217 test modules;
- 105 modules blocked during collection;
- 112 collection-success modules;
- 1,283 runnable cases;
- 1,119 passing and 164 failing cases;
- 162 failures attributed to stale tests or obsolete architecture assertions;
- 2 demonstrated production regressions.

The implementation agent must record the starting commit and `git status
--short` before editing. Existing unrelated user changes must not be changed.

Before editing, freeze three sorted artifacts under `/tmp` from a fresh
collection run:

- the 112 collection-success module paths;
- the 1,283 runnable node IDs;
- each of the 105 blocked module paths paired with its first exception type and
  missing root import/symbol.

These are validation inputs, not repository documents. Post-edit collection is
compared to these exact sets so a newly skipped module cannot look like a green
test run.

## Hard boundaries

1. No compatibility facade for `Entity.create`, `visible`, `blocks_vision_field`,
   `provider_ref`, deleted module paths, or old server/content bootstrap.
2. No EventQueue schema, event phase, reducer framework, controller, Encounter
   lifecycle, GridMap storage, or content-system redesign.
3. `Entity.position` remains objective mechanical state. `Senses.position`
   remains subjective reducer-owned state.
4. Turn-start perception is reduced before `TurnStartEvent` completion through
   the existing `SpatialSensesSystem` pre-completion system. Encounter must not
   regain a late perception-refresh method.
5. Existing behavioral tests are ported through public/stable boundaries. Do
   not replace behavior assertions with source-layout or private-registry tests.
6. Collection-blocked tests are not edited merely because search finds the same
   stale spelling. Their capability migration is outside this cut.
7. Use Pydantic for persisted/event contracts already modeled with Pydantic.
   Add no custom serialization or parallel state object.

## Acceptance boundaries

| Work | Input | Observable result |
| --- | --- | --- |
| Turn start | Start the current deployed actor's turn after its perception differs from objective world state | Before the completed turn-start root freezes, a child `SensoryUpdateEvent` records the exact changed subjective projection with reason `TURN_START` |
| Gust entry | Move a deployed creature into an active Gust of Wind zone | The saving throw and forced movement originate from the creature's committed objective entry position |
| Entity test construction | Existing configured test scenario | The entity reaches only the construction/composition/deployment stage the scenario actually uses and exposes the same gameplay behavior as before the creation hard cut |
| Tile optics fixture | Existing wall/floor fixture | `blocks_optics` expresses optical blocking independently of `walkable` |
| Spell expectations | Circle of Death / Incendiary Cloud scenario | Range is tested with perception preconditions satisfied; cloud contributes heavy optical obscurement without falsifying objective illumination |
| Architecture cleanup | Run architecture lane | Checks of active architecture remain; checks that only open deleted files or boot deleted processes are gone |

## Phase 1 — Fix the two production regressions

### 1.1 Turn-start perception

Owner: `dnd/blocks/sensory.py`.

Use the existing `SpatialSensesSystem` pre-completion boundary:

1. Include `EventType.TURN_START` in the system's handled event types.
2. For a turn-start event, select only the registered actor identified by the
   event's entity/source identity. Do not scan all observers.
3. Recompute that actor through the existing snapshot → exact resolver → delta
   reducer path.
4. Map the delta reason to `SensoryUpdateReason.TURN_START`.
5. Do not reuse the current unconditional `senses._paths_dirty = True` behavior
   for turn start. Compare the resolved perception first and dirty subjective
   navigation only when a navigation-relevant perception input changed. A clean
   actor with current perception and clean paths emits no sensory delta.
6. Emit no `SensoryUpdateEvent` when the before/after projection is identical;
   retain the existing delta helper's no-change behavior.
7. The sensory completion must be a causal child registered before the
   `TurnStartEvent` completion freezes.

Do not modify `Encounter.start_turn`, `_skip_surprised_turn`, or
`_materialize_turn_navigation` to perform perception work. Navigation
materialization remains separate and may occur after `entity.on_turn_start()`.

Behavioral proof:

- retain and pass
  `tests/manual/test_17_encounters_turns_controllers.py::test_turn_start_full_senses_refresh_emits_seen_cell_delta`;
- replace its direct clearing of reducer-owned `visible`, `seen`, and `entities`
  with supported sense-source/objective setup. One suitable scenario is an
  actor and a non-actor with distant contacts outside their previously resolved
  range, followed by source-owned long-range visual sense grants without direct
  perception-map mutation;
- assert that starting the actor's turn refreshes the actor only and that the
  completed sensory delta is a child of the completed turn-start root, without
  inspecting private callbacks;
- assert that the stale registered non-actor remains untouched;
- make a clean actor with clean navigation producing no empty/path-only
  `TURN_START` sensory delta a mandatory behavior proof.

### 1.2 Gust of Wind objective positioning

Owner: `dnd/spells/evocation.py`, limited to `GustOfWindZone` and
`_apply_gust_push`.

1. Use `entity.position` for zone-membership checks performed by objective
   turn-start mechanics.
2. Use `entity.position` as the forced movement start in `_apply_gust_push`.
3. Preserve `caster_pos`, saving-throw behavior, collision checks,
   `_pushes_in_flight`, event parenting, and the existing forced-movement event
   lifecycle.
4. Do not synchronize or mutate `entity.senses.position` early.
5. Do not introduce a new position argument, state mirror, or Gust-specific
   movement path unless live code proves `entity.position` cannot express the
   committed objective position.

Behavioral proof:

- retain and pass
  `tests/manual/test_remaining_zone_spell_legacy_contract.py::test_gust_of_wind_executes_cast_entry_turn_wall_and_cleanup_edges`;
- preserve both entry-triggered and turn-start-triggered push assertions;
- preserve the existing one completed saving throw and one completed forced
  movement per failed save.

The same regression later constructs a wall with the deleted `visible=False`
argument. Port that one proof prerequisite here to
`blocks_optics=True, blocks_propagation=True`; the complete fixture migration
remains Phase 3.

Phase gate:

```bash
.venv/bin/python -m pytest -q \
  tests/manual/test_17_encounters_turns_controllers.py::test_turn_start_full_senses_refresh_emits_seen_cell_delta \
  tests/manual/test_remaining_zone_spell_legacy_contract.py::test_gust_of_wind_executes_cast_entry_turn_wall_and_cleanup_edges
```

## Phase 2 — Port stale entity construction in runnable tests

The 140 failures are mostly fan-out from configured helper functions in 17
test modules, not 140 independent production defects.

For each affected helper, select the smallest active lifecycle that the test
actually observes:

1. Use `dnd.entities.entity_creation.create_entity(...)` for aggregate/block
   rules that do not require a committed creation fact or world occupancy.
2. Add the existing `compose_entity(...)` only when the test observes committed
   creation/composition without needing deployment.
3. Use `tests.engine.support.create_test_entity(...)` only when the scenario
   expects an immediately composed, committed, deployed actor or queries world
   occupancy.
4. Preserve exact `source_entity_uuid` by passing `source_id` where identity is
   asserted.
5. Preserve `name`, `EntityConfig`, position, faction, block composition, and
   map lookup behavior.
6. In particular, do not deploy aggregate-only source-owned primitive tests
   merely because their old helper accepted a position.
7. Remove newly unused `Entity`/creation imports. Do not create a second local
   wrapper that reproduces the obsolete signature.

Affected modules from the audit:

- `tests/engine/test_condition_lifecycle.py`
- `tests/engine/test_manual_07_entity_composition.py`
- `tests/engine/test_manual_09_conditions.py`
- `tests/engine/test_runtime_identity_registries.py`
- `tests/manual/test_01_runtime_identity_and_registries.py`
- `tests/manual/test_02_entity_anatomy.py`
- `tests/manual/test_10_combat_resolution.py`
- `tests/manual/test_126_action_override_runtime.py`
- `tests/manual/test_126_jump_legacy_contract.py`
- `tests/manual/test_126_two_weapon_fighting_legacy_contract.py`
- `tests/manual/test_133_item_core_lifecycle_legacy_contract.py`
- `tests/manual/test_13_spellcasting_core.py`
- `tests/manual/test_14_spell_families.py`
- `tests/manual/test_50_counterspell_engine_contract.py`
- `tests/progression/test_source_owned_engine_primitives.py`
- `tests/progression/test_spell_damage_affinity_contributions.py`
- `tests/progression/test_spellcasting_source_action_propagation.py`

Run each changed module immediately after porting it. A failure after the helper
port must be classified before changing its expected output.

## Phase 3 — Port stale GridMap optics fixtures

Within collection-success modules only, replace obsolete `visible=` arguments:

- `visible=False` wall fixtures become
  `blocks_optics=True, blocks_propagation=True`;
- `visible=True` fixtures become
  `blocks_optics=False, blocks_propagation=False`;
- `walkable` remains independent and unchanged.

Search every collection-success module rather than stopping at the seven cases
that initially failed. In particular, the later wall fixture inside the Gust
regression must be ported even though the earlier Gust failure originally hid
it.

Known runnable owners include:

- `tests/manual/test_08_world_model_and_movement.py`
- `tests/manual/test_126_jump_legacy_contract.py`
- `tests/manual/test_126_shatter.py`
- `tests/manual/test_127_lightning_bolt.py`
- `tests/manual/test_138_mixed_damage_spell_contract.py`
- `tests/manual/test_aoe_shape_legacy_contract.py`
- `tests/manual/test_remaining_zone_spell_legacy_contract.py`

Do not edit currently collection-blocked content tests in this phase.

## Phase 4 — Repair the bounded stale signatures

Make only the caller-side migrations proven by the audit:

1. In `tests/manual/test_legacy_information_privacy_coverage.py`, pass
   `caster_level=5` to its runnable `create_test_monster` caller; do not add a
   `level` alias. Leave the collection-blocked
   `tests/engine/test_monster_presets.py` untouched for the later migration
   ledger.
2. In the same runnable information-privacy module, construct the
   direct `ConditionRemovalEvent` with the condition's required exact
   `condition_behavior_id`; retain the typed identity/reveal assertions.
3. In `tests/manual/test_133_item_core_lifecycle_legacy_contract.py`, use and
   assert `blocks_optics_field`, and replace both stale `blocks_vision()` calls
   with the active `blocks_optics_at_center()` rules query. Preserve both the
   false and true behavioral assertions.
4. In `tests/progression/test_source_owned_engine_primitives.py`, port only
   `AttackMultiplicityGrant` rows from `provider_ref` to the required direct
   `provider_id`. Derive the direct provider ID from the authored identity being
   tested; do not change unrelated APIs that still legitimately accept a
   `ContentRef`.

Run each named test module after its migration.

## Phase 5 — Correct two post-vision expectations

### 5.1 Circle of Death range

The test's subject is spell range, so establish the perception precondition
through the supported senses model before casting. Give the caster a
source-owned visual sense with sufficient range and run the existing exact
observer resolver. Do not mutate `senses.visible` directly and do not weaken
production visibility validation.

Retain the behavioral contract:

- 155 feet is rejected specifically as out of range;
- 150 feet succeeds when all other cast preconditions are satisfied.

Owner:
`tests/manual/test_130_tier2_spells.py::test_circle_of_death_range`.

### 5.2 Incendiary Cloud optics

The active spell contributes `OpticalObscurement.HEAVY`; it does not turn
objective illumination into darkness.

Rewrite the assertions to prove:

- an active cloud footprint retains the tile's objective light level and has
  heavy optical obscurement;
- a position removed from the moving footprint loses that obscurement;
- a newly covered position gains it;
- concentration cleanup removes it;
- the existing damage, movement, and cleanup behavior remains unchanged.

Query the active GridMap optical-obscurement boundary. Do not inspect private
condition registries or reintroduce light mutation.

Owner:
`tests/manual/test_remaining_zone_spell_legacy_contract.py::test_incendiary_cloud_executes_initial_entry_turn_move_and_cleanup`.

## Phase 6 — Remove nine obsolete topology assertions

These are not gameplay tests and refer only to deleted files/processes.

The exact authorized baseline-node removals are:

- `tests/architecture/test_source_model_hygiene.py::test_encounter_models_use_described_pydantic_fields`
- `tests/architecture/test_source_model_hygiene.py::test_encounter_models_use_google_style_docstrings`
- `tests/architecture/test_source_model_hygiene.py::test_encounter_module_has_no_inline_comments`
- `tests/architecture/test_source_model_hygiene.py::test_cleaned_server_api_models_use_described_pydantic_fields`
- `tests/architecture/test_source_model_hygiene.py::test_cleaned_server_api_models_use_google_style_docstrings`
- `tests/architecture/test_source_model_hygiene.py::test_server_session_dataclasses_use_described_fields`
- `tests/architecture/test_source_model_hygiene.py::test_server_session_dataclasses_use_google_style_docstrings`
- `tests/architecture/test_source_model_hygiene.py::test_server_http_errors_do_not_use_bare_string_details`
- `tests/architecture/test_spell_catalog_composition.py::test_content_bootstrap_and_composed_spell_catalog_cold_start`

1. In `tests/architecture/test_source_model_hygiene.py`, delete the eight tests
   that open the removed `dnd/encounter.py` or files under removed `server/`:
   three Encounter source-style checks and five server source-style/error
   checks. Remove only constants/helpers/imports made dead by those deletions.
   Preserve hygiene checks over active code.
2. In `tests/architecture/test_spell_catalog_composition.py`, delete
   `test_content_bootstrap_and_composed_spell_catalog_cold_start`, which starts
   deleted `dnd.content_system` and `server.spell_catalog`. Preserve
   `test_native_spell_catalog_has_no_extension_dependency`.

Do not retarget professional-style/source-format assertions onto moved active
files merely to preserve their test count. Do not restore a subprocess or old
bootstrap facade.

## Validation sequence

The implementation agent must report exact commands and counts.

1. Before each production fix, reproduce its exact regression test.
2. After Phase 1, run the two regressions together plus:

```bash
.venv/bin/python -m pytest -q \
  tests/engine/test_senses_light_stealth.py \
  tests/engine/test_event_lifecycle.py \
  tests/engine/test_spatial_effects.py
```

3. After every test-helper/API port, run the changed module.
4. Run the active architecture lane after Phase 6.
5. Run the exact pre-edit frozen 112 module paths. Recreate their node set and
   compare it to the frozen 1,283-node set using the explicit authorized delta:
   expected nodes are the frozen set minus the exact nine node IDs listed in
   Phase 6, plus only any named Phase 1 behavioral proof IDs introduced by this
   cut. Without new proof functions, the expected count is 1,274. Acceptance is
   every surviving baseline node and authorized new proof passing, all 112
   modules remaining collection-success, no other missing node, no newly
   excluded module, and no timeout.
6. Run full collection and compare every blocked module's first exception/root
   signature to the frozen 105-row ledger. The already-ledgered blockers may
   remain, but this cut must add no collection error or silently change a
   blocker's failure class.
7. Run:

```bash
.venv/bin/python -m compileall -q dnd tests
git diff --check
```

## Stop conditions

Stop and report rather than broadening scope if:

- a stale constructor test actually requires content composition that the
  active `create_test_entity` cannot represent;
- a currently runnable module reveals a gameplay failure unrelated to these
  migrations;
- turn-start handling would require changing EventQueue phases/schema rather
  than registering the existing pre-completion system for the event;
- Gust cannot use committed `Entity.position` without changing movement
  settlement;
- a proposed expectation change weakens a real gameplay contract;
- the baseline user worktree changes from outside the implementation task.

## Completion ledger

The implementation report must include:

- production files changed for the two regressions;
- test modules ported in each phase;
- exact obsolete tests deleted;
- exact test commands and counts;
- any newly exposed failure and its classification;
- the remaining collection-blocked module count, carried unchanged into the
  later content/server migration ledger.
