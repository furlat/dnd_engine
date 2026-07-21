# Known Issues

Bugs, failing tests, and hypotheses documented during implementation sessions. Updated by dispatching background sub-agents when issues are found during unrelated work.

## Format

```
### [SHORT TITLE]
- **Found**: [date or session context]
- **Test file**: `examples/test_xxx.py` (if applicable)
- **Error**: [brief error description]
- **Hypothesis**: [what might be causing it]
- **Status**: OPEN | INVESTIGATING | FIXED
```



## Open Issues

### Battlefield deployment neutral schedule has stale catalog cardinality expectations
- **Found**: 2026-07-20 during focused test validation; unrelated to the change under test.
- **Test file**: `tests/manual/test_72_battlefield_deployment_catalog.py::test_one_seed_neutral_schedule_has_all_9180_matches_and_zero_exclusions`
- **Error**: The test expects 9,180 schedule entries from a hardcoded set of 15 hero configurations, but the current canonical roster produces 13,680 entries after configuration expansion.
- **Hypothesis**: The assertion and count expectations are stale. They should derive from the current eligible catalog cardinalities instead of hardcoding the former 15-configuration total.
- **Status**: OPEN

### Sessions API client contract has stale exact cursor readouts
- **Found**: 2026-07-19 during focused regression validation; unrelated to the change under test.
- **Test file**: `tests/manual/test_18_sessions_api_client_contract.py` (2 failures)
- **Command**: `uv run pytest tests/manual/test_18_sessions_api_client_contract.py -q`
- **Failing tests**: `test_execute_action_by_index_returns_state_logs_and_cursors` and `test_event_and_combat_log_history_are_cursor_addressed`.
- **Actual vs expected**: Both tests hard-code event cursor/count `78`, while the current deterministic action and history responses consistently produce `72`.
- **Preserved semantics**: The event cursor equals the serialized event-history length, the API and queue cursors agree, all cursor-addressed history assertions pass, the expected 19 completion events remain present, and the combat logs and their cursor assertions pass. Only the exact golden cursor readouts fail.
- **Hypothesis**: The expected value `78` is a stale golden count after event-emission lifecycle changes, not evidence of an inconsistent session or history contract. Preserve the semantic history, completion, log, and cursor-equality assertions when refreshing the readout.
- **Resolution**: Refreshed the two tutorial readouts to the canonical 72-event lifecycle while preserving every route/queue equality, completion-count, combat-log, and cursor-order assertion.
- **Status**: RESOLVED 2026-07-20

### Spell catalog reports Fire Bolt as not using an attack roll
- **Found**: 2026-07-19 during focused regression validation; separate from the stale session cursor readouts.
- **Test file**: `tests/manual/test_18_sessions_api_client_contract.py::test_spell_catalog_route_exposes_design_time_spell_metadata`
- **Error**: The test expects `fire_bolt.attack_roll` to be `true`, while the current spell-catalog response reports `false`.
- **Cause**: The catalog projector recognized obsolete direct attack helpers but not the shared `SpellAction.resolve_spell_attack()` primitive used by Fire Bolt and the current spell-attack implementations.
- **Resolution**: The backend catalog now recognizes the shared spell-attack resolver. No NeuroClient override or duplicate spell metadata was added.
- **Verification**: `test_spell_catalog_route_exposes_design_time_spell_metadata` passes, focused Pyright is clean, and the restarted live route reports Fire Bolt with `attack_roll: true`, range 120, and entity targeting.
- **Status**: RESOLVED 2026-07-20

### Chapter 12 Fireball visibility test observes an unexpected level-3 slot count
- **Found**: 2026-07-16 while running an over-broad Chapter 12 light/senses regression selection during AI movement visibility optimization; unrelated to the bright-light fast path under test.
- **Test file**: `tests/engine_book/test_chapter_12_senses_light_stealth.py::test_eb_12_018_aoe_preview_hides_hidden_entities_but_execution_hits_them`
- **Command**: `uv run pytest tests/engine_book/test_chapter_12_senses_light_stealth.py -q -k "darkvision or magical or light or self_movement_updates_visibility or visibility_cache"`
- **Error**: The action resolves correctly, both hidden and visible targets take Fireball damage, and Hidden is removed, but the test expects `caster.action_economy.spell_slot_3.normalized_score == 2`; the current result is `1`.
- **Hypothesis**: The fixture or spell-slot setup changed relative to the test's exact slot-count assertion, or the action is consuming an additional level-3 slot in this direct-cast path. This needs a focused spell-slot investigation separate from movement/visibility performance.
- **Status**: OPEN

### Policy-host LOS test stub rejects the production workspace keyword
- **Found**: 2026-07-15 during focused validation of the turn-duration augmentation change; pre-existing and unrelated to that change.
- **Test file**: `tests/manual/test_48_policy_host.py::test_enable_then_act_reuses_los_for_equivalent_subjective_geometry`
- **Command**: `uv run pytest tests/manual/test_48_policy_host.py -q` (`49 passed, 1 failed`)
- **Error**: The test-local `counted_line_of_sight` monkeypatch does not accept the `workspace=` keyword now passed by `ai/policy/routines.py::_route_costs_to_capability_envelope`, so the test fails with `TypeError`.
- **Scope**: Production behavior is unaffected; the failure occurs only in the stale monkeypatched test double.
- **Hypothesis**: Update the test stub signature to accept `workspace` and delegate that keyword to the original line-of-sight implementation.
- **Status**: OPEN

### Hypnotic Pattern cannot be ended with Shake Awake
- **Found**: 2026-07-16 during a read-only audit of break-on-damage control effects.
- **Source**: `dnd/spells/illusion.py` says another creature can use an action to shake a Hypnotic Pattern target out of its stupor, but `dnd/actions.py::ShakeAwake` recognizes and removes only `Sleep` and `Eyebite Asleep`.
- **Impact**: Hypnotic Pattern correctly ends on positive post-mitigation damage, but the documented adjacent-creature wake-up path is unavailable through the existing Shake Awake action.
- **Hypothesis**: The Shake Awake target validation and removal branches have not been extended to the `Hypnotic Pattern` condition.
- **Status**: OPEN

### Codex takeover turn-advance test patches an unused command symbol
- **Found**: 2026-07-16 during focused validation of the control-preservation change; unrelated to that change.
- **Test file**: `tests/manual/test_30_codex_takeover_tools.py::test_ai_command_advances_when_accepted_action_ends_actor_turn`
- **Error**: The test monkeypatches `server.event_server.execute_action_by_index`, but the command route no longer calls that symbol. The real movement therefore executes, and `payload.turn_continues` remains `True` instead of matching the mocked turn-ending result.
- **Hypothesis**: The test mock is stale and must patch the command route's current execution boundary rather than the obsolete imported symbol.
- **Status**: OPEN

### Reckless interposition performance fixture has a stale semantic reference
- **Found**: 2026-07-15 during focused validation of Reckless interposition; unrelated stale fixture failure.
- **Test file**: `tests/manual/test_43_ai_runtime_performance.py::test_reckless_augmentation_interposes_before_retained_move_attack_goal`
- **Error**: The test fails before policy evaluation while `_load_reckless_bridge_world_at_cursor` loads its retained fixture. The fixture expects semantic reference `setup.reckless_attack@v1:8e695d3ea70ac98c`, but the current computed reference is `setup.reckless_attack@v1:c11f9113b045a880`.
- **Hypothesis**: `_load_reckless_bridge_world_at_cursor` does not apply the repository's existing legacy semantic migration helper. Apply that helper at this retained-fixture loading boundary or refresh the fixture through the canonical migration path.
- **Preserved behavior**: The live exact-seed `caster_crossfire` replay now proves that Reckless augmentation interposes before the retained move-attack goal.
- **Status**: OPEN

### Subjective observation stream test leaves unpacked encounter unused
- **Found**: 2026-07-15 during focused type checking; unrelated and pre-existing.
- **Test file**: `tests/manual/test_28_subjective_observation_stream.py`
- **Command**: `uv run pyright tests/manual/test_28_subjective_observation_stream.py`
- **Error**: `/mnt/c/Users/tommaso/Documents/Dev/dnd_engine/tests/manual/test_28_subjective_observation_stream.py:1165:40 - error: Variable "encounter" is not accessed (reportUnusedVariable)`
- **Hypothesis**: A tuple result from `create_observation_game()` is unpacked, but the `encounter` value is unused in this test.
- **Status**: OPEN

### Live replication tutorial has stale exact event-count readouts
- **Found**: 2026-07-15 during focused regression validation of the seamless subjective runtime; reconfirmed 2026-07-20 as unrelated to the current SDK work.
- **Test file**: `tests/manual/test_25_live_replication_streams.py` (3 failures)
- **Command**: `uv run pytest -q tests/manual/test_25_live_replication_streams.py::test_cursor_replay_returns_events_and_logs_after_saved_cursors tests/manual/test_25_live_replication_streams.py::test_live_subscription_fans_out_game_events_and_combat_logs tests/manual/test_25_live_replication_streams.py::test_combat_log_frames_follow_completion_events_in_the_queue`
- **Failing tests**: `test_cursor_replay_returns_events_and_logs_after_saved_cursors`, `test_live_subscription_fans_out_game_events_and_combat_logs`, and `test_combat_log_frames_follow_completion_events_in_the_queue`.
- **Actual vs expected**: `test_cursor_replay_returns_events_and_logs_after_saved_cursors` expects 26 game events, 6 completions, and final cursor 68, but receives 30 game events, 7 completions, and final cursor 72. `test_live_subscription_fans_out_game_events_and_combat_logs` expects 27 total envelopes / 26 game events and latest stream id `e=68;l=2`, but receives 31 total envelopes / 30 game events and `e=72;l=2`. `test_combat_log_frames_follow_completion_events_in_the_queue` expects the first combat log at index 26 after completion index 25 with 6 prior completions, but receives it at index 30 after completion index 29 with 7 prior completions.
- **Preserved semantics**: Cursor replay starts at the saved cursor, every event cursor equals its event index plus one, the latest event cursor matches `EventQueue`, stream ids match their cursor pairs, the latest game event is a completion, and the combat-log envelope remains strictly ordered after the final completion. Only the exact golden readout assertions fail.
- **Cause**: The canonical attack lifecycle now includes all four phases of the factual `DamageAppliedEvent`. Its completion accounts for the seventh completion, and the complete lifecycle moves the final cursor from 68 to 72.
- **Resolution**: Refreshed the tutorial readouts while retaining the semantic replay, cursor continuity, stream-id, completion ordering, and combat-log ordering assertions.
- **Status**: RESOLVED 2026-07-20

### Spell-family manual test has stale Pyright annotations and optional narrowing
- **Found**: 2026-07-15 during focused type checking of entity and spell-family changes; unrelated and pre-existing relative to that work.
- **Test file**: `tests/manual/test_14_spell_families.py` (5 Pyright errors at lines 102, 172, 354, and 722)
- **Command**: `uv run pyright dnd/entity.py dnd/spells/abjuration.py dnd/spells/illusion.py tests/manual/test_14_spell_families.py`
- **Error**: The saving-throw helper passes a general `str` where `get_saving_throw()` requires `AbilityName` at line 102. Readout construction accesses optional `attack_outcome.value` at line 172 and optional `dice_roll.results` / `dice_roll.total` at line 354 without narrowing. The Sleep target-name readout accesses `.name` on the optional result of `Entity.get()` at line 722.
- **Hypothesis**: These are stale test typing issues rather than production spell failures. The helper parameter should use `AbilityName`, and the readout paths should explicitly narrow the completed event fields and entity lookup before member access.
- **Status**: OPEN

### Local read-model test double does not satisfy the subjective runtime protocol
- **Found**: 2026-07-14 during focused type checking of the local read-model tests.
- **Test file**: `tests/manual/test_50_codex_local_read_model.py` (2 pyright errors at lines 29 and 63; both runtime tests pass)
- **Command**: `uv run pyright ... tests/manual/test_50_codex_local_read_model.py`
- **Error**: `_ArtifactRuntime` is passed to `HotCodexRuntime` but does not satisfy `SubjectiveRuntimeLike`; it is missing `wait_for_epoch`, `execute`, and `end_turn`.
- **Hypothesis**: This is an incomplete test double/type-check issue, not a production runtime failure. Make the fake explicitly implement the complete protocol with unreachable or stub command methods, or narrow the constructor dependency for read-only tests without weakening the production protocol.
- **Resolution**: The read-only fake now implements every runtime protocol method with explicit unreachable command stubs, uses the typed policy telemetry contract, and no longer exposes the deleted `materialized` state alias.
- **Status**: RESOLVED 2026-07-14; the focused test file passes all 3 tests and focused Pyright is clean.

### SRD rule mapping references a missing interactive-ruleset index
- **Found**: 2026-07-14 during focused `uv run pytest tests/engine_book/test_srd_rule_mapping.py -q`; unrelated and pre-existing relative to the AI legacy removal.
- **Test file**: `tests/engine_book/test_srd_rule_mapping.py::test_srd_rule_mapping_sources_exist_and_have_relationship_labels`
- **Error**: `00-neurodragon-dev-manual.mdx` references the missing source `interactive_ruleset/README.md`.
- **Hypothesis**: Mapping row `00` needs an existing umbrella source, or the local ruleset needs its intended index restored; do not invent either during AI cleanup.
- **Status**: OPEN

### Subjective action query return type disagrees with its annotation
- **Found**: 2026-07-14 during the legacy AI cleanup focused type check; unrelated and pre-existing relative to the deleted legacy stack.
- **Command**: `uv run pyright ai dnd/controller.py dnd/scenarios/controller_catalogue.py dnd/scenarios/__init__.py tests/manual/test_24_built_in_controllers.py`
- **Error**: `ai/subjective/queries.py:32:16` returns `Tuple[ActionAffordance, ...]`, but its annotation promises `list[ActionAffordance]` (`reportReturnType`).
- **Hypothesis**: The return annotation should express an immutable tuple or `Sequence`, or the implementation should deliberately materialize a list, according to the intended query API contract.
- **Status**: OPEN

### Engine-book integrity is missing five parity rows
- **Found**: 2026-07-14 while running focused validation during legacy AI cleanup; appears unrelated and pre-existing relative to that cleanup.
- **Test file**: `tests/engine_book/test_book_integrity.py`
- **Error**: The integrity checks report missing parity rows for `EB-11-022`, `EB-11-023`, `EB-12-020`, `EB-12-021`, and `EB-12-022`.
- **Hypothesis**: New or renumbered Chapter 11 and 12 examples were not added to the engine-book parity metadata.
- **Status**: OPEN

### Engine-book Chapter 11 and 12 outline ranges are stale
- **Found**: 2026-07-14 while running focused validation during legacy AI cleanup; appears unrelated and pre-existing relative to that cleanup.
- **Test file**: `tests/engine_book/test_book_integrity.py`
- **Error**: Chapter 11 is expected to extend through `023` but the outline ends at `021`; Chapter 12 is expected to extend through `022` but the outline ends at `019`.
- **Hypothesis**: The chapter outline ranges were not updated when later examples were introduced.
- **Status**: OPEN

### Engine-book integrity expects a missing timing middleware symbol
- **Found**: 2026-07-14 while running focused validation during legacy AI cleanup; appears unrelated and pre-existing relative to that cleanup.
- **Test file**: `tests/engine_book/test_book_integrity.py`
- **Error**: The integrity check expects a top-level `server.event_server.timing_middleware`, but that symbol is absent.
- **Hypothesis**: The middleware was renamed, moved, or removed without updating the integrity contract.
- **Status**: OPEN

### advance_encounter lacks the required Google-style Args block
- **Found**: 2026-07-14 while running focused validation during legacy AI cleanup; appears unrelated and pre-existing relative to that cleanup.
- **Test file**: `tests/engine_book/test_book_integrity.py`
- **Error**: The docstring integrity check reports that `advance_encounter` has parameters but no Google-style `Args:` block.
- **Hypothesis**: The function signature changed or its docstring predates the current Google-style documentation requirement.
- **Status**: OPEN

### Seeded external self-play is not replay-stable across fresh UUID allocations
- **Found**: 2026-07-14 comparing `ai/evidence/runs/20260714-v133-spacing-sensory-validation.json` with `ai/evidence/runs/20260714-v134-nonoverlapping-timing-validation.json`, then reproducing with two fresh processes running `run_external_selfplay("skeleton_anti_aoe_split", random_seed=2026071406, hero_first=True)`.
- **Test file**: Add a UUID-renaming regression to `tests/manual/test_44_typed_agent_policy.py` and a normalized cross-subprocess replay check to `tests/manual/test_39_ai_validation_harness.py`.
- **Error**: Both artifacts have the same seed and policy hash, but v133 ends after 26 commands with final monster HP `-2/-3/-5`, while v134 ends after 20 with `-4/-1/0`. At command 9 both rank 41 proposals and select score `180.012`; v133 selects Warlock UUID `1b29...` and v134 selects Warrior UUID `6e57...`, respectively the lexicographically smallest monster UUID in each process. Fresh reproduction also selected different command-9 primaries and ended in 30 versus 26 commands.
- **Hypothesis**: `ai.external_selfplay.run_external_selfplay()` seeds only Python `random`, while arena actor IDs come from unseeded `uuid4()` calls. `ai/policy/candidates.py::_additional_targets()` and `_optimize_repeat_allocation()` sort UUID sets and break equal allocations by UUID, and `ai/policy/utility.py::UtilityArbiter._sort_key()` breaks equal proposal scores by a `row_id` containing the target UUID. The relevant sets are sorted, so raw hash iteration is not the observed cause; the unstable UUID sort key is. `dnd/spells/evocation.py::ScorchingRay.get_all_targets()` puts the UUID-selected primary first, then `dnd/core/base_actions.py::BaseAction.apply()` resolves that list sequentially, assigning the same seeded attack/damage stream to different creatures and cascading into different outcomes.
- **Recommendation**: Build two equivalent typed-policy contexts whose actor names, positions, HP, actions, and outcome profiles match but whose opaque UUID labels are permuted; assert identical target names, allocation order, and selected intent after UUID normalization. Also launch the arena twice via separate subprocesses and compare normalized semantic traces, command counts, and final HP. Replace UUID fallbacks in policy/allocation ordering with a stable semantic replay key before expecting the subprocess test to pass.
- **Resolution**: Added identity-independent semantic replay keys to production policy proposals and utility arbitration. Multi-target damage/control allocation, execution ordering, outcome evidence, spacing/contact selection, and bounded routines now order equal choices through disclosed action semantics plus known target/object positions and normalized names. Opaque `row_id` remains only as a compatibility fallback for custom proposals without a semantic replay key.
- **Verification**: `tests/manual/test_44_typed_agent_policy.py::test_equal_multi_target_choices_are_invariant_to_opaque_uuid_labels` permutes target UUIDs and preserves primary position and projectile allocation. `tests/manual/test_39_ai_validation_harness.py::test_external_selfplay_seed_replays_across_fresh_processes` launches fresh interpreters with different `PYTHONHASHSEED` values, confirms disjoint actor UUIDs and an equal composite policy hash, then reproduces the complete normalized split-skeleton trace and final HP. Full focused files pass: `40 passed` in test 44, `16 passed` in test 48, and `17 passed` in test 39.
- **Status**: RESOLVED

