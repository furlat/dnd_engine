# Stale test repair — 2026-10-17

Worktree `codex/single-pass-propagation` (base d13e6ad). Only `tests/` was edited.
Every traceback was re-read before editing. All failures matched the approved
triage. None was an engine bug.

## Result

- `pytest $(cat .runtime/single-pass/known_failures.txt)`: **69 passed** (was 69 failed).
- All nine edited files run in full: **469 passed**.
- `tests/player/test_application_review.py` still fails to collect. It was left unchanged on purpose (see below).
- The final run included the concurrent agent's uncommitted engine edits
  (`dnd/blocks/sensory.py`, `dnd/core/gridmap.py`, +11 lines).

## Door/edge reach (54)

Evidence: every failure was `ValueError: Item is out of reach` at `dnd/actions_functional.py:839`.
Directional doors have `get_manual_contact_range() == 0`
(`dnd/items/environment.py`). Contact cells are the owner tile and its
neighbour across the edge (`gridmap.attack_object_contact`).

- `tests/engine/test_environment_destruction.py:111`: attacker moved from (2,3) to (4,3), the far side of the (3,3) EAST edge.
  - The owner tile (3,3) is the "doorway". `DirectionalDoor._doorway_occupied` checks it, so an actor standing there removes the Close action that the test unpacks.
  - The change applies to all variants. The stale Open action is now rejected only because the door was destroyed, not because the actor was out of reach.
- `test_environment_destruction.py:157,163` (door-close test):
  - The operator moves from (2,3) to (4,3).
  - The traveler still occupies (3,3).
  - The traveler now leaves to (2,3) instead of (4,3), because (4,3) is taken by the operator.
  - All assertions are unchanged.
- `tests/engine/test_window_attack_access.py:44`: the allowed position changes from (3,2) to (5,2), the far side of the (4,2) EAST edge. The actor cannot use the owner tile (4,2), because the follow-up Close would see an occupied doorway.

Note, not acted on: an actor standing in the owner tile can open an edge door but can never close it. This matches the test's own model, where the owner tile is the opening.

## Globe propagation (4)

`tests/engine/test_globe_propagation.py:42-43` and `:111-113` now use `fixed_dice_faces(*([1] * 130))`.

Why the old tests broke:
- Fireball rolls 8d6 separately for each exposed recipient (`dnd/spells/evocation.py:1119`), and walls are now recipients. With caster + 7 walls the doorway case needs 65 faces, but the old pool had only 30.
- The L-wall and corridor cases used random dice. Random 8d6 (mean 28) breaks 27 HP stone walls, and the staged re-expansion (`propagation_revision`, `evocation.py` ~1035) then reaches the full 49-cell disc.

Probe with all-1 faces reproduced exactly 36 / 49 / 26 / 23. Faces used were 65, 57, 89 and 121. The expected reach numbers are unchanged.

Observation, not acted on: rolling damage per target differs from PHB "roll once for all targets".

## Dimension Door (2)

`tests/engine/test_banishment_dimension_door.py:78`: `"dimension_door"` becomes `"spell.dimension_door"`. In d13e6ad the effect origin `source_id` became `self.semantic_key` (`dnd/core/base_actions.py:2026`).

## Event lifecycle (3)

`tests/engine/test_event_lifecycle.py:7,33,435-437`: the helper passes `data=EmptyLogData()`, which is valid for ACTION. The ENTITY_SPOTTED entry passes `EntitySpottedLogData(...)`, as required by the `CombatLogEntry.data` field and the category validator (`dnd/core/combat_log.py:842,885`).

## World-prop cold init (4)

`tests/engine/test_world_prop_cold_initialization.py:22,86,92` now passes `PlayerAudience((observer,), (observer,))`. This is identical to the old UUID semantics, where controlled and observers were both `{observer}` (`a09a5cabf:game/presentation.py:579`).

## World entity birth (1)

`tests/engine/test_world_entity_initialization.py:345-346`: added the expected `scribed_spell_ids` and `permanent_feature_uses`. Both are new `EntityCreatedEvent` fields (059ad0af4, `dnd/core/events.py:842-843`) and are populated from the Entity fields (`dnd/entity.py:1208`).

## Body residue (1)

`tests/engine/test_body_residues.py:330-331`: the expected sequence is now `[MEMBERSHIP_COMMITTED, APPLICATION, MEMBERSHIP_COMMITTED, REMOVAL]`. `ConditionMembershipCommittedEvent` was added in 059ad0af4, after the test's last edit (cd6d4ec36). The assertion still requires the exact sequence, and `movement_revision` is still checked as unchanged.

## Collection errors

**`tests/engine/test_solid_walls.py`: fixed (18 pass).**
- The file was created in b9c746d89, the same commit that moved `tests/game/door_destruction_scenarios.py` to `game_obsolete/`, so it never collected.
- The wall feature exists in `dnd/`, and no other test covers it.
- Ported `review_actor` inline (lines 40-56), minus its unused `ranged`/`faction` branches.