### Combat tutorial test file has stale pyright narrowing errors
- **Found**: 2026-07-04 while validating the prone auto-stand regression added during AI zone-control iteration.
- **Test file**: `tests/manual/test_10_combat_resolution.py`
- **Error**: `uv run pyright ai/external/state.py ai/external/policy.py dnd/actions_functional.py tests/manual/test_35_subjective_external_ai.py tests/manual/test_10_combat_resolution.py` reports pre-existing typing issues in the combat tutorial file: an unused `DamageType` import, optional subscripts/member access, and generic `Event` values that are not narrowed before reading `contest_success` / `push_distance`.
- **Hypothesis**: Runtime tests pass, but the tutorial test file predates stricter pyright narrowing for concrete event subclasses. The issue is local to test typing, not the prone auto-stand behavior.
- **Status**: OPEN

### Hold Person initial save may leave caster concentrating with no held target
- **Found**: 2026-07-04 during `condition_lock_sanctum` external self-play while adding control outcome telemetry.
- **Test file**: Not isolated yet. Observed in `ai.external_selfplay.run_external_selfplay("condition_lock_sanctum")`.
- **Error**: One accepted `Hold Person__slot_2` command returned the message `Hold Person - target saved (still concentrating)`. If the initial save succeeds and no target is held, the expected rules-facing behavior is likely that the spell effect ends rather than leaving the caster concentrating.
- **Hypothesis**: The Hold Person spell path may start or retain concentration before confirming at least one target failed the initial save, or the combat-log message may incorrectly report concentration state after a resisted control attempt.
- **Status**: OPEN

### Free powerful consumable rows distort challenge measurements
- **Found**: 2026-07-04 across Barbarian, Sorcerer, skeleton, and hazard validation rotations.
- **Test file**: Not isolated as a failing rule test. Observed in external self-play batches including `buff_consumable_ambush`, `skeleton_mark_focus_fire`, `multi_projectile_no_aoe_lab`, and `forced_movement_hazard_bridge`.
- **Error**: Haste, Greater Invisibility, and healing potion rows can appear as free or low-friction item-use options. The policy can use them sensibly, but they strongly distort encounter difficulty and make challenge measurements hard to compare across arenas.
- **Hypothesis**: Consumable item-use action economy/cost policy is not explicit enough for challenge validation. Free doors/levers may be intended videogame interactions, but free high-power consumables need a separate balance decision.
- **Status**: OPEN

### AI epoch Move row can be rejected by execute-by-index as failed movement
- **Found**: 2026-07-04 during `buff_consumable_ambush` external self-play after adding opening item-buff behavior.
- **Test file**: Not yet isolated. Observed in `ai.external_selfplay.run_external_selfplay("buff_consumable_ambush")`.
- **Error**: The Barbarian selected a legal decision-epoch `Move` row toward `(13, 6)` with reason `move_toward_visible_enemy`, but `/ai/sessions/{session_id}/commands/execute` returned `rejected` with message `Failed to move for Move`.
- **Hypothesis**: A movement row generated by the epoch can become non-executable by the time `execute_by_index` applies it, or the movement target serializer/executor disagree about path legality. This may involve path blockers, occupied cells, or safe-path preference around the open-door arena after several forced/reposition moves.
- **Status**: OPEN

### Ranged-harrier hold-spacing command reports enemy position instead of spacing anchor
- **Found**: 2026-07-04 while validating the Sorcerer-Barbarian self-play harness with the broader external AI regression file.
- **Test file**: `tests/manual/test_35_subjective_external_ai.py::test_ranged_harrier_skips_healthy_melee_follow_up_after_spending_action`
- **Error**: The policy correctly ends turn with `hold_ranged_spacing` after spending the action, but `reference_entity_position` is `(3, 1)` while the test expects the spacing anchor `(5, 1)`.
- **Hypothesis**: The behavior is tactically correct, but the metadata contract is muddled: `reference_entity_position` currently means the referenced enemy position, while this test expects the desired spacing/anchor position. The policy payload likely needs a separate field for spacing anchor instead of overloading reference entity metadata.
- **Resolution**: Fixed by adding `spacing_anchor_position` to `AgentCommand` and keeping `reference_entity_position` as the actual subjective enemy position. The regression now asserts both fields explicitly.
- **Verification**: `uv run pytest tests/manual/test_35_subjective_external_ai.py -q`; `uv run pyright ai/external/policy.py tests/manual/test_35_subjective_external_ai.py`.
- **Status**: RESOLVED

### Codex subjective final brief can omit the final killed enemy
- **Found**: 2026-07-02 during Codex barbarian full-game playtest through `ai.codex_tools`.
- **Test file**: Not yet covered. Observed after a completed `/simulation/start-human?character_class=barbarian` game with Codex controlling heroes and external AI controlling monsters.
- **Error**: After the final Frenzied Strike ended the encounter, `ai.codex_tools turn` showed no living enemies and listed the previously killed Skeleton Warrior and Skeleton Archer as dead, but did not list the final killed Skeleton Warlock in `visible_entities`/`dead_enemies`.
- **Hypothesis**: The final death/encounter-end observation frame may clear or fail to materialize the last killed entity for the Codex session, possibly because visibility projection stops after encounter end or because the death transition is not retained as remembered knowledge.
- **Status**: OPEN

### External AI can submit a stale command immediately after turn-start epoch
- **Found**: 2026-07-02 in server logs during Codex barbarian playtest cleanup.
- **Test file**: Not yet isolated. Runtime logs from `/tmp/dnd_engine_barbarian.log`.
- **Error**: The external AI received a `turn_start` decision epoch, selected `Eldritch Blast`, then the command endpoint rejected it as stale because the current epoch had advanced to a `snapshot` epoch at the next observation cursor. The agent recovered through resync and retried successfully.
- **Hypothesis**: Snapshot/epoch generation can supersede a just-emitted turn-start epoch before the external agent submits its command. Epoch identity may need a more stable per-decision boundary, or the command validator should accept semantically equivalent epochs when no game-state-changing event occurred between them.
- **Status**: OPEN

### Directional environment example scripts have stale pyright types
- **Found**: 2026-06-28 during directional environment item metadata hygiene.
- **Test file**: `examples/test_directional_environment_items.py`, `examples/test_directional_arena_hotswap.py`
- **Error**: `uv run pyright dnd/items/environment.py examples/test_directional_environment_items.py examples/test_directional_arena_hotswap.py` reports optional-member access on `object_at(...).uuid` in the arena hotswap script and passes generic `Event` declarations into `Attack._validate()` where pyright expects `AttackEvent` in the directional environment script.
- **Hypothesis**: Runtime guards already protect these paths, but the script helpers do not narrow optional and event types enough for pyright. This appears to be a stale example typing issue, not a directional item behavior regression.
- **Resolution**: Fixed by narrowing attack declaration events with `isinstance(..., AttackEvent)` before calling `Attack._validate()` and by making the arena `object_at()` helper generic with explicit wall-object narrowing before reading `.uuid`.
- **Verification**: `uv run pyright dnd/items/environment.py examples/test_directional_environment_items.py examples/test_directional_arena_hotswap.py`, `uv run python examples/test_directional_environment_items.py`, and `uv run python examples/test_directional_arena_hotswap.py` pass.
- **Status**: RESOLVED

### Core action engine-book example has stale pyright types
- **Found**: 2026-06-28 during health block metadata hygiene.
- **Test file**: `examples/test_engine_book_core_actions_combat.py`
- **Error**: `uv run pyright dnd/blocks/health.py examples/test_engine_book_entity_composition.py examples/test_engine_book_core_actions_combat.py` reports stale typing in the core-action example script: indirect `dnd.core.dice` monkeypatch attributes, generic `Event` values passed to `Attack._validate()`, optional status-message string access, generic event attributes, and shield/weapon union narrowing.
- **Hypothesis**: Runtime behavior is protected by the script and pytest parity layer, but the example uses dynamic test helpers and event filtering patterns that pyright cannot narrow. This appears to be an example typing backlog, not a health-block regression.
- **Resolution**: Fixed in `examples/test_engine_book_core_actions_combat.py` by importing the dice module directly for deterministic monkeypatching, narrowing attack declaration events with `isinstance(..., AttackEvent)` before validation, guarding optional status messages, filtering event history to concrete event payload classes, and narrowing melee-main equipment to `Weapon` before adding extra damage dice.
- **Verification**: `uv run pyright dnd/blocks/health.py examples/test_engine_book_entity_composition.py examples/test_engine_book_core_actions_combat.py`, `uv run python examples/test_engine_book_core_actions_combat.py`, `uv run pytest -q tests/engine_book/test_chapter_10_core_actions_combat.py tests/engine_book/test_book_integrity.py`, and `uv run pytest -q tests/engine_book` pass.
- **Status**: RESOLVED

### Retaliation reaction attack also spent the normal action
- **Found**: 2026-06-28 during Chapter 16 Retaliation parity expansion.
- **Test file**: `examples/test_engine_book_class_features.py`
- **Error**: `retaliation_processor()` instantiated a normal `Attack`, so a triggered Retaliation spent the Barbarian's normal action through `Attack._apply_costs()` and then spent the reaction manually.
- **Hypothesis**: Retaliation should own the reaction cost and the nested attack should be costless, matching the feature's reaction-attack contract.
- **Resolution**: Fixed in `dnd/classes/barbarian.py` by constructing the Retaliation `Attack` with `costs=[]` and leaving the explicit reaction spend in the handler.
- **Verification**: EB-16-022 proves a successful adjacent Retaliation reduces the attacker's HP, spends the reaction, preserves the Barbarian's action, and respects no-reaction, distance, weapon, and cleanup gates.
- **Status**: RESOLVED

### Indomitable Might skill-check mutation does not recompute outcome
- **Found**: 2026-06-28 during Chapter 16 Barbarian event-heavy parity expansion.
- **Test file**: Exploratory verification while extending `examples/test_engine_book_class_features.py`.
- **Error**: A forced-low Athletics `SkillCheckEvent` for a level-18 Barbarian with Indomitable Might emitted an EFFECT event whose dice total was replaced with the Strength score (`20`), but the event `result` stayed `False`, the completion event also kept `result == False`, and `Entity.skill_check()` returned the original pre-handler roll total (`6`) with `success == False`.
- **Hypothesis**: `Entity.skill_check()` computes `skill_check_outcome` and `success` before firing SKILL_CHECK EFFECT handlers. `indomitable_might_processor()` replaces `event.dice_roll.total`, but neither the processor nor `Entity.skill_check()` recomputes `result`, and the method returns the local pre-handler `roll` and `success`.
- **Resolution**: Fixed in `dnd/entity.py` by recomputing the skill-check outcome from the post-handler EFFECT event's final dice roll before phasing to COMPLETION, and by returning that final roll/result from `Entity.skill_check()`.
- **Verification**: EB-16-021 proves low Athletics checks are raised to the Strength score, the returned API result and completed `SkillCheckEvent.result` both become successful, non-Athletics checks are unchanged, and removing Indomitable Might removes the handler behavior.
- **Status**: RESOLVED

### Heal roll-result helper did not complete result events
- **Found**: 2026-06-28 during Chapter 03 dice/result parity expansion
- **Test file**: `examples/test_engine_book_dice_events.py`
- **Error**: `fire_heal_roll_result()` fired `HEAL_ROLL_RESULT` through `EFFECT` and returned the final roll, but unlike d20 and damage result paths it did not phase the roll-result event to `COMPLETION`.
- **Hypothesis**: The helper mirrored handler interception but missed the lifecycle completion step that keeps event history and parent lineage consistent with other roll-result systems.
- **Resolution**: Fixed in `dnd/spells/spell_utils.py` by completing the `HealRollResultEvent` after EFFECT handlers run.
- **Verification**: EB-03-015 proves healing result events now store DECLARATION, EFFECT, and COMPLETION phases and preserve the parent lineage while returning the final roll.
- **Status**: RESOLVED

### HealEvent total_healing mutations were ignored during HP application
- **Found**: 2026-06-28 during Chapter 03 dice/result parity expansion
- **Test file**: `examples/test_engine_book_dice_events.py`
- **Error**: `Entity.receive_healing()` let `HEAL` EFFECT handlers mutate `HealEvent.total_healing`, but HP application still called `self.health.heal(amount)` with the original requested amount. Canceled healing already blocked HP changes; reduced or increased healing did not.
- **Hypothesis**: The method treated the post-EFFECT `HealEvent` as observational metadata instead of the source of truth for the final amount to apply.
- **Resolution**: Fixed in `dnd/entity.py` by applying `max(0, heal_event.total_healing)` after EFFECT handlers run.
- **Verification**: EB-03-018 proves reduced healing applies the handler-mutated amount, while canceled healing leaves HP unchanged and completes with `actual_healing == 0`.
- **Status**: RESOLVED

### Chained d20 replacement audit used the original roll for every entry
- **Found**: 2026-06-28 during Chapter 03 dice/result parity expansion
- **Test file**: `examples/test_engine_book_dice_events.py`
- **Error**: `D20RollResultEvent.replace_roll()` used `self.roll.total` as the old total for every audit entry. Later handlers received the current effective replacement, but the audit text for a second replacement still described original-to-new instead of previous-effective-to-new.
- **Hypothesis**: The single-roll d20 path predated the multi-handler audit pattern used by damage result events and did not call `get_effective_roll()` when creating its audit message.
- **Resolution**: Fixed in `dnd/core/events.py` by deriving the old total from `self.get_effective_roll().total` before storing the new `final_roll`.
- **Verification**: EB-03-019 proves simple exact attack d20 handlers run before filtered exact handlers, later handlers see the previous effective total, and audit entries record 5 to 12, then 12 to 15, then 15 to 18.
- **Status**: RESOLVED

### Real attack d20 result events lost weapon-slot context
- **Found**: 2026-06-28 during Chapter 03 dice/result parity expansion
- **Test file**: `examples/test_engine_book_dice_events.py`
- **Error**: `Attack._apply()` created `AttackD20RollResultEvent` through `Entity.roll_d20()` without passing the active `weapon_slot`, so real attack d20 result handlers saw `weapon_slot is None`.
- **Hypothesis**: The attack pipeline threaded `weapon_slot` into attack validation and damage but skipped the result-event call.
- **Resolution**: Fixed in `dnd/actions.py` by passing `weapon_slot=weapon_slot` to `source_entity.roll_d20(...)`.
- **Verification**: EB-03-016 proves a real `MELEE_MAIN` attack completion event carries `weapon_slot == WeaponSlot.MELEE_MAIN`.
- **Status**: RESOLVED

### Great Weapon Fighting applied beyond eligible two-handed weapon dice
- **Found**: 2026-06-28 during Chapter 03 dice/result parity expansion
- **Test file**: `examples/test_engine_book_dice_events.py`
- **Error**: The GWF processor rerolled every damage packet in `DamageRollResultEvent.final_rolls` using the main weapon's die size, and treated any versatile melee weapon as eligible even when a shield occupied the off hand.
- **Hypothesis**: The processor conflated all attack damage packets with primary weapon damage and had no explicit two-hand check for versatile weapons.
- **Resolution**: Fixed in `dnd/classes/fighter.py` by rerolling only the primary damage packet and by requiring versatile weapons to be in `MELEE_MAIN` with an empty melee off hand.
- **Verification**: EB-03-013 proves positive/no-low/ranged/one-handed GWF filters, EB-03-016 proves extra damage packets are preserved, and EB-03-017 proves shielded versatile weapons do not qualify while unshielded versatile weapons do.
- **Status**: RESOLVED

### Paralyzed did not grant attacker advantage
- **Found**: 2026-06-28 during Chapter 08 standard-condition parity expansion
- **Test file**: `examples/test_engine_book_standard_conditions.py`
- **Error**: `Paralyzed` applied Incapacitated, Strength/Dexterity save auto-failures, and close-range auto-critical hits, but did not add the SRD attacker-advantage modifier even though the condition description included that clause.
- **Hypothesis**: The severe-condition implementation added the close-range critical target-side contextual modifier but skipped the static target-side advantage modifier that similar conditions such as `Stunned` and `Unconscious` already use.
- **Resolution**: Fixed in `Paralyzed._apply()` by adding a static `AdvantageStatus.ADVANTAGE` modifier to the target's `equipment.ac_bonus.to_target_static`.
- **Verification**: EB-08-006 now proves paralyzed targets grant attacker advantage at both adjacent and distant ranges, while adjacent attackers still get `AUTOCRIT` and distant attackers do not.
- **Status**: RESOLVED

### Critical immunity status was ignored by attack outcome resolution
- **Found**: 2026-06-28 during Chapter 03 engine-book parity expansion
- **Test file**: `examples/test_engine_book_dice_events.py`
- **Error**: `ModifiableValue.critical` could resolve to `CriticalStatus.NOCRIT`, but `determine_attack_outcome()` ignored that status. Natural 20s, lowered critical thresholds, and `AUTOCRIT` could still return `AttackOutcome.CRIT` when the roll carried `NOCRIT`.
- **Hypothesis**: The value layer had a critical-immunity state, but the shared d20 outcome interpreter only checked `AUTOCRIT`.
- **Resolution**: Fixed in `determine_attack_outcome()` by downgrading otherwise-critical hits to ordinary hits when `roll.critical_status == CriticalStatus.NOCRIT`, while preserving `AUTOMISS`, `AUTOHIT`, natural 1, and miss behavior.
- **Verification**: EB-03-009 proves `AUTOMISS` beats natural 20, `AUTOHIT` beats natural 1, `AUTOCRIT` can upgrade auto-hits, `NOCRIT` suppresses natural-20 and threshold criticals, and `AUTOCRIT`/lowered thresholds do not make ordinary misses hit.
- **Status**: RESOLVED

### Inactive contextual damage-type modifiers raised during aggregation
- **Found**: 2026-06-28 during Chapter 02 engine-book parity expansion
- **Test file**: `examples/test_engine_book_modifiable_values.py`
- **Error**: `ContextualValue.damage_types` called `max(type_counts.values())` even when every contextual damage-type callable returned `None`, so inactive contextual damage-type modifiers could raise `ValueError` instead of contributing no type.
- **Hypothesis**: The contextual damage-type aggregation path missed the same empty-active-result guard already used by other contextual modifier channels.
- **Resolution**: Fixed by returning an empty damage-type list when contextual damage-type modifiers exist but none evaluate to a concrete `DamageTypeModifier`.
- **Verification**: EB-02-011 proves inactive contextual damage-type modifiers leave both the contextual channel and aggregate `ModifiableValue` with no damage type, then contribute normally when context activates the callable.
- **Status**: RESOLVED

### BaseBlock constructor source propagation runs before field discovery
- **Found**: 2026-05-29 during Chapter 05 engine-book parity expansion
- **Test file**: `examples/test_engine_book_blocks_context.py`
- **Error**: `BaseBlock.set_values_and_blocks_source()` and `validate_values_and_blocks_source_and_target()` run before `populate_blocks_and_values()` discovers explicit Pydantic `ModifiableValue` and child `BaseBlock` fields. Constructor-provided fields with mismatched sources can remain mismatched after construction.
- **Hypothesis**: `populate_blocks_and_values()` likely needs to run before source/target/context normalization and validation, or discovery should happen in a pre/post-init path before those validators depend on `self.values` and `self.blocks`.
- **Resolution**: Fixed on 2026-06-27 in `BaseBlock.set_values_and_blocks_source()` by populating direct value/block indexes before source, target, and context propagation or validation run.
- **Verification**: EB-05-013 now proves constructor-provided foreign direct values and child blocks are discovered and normalized to the parent source, target, and context.
- **Status**: RESOLVED

### BaseBlock indexes canceled no-effect condition applications
- **Found**: 2026-05-29 during Chapter 05 engine-book parity expansion
- **Test file**: `examples/test_engine_book_blocks_context.py`
- **Error**: `BaseCondition.apply()` returns a canceled event when `_apply()` returns no effect event, but `BaseBlock.add_condition()` treats that truthy event as success and indexes the condition even though `condition.applied` is `False`.
- **Hypothesis**: `BaseBlock.add_condition()` should probably require a non-canceled completion event, or `BaseCondition.apply()` should return `None` for failed application. Current behavior is documented as EB-05-010 until Tommaso approves a behavior change.
- **Resolution**: Fixed on 2026-06-27 in `BaseBlock.add_condition()` by indexing only when the returned event is not canceled and `condition.applied` is true.
- **Verification**: EB-05-010 and EB-07-010 now prove no-effect condition applications return a canceled event for observability but do not write active-condition name, UUID, or source indexes.
- **Status**: RESOLVED

### Repeated standard action setup duplicates handlers
- **Found**: 2026-05-29 during Chapter 06 engine-book parity expansion
- **Test file**: `examples/test_engine_book_entity_composition.py`
- **Error**: Calling `setup_standard_actions(entity)` twice clears action templates but leaves existing handlers registered. The second call doubles the source entity's global `EventQueue` handlers from 6 to 12 and doubles entity-tracked handlers from 4 to 8.
- **Hypothesis**: Standard action setup should either remove/replace prior handlers by name/source before registering new ones, or be documented as one-time initialization and guarded against repeated calls. Current behavior is documented as EB-06-014 until Tommaso approves a behavior change.
- **Resolution**: Fixed on 2026-06-27 in `setup_standard_actions()` by removing prior standard entity handlers and weapon-template handlers for the entity before re-registering the standard template/handler set.
- **Verification**: EB-06-014 now proves repeated setup leaves six global standard handlers and four entity-owned handlers with one copy of each standard handler name.
- **Status**: RESOLVED

### Intermittent control-spell repeat-save cleanup failure
- **Found**: 2026-06-27 during Chapter 07 condition-lifecycle hygiene verification
- **Test file**: `tests/engine_book/test_chapter_15_spell_families.py`
- **Error**: One run of `uv run pytest -s -q tests/engine_book` failed `test_eb_15_017_hold_person_failed_save_repeat_save_and_cleanup`: after `target.on_turn_end(...)`, `"Hold Person"` remained in `target.active_conditions`. Running the Chapter 15 spell-family parity file in isolation passed, and an immediate full `tests/engine_book` rerun also passed (`221 passed`).
- **Repeat**: Recurred on 2026-06-27 during Chapter 15 illusion hygiene verification. The full `tests/engine_book` run failed the same assertion after `target.on_turn_end(...)`; an immediate focused rerun of `tests/engine_book/test_chapter_15_spell_families.py::test_chapter_15_example_parity` passed (`21 passed`).
- **Repeat**: Recurred on 2026-06-27 during Chapter 15 necromancy hygiene verification. `uv run python examples/test_engine_book_spell_families.py` failed the same assertion in `test_eb_15_017_hold_person_failed_save_repeat_save_and_cleanup` after `target.on_turn_end(...)`, while the focused Chapter 15/book-integrity pytest layer passed in the same verification window.
- **Repeat**: Recurred again on 2026-06-27 during the same necromancy verification rerun. `uv run python examples/test_engine_book_spell_families.py` next failed the sibling assertion in `test_eb_15_018_hold_monster_excludes_undead_and_repeats_cleanup`: after `target.on_turn_end(...)`, `"Hold Monster"` remained in `target.active_conditions`.
- **Repeat**: Recurred on 2026-06-27 during Chapter 15 conjuration hygiene verification. `uv run pytest -s -q tests/engine_book/test_chapter_15_spell_families.py tests/engine_book/test_book_integrity.py` failed `test_eb_15_018_hold_monster_excludes_undead_and_repeats_cleanup` with `"Hold Monster"` still active after `target.on_turn_end(...)`; an immediate rerun of the same command passed (`27 passed`), and the full `tests/engine_book` suite passed in the same verification window (`221 passed`).
- **Repeat**: Recurred on 2026-06-27 during Chapter 15 evocation hygiene verification. `uv run pytest -s -q tests/engine_book/test_chapter_15_spell_families.py tests/engine_book/test_book_integrity.py` failed `test_eb_15_018_hold_monster_excludes_undead_and_repeats_cleanup` with `"Hold Monster"` still active after `target.on_turn_end(...)`; an immediate focused Chapter 15 rerun passed (`21 passed`), the narrow Chapter 15/book-integrity gate passed (`27 passed`), and the full `tests/engine_book` suite passed (`221 passed`).
- **Hypothesis**: This looks like an intermittent full-suite ordering/state leak or nondeterministic handler/save interaction around repeat-save cleanup. Check global registries, `EventQueue` handlers, and spell-family reset helpers if it repeats.
- **Resolution**: Fixed on 2026-06-27 in `dnd/entity.py` by making `determine_attack_outcome()` apply natural 1/critical-face semantics only to `RollType.ATTACK`. Saving throws and skill checks now compare `DiceRoll.total` to DC, matching the SRD relationship recorded in Chapter 03. The apparent intermittent cleanup failure was a natural-1 repeat save with a total high enough to beat the DC being treated as `CRIT_MISS`, so the hold condition correctly stayed active under the old engine behavior.
- **Verification**: Added EB-03-007 in `examples/test_engine_book_dice_events.py`; 200-iteration Hold Person and Hold Monster cleanup repro loops passed; `uv run pytest -s -q tests/engine_book/test_chapter_03_dice_events.py tests/engine_book/test_book_integrity.py` passed (`13 passed`); `uv run pytest -s -q tests/engine_book/test_chapter_15_spell_families.py tests/engine_book/test_book_integrity.py` passed (`27 passed`); full `uv run pytest -s -q tests/engine_book` passed (`222 passed`).
- **Status**: RESOLVED

### Partial stack merge can mutate inventory before capacity failure
- **Found**: 2026-06-08 during Chapter 13 engine-book parity expansion
- **Test file**: `examples/test_engine_book_items_inventory_equipment.py`
- **Error**: `Inventory.add_item()` merges as much of an incoming compatible stack as possible before checking whether the remaining stack can be inserted. If the final insert fails because of weight capacity, the method returns `False`, but the existing stack has already increased and the incoming stack has already decreased.
- **Hypothesis**: Stack insertion likely needs to precompute the full merge/remainder outcome before mutating either stack, or define `False` as partial-success-with-remainder and expose that explicitly. Current behavior is documented as EB-13-012 until Tommaso approves a behavior change.
- **Resolution**: Fixed on 2026-06-27 in `Inventory.add_item()` by using the same hypothetical merge/remainder plan for `can_add()` and `add_item()` before mutating stack counts.
- **Verification**: EB-13-012 now proves a failed capacity add leaves the existing stack, incoming stack, inventory membership, and total weight unchanged.
- **Status**: RESOLVED

### Transfer into existing stack can stamp consumed item as stored
- **Found**: 2026-06-27 during Chapter 13 engine-book parity expansion
- **Test file**: `examples/test_engine_book_items_inventory_equipment.py`
- **Error**: `Inventory.transfer_to()` could transfer an item into an already-compatible target stack, let `Inventory.add_item()` consume and unregister the incoming object, then stamp that consumed object with the target owner and storage UUID even though it was not present in the target inventory.
- **Hypothesis**: Stack merge consumption should be an identity cleanup boundary. The surviving target stack remains stored, while the fully consumed incoming object should have `stack_count == 0`, no registry entry, and no authoritative owner/storage/tile fields.
- **Resolution**: Fixed on 2026-06-27 by clearing consumed item location fields inside `Inventory.add_item()` and by making `Inventory.transfer_to()` stamp target ownership only when the incoming object remains present in the target inventory.
- **Verification**: EB-13-017 now proves transfer into an existing stack increases the target stack, unregisters the consumed incoming object, and leaves the consumed object's owner/storage fields clear.
- **Status**: RESOLVED

### High-level equip cancellation can orphan inventory items
- **Found**: 2026-06-08 during Chapter 13 engine-book parity expansion
- **Test file**: `examples/test_engine_book_items_inventory_equipment.py`
- **Error**: `Entity.equip_item()` removes an item from inventory before calling `Equipment.equip()`. If a `WEAPON_EQUIP` execution handler cancels the equip event, `Entity.equip_item()` still returns `True`, the equipment slot remains empty, and the item is no longer in the inventory even though `stored_in_uuid` still points at that inventory.
- **Hypothesis**: `Equipment.equip()` probably needs to return success/failure, and `Entity.equip_item()` should only remove from inventory after a successful equip or should roll back on canceled equipment events.
- **Resolution**: Fixed on 2026-06-27 by making `Equipment.equip()` return `False` when an equip event is canceled before slot assignment, and by having `Entity.equip_item()` remove the incoming item from inventory only after a successful equipment assignment.
- **Verification**: EB-13-013 now proves a canceled high-level weapon equip returns `False`, keeps the pre-existing equipped weapon in its slot, and leaves the incoming item in inventory with owner/storage fields intact.
- **Status**: RESOLVED

### Resolved two-handed weapon and shield policy gap
- **Found**: 2026-06-08 during Chapter 13 engine-book parity expansion
- **Test file**: `examples/test_engine_book_items_inventory_equipment.py`
- **Error**: A weapon with `WeaponProperty.TWO_HANDED` can be equipped in `MELEE_MAIN` while a shield is equipped in `MELEE_OFF`. The engine validates ranged/melee slot type and off-hand light-weapon rules, but does not enforce a hand-occupancy policy for two-handed weapons versus shields.
- **Hypothesis**: Equipment needs a hand-occupancy model that resolves two-handed melee conflicts consistently while preserving the engine's parallel melee/ranged videogame loadouts.
- **Resolution**: Fixed on 2026-06-29 in `Equipment.equip()` by replacing hard-block validation with order-based melee slot displacement.
- **Verification**: EB-13-014 now proves a shield/off-hand item displaces an active two-handed melee main weapon, a two-handed melee main weapon displaces an occupied melee off hand, and high-level equip rehomes displaced items to inventory.
- **Status**: RESOLVED

### Equipped item destruction can leave stale equipment slots and modifiers
- **Found**: 2026-06-27 during Chapter 13 engine-book parity expansion
- **Test file**: `examples/test_engine_book_items_inventory_equipment.py`
- **Error**: `BaseItem.destroy()` calls `container.remove_contained_item()` when an item has `stored_in_uuid`, but `Equipment` inherited the no-op `BaseBlock.remove_contained_item()`. Destroying an equipped shield cleared the shield object's own flags and registry entry, but left `entity.equipment.weapon_melee_off` pointing at the destroyed shield, so the shield AC bonus still contributed to `entity.ac_bonus()`.
- **Hypothesis**: Equipment needs to participate in the same container cleanup contract as Inventory. Because destruction is not a voluntary unequip action, the slot cleanup should run item unequip hooks but should not be cancelable by `*_UNEQUIP` event handlers.
- **Resolution**: Fixed on 2026-06-27 by adding `Equipment.remove_contained_item()`, which finds the slot containing the UUID, calls the item's unequip hook path directly, and clears the slot.
- **Verification**: EB-13-018 now proves destroyed equipped shields clear their slot and AC contribution, while destroyed chain mail clears its slot, Stealth disadvantage hook, heavy-armor movement hook, owner/storage fields, and registry entry.
- **Status**: RESOLVED

### Generic usable item actions can overspend charges
- **Found**: 2026-06-27 during Chapter 13 engine-book parity expansion
- **Test file**: `examples/test_engine_book_items_inventory_equipment.py`
- **Error**: The base `UsableItem.get_use_actions()` only hid actions when `charges == 0`. A generic use action with `charge_cost=2` on an item with one charge was still discoverable; `execute_use_action()` applied the action, then ignored `consume_charge(False)`, leaving the item unchanged after the effect.
- **Hypothesis**: Base usable-item discovery should follow the same charge-cost filtering already implemented by `SpellScroll`, and `execute_use_action()` should reject stale/direct calls before applying effects.
- **Resolution**: Fixed on 2026-06-27 by filtering base usable action templates when `charges < charge_cost` and by adding a pre-execution charge guard in `execute_use_action()`.
- **Verification**: EB-13-020 now proves an undercharged generic healing potion exposes no action, direct execution raises before healing, charges remain unchanged, and the item stays in inventory.
- **Status**: RESOLVED

### Raw inventory add can leave items with multiple authoritative locations
- **Found**: 2026-06-27 during Chapter 13 engine-book parity expansion
- **Test file**: `examples/test_engine_book_items_inventory_equipment.py`
- **Error**: Calling `Inventory.add_item()` directly on a floor item inserted it into the inventory but left `tile_uuid` and the grid object index intact. Calling it directly on an item that was already in another inventory could also leave the previous inventory still claiming the same UUID.
- **Hypothesis**: Even though `Inventory.add_item()` is lower level than `Entity.loot_item()`, successful insertion should be a container boundary: detach previous floor/container membership first, then stamp owner/storage for surviving stacks.
- **Resolution**: Fixed on 2026-06-27 by making `Inventory.add_item()` detach successful inserts from previous containers and grid placement, clear floor tile state, and stamp surviving stacks with the inventory owner/storage UUIDs.
- **Verification**: EB-13-021 now proves raw inventory add removes a floor item from the grid, stamps owner/storage, and rehomes an item from one inventory to another without leaving the previous inventory membership.
- **Status**: RESOLVED

### Fireball scroll legacy test has an invalid saved-damage lower bound
- **Found**: 2026-06-27 during Chapter 13 equipment cancellation regression checks
- **Test file**: `examples/test_inventory_use_actions.py`
- **Error**: `test_scroll_fireball_actual_damage` failed with `AssertionError: Min 8d6 = 8 damage (even with save), got 7`. A successful Dexterity save halves Fireball damage, so the saved lower bound for 8d6 can be lower than 8.
- **Hypothesis**: The legacy assertion should account for save-for-half or force failed saves if it intends to assert raw 8d6 damage bounds. The engine-book parity suite passed in the same verification window.
- **Resolution**: `test_scroll_fireball_actual_damage` now asserts each target takes 4-48 fire damage, the valid range after 8d6 Fireball damage and save-for-half. This keeps the test focused on AoE scroll execution while respecting the SRD save clause.
- **Status**: RESOLVED 2026-06-27

### Entity.is_spellcaster ignores registered spell templates
- **Found**: 2026-06-08 during Chapter 14 engine-book parity expansion
- **Test file**: `examples/test_engine_book_spellcasting_core.py`
- **Error**: An entity with no spell slots but a registered `Fire Bolt` cantrip has a visible available spell action, but `Entity.is_spellcaster` still returns `False`. The property currently checks spell-slot base values and does not inspect registered `SpellAction` templates.
- **Resolution**: `Entity.is_spellcaster` now returns true for entities with positive base spell slots or registered spell action templates. EB-06-008 and EB-14-013 cover the slot-or-template behavior, including cantrip-only spellcasters.
- **Status**: RESOLVED 2026-06-27

### HP-pool spells mutate target-selection state across validation and application
- **Found**: 2026-06-27 during Chapter 15 engine-book parity expansion
- **Test file**: `examples/test_engine_book_spell_families.py`
- **Error**: `Sleep.get_all_targets()` and `ColorSpray.get_all_targets()` spend `hp_pool_remaining` while selecting targets. `SpellAction.apply()` can ask for targets during validation and again during application, so a deterministic pool that exactly covers one target can be depleted before the spell effect is applied.
- **Hypothesis**: HP-pool spell target selection needs a cached selected-target list for the action instance so validation and convolution use the same UUIDs.
- **Status**: FIXED — `Sleep` and `ColorSpray` now cache selected HP-pool target UUIDs per spell instance; EB-15-013 and EB-15-014 cover repeated target selection and exact-pool application.

### Sleep HP-pool selection included unconscious creatures
- **Found**: 2026-06-27 during Chapter 15 HP-pool parity expansion
- **Test file**: `examples/test_engine_book_spell_families.py`
- **Error**: `Sleep.get_all_targets()` skipped undead and charmed-immune creatures, but did not skip creatures already under `Unconscious`, while the local SRD Sleep text says unconscious creatures are ignored when ordering HP-pool targets.
- **Hypothesis**: Sleep should mirror Color Spray's existing unconscious skip before sorting and spending the HP pool.
- **Status**: FIXED — `Sleep.get_all_targets()` now skips active `Unconscious` creatures, and EB-15-030 covers upcast dice plus unconscious, undead, and charmed-immunity skips.

### Color Spray cannot-see clause is only partially represented
- **Found**: 2026-06-27 during Chapter 15 HP-pool parity expansion
- **Test file**: `examples/test_engine_book_spell_families.py`
- **Error**: EB-15-030 covers Color Spray skips for unconscious, already-blinded, and `Blinded`-immune targets. The local SRD text also excludes creatures that cannot see, but the engine does not expose a single sight-capability predicate that covers all possible reasons a creature cannot see.
- **Hypothesis**: Color Spray needs a shared sensory capability query, likely on `Senses` or `Entity`, before it can distinguish ordinary visible creatures from every sightless or currently unable-to-see creature without hard-coding spell-local cases.
- **Resolution**: `Entity` now exposes `has_ordinary_sight` and `can_see_visual_effects()`, which returns false for Blinded, Unconscious, and explicitly sightless creatures while preserving ordinary sight by default. `ColorSpray.get_all_targets()` uses that shared predicate before spending HP-pool budget, and EB-15-030 proves a 1 HP sightless target in the cone is skipped.
- **Status**: RESOLVED 2026-06-27