**`tests/player/test_application_review.py`: left unchanged, needs a human decision.**
- It imports `game.runtime_protocol` and `game.runtime_worker`. Both were deleted in b9c746d89 (copies are in `game_obsolete/`, 320 lines). They form the stdio worker protocol, not a scenario helper.
- The new `server/protocol.py` has a different HTTP contract.

Coverage per test:
- `published_initialization`: covers deleted worker code only.
- `common_operation...handler`: covers deleted worker code only. Handler toggling is covered over HTTP in `tests/player/test_high_level_spell_transport.py:355`.
- `discovery_generation_counts_only_its_seats_queries`: uses only `dnd.player` and no other test covers it. It is blocked only by the module import.
- `content_observed_and_removed`: equivalent to `tests/player/test_content_local_admission.py::test_transient_world_content_matches_reference_and_cold_replay`.
- `content_reuse_preserves_private_links`: partly covered by `test_catalog_replacement_admits_public_values_and_keeps_private_links_hidden`. Not covered elsewhere: the identity-reuse assertions and the "changed its definition" rejection.

Options:
1. Delete the file.
2. Keep only the three `dnd.player` tests, on a `create_session` fixture like `test_content_local_admission.py`.
3. Port the worker into tests (not recommended).

Out of scope, seen only: `tests/manual/test_true_strike_runtime.py:10` also imports `tests.game.*`.

## Follow-up (human decision: adapt what can be saved, drop the useless ones)

### Correction to my earlier classification

Above, I said `published_initialization` and `common_operation...handler` "cover deleted worker code only". That was wrong. In `game_obsolete/runtime_worker.py`, `start_runtime` and `dispatch` are thin wrappers over live code:
- `create_session` and `initialize_audiences`;
- `advance_controller`, `discover_player_actions` and `toggle_player_handler`;
- `capture_application_operation`.

Only the stdio codec (`REPLY_CODEC`, request ids) is deleted. The asserted behavior is live:
- the client reduction of the published initialization and content equals `latest`;
- an eventless handler toggle replicates its HUD after-value exactly.

I found no exact replica of either. `tests/player/test_high_level_spell_transport.py:355` toggles a handler but does not compare the client-reduced state with the server. Both tests therefore fall under "can be saved" and were adapted, not deleted.

### `tests/player/test_application_review.py`: rewritten, 4 tests

- No `game.*` imports and no worker copy remain.
- New `started` fixture: `random.seed(0)`, `create_session()`, `initialize_audiences(..., exclusive_current=True)` (the mode the live `server/worker.py:84` uses), then `close_session` + `reset_engine_runtime`.
- Detached-client helpers:
  - `TypeAdapter(PlayerInitialization)` JSON round trip;
  - `PlayerUpdate.model_validate_json`.
- Kept, adapted:
  - `published_initialization...`: dropped the worker tautology `reply content == latest.content`.
  - `common_operation_replays_eventless_handler_after_values`.
  - `content_reuse_preserves_private_links...`: unchanged assertions.
- Kept unchanged: `discovery_generation_counts_only_its_seats_queries`, which already used only `dnd.player`.
- Deleted: `content_observed_and_removed_in_one_operation_is_still_admitted`.
  - It is fully covered by `tests/player/test_content_local_admission.py::test_transient_world_content_matches_reference_and_cold_replay`, which uses the same Guardian of Faith scenario and descriptor, in the live `exclusive_current` mode.
  - That test makes the same four assertions, plus `content == admitted_content(...)` and a cold replay after reset.

### `tests/manual/test_true_strike_runtime.py`: adapted, 4 tests

- **Live behavior covered:** a discovered True Strike owns one real weapon attack, and the captured lineage shows it. The attack has:
  - `provided_by_id == "spell.true_strike"` and is parented to the spell lineage;
  - intelligence override and no costs;
  - the shortsword or shortbow item presentation;
  - Piercing + Radiant damage components (8 + 4);
  - a capture that survives `reset_engine_runtime`.
- **Not covered elsewhere:**
  - `tests/manual/test_133_new_spells_batch4_legacy_contract.py` covers the casting ability, the radiant die and miss damage types.
  - `tests/engine/test_spell_catalog_repair_interactions.py` covers effect refusal.
  - `tests/engine/test_spell_object_targeting.py` covers bow range.
  - None of them covers the captured lineage or item identity.
- **Change:** ported `true_strike_history` inline from `game_obsolete/tests/game/true_strike_scenarios.py`. All of its APIs are live (`dnd.player.capture`, `dnd.player.recorded`, `register_true_strike`). Dropped only the unused `weapon` parameter and the presentation-only `AppearanceConfig`. All assertions are unchanged.

### Runs

- `pytest tests/player/test_application_review.py tests/manual/test_true_strike_runtime.py tests/player/test_content_local_admission.py`: **11 passed**.
- `pytest --collect-only -q tests`: 5769 collected, **106 collection errors**, all in `tests/manual` (99), `tests/ai` (5) and `tests/paused_server` (2). There are none in `tests/engine`, `tests/player`, `tests/architecture`, `tests/progression` or top-level `tests/`.
- Every error imports a module or name that no longer exists. None was touched. Grouped by missing import:
  - `ai` (27): manual/test_30, 32, 33, 42-45, 47-50 (codex_local_read_model), 60, 89-93, 99-107 (codex_*), 110_multi_game_gateway
  - `dnd.content_system.item_bindings` (14): manual/test_113_subjective_replication_routes, 120_subjective_world_projection, 122, 125 ×2, 177, 178_spell_catalog_content_identity, 179_player_item_transport_identity, 180, 182, 18, 95, directional_environment_legacy_contract, srd_armor_content_factories
  - `server.event_server` / `from server import event_server` (11): manual/test_101_directory_event_stream, 109, 112, 150, 153, 189_game_creation_visual_preview, 96, 118_objective_diagnostics_routes, 147, 149, 19
  - `server.event_stream` (7): manual/test_110_gateway_restart, 116, 118_worker_replay, 119, 123, 124, 25
  - `server.game_directory` (6): manual/test_101_game_directory_{hot_path,migrations,repository}, 111, 173, 194
  - `server.agent_runtime` (5): manual/test_28, 31, 36, 50_counterspell_engine_contract, 50_movement_revalidation
  - `server.external_ai_protocol` (4) and `server.registered_ai_controller` (1): ai/test_external_ai_protocol, external_ai_service, live_ai_matchups, registered_ai_provider, registered_ai_controller
  - `dnd.content_system.builtin_character_builds` (3): manual/test_186, 193; paused_server/test_persistent_character_scenario_deployment
  - one or two each:
    - `dnd.core.content.item_definitions`: 168, 171
    - `dnd.core.progression.character_ruleset_digest`: 184, 185
    - `server.world_contracts`: 117, 120_player_replication_journal
    - `dnd.classes.content_factories`: 181_action
    - `AuthoredBehaviorAttribution`: 181_affordance
    - `ItemContentRefSnapshot`: 121
    - `dnd.items.{apparel_presets,armors,weapons}`: 178_authored_item_visual_inventory, 158, 166
    - `dnd.player_character_body`: 139
    - `server.api_models`: 98
    - `server.worker_terminal_spool`: 189_worker_terminal_spool
    - `server.agent_protocol`: 34
    - `server.character_directory_contracts`: 187
    - `server.character_directory_service`: paused_server/test_persistent_character_equipment_mutation
    - `server.character_settlement`: 101_game_directory_evidence
    - `server.combat_log_projection`: 113_subjective_combat_log_projection
    - `server.combat_log_source`: 115
    - `server.content_catalog`: 179_condition_content_identity
    - `server.event_contract`: 97
    - `server.game_artifact_store`: 104
    - `server.game_summary_store`: 103
    - `server.hosted_worker`: 163
    - `server.replication_perspective`: 113_subjective_replication_contract
    - `server.timeline_contracts`: 114

## Collection errors, part 2: 106 files (human rule: adapt what can be saved, drop the useless ones)

Only `tests/` was edited. Nothing was committed. I did not touch the concurrent agent's engine edits
(`dnd/blocks/sensory.py`, `dnd/core/gridmap.py`, `dnd/core/base_actions.py`,
`dnd/entity.py`, `dnd/spatial/area_conditions.py`, `tests/engine/test_spatial_conditions.py`).
All runs below include those edits.

### Result

- `uv run --no-sync python -m pytest --collect-only -q tests -p no:cacheprovider`: **5915 collected, 0 errors** (was 5769 collected, 106 errors).
- No file that collected before lost a test. The one changed count, `tests/engine/test_spatial_conditions.py` (24 → 25), comes from the concurrent agent's edit at 01:41.
- **15 files adapted** (145 tests now collect from them), **91 files deleted**, **4 orphaned support modules deleted**.
- Adapted files, each run on its own: **88 passed, 57 failed**. Every failure is listed under "Failures kept on purpose". None is a test-harness error.

### Method

- Each file's imports were resolved against the live tree. A probe then ran a copy of every file in which each deleted name was replaced by a stub that raises `DEAD_IMPORT` when used.
  - The probe ran each live-failing test in isolation, so a failure caused only by test order was not mistaken for a real one.
  - The probe lived in `tests/zz_stale_probe/`. It was moved out of `tests/` and no longer exists there.
- A test was **kept** when it uses only live code, and either passes or fails on a live production difference, and no collected test already covers it.
- A test was **deleted** in these cases:
  - it needs a deleted module or artifact;
  - it pins a frozen migration ledger or allowlist;
  - a collected test already covers it (named in the tables);
  - its expectation contradicts an explicit live design (cited).
- Legend for the evidence column:
  - **[S]**: module moved to `server_obsolete/` in b9c746d89 (2026-10-10). The live `server/` is the new headless player server and has no equivalent module.
  - **[A]**: `ai` package moved to `ai_obsolete/` in b9c746d89. The live AI is `dnd/ai`.
  - **[I]**: deleted in 5ce30f087 (2026-09-01, Python item factories replaced by direct pack content).
  - **[C]**: deleted in 5c860f464 (2026-09-02, character creation; `character_ruleset_digest` also removed there).
  - **[T]**: `dnd/tiles.py` deleted in fb6f18cc6 (2026-08-30).