### Eyebite repeat strike cost and Sickened save ability diverged from SRD
- **Found**: 2026-06-27 during Chapter 15 Eyebite parity expansion
- **Test file**: `examples/test_engine_book_spell_families.py`
- **Error**: `EyebiteStrike` declared an action cost but inherited `BaseAction._apply_costs()`, so repeat strikes did not spend the caster's action. `SickenedCondition` also used a Constitution repeat save at turn end, while the local SRD Eyebite text says Sickened repeats the Wisdom saving throw.
- **Hypothesis**: Eyebite's granted action should opt into the standard action-economy cost applier, and Sickened's repeat-save handler should use the same Wisdom save ability as the initial Eyebite strike.
- **Status**: FIXED — `EyebiteStrike._apply_costs()` now applies its action cost, `SickenedCondition` repeats a Wisdom save, and EB-15-031 covers initial Sickened application, repeat strike cost, repeat-save ability, and concentration cleanup.

### Eyebite Panicked movement surfaces diverged from SRD
- **Found**: 2026-06-27 during Chapter 15 Eyebite parity expansion
- **Test file**: `examples/test_engine_book_spell_families.py`
- **Error**: EB-15-031 through EB-15-033 covered the granted action lifecycle for Sickened, successful-save retarget blocking, visible-target validation, and the action surface for waking `Eyebite Asleep`. `EyebitePanickedEffect` still applied `Frightened` plus a repeat Wisdom save rather than enforcing Dash movement away from the caster and ending when the target is at least 60 feet away and unable to see the caster.
- **Hypothesis**: Eyebite needed a movement/visibility end-condition model for Panicked before that SRD clause could be represented cleanly.
- **Status**: FIXED — EB-15-034 removes the Panicked repeat save, spends Dash on the panicked target's turn, moves it away along a selected safe route, and ends the effect only once it is at least 60 feet away and cannot see the caster.

### Condition-owned handler cleanup can leave stale block-local indexes
- **Found**: 2026-06-27 during Chapter 15 Shield parity expansion
- **Test file**: `examples/test_engine_book_spell_families.py`
- **Error**: Removing `Shield` at turn start removed its condition-owned handlers from `EventQueue`, but `shielded.get_event_handler_by_name("Shield: Magic Missile Block")` still found a stale local handler. `EventHandler.remove()` looked up the owner through `BaseObject.get(source_entity_uuid)`, while entities are registered as `BaseBlock` instances rather than `BaseObject` instances in this path.
- **Hypothesis**: Blocks that register handlers should stamp themselves as handler owners so handler cleanup can remove block-local indexes without importing upward from the event layer.
- **Status**: FIXED — `BaseBlock.add_event_handler()` now stores the registering block on the handler, and `EventHandler.remove()` uses that owner to clear block-local indexes; EB-15-020 covers Shield turn-start handler cleanup.

### Web lacks its SRD turn-start restraint save
- **Found**: 2026-06-27 during Chapter 15 zone-spell parity expansion
- **Test file**: `examples/test_engine_book_spell_families.py`
- **Error**: `WebZone` restrained creatures on entry and on initial cast, but did not register a turn-start handler. The SRD `Web` text requires a Dexterity save when a creature starts its turn in the webs.
- **Hypothesis**: `WebZone` should mirror the existing entry-save processor with a normal `TURN_START` handler that checks whether the acting entity's position is in `affected_positions`.
- **Status**: FIXED — `WebZone` now registers `Web Turn Start Save`, and EB-15-021 covers failed turn-start saves applying `Web Restrained` and its `Restrained` subcondition.

### Web zone omitted SRD light obscurement
- **Found**: 2026-06-27 during Chapter 15 Web parity expansion
- **Test file**: `examples/test_engine_book_spell_families.py`
- **Error**: `WebZone` applied difficult terrain and restraint handlers but did not apply any tile obscurement, while the local SRD Web text says the area is lightly obscured.
- **Hypothesis**: Web should use `ZoneControlCondition`'s existing light modifier path with `sets_light_level=LightLevel.DIM_LIGHT` and `light_is_obscurement=True`.
- **Status**: FIXED — `WebZone` now applies dim-light obscurement through tile modifiers, and EB-15-029 covers obscurement application and cleanup.

### Web fire exposure lacks engine surface
- **Found**: 2026-06-27 during Chapter 15 Web parity expansion
- **Test file**: `examples/test_engine_book_spell_families.py`
- **Error**: EB-15-029 proves default 2D grid Web casts persist as floor-layered zones, and EB-15-037 now proves explicit unanchored/unlayered Web casts collapse at the caster's next turn start. The engine still did not expose environmental fire exposure for one-round burning Web cubes.
- **Hypothesis**: Web fire needs a shared environmental primitive: a way for position-targeted fire effects or flame objects to expose a tile to fire and burn away a specific 5-foot cube for one round.
- **Progress**: `Web.anchored_or_layered=False` now creates an unanchored Web zone that registers a collapse handler, removes the zone at the caster's next turn start, cleans terrain/light modifiers, and removes concentration through the linked-condition path.
- **Status**: FIXED — `FireExposureEvent` now exposes a grid position to environmental fire, `WebZone` burns away the affected cube, removes that cube's terrain/light/marker state, clears same-source `Web Restrained`, deals one-round 2d4 fire to creatures starting their turn in the burning cube, and preserves the rest of the concentration zone. EB-15-042 covers the full lifecycle.

### Spirit Guardians exit handling removes slow during internal zone movement
- **Found**: 2026-06-27 during Chapter 15 zone-spell parity expansion
- **Test file**: `examples/test_engine_book_spell_families.py`
- **Error**: Moving from one `Spirit Guardians` zone tile to another fired `SPATIAL_ENTITY_LEFT` for the old cell and removed `Spirit Guardians Slowed`, even though the entity remained inside the zone. The manually added exit spatial handler was also tracked as a normal handler, so concentration cleanup left stale spatial position indexes.
- **Hypothesis**: The exit processor should inspect the movement destination carried on the left event and only remove slow when the destination is outside `affected_positions`. The manual exit handler should be returned as a spatial handler UUID so `ZoneControlCondition` cleanup removes its position indexes.
- **Status**: FIXED — `SpiritGuardiansZone` now preserves slow during internal zone movement, removes it only on actual exit, and tracks the exit handler as a spatial handler; EB-15-021 covers internal movement, exit cleanup, and concentration cleanup of spatial indexes.

### Attack Object action cost diverged from discovery
- **Found**: 2026-05-29 during Chapter 09 engine-book parity expansion
- **Test file**: `examples/test_engine_book_action_templates_discovery.py`
- **Error**: `Attack Object` discovery reports `cost_type == "actions"` and `cost_amount == 1`, but executing the action leaves `entity.action_economy.actions.normalized_score == 1`.
- **Hypothesis**: `AttackObject` inherits `BaseAction._apply_costs()`, which only phases the event to completion and does not consume action economy. The subclass likely needs an `_apply_costs()` implementation similar to other concrete action classes, or `BaseAction._apply_costs()` should become the generic action-cost applier.
- **Status**: FIXED — `AttackObject._apply_costs()` now uses the standard action-economy cost applier, and EB-09-012 proves that destroying a breakable object spends the advertised action.

### Natural 20 attacks are not automatic hits against unreachable AC
- **Found**: 2026-05-29 during Chapter 10 engine-book parity expansion
- **Test file**: `examples/test_engine_book_core_actions_combat.py`
- **Error**: A natural 20 attack roll against an AC raised beyond the final roll total resolves as `AttackOutcome.MISS`, even though the SRD attack-roll rule makes natural 20 an automatic critical hit.
- **Hypothesis**: `determine_attack_outcome()` checks natural 20 only inside the `roll.total >= target_ac` branch. It likely needs a natural-roll branch before the AC comparison, after explicit `AUTOMISS` handling.
- **Resolution**: Fixed on 2026-06-27 in `dnd/entity.py` by resolving `RollType.ATTACK` natural 20 as `AttackOutcome.CRIT` before the AC comparison, while preserving explicit `AUTOMISS` and `AUTOHIT` precedence.
- **Verification**: EB-03-007 now proves the primitive outcome rule directly, and EB-10-010 now proves an integrated `Attack` with natural 20 damages a target whose AC is unreachable by total alone.
- **Status**: RESOLVED

### Removed duplicate SRD Shove action surface
- **Found**: 2026-06-28 during Chapter 10 SRD-vs-engine tracking
- **Test file**: `examples/test_engine_book_core_actions_combat.py`
- **Error**: The engine briefly carried both the videogame `Shove` action and an explicit `SrdShove` action, which made the runtime surface look like it supported selectable rulesets.
- **Resolution**: Fixed on 2026-06-29 by removing the `SrdShove`/`SrdShoveEvent` runtime surface and deleting its engine-book parity row. `Shove` remains the single supported videogame action: bonus action, passive target resistance, Strength-scaled forced movement, and no default SRD prone/push choice.
- **Verification**: EB-10-022 now proves the single shove contract through `test_eb_10_022_shove_uses_videogame_bonus_action_forced_movement`; SRD text remains reference material only.
- **Status**: FIXED

### Player-style death saving throw subsystem is not implemented
- **Found**: 2026-06-28 during Chapter 10 SRD-vs-engine tracking
- **Test file**: `examples/test_engine_book_core_actions_combat.py`
- **Error**: The local SRD death text distinguishes instant death, falling unconscious at 0 HP, death-save successes/failures, natural 1/20 death-save effects, damage-at-0 failures, stabilization, and monster death defaults. The engine applies `DeathEvent` and `Dead` to any entity at 0 HP or below, with no player/monster distinction, death-save counters, stable state, start-turn death-save roll, or API-visible dying state.
- **Hypothesis**: Current HP flow models monster-style death for all entities. A future player-death subsystem would need new state, events, turn integration, healing/stabilization cleanup, damage-at-0 handling, and API fields.
- **Resolution**: `Entity` now has opt-in player-style death-save state through `uses_death_saves`, death-save counters, and `is_stable`. Default entities still use monster-style immediate `Dead` at 0 HP. Opted-in entities fall `Unconscious` at 0 HP unless massive damage kills them, roll `DeathSaveEvent` at turn start, stabilize after three successes, die after three failures, treat natural 1 as two failures, regain 1 HP on natural 20, add failures for damage at 0 HP, and clear death-save state on true healing.
- **Verification**: EB-10-023 pins default monster-style death. EB-10-025 proves turn-start player-style death saves and natural-1 death. EB-10-026 proves natural-20 healing, three-success stabilization, stable save skipping, critical damage-at-0 failures, healing reset, and massive-damage death.
- **Remaining scope**: Concrete Medicine-check and healer's-kit stabilization actions are still future action surfaces; the lower-level `Entity.stabilize()` primitive now exists.
- **Status**: RESOLVED 2026-06-28

### Mixed weapon damage applies resistance, vulnerability, and immunity using only the primary damage type
- **Found**: 2026-05-29 during Chapter 10 engine-book parity expansion
- **Test file**: `examples/test_engine_book_core_actions_combat.py`
- **Error**: A weapon attack with 6 slashing plus 6 fire damage applies damage-type multipliers to the summed 12 damage using only the primary slashing type. Against slashing resistance it deals 6 total damage; against slashing vulnerability it deals 24 total damage; against slashing immunity it deals 0 total damage, canceling the fire component too.
- **Hypothesis**: `Attack.attack_consequences()` should apply resistance/vulnerability/immunity per `Damage` component, or `TakeDamageEvent`/`Entity.receive_damage()` should support typed damage components instead of one aggregate `damage_type`.
- **Resolution**: Fixed on 2026-06-27 by adding `Health.take_damage_components()` and routing unmodified multi-component `Entity.receive_damage()` calls through it. Each component applies its own resistance/vulnerability/immunity multiplier, then flat damage reduction and temporary HP are applied once to the combined post-multiplier damage.
- **Verification**: EB-10-016 now proves 6 slashing plus 6 fire against slashing resistance deals 9 total damage; EB-10-019 now proves slashing vulnerability deals 18 and slashing immunity still allows the 6 fire damage through.
- **Status**: RESOLVED

### Lethal opportunity attack movement advances into the next cell before stopping
- **Found**: 2026-05-29 during Chapter 10 engine-book parity expansion
- **Test file**: `examples/test_engine_book_core_actions_combat.py`
- **Error**: A mover killed by an opportunity attack while leaving reach ends at the provoking step destination `(5, 7)` and `Move` completes as partial movement. `Jump` does the same state update, then raises `ValueError: Not enough bonus_actions...` because `Dead`/`Incapacitated` zeroes action economy before `Jump._apply_costs()` spends the bonus action. Under the usual SRD timing model, the opportunity attack interrupts just before the creature leaves reach, so a lethal OA should likely leave the creature in the origin cell `(5, 6)`.
- **Hypothesis**: `Move._apply()` and `Jump._apply()` fire `STEP_MOVEMENT`, let handlers apply OA, then update the entity position before checking for `Dead`. The death check may need to happen immediately after the processed step event and before `Entity.update_entity_position()`. `Jump` may also need to settle action costs before movement side effects or tolerate post-death cost application.
- **Resolution**: Fixed on 2026-06-27 in `Move._apply()` and `Jump._apply()` by checking for `Dead`/`Incapacitated` immediately after step-event handlers run and before `Entity.update_entity_position()`. Lethal opportunity attacks now leave the creature in the origin cell, and the interrupted step does not reach `COMPLETION`. `Jump._apply_costs()` now returns the existing completion event without consuming costs if the jumper is already dead or incapacitated.
- **Verification**: EB-10-017 now proves lethal Move opportunity attacks stop before leaving reach; EB-10-018 now proves lethal Jump opportunity attacks complete as partial jumps without raising the post-death bonus-action cost error.
- **Status**: RESOLVED

### Forced movement skips intermediate terrain and completes before final landing damage
- **Found**: 2026-05-29 during Chapter 10 engine-book parity expansion
- **Test file**: `examples/test_engine_book_core_actions_combat.py`
- **Error**: Shove-style forced movement updates the target directly from the start cell to the final cell. It emits no `STEP_MOVEMENT` events and no intermediate `SPATIAL_ENTITY_ENTERED` events, so hazardous terrain between start and landing is skipped. If the final landing cell deals terrain damage, the `TakeDamageEvent.parent_event` points at the `ForcedMovementEvent`, but the forced movement event has already completed and its combat log has no damage sub-entry.
- **Hypothesis**: `Shove._apply()` calls `ForcedMovementEvent.phase_to(COMPLETION)` before `Entity.update_entity_position()`. Forced movement may need a step/transition loop for terrain-sensitive effects, or at least a final-position update before completing the forced movement event so child damage can be collected in the combat log.
- **Resolution**: Fixed on 2026-06-27 in `Shove._apply()` by advancing forced movement through `EXECUTION` and `EFFECT`, updating the target one 5-foot transition at a time under the forced-movement event, and completing the forced-movement event only after terrain/spatial effects resolve.
- **Verification**: EB-10-021 now proves forced movement emits no `STEP_MOVEMENT`, preserves target movement economy, emits intermediate `SPATIAL_ENTITY_ENTERED` effects, applies both traversed spike cells, and nests the damage logs under the forced movement lineage.
- **Status**: RESOLVED

### Diagonal pathfinding cost and exact max-distance pruning disagree
- **Found**: 2026-05-29 during Chapter 11 engine-book parity expansion
- **Test file**: `examples/test_engine_book_grid_tiles_pathfinding.py`
- **Error**: `GridMap.compute_paths((0, 0))` returns a one-cell diagonal `(1, 1)` at cost `1`, but `GridMap.compute_paths((0, 0), max_distance=1)` excludes `(1, 1)` while including cardinal cost-1 neighbors. The hidden diagonal tie-break epsilon is included in pruning even though it is stripped from returned distances.
- **Hypothesis**: `dnd/core/dijkstra.py` should probably compare `max_distance` against the public true movement cost, or allow a tiny tolerance for epsilon-only overflow, while still using epsilon for queue tie-breaking.
- **Resolution**: Fixed on 2026-06-27 in `dnd/core/dijkstra.py` by comparing `max_distance` to the true movement distance before diagonal tie-break epsilon is applied to the priority distance.
- **Verification**: EB-11-012 now proves a one-cell diagonal with returned cost `1` is included by `GridMap.compute_paths(..., max_distance=1)` with the expected path.
- **Status**: RESOLVED

### Negative-coordinate tiles are not fully reachable by pathfinding
- **Found**: 2026-05-29 during Chapter 11 engine-book parity expansion
- **Test file**: `examples/test_engine_book_grid_tiles_pathfinding.py`
- **Error**: `GridMap` can store tiles at negative coordinates and `GridMap.can_transition((-2, 0), (-1, 0))` returns `True`, but `GridMap.compute_paths((-2, 0))` returns only the start tile. Starting from `(-1, 0)` can reach `(0, 0)`, but cannot reach deeper negative tile `(-2, 0)`.
- **Hypothesis**: `GridMap.compute_paths()` passes only width and height to `dijkstra()`, and `dnd/core/dijkstra.py::get_neighbors()` clamps raw coordinates to `0 <= nx < width` and `0 <= ny < height`. The pathfinder likely needs origin offsets or bounds-aware min/max coordinates rather than nonnegative width/height alone.
- **Resolution**: `dijkstra()` and `get_neighbors()` now accept `min_x` and `min_y` search origins, and `GridMap.compute_paths()` passes the map's actual bounds. EB-11-013 proves paths can move through negative-coordinate tiles in both directions.
- **Status**: RESOLVED 2026-06-27

### Raw GridMap object removal leaves BaseItem floor-location fields stale
- **Found**: 2026-05-29 during Chapter 11 engine-book parity expansion
- **Test file**: `examples/test_engine_book_grid_tiles_pathfinding.py`
- **Error**: `BaseItem.place_on_grid()` sets `item.tile_uuid` and `item.position`, but calling `GridMap.remove_object(item.uuid)` only removes the object UUID from grid indexes and observer senses. The item still has its previous `tile_uuid`, and `item.get_position()` still returns the removed floor position.
- **Hypothesis**: `GridMap.remove_object()` is intentionally type-unaware, but callers can easily mistake it for full item removal. Either higher-level item APIs should be the only public removal path for `BaseItem` objects, or `GridMap.remove_object()` should optionally notify/remove item location state through a polymorphic hook.
- **Resolution**: `GridMap.remove_object()` now calls `BaseBlock.on_grid_object_removed()`, and `BaseItem` clears `tile_uuid` when the removal is an authoritative location clear. Internal object re-placement opts out of location clearing, and EB-11-016 proves raw removal clears floor location without destroying the item.
- **Status**: RESOLVED 2026-06-27