### Adapted (LIVE-UNCOVERED)

| File | Missing import | Change | Run |
| --- | --- | --- | --- |
| `manual/test_42_action_semantics.py` | `ai.subjective.semantic_pool` [A] | Dropped the import and the 6 `SemanticContractPool` tests. 36 tests of live `dnd.ai` action semantics are unchanged; `action_semantics_for_available_action` and `evaluate_fact_expression` have no other test. | 36 pass |
| `manual/test_50_counterspell_engine_contract.py` | `server.agent_runtime`, `server.event_server` [S] | Kept 2 uncovered tests: declaration cancel spends no resources, and a handler `model_copy` becomes a stored version. 8 tests are already ported to `engine/test_content_recovery_behavior_semantics.py` (bindings, allied spell, Quickened, third-rank floor, check outcomes). The subjective-redaction test was deleted; see below. | 2 pass |
| `manual/test_50_movement_revalidation.py` | `server.agent_runtime.observation_journal`, `test_28.create_observation_game` | Tests 1–2 unchanged. Tests 3–4 now build `before` with the live `SubjectiveAIStateProjector` (fixture `hero_world`) instead of the deleted journal snapshot. The hostile fact uses a fresh uuid; the assertions are unchanged. The old-HTTP command-stream test was deleted [S]. | 4 pass |
| `manual/test_36_seamless_subjective_runtime.py` | `ai.*`, `server.*` | Kept 3 `EventQueue` batch and completion-sequence callback tests (uncovered) and the action-timing test. The timing test now starts with `reset_authored_encounter_state()`; before, it relied on a preceding test's reset. | 3 pass, 1 fail (catalog) |
| `manual/test_28_subjective_observation_stream.py` | `server.*`, `ai.knowledge`, `item_bindings` | Kept 4 pure `project_combat_log` cases: hidden movement prefix, nested identity scrub, multi-projectile summary, damage evidence. They are not duplicated in `engine/test_typed_combat_log.py` or `engine/test_subjective_combat_log_replay.py`. 44 session/stream tests deleted [S] [A]. | 4 pass |
| `manual/test_31_subjective_runtime_epochs.py` | `server.action_serialization`, `server.agent_runtime`, `item_bindings` | Kept the 42 tests that reference no deleted name; 18 deleted. Added an autouse `reset_authored_encounter_state()`. Two harness fixes: the local stale `_materialize_srd_fixture` (no compose/deploy) was replaced by the maintained `test_53` helper, which fixed 7 SRD tests; `senses.entities.values()` → `contact.position`. Cost rows are now typed `BaseCost`, shaped like the real `ExtraAttack` cost (`dnd/classes/fighter.py:1164`). | 16 pass, 26 fail |
| `manual/test_43_ai_runtime_performance.py` | `ai.*`, `server.runtime_performance`, `server.session` | Kept the 38 tests without deleted names; deleted the rest: `ai/evidence` replay artifacts, the GC/HTTP harness, and 3 more listed below. Added an autouse reset. The Fireball save-bonus test now asserts `total_targets >= 2`, because exposed walls are also recipients (7 applications; see the globe section above). Its intent, `saving_throw_bonus_calls == 2`, is unchanged. | 11 pass, 27 fail (catalog) |
| `manual/test_121_canonical_presentation_mapper.py` | `server.player_replication.*` [S] | Kept 1 test: step `phase_to(COMPLETION)` derives position evidence for the event and its log. Collected tests only set this evidence by hand. 37 mapper tests deleted. | 1 pass |
| `manual/test_139_condition_presentation_contract.py` | `dnd.player_character_body` [C], `server.*` | Kept the internal-marker test (3 params) and the "every public condition has name/description" invariant. | 3 pass, 1 fail |
| `manual/test_149_remaining_legacy_contract.py` | `server.event_server`, `server.event_stream` | Rewritten to the one uncovered case: Prone applied on the owner's turn with no movement left stays applied. The owner-turn auto-stand duplicates `engine/test_standard_conditions.py::test_eb_08_010`. The mobile half is covered by `test_eb_08_009`, which asserts the current `applied is False`. Ledger and SSE tests deleted. | 1 pass |
| `manual/test_178_authored_item_visual_inventory.py` | `dnd.items.apparel_presets`, `authored_variant_presets` [I], `server.content_catalog` | Kept 4: `ContentPresentation` tint/sprite validation (uncovered) and 2 ledger facts that still hold. Deleted 11: count freezes now off (77 → 85 categories), deleted modules, and removed content ids. | 4 pass |
| `manual/test_178_spell_catalog_content_identity.py` | `server.*`, `item_bindings` | Kept the spell identity consistency test and the icon-key test (uncovered). 11 catalog/replication tests deleted. | 2 pass |
| `manual/test_179_condition_content_identity.py` | `server.content_catalog` | Kept the generic invariant "every public condition leaf has a content declaration". Added `import_dnd_modules()` (as `test_139` already does) so the subclass inventory does not depend on which modules happened to be imported. | 1 fail |
| `manual/test_181_action_content_identity.py` | `dnd.classes.content_factories` [C], `server.content_catalog` | Same: kept the generic action declaration invariant and added `import_dnd_modules()`. 5 tests deleted: stale `BehaviorBinding` constructor, removed content ids. | 1 fail |
| `manual/test_181_affordance_content_identity.py` | `dnd.premade_characters` [C], `AuthoredBehaviorAttribution`, `server.*` | Kept the unbound-template rejection test; the guard at `dnd/entity.py:5769` has no other test. 10 tests deleted. | 1 pass |

Tests deleted from kept files because their expectation contradicts live design:
- `test_50_counterspell::test_subjective_counterspell_log_redacts_an_unseen_reactor`. The live projector deliberately turns an unknown-source `spell_interruption` into a generic `ACTION` "An unseen source acts" with `EmptyLogData` (`dnd/subjective_combat_log.py:84-92`). The old `SPELL_INTERRUPTION` / `outcome_code` expectations cannot hold, and dropping them would weaken the test. Observation, not acted on: the live `CounterspellReactionEvent` log has empty `perceiver_uuids`, so a witness who sees the caster gets no entry at all.
- `test_43`:
  - `test_aoe_propagation_footprints_survive_visibility_only_changes`: `StopIteration`. Every visible cell is now an AoE candidate, so the test's premise is gone.
  - `test_epoch_normalizes_one_outcome_profile_per_source_action`: the epoch no longer calls the monkeypatched `ActionOutcomeProfile.model_validate` (0 calls).
  - `test_required_target_aoe_prefilter_uses_action_relationship_filter`: patches private `Entity._compute_aoe_at_position` with a stale signature. It did not finish within the 180 s timeout in isolation; the cause was not investigated.
- `test_114_timeline_contracts.py` (whole file). Its only live-looking test orders `perceiver_uuids` in JSON, but the live `CombatLogEntry` excludes that field from serialization (`exclude=True`, `dnd/core/combat_log.py:848-857`).

### Failures kept on purpose (engine/content not changed; human decision needed)

1. **Authored catalog references uninstalled player creatures: 53 tests** (`test_31` ×25, `test_43` ×27, `test_36` ×1). All fail with `KeyError: Unknown content reference content.neurodragon:creature:creature.player.{sorcerer,fighter}@1`.
   - 29 of 42 encounters in `dnd/scenarios/authored_catalog.json` cannot be assembled. Probe over every id: only 13 assemble (e.g. `caster_crossfire`, `trap_lever_killzone`, `lantern_crypt`).
   - Already-collected tests fail the same way, e.g. `manual/test_37_authored_encounter_mechanics.py::test_reaction_counterspell_lab_registers_reaction_defenses`.
   - The tests are unchanged and use only live code; they pass once the catalog content exists.
2. **Lever semantics never match live rows** (`test_31::test_visible_environment_interaction_is_a_capability_before_it_is_legal`): the result is `interaction.object.use` instead of `interaction.trap.deactivate`.
   - `dnd/ai/runtime/action_semantics.py:1125` keys the mapping by `"dnd.items.environment_interactables.PullLeverAction"`.
   - The live row's `semantic_key` and `behavior_id` are `action.environment.trap_lever.pull`.
   - `test_42::test_pull_lever_exposes_typed_hazard_deactivation` passes only because it builds the row with the old key by hand.
3. **Public conditions without name/description** (`test_139`): 16 classes, including abstract bases such as `AreaCondition`. Most concrete ones are recent spatial conditions, e.g. `IceSurface`, `WetSurface`, `GasVent`, `JawTrap`, `Tripwire`, `SteamCloud`. `ObjectResidueCondition` also has no name. `IceSurface` instances are built with no description (`dnd/items/spell_payloads.py:198`), so `PerceivedSpatialEffect.description` is empty.
4. **Public classes without a content declaration** (`test_179`, `test_181_action`): 28 condition leaves and 22 concrete actions. Examples: Sorcerer features, `Entangle`/`EvardsBlackTentacles`, spatial traps, `ConvertSPToSlot`, `QuickenedSpell`. Either this is drift or the invariant is obsolete; I cannot tell which.

### Deleted (DEAD / LIVE-COVERED)