### Generic ZoneControlCondition cone and line construction collapses to the origin
- **Found**: 2026-05-29 during Chapter 11 engine-book parity expansion
- **Test file**: `examples/test_engine_book_grid_tiles_pathfinding.py`
- **Error**: Direct `Cone` and `Line` AoE shapes expand correctly when given a caster origin plus a distinct target direction, but generic `ZoneControlCondition(zone_shape="cone"|"line", zone_direction=...)` computes only `{zone_center}`. The default zone builder passes `zone_center` as both the AoE target and the caster position, and passes `radius_feet`/`direction` fields that `Cone` and `Line` do not consume.
- **Hypothesis**: `ZoneControlCondition._compute_affected_positions()` likely needs shape-specific construction: convert `zone_direction` into a target endpoint and pass `length_feet`/`width_feet` for line-like zones, or make directional zone subclasses always override the method as `GustOfWindZone` does today.
- **Resolution**: `ZoneControlCondition._compute_affected_positions()` now converts `zone_direction` into a target endpoint for generic cone and line zones, passes `zone_radius_feet` as length, and exposes `zone_width_feet` for line width. EB-11-018 proves generic cone/line zones match direct AoE construction.
- **Status**: RESOLVED 2026-06-27

### Cylinder action previews can use wall-filtered subjective geometry
- **Found**: 2026-05-29 during Chapter 11 engine-book parity expansion
- **Test file**: `examples/test_engine_book_grid_tiles_pathfinding.py`
- **Error**: `Cylinder.compute_for_targeting()` and `Cylinder.compute_objective()` include the full geometric footprint through lateral walls, but inherited `Cylinder.compute_subjective()` applies propagation FOV and omits cells behind walls. `Entity._compute_aoe_at_position()` calls `shape.compute_subjective()` for all AoE action previews, so a cylinder spell preview can show a wall-filtered footprint even though execution affects the full cylinder area.
- **Hypothesis**: AoE preview should dispatch to `compute_for_targeting()` when a shape implements it, or `Cylinder` should override `compute_subjective()` with the same footprint semantics while preserving perception-filtered entity UUIDs.
- **Resolution**: `Cylinder.compute_subjective()` now delegates to the full-footprint targeting computation while preserving perception-filtered entity UUIDs. EB-11-019 proves subjective preview, targeting, and objective execution share the same footprint through lateral walls.
- **Status**: RESOLVED 2026-06-27

### Magical darkness zone removal does not recompute FOV for cells behind it
- **Found**: 2026-05-29 during Chapter 12 engine-book parity expansion
- **Test file**: `examples/test_engine_book_senses_light_stealth.py`
- **Error**: Applying a single-cell magical darkness zone uses the batched light path and emits `requires_fov=True`, so observers drop the magical darkness cell and cells behind it. Removing that same zone changes the tile back to bright light, but the removal batch computes `requires_fov=False` because no changed tile currently resolves to `MAGICAL_DARKNESS`. Observers refresh the former darkness cell but do not resubscribe to or restore visibility for cells behind it.
- **Hypothesis**: Light batch events likely need to know whether any changed position previously blocked vision, not only whether it blocks vision after the mutation. Zone light cleanup may need to pass old light/blocking state into `_fire_light_batch_events()`, or light modifier removal should explicitly request FOV recomputation when removing magical darkness.
- **Resolution**: Zone light apply/removal now detects old or new `MAGICAL_DARKNESS` at changed positions and passes `requires_fov=True` into the batch light event. EB-12-011 proves removing a magical-darkness zone restores cells and entities behind it.
- **Status**: RESOLVED 2026-06-27

### Daylight cannot dispel Darkness through the current visibility gate
- **Found**: 2026-06-27 during Chapter 15 zone-spell edge probing
- **Test file**: `examples/test_engine_book_spell_families.py`
- **Error**: After `Darkness` applies magical darkness to a target point, `Daylight` targeting the same point cancels during validation with `Position (...) not visible`. The `Darkness Zone` condition remains active and the tile remains `LightLevel.MAGICAL_DARKNESS`. This makes the SRD Daylight clause that dispels darkness from a spell of 3rd level or lower unreachable through that direct targeting path.
- **Hypothesis**: Light/obscurement spell validation may need a targeting exception for positions inside spell-created darkness, or `Daylight` needs an overlap/dispel path that can target the edge or an adjacent visible point and remove lower-level darkness zones in the affected area. The current implementation layers illumination/obscurement modifiers and does not remove the source darkness condition.
- **Status**: FIXED — `Daylight` now allows direct targeting of magical-darkness tiles and removes overlapping `Darkness Zone` conditions after computing the Daylight zone. EB-15-026 covers Fog Cloud obscurement cleanup, Darkness blocking darkvision, and Daylight dispelling the active Darkness zone.

### Insect Plague zone omitted SRD difficult terrain and light obscurement
- **Found**: 2026-06-27 during Chapter 15 damage-zone parity expansion
- **Test file**: `examples/test_engine_book_spell_families.py`
- **Error**: Before EB-15-027, `InsectPlagueZone` dealt piercing damage and created markers/handlers, but `adds_difficult_terrain` was `False` and no light/obscurement modifier was applied, while the SRD spell area is difficult terrain and lightly obscured.
- **Hypothesis**: The zone should use `ZoneControlCondition`'s existing terrain and light modifier channels: `adds_difficult_terrain=True`, `sets_light_level=LightLevel.DIM_LIGHT`, `light_is_obscurement=True`.
- **Status**: FIXED — `InsectPlagueZone` now applies difficult terrain and dim-light obscurement, and EB-15-027 covers damage, terrain/light cleanup, and upcast dice.

### Stinking Cloud over-locked action economy and ignored poison immunity
- **Found**: 2026-06-27 during Chapter 15 gas-zone parity expansion
- **Test file**: `examples/test_engine_book_spell_families.py`
- **Error**: Before EB-15-028, a failed Stinking Cloud save applied `NauseatedCondition` by capping actions, bonus actions, and reactions at zero. The local SRD text spends the creature's action, not every turn resource. The zone also forced a saving throw for poison-immune creatures.
- **Hypothesis**: `NauseatedCondition` should cap only `action_economy.actions`, and `StinkingCloudZone` should short-circuit when the entity has poison damage immunity.
- **Status**: FIXED — Stinking Cloud now leaves bonus actions, reactions, and movement available, skips poison-immune creatures, and EB-15-028 covers both behaviors.

### Sleet Storm used sphere propagation and DC 10 concentration disruption
- **Found**: 2026-06-27 during Chapter 15 ice-zone parity expansion
- **Test file**: `examples/test_engine_book_spell_families.py`
- **Error**: Before EB-15-028, `SleetStormZone` used `zone_shape="sphere"`, so wall propagation could shadow cells that should be in the falling cylinder area. Its concentration disruption save was also hard-coded to DC 10 instead of using the caster's spell save DC.
- **Hypothesis**: Generic `ZoneControlCondition` should support the existing `Cylinder` AoE shape, `SleetStormZone` should select it, and the turn-start concentration check should use `self.spell_dc`.
- **Status**: FIXED — `ZoneControlCondition` now supports `zone_shape="cylinder"`, Sleet Storm uses it, concentration disruption uses the caster's spell save DC, and EB-15-028 covers wall-shadow, prone, terrain/obscurement, cleanup, and concentration-break behavior.

### Stinking Cloud and Sleet Storm environmental clauses lack engine surfaces
- **Found**: 2026-06-27 during Chapter 15 gas/ice-zone parity expansion
- **Test file**: `examples/test_engine_book_spell_families.py`
- **Error**: EB-15-028 covered poison immunity through the health resistance API, but the engine originally did not expose a general breathing requirement trait for Stinking Cloud's breathless-creature automatic success. The same slice did not find a wind model for Stinking Cloud dispersal or a flame object/state model for Sleet Storm flame dousing.
- **Hypothesis**: The remaining wind clause needed an explicit wind primitive with duration semantics before Stinking Cloud could disperse after 4 rounds in moderate wind or 1 round in strong wind without spell-local ad hoc flags.
- **Progress**: `Entity` now exposes `requires_breathing`, `EntityConfig` propagates it, and `StinkingCloudZone` skips turn-start saving throws and nausea for breathless creatures. `BaseItem` now exposes an exposed-flame dousing contract, `Torch` and `WallTorch` implement it, lit items emit `ExposedFlameEvent`, and `SleetStormZone` douses carried and placed exposed flames in its area. `WindExposureEvent` now carries wind speed and exposed positions, `GustOfWindZone` emits strong wind exposure from its line, and `StinkingCloudZone` consumes wind exposure to disperse after the SRD round thresholds.
- **Verification**: EB-15-041 proves a breathless creature inside Stinking Cloud receives no saving throw, no `Nauseated` condition, and no action loss. EB-15-043 proves Sleet Storm douses lit carried torches and placed wall torches on initial cast, immediately douses newly ignited flames inside an active storm, and preserves outside flames. EB-15-044 proves Stinking Cloud disperses after four cloud-caster turn starts in 10 mph wind and after one in 20 mph Gust of Wind exposure.
- **Status**: FIXED

### Passive perception sensory updates omit the paths-dirty payload flag
- **Found**: 2026-05-29 during Chapter 12 engine-book parity expansion
- **Test file**: `examples/test_engine_book_senses_light_stealth.py`
- **Error**: When a condition changes an observer's passive perception, `SpatialSensesCallback._handle_own_perception_change()` refilters visible entities and sets `observer.senses._paths_dirty = True`. The emitted `SENSORY_UPDATE` includes `passive_perception_changed=True`, the replacement `passive_perception`, and visible entity deltas, but `paths_dirty` remains `False`.
- **Hypothesis**: `_emit_update()` appears to compare before/after snapshots for `_paths_dirty` before or without capturing the mutation made during passive-perception refiltering. The payload should probably report `paths_dirty=True` whenever the callback marks the observer's path cache dirty.
- **Resolution**: `SpatialSensesCallback._emit_sensory_update()` now treats condition-driven passive-perception or sense-mode changes as path-refresh payloads whenever the observer's path cache is dirty after the update, even if the cache was already dirty before that event. EB-12-012 now asserts `paths_dirty=True` in the passive-perception replacement payload.
- **Status**: RESOLVED 2026-06-27

### Directional collision memory is not cleared at turn start
- **Found**: 2026-05-29 during Chapter 12 engine-book parity expansion
- **Test file**: `examples/test_engine_book_senses_light_stealth.py`
- **Error**: Hidden edge-like blockers record `Senses.directional_collision_blocked` entries such as `((0, 0), "east")`, while hidden cell blockers record `Senses.collision_blocked` positions. `Encounter.start_turn()` clears only `entity.senses.collision_blocked`, then refreshes senses. Directional collision memory persists into the new turn and continues blocking the remembered transition.
- **Hypothesis**: `Encounter.start_turn()` should probably clear both positional and directional collision memory before refreshing senses, or the persistence should be explicitly intentional and surfaced in the API. Current behavior is documented as EB-12-013.
- **Resolution**: `Encounter.start_turn()` now clears both `collision_blocked` and `directional_collision_blocked` before refreshing senses. EB-12-013 proves a remembered hidden directional blocker affects immediate replanning, then resets at the next turn start and allows the fresh direct subjective path again.
- **Status**: RESOLVED 2026-06-27

### Lucky feat example silently skips attack-roll coverage
- **Found**: 2026-05-28 during Chapter 16 engine-book parity validation
- **Test file**: `examples/test_lucky_feat.py`
- **Error**: `uv run python examples/test_lucky_feat.py` exits with status 0, but the attack-roll section prints `ERROR: No attack actions available` and returns without asserting attack-roll Lucky behavior.
- **Hypothesis**: The test creates skeleton attackers and calls `setup_standard_actions()`, but no usable attack action is surfaced in `get_available_actions()` for that scenario. The script should either equip/register an attack deterministically or fail when the attack-roll scenario is not exercised.
- **Resolution**: `setup_test_environment()` now creates a real grid, and `test_lucky_on_attack_roll()` equips the attacker with a longsword before standard action setup. The attack section asserts an attack action exists, forces a low attack d20 plus Lucky reroll, and requires one luck point plus at least one modified `ATTACK_D20_ROLL_RESULT`.
- **Status**: RESOLVED 2026-06-27

### Restoration spell implementations are narrower than SRD text
- **Found**: 2026-06-27 during Chapter 15 restoration parity expansion
- **Test file**: `examples/test_engine_book_spell_families.py`
- **Error**: EB-15-023 originally documented narrower behavior: `LesserRestoration` removed only a fixed condition list, and `GreaterRestoration` did not cover all SRD restoration categories.
- **Resolution**: `LesserRestoration` now handles disease-tagged conditions. `GreaterRestoration` now handles one curse-tagged condition, one petrification-tagged condition, one ability-score-reduction-tagged condition, one hit-point-maximum-reduction-tagged condition, and one `Exhaustion` level. `RemoveCurse` removes every active `ConditionTag.CURSE` condition instead of the first one.
- **Verification**: EB-15-023 proves disease-tagged Lesser Restoration removal, supported major-condition Greater Restoration removal with sub-condition cleanup, one curse-tagged Greater Restoration removal, and all-curse Remove Curse removal while unrelated `Poisoned` remains. EB-15-038 proves Greater Restoration removes the newer SRD-tagged effect surfaces and that ability-score and hit-point-maximum modifiers are cleaned up. EB-08-014 adds a standard `Petrified` condition model for the expressible SRD effects, EB-15-039 proves Greater Restoration removes it, EB-08-015 adds levelled `Exhaustion`, and EB-15-040 proves Greater Restoration reduces it one level at a time.
- **Status**: RESOLVED 2026-06-28

### Exhaustion recovery lifecycle is not wired to rests or revival
- **Found**: 2026-06-28 during Chapter 08 exhaustion implementation
- **Test file**: `examples/test_engine_book_standard_conditions.py`
- **Error**: EB-08-015 implements and documents the six cumulative Exhaustion levels, and EB-15-040 proves Greater Restoration reduces Exhaustion by one level. The SRD condition text also says finishing a qualifying long rest reduces exhaustion by 1, and being raised from the dead reduces exhaustion by 1. The current engine has resource-level `ActionEconomy.on_long_rest()` and condition duration `long_rest()` markers, but no general entity rest/revival lifecycle that reduces `Exhaustion.level`.
- **Hypothesis**: A future rest/revival lifecycle should either call a condition-level reduction helper or replace the active `Exhaustion` condition with `level - 1`, preserving condition cleanup semantics.
- **Resolution**: `BaseCondition` now exposes a polymorphic level-reduction hook, `Exhaustion` returns a lower-level replacement, `Entity.on_long_rest()` reduces living entities' Exhaustion by one level after resource/slot/long-rest-duration recovery, `Entity.revive()` removes `Dead` through normal cleanup and reduces Exhaustion by one level, and `GreaterRestoration` delegates to the shared entity reduction path.
- **Verification**: EB-06-015 proves long-rest Exhaustion reduction, `UNTIL_LONG_REST` condition expiry, spell-slot restoration, directional resource recharge, and revival cleanup plus Exhaustion reduction. EB-06-016 proves long-rest normal HP restoration, temporary HP expiry, and the dead/0-HP no-benefit guard. EB-06-017 proves Hit Dice spending/recovery, CON-modifier healing, HP-cap behavior, and long-rest half-total recovery. EB-15-040 still proves Greater Restoration reduces Exhaustion one level at a time.
- **Remaining scope**: Food/drink qualification, 24-hour long-rest cadence, and concrete resurrection spells remain separate unimplemented lifecycle/spell surfaces.
- **Status**: RESOLVED 2026-06-28

### Protective abjuration spells model narrower hooks than SRD text
- **Found**: 2026-06-27 during Chapter 15 protective-abjuration parity expansion
- **Test file**: `examples/test_engine_book_spell_families.py`
- **Error**: EB-15-025 originally documented narrower behavior: `ProtectionFromPoison` neutralized an active `Poisoned` condition and granted poison-save advantage, poison resistance, and future `Poisoned` immunity; `DeathWard` rewrote lethal damage to leave the target at 1 HP and negated one no-damage instant-death event; `FreedomOfMovement` bypassed difficult terrain, blocked magical speed reduction, blocked `Grappled`/`Restrained`, blocked magically tagged `Paralyzed`, and let a protected creature spend 5 feet of movement to escape active nonmagical `Grappled` or `Restrained`, but did not model the SRD underwater movement and attack clauses.
- **Hypothesis**: The gap needed explicit underwater attack context plus an action-level swimming movement lifecycle that chooses `MovementMode.SWIMMING`, accounts for creatures without swim speed, and gives Freedom of Movement a concrete traversal path to suppress those movement penalties.
- **Resolution**: `ProtectionFromPoison` now removes an already-active `Poisoned` condition before adding its persistent protection and adds contextual advantage to saving throw requests whose `condition_context` is `"Poisoned"`. `DeathWard` now handles `InstantDeathEvent`; `PowerWordKill` uses that no-damage primitive, so Death Ward can negate it once without changing HP. `FreedomOfMovement` now uses condition-aware contextual immunity to block only incoming `Paralyzed` conditions tagged `ConditionTag.MAGICAL`, its `ignore_magical_speed_reduction` flag prevents magical movement-speed penalties from `Slowed`, `Spirit Guardians Slowed`, and `Ray of Frost Effect`, its `ignore_underwater_penalties` flag suppresses `Underwater` attack penalties and no-swim-speed movement surcharges, and `Freedom of Movement Escape` spends 5 feet of movement to remove active nonmagical `Grappled` or `Restrained` while unregistering on cleanup. `Underwater` now models the SRD underwater attack penalties, and `Swim` uses `MovementMode.SWIMMING` for water traversal and registered-action discovery.
- **Verification**: EB-15-025 proves active poison neutralization, poison-save advantage, poison resistance, future `Poisoned` immunity, lethal-damage survival, no-damage instant-death negation, magical speed-reduction prevention, magical paralysis immunity, nonmagical restraint escape, underwater ranged/melee attack-penalty suppression, Swim discovery in water, Freedom-protected swim cost, unprotected no-swim-speed doubled swim cost, and cleanup.
- **Status**: RESOLVED 2026-06-28

### Equipment API test sends stale equip/unequip payloads
- **Found**: 2026-05-08 during edge-aware spatial foundation validation
- **Test file**: `examples/server_tests/test_equipment_api.py`
- **Error**: Running against a temporary `uvicorn server.event_server:app --port 8000` reaches the equipment endpoints, but `POST /entity/{uuid}/equip` and `POST /entity/{uuid}/unequip` return HTTP 422 because the request body omits required `entity_uuid`. The later expected 400/404 error-case checks then fail as follow-on failures.
- **Hypothesis**: The server request models were updated to require `entity_uuid`, but this manual integration test still sends the older payload shape with only `session_id`, `item_uuid`/`slot`. The test likely needs to include `entity_uuid` in equip/unequip payloads or the endpoint model needs compatibility handling.
- **Resolution**: Current `examples/server_tests/test_equipment_api.py` sends `entity_uuid` in equip, unequip, and error-case request bodies. Verified with `uv run python examples/server_tests/test_equipment_api.py`, which starts a managed uvicorn server on port 8768 and passes 42/42 checks.
- **Status**: RESOLVED 2026-06-27

### WebSocket ping test assumes pong is the next frame
- **Found**: 2026-05-03 during spell catalog endpoint validation
- **Test file**: `server/test_websocket.py`
- **Error**: Running `PYTHONPATH=. .venv/bin/python server/test_websocket.py` reaches `test_websocket_connection`, sends `{"type": "ping"}`, then `assert data["type"] == "pong"` fails because the next received frame can still be an `"event"` frame.
- **Hypothesis**: The WebSocket stream is asynchronous and may have queued spatial events when the ping is sent. The test should drain/filter frames until it sees `pong` or times out, instead of assuming request/response ordering on a mixed event/control channel.
### Decision epochs can expose melee rows that execution rejects as out of reach
- **Found**: 2026-07-02 during Barbarian Hero vs enemy policy v3 playtest.
- **Observed artifact**: `/tmp/dnd_barbarian_v3_iteration/014_frenzied_warlock_r2.json`
- **Error**: The Codex turn summary exposed and recommended `entity|Frenzied Strike|uuid=...` against Skeleton Warlock while the Hero was still 10 ft away. The AI command endpoint rejected the row with `Target entity not in reach for Frenzied Strike (Greataxe)`.
- **Impact**: The decision epoch/action-row surface can claim a melee command is executable when the authoritative executor will reject it. This wastes an agent action attempt and makes recommendation ranking untrustworthy for melee turns.
- **Mitigation**: `ai.codex_tools.client.build_turn_summary()` now suppresses plainly out-of-reach melee rows from operator attacks/recommendations and warns the operator to move adjacent first.
- **Resolution**: Fixed the concrete source of this failure in `FrenziedStrike.pre_validate()`. Discovery now delegates to the normal action validation path after confirming a melee weapon exists, so out-of-reach or non-visible Frenzied Strike targets are filtered before decision epochs or summaries can expose them.
- **Verification**: `uv run pytest tests/manual/test_15_class_features.py::test_frenzied_strike_discovery_excludes_targets_outside_weapon_reach -q`
- **Status**: RESOLVED 2026-07-02

- **Resolution**: Current `server/test_websocket.py` uses `receive_until_type(websocket, "pong")` for ping verification. Verified with `PYTHONPATH=. uv run python server/test_websocket.py`, which passed all 3 in-process websocket checks.
- **Status**: RESOLVED 2026-06-27

### `alt_skip_slot` getattr in BaseAction violates no-duck-typing principle
- **Found**: 2026-02-28
- **File**: `dnd/core/base_actions.py` line 274
- **Error**: `getattr(self, 'alt_skip_slot', False)` — parent class (`BaseAction.effective_costs()`) uses getattr to access a field (`alt_skip_slot`) that only exists on a subclass (`SpellAction`). This is duck-typing from parent to child, violating the codebase rule against getattr/hasattr.
- **Hypothesis**: `alt_skip_slot` should either be moved up to `BaseAction` (alongside the other `alt_*` override fields that are already there), or `effective_costs()` should be overridden in `SpellAction` to handle spell-slot-specific cost filtering. Moving the field up is the simpler fix since `alt_cost_type`, `alt_extra_costs`, `alt_target_type`, and `alt_target_count` are already on `BaseAction`.
- **Status**: FIXED — moved `alt_skip_slot` to `BaseAction` alongside other `alt_*` fields, removed duplicate from `SpellAction`


### Surprised combatants can take reactions before their skipped first turn
- **Found**: 2026-06-28 during Chapter 18 surprise/reaction parity expansion
- **Test file**: `examples/test_engine_book_encounters_apis.py`
- **Error**: `CombatantState.surprised` skipped a combatant's first round-1 turn, but the combatant still began the encounter with a usable reaction. This violated the SRD surprise rule in `interactive_ruleset/Gameplay/Combat.md`: a surprised creature cannot take reactions until its first turn ends. Opportunity-attack handlers could therefore fire before the surprised combatant's skipped turn occurred.
- **Resolution**: `Encounter.start_encounter()` now spends the starting reactions of surprised combatants. The surprised turn skip path runs the entity turn-start and turn-end hooks without asking the controller for an action, so the first-turn boundary still recharges reactions after the skipped turn ends.
- **Verification**: EB-18-019 proves a surprised monster cannot make an opportunity attack before its skipped first turn, then has its reaction available again when round 2 starts.
- **Status**: RESOLVED


### Removed MeleeAIController previously chose Shove before a melee attack
- **Found**: 2026-06-28 during Chapter 18 controller parity expansion
- **Test file**: `examples/test_engine_book_encounters_apis.py`
- **Error**: The former `MeleeAIController.get_next_action()` looped over all entity-targeted actions and instantiated the first affordable valid target. Because `Shove` is also entity-targeted and was registered before weapon attack templates, an adjacent melee AI chose `Shove` instead of `Attack_MELEE_MAIN`, contradicting the controller's documented priority.
- **Resolution**: The in-process melee controller has been removed from the active runtime. Monster turns now use `ExternalAIController`, which waits for the external AI session/subprocess to choose from session-authorized available actions.
- **Verification**: EB-18-021 now proves the external-AI wait boundary and engine-derived attack affordance; EB-18-034 proves legal movement path rows preserve directional blockers for downstream AI policy.
- **Status**: SUPERSEDED



### API error messages need improvement
- **Found**: 2026-02-24
- **Test file**: `examples/test_engine_book_encounters_apis.py`
- **Error**: Some HTTP 400/404 responses from the server still return generic string details with no structured context. The action, entity, handler, equipment, session/game, event-filter, simulation, and mapeditor endpoint slices now expose correction payloads, but other endpoint families can still leave an AI agent without the current state, valid alternatives, or endpoint-specific recovery hints.
- **Hypothesis**: Remaining endpoint families should move toward structured detail payloads with a machine-readable code, current resource state, and valid alternatives. The action routes can use available-action discovery as their correction source; other endpoints need endpoint-specific context.
- **Progress**: `/action/execute` now returns structured `detail` objects for unknown action names and invalid target indexes. `/action/self`, `/action/entity`, and ordinary `/action/position` now return the same structure for unknown actions and wrong endpoint/action-shape requests. EB-18-009 and EB-18-010 prove the payload includes `code`, `message`, acting entity identity, action economy, valid action names, and the grouped available-actions correction payload. EB-18-023 proves malformed or missing `/action/entity` target UUIDs also return structured target context, known entities, action economy, and available-action corrections. EB-18-011 proves `/entity/{uuid}` lookup and handler-toggle errors include known entities or valid handler choices. EB-18-012 proves equipment/item/equip/unequip errors include valid slots, inventory item UUIDs, equipped item UUIDs, and the current equipment snapshot. EB-18-013 proves session and game-join errors include valid player types, known sessions, active-game state, requested entities/faction, and known entities. EB-18-026 proves the lower-level session action-authority validator now reports invalid sessions, disconnected sessions, missing active games, unowned entities, wrong turns, and stopped turn states with structured context. EB-18-014 proves event-filter, SSE session UUID, and simulation-control errors include valid event/phase choices, cursor state, simulation state, requested delay, and delay bounds. EB-18-015 proves mapeditor failures include valid preset/tile/object/loot IDs, saved map IDs, current map summary, directional-patch required fields, and request-specific context. EB-18-024 proves `/tile/{x}/{y}` missing-tile errors include the requested position, current grid bounds, tile count, entity count, and object count. EB-18-025 proves `/action/end-turn` no-active-encounter errors include the requested session/entity, active game context, simulation state, and known entities.
- **Resolution**: Server action/API errors now use structured `detail` dictionaries. `server/event_server.py` and `server/session.py` have no bare string `HTTPException(detail=...)` calls; remaining direct constructors use structured helper payloads.
- **Verification**: EB-18-009 through EB-18-015 and EB-18-023 through EB-18-026 cover the endpoint families above. `tests/engine_book/test_book_integrity.py::test_server_http_errors_do_not_use_bare_string_details` guards the source-level contract, and `rg -n "HTTPException\\(|detail=\\\"|detail=f\\\"" server -g '*.py'` now reports only structured constructors/helper calls.
- **Status**: RESOLVED

### Raw ability-score modifiers were counted as direct ability-modifier bonuses
- **Found**: 2026-06-28 during Chapter 16 Primal Champion parity expansion
- **Test file**: `examples/test_engine_book_class_features.py`
- **Error**: `PrimalChampion` correctly raised raw Strength and Constitution scores from 20 to 24, but attack, save, skill, AC, and HP-derived paths treated the +4 raw score modifier as a +4 ability modifier in several entity assembly methods. SRD parity expects a +4 raw ability-score increase at 20 to become a +2 ability-modifier increase.
- **Resolution**: `Ability.modifier` and `Ability.get_combined_values()` now aggregate the raw score first and then apply the D&D ability-score normalizer. Entity skill, saving throw, attack, AC, and spell-attack assembly now use `Ability.get_combined_values()` instead of manually combining `ability_score` and `modifier_bonus`.
- **Verification**: EB-16-023 proves Primal Champion gives +2 to the relevant STR/CON-derived combat surfaces and +40 HP at Barbarian level 20.
- **Status**: RESOLVED

### Divine Smite omitted the SRD undead and fiend bonus die
- **Found**: 2026-06-28 during Chapter 16 Divine Smite parity expansion
- **Test file**: `examples/test_engine_book_class_features.py`
- **Error**: `create_divine_smite_processor()` capped smite dice at 5d8 from spell slot level but did not add the SRD +1d8 against undead or fiend targets, even though `Entity.creature_type` and `CreatureType.UNDEAD`/`CreatureType.FIEND` were available.
- **Resolution**: Divine Smite now checks the target entity's creature type in the damage-roll-result handler, adds one d8 for undead and fiend targets, and caps those target-type smites at 6d8. The handler records `divine_smite_creature_type_bonus` in event context.
- **Verification**: EB-16-024 proves humanoid targets keep the normal 5d8 cap, undead targets add the bonus d8 at 1st-level slots, and fiend targets can reach the 6d8 target-type cap with a 5th-level slot.
- **Status**: RESOLVED

### Lucky condition removal left its luck-point resource behind
- **Found**: 2026-06-28 during Chapter 16 Lucky policy parity expansion
- **Test file**: `examples/test_engine_book_class_features.py`
- **Error**: Removing `LuckyFeature` cleaned up the owned d20 handler through the base condition lifecycle, but the `luck_points` resource granted in `_apply()` remained on the entity.
- **Resolution**: `LuckyFeature._remove()` now removes the `luck_points` resource before delegating to the base removal phases.
- **Verification**: EB-16-025 proves Lucky's automatic policy gates, long-rest recharge, handler cleanup, and resource cleanup.
- **Status**: RESOLVED

### Pytest capture mode fails in the Codex shell during engine-book runs
- **Found**: 2026-06-28 during Chapter 18 API parity verification
- **Test file**: `tests/engine_book/test_chapter_18_encounters_apis.py`
- **Error**: Running `uv run pytest -q tests/engine_book/test_chapter_18_encounters_apis.py tests/engine_book/test_book_integrity.py` from the Codex shell reported `no tests ran`, then failed during pytest shutdown with `FileNotFoundError` in `_pytest/capture.py` while truncating the capture temp file. `uv run pytest --collect-only --capture=no -q tests/engine_book/test_chapter_18_encounters_apis.py` collected the expected ten Chapter 18 parity cases, and a `pytest.main(["-q", "--capture=no", "tests/engine_book"])` driver passed the full engine-book suite.
- **Hypothesis**: This looks like an interaction between pytest 9 capture handling and the current Codex shell/WSL output capture path rather than an engine failure.
- **Resolution**: `pyproject.toml` now sets pytest `addopts = ["--capture=no"]`, and the book-integrity test asserts that the uv-driven pytest contract keeps capture disabled.
- **Verification**: The previously failing no-`-s` command now passes, and full `uv run pytest -q tests/engine_book` runs through the configured capture mode.
- **Status**: RESOLVED 2026-06-28

### Intermittent EB-10 forced-movement spatial-entered ordering in full-suite runs
- **Found**: 2026-06-28 during full engine-book verification after Chapter 16 Primal Champion expansion
- **Test file**: `tests/engine_book/test_chapter_10_core_actions_combat.py`
- **Error**: One `uv run pytest -s -q tests/engine_book` run failed `test_eb_10_021_forced_movement_traverses_terrain_without_step_costs` because the collected `SPATIAL_ENTITY_ENTERED` EFFECT positions included the pushed target's starting cell `(6, 5)` after the expected traversal positions `(7, 5)`, `(8, 5)`, `(9, 5)`, `(10, 5)`.
- **Root cause**: `EventQueue._store_event()` appended to `_all_events` and then sorted the same list by timestamp. `event_cursor()` and `iter_events_since()` use `_all_events` length and slicing as an append-stream cursor, so a late-registered event with an older timestamp could move pre-cursor events after the cursor and hide the newly registered event. EB-10-021 then observed a pre-cursor starting-cell `SPATIAL_ENTITY_ENTERED` event as though it happened after the cursor.
- **Resolution**: `_all_events` is now append-stable. `get_events_chronological()` returns a timestamp-sorted copy for chronological reads, while cursor-based APIs keep raw append-stream semantics. EB-04-013 pins this invariant.
- **Verification**: A focused reproducer now returns only the late appended event after the cursor, `uv run python examples/test_engine_book_event_lifecycle.py` passes, `uv run pytest -q tests/engine_book/test_chapter_04_event_lifecycle.py tests/engine_book/test_chapter_10_core_actions_combat.py tests/engine_book/test_book_integrity.py` passes 46/46, `uv run pyright dnd/core/events.py examples/test_engine_book_event_lifecycle.py examples/test_engine_book_core_actions_combat.py` reports 0 errors, a 300-iteration EB-10-021 stress loop passes, full `uv run pytest -q tests/engine_book` passes 341/341, and the direct Chapter 10 example script passes.
- **Status**: RESOLVED 2026-06-28

### Barbarian unarmored-defense shield example assumed shield with two-handed weapon
- **Found**: 2026-06-28 during Chapter 13 armor factory hygiene verification.
- **Test file**: `examples/test_barbarian_unarmored_defense.py`
- **Error**: `test_unarmored_defense_with_shield()` used a helper that always equipped a greataxe, then tried to equip a shield in the melee off hand. The old hard-blocking equipment policy raised `ValueError`; the current videogame policy would instead displace the two-handed melee weapon.
- **Hypothesis**: The legacy test intended to verify Unarmored Defense plus shield AC, not the hand-occupancy policy already pinned by EB-13-014.
- **Resolution**: The test helper now accepts `equip_greataxe=False`, and the shield-specific test uses that setup before equipping the shield.
- **Verification**: `uv run python examples/test_barbarian_unarmored_defense.py` passes.
- **Status**: RESOLVED 2026-06-28

### Combat-log SSE can publish an action log before the matching completion event
- **Found**: 2026-06-28 during Chapter 18 SSE combat-log ordering expansion
- **Test file**: `examples/test_engine_book_encounters_apis.py`
- **Error**: A live stream subscription received the Dash `combat_log` envelope before the Dash completion `game_event`. `EventQueue.phase_to(COMPLETION)` calls the combat-log callback before posting the completion event, and the event passed to the callback still has the previous phase UUID. `server.event_stream.DndEventStream._on_combat_log()` only checked whether that UUID was already indexed, so it published the log immediately instead of holding it until the completion event was stored.
- **Resolution**: `DndEventStream._on_combat_log()` now treats registered events as pending when the stored event is missing or its stored phase differs from the callback event phase. Pending log payloads are released when `_on_event()` publishes the matching completion event, and their event cursor is updated to the completion event cursor before SSE formatting.
- **Verification**: EB-18-018 proves a Dash combat log follows the Dash completion game event and that the SSE id uses the completion event cursor plus the combat-log cursor.
- **Status**: RESOLVED



### Orchestrator drain timeout causes commands to execute against wrong entity
- **Found**: 2026-02-25, PvP session (Match 1, Round 2)
- **Test file**: N/A (orchestrator/CLI issue, not game engine)
- **Error**: Before the Codex CLI migration, after a 45-second drain timeout killed the autonomous subprocess, buffered commands (e.g. `dodge`) could execute against the *next* entity in turn order instead of the intended entity. In the observed case, a `dodge` command meant for Skeleton Warlock was applied to Skeleton Archer after the turn auto-advanced.
- **Root cause**: Two problems:
  1. The subprocess could keep generating or flushing output after the orchestrator had already detected the turn end and moved on.
  2. Orphaned commands were routed through the agent CLI without validating that the command still belonged to the entity whose turn originally spawned the subprocess.
- **Impact**: Entity gets actions applied without spending action economy (Archer got Dodging for free). Turn log file for the affected entity is never created.
- **Resolution**: The orchestrator now builds `codex exec --json` invocations and injects an exact guarded command prefix into each turn prompt: `uv run python -m cli.agent --token ... --expect-entity ... <command>`. The agent CLI validates the expected entity UUID against the server's current active controlled entity before executing any game command, so stale buffered commands are rejected instead of being applied to the next turn's entity. The old `claude` player/session/controller surface was migrated to `codex`.
- **Verification**: `uv run pyright dnd/controller.py dnd/encounter.py server/session.py server/event_server.py cli/agent.py cli/orchestrator.py examples/test_engine_book_encounters_apis.py` passed with 0 errors. `uv run pytest -q tests/engine_book/test_chapter_18_encounters_apis.py tests/engine_book/test_book_integrity.py` passed 35/35. `uv run python examples/test_engine_book_encounters_apis.py` passed.
- **Status**: RESOLVED 2026-06-28

### Codex self-play metrics missed current stream command and token events
- **Found**: 2026-07-01 during a real Codex-vs-Codex sorcerer self-play run.
- **Test file**: N/A yet; observed in `game_logs/selfplay_sorcerer_smoke_2`.
- **Error**: The orchestrator completed a one-turn victory and the turn log contains multiple `command_execution` stream items plus a `turn.completed` usage payload, but `metrics.json` reports `game_actions: 0`, zero action timestamps, and zero token usage.
- **Resolution**: `cli/orchestrator.py` now handles the current `thread.started`, `item.started`, `item.completed`, and `turn.completed` Codex stream events. It records Codex thread IDs for resume, counts completed `cli.agent` command executions, records first-action time, counts agent messages, reads current usage fields such as `cached_input_tokens`, and writes current-schema command steps into trajectory logs.
- **Verification**: EB-18-029 proves current Codex item streams produce nonzero command metrics, token metrics, and trajectory steps. `uv run pytest tests/engine_book/test_chapter_18_encounters_apis.py -q` passes 35/35, and `uv run pyright cli/orchestrator.py tests/engine_book/test_chapter_18_encounters_apis.py` reports 0 errors.
- **Status**: RESOLVED 2026-07-01