| File | Missing import | Class | Evidence |
| --- | --- | --- | --- |
| `ai/test_external_ai_protocol.py` | `server.external_ai_protocol` | DEAD (deleted) | [S] external-AI HTTP protocol; no live equivalent |
| `ai/test_external_ai_service.py` | `server.external_ai_protocol, services.ai_policy_server.*` | DEAD (deleted) | [S]; `services/ai_policy_server/app.py:13` itself imports the deleted module, so the service cannot load |
| `ai/test_live_ai_matchups.py` | `server.external_ai_protocol, server.registered_ai_*` | DEAD (deleted) | [S]; the only test without a dead name launches the `services.ai_policy_server` CLI, which cannot load |
| `ai/test_registered_ai_controller.py` | `server.registered_ai_controller` | DEAD (deleted) | [S] |
| `ai/test_registered_ai_provider.py` | `server.external_ai_protocol, server.registered_ai_provider` | DEAD (deleted) | [S] |
| `manual/test_100_codex_predicate_ledger.py` | `ai.codex_tools.representation.predicates` | DEAD (deleted) | [A] |
| `manual/test_101_codex_local_inspection.py` | `ai.codex_tools.representation.inspection` | DEAD (deleted) | [A] |
| `manual/test_101_directory_event_stream.py` | `server.event_server, server.directory_event_stream` | DEAD (deleted) | [S] |
| `manual/test_101_game_directory_evidence.py` | `server.character_settlement, server.game_directory` | DEAD (deleted) | [S] |
| `manual/test_101_game_directory_hot_path.py` | `server.game_directory` | DEAD (deleted) | [S] |
| `manual/test_101_game_directory_migrations.py` | `server.game_directory` | DEAD (deleted) | [S] |
| `manual/test_101_game_directory_repository.py` | `server.game_directory` | DEAD (deleted) | [S] |
| `manual/test_102_codex_representation_projector.py` | `ai.codex_tools.representation.*` | DEAD (deleted) | [A] |
| `manual/test_103_codex_representation_runtime.py` | `ai.codex_tools.hot_runtime, ai.policy.host` | DEAD (deleted) | [A] |
| `manual/test_103_worker_game_summary_store.py` | `server.game_summary_store` | DEAD (deleted) | [S] |
| `manual/test_104_codex_subjective_geometry.py` | `ai.codex_tools.representation.geometry` | DEAD (deleted) | [A] |
| `manual/test_104_game_artifact_store.py` | `server.game_artifact_store` | DEAD (deleted) | [S] |
| `manual/test_105_codex_local_typed_client.py` | `ai.codex_tools.local_client` | DEAD (deleted) | [A] |
| `manual/test_106_codex_session_transcript.py` | `ai.codex_tools.session_transcript, server.agent_protocol` | DEAD (deleted) | [A] [S] |
| `manual/test_107_codex_fast_wire_cli.py` | `ai.codex_tools` | DEAD (deleted) | [A]; the remaining test imports `ai.codex_tools.wire_cli` in a subprocess |
| `manual/test_109_hosted_game_runtime.py` | `server.event_server, server.hosted_worker` | DEAD (deleted) | [S] |
| `manual/test_110_gateway_restart.py` | `server.event_stream, server.game_gateway` | DEAD (deleted) | [S] |
| `manual/test_110_multi_game_gateway.py` | `ai.remote_connection, server.game_gateway, builtin_character_builds` | DEAD (deleted) | [A] [S] [C] |
| `manual/test_111_player_identity_characters.py` | `server.game_directory, server.game_gateway` | DEAD (deleted) | [S] |
| `manual/test_112_server_life_state_contract.py` | `server.event_server, server.world_projection` | DEAD (deleted) | [S] old player replica |
| `manual/test_113_subjective_combat_log_projection.py` | `server.combat_log_projection` | LIVE-COVERED (deleted) | [S]; the module was a signature wrapper over live `dnd.subjective_combat_log.project_combat_log`. Every case builds untyped `data` dicts that the typed `CombatLogEntry` rejects; typed successors are `tests/engine/test_subjective_combat_log_replay.py` and `tests/engine/test_typed_combat_log.py` |
| `manual/test_113_subjective_replication_contract.py` | `server.replication_perspective, server.session` | DEAD (deleted) | [S] |
| `manual/test_113_subjective_replication_routes.py` | `server.player_replication, item_bindings` | DEAD (deleted) | [S] [I] |
| `manual/test_114_timeline_contracts.py` | `server.timeline_contracts` | DEAD (deleted) | [S]; the one live-looking test asserts JSON order of `perceiver_uuids`, which live `CombatLogEntry` excludes from serialization (`exclude=True`, `dnd/core/combat_log.py:848-857`) |
| `manual/test_115_objective_timeline.py` | `server.combat_log_source, server.objective_timeline` | DEAD (deleted) | [S] |
| `manual/test_116_objective_replay.py` | `server.event_stream, server.objective_replay` | DEAD (deleted) | [S] |
| `manual/test_117_player_replication_contract.py` | `server.player_replication_contract, server.world_contracts` | DEAD (deleted) | [S] |
| `manual/test_118_objective_diagnostics_routes.py` | `server.event_server, server.event_stream` | DEAD (deleted) | [S] |
| `manual/test_118_worker_replay.py` | `server.event_stream, server.worker_replay` | DEAD (deleted) | [S] |
| `manual/test_119_gateway_replay_access.py` | `server.game_gateway, server.player_replay` | DEAD (deleted) | [S] |
| `manual/test_120_player_replication_journal.py` | `server.player_replication.journal` | DEAD (deleted) | [S] |
| `manual/test_120_subjective_world_projection.py` | `server.player_replication.world_projection, item_bindings` | DEAD (deleted) | [S] [I] |
| `manual/test_122_canonical_replication_runtime.py` | `server.player_replication.runtime, item_bindings` | DEAD (deleted) | [S] [I] |
| `manual/test_123_subjective_player_replay.py` | `server.player_replay, server.player_replication` | DEAD (deleted) | [S] |
| `manual/test_124_worker_subjective_replay.py` | `server.worker_player_replay` | DEAD (deleted) | [S] |
| `manual/test_125_active_weapon_stance.py` | `server.player_replication.world_projection, item_bindings` | LIVE-COVERED / DEAD (deleted) | [S] [I]; the stance-switch test is ported verbatim in `tests/engine/test_content_recovery_item_semantics.py` |
| `manual/test_125_subjective_objective_render_parity.py` | `server.replicated_world, server.objective_state` | DEAD (deleted) | [S] |
| `manual/test_147_mapeditor_legacy_contract.py` | `server.event_server, server.event_stream` | DEAD (deleted) | [S]; the only passing test counts entries of its own legacy ledger |
| `manual/test_150_native_ai_game_creation.py` | `server.event_server` | DEAD (deleted) | [S] |
| `manual/test_153_registered_ai_game_creation.py` | `server.event_server, server.registered_ai_*` | DEAD (deleted) | [S] |
| `manual/test_158_srd_5_1_source_coverage_ledger.py` | `dnd.items.armors, dnd.items.weapons, *_REF names, dnd.monsters.circus_fighter_items` | DEAD (deleted) | [I]; a ledger of the deleted Python item roots |
| `manual/test_163_content_worker_identity.py` | `server.hosted_worker` | DEAD (deleted) | [S] |
| `manual/test_166_club_content_factory.py` | `item_bindings, dnd.items.weapons, server.mapeditor_support` | DEAD (deleted) | [I] [S] |
| `manual/test_168_content_catalog_contract.py` | `server.content_catalog, dnd.core.content.item_definitions` | DEAD (deleted) | [S] [I] public catalog; the live client catalog is `dnd/player/content_composition.py` |
| `manual/test_171_behavior_definition_contract.py` | `dnd.core.content.item_definitions, registration.item_factory, server.content_catalog` | DEAD (deleted) | [I] [S]; probe: 9/9 hit deleted names |
| `manual/test_173_character_revision_repository.py` | `server.game_directory` | DEAD (deleted) | [S] |
| `manual/test_177_content_recipe_presets.py` | `dnd.items.apparel_presets, dnd.items.armors, server.content_catalog` | DEAD (deleted) | [I] [S]; the remaining test parses the deleted `dnd/classes/content_factories.py` |
| `manual/test_179_player_item_transport_identity.py` | `item_bindings, dnd.items.weapons, server.player_replication` | DEAD (deleted) | [I] [S] |
| `manual/test_180_environment_content_identity.py` | `item_bindings, dnd.items.environment_content, dnd.tiles, server.mapeditor_support` | DEAD (deleted) | [I] [T] [S]; the two remaining tests are frozen July allowlists (exact identity set, constructor call sites) contradicted by later content |
| `manual/test_182_mapeditor_content_recipe_hard_cut.py` | `item_bindings, server.mapeditor_support` | DEAD (deleted) | [I] [S] |
| `manual/test_184_character_profile_progression_repository.py` | `dnd.core.progression.character_ruleset_digest, server.game_directory` | DEAD (deleted) | [C] [S] |
| `manual/test_185_local_profile_manager.py` | `dnd.core.progression.character_ruleset_digest, server.game_directory.local_profiles` | DEAD (deleted) | [C] [S] |
| `manual/test_186_character_directory_service.py` | `builtin_character_builds, server.character_directory_service` | DEAD (deleted) | [C] [S] |
| `manual/test_187_standalone_local_game_lifecycle.py` | `server.character_directory_contracts, server.local_game_lifecycle` | DEAD (deleted) | [S] |
| `manual/test_189_game_creation_visual_preview.py` | `server.event_server, server.game_creation_preview` | DEAD (deleted) | [S] |
| `manual/test_189_worker_terminal_spool.py` | `server.worker_terminal_spool` | DEAD (deleted) | [S] |
| `manual/test_18_sessions_api_client_contract.py` | `server.event_server, server.session, item_bindings` | DEAD (deleted) | [S] [I] |
| `manual/test_193_game_creation_composition.py` | `builtin_character_builds, server.game_creation_composition` | DEAD (deleted) | [C] [S] |
| `manual/test_194_saved_encounter_directory.py` | `server.game_directory` | DEAD (deleted) | [S] |
| `manual/test_19_map_editor_scenario_authoring.py` | `server.event_server` | DEAD (deleted) | [S] map-editor HTTP routes |
| `manual/test_25_live_replication_streams.py` | `server.event_stream, server.api_models` | DEAD (deleted) | [S] SSE replication |
| `manual/test_30_codex_takeover_tools.py` | `ai.codex_tools, server.event_server, server.session` | DEAD (deleted) | [A] [S] |
| `manual/test_32_subjective_runtime_store.py` | `ai.subjective.store` | DEAD (deleted) | [A] |
| `manual/test_33_subjective_runtime_processors.py` | `ai.subjective.*, ai.knowledge.deriver` | DEAD (deleted) | [A] |
| `manual/test_34_agent_event_stream.py` | `server.agent_event_stream, server.agent_protocol, ai.subjective.runtime` | DEAD (deleted) | [A] [S] |
| `manual/test_44_typed_agent_policy.py` | `ai.policy.*, ai.knowledge, ai.subjective.*` | DEAD (deleted) | [A] |
| `manual/test_45_policy_routines.py` | `ai.policy.routines, ai.policy.economy` | DEAD (deleted) | [A] |
| `manual/test_47_direct_codex_artifacts.py` | `ai.codex_tools.artifacts, ai.codex_tools.direct_game` | DEAD (deleted) | [A] |
| `manual/test_48_policy_host.py` | `ai.policy.host, ai.policy.candidates` | DEAD (deleted) | [A] |
| `manual/test_49_hot_codex_runtime.py` | `ai.codex_tools.hot_runtime, ai.policy, server.agent_protocol` | DEAD (deleted) | [A] [S] |
| `manual/test_50_codex_local_read_model.py` | `ai.codex_tools.*, ai.subjective.*` | DEAD (deleted) | [A] |
| `manual/test_60_agent_observer_projection.py` | `ai.telemetry.observer_projection` | DEAD (deleted) | [A] |
| `manual/test_89_candidate_policy_generation.py` | `ai.policy.generations.*` | DEAD (deleted) | [A] |
| `manual/test_90_logical_option_composition.py` | `ai.planning.*` | DEAD (deleted) | [A] |
| `manual/test_91_candidate_commitments.py` | `ai.policy.generations.current_commitments` | DEAD (deleted) | [A] |
| `manual/test_92_candidate_logical_options.py` | `ai.planning.*, ai.policy.generations.*` | DEAD (deleted) | [A] |
| `manual/test_93_candidate_result_lifecycle.py` | `ai.policy.host, ai.policy.generations.*` | DEAD (deleted) | [A] |
| `manual/test_95_creature_presentation_contract.py` | `item_bindings, dnd.items.apparel_presets, server.world_projection` | DEAD (deleted) | [I] [S] |
| `manual/test_96_game_creation_api.py` | `server.event_server, server.event_stream` | DEAD (deleted) | [S] `/game-creation/*` routes |
| `manual/test_97_event_wire_contract.py` | `server.event_contract, server.timeline_contracts` | DEAD (deleted) | [S] generated wire contract and `WireEvent`; live schema is checked by `tests/player/test_protocol_schema_review.py` |
| `manual/test_98_typescript_replication_sdk.py` | `server.api_models (via devtools.generate_typescript_sdk)` | LIVE-COVERED / DEAD (deleted) | [S] old TS SDK; the one live test (reset changes generation) is implied by `tests/engine/test_subjective_combat_log_replay.py::test_surviving_encounter_rejects_old_logs_after_generation_reset` |
| `manual/test_99_codex_representation_models.py` | `ai.codex_tools.representation.*` | DEAD (deleted) | [A] |
| `manual/test_directional_environment_legacy_contract.py` | `item_bindings, dnd.items.environment_content, server.mapeditor_support` | DEAD (deleted) | [I] [S]; the old tile-object wall model (string channels, no `item_id`) is gone. Live edge walls/doors and OA through edges are covered by `tests/engine/test_world_geometry_contract.py`, `test_grid_pathfinding.py` and `test_window_attack_access.py` |
| `manual/test_srd_armor_content_factories.py` | `item_bindings, item_materialization, dnd.items.armors` | DEAD (deleted) | [I]; armor is direct pack content, inventory covered by `tests/architecture/test_content_recovery_cri_direct_items.py::test_cri_public_item_inventory_is_complete_and_direct` |
| `paused_server/test_persistent_character_equipment_mutation.py` | `server.character_directory_service, builtin_character_builds` | DEAD (deleted) | [S] [C] |
| `paused_server/test_persistent_character_scenario_deployment.py` | `builtin_character_builds, server.game_creation_composition` | DEAD (deleted) | [S] [C] |

Orphaned support modules deleted. Every consumer was in the deleted set, and each drives a deleted surface:
- `manual/live_replication_support.py` imports `server.event_stream`.
- `manual/server_test_client.py` imports `server.event_server`.
- `ai/live_socket_provider_app.py` imports `server.external_ai_protocol`.
- `manual/game_creation_test_support.py` posts to the old `/game-creation/*` routes.

`paused_server/README.md` now describes the one remaining probe.

### Out of scope, seen only

- `paused_server/test_spell_catalog_cold_start.py` collects, but its subprocess imports `server.spell_catalog`, which exists only in `server_obsolete/`.
- Collected `manual/test_12_perception_light_stealth_and_invisibility.py` fails with `AttributeError: _entity_by_position`. Its reset calls `Entity._entity_by_position.clear()` (line 42), and that attribute does not exist at HEAD either.