### Published AI decision epoch was rejected as stale after its own control frame
- **Found**: 2026-07-02 during Sorcerer challenge validation against external enemy policy v4.
- **Test file**: `tests/manual/test_36_seamless_subjective_runtime.py`
- **Error**: Skeleton Warrior selected `Move -> (7, 7)` from a valid `turn_start` decision epoch, but `/ai/sessions/{session_id}/commands/execute` rebuilt a `snapshot` epoch after the decision-epoch control frame had advanced the observation cursor. The row was then rejected as `stale` even though no gameplay state had changed.
- **Resolution**: `server.event_server` now tracks the current published decision epoch per session and reuses it while it still matches the active actor, round, and turn. Epochs rotate when a real action boundary publishes a new epoch or when the turn is cleared.
- **Verification**: `test_published_epoch_survives_control_cursor_advancement` proves a command based on the published epoch is accepted after the control frame advances the cursor. Focused seamless runtime tests and pyright pass.
- **Status**: RESOLVED 2026-07-02

### Subjective observation forgets living enemies after line-of-sight closure
- **Found**: 2026-07-02 during Sorcerer challenge validation against external enemy policy v4.
- **Test file**: N/A yet; live artifact `/tmp/dnd_sorcerer_v4_iteration/008_close_door.json`.
- **Error**: After the Hero closed the central door, living Skeleton Archer and Skeleton Warrior disappeared from `living_enemies` and did not appear in `remembered_enemies`. Only the dead Warlock remained remembered, with `position: null`. When Warrior reopened the door, the living enemies reappeared as visible.
- **Hypothesis**: The observation projector builds known entity facts from current `observer.senses.entities`, but does not retain last-known facts for visible-before living enemies when blockers remove current visibility.
- **Additional evidence**: 2026-07-03 Sorcerer v5 challenge playtest reached turns where visible `living_enemies` became empty while Skeleton Warlock was still alive elsewhere. The operator surface fell back to frontier exploration instead of last-known enemy search, increasing tool calls and movement churn.
- **Additional evidence**: 2026-07-03 skeleton-side Barbarian validation showed the same failure through a door loop. When a skeleton closed the central door, the living Barbarian Hero dropped out of `living_enemies` and did not appear as remembered/last-known, so the next compact surface treated reopening the door as fresh exploration instead of a known enemy line-of-sight recovery.
- **Progress**: 2026-07-03 external enemy policy v7 now consumes remembered enemy facts when they exist and pursues last-known positions before generic exploration. This mitigates consumers that receive valid memory, but it does not fix the projector bug where some living enemies disappear instead of becoming remembered.
- **Status**: OPEN

### Subjective runtime creates excessive resync/subscription churn in short fights
- **Found**: 2026-07-02 during Sorcerer challenge validation against external enemy policy v4.
- **Test file**: N/A yet; live server log `/tmp/dnd_sorcerer_v4_iteration/server.log`.
- **Error**: One short fight produced `41` AI observation snapshots, `20` observation subscribe requests, `10` resync starts, `10` resync completions, and pending `BoundedSubscription.get()` task warnings on disconnect.
- **Hypothesis**: The hot runtime treats normal stream closure/sync boundaries too aggressively as resync conditions, and the SSE generator still leaves pending subscription tasks around some disconnect paths.
- **Additional evidence**: 2026-07-03 Barbarian validation after the epoch-cache fix removed stale command acks, but still produced `75` snapshots, `36` observation subscribe requests, `15` resync starts, `15` resync completions, and `26` pending subscription task warnings. This confirms the churn is independent of the false-stale bug.
- **Progress**: 2026-07-03 found and fixed a command-follow-up bug where the hot runtime treated the normal initial SSE `sync` envelope as a resync trigger before consuming replayed `COMMAND_RESULT` and follow-up `DECISION_EPOCH` frames. A follow-up Barbarian rerun completed without hanging, but still showed `3` stale command acks. Those were traced to server-side epoch clears: a late clear for the previous actor could erase the newer active actor epoch, causing the next snapshot to mint a different `snapshot` epoch for the same actor/round/turn. Epoch clear is now actor-aware and does not discard another actor's current epoch.
- **Additional evidence**: 2026-07-03 Sorcerer v5 challenge playtest confirmed the stale/resync fixes worked in a full game: `0` stale command acks and `0` resync starts/completions. The remaining runtime issue is now clearer: the same game still produced `133` snapshot requests, `102` observation subscriptions, and `85` pending `BoundedSubscription.get()` task warnings.
- **Additional evidence**: 2026-07-03 skeleton-side Barbarian validation completed after the door-boundary fix, but the final-run server-log slice still showed `249` snapshots, `72` observation subscriptions, and `87` pending subscription task warnings. The run had `0` debug `/available-actions` hits, so this is stream/materialization pressure rather than fallback action polling.
- **Additional evidence**: 2026-07-03 default-monster Barbarian attempt with policy v6 timed out before a winner and showed command-result latency around `5077 ms` p50 and `21047 ms` max in the collected enemy trace. The tactical policy needed improvement too, but the latency confirms runtime throughput remains a separate bottleneck.
- **Additional evidence**: 2026-07-03 Sorcerer v7 victory still produced `105` snapshots, `90` observation subscriptions, `75` pending subscription task warnings, and external-AI command-result latency around `2731 ms` p50 / `24178 ms` max. The terminal Codex watch hang was fixed separately, so this issue is now specifically stream churn and command latency.
- **Additional evidence**: 2026-07-04 in-process `skeleton_mark_focus_fire` self-play timing shows policy selection is tiny (`0.19 ms` average, `0.635 ms` max), while snapshot fetch/validation, dense epoch reduction, and command submission dominate the command-loop cost. This narrows the speed problem away from the behavior-tree selector itself.
- **Additional evidence**: 2026-07-04 `forced_movement_hazard_bridge` self-play shows the same shape after route tracing: policy averaged `0.179 ms` with `0.742 ms` max, while snapshot, reduction, and command submission still produced larger spikes (`337.237 ms`, `282.276 ms`, and `399.482 ms` max respectively).
- **Verification**: `test_runtime_command_followup_ignores_initial_stream_sync` now proves `sync -> command_result -> decision_epoch` completes without snapshot resync. `test_epoch_clear_for_previous_actor_does_not_invalidate_current_server_epoch` proves a clear for actor A does not invalidate actor B's current server epoch. A fresh full game has now separated the concerns: false stale/resync appears fixed, but snapshot/subscription volume and disconnect cleanup remain open.
- **Status**: OPEN

### Codex watch blocked after encounter end
- **Found**: 2026-07-03 during Sorcerer v7 default-monster playtest.
- **Test file**: `tests/manual/test_30_codex_takeover_tools.py`
- **Error**: The Sorcerer defeated all three skeletons, `/game/status` reported `encounter_active=false`, but `CodexToolClient.watch()` opened another observation subscription and waited indefinitely because no future controlled turn could arrive.
- **Resolution**: `CodexToolClient.watch()` now checks `/game/status` after the current brief. If the encounter is over, it returns `WatchResult(status="encounter_ended", event="encounter_ended")` without opening another stream.
- **Verification**: `test_codex_watch_returns_when_encounter_already_ended` proves no stream is opened after terminal status. The live ended Sorcerer server returned `encounter_ended` in `13.73 ms`.
- **Status**: RESOLVED 2026-07-03

### Sorcerer turn summaries are still too large
- **Found**: 2026-07-03 during Sorcerer v7 default-monster playtest.
- **Test file**: N/A yet; live artifact `/tmp/dnd_sorcerer_v7_default_monsters/000_play_summary.json`.
- **Error**: The largest compact Sorcerer turn summary still reached `50222` characters and `653` normalized action choices.
- **Hypothesis**: Spell-slot variants, scroll variants, multi-target rows, and position-targeted area rows are still being serialized too broadly even after variant grouping. The agent needs a tighter default summary plus expandable detail, not every legal row in the primary surface.
- **Status**: OPEN

### Caster useful movement could require raw fallback when no retreat row existed
- **Found**: 2026-07-03 during skeleton-side v7 playtest against external Barbarian.
- **Test file**: `tests/manual/test_30_codex_takeover_tools.py`
- **Error**: Skeleton Warlock had spent its action and had useful movement rows toward the visible Hero, but because Warlock is a spacing-preferring caster and no retreat row existed, the recommendation list stayed empty while `meaningful_commands_remaining` was true. The driver used raw `fallback:useful_moves` three times.
- **Resolution**: Useful visible-enemy movement is now recommended when a caster prefers spacing but no retreat move exists. Retreat still wins when available.
- **Verification**: `test_codex_turn_summary_recommends_caster_closing_when_no_retreat_exists` covers the Warlock shape, and `test_codex_turn_summary_prefers_retreat_over_adjacency_for_spellcaster_without_offense` proves retreat priority remains intact.
- **Status**: RESOLVED 2026-07-03

### Autonomous ranged enemies closed after spending their pressure action
- **Found**: 2026-07-03 while reviewing the enemy-AI challenge goal after skeleton-side v7 playtesting.
- **Test file**: `tests/manual/test_35_subjective_external_ai.py`
- **Error**: The external enemy behavior tree could cast or attack, then use leftover movement to walk toward the visible Hero because generic visible-enemy pursuit ran after the pressure rows were no longer affordable. This made archers and warlocks easier to punish.
- **Resolution**: The external reducer now carries action-economy values from decision epochs. The behavior tree has a ranged-spacing branch before generic pursuit: spent ranged/caster actors retreat when a farther movement row exists, otherwise they hold range; melee actors still close.
- **Verification**: `test_ranged_enemy_retreats_after_spending_pressure_action`, `test_ranged_enemy_holds_spacing_after_spending_action_when_no_retreat_exists`, and `test_melee_enemy_still_closes_after_spending_action` cover the policy boundary.
- **Status**: RESOLVED 2026-07-03

### Barbarian operator surface could fall into torch-toggle utility loops
- **Found**: 2026-07-03 during Barbarian Hero playtest against external skeleton AI.
- **Test file**: `tests/manual/test_30_codex_takeover_tools.py`
- **Error**: The first Barbarian run hit the step limit with `90` commands because the turn summary had no recommendations but still reported `meaningful_commands_remaining=true`. Raw fallback then executed `56` torch toggles plus free potion rows while the encounter remained active.
- **Root cause**: Basic/utility self interactions were too broadly counted as meaningful. Dash, Disengage, Dodge, Reckless Attack, End Rage, torch toggles, and free consumables could keep the turn alive even when no tactical recommendation existed.
- **Resolution**: Dash is now recommended when no-contact exploration stalls with zero movement and an action remains. Frenzy/Reckless recommendations require living-enemy pressure. End Rage, torch toggles, and free consumables no longer keep spent turns alive.
- **Verification**: `test_codex_turn_summary_recommends_dash_for_no_contact_exploration_when_movement_spent` covers the Dash replacement, and `test_codex_turn_summary_end_rage_and_light_toggles_do_not_keep_spent_turn_alive` covers the spent-turn utility boundary. A fresh live validation completed with `0` torch toggles and Hero victory.
- **Status**: RESOLVED 2026-07-03

### Persistent-zone policy chooses direct damage before approach-lane control
- **Found**: 2026-07-13 during a read-only AI architecture review.
- **Test command**: `uv run pytest tests/manual/test_35_subjective_external_ai.py -q` (`1 failed, 116 passed`).
- **Failure**: `test_persistent_zone_policy_uses_guardian_on_approach_lane_before_damage` expects `choose_external_melee_command` to return `Guardian of Faith__slot_4`, but it returns `Magic Missile__slot_1`.
- **Resolution**: The duplicate reduced-state evaluator and this implementation-specific test were removed. Persistent zones and direct damage now compete through typed shared-policy proposals and utility evidence; no controller can fall back to the former ordered leaf stack.
- **Status**: SUPERSEDED 2026-07-14 by the single `PolicyHost` architecture. Persistent-zone utility still requires scenario-level evidence in the continuing self-play loop.

### Fast Move discovery has an incompatible paths-by-position type
- **Found**: 2026-07-13 during a read-only AI architecture review.
- **Command**: `uv run pyright dnd/entity.py dnd/core/base_actions.py`.
- **Failure**: `dnd/entity.py:3459` passes `paths_by_position` with type `DefaultDict[...] | dict[...]` to `_collect_fast_move_targets`, whose parameter is annotated `DefaultDict[...]`, producing `reportArgumentType`. Runtime tests were not failing.
- **Repeat**: The same sole diagnostic appeared while type-checking the typed AI routine and entity-composition changes with `uv run pyright dnd/entity.py ai/policy/routines.py ai/external/policy.py ai/external_melee_agent.py ai/external_selfplay.py ai/evaluation/artifacts.py ai/knowledge/deriver.py ai/external/state.py tests/engine_book/test_chapter_06_entity_composition.py tests/manual/test_45_policy_routines.py`.
- **Hypothesis**: The helper annotation is narrower than the actual branch result. Its read-only access may accept a `Mapping[Tuple[int, int], List[Tuple[int, int]]]` rather than requiring default-factory behavior.
- **Status**: RESOLVED 2026-07-13; `_collect_fast_move_targets` now accepts the read-only `Mapping` contract used by walking and swimming path maps. Focused Pyright reports zero errors.

### Dash ignores effective speed modifiers such as Barbarian Fast Movement
- **Found**: 2026-07-13 while reviewing the live level-5 Barbarian run in `ai/evidence/runs/20260713-phase4-double-door-dark-hunt-seed8675310.json`.
- **Live evidence**: `Validation Door Barbarian` had `Fast Movement` and an effective movement value of `40`, but `self|Dash|index=0` reported `Applied Dashing - gained 30ft extra movement`. An isolated reproduction starts at `40` and ends at `70`; speed-relative Dash should grant `40` and produce `80` available movement before movement costs.
- **Root cause**: `Dashing._apply()` reads `movement.get_base_modifier().value`, and `Dash._apply()` reports `action_economy.get_base_value("movement")`. Both return the immutable `30` base and omit the contextual `+10` Fast Movement modifier.
- **Coverage gap**: Existing tests prove ordinary 30-foot Dash and Fast Movement separately, but do not combine Dash with modified speed.
- **Hypothesis**: Movement needs explicit speed-relative semantics that distinguish effective walking speed from remaining movement budget, movement costs, and movement grants from earlier Dash uses. Reading `normalized_score` directly would include the wrong categories after movement is spent or Dash is applied, so the fix should expose the effective current speed before adding a Dash budget grant.
- **Status**: OPEN; documented only during read-only investigation.

### Action-discovery manual test has stale optional target narrowing
- **Found**: 2026-07-14 during focused Pyright validation over touched files; reproduced on 2026-07-15 during focused type checking of action changes.
- **Test file**: `tests/manual/test_09_action_discovery_and_costs.py` (9 Pyright errors at lines 117, 282, 605, 611, and 623)
- **Command**: `uv run pyright dnd/actions.py tests/manual/test_09_action_discovery_and_costs.py`
- **Error**: The test passes optional `target_uuid` values to `Entity.get()` without narrowing at all five locations (`reportArgumentType`) and accesses `.name` on optional `Entity.get()` results at lines 282, 605, 611, and 623 (`reportOptionalMemberAccess`).
- **Scope**: The newly changed `dnd/actions.py` itself has no reported error; these diagnostics are pre-existing test typing issues unrelated to the action changes.
- **Hypothesis**: The readout paths should explicitly narrow each target UUID and entity lookup before member access.
- **Status**: OPEN

### EB-10-021 reuses an exhausted event iterator
- **Found**: 2026-07-13 during focused forced-movement verification.
- **Test command**: `uv run pytest tests/engine_book/test_chapter_10_core_actions_combat.py::test_eb_10_021_forced_movement_traverses_terrain_without_step_costs`.
- **Failure**: The later `next(...)` lookup raises `StopIteration`, even though `forced_event` was found during the first pass over the same event sequence.
- **Cause**: `indexed_events = EventQueue.iter_events_since(cursor)` is a one-shot iterator. The `new_events = [...]` comprehension exhausts it, and the test later attempts to reuse `indexed_events` in `next(...)`.
- **Suggested correction**: This is a test-only defect. Materialize the sequence once with `indexed_events = list(EventQueue.iter_events_since(cursor))`, then perform both searches against that list.
- **Status**: OPEN; documented only.

### Entity fast-move helper has a narrow path-map annotation
- **Command**: `uv run pyright dnd/entity.py`.
- **Error**: Around `dnd/entity.py:3460`, a `DefaultDict[...] | dict[...]` value is passed to `_collect_fast_move_targets`, whose parameter accepts only `DefaultDict[...]`, producing `reportArgumentType`.
- **Hypothesis**: The helper parameter annotation is narrower than its actual callers require; it likely needs a read-only mapping-compatible type rather than guaranteed `DefaultDict` behavior.
- **Status**: RESOLVED 2026-07-13; duplicate of the entry above. The helper now accepts `Mapping`, and focused Pyright reports zero errors.

### Live-replication tutorial fixtures hard-coded stale EventQueue cursors
- **Found**: 2026-07-14 during focused live-replication stream testing.
- **Test file**: `tests/manual/test_25_live_replication_streams.py` (`6` failures).
- **Failure**: Tutorial output originally hard-coded initial EventQueue cursor `52` and post-attack cursor `78`. The sensory-prefilter repair first reduced those totals to `48` and `74`; the later EventQueue identity repair removed exact-object duplicate registrations and established the current unique-version totals of `42` and `68`.
- **Root cause**: The old `52`-event setup included one empty, `paths_dirty`-only `SENSORY_UPDATE` lifecycle (four phases). `server/live_replication.py:65-67` creates both actors before the explicit senses initialization, and the current spatial prefilter in `dnd/blocks/sensory.py:531-539` now rejects the irrelevant setup spatial event before taking a senses snapshot or emitting that lifecycle. No observable facts were lost: `ai/observation/projector.py:1362-1382` already treats path dirtiness by itself as non-subjective.
- **Preserved behavior**: Fanout counts remain correct, and the attack still advances the cursor by exactly `26` events.
- **FOV check**: Bounded and unbounded shadowcast produced the same cursor at each stage, so the FOV optimization was not the source of either count correction.
- **Resolution**: The deterministic tutorial readouts now expect `42`/`68`. Event history contains unique event versions, the attack still advances by exactly `26` events, and the behavioral assertions continue to prove the meaningful attack delta and fanout counts.
- **Status**: RESOLVED 2026-07-14; `tests/manual/test_25_live_replication_streams.py` passes all 8 focused tests.

### Standalone spotted and hazard combat logs may not wake subjective observation sessions
- **Found**: 2026-07-14 while tracing standalone combat-log delivery into initialized subjective sessions.
- **Affected logs**: `ENTITY_SPOTTED` and `HAZARD_DETECTED` are emitted through `EventQueue.push_combat_log()` from `dnd/entity.py:3215-3234` and `dnd/blocks/sensory.py:1030-1083`.
- **Failure risk**: `EventQueue.push_combat_log()` creates an unregistered completion (`use_register=False`) and invokes only the combat-log callback (`dnd/core/events.py:979-995`). The encounter appends the entry and notifies encounter combat-log listeners (`dnd/encounter.py:804-835`), but the subjective projector is attached only through `EventQueue.add_on_event_callback()` and updates initialized sessions only when a registered completion arrives (`ai/observation/projector.py:146-149`, `ai/observation/projector.py:207-223`). A standalone spotted/hazard log can therefore advance the encounter combat-log history without publishing a subjective observation frame or waking that session live.
- **Root cause**: Subjective combat-log history is imported from the encounter when a projection cache first bootstraps (`ai/observation/projector.py:653-662`); after initialization, combat-log patches are produced while iterating registered EventQueue completions (`ai/observation/projector.py:688-715`, `ai/observation/projector.py:748-825`). There is no corresponding encounter combat-log listener for standalone entries.
- **Resolution**: `EventQueue.push_combat_log()` now marks its unregistered carrier explicitly as a standalone log boundary. The subjective projector attaches to the existing encounter combat-log listener, flushes pending registered completions first, filters the entry per session, and publishes one cursor-ordered `COMBAT_LOG` observation frame. Registered event logs remain owned exclusively by EventQueue completion projection. Spotted/hazard producers now include perceiver metadata, and spotted logs include observer-scoped identity grants so synchronous filtering preserves only the identity actually established by that observer.
- **Verification**: `tests/manual/test_28_subjective_observation_stream.py` covers live wakeup, replay equality, unchanged EventQueue cursor, exact combat-log cursor, observer filtering, target identity, and registered-log non-duplication.
- **Status**: RESOLVED 2026-07-14; all 25 focused subjective observation tests pass.

### Server action protocol boundaries have incompatible model and collection types
- **Command**: `uv run pyright server/event_server.py`.
- **Errors**: Around `server/event_server.py:3015`, a `dnd.core.base_actions.ActionOutcomeProfile` is passed where `ai.protocol.control.ActionOutcomeProfile` is expected. Around `server/event_server.py:3897`, a `Sequence[str]` is passed where `ExecuteByIndexRequest` requires `List[str]`.
- **Required correction**: Add deliberate protocol conversion/copying at both boundaries instead of relying on structurally similar models or broader collection types.
- **Resolution**: The server now converts the engine outcome profile into the protocol model and materializes the target UUID sequence as the request model's list type.
- **Status**: RESOLVED 2026-07-14; focused Pyright over `server/event_server.py` is clean.

### Potion of Haste contradicts its no-lethargy contract
- **Found**: 2026-07-14 during a focused rules audit.
- **Source**: `dnd/items/test_items.py:1474-1479` says `DrinkHastePotionAction` has no lethargy, but `dnd/items/test_items.py:1512-1516` creates `HasteEffect` without overriding its effective `apply_lethargy=True` default (`dnd/spells/transmutation.py:624`). On expiry/removal, `dnd/spells/transmutation.py:773-784` therefore applies one round of `Incapacitated`.
- **Required decision**: Choose one explicit ruleset for the potion: retain lethargy and correct the action contract, or disable lethargy in the potion-created effect. Do not silently reconcile the mismatch.
- **Status**: OPEN; audit entry only, no production behavior changed.

### Potion-created spell effects omit the magical condition tag
- **Found**: 2026-07-14 during a focused rules audit.
- **Source**: Potion creation omits `ConditionTag.MAGICAL` for `GreaterInvisibilityEffect` at `dnd/items/test_items.py:1097-1100` and `HasteEffect` at `dnd/items/test_items.py:1512-1516`, so both inherit the empty tag set from `dnd/core/base_conditions.py:306-308`. Spell creation explicitly supplies the tag at `dnd/spells/illusion.py:860-864` and `dnd/spells/transmutation.py:843-848`.
- **Impact**: Identical named effects differ under antimagic-style and other tag-filtered behavior solely by whether a potion or spell created them.
- **Status**: OPEN; requires an explicit ruleset decision, and no production behavior was changed.

### Engine-book integrity metadata and documentation lag current coverage
- **Found**: 2026-07-15 while running unrelated focused validation; consolidated rerun of the four existing engine-book integrity issues above.
- **Command**: `uv run pytest tests/engine_book/test_book_integrity.py -q`
- **Result**: 27 integrity tests passed and four failed: parity rows are missing for `EB-11-022`, `EB-11-023`, `EB-12-020`, `EB-12-021`, and `EB-12-022`; outline ranges stop before Chapter 11 `023` and Chapter 12 `022`; the manifest expects missing `server/event_server.py::timing_middleware`; and `advance_encounter` lacks the manifest-required Google-style `Args:` block.
- **Hypothesis**: The integrity metadata and documentation lag the current code and tests.
- **Status**: OPEN; documented only, no fixes attempted.

### Spellcasting core test has pre-existing Optional UUID typing errors
- **Found**: 2026-07-15 during focused Pyright validation of combat-log, base-action, and Eldritch Blast outcome-profile changes.
- **Command**: `uv run pyright tests/manual/test_13_spellcasting_core.py`
- **Error**: Six pre-existing Optional/UUID diagnostics occur at the current lines 369, 414, 620, and 623. Optional UUIDs reach `BaseObject.get()`, and optional event or lookup results are accessed through `.value` or `.name` without narrowing.
- **Scope**: The new Eldritch Blast test is not implicated. Focused runtime tests pass, and focused Pyright over the changed production, epoch, and policy files reports zero errors.
- **Hypothesis**: Narrow the optional event fields, UUIDs, and lookup results explicitly in the tutorial readout paths.
- **Status**: OPEN; test typing issue only, no fix attempted.

### Policy host consumer-parity fixture omits the current conditional-target trace node
- **Found**: 2026-07-15 during focused policy-host test validation.
- **Test**: `tests/manual/test_48_policy_host.py::test_policy_host_exposes_one_identical_decision_and_trace_to_every_consumer`
- **Failure**: The expected policy trace omits the current `ConditionalTargetEffects` node produced by the policy host, so the asserted trace no longer matches the production trace.
- **Scope**: This is an unrelated pre-existing fixture mismatch. The test-only edit under validation did not modify policy production code.
- **Status**: OPEN; documented only, no production or test behavior changed.

### Resolved: Counterspell violated cast-cost, spell-level, and event-history contracts
- **Found**: 2026-07-15 during current AI protocol work on Counterspell interruption outcomes.
- **Original cast costs**: When Counterspell cancels the execution event, `BaseAction.apply()` returns at `dnd/core/base_actions.py:1179-1183`; `_apply_costs()` at `dnd/core/base_actions.py:1261-1266` is never reached, so the original caster spends neither the action nor the spell slot.
- **Cantrips**: `dnd/spells/abjuration.py:704-708` treats cast level `0` as ineligible and returns before Counterspell can react, incorrectly ignoring cantrips.
- **Minimum slot**: `dnd/spells/abjuration.py:710-716` searches from the incoming spell level, so a level-1 or level-2 spell can consume an illegal level-1 or level-2 Counterspell slot instead of enforcing Counterspell's minimum level-3 slot.
- **Duplicate cancel history**: `Event.cancel()` posts the CANCEL version at `dnd/core/events.py:460-477`, then the handler dispatcher appears to store the same canceled event UUID again at `dnd/core/events.py:1127-1151`.
- **Resolution**: `Event.canceled_from_phase` now distinguishes declaration rejection from execution interruption; `SpellAction` settles its serialized action and selected-slot costs only for the committed execution case. Counterspell accepts level-zero cantrips, enforces a minimum level-3 reaction slot, and emits a typed `CounterspellReactionEvent` plus subjectivity-filtered interruption log. Handler-produced event versions now use collision-safe identity, while exact-object re-registration is idempotent.
- **Verification**: `tests/manual/test_50_counterspell_engine_contract.py` covers automatic and checked interruption, failed checks, upcasts, declaration cancellation, event-history identity, reaction logs, and hidden-reactor redaction. Related event lifecycle, spell-family, subjective-observation, self-play, and Pyright checks pass.
- **Status**: RESOLVED on 2026-07-15.

### Forced-movement focused test reuses an exhausted event iterator
- **Found**: 2026-07-15 during focused Counterspell/EventQueue UUID-idempotency validation.
- **Test**: `tests/engine_book/test_chapter_10_core_actions_combat.py::test_eb_10_021_forced_movement_traverses_terrain_without_step_costs` failed at approximately line 561; 24 other tests passed.
- **Failure**: The test consumes `EventQueue.iter_events_since(cursor)` into `new_events`, then calls `next(...)` on the same exhausted iterator, raising `StopIteration`.
- **Hypothesis**: This is test fixture/iterator reuse, not a regression from the Counterspell/EventQueue UUID-idempotency change.
- **Status**: OPEN; documented only, no code or tests changed.

### EB-13-008 second potion use returns no result
- **Found**: 2026-07-15 while auditing unrelated Counterspell item-charge behavior.
- **Test**: `tests/engine_book/test_chapter_13_items_inventory_equipment.py::test_eb_13_008_consumable_use_actions_consume_charges_and_stacks`.
- **Failure**: The second `execute_use_action()` call returns `None`, failing the assertion that the second potion use succeeds and consumes the final stack item.
- **Hypothesis**: Both potion uses occur without refreshing action economy, so the first use may exhaust the bonus action required by the second; further focused investigation is needed to distinguish a stale test setup from an item-use regression.
- **Status**: OPEN; documented only, no code or tests changed.

### Flame Strike applies its radiant component as fire damage
- **Found**: 2026-07-15 while adding execution-honest spell outcome contracts for subjective AI.
- **Source**: `dnd/spells/evocation.py:3701-3725` rolls separate fire and radiant components and preserves both in the completion log, but combines their totals and calls `receive_damage(..., DamageType.FIRE, ...)` once.
- **Impact**: Fire resistance, vulnerability, or immunity is applied to the radiant component as well, while the combat log and intended spell contract still describe two damage types. A truthful AI outcome profile cannot currently agree with both HP mutation and the emitted log.
- **Required correction**: Apply the two typed damage components independently while preserving save-for-half semantics and coherent aggregate logging, with focused resistance/immunity tests.
- **Status**: OPEN; audit entry only, no spell behavior changed.

### Chill Touch ignores modified spell critical thresholds
- **Found**: 2026-07-15 while adding execution-honest spell outcome contracts for subjective AI.
- **Source**: `dnd/spells/necromancy.py:300-306` calls `determine_attack_outcome(dice_roll, target_ac)` without the caster's spell critical threshold, unlike spell attacks that pass `caster.get_spell_crit_threshold()`.
- **Impact**: A caster whose spell critical threshold is lowered still crits with Chill Touch only on a natural 20. The new outcome profile deliberately uses threshold 20 to match current execution rather than advertising a rule the action does not implement.
- **Required correction**: Decide whether Chill Touch should follow the shared spell-attack critical contract, then change execution and its outcome profile together with a focused modified-threshold test.
- **Status**: OPEN; audit entry only, no spell behavior changed.

### Subjective observation stream test retains an unused encounter fixture
- **Found**: 2026-07-15 during a focused Pyright run for unrelated work.
- **Command**: `uv run pyright tests/manual/test_28_subjective_observation_stream.py`
- **Error**: Around line 1117, local variable `encounter` is assigned but never accessed (`reportUnusedVariable`).
- **Hypothesis**: This is a trivial stale test-fixture binding; remove the assignment or use the returned encounter if the test is intended to assert against it.
- **Status**: OPEN; test typing cleanup only, no runtime behavior is implicated and no code change was attempted.

### EB-12-018 expects the pre-cast level-3 spell-slot count
- **Found**: 2026-07-15 during focused sensory-indexing validation.
- **Test**: `tests/engine_book/test_chapter_12_senses_light_stealth.py::test_eb_12_018_aoe_preview_hides_hidden_entities_but_execution_hits_them` fails at approximately line 774.
- **Failure**: The test expects `spell_slot_3 == 2` after a level-5 caster successfully casts Fireball.
- **Reproduction**: The exact focused test reproduces the failure. `create_caster` initializes the level-5 character with `full_caster_spell_slots_for_level(5)`, which provides two level-3 slots. One valid Fireball cast correctly consumes one slot, leaving `spell_slot_3 == 1`.
- **Hypothesis**: The assertion is stale; the spell behavior and action cost are correct.
- **Status**: OPEN; documented only and not fixed during the sensory-indexing task.

### Seamless subjective-runtime test doubles do not match Starlette interfaces
- **Found**: 2026-07-15 during focused Pyright validation for unrelated subjective-runtime work.
- **Command**: `uv run pyright tests/manual/test_36_seamless_subjective_runtime.py`
- **Errors**: Pre-existing diagnostics around lines 187-272 report `_ConnectedRequest` as incompatible with the request accepted by `subscribe_ai_observation`, an `AsyncContentStream` test double without the required `aclose()` member, and access to `.headers` on a response inferred as `object`.
- **Hypothesis**: The test doubles and response annotations model only the runtime behavior used by the tests, but their declared types do not conform to the corresponding Starlette request, response, and async-stream interfaces.
- **Status**: OPEN; test-helper typing issue only, no production code or tests changed.

### Policy-host fixtures use a Pydantic flat constructor shape invisible to Pyright
- **Found**: 2026-07-15 during focused Pyright validation for unrelated policy investigation.
- **Command**: `uv run pyright ai/policy/routines.py tests/manual/test_48_policy_host.py`
- **Result**: `ai/policy/routines.py` reports no errors; `tests/manual/test_48_policy_host.py` reports 177 construction errors.
- **Representative errors**: At line 1519, Pyright reports that `ActionAffordance(...)` is missing required parameter `source`; lines 1521-1527 then report no parameters named `bucket`, `template_name`, `display_name`, `action_category`, `target_type`, `can_afford`, or `cost`. The same pattern recurs in later fixture constructors, including around lines 1646 and 1752.
- **Hypothesis**: `ActionAffordance` statically declares the canonical factored `source: ActionSourceDefinition` field, while its Pydantic `mode="before"` validator accepts and factors the legacy flat input shape at runtime. Pyright sees only the canonical constructor signature. Tests should use the factored constructor or a typed fixture/factory (or deliberately validate a mapping) rather than relying on runtime-only input normalization.
- **Status**: OPEN; test-construction/static-typing mismatch only, with no reported production error in `ai/policy/routines.py`.

### Ranged spell attacks did not receive Threatened disadvantage
- **Found**: 2026-07-16 during Rotation 13 in `standard_skeleton_doors`.
- **Observed behavior**: Validation Sorcerer at `(7, 12)` cast Scorching Ray against the adjacent Validation Skeleton Warrior at `(7, 11)`. All four spell-attack logs recorded `advantage_status=none`, `advantage_breakdown=[]`, and `is_threatened=false`.
- **Expected ruleset behavior**: In the chosen BG3/videogame ruleset, being Threatened imposes disadvantage on ranged attack rolls, including ranged spell attacks.
- **Evidence**: `ai/evidence/direct_codex_runs/20260716T150526_870617_0000-standard_skeleton_doors-direct-codex-bbfbd73d.json` retains the subjective run and engine-rule annotation.
- **Cause**: Spell subclasses rolled directly from `spell_attack_bonus()` and bypassed the shared ranged-attack consequence path. `SpellEvent` also lacked a field through which combat logs could retain the threat state.
- **Resolution**: `SpellAction.resolve_spell_attack()` now owns spell-attack propagation, ranged Threatened disadvantage, spell-specific advantage modifiers, d20 resolution, and typed result evidence. Every attack-roll spell uses it; actor-side outcome profiles apply the same rule; `SpellEvent` forwards `is_threatened` into `AttackLogData`.
- **Verification**: The adjacent-hostile regression passes, `tests/manual/test_14_spell_families.py` reports `14 passed`, `tests/engine_book/test_chapter_15_spell_families.py` reports `46 passed`, the existing weapon-threat contract passes, and touched production files report zero Pyright errors.
- **Status**: RESOLVED 2026-07-16.

### External self-play exact-policy assertion expects Hold Person
- **Found**: 2026-07-17 during focused arena-factory validation.
- **Command**: `uv run pytest tests/manual/test_39_ai_validation_harness.py -k external_selfplay_runs_sorcerer_barbarian_duel_through_epoch_commands`
- **Failure**: Self-play completed, but the test expected the second action `Hold Person__slot_2` and observed `Scorching Ray__slot_3`.
- **Hypothesis**: The exact-policy assertion is likely stale after policy evolution; this is unrelated to and not caused by the new arena-factory seam.
- **Status**: OPEN; documented only, no behavior changed.

### Policy host advances memory for an accepted but canceled action
- **Found**: 2026-07-18 during focused policy-host validation for unrelated work.
- **Command**: `uv run pytest tests/manual/test_48_policy_host.py -q`
- **Test**: `tests/manual/test_48_policy_host.py::test_policy_host_does_not_advance_memory_for_accepted_canceled_action`
- **Failure**: The test expected `memory_advanced is False`, but the policy host returned `True` for a command with an `ACCEPTED` acknowledgement and `ActionResolutionStatus.CANCELED` resolution.
- **Likely area**: Policy-host command-result correlation and memory advancement logic, specifically the branch that interprets transport acceptance independently from the action's terminal canceled resolution.
- **Status**: OPEN; documented only, no production code or tests changed.

### Spell Studio targeting smoke uses a stale numeric-input locator
- **Found**: 2026-07-20 while reproducing the existing NeuroClient smoke failure.
- **Command**: `npm run studio:targeting-smoke` from `/home/tommaso/Dev/NeuroClient/app`.
- **Observed output**: The process exited `1` after `8.19s` with `ok: false`, no `pageerror`, and correct target toggle/removal facts. The final fact reported `projectileSpeed: "18"` instead of the asserted `"220"`; the remaining console output was limited to Chromium WebGL `ReadPixels` performance warnings.
- **Hypothesis**: The harness's positional selector `input[type='number']:nth(1)` is stale and now selects the target-distance input, whose production control correctly clamps values to `18`, rather than the timeline's projectile-speed input. The elapsed time comes from navigation, studio readiness, fixed waits, screenshot capture, and browser teardown; no harness timeout fired.
- **Status**: OPEN; harness-only mismatch documented without changing NeuroClient production or test code.
