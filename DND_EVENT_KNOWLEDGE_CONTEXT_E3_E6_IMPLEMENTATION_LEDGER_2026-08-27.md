# Event knowledge-context E3–E6 implementation ledger

Date: 2026-08-27
Repository: `/mnt/c/users/tommaso/documents/dev/dnd_engine`
Scope: Slice 3.0 preflight only

## 1. Checkpoint status

`SLICE_3_0_PREFLIGHT_COMPLETE — READY_FOR_COORDINATOR_REVIEW`

No production or test file was edited in this checkpoint. The exact accepted
264-node command was recovered from the original E1/E2 turn
`01a044e0-6ea9-79d2-97ae-f461cbfacd12` and independently rerun by the
coordinator. The 264-node identity and result are recorded in Section 4.3;
the earlier 126-node subordinate evidence remains unchanged.

## 2. Authority and instruction verification

All raw-byte SHA-256 values below were verified with `sha256sum` before this
ledger was written.

| Artifact | SHA-256 | Result |
| --- | --- | --- |
| `DND_EVENT_KNOWLEDGE_CONTEXT_E3_E6_IMPLEMENTATION_PLAN_2026-08-27.md` | `aaf75e26e3b1e13419caf3d0b7e8346ad8a86531bc155b90f6d37767a8328c98` | exact accepted plan |
| `DND_EVENT_KNOWLEDGE_CONTEXT_REDUCTION_PLAN_2026-08-27.md` | `7856a537f0b75063fe5bcb012fd7d020b2f92a1e018c17d1ccf6b5e830605c21` | exact governing authority |
| `DND_EVENT_KNOWLEDGE_CONTEXT_IMPLEMENTATION_PLAN_2026-08-27.md` | `3f98f0b926fce8e9662c5718c01aa863734a563897bebe0b403173d8eba0a9ad` | exact governing E1/E2 plan |
| `DND_PYGAME_SCRIPTED_ENCOUNTER_MVP_IMPLEMENTATION_PLAN_2026-08-27.md` | `8e83dde4916ca3a6a4691bd9b25f720d3e381fe49e6458d4c0800007f9b390b9` | exact named broader authority; no implementation scope taken |
| `dnd/core/events/knowledge.py` | `dccc01145c03949cbd7d3a39fdf2a5cac28c7e2ae1b1b9b7e4e0d34c4662f373` | exact accepted E1/E2 byte |
| `dnd/blocks/sensory.py` | `d34977d94df4224b6e9708b7d92fc46453bb59df002f4eec9a1e010621f5d5ad` | exact accepted E1/E2 byte |
| `tests/engine/test_event_knowledge_context.py` | `5c2527859498edf08b13eba4940a77df533d69bc2f54ab1867d82a2f0a4d3ba1` | exact accepted E1/E2 byte |
| `tests/architecture/test_event_knowledge_context_architecture.py` | `f4f96e53cdbef505501887cbd786c1f1275fb1bd6a101e76e41f8a2addbbb3d3` | exact accepted E1/E2 byte |
| `agents.md` | `fcc5dd1e15bae2ff86a7203f42b0c55de4d51dd0d93bc3a3ae059b7e58ee39b1` | read completely; exact current byte |
| `HOW_TO_TEST.MD` | `96ba573eb50504f9e2c9c8676acc2f352ae198466d79f46e75c57d3f29995013` | read completely; 517 lines; exact current byte |

The accepted E3–E6 plan states that the combined proof cut is 264 passing
nodes and that the two E1/E2 feature/architecture files collect 21 nodes.
The exact command recovered from the original E1/E2 turn is recorded in
Section 4.3.

## 3. Dirty checkout frozen before this ledger

Exact `git status --short --untracked-files=all` before creating this file:

```text
 M dnd/blocks/sensory.py
?? DND_EVENT_KNOWLEDGE_CONTEXT_E3_E6_IMPLEMENTATION_PLAN_2026-08-27.md
?? DND_EVENT_KNOWLEDGE_CONTEXT_IMPLEMENTATION_PLAN_2026-08-27.md
?? DND_EVENT_KNOWLEDGE_CONTEXT_REDUCTION_PLAN_2026-08-27.md
?? DND_EVENT_REDUCTION_FIRST_PRINCIPLES_STUDY_2026-08-27.md
?? DND_PYGAME_FIRST_PRINCIPLES_CLIENT_STUDY_2026-08-27.md
?? DND_PYGAME_SCRIPTED_ENCOUNTER_MVP_IMPLEMENTATION_PLAN_2026-08-27.md
?? dnd/core/events/knowledge.py
?? tests/architecture/test_event_knowledge_context_architecture.py
?? tests/engine/test_event_knowledge_context.py
```

The modified/untracked E1/E2 paths above were pre-existing and their bytes
match the accepted hashes in Section 2. The only new worktree path created by
this task is this ledger. No unrelated dirty path was touched.

## 4. Baseline and collection evidence

### 4.1 Explicit E0 baseline

The practical E1/E2 plan names these four baseline modules:

| Path | Collected nodes |
| --- | ---: |
| `tests/engine/test_objective_state.py` | 2 |
| `tests/engine/test_event_wire_visibility_contract.py` | 4 |
| `tests/engine/test_direct_scenario_deployment.py` | 49 |
| `tests/engine/test_move_settlement.py` | 50 |
| **E0 baseline total** | **105** |

Normalized identity algorithm used for the measured collection: collect with
pytest, keep node-ID lines matching `^tests/.*::`, sort unique in bytewise
locale order, join with a terminal newline, and SHA-256 the resulting UTF-8
bytes. The E0-only normalized node-set SHA was
`bd90102c5d159d44201cb7896b219d2d0164fa9b4eef5ef7b3bc28b533dbb75c`.

### 4.2 Accepted E1/E2 focus

The exact focused paths named by the E3–E6 plan collected 21 nodes:

| Path | Collected nodes |
| --- | ---: |
| `tests/engine/test_event_knowledge_context.py` | 17 |
| `tests/architecture/test_event_knowledge_context_architecture.py` | 4 |
| **E1/E2 focus total** | **21** |

Its normalized node-set SHA under the same algorithm was
`f86cb8065426fb27084a9558b1f968c51a41682c7575fd8cc2d58aabff38d4d3`.

### 4.3 Accepted 264-node combined cut

The exact accepted selector command recovered from original E1/E2 turn
`01a044e0-6ea9-79d2-97ae-f461cbfacd12` was:

```text
.venv/bin/python -m pytest -q tests/engine/test_event_knowledge_context.py tests/engine/test_objective_state.py tests/engine/test_direct_scenario_deployment.py tests/engine/test_event_wire_visibility_contract.py tests/engine/test_move_settlement.py tests/engine/test_senses_light_stealth.py tests/engine/test_combat_actions.py tests/engine/test_action_cost_and_position_commit.py tests/architecture
```

The coordinator reran that exact command on the current checkout: `264 passed
in 136.74s`. Its exact collected set is 264 nodes. Under the frozen identity
algorithm in Section 4.1 (retain `^tests/.*::`, C-bytewise sort unique, join
with a terminal newline, SHA-256 the UTF-8 bytes), the normalized node-set
SHA-256 is
`13043bdba75fae26de00295ea681e809be2524b83252c683217ba972839269b0`.

This closes the selector-inventory blocker. The exact 264-node command is the
Slice 3.0 accepted combined cut and its status is green.

### 4.4 Combined executable subordinate preflight run

Command run (the four explicit E0 modules plus the accepted 21-node E1/E2
focus):

```text
timeout 180 .venv/bin/python -m pytest -q -p no:cacheprovider tests/engine/test_objective_state.py tests/engine/test_event_wire_visibility_contract.py tests/engine/test_direct_scenario_deployment.py tests/engine/test_move_settlement.py tests/engine/test_event_knowledge_context.py tests/architecture/test_event_knowledge_context_architecture.py
```

Result: `126 passed in 53.50s` (105 E0 baseline + 21 E1/E2 focus).

The combined 126-node normalized node-set SHA was
`d098f026dfab788949d4c438b5f33da031423cf2c4a9907797127d968da8cdac`.

No collection or test failure occurred in the measured 126-node preflight run;
it is retained as subordinate evidence alongside the accepted 264-node cut
above.

## 5. Public API inventory inspected

The following existing public boundaries were inspected read-only. No private
event storage or live-world lookup is proposed for the future fixture.

### Encounter construction, reset, and lifecycle

- `dnd/encounters/encounter.py:218-232` — `Encounter.get()`,
  `Encounter.get_active()`, and `Encounter.clear_registry()`.
- `dnd/encounters/encounter.py:252-283` — `Encounter.add_combatant(entity,
  controller, surprised=False)` is the direct ownership/roster registration
  boundary.
- `dnd/encounters/encounter.py:290-308` — `set_controller_for()` replaces a
  controller through the existing encounter API.
- `dnd/encounters/encounter.py:310-341` — `roll_initiative()` establishes
  initiative order from public combatant/entity state.
- `dnd/encounters/encounter.py:362-400` — `start_encounter()` activates the
  encounter, installs the existing combat-log callback, and starts the first
  round.
- `dnd/encounters/encounter.py:402-435` — `end_encounter(reason)` is the
  ordinary terminal completion boundary.
- `dnd/core/events/events_registry.py:2583-2620` — `EventQueue.reset()` is
  the existing event-generation reset boundary used by the test fixtures.

### Action discovery, execution, and controller boundary

- `dnd/actions/operations.py:66-100` — `setup_standard_actions(entity)`.
- `dnd/actions/operations.py:259-276` — `get_available_actions(entity)`.
- `dnd/actions/operations.py:381-410` — `execute_action(entity, template_name,
  target, prefer_safe=...)`.
- `dnd/actions/operations.py:494-535` — `execute_available_action(...)`.
- `dnd/actions/operations.py:537-592` — `execute_by_index(...)`.
- `dnd/actions/operations.py:594-618` — `register_spell(...)`.
- `dnd/encounters/controllers.py:149-183` — controller
  `get_next_action()` and `execute_next_action()`.
- `dnd/encounters/encounter.py:896-950` — `run_turn()` and
  `complete_current_turn()`.
- `dnd/encounters/encounter.py:969-1171` — the existing
  `advance_one_controller_boundary()` / `advance_one_controller_action_boundary()`
  public synchronous controller boundary and its external wait result.
- `dnd/encounters/encounter.py:1184-1216` — `Encounter.execute_action()`
  delegates to the existing indexed action execution path.

### Event cursor, phase storage, batches, and combat log

- `dnd/core/events/events_registry.py:1648-1710` — passive
  `add_on_event_batch_callback()`, `remove_on_event_batch_callback()`, and
  `batch_on_event_callbacks()`; the latter retains storage order across nested
  action/reaction work without a second queue.
- `dnd/core/events/events_registry.py:1725-1745` — public
  `event_cursor()`, `generation_id()`, and `iter_events_since(since)`.
- `dnd/core/events/events_registry.py:1825-1855` — `EventQueue.register()`
  stores concrete event versions and dispatches existing handlers.
- `dnd/core/events/events_registry.py:1916-1941` —
  `publish_declaration()`.
- `dnd/core/events/events_registry.py:2045-2067` — `publish_preflighted()`
  stores an already accepted event without running declaration validators a
  second time.
- `dnd/core/events/events_registry.py:2070-2087` — `publish_completed_fact()`.
- `dnd/core/events/events_registry.py:2090-2133` —
  `register_completion_sequence()` for existing simultaneous completion facts.
- `dnd/core/events/events_registry.py:1247-1253` —
  `set_combat_log_callback()`.
- `dnd/encounters/encounter.py:725-761` — the existing callback and
  `add_event_to_combat_log()` append boundary.
- `dnd/encounters/encounter.py:763-777` — `get_combat_log(since)` and
  `clear_combat_log()`.

### Existing tests inspected for required proof beats

- Movement-generated opportunity attack:
  `tests/engine/test_combat_actions.py::test_eb_10_005_opportunity_attack_uses_reaction_on_step_movement`
  (lines 601-621). It uses public `Move(...).apply()`, the existing reaction
  handler setup, deterministic dice, and public HP/reaction/event evidence.
- Legal caster action:
  `tests/engine/test_action_discovery.py::test_eb_09_009_registered_multi_entity_spell_discovers_and_executes`
  (lines 563-630). It uses public entity creation, `setup_standard_actions`,
  `register_spell`, `get_available_actions`, and action execution.
- Deterministic initiative/authored roster:
  `tests/engine/test_direct_scenario_deployment.py::test_fixed_opening_preserves_initiative_and_forces_the_authored_roster`
  (lines 122-143). It is the existing authored-roster/initiative
  characterization boundary.
- Ordinary encounter start/end and callbacks:
  `tests/engine/test_encounter_apis.py::test_eb_18_001_encounter_start_sets_active_state_callbacks_and_round`
  (lines 320-350) starts the encounter and exercises `end_encounter()`.
- Action/combat-log listener payload:
  `tests/engine/test_encounter_apis.py::test_eb_18_004_execute_action_captures_combat_log_and_listener_payload`
  (lines 514-545).
- Event phase/cursor and combat-log lifecycle:
  `tests/engine/test_event_lifecycle.py` nodes `test_eb_04_001` through
  `test_eb_04_013` characterize phased UUID/lineage storage, completion,
  child logs, cancellation, and append-stable cursors. The measured E0/E1/E2
  run includes no speculative fixture or new event path.

## 6. Proposed direct fixture roles and smallest public commands

These are proposed Slice 3.1 inputs only; no legality, outcome, or event
inventory is claimed in Slice 3.0.

| Stable role | Proposed existing public setup |
| --- | --- |
| `hero_frontline` | durable controlled martial `Entity`, standard actions, placed in authored direct battlefield data |
| `hero_caster` | controlled caster `Entity`, standard actions plus registered Magic Missile if public discovery confirms it is legal |
| `enemy_guard` | durable autonomous melee `Entity` with the existing opportunity-attack handler capability |
| `enemy_raider` | second autonomous `Entity` with a deterministic controller action boundary |

Smallest proposed command sequence, to be proved during Slice 3.1:

1. Reset the existing runtime through the established public/test reset seam
   and construct the direct authored battlefield.
2. Create the four entities and controllers, then call
   `Encounter.add_combatant()` for each and use the existing fixed-initiative
   setup contract before `Encounter.start_encounter()`.
3. At the controlled boundary, call `get_available_actions()` and execute a
   discovered movement target through `execute_available_action()`; allow the
   installed `enemy_guard` capability to generate any opportunity attack.
4. For `hero_frontline`, perform one fresh discovered weapon attack against
   an eligible `enemy_raider` target.
5. At a later controlled boundary, call `register_spell()`, rediscover the
   caster action, and execute only the legal target returned by the public
   discovery result.
6. Advance autonomous turns through the existing encounter controller
   boundary, use `complete_current_turn()` / `next_turn()` for controlled
   turn transitions, and call `check_deaths()` only through its existing
   encounter lifecycle when required.
7. Call `end_encounter()` explicitly after the script's ordinary beats and
   inspect `get_combat_log()` plus the closed `EventQueue` cursor range.

No proposed row stores an expected event, roll, damage, reaction, sensory
delta, presentation cue, or manually constructed outcome. The future fixture
will use real engine-generated events and live public action legality.

## 7. Exact future authorization envelope

This Slice 3.0 checkpoint does not edit these files. The E3–E6 plan's bounded
future production envelope is:

- existing `dnd/core/events/knowledge.py`;
- existing `dnd/blocks/sensory.py`;
- new `dnd/event_reduction.py`, only for the authorized composition root.

The bounded future test/record envelope is:

- existing `tests/engine/test_event_knowledge_context.py`;
- existing `tests/architecture/test_event_knowledge_context_architecture.py`;
- new `tests/engine/test_event_knowledge_scripted_encounter.py`;
- new `tests/engine/test_event_knowledge_async_boundary.py`;
- new `tests/architecture/test_event_reduction_architecture.py` only if the
  existing architecture file cannot state the composition-root gates;
- this one implementation ledger;
- one final manifest only at the later certification stage.

No E3/E4/E5/E6 file is authorized in this preflight. The pygame plan's future
`game/` package is explicitly excluded from this track and was not created.

## 8. Verification record and stop condition

Pre-ledger verification completed:

- authority hashes: exact, Section 2;
- complete `agents.md` and 517-line `HOW_TO_TEST.MD`: read;
- E0 baseline plus E1/E2 focus: `126 passed in 53.50s`;
- E0 collection: 105 nodes, normalized SHA recorded in Section 4.1;
- E1/E2 collection: 21 nodes, normalized SHA recorded in Section 4.2;
- combined subordinate collection: 126 nodes, normalized SHA recorded in
  Section 4.4;
- accepted combined collection: 264 nodes, normalized SHA recorded in
  Section 4.3;
- `git diff --check -- dnd/blocks/sensory.py`: exit 0; only the existing
  LF/CRLF normalization warning was emitted;
- no production/test byte changed during this checkpoint.

The accepted 264-node command/list/hash is now frozen in Section 4.3 and the
coordinator rerun is green. Slice 3.1 is not started; the next action remains
coordinator authorization after review of this ledger-only correction.


## 9. Slice 3.1 direct proving encounter — inventory frozen

Status: `SLICE_3_1_INVENTORY_FROZEN — READY_FOR_COORDINATOR_REVIEW`.

This checkpoint is bound to the accepted implementation authority
`DND_EVENT_KNOWLEDGE_CONTEXT_E3_E6_IMPLEMENTATION_PLAN_2026-08-27.md`,
SHA-256 `aaf75e26e3b1e13419caf3d0b7e8346ad8a86531bc155b90f6d37767a8328c98`,
and the accepted Slice 3.0 ledger SHA-256
`313980f2de58e653798e901d1fcfd038c0873d34b1f67beea3c8e349581995c1`.
Only the authorized test file and this existing ledger were changed for Slice 3.1;
no production file, governing plan, excluded path, or unrelated dirty path was
changed.

### Authorized file and node inventory

- New test: `tests/engine/test_event_knowledge_scripted_encounter.py`.
- Existing ledger: `DND_EVENT_KNOWLEDGE_CONTEXT_E3_E6_IMPLEMENTATION_LEDGER_2026-08-27.md`.
- New collecting node:
  `tests/engine/test_event_knowledge_scripted_encounter.py::test_direct_public_proving_encounter_freezes_the_real_event_inventory`.
- Final test-file SHA-256 from the inventory run: 237acb1b89a9e841216f971dcd3a5e3dc12d50ea21f14d67da67fccf19b7d612  tests/engine/test_event_knowledge_scripted_encounter.py.
- The accepted 264-node command remains the unchanged baseline:
  264 collected, normalized SHA-256
  `13043bdba75fae26de00295ea681e809be2524b83252c683217ba972839269b0`.
- The Slice 3.1 sorted unique union is the accepted 264 nodes plus the one node
  above: 265 nodes, normalized SHA-256
  `b3a6c990713aab169bb2b8b69463a817bc4351989af2583c47798ceb0f4f1f8c`.
  Normalization is the accepted algorithm: retain `^tests/.*::` lines, C-bytewise
  sort, unique, and append one terminal newline.

Exact new-node collection command/result:

```
.venv/bin/python -m pytest --collect-only -q -p no:cacheprovider tests/engine/test_event_knowledge_scripted_encounter.py
1 test collected in 4.08s
```

Exact accepted-baseline command/result:

```
.venv/bin/python -m pytest -q -p no:cacheprovider tests/engine/test_event_knowledge_context.py tests/engine/test_objective_state.py tests/engine/test_direct_scenario_deployment.py tests/engine/test_event_wire_visibility_contract.py tests/engine/test_move_settlement.py tests/engine/test_senses_light_stealth.py tests/engine/test_combat_actions.py tests/engine/test_action_cost_and_position_commit.py tests/architecture
264 passed in 146.86s
```

Exact final union command/result:

```
.venv/bin/python -m pytest -q -p no:cacheprovider tests/engine/test_event_knowledge_scripted_encounter.py tests/engine/test_event_knowledge_context.py tests/engine/test_objective_state.py tests/engine/test_direct_scenario_deployment.py tests/engine/test_event_wire_visibility_contract.py tests/engine/test_move_settlement.py tests/engine/test_senses_light_stealth.py tests/engine/test_combat_actions.py tests/engine/test_action_cost_and_position_commit.py tests/architecture
265 passed in 134.67s
```

The final single-node inventory run used the same current test bytes and emitted
`1 passed in 6.06s`. It captured the following complete public stream evidence. UUIDs
are run-instance values; the stable frozen inventory is the ordered
class/phase/type/index sequence.

```text
SLICE_3_1_BOUNDARY_RANGES
world_initialization [0,1)
create_and_deploy:hero_frontline [1,7)
create_and_deploy:hero_caster [7,14)
create_and_deploy:enemy_guard [14,22)
create_and_deploy:enemy_raider [22,31)
initiative_roll [31,31)
encounter_start [31,33)
hero_frontline_turn_start [33,37)
hero_frontline_move [37,85)
hero_frontline_weapon_attack [85,115)
hero_frontline_turn_end [115,119)
enemy_guard_action_boundary [119,153)
enemy_raider_action_boundary [153,191)
hero_caster_turn_start [191,199)
hero_caster_discovered_spell [199,237)
hero_caster_turn_end [237,243)
encounter_end [243,244)
SLICE_3_1_EVENT_COUNTS
dnd.actions.standard.AttackEvent completion attack = 3
dnd.actions.standard.AttackEvent declaration attack = 3
dnd.actions.standard.AttackEvent effect attack = 6
dnd.actions.standard.AttackEvent execution attack = 9
dnd.actions.standard.MovementEvent completion movement = 2
dnd.actions.standard.MovementEvent declaration movement = 2
dnd.actions.standard.MovementEvent effect movement = 2
dnd.actions.standard.MovementEvent execution movement = 2
dnd.actions.standard.SpellEvent completion cast_spell = 4
dnd.actions.standard.SpellEvent declaration cast_spell = 1
dnd.actions.standard.SpellEvent effect cast_spell = 1
dnd.actions.standard.SpellEvent execution cast_spell = 4
dnd.core.base_conditions.ConditionApplicationEvent completion condition_application = 7
dnd.core.base_conditions.ConditionApplicationEvent declaration condition_application = 7
dnd.core.base_conditions.ConditionApplicationEvent effect condition_application = 7
dnd.core.base_conditions.ConditionApplicationEvent execution condition_application = 7
dnd.core.base_conditions.ConditionRemovalEvent completion condition_removal = 3
dnd.core.base_conditions.ConditionRemovalEvent declaration condition_removal = 3
dnd.core.base_conditions.ConditionRemovalEvent effect condition_removal = 3
dnd.core.base_conditions.ConditionRemovalEvent execution condition_removal = 3
dnd.core.events.encounter_events.EncounterEndEvent completion encounter_end = 1
dnd.core.events.encounter_events.EncounterStartEvent completion encounter_start = 1
dnd.core.events.encounter_events.RoundEndEvent completion round_end = 1
dnd.core.events.encounter_events.RoundStartEvent completion round_start = 2
dnd.core.events.encounter_events.TurnEndEvent completion turn_end = 4
dnd.core.events.encounter_events.TurnEndEvent declaration turn_end = 4
dnd.core.events.encounter_events.TurnEndEvent effect turn_end = 4
dnd.core.events.encounter_events.TurnEndEvent execution turn_end = 4
dnd.core.events.encounter_events.TurnStartEvent completion turn_start = 4
dnd.core.events.encounter_events.TurnStartEvent declaration turn_start = 4
dnd.core.events.encounter_events.TurnStartEvent effect turn_start = 4
dnd.core.events.encounter_events.TurnStartEvent execution turn_start = 4
dnd.core.events.entity_events.EntityCreatedEvent completion entity_created = 4
dnd.core.events.resolution_events.AttackD20RollResultEvent completion attack_d20_roll = 3
dnd.core.events.resolution_events.AttackD20RollResultEvent declaration attack_d20_roll = 3
dnd.core.events.resolution_events.AttackD20RollResultEvent effect attack_d20_roll = 3
dnd.core.events.resolution_events.DamageAppliedEvent completion damage_applied = 6
dnd.core.events.resolution_events.DamageAppliedEvent declaration damage_applied = 6
dnd.core.events.resolution_events.DamageAppliedEvent effect damage_applied = 6
dnd.core.events.resolution_events.DamageAppliedEvent execution damage_applied = 6
dnd.core.events.resolution_events.DamageRollResultEvent completion damage_roll_result = 3
dnd.core.events.resolution_events.DamageRollResultEvent declaration damage_roll_result = 3
dnd.core.events.resolution_events.DamageRollResultEvent effect damage_roll_result = 3
dnd.core.events.resolution_events.TakeDamageEvent completion take_damage = 6
dnd.core.events.resolution_events.TakeDamageEvent declaration take_damage = 6
dnd.core.events.resolution_events.TakeDamageEvent effect take_damage = 6
dnd.core.events.resolution_events.TakeDamageEvent execution take_damage = 6
dnd.core.events.world_events.SensoryUpdateEvent completion sensory_update = 21
dnd.core.events.world_events.SpatialChangeEvent completion spatial_entity_entered = 6
dnd.core.events.world_events.SpatialChangeEvent completion spatial_entity_left = 2
dnd.core.events.world_events.SpatialChangeEvent declaration spatial_entity_entered = 6
dnd.core.events.world_events.SpatialChangeEvent declaration spatial_entity_left = 2
dnd.core.events.world_events.SpatialChangeEvent effect spatial_entity_entered = 6
dnd.core.events.world_events.SpatialChangeEvent effect spatial_entity_left = 2
dnd.core.events.world_events.SpatialChangeEvent execution spatial_entity_entered = 6
dnd.core.events.world_events.SpatialChangeEvent execution spatial_entity_left = 2
dnd.core.events.world_events.StepMovementEvent completion step_movement = 2
dnd.core.events.world_events.StepMovementEvent effect step_movement = 2
dnd.core.events.world_events.WorldInitializedEvent completion world_initialized = 1
SLICE_3_1_PARENT_EDGE_COUNT 148
SLICE_3_1_PARENT_EDGES [(5, 4), (11, 10), (12, 10), (18, 17), (19, 17), (20, 17), (26, 25), (27, 25), (28, 25), (29, 25), (40, 39), (41, 40), (42, 40), (43, 42), (44, 42), (45, 42), (46, 42), (47, 40), (48, 47), (49, 47), (50, 47), (51, 40), (52, 40), (53, 52), (54, 52), (55, 52), (56, 52), (57, 52), (58, 52), (59, 58), (60, 58), (61, 58), (62, 61), (63, 61), (64, 61), (65, 64), (66, 61), (67, 58), (68, 52), (69, 40), (70, 40), (71, 40), (72, 40), (73, 40), (74, 40), (75, 40), (76, 40), (77, 40), (78, 77), (79, 77), (80, 77), (81, 77), (82, 40), (83, 39), (87, 86), (88, 86), (89, 86), (90, 89), (91, 86), (93, 92), (94, 92), (95, 92), (98, 97), (99, 97), (100, 97), (101, 97), (102, 97), (103, 97), (104, 103), (105, 103), (106, 103), (107, 106), (108, 106), (109, 106), (110, 106), (111, 103), (112, 97), (134, 133), (135, 134), (136, 134), (137, 134), (138, 134), (139, 134), (140, 134), (141, 134), (142, 141), (143, 141), (144, 141), (145, 141), (146, 134), (147, 133), (159, 158), (160, 158), (161, 158), (162, 161), (163, 158), (165, 164), (166, 164), (167, 164), (170, 169), (171, 169), (172, 169), (173, 169), (174, 169), (175, 169), (176, 175), (177, 175), (178, 175), (179, 178), (180, 178), (181, 178), (182, 178), (183, 175), (184, 169), (201, 200), (202, 200), (203, 200), (204, 201), (205, 201), (206, 201), (207, 204), (208, 204), (209, 204), (210, 207), (211, 207), (212, 207), (213, 207), (214, 204), (215, 201), (216, 200), (217, 215), (218, 215), (219, 215), (220, 218), (221, 218), (222, 218), (223, 218), (224, 215), (225, 200), (226, 225), (227, 225), (228, 225), (229, 228), (230, 228), (231, 228), (232, 228), (233, 225), (234, 200)]
SLICE_3_1_SENSORY_CAUSALITY_COUNT 21
SLICE_3_1_SENSORY_BEFORE_CAUSATIVE_COMPLETION 21
SLICE_3_1_ENCOUNTER_UUID 9c4ff160-a213-4123-83ec-25ce1a8e239e
SLICE_3_1_COMBAT_LOG_RANGES [('initiative_roll', 0, 0), ('encounter_start', 0, 0), ('hero_frontline_turn_start', 0, 1), ('hero_frontline_move', 1, 2), ('hero_frontline_weapon_attack', 2, 3), ('hero_frontline_turn_end', 3, 4), ('enemy_guard_action_boundary', 4, 7), ('enemy_raider_action_boundary', 7, 10), ('hero_caster_turn_start', 10, 11), ('hero_caster_discovered_spell', 11, 12), ('hero_caster_turn_end', 12, 13), ('encounter_end', 13, 13)]
SLICE_3_1_COMBAT_LOG_LINKS [(0, 36, '0205f3b0-6e27-4747-a7de-e5e1a747ab4a', '31bb9cf5-1d79-45a6-8a55-af97fda0b6cd', 'dnd.core.events.encounter_events.TurnStartEvent', 'turn_start', ('turn_start', ())), (1, 84, '734f9a30-0a79-47f9-aa82-a974609f1099', 'ed82fae4-8f03-4f11-96d3-cd2c3122397a', 'dnd.actions.standard.MovementEvent', 'movement', ('movement', (('movement', (('attack', (('damage_taken', ()),)),)),))), (2, 114, '4134b938-4700-4557-bc56-d80aff1f3e23', 'fcb978e1-334d-4a8b-b480-81eae5a3e083', 'dnd.actions.standard.AttackEvent', 'attack', ('attack', (('damage_taken', ()),))), (3, 118, '314ae66f-2013-4e92-93d7-9e19bc39df6d', '8a7f214c-6ca5-4ddb-b22a-c1a091074ab0', 'dnd.core.events.encounter_events.TurnEndEvent', 'turn_end', ('turn_end', ())), (4, 130, '230092e0-dbee-44b3-8b12-5d3e8839cb2e', '7303ef49-b6a4-4e5e-974d-3fc284aabdb2', 'dnd.core.events.encounter_events.TurnStartEvent', 'turn_start', ('turn_start', ())), (5, 148, 'f602d0af-ee8f-46c9-bd8f-7b42fa8f425d', 'bed498f8-5740-4a8a-b901-41a68ba05251', 'dnd.actions.standard.MovementEvent', 'movement', ('movement', (('movement', ()),))), (6, 152, '0c405409-385b-4b15-ae04-124c3eceeb7c', 'c5fbff2c-0772-4de1-b510-41508ab26723', 'dnd.core.events.encounter_events.TurnEndEvent', 'turn_end', ('turn_end', ())), (7, 156, '232cc988-162e-4602-a5ff-90b5bc7e5a56', '6c07a1df-adf8-43e7-8fdc-f807fa8230e7', 'dnd.core.events.encounter_events.TurnStartEvent', 'turn_start', ('turn_start', ())), (8, 186, '89227e5c-90cf-47d5-b5ee-6fc8450f7810', '98796a14-2a76-4ab6-bf36-0f1aef82906b', 'dnd.actions.standard.AttackEvent', 'attack', ('attack', (('damage_taken', ()),))), (9, 190, 'afa87edb-a418-4909-a42c-8518ff4ebfca', '8415252a-6d13-45ec-a3e6-0917f14f37f7', 'dnd.core.events.encounter_events.TurnEndEvent', 'turn_end', ('turn_end', ())), (10, 198, '5d9812df-baa1-456e-af7d-48a826ddbfa3', 'f67a002d-e0f6-4418-b9a6-d480b7877997', 'dnd.core.events.encounter_events.TurnStartEvent', 'turn_start', ('turn_start', ())), (11, 236, '8eea92b7-cd26-48d0-a7dc-4d5d5b434986', '955a2df8-b88c-42e1-af7a-2cf01df0adb2', 'dnd.actions.standard.SpellEvent', 'multi_entity_action', ('multi_entity_action', (('spell_damage', (('damage_taken', ()),)), ('spell_damage', (('damage_taken', ()),)), ('spell_damage', (('damage_taken', ()),))))), (12, 240, '7572e1f2-98d6-4362-83f2-13b5702eabb7', '15023e38-992e-4d56-b771-2635a13579cf', 'dnd.core.events.encounter_events.TurnEndEvent', 'turn_end', ('turn_end', ()))]
SLICE_3_1_EVENT_INVENTORY
000 dnd.core.events.world_events.WorldInitializedEvent completion world_initialized
001 dnd.core.events.entity_events.EntityCreatedEvent completion entity_created
002 dnd.core.events.world_events.SpatialChangeEvent declaration spatial_entity_entered
003 dnd.core.events.world_events.SpatialChangeEvent execution spatial_entity_entered
004 dnd.core.events.world_events.SpatialChangeEvent effect spatial_entity_entered
005 dnd.core.events.world_events.SensoryUpdateEvent completion sensory_update
006 dnd.core.events.world_events.SpatialChangeEvent completion spatial_entity_entered
007 dnd.core.events.entity_events.EntityCreatedEvent completion entity_created
008 dnd.core.events.world_events.SpatialChangeEvent declaration spatial_entity_entered
009 dnd.core.events.world_events.SpatialChangeEvent execution spatial_entity_entered
010 dnd.core.events.world_events.SpatialChangeEvent effect spatial_entity_entered
011 dnd.core.events.world_events.SensoryUpdateEvent completion sensory_update
012 dnd.core.events.world_events.SensoryUpdateEvent completion sensory_update
013 dnd.core.events.world_events.SpatialChangeEvent completion spatial_entity_entered
014 dnd.core.events.entity_events.EntityCreatedEvent completion entity_created
015 dnd.core.events.world_events.SpatialChangeEvent declaration spatial_entity_entered
016 dnd.core.events.world_events.SpatialChangeEvent execution spatial_entity_entered
017 dnd.core.events.world_events.SpatialChangeEvent effect spatial_entity_entered
018 dnd.core.events.world_events.SensoryUpdateEvent completion sensory_update
019 dnd.core.events.world_events.SensoryUpdateEvent completion sensory_update
020 dnd.core.events.world_events.SensoryUpdateEvent completion sensory_update
021 dnd.core.events.world_events.SpatialChangeEvent completion spatial_entity_entered
022 dnd.core.events.entity_events.EntityCreatedEvent completion entity_created
023 dnd.core.events.world_events.SpatialChangeEvent declaration spatial_entity_entered
024 dnd.core.events.world_events.SpatialChangeEvent execution spatial_entity_entered
025 dnd.core.events.world_events.SpatialChangeEvent effect spatial_entity_entered
026 dnd.core.events.world_events.SensoryUpdateEvent completion sensory_update
027 dnd.core.events.world_events.SensoryUpdateEvent completion sensory_update
028 dnd.core.events.world_events.SensoryUpdateEvent completion sensory_update
029 dnd.core.events.world_events.SensoryUpdateEvent completion sensory_update
030 dnd.core.events.world_events.SpatialChangeEvent completion spatial_entity_entered
031 dnd.core.events.encounter_events.EncounterStartEvent completion encounter_start
032 dnd.core.events.encounter_events.RoundStartEvent completion round_start
033 dnd.core.events.encounter_events.TurnStartEvent declaration turn_start
034 dnd.core.events.encounter_events.TurnStartEvent execution turn_start
035 dnd.core.events.encounter_events.TurnStartEvent effect turn_start
036 dnd.core.events.encounter_events.TurnStartEvent completion turn_start
037 dnd.actions.standard.MovementEvent declaration movement
038 dnd.actions.standard.MovementEvent execution movement
039 dnd.actions.standard.MovementEvent effect movement
040 dnd.core.events.world_events.StepMovementEvent effect step_movement
041 dnd.actions.standard.AttackEvent declaration attack
042 dnd.actions.standard.AttackEvent execution attack
043 dnd.core.base_conditions.ConditionApplicationEvent declaration condition_application
044 dnd.core.base_conditions.ConditionApplicationEvent execution condition_application
045 dnd.core.base_conditions.ConditionApplicationEvent effect condition_application
046 dnd.core.base_conditions.ConditionApplicationEvent completion condition_application
047 dnd.actions.standard.AttackEvent execution attack
048 dnd.core.events.resolution_events.AttackD20RollResultEvent declaration attack_d20_roll
049 dnd.core.events.resolution_events.AttackD20RollResultEvent effect attack_d20_roll
050 dnd.core.events.resolution_events.AttackD20RollResultEvent completion attack_d20_roll
051 dnd.actions.standard.AttackEvent execution attack
052 dnd.actions.standard.AttackEvent effect attack
053 dnd.core.events.resolution_events.DamageRollResultEvent declaration damage_roll_result
054 dnd.core.events.resolution_events.DamageRollResultEvent effect damage_roll_result
055 dnd.core.events.resolution_events.DamageRollResultEvent completion damage_roll_result
056 dnd.core.events.resolution_events.TakeDamageEvent declaration take_damage
057 dnd.core.events.resolution_events.TakeDamageEvent execution take_damage
058 dnd.core.events.resolution_events.TakeDamageEvent effect take_damage
059 dnd.core.events.resolution_events.DamageAppliedEvent declaration damage_applied
060 dnd.core.events.resolution_events.DamageAppliedEvent execution damage_applied
061 dnd.core.events.resolution_events.DamageAppliedEvent effect damage_applied
062 dnd.core.base_conditions.ConditionApplicationEvent declaration condition_application
063 dnd.core.base_conditions.ConditionApplicationEvent execution condition_application
064 dnd.core.base_conditions.ConditionApplicationEvent effect condition_application
065 dnd.core.events.world_events.SensoryUpdateEvent completion sensory_update
066 dnd.core.base_conditions.ConditionApplicationEvent completion condition_application
067 dnd.core.events.resolution_events.DamageAppliedEvent completion damage_applied
068 dnd.core.events.resolution_events.TakeDamageEvent completion take_damage
069 dnd.actions.standard.AttackEvent effect attack
070 dnd.actions.standard.AttackEvent completion attack
071 dnd.core.events.world_events.SpatialChangeEvent declaration spatial_entity_left
072 dnd.core.events.world_events.SpatialChangeEvent execution spatial_entity_left
073 dnd.core.events.world_events.SpatialChangeEvent effect spatial_entity_left
074 dnd.core.events.world_events.SpatialChangeEvent completion spatial_entity_left
075 dnd.core.events.world_events.SpatialChangeEvent declaration spatial_entity_entered
076 dnd.core.events.world_events.SpatialChangeEvent execution spatial_entity_entered
077 dnd.core.events.world_events.SpatialChangeEvent effect spatial_entity_entered
078 dnd.core.events.world_events.SensoryUpdateEvent completion sensory_update
079 dnd.core.events.world_events.SensoryUpdateEvent completion sensory_update
080 dnd.core.events.world_events.SensoryUpdateEvent completion sensory_update
081 dnd.core.events.world_events.SensoryUpdateEvent completion sensory_update
082 dnd.core.events.world_events.SpatialChangeEvent completion spatial_entity_entered
083 dnd.core.events.world_events.StepMovementEvent completion step_movement
084 dnd.actions.standard.MovementEvent completion movement
085 dnd.actions.standard.AttackEvent declaration attack
086 dnd.actions.standard.AttackEvent execution attack
087 dnd.core.base_conditions.ConditionApplicationEvent declaration condition_application
088 dnd.core.base_conditions.ConditionApplicationEvent execution condition_application
089 dnd.core.base_conditions.ConditionApplicationEvent effect condition_application
090 dnd.core.events.world_events.SensoryUpdateEvent completion sensory_update
091 dnd.core.base_conditions.ConditionApplicationEvent completion condition_application
092 dnd.actions.standard.AttackEvent execution attack
093 dnd.core.events.resolution_events.AttackD20RollResultEvent declaration attack_d20_roll
094 dnd.core.events.resolution_events.AttackD20RollResultEvent effect attack_d20_roll
095 dnd.core.events.resolution_events.AttackD20RollResultEvent completion attack_d20_roll
096 dnd.actions.standard.AttackEvent execution attack
097 dnd.actions.standard.AttackEvent effect attack
098 dnd.core.events.resolution_events.DamageRollResultEvent declaration damage_roll_result
099 dnd.core.events.resolution_events.DamageRollResultEvent effect damage_roll_result
100 dnd.core.events.resolution_events.DamageRollResultEvent completion damage_roll_result
101 dnd.core.events.resolution_events.TakeDamageEvent declaration take_damage
102 dnd.core.events.resolution_events.TakeDamageEvent execution take_damage
103 dnd.core.events.resolution_events.TakeDamageEvent effect take_damage
104 dnd.core.events.resolution_events.DamageAppliedEvent declaration damage_applied
105 dnd.core.events.resolution_events.DamageAppliedEvent execution damage_applied
106 dnd.core.events.resolution_events.DamageAppliedEvent effect damage_applied
107 dnd.core.base_conditions.ConditionApplicationEvent declaration condition_application
108 dnd.core.base_conditions.ConditionApplicationEvent execution condition_application
109 dnd.core.base_conditions.ConditionApplicationEvent effect condition_application
110 dnd.core.base_conditions.ConditionApplicationEvent completion condition_application
111 dnd.core.events.resolution_events.DamageAppliedEvent completion damage_applied
112 dnd.core.events.resolution_events.TakeDamageEvent completion take_damage
113 dnd.actions.standard.AttackEvent effect attack
114 dnd.actions.standard.AttackEvent completion attack
115 dnd.core.events.encounter_events.TurnEndEvent declaration turn_end
116 dnd.core.events.encounter_events.TurnEndEvent execution turn_end
117 dnd.core.events.encounter_events.TurnEndEvent effect turn_end
118 dnd.core.events.encounter_events.TurnEndEvent completion turn_end
119 dnd.core.events.encounter_events.TurnStartEvent declaration turn_start
120 dnd.core.events.encounter_events.TurnStartEvent execution turn_start
121 dnd.core.base_conditions.ConditionRemovalEvent declaration condition_removal
122 dnd.core.base_conditions.ConditionRemovalEvent execution condition_removal
123 dnd.core.base_conditions.ConditionRemovalEvent effect condition_removal
124 dnd.core.base_conditions.ConditionRemovalEvent completion condition_removal
125 dnd.core.base_conditions.ConditionRemovalEvent declaration condition_removal
126 dnd.core.base_conditions.ConditionRemovalEvent execution condition_removal
127 dnd.core.base_conditions.ConditionRemovalEvent effect condition_removal
128 dnd.core.base_conditions.ConditionRemovalEvent completion condition_removal
129 dnd.core.events.encounter_events.TurnStartEvent effect turn_start
130 dnd.core.events.encounter_events.TurnStartEvent completion turn_start
131 dnd.actions.standard.MovementEvent declaration movement
132 dnd.actions.standard.MovementEvent execution movement
133 dnd.actions.standard.MovementEvent effect movement
134 dnd.core.events.world_events.StepMovementEvent effect step_movement
135 dnd.core.events.world_events.SpatialChangeEvent declaration spatial_entity_left
136 dnd.core.events.world_events.SpatialChangeEvent execution spatial_entity_left
137 dnd.core.events.world_events.SpatialChangeEvent effect spatial_entity_left
138 dnd.core.events.world_events.SpatialChangeEvent completion spatial_entity_left
139 dnd.core.events.world_events.SpatialChangeEvent declaration spatial_entity_entered
140 dnd.core.events.world_events.SpatialChangeEvent execution spatial_entity_entered
141 dnd.core.events.world_events.SpatialChangeEvent effect spatial_entity_entered
142 dnd.core.events.world_events.SensoryUpdateEvent completion sensory_update
143 dnd.core.events.world_events.SensoryUpdateEvent completion sensory_update
144 dnd.core.events.world_events.SensoryUpdateEvent completion sensory_update
145 dnd.core.events.world_events.SensoryUpdateEvent completion sensory_update
146 dnd.core.events.world_events.SpatialChangeEvent completion spatial_entity_entered
147 dnd.core.events.world_events.StepMovementEvent completion step_movement
148 dnd.actions.standard.MovementEvent completion movement
149 dnd.core.events.encounter_events.TurnEndEvent declaration turn_end
150 dnd.core.events.encounter_events.TurnEndEvent execution turn_end
151 dnd.core.events.encounter_events.TurnEndEvent effect turn_end
152 dnd.core.events.encounter_events.TurnEndEvent completion turn_end
153 dnd.core.events.encounter_events.TurnStartEvent declaration turn_start
154 dnd.core.events.encounter_events.TurnStartEvent execution turn_start
155 dnd.core.events.encounter_events.TurnStartEvent effect turn_start
156 dnd.core.events.encounter_events.TurnStartEvent completion turn_start
157 dnd.actions.standard.AttackEvent declaration attack
158 dnd.actions.standard.AttackEvent execution attack
159 dnd.core.base_conditions.ConditionApplicationEvent declaration condition_application
160 dnd.core.base_conditions.ConditionApplicationEvent execution condition_application
161 dnd.core.base_conditions.ConditionApplicationEvent effect condition_application
162 dnd.core.events.world_events.SensoryUpdateEvent completion sensory_update
163 dnd.core.base_conditions.ConditionApplicationEvent completion condition_application
164 dnd.actions.standard.AttackEvent execution attack
165 dnd.core.events.resolution_events.AttackD20RollResultEvent declaration attack_d20_roll
166 dnd.core.events.resolution_events.AttackD20RollResultEvent effect attack_d20_roll
167 dnd.core.events.resolution_events.AttackD20RollResultEvent completion attack_d20_roll
168 dnd.actions.standard.AttackEvent execution attack
169 dnd.actions.standard.AttackEvent effect attack
170 dnd.core.events.resolution_events.DamageRollResultEvent declaration damage_roll_result
171 dnd.core.events.resolution_events.DamageRollResultEvent effect damage_roll_result
172 dnd.core.events.resolution_events.DamageRollResultEvent completion damage_roll_result
173 dnd.core.events.resolution_events.TakeDamageEvent declaration take_damage
174 dnd.core.events.resolution_events.TakeDamageEvent execution take_damage
175 dnd.core.events.resolution_events.TakeDamageEvent effect take_damage
176 dnd.core.events.resolution_events.DamageAppliedEvent declaration damage_applied
177 dnd.core.events.resolution_events.DamageAppliedEvent execution damage_applied
178 dnd.core.events.resolution_events.DamageAppliedEvent effect damage_applied
179 dnd.core.base_conditions.ConditionApplicationEvent declaration condition_application
180 dnd.core.base_conditions.ConditionApplicationEvent execution condition_application
181 dnd.core.base_conditions.ConditionApplicationEvent effect condition_application
182 dnd.core.base_conditions.ConditionApplicationEvent completion condition_application
183 dnd.core.events.resolution_events.DamageAppliedEvent completion damage_applied
184 dnd.core.events.resolution_events.TakeDamageEvent completion take_damage
185 dnd.actions.standard.AttackEvent effect attack
186 dnd.actions.standard.AttackEvent completion attack
187 dnd.core.events.encounter_events.TurnEndEvent declaration turn_end
188 dnd.core.events.encounter_events.TurnEndEvent execution turn_end
189 dnd.core.events.encounter_events.TurnEndEvent effect turn_end
190 dnd.core.events.encounter_events.TurnEndEvent completion turn_end
191 dnd.core.events.encounter_events.TurnStartEvent declaration turn_start
192 dnd.core.events.encounter_events.TurnStartEvent execution turn_start
193 dnd.core.base_conditions.ConditionRemovalEvent declaration condition_removal
194 dnd.core.base_conditions.ConditionRemovalEvent execution condition_removal
195 dnd.core.base_conditions.ConditionRemovalEvent effect condition_removal
196 dnd.core.base_conditions.ConditionRemovalEvent completion condition_removal
197 dnd.core.events.encounter_events.TurnStartEvent effect turn_start
198 dnd.core.events.encounter_events.TurnStartEvent completion turn_start
199 dnd.actions.standard.SpellEvent declaration cast_spell
200 dnd.actions.standard.SpellEvent execution cast_spell
201 dnd.actions.standard.SpellEvent execution cast_spell
202 dnd.actions.standard.SpellEvent execution cast_spell
203 dnd.actions.standard.SpellEvent execution cast_spell
204 dnd.core.events.resolution_events.TakeDamageEvent declaration take_damage
205 dnd.core.events.resolution_events.TakeDamageEvent execution take_damage
206 dnd.core.events.resolution_events.TakeDamageEvent effect take_damage
207 dnd.core.events.resolution_events.DamageAppliedEvent declaration damage_applied
208 dnd.core.events.resolution_events.DamageAppliedEvent execution damage_applied
209 dnd.core.events.resolution_events.DamageAppliedEvent effect damage_applied
210 dnd.core.base_conditions.ConditionApplicationEvent declaration condition_application
211 dnd.core.base_conditions.ConditionApplicationEvent execution condition_application
212 dnd.core.base_conditions.ConditionApplicationEvent effect condition_application
213 dnd.core.base_conditions.ConditionApplicationEvent completion condition_application
214 dnd.core.events.resolution_events.DamageAppliedEvent completion damage_applied
215 dnd.core.events.resolution_events.TakeDamageEvent completion take_damage
216 dnd.actions.standard.SpellEvent completion cast_spell
217 dnd.core.events.resolution_events.TakeDamageEvent declaration take_damage
218 dnd.core.events.resolution_events.TakeDamageEvent execution take_damage
219 dnd.core.events.resolution_events.TakeDamageEvent effect take_damage
220 dnd.core.events.resolution_events.DamageAppliedEvent declaration damage_applied
221 dnd.core.events.resolution_events.DamageAppliedEvent execution damage_applied
222 dnd.core.events.resolution_events.DamageAppliedEvent effect damage_applied
223 dnd.core.events.resolution_events.DamageAppliedEvent completion damage_applied
224 dnd.core.events.resolution_events.TakeDamageEvent completion take_damage
225 dnd.actions.standard.SpellEvent completion cast_spell
226 dnd.core.events.resolution_events.TakeDamageEvent declaration take_damage
227 dnd.core.events.resolution_events.TakeDamageEvent execution take_damage
228 dnd.core.events.resolution_events.TakeDamageEvent effect take_damage
229 dnd.core.events.resolution_events.DamageAppliedEvent declaration damage_applied
230 dnd.core.events.resolution_events.DamageAppliedEvent execution damage_applied
231 dnd.core.events.resolution_events.DamageAppliedEvent effect damage_applied
232 dnd.core.events.resolution_events.DamageAppliedEvent completion damage_applied
233 dnd.core.events.resolution_events.TakeDamageEvent completion take_damage
234 dnd.actions.standard.SpellEvent completion cast_spell
235 dnd.actions.standard.SpellEvent effect cast_spell
236 dnd.actions.standard.SpellEvent completion cast_spell
237 dnd.core.events.encounter_events.TurnEndEvent declaration turn_end
238 dnd.core.events.encounter_events.TurnEndEvent execution turn_end
239 dnd.core.events.encounter_events.TurnEndEvent effect turn_end
240 dnd.core.events.encounter_events.TurnEndEvent completion turn_end
241 dnd.core.events.encounter_events.RoundEndEvent completion round_end
242 dnd.core.events.encounter_events.RoundStartEvent completion round_start
243 dnd.core.events.encounter_events.EncounterEndEvent completion encounter_end
SLICE_3_1_COMBAT_LOGS 13
```

### Public proving behavior and inventory interpretation

The direct fixture uses the existing public `reset_engine_runtime()`,
`build_battlefield("battlefield.open_floor_bright")`, `Game.deploy_entity`,
`add_opportunity_attack_handler`, `Encounter.add_combatant`,
`Encounter.roll_initiative`, `Encounter.start_encounter`,
`Encounter.advance_one_controller_action_boundary`,
`Encounter.execute_action`, `Encounter.complete_current_turn`, and
`Encounter.end_encounter`. The four stable roles are
`hero_frontline`, `hero_caster`, `enemy_guard`, and `enemy_raider`.
Intentions contain only the role/action-template/target and turn-end choice;
the test does not store or manufacture events, rolls, damage, sensory deltas,
presentation cues, or expected outcomes. `fixed_dice_faces` makes the
otherwise ordinary resolver reproducible.

The captured ranges prove:

- cold reset/world initialization: `[0,1)`;
- four ordinary create/deploy ranges: `[1,7)`, `[7,14)`, `[14,22)`,
  `[22,31)`;
- deterministic initiative call: `[31,31)` (no event was emitted);
- encounter/round start: `[31,33)`;
- controlled frontline turn start: `[33,37)`;
- frontline move: `[37,85)`, including an engine-generated guard
  Opportunity Attack;
- discovered frontline weapon attack: `[85,115)`;
- frontline turn completion: `[115,119)`;
- first autonomous enemy boundary (guard movement): `[119,153)`;
- immediately consecutive second autonomous enemy boundary (raider attack):
  `[153,191)`, with no presentation acknowledgement between calls;
- controlled caster turn start: `[191,199)`;
- discovered legal caster spell: `[199,237)`;
- caster turn completion: `[237,243)`;
- ordinary explicit `Encounter.end_encounter(...)`: `[243,244)`.

The public assertions confirm the generated Opportunity Attack, the discovered
weapon attack, guard movement, raider attack, legal `Magic Missile__slot_1`
cast, distinct controlled turns, terminal encounter state, 244 stored event
versions, and 13 linked encounter combat-log entries. The selected spell
creates no persistent spatial effect in this stream.

The parent/lineage scan resolved every parent UUID through public
`EventQueue.get_event_by_uuid` and recorded 148 parent edges; every resolved
child retained the expected lineage relationship. All 21 public
`SensoryUpdateEvent` instances resolved their causal event and completion
through public queue history, and all 21 occurred before the causative
completion. The captured combat-log rows give the exact encounter UUID,
log-index/source-index pairs, source event UUID and lineage, concrete terminal
event class, entry kind, and recursive public `sub_entries` tree shape. The
combat-log range rows show length before/after every recorded encounter
boundary (0 through 13), every appended entry is linked to a terminal real
event, and no standalone entry lacks a linked source.

### Requested event paths, cold-read status, and missing facts

| Requested path | Concrete public path observed in this stream | Reviewed cold-read status |
|---|---|---|
| bootstrap | `WorldInitializedEvent`, `EntityCreatedEvent` | emitted; existing E1/E2 queue path reviewed |
| scene state | `SpatialChangeEvent`, `SensoryUpdateEvent` | emitted; existing E1/E2 queue path reviewed |
| movement | `MovementEvent`, `StepMovementEvent` | emitted; existing E1/E2 queue path reviewed |
| attack | `AttackEvent`, `AttackD20RollResultEvent` | emitted; existing E1/E2 queue path reviewed |
| damage | `DamageRollResultEvent`, `TakeDamageEvent`, `DamageAppliedEvent` | emitted; existing E1/E2 queue path reviewed |
| life | no life-state event emitted by this fixture | not a reviewed cold read; missing from this stream |
| condition | `ConditionApplicationEvent`, `ConditionRemovalEvent` | emitted; existing queue path reviewed |
| equipment | no separate equipment/item event emitted | not a reviewed cold read; missing from this stream |
| turn | `EncounterStartEvent`, `RoundStartEvent`, `RoundEndEvent`, `TurnStartEvent`, `TurnEndEvent`, `EncounterEndEvent` | emitted; existing queue path reviewed |
| text | no text event emitted | not a reviewed cold read; missing from this stream |
| fallback presentation | no presentation acknowledgement/fallback event path is exercised | not a reviewed cold read; reserved for later slice |

Exact missing facts are therefore: no life-state event, no separate equipment/item
event, no text event, and no fallback-presentation/cold-read result. The
zero-event initiative call is also recorded rather than synthesized. No missing
fact was backfilled with an invented event or outcome. The 3.1 fixture does not
claim the asynchronous presentation boundary or any E3–E6 knowledge policy.

### Validation and dirty-scope result

- New test collection: 1 collected.
- New test direct inventory run: 1 passed in 6.06s.
- Accepted 264-node baseline: 264 passed in 146.86s.
- Final exact sorted union: 265 passed in 134.67s.
- Final test compilation:
  `.venv/bin/python -m compileall -q tests/engine/test_event_knowledge_scripted_encounter.py`: exit 0.
- Scoped `git diff --check` for the new test and this ledger: exit 0.
- Existing E1/E2 production/test paths remained pre-existing accepted dirty
  work; Slice 3.1 added no production modification.
- No subagents, excluded files, game package, production reducer, or new event
  path were used.

Final checkpoint status:
`SLICE_3_1_INVENTORY_FROZEN — READY_FOR_COORDINATOR_REVIEW`.

## 11. Slice 3.1 final test-quality correction — inventory frozen

This bounded test-and-ledger correction preserves the direct fixture, listener
proof, 244-event stream, and 265-node union.

### Public-boundary corrections

- `Encounter.roll_initiative()` now receives distinct ordinary public dice
  faces `(20, 16, 12, 8)). The resulting public
  `encounter.initiative_order` is asserted to be exactly
  `hero_frontline -> enemy_guard -> enemy_raider -> hero_caster`.
  Direct writes to `initiative_order` and `current_turn_index` were removed.
- The first attempted all-parent-version assertion exposed an existing
  provisional `StepMovementEvent` at source index 40 with a resolved
  `parent_event` but `parent_lineage=None). No production change is
  authorized in Slice 3.1. The corrected proof retains the complete
  148-edge child-index/parent-index inventory and applies the real
  `event.parent_lineage == parent.lineage_uuid` contract to each resolved
  completion child; 56 such completion edges were checked and all passed.
  Non-completion versions remain recorded as parent edges but are not
  mislabeled as resolved lineage records.

### Final verification

- Focused selector:
  `1 passed in 5.18s`.
- Final exact accepted baseline: 264 passed in 146.86s; normalized SHA-256
  `13043bdba75fae26de00295ea681e809be2524b83252c683217ba972839269b0`.
- Final exact sorted union: 265 passed in 121.03s; normalized SHA-256
  `b3a6c990713aab169bb2b8b69463a817bc4351989af2583c47798ceb0f4f1f8c`.
- Collection remains exactly 265 nodes with the same one authorized Slice 3.1
  node; no node was added, removed, or renamed.
- Final test SHA-256: 8dd2d36c05dcbd7ab649d3a0d8b717533d102dc9861ceb1238e5947573294186  tests/engine/test_event_knowledge_scripted_encounter.py.
- `.venv/bin/python -m compileall -q
  tests/engine/test_event_knowledge_scripted_encounter.py`: exit 0.
- Final new-file/ledger diff checks are clean except the existing LF/CRLF
  normalization warning.
- No production, excluded, governing-plan, or unrelated dirty bytes changed.

The final public listener/terminal evidence from the focused run is retained
below. It includes the exact run-instance listener UUIDs, terminal UUIDs,
lineages, source indices, concrete classes, combat-log kinds, and recursive
public tree shapes; the stable event class/phase/type inventory remains in the
preceding checkpoint.

```text
SLICE_3_1_PARENT_EDGE_COUNT 148
SLICE_3_1_RESOLVED_PARENT_LINEAGE_EDGE_COUNT 56
SLICE_3_1_PARENT_EDGES [(5, 4), (11, 10), (12, 10), (18, 17), (19, 17), (20, 17), (26, 25), (27, 25), (28, 25), (29, 25), (40, 39), (41, 40), (42, 40), (43, 42), (44, 42), (45, 42), (46, 42), (47, 40), (48, 47), (49, 47), (50, 47), (51, 40), (52, 40), (53, 52), (54, 52), (55, 52), (56, 52), (57, 52), (58, 52), (59, 58), (60, 58), (61, 58), (62, 61), (63, 61), (64, 61), (65, 64), (66, 61), (67, 58), (68, 52), (69, 40), (70, 40), (71, 40), (72, 40), (73, 40), (74, 40), (75, 40), (76, 40), (77, 40), (78, 77), (79, 77), (80, 77), (81, 77), (82, 40), (83, 39), (87, 86), (88, 86), (89, 86), (90, 89), (91, 86), (93, 92), (94, 92), (95, 92), (98, 97), (99, 97), (100, 97), (101, 97), (102, 97), (103, 97), (104, 103), (105, 103), (106, 103), (107, 106), (108, 106), (109, 106), (110, 106), (111, 103), (112, 97), (134, 133), (135, 134), (136, 134), (137, 134), (138, 134), (139, 134), (140, 134), (141, 134), (142, 141), (143, 141), (144, 141), (145, 141), (146, 134), (147, 133), (159, 158), (160, 158), (161, 158), (162, 161), (163, 158), (165, 164), (166, 164), (167, 164), (170, 169), (171, 169), (172, 169), (173, 169), (174, 169), (175, 169), (176, 175), (177, 175), (178, 175), (179, 178), (180, 178), (181, 178), (182, 178), (183, 175), (184, 169), (201, 200), (202, 200), (203, 200), (204, 201), (205, 201), (206, 201), (207, 204), (208, 204), (209, 204), (210, 207), (211, 207), (212, 207), (213, 207), (214, 204), (215, 201), (216, 200), (217, 215), (218, 215), (219, 215), (220, 218), (221, 218), (222, 218), (223, 218), (224, 215), (225, 200), (226, 225), (227, 225), (228, 225), (229, 228), (230, 228), (231, 228), (232, 228), (233, 225), (234, 200)]
SLICE_3_1_SENSORY_CAUSALITY_COUNT 21
SLICE_3_1_SENSORY_BEFORE_CAUSATIVE_COMPLETION 21
SLICE_3_1_ENCOUNTER_UUID 45c1eded-061e-400a-bb35-2b27e5dc134c
SLICE_3_1_COMBAT_LOG_RANGES [('initiative_roll', 0, 0), ('encounter_start', 0, 0), ('hero_frontline_turn_start', 0, 1), ('hero_frontline_move', 1, 2), ('hero_frontline_weapon_attack', 2, 3), ('hero_frontline_turn_end', 3, 4), ('enemy_guard_action_boundary', 4, 7), ('enemy_raider_action_boundary', 7, 10), ('hero_caster_turn_start', 10, 11), ('hero_caster_discovered_spell', 11, 12), ('hero_caster_turn_end', 12, 13), ('encounter_end', 13, 13)]
SLICE_3_1_LISTENER_OBSERVATION_COUNT 13
SLICE_3_1_LISTENER_TO_TERMINAL_LINKS [(0, '5e2c2f3f-d04a-4115-8ff3-bb7b5f28398e', 'e7355ea2-e425-401f-8e0b-8fb9f8f7cb90', 'dnd.core.events.encounter_events.TurnStartEvent', 36, '4641dc2a-2858-4bab-98bc-eb4f4251e822', 'e7355ea2-e425-401f-8e0b-8fb9f8f7cb90', 'turn_start', ('turn_start', ())), (1, '3d07b201-3127-4fd0-aaf7-eb68de5ed573', 'a1049491-67ba-4eed-a2ac-698d12dec932', 'dnd.actions.standard.MovementEvent', 84, 'bcab360b-f43c-4514-b3b7-10fe41a03a15', 'a1049491-67ba-4eed-a2ac-698d12dec932', 'movement', ('movement', (('movement', (('attack', (('damage_taken', ()),)),)),))), (2, '423f45cd-7448-4acb-b1b4-4502da14ec10', 'e2ed1c15-5e7e-410f-b328-7a184b6690dc', 'dnd.actions.standard.AttackEvent', 114, 'f039c38f-8de8-4c25-89c2-0dcb8dacbcb7', 'e2ed1c15-5e7e-410f-b328-7a184b6690dc', 'attack', ('attack', (('damage_taken', ()),))), (3, '5ae9dfe2-ad66-4580-9cad-939279d8a0cc', '3d60f5e1-8dd3-4265-bcee-ea2fb72415ed', 'dnd.core.events.encounter_events.TurnEndEvent', 118, 'ca3bc1e5-d994-40e1-8e14-876162937c79', '3d60f5e1-8dd3-4265-bcee-ea2fb72415ed', 'turn_end', ('turn_end', ())), (4, '1c319f81-37c9-44fd-a6b1-139c2c0d7657', '7c559f18-51ce-4826-8e9f-bd1e8194bb58', 'dnd.core.events.encounter_events.TurnStartEvent', 130, '054088da-ee9e-4ec5-a1cf-7cca3f7c62ac', '7c559f18-51ce-4826-8e9f-bd1e8194bb58', 'turn_start', ('turn_start', ())), (5, '4e09cfa6-7f13-447b-accc-201c5e8c573c', '886fd7d5-b552-4ea7-983a-08a48efb3c9c', 'dnd.actions.standard.MovementEvent', 148, '4f2fb371-5a22-4d50-bc4b-98163e22d0f6', '886fd7d5-b552-4ea7-983a-08a48efb3c9c', 'movement', ('movement', (('movement', ()),))), (6, '63c171ac-fb5b-439a-bda7-3b895e6eb2d0', 'c73f8253-a82a-4583-9997-7b58450ed984', 'dnd.core.events.encounter_events.TurnEndEvent', 152, '8d932fd6-898f-4768-8cea-b9a963649cb6', 'c73f8253-a82a-4583-9997-7b58450ed984', 'turn_end', ('turn_end', ())), (7, '16181f57-5661-4c03-bd9e-a6fa7efbcce0', '0e684445-d6f7-4c6b-beff-8000cd3ff9e0', 'dnd.core.events.encounter_events.TurnStartEvent', 156, '7c6d7b8a-f860-4446-b7f5-1490d010f21b', '0e684445-d6f7-4c6b-beff-8000cd3ff9e0', 'turn_start', ('turn_start', ())), (8, '0311ab9a-f521-4bba-8d3a-e004910b7dd4', '6cb3be91-ab65-4d0f-9562-e87ca298a2f1', 'dnd.actions.standard.AttackEvent', 186, '41fef37a-036b-47c8-ad3b-cd2a1d48e7de', '6cb3be91-ab65-4d0f-9562-e87ca298a2f1', 'attack', ('attack', (('damage_taken', ()),))), (9, '7cd66cfc-39a4-442e-bb0e-bc2b652edb74', '2cf8acde-c47f-4a28-85fc-0744637f18bf', 'dnd.core.events.encounter_events.TurnEndEvent', 190, 'e087b228-2b01-4186-995b-cc33ffdcb687', '2cf8acde-c47f-4a28-85fc-0744637f18bf', 'turn_end', ('turn_end', ())), (10, 'bf66fcc8-f604-452f-b9d4-bed2d182aa1c', '14cbf035-2573-42c2-ab92-c86117e37dc2', 'dnd.core.events.encounter_events.TurnStartEvent', 198, 'b6e0ffb1-22fd-46f0-bdb0-98bc66dff3ea', '14cbf035-2573-42c2-ab92-c86117e37dc2', 'turn_start', ('turn_start', ())), (11, '7228dc2f-f09e-40bc-b579-c9ca22058aca', '2f5aefe1-6778-4ba1-ba15-661fa42a995e', 'dnd.actions.standard.SpellEvent', 236, '7cd03501-4ec9-4423-b95a-5594eeba861c', '2f5aefe1-6778-4ba1-ba15-661fa42a995e', 'multi_entity_action', ('multi_entity_action', (('spell_damage', (('damage_taken', ()),)), ('spell_damage', (('damage_taken', ()),)), ('spell_damage', (('damage_taken', ()),))))), (12, 'd47b8594-a091-47e2-9f62-73dcea2ccc83', '88f1ed5f-fd2a-4917-8d76-4f09de8ebaf0', 'dnd.core.events.encounter_events.TurnEndEvent', 240, 'f473ac9d-ebdc-4302-91f7-80837d2452bb', '88f1ed5f-fd2a-4917-8d76-4f09de8ebaf0', 'turn_end', ('turn_end', ()))]
SLICE_3_1_COMBAT_LOG_LINKS [(0, 36, '4641dc2a-2858-4bab-98bc-eb4f4251e822', 'e7355ea2-e425-401f-8e0b-8fb9f8f7cb90', 'dnd.core.events.encounter_events.TurnStartEvent', 'turn_start', ('turn_start', ())), (1, 84, 'bcab360b-f43c-4514-b3b7-10fe41a03a15', 'a1049491-67ba-4eed-a2ac-698d12dec932', 'dnd.actions.standard.MovementEvent', 'movement', ('movement', (('movement', (('attack', (('damage_taken', ()),)),)),))), (2, 114, 'f039c38f-8de8-4c25-89c2-0dcb8dacbcb7', 'e2ed1c15-5e7e-410f-b328-7a184b6690dc', 'dnd.actions.standard.AttackEvent', 'attack', ('attack', (('damage_taken', ()),))), (3, 118, 'ca3bc1e5-d994-40e1-8e14-876162937c79', '3d60f5e1-8dd3-4265-bcee-ea2fb72415ed', 'dnd.core.events.encounter_events.TurnEndEvent', 'turn_end', ('turn_end', ())), (4, 130, '054088da-ee9e-4ec5-a1cf-7cca3f7c62ac', '7c559f18-51ce-4826-8e9f-bd1e8194bb58', 'dnd.core.events.encounter_events.TurnStartEvent', 'turn_start', ('turn_start', ())), (5, 148, '4f2fb371-5a22-4d50-bc4b-98163e22d0f6', '886fd7d5-b552-4ea7-983a-08a48efb3c9c', 'dnd.actions.standard.MovementEvent', 'movement', ('movement', (('movement', ()),))), (6, 152, '8d932fd6-898f-4768-8cea-b9a963649cb6', 'c73f8253-a82a-4583-9997-7b58450ed984', 'dnd.core.events.encounter_events.TurnEndEvent', 'turn_end', ('turn_end', ())), (7, 156, '7c6d7b8a-f860-4446-b7f5-1490d010f21b', '0e684445-d6f7-4c6b-beff-8000cd3ff9e0', 'dnd.core.events.encounter_events.TurnStartEvent', 'turn_start', ('turn_start', ())), (8, 186, '41fef37a-036b-47c8-ad3b-cd2a1d48e7de', '6cb3be91-ab65-4d0f-9562-e87ca298a2f1', 'dnd.actions.standard.AttackEvent', 'attack', ('attack', (('damage_taken', ()),))), (9, 190, 'e087b228-2b01-4186-995b-cc33ffdcb687', '2cf8acde-c47f-4a28-85fc-0744637f18bf', 'dnd.core.events.encounter_events.TurnEndEvent', 'turn_end', ('turn_end', ())), (10, 198, 'b6e0ffb1-22fd-46f0-bdb0-98bc66dff3ea', '14cbf035-2573-42c2-ab92-c86117e37dc2', 'dnd.core.events.encounter_events.TurnStartEvent', 'turn_start', ('turn_start', ())), (11, 236, '7cd03501-4ec9-4423-b95a-5594eeba861c', '2f5aefe1-6778-4ba1-ba15-661fa42a995e', 'dnd.actions.standard.SpellEvent', 'multi_entity_action', ('multi_entity_action', (('spell_damage', (('damage_taken', ()),)), ('spell_damage', (('damage_taken', ()),)), ('spell_damage', (('damage_taken', ()),))))), (12, 240, 'f473ac9d-ebdc-4302-91f7-80837d2452bb', '88f1ed5f-fd2a-4917-8d76-4f09de8ebaf0', 'dnd.core.events.encounter_events.TurnEndEvent', 'turn_end', ('turn_end', ()))]
```

Final checkpoint status:
`SLICE_3_1_INVENTORY_FROZEN — READY_FOR_COORDINATOR_REVIEW`.
Slice 3.2 is not started.



## 10. Slice 3.1 listener identity correction — inventory frozen

The coordinator-required passive listener proof is now included in the existing
direct fixture. This is test-only and does not change the accepted 265-node
union or any production behavior.

### Listener-to-terminal public evidence

- `Encounter.add_combat_log_listener` is called once before initiative and
  mechanics emit combat logs.
- The listener is removed through the existing
  `Encounter.remove_combat_log_listener` API in the outer `finally`, including
  exceptional exits.
- Each listener payload is checked as a typed `CombatLogEntry` and retained only
  as a detached deep `model_copy(deep=True)` test observation.
- The closed public queue is then searched for exactly one top-level
  `EventPhase.COMPLETION` event with the listener lineage and concrete class,
  whose `combat_log` equals the detached entry and the encounter log entry by
  value.
- All 13 observed listener log indices are unique and cover `0..12); every
  listener UUID differs from its resolved stored terminal UUID; every resolved
  source index and recursive public `sub_entries` tree matches the encounter
  log; no standalone encounter-log row is left without a linked terminal event.
- The stable event stream remains 244 versions, with the prior full
  class/phase/type inventory and 148 parent edges unchanged. The exact
  run-instance encounter/listener/terminal identities and tree evidence are:

```text
SLICE_3_1_ENCOUNTER_UUID 1426cc3d-29e8-4600-8341-23cd6ed8423c
SLICE_3_1_COMBAT_LOG_RANGES [('initiative_roll', 0, 0), ('encounter_start', 0, 0), ('hero_frontline_turn_start', 0, 1), ('hero_frontline_move', 1, 2), ('hero_frontline_weapon_attack', 2, 3), ('hero_frontline_turn_end', 3, 4), ('enemy_guard_action_boundary', 4, 7), ('enemy_raider_action_boundary', 7, 10), ('hero_caster_turn_start', 10, 11), ('hero_caster_discovered_spell', 11, 12), ('hero_caster_turn_end', 12, 13), ('encounter_end', 13, 13)]
SLICE_3_1_LISTENER_OBSERVATION_COUNT 13
SLICE_3_1_LISTENER_TO_TERMINAL_LINKS [(0, '69dfcf43-12fb-4f5b-a51a-7510cc6f2298', '7475ae69-48f8-4965-b654-b82d352a38d5', 'dnd.core.events.encounter_events.TurnStartEvent', 36, '0cdc9d91-028f-4282-bd3c-c59deacbbb35', '7475ae69-48f8-4965-b654-b82d352a38d5', 'turn_start', ('turn_start', ())), (1, '9891ec8e-b9f2-43ce-894e-374a8073d881', '7bb4fe60-0182-4a5f-9e60-65ac90f059d7', 'dnd.actions.standard.MovementEvent', 84, 'f9aa2ff1-35d1-4827-aff8-a48db44d3d84', '7bb4fe60-0182-4a5f-9e60-65ac90f059d7', 'movement', ('movement', (('movement', (('attack', (('damage_taken', ()),)),)),))), (2, '7710aa43-f460-48be-800f-14dc54db5da5', '3da3c176-f941-4ab8-9967-ad7d690b14ca', 'dnd.actions.standard.AttackEvent', 114, '43b66068-3580-4753-abb1-0172a4f00de1', '3da3c176-f941-4ab8-9967-ad7d690b14ca', 'attack', ('attack', (('damage_taken', ()),))), (3, 'e18fd9f3-4f79-48c0-974e-6aaf42f1bf7f', '1e59ffa3-4051-49f3-a047-8ab33efe6834', 'dnd.core.events.encounter_events.TurnEndEvent', 118, 'd8486148-54cd-4fc2-95ac-71bd3e5480c9', '1e59ffa3-4051-49f3-a047-8ab33efe6834', 'turn_end', ('turn_end', ())), (4, 'dfaa3657-51de-4d3f-b128-4f9e07e26016', 'a497aa7c-666f-4e70-9df2-5988fe201239', 'dnd.core.events.encounter_events.TurnStartEvent', 130, '151b8c6c-168c-4d71-b7dd-048cb79fc3fb', 'a497aa7c-666f-4e70-9df2-5988fe201239', 'turn_start', ('turn_start', ())), (5, 'adc6730b-1dff-4eee-8e8b-268bca168a0b', 'e18fea87-60ea-4c2d-82c0-48c529daff90', 'dnd.actions.standard.MovementEvent', 148, '7ec9fc05-76fd-4350-8538-779e1a1d01e5', 'e18fea87-60ea-4c2d-82c0-48c529daff90', 'movement', ('movement', (('movement', ()),))), (6, '90fe820c-df05-4ada-8987-7a0aafc1fb6f', 'deb8c003-dd12-4208-a96b-230a9c6d2657', 'dnd.core.events.encounter_events.TurnEndEvent', 152, '3d45d723-bbe3-4285-9156-51267430f771', 'deb8c003-dd12-4208-a96b-230a9c6d2657', 'turn_end', ('turn_end', ())), (7, '82a34522-7fa7-4fd2-b9e6-db8d95e35da7', '07dee44b-508f-4738-9fed-5e7ed09958a5', 'dnd.core.events.encounter_events.TurnStartEvent', 156, 'b79ebd76-eeff-4210-801b-1c4999d40f14', '07dee44b-508f-4738-9fed-5e7ed09958a5', 'turn_start', ('turn_start', ())), (8, 'ec03989f-2d56-4cb7-8c34-d98426ac8ea0', '4aa241f6-bfbe-47a7-9e0a-7325df2de612', 'dnd.actions.standard.AttackEvent', 186, '4b7eb41c-0284-4ede-8aab-e4e322448d66', '4aa241f6-bfbe-47a7-9e0a-7325df2de612', 'attack', ('attack', (('damage_taken', ()),))), (9, '186e3488-4776-4736-ac07-1ac097b41743', '4a3f8920-7f01-4826-9354-98ef4cada5bb', 'dnd.core.events.encounter_events.TurnEndEvent', 190, '50b70225-a85f-449a-a7b7-69be0c72c48c', '4a3f8920-7f01-4826-9354-98ef4cada5bb', 'turn_end', ('turn_end', ())), (10, '1b120c40-bd9c-431d-be9c-c657154dc101', '4d5527b9-3952-4167-a6a1-3acb9087425a', 'dnd.core.events.encounter_events.TurnStartEvent', 198, '00b61a21-83f5-432e-ba3f-bca58912bd0b', '4d5527b9-3952-4167-a6a1-3acb9087425a', 'turn_start', ('turn_start', ())), (11, '9f7132bd-cb05-426c-ba65-53bf0ce9c8f2', 'b0863cf7-2742-4bc1-b61d-262c5d9ecb30', 'dnd.actions.standard.SpellEvent', 236, '5998002a-a934-45f3-b947-208feaf0158f', 'b0863cf7-2742-4bc1-b61d-262c5d9ecb30', 'multi_entity_action', ('multi_entity_action', (('spell_damage', (('damage_taken', ()),)), ('spell_damage', (('damage_taken', ()),)), ('spell_damage', (('damage_taken', ()),))))), (12, '3925b057-903d-4042-ab7b-8d9b86172ad7', 'bffcd68f-7dc9-42c3-b618-37d8bdaeec69', 'dnd.core.events.encounter_events.TurnEndEvent', 240, '08ac77ba-e793-4b64-8b09-69afd94a8434', 'bffcd68f-7dc9-42c3-b618-37d8bdaeec69', 'turn_end', ('turn_end', ()))]
SLICE_3_1_COMBAT_LOG_LINKS [(0, 36, '0cdc9d91-028f-4282-bd3c-c59deacbbb35', '7475ae69-48f8-4965-b654-b82d352a38d5', 'dnd.core.events.encounter_events.TurnStartEvent', 'turn_start', ('turn_start', ())), (1, 84, 'f9aa2ff1-35d1-4827-aff8-a48db44d3d84', '7bb4fe60-0182-4a5f-9e60-65ac90f059d7', 'dnd.actions.standard.MovementEvent', 'movement', ('movement', (('movement', (('attack', (('damage_taken', ()),)),)),))), (2, 114, '43b66068-3580-4753-abb1-0172a4f00de1', '3da3c176-f941-4ab8-9967-ad7d690b14ca', 'dnd.actions.standard.AttackEvent', 'attack', ('attack', (('damage_taken', ()),))), (3, 118, 'd8486148-54cd-4fc2-95ac-71bd3e5480c9', '1e59ffa3-4051-49f3-a047-8ab33efe6834', 'dnd.core.events.encounter_events.TurnEndEvent', 'turn_end', ('turn_end', ())), (4, 130, '151b8c6c-168c-4d71-b7dd-048cb79fc3fb', 'a497aa7c-666f-4e70-9df2-5988fe201239', 'dnd.core.events.encounter_events.TurnStartEvent', 'turn_start', ('turn_start', ())), (5, 148, '7ec9fc05-76fd-4350-8538-779e1a1d01e5', 'e18fea87-60ea-4c2d-82c0-48c529daff90', 'dnd.actions.standard.MovementEvent', 'movement', ('movement', (('movement', ()),))), (6, 152, '3d45d723-bbe3-4285-9156-51267430f771', 'deb8c003-dd12-4208-a96b-230a9c6d2657', 'dnd.core.events.encounter_events.TurnEndEvent', 'turn_end', ('turn_end', ())), (7, 156, 'b79ebd76-eeff-4210-801b-1c4999d40f14', '07dee44b-508f-4738-9fed-5e7ed09958a5', 'dnd.core.events.encounter_events.TurnStartEvent', 'turn_start', ('turn_start', ())), (8, 186, '4b7eb41c-0284-4ede-8aab-e4e322448d66', '4aa241f6-bfbe-47a7-9e0a-7325df2de612', 'dnd.actions.standard.AttackEvent', 'attack', ('attack', (('damage_taken', ()),))), (9, 190, '50b70225-a85f-449a-a7b7-69be0c72c48c', '4a3f8920-7f01-4826-9354-98ef4cada5bb', 'dnd.core.events.encounter_events.TurnEndEvent', 'turn_end', ('turn_end', ())), (10, 198, '00b61a21-83f5-432e-ba3f-bca58912bd0b', '4d5527b9-3952-4167-a6a1-3acb9087425a', 'dnd.core.events.encounter_events.TurnStartEvent', 'turn_start', ('turn_start', ())), (11, 236, '5998002a-a934-45f3-b947-208feaf0158f', 'b0863cf7-2742-4bc1-b61d-262c5d9ecb30', 'dnd.actions.standard.SpellEvent', 'multi_entity_action', ('multi_entity_action', (('spell_damage', (('damage_taken', ()),)), ('spell_damage', (('damage_taken', ()),)), ('spell_damage', (('damage_taken', ()),))))), (12, 240, '08ac77ba-e793-4b64-8b09-69afd94a8434', 'bffcd68f-7dc9-42c3-b618-37d8bdaeec69', 'dnd.core.events.encounter_events.TurnEndEvent', 'turn_end', ('turn_end', ()))]
```

### Correction validation and bindings

- Focused listener-correction selector:
  `1 passed in 5.70s`.
- Final test-file SHA-256: 43ead75d06507aa3840e5402530ceb980c6e2b4e3c472c0ee8383c0c6061dcea  tests/engine/test_event_knowledge_scripted_encounter.py.
- Accepted baseline remains 264 nodes with SHA-256
  `13043bdba75fae26de00295ea681e809be2524b83252c683217ba972839269b0`.
- Exact union remains 265 nodes with normalized SHA-256
  `b3a6c990713aab169bb2b8b69463a817bc4351989af2583c47798ceb0f4f1f8c`;
  the final union execution was `265 passed in 141.47s`.
- Final test compilation remained exit 0.
- The focused scoped whitespace/diff check remains clean apart from the
  existing LF/CRLF normalization warning.
- No production, plan, excluded, or unrelated dirty path was changed.
- Slice 3.2 is not started.

Final checkpoint status:
`SLICE_3_1_INVENTORY_FROZEN — READY_FOR_COORDINATOR_REVIEW`.

## Slice 3.2 reducer completion checkpoint

Slice 3.2 was implemented only after the accepted Slice 3.1 checkpoint
(`3741a310e0479dd707e22153a17845134ba05dc6d6fb6d2e8c6ec4724d9853a2`).
The governing plan was reverified at SHA-256
`aaf75e26e3b1e13419caf3d0b7e8346ad8a86531bc155b90f6d37767a8328c98`.
Its governing authorities were reverified as follows:

| Authority | SHA-256 |
| --- | --- |
| `DND_EVENT_KNOWLEDGE_CONTEXT_REDUCTION_PLAN_2026-08-27.md` | `7856a537f0b75063fe5bcb012fd7d020b2f92a1e018c17d1ccf6b5e830605c21` |
| `DND_EVENT_KNOWLEDGE_CONTEXT_IMPLEMENTATION_PLAN_2026-08-27.md` | `3f98f0b926fce8e9662c5718c01aa863734a563897bebe0b403173d8eba0a9ad` |
| `DND_PYGAME_SCRIPTED_ENCOUNTER_MVP_IMPLEMENTATION_PLAN_2026-08-27.md` | `8e83dde4916ca3a6a4691bd9b25f720d3e381fe49e6458d4c0800007f9b390b9` |

### Bounded implementation

- Created only the authorized `dnd/event_reduction.py` composition root.
- Moved the E2 occurrence/path policy functions and their router/delivery
  assembly from `dnd/blocks/sensory.py`; the sensory snapshot, pure reducer,
  observer knowledge, party join, and evidence methods remain there.
- Extended the existing knowledge envelope with the approved deterministic
  `BatchId`/`DeliveryId`, `SourceDisposition`, `SourceCoverage`, and the
  `EventBatch`/`EventDelivery` metadata fields. No parallel event or log
  schema was added.
- `EventReducer` accepts exactly two controlled UUIDs, validates the callback
  UUID/class tail against the current queue cursor and generation, captures
  only the callback-proven range, replays controlled sensory deltas in source
  order, and commits state only after the full range and coverage are valid.
- Unadmitted concrete classes produce payload-free `NO_CLASS_POLICY` error
  coverage. No live world lookup is performed.
- The passive combat-log method stores only typed detached listener evidence
  until the batch closes, resolves exactly one captured top-level terminal by
  lineage/class/tree value, keeps only the encounter UUID/log-index archive
  reference, and rejects listener/terminal UUID aliasing.

### Exact Slice 3.2 public/architecture proof inventory

The eight newly collecting nodes, beyond the accepted 265-node Slice 3.1
union, are exactly:

```text
tests/engine/test_event_knowledge_context.py::test_event_reducer_captures_one_tail_and_replays_party_senses
tests/engine/test_event_knowledge_context.py::test_event_reducer_listener_resolves_transient_log_to_stored_terminal_archive
tests/engine/test_event_knowledge_context.py::test_event_reducer_rejects_reordered_split_and_generation_ranges_without_advancing
tests/engine/test_event_knowledge_context.py::test_event_reducer_repeated_fresh_reduction_has_identical_ids_and_values
tests/engine/test_event_knowledge_context.py::test_event_reducer_unadmitted_occurrence_has_error_coverage_without_payload
tests/architecture/test_event_knowledge_context_architecture.py::test_batch_metadata_is_the_single_existing_knowledge_envelope_extension
tests/architecture/test_event_knowledge_context_architecture.py::test_reduction_composition_root_owns_e2_policy_assembly
tests/architecture/test_event_knowledge_context_architecture.py::test_reduction_has_only_module_scope_imports_and_never_transitions_events
```

The exact collection input was:

```text
.venv/bin/python -m pytest -q -p no:cacheprovider --collect-only \
  tests/engine/test_event_knowledge_context.py \
  tests/engine/test_objective_state.py \
  tests/engine/test_direct_scenario_deployment.py \
  tests/engine/test_event_wire_visibility_contract.py \
  tests/engine/test_move_settlement.py \
  tests/engine/test_senses_light_stealth.py \
  tests/engine/test_combat_actions.py \
  tests/engine/test_action_cost_and_position_commit.py \
  tests/engine/test_event_knowledge_scripted_encounter.py \
  tests/architecture
```

The output was sorted C-bytewise, deduplicated, and terminated with one LF;
it collected 273 unique node IDs with SHA-256
`6df0dd89a42fac305e5fc1eee8152548c901369bf6d356f9ab4328476d62a3c0`.
The exact list was executed newline/argument-boundary safely from that
collected list: `273 passed in 145.87s (0:02:25)`.
The unchanged accepted Slice 3.1 union remains 265 nodes; the current 273
count is that union plus the eight IDs above, not a replacement baseline.

The focused/architecture command

```text
.venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/engine/test_event_knowledge_context.py \
  tests/architecture/test_event_knowledge_context_architecture.py
```

passed `29 passed in 4.93s`. The final 273-node execution above includes the
accepted E1/E2 regressions and Slice 3.1 proving node; no separate historical
272-node result is used as the final Slice 3.2 validation.

### Validation and current bytes

- `.venv/bin/python -m compileall -q` over every changed active Python file
  (`dnd/event_reduction.py`, `dnd/core/events/knowledge.py`,
  `dnd/blocks/sensory.py`, the two changed test files) exited 0.
- Scoped `git diff --check` exited 0. Git reported only the existing
  `dnd/blocks/sensory.py` LF/CRLF normalization warning.
- The composition architecture gate passed: exactly one stateful production
  class (`EventReducer`), no policy definitions remain in `sensory.py`, no
  function-local imports, no forbidden event lifecycle calls, and no direct
  live-world/encounter/grid lookup.
- The full `tests/architecture` portion of the exact union passed as part of
  the 273-node execution; no architecture node was excluded.
- No unrelated production, test, excluded-scope, governing-plan, or dirty
  path was reset, cleaned, or rewritten. The authorized production files and
  the explicitly extended E2/architecture test files are the only Slice 3.2
  changes; the accepted Slice 3.1 fixture behavior was not altered.

Current governed active-file SHA-256 values are:

```text
ec745ba6d8a70d0159dbada7f6329a5dd427feae10d0b9a628f6e5f3333e18ba  dnd/event_reduction.py
f9347cdeb21591b051014b06a90d4d5604904abdfe1c0d40d4d55d2c7d433026  dnd/core/events/knowledge.py
9ccca8d2ec117b312f51589020123b177eb1f5a15e719f0fc6e707fc8ed96dff  dnd/blocks/sensory.py
68a7de5d30a4551d3c8c763dcce957e39ab283b89053809e4aa62eb564d943a0  tests/engine/test_event_knowledge_context.py
cdfac7f075dbc34a61cdcb119d29ff4b763c91c92803318f3343b2bec9ef57b0  tests/architecture/test_event_knowledge_context_architecture.py
8dd2d36c05dcbd7ab649d3a0d8b717533d102dc9861ceb1238e5947573294186  tests/engine/test_event_knowledge_scripted_encounter.py (accepted, unchanged)
```

No Slice 3.2 final manifest is created: the plan authorizes the final
manifest only in a later certification slice. The existing ledger is the
only record updated here. No Slice 3.3 policy, provenance, disclosure,
formatter, or async consumer work was started.

Checkpoint status:
`SLICE_3_2_REDUCER_COMPLETE — READY_FOR_COORDINATOR_REVIEW`.

### Slice 3.2 bounded correction and revalidation

The earlier 273-node Slice 3.2 result and its implementation hashes are
superseded by this bounded correction and are not final evidence. No Slice
3.3 work was started.

The correction removed the invalid parent-topology heuristic from
`EventReducer._validate_callback_tail`. Legitimate public
`EventQueue.register_completion_sequence` callbacks may contain multiple
top-level completion events; contiguous cursor history, queue UUID/class
identity, and generation identity remain the only callback-boundary checks.
The E2 router now has one fixed table with direct `AttackEvent` and
`DamageAppliedEvent` entries and no caller-supplied class injection. The
duplicated `_identified`, `_located`, and `_position_known` helpers were
removed from `dnd/event_reduction.py`; the retained evidence methods in
`sensory.py` remain the owners of those semantics. The shared-source proof
constructs objective knowledge from the exact party delivery's captured
object and makes no second `EventArchive.capture_queue_range` call.

The public correction proofs are:

```text
tests/engine/test_event_knowledge_context.py::test_event_reducer_accepts_public_completion_sequence_batch_once
tests/engine/test_event_knowledge_context.py::test_event_reducer_rejects_cursor_duplicate_or_merged_history_without_advancing
tests/engine/test_event_knowledge_context.py::test_event_reducer_rejects_zero_terminal_log_match_without_advancing
tests/engine/test_event_knowledge_context.py::test_event_reducer_rejects_ambiguous_terminal_log_match_without_advancing
```

The completion-sequence proof attaches through the public
`EventQueue.add_on_event_batch_callback`, publishes two real top-level
completion events through `register_completion_sequence`, and verifies both
source slots are retained while the reducer advances once over `[0, 2)`.
The cursor-history proof accepts two actual one-event callbacks, then rejects
both a caller-merged old-plus-new tail and a duplicate processed tail without
advancing. The existing reordered, split/non-tail, and generation-rejection
proofs remain in
`test_event_reducer_rejects_reordered_split_and_generation_ranges_without_advancing`.
The zero-match and ambiguous-match proofs use only public Encounter listener,
EventQueue, and reducer APIs; each verifies the cursor, party state, archive,
objective references, last batch, and pending listener evidence remain
unadvanced after failure. No test reads `_snapshot` or a private reducer
method.

The first focused run after the edit exposed only missing required
`Encounter.source_entity_uuid` values in the two new public fixtures (2
failures, 31 passes). Supplying the existing observer UUID to each Encounter
was the bounded test-only repair; no production repair was needed.

Post-repair validation results:

- Focused reducer/context plus Slice 3.2 architecture tests: `33 passed in
  5.89s`.
- Affected E1/E2 engine paths, including the scripted encounter, without the
  architecture directory: `225 passed in 135.60s`.
- Complete `tests/architecture`: `52 passed in 35.82s`.
- Explicit no-local-import/canonical-owner selectors: `5 passed in 3.26s`.
- Compileall for `dnd/event_reduction.py`,
  `dnd/core/events/knowledge.py`, `dnd/blocks/sensory.py`, the changed engine
  test, and the architecture test: exit `0`.
- Scoped `git diff --check`: exit `0`; only the existing LF/CRLF
  normalization warnings were emitted. The untracked changed files had no
  whitespace diagnostics from the corresponding no-index check.
- The stale-heuristic/injection/duplicate-helper/wrapper search was empty.

The exact collection input was unchanged from the accepted Slice 3.1/E1/E2
path union:

```text
.venv/bin/python -m pytest -q -p no:cacheprovider --collect-only \
  tests/engine/test_event_knowledge_context.py \
  tests/engine/test_objective_state.py \
  tests/engine/test_direct_scenario_deployment.py \
  tests/engine/test_event_wire_visibility_contract.py \
  tests/engine/test_move_settlement.py \
  tests/engine/test_senses_light_stealth.py \
  tests/engine/test_combat_actions.py \
  tests/engine/test_action_cost_and_position_commit.py \
  tests/engine/test_event_knowledge_scripted_encounter.py \
  tests/architecture
```

Collection output was filtered to `^tests/.*::`, sorted C-bytewise,
deduplicated, and terminated with one LF. It produced `277` unique node IDs
with normalized SHA-256
`6391ee771834440e73a51eb8acbc29e203871fba60e9f9902d1f75ded6a2615c`.
That exact sorted list was passed newline-safely to the same pytest runtime:
`277 passed in 184.41s (0:03:04)`. This fresh collection identity is the
post-repair result; the historical 273-node result above is superseded.

Current governed active-file SHA-256 values after this correction are:

```text
a3ba5eda572226dcc3de0397ff33233428a419eabc59df54b6d0b5a417898bec  dnd/event_reduction.py
f9347cdeb21591b051014b06a90d4d5604904abdfe1c0d40d4d55d2c7d433026  dnd/core/events/knowledge.py
9ccca8d2ec117b312f51589020123b177eb1f5a15e719f0fc6e707fc8ed96dff  dnd/blocks/sensory.py
a44efd118ceca498196b3242d15a61871a705824fa07ab6a13160bf47c8b054b  tests/engine/test_event_knowledge_context.py
cdfac7f075dbc34a61cdcb119d29ff4b763c91c92803318f3343b2bec9ef57b0  tests/architecture/test_event_knowledge_context_architecture.py
8dd2d36c05dcbd7ab649d3a0d8b717533d102dc9861ceb1238e5947573294186  tests/engine/test_event_knowledge_scripted_encounter.py (accepted, unchanged)
```

No Slice 3.2 final manifest was created because the plan authorizes that
artifact only in a later certification slice. The final physical checkpoint
status is:
`SLICE_3_2_REDUCER_COMPLETE — READY_FOR_COORDINATOR_REVIEW`.

### Slice 3.2 final bounded listener-lineage test correction and revalidation

The prior post-repair 277-node result and its test/ledger hashes are
superseded by this test-only correction. In
`test_event_reducer_rejects_ambiguous_terminal_log_match_without_advancing`,
both queued terminal candidates now use the exact public
`listener_event.lineage_uuid`; the test also proves both candidates share that
lineage and the listener's exact `Event` class while all three UUIDs remain
distinct. The ambiguous path therefore reaches the greater-than-one terminal
candidate check rather than repeating the zero-match path. No production file,
plan, excluded path, or Slice 3.3 file was changed.

Focused listener proofs:

```text
tests/engine/test_event_knowledge_context.py::test_event_reducer_listener_resolves_transient_log_to_stored_terminal_archive
tests/engine/test_event_knowledge_context.py::test_event_reducer_rejects_zero_terminal_log_match_without_advancing
tests/engine/test_event_knowledge_context.py::test_event_reducer_rejects_ambiguous_terminal_log_match_without_advancing
```

Result: `3 passed in 4.06s`.

Post-correction validation results:

- Full `tests/engine/test_event_knowledge_context.py` plus complete
  `tests/architecture`: `78 passed in 43.27s`.
- Compileall for all governed Slice 3.2 Python files: exit `0`.
- Scoped `git diff --check`: exit `0`; only the existing LF/CRLF
  normalization warnings were emitted.
- The stale heuristic, caller-class injection, duplicate-helper, and
  compatibility-wrapper scan remained empty.

The exact sorted-unique collection input and algorithm remain the same as the
accepted E1/E2 path union: filter `^tests/.*::`, sort C-bytewise, deduplicate,
and terminate with one LF. Fresh collection produced `277` node IDs with
normalized SHA-256
`6391ee771834440e73a51eb8acbc29e203871fba60e9f9902d1f75ded6a2615c`.
That exact newline-safe node list was executed after this final test edit:
`277 passed in 136.95s (0:02:16)`.

Current governed active-file SHA-256 values are:

```text
a3ba5eda572226dcc3de0397ff33233428a419eabc59df54b6d0b5a417898bec  dnd/event_reduction.py
f9347cdeb21591b051014b06a90d4d5604904abdfe1c0d40d4d55d2c7d433026  dnd/core/events/knowledge.py
9ccca8d2ec117b312f51589020123b177eb1f5a15e719f0fc6e707fc8ed96dff  dnd/blocks/sensory.py
a89c05ce45c53d45ac22de458d5ae6d8f45fb05f842253ae283664877cd7ad7f  tests/engine/test_event_knowledge_context.py
cdfac7f075dbc34a61cdcb119d29ff4b763c91c92803318f3343b2bec9ef57b0  tests/architecture/test_event_knowledge_context_architecture.py
8dd2d36c05dcbd7ab649d3a0d8b717533d102dc9861ceb1238e5947573294186  tests/engine/test_event_knowledge_scripted_encounter.py (accepted, unchanged)
```

No Slice 3.2 final manifest was created because that artifact remains
authorized only in a later certification slice. Final physical checkpoint
status:
`SLICE_3_2_REDUCER_COMPLETE — READY_FOR_COORDINATOR_REVIEW`.

## Slice 3.3 exact admission, provenance, causal disclosure, and memory

This checkpoint implements only Slice 3.3 of the accepted plan
`aaf75e26e3b1e13419caf3d0b7e8346ad8a86531bc155b90f6d37767a8328c98`.
The accepted Slice 3.2 baseline remains the 277-node union with normalized
SHA-256 `6391ee771834440e73a51eb8acbc29e203871fba60e9f9902d1f75ded6a2615c`.
No plan, excluded path, Slice 3.1 fixture, or unrelated dirty file was
changed. Slice 3.3 changed only:

```text
dnd/event_reduction.py
tests/engine/test_event_knowledge_context.py
tests/architecture/test_event_knowledge_context_architecture.py
```

The one exact concrete-class manifest table contains these 20 frozen
Slice 3.1 classes, each once, with its explicit selector, collection path,
coverage role, and reference-only provenance policy:

```text
dnd.core.events.world_events.WorldInitializedEvent
dnd.core.events.entity_events.EntityCreatedEvent
dnd.core.events.world_events.SpatialChangeEvent
dnd.core.events.world_events.SensoryUpdateEvent
dnd.core.events.encounter_events.EncounterStartEvent
dnd.core.events.encounter_events.RoundStartEvent
dnd.core.events.encounter_events.TurnStartEvent
dnd.actions.standard.MovementEvent
dnd.core.events.world_events.StepMovementEvent
dnd.actions.standard.AttackEvent
dnd.core.events.resolution_events.AttackD20RollResultEvent
dnd.core.events.resolution_events.DamageRollResultEvent
dnd.core.events.resolution_events.TakeDamageEvent
dnd.core.events.resolution_events.DamageAppliedEvent
dnd.core.base_conditions.ConditionApplicationEvent
dnd.core.base_conditions.ConditionRemovalEvent
dnd.actions.standard.SpellEvent
dnd.core.events.encounter_events.TurnEndEvent
dnd.core.events.encounter_events.RoundEndEvent
dnd.core.events.encounter_events.EncounterEndEvent
```

The retained exact `Event` route is only the existing E1/E2
intentionally-silent base-event contract. Provenance values are only
`semantic key -> (generation_id, source_index, existing ReadPath)`; completion
sources update references, hidden changes do not change joined party scene
memory, and reduction performs no live-world query or event transition.
Controlled sensory grants resolve their cause in the captured archive, require
exactly one same-lineage top-level completion at or after the cause, and attach
late disclosure to the original sensory source slot. Missing or wrong-lineage
causative terminals fail before reducer state commits. All reducer scene grants
in this checkpoint use that strict terminal-resolution path.

Added public proofs:

```text
tests/engine/test_event_knowledge_context.py::test_slice_3_3_hidden_committed_change_updates_reference_without_party_memory
tests/engine/test_event_knowledge_context.py::test_slice_3_3_sensory_grant_resolves_one_closed_causative_terminal
tests/engine/test_event_knowledge_context.py::test_slice_3_3_missing_causative_terminal_is_fatal_without_advancing
tests/engine/test_event_knowledge_context.py::test_slice_3_3_reacquisition_keeps_old_source_and_uses_new_batch_disclosure
tests/engine/test_event_knowledge_context.py::test_slice_3_3_wrong_lineage_causative_terminal_is_fatal
tests/architecture/test_event_knowledge_context_architecture.py::test_slice_3_3_has_one_exact_manifest_for_the_frozen_event_classes
tests/architecture/test_event_knowledge_context_architecture.py::test_slice_3_3_reducer_has_no_live_world_or_second_policy_source
```

These extend the existing public two-observer loss/join/light/nonvisual
contact, hidden/unadmitted, detached replay, listener, cursor, generation,
reordered, split, duplicate, and ambiguous-terminal proofs. No private
world access, mock, second policy/provenance table, or compatibility path is
used.

Final validation after the final Slice 3.3 code/test bytes:

- Focused event-knowledge plus Slice 3.3 architecture: `40 passed in 8.48s`.
- Complete `tests/architecture`: `54 passed in 86.42s`.
- Accepted E1/E2/Slice 3.2 path command plus unchanged encounter fixture and
  complete architecture: `283 passed in 322.82s (0:05:22)`.
- Collection filtered `^tests/.*::`, sorted C-bytewise, deduplicated, and
  added one terminal LF: `283` unique IDs, normalized SHA-256
  `13aad1149df4f069bfd2a174a5afdad990f6ec29467a444bf3ab768b449a7cc8`.
  This is the accepted 277-node union plus six net Slice 3.3 proof nodes.
- Compile/py_compile: exit `0`; scoped `git diff --check`: exit `0` with only
  the pre-existing accepted LF/CRLF normalization warning for
  `dnd/blocks/sensory.py`; no changed-file trailing whitespace.
- Existing no-local-import/canonical-owner and stale-heuristic,
  caller-injection, duplicate-helper, wrapper, live-world, and second-policy
  source gates were green/empty.

Current governed raw-byte SHA-256 values:

```text
7293a765b25b4111c8f2b2bdbabef36d809c2a94b779dbc3a67769a2fcb2732f  dnd/event_reduction.py
f9347cdeb21591b051014b06a90d4d5604904abdfe1c0d40d4d55d2c7d433026  dnd/core/events/knowledge.py
9ccca8d2ec117b312f51589020123b177eb1f5a15e719f0fc6e707fc8ed96dff  dnd/blocks/sensory.py (accepted, unchanged)
993351fa2403e3836f5ba953204d416fa20b2bf51ed1bc4fcaf59d7538222b48  tests/engine/test_event_knowledge_context.py
2ab491e4989b5b9a7fde0ae46b595e8f70f40048f426a871f858c757bfc6116b  tests/architecture/test_event_knowledge_context_architecture.py
8dd2d36c05dcbd7ab649d3a0d8b717533d102dc9861ceb1238e5947573294186  tests/engine/test_event_knowledge_scripted_encounter.py (accepted, unchanged)
```

Governing authority SHA-256 values verified:

```text
aaf75e26e3b1e13419caf3d0b7e8346ad8a86531bc155b90f6d37767a8328c98  DND_EVENT_KNOWLEDGE_CONTEXT_E3_E6_IMPLEMENTATION_PLAN_2026-08-27.md
7856a537f0b75063fe5bcb012fd7d020b2f92a1e018c17d1ccf6b5e830605c21  DND_EVENT_KNOWLEDGE_CONTEXT_REDUCTION_PLAN_2026-08-27.md
3f98f0b926fce8e9662c5718c01aa863734a563897bebe0b403173d8eba0a9ad  DND_EVENT_KNOWLEDGE_CONTEXT_IMPLEMENTATION_PLAN_2026-08-27.md
8e83dde4916ca3a6a4691bd9b25f720d3e381fe49e6458d4c0800007f9b390b9  DND_PYGAME_SCRIPTED_ENCOUNTER_MVP_IMPLEMENTATION_PLAN_2026-08-27.md
```

Final physical checkpoint status:

`SLICE_3_3_DISCLOSURE_COMPLETE — READY_FOR_COORDINATOR_REVIEW`

## Slice 3.3 final superseding correction checkpoint

This is the physical-final Slice 3.3 checkpoint and supersedes the prior
Slice 3.3 metadata. The exact concrete-class manifest now uses explicit
family selectors for all 20 frozen classes, including symmetric encounter
boundaries. Uncontrolled located step movement exposes only `committed`,
`trajectory`, and event-time-known endpoint/elevation/disclosed geometry;
path index, total path length, movement cost, and provocation policy remain
unreadable. Condition removal no longer admits application disposition, and
spell admission does not admit mutable `save_roll`. Connector provenance
uses exact nested connector source paths and no pseudo semantic roots.

The final public proof set includes:

```text
tests/engine/test_event_knowledge_context.py::test_committed_step_exposes_only_event_time_known_geometry
tests/engine/test_event_knowledge_context.py::test_slice_3_3_family_masks_keep_private_perceived_fields_unknown
tests/engine/test_event_knowledge_context.py::test_slice_3_3_controlled_masks_admit_owned_roll_and_condition_consequences
tests/engine/test_event_knowledge_context.py::test_slice_3_3_boundary_roll_and_removal_masks_are_explicit
```

The boundary proof directly constructs and reads RoundStartEvent,
RoundEndEvent, TurnStartEvent, TurnEndEvent, DamageRollResultEvent, and
ConditionRemovalEvent, proving public identity/outcomes while roster,
turn-resource/usage, perceived damage packets, private save/HP fields, and
the live condition remain unavailable. The real-engine wall/light,
invisibility/special-sense, movement-step, provenance, two-observer loss,
and exact causative-terminal proofs remain callback-bound and public.

Final validation after the last production/test edits:

- Focused corrected policy/provenance group plus the event-knowledge
  architecture gate: `16 passed in 5.52s`.
- Exact ten-selector union recollection: `300` sorted unique node IDs with
  normalized SHA-256
  `232cdee29b051e56fda3a0fbf94ba8c813549c93e25657c3ac9284fe57832351`.
- Exact newline-safe execution of that sorted node list: `300 passed in
  121.96s (0:02:01)`.
- Compileall: exit `0`; `git diff --check`: exit `0`, with only the existing
  accepted LF/CRLF normalization warning for `dnd/blocks/sensory.py`.
- Hard-cut scans for the retired blind mask/resolution helper, caller-class
  injection, merged-batch heuristic, duplicate helper, compatibility wrapper,
  and second policy source are empty. No Slice 4 work or manifest was started.

Current final governed raw-byte SHA-256 values:

```text
243248b8e7756b0af06e6340d2cb95391733d3e0107cae4efdbcf19e73567e71  dnd/event_reduction.py
f9347cdeb21591b051014b06a90d4d5604904abdfe1c0d40d4d55d2c7d433026  dnd/core/events/knowledge.py
9ccca8d2ec117b312f51589020123b177eb1f5a15e719f0fc6e707fc8ed96dff  dnd/blocks/sensory.py (accepted, unchanged)
3e9860172f867066b424214ed72f3797528b09257edba5d61526fc7ada86fcd9  tests/engine/test_event_knowledge_context.py
d43dd829e7e6d43397b1a39d9af7f7c6ae5024c3f75e16152a68b6deb80dcd1e  tests/architecture/test_event_knowledge_context_architecture.py
8dd2d36c05dcbd7ab649d3a0d8b717533d102dc9861ceb1238e5947573294186  tests/engine/test_event_knowledge_scripted_encounter.py (accepted, unchanged)
```

Final physical status:

`SLICE_3_3_DISCLOSURE_COMPLETE — READY_FOR_COORDINATOR_REVIEW`

## Slice 3.3 superseding step/family policy correction and revalidation

This physical-end checkpoint supersedes the preceding Slice 3.3 checkpoint.
The uncontrolled `StepMovementEvent` mask now admits only the public
`committed` and `trajectory` paths, plus event-time-known endpoint/elevation
paths and a disclosed segment when every segment position is known. It does
not admit `path_index`, `total_path_length`, `movement_cost`, or
`provocation_policy` merely because the occurrence is located. Controlled
steps retain their owned movement fields.

The condition selector admits `application_disposition` only for
`ConditionApplicationEvent`; `ConditionRemovalEvent` admits `expired`, its
condition identity, and controlled target consequences without exposing the
condition object. Spell admission does not include mutable `save_roll`.
World-initialized connector provenance uses each connector field's exact
nested source ReadPath as its semantic key; no pseudo root `kind` or
`authored_id` key is created. Encounter start/end use the same
identity/occurrence gate and never reveal the full roster.

The direct public policy-read proof now covers the previously unconstructed
exact classes `RoundStartEvent`, `RoundEndEvent`, `TurnStartEvent`,
`TurnEndEvent`, `DamageRollResultEvent`, and `ConditionRemovalEvent`:

```text
tests/engine/test_event_knowledge_context.py::test_slice_3_3_boundary_roll_and_removal_masks_are_explicit
```

It proves public round/turn identity while turn resources and usage remain
unknown, hides perceived damage packets while admitting controlled roll
fields, and exposes removal identity/expiry plus controlled consequences
without exposing the live condition. The step proof also now covers both
event-time-located and controlled cases with exact Known/Unknown assertions.

Final validation after the correction:

- Focused policy/provenance/engine proof selectors plus the event-knowledge
  architecture gate: `16 passed in 5.52s`.
- Exact ten-selector collection input (the accepted E1/E2/Slice 3.2 paths,
  unchanged scripted encounter, and complete architecture) produced `300`
  sorted unique node IDs using the `^tests/.*::`, C-bytewise sort,
  deduplication, one-terminal-LF algorithm. Normalized node SHA-256:
  `232cdee29b051e56fda3a0fbf94ba8c813549c93e25657c3ac9284fe57832351`.
- The exact sorted node list was executed as newline-safe pytest arguments:
  `300 passed in 121.96s (0:02:01)`.
- Compileall for all changed/new active Python files: exit `0`.
- `git diff --check`: exit `0`; only the pre-existing LF/CRLF normalization
  warning for accepted dirty `dnd/blocks/sensory.py` was emitted.
- Retired blind `_base_knowledge_mask` and `_resolution_roll_mask`, caller
  class injection, merged-batch heuristic, duplicate helper, and
  compatibility-wrapper scans are empty. The remaining
  `capture_queue_range` matches are the existing public detached-archive
  capture seam in the reducer/tests, not a live-world query.

Current governed raw-byte SHA-256 values:

```text
243248b8e7756b0af06e6340d2cb95391733d3e0107cae4efdbcf19e73567e71  dnd/event_reduction.py
f9347cdeb21591b051014b06a90d4d5604904abdfe1c0d40d4d55d2c7d433026  dnd/core/events/knowledge.py
9ccca8d2ec117b312f51589020123b177eb1f5a15e719f0fc6e707fc8ed96dff  dnd/blocks/sensory.py (accepted, unchanged)
3e9860172f867066b424214ed72f3797528b09257edba5d61526fc7ada86fcd9  tests/engine/test_event_knowledge_context.py
d43dd829e7e6d43397b1a39d9af7f7c6ae5024c3f75e16152a68b6deb80dcd1e  tests/architecture/test_event_knowledge_context_architecture.py
8dd2d36c05dcbd7ab649d3a0d8b717533d102dc9861ceb1238e5947573294186  tests/engine/test_event_knowledge_scripted_encounter.py (accepted, unchanged)
```

No Slice 3.3 manifest was created because that artifact remains authorized
only in a later certification slice. No Slice 4 work was started.
Final physical status:

`SLICE_3_3_DISCLOSURE_COMPLETE — READY_FOR_COORDINATOR_REVIEW`

## Slice 3.3 bounded family-mask repair and public read proofs

This final Slice 3.3 checkpoint supersedes the earlier 283-node checkpoint
claims. The one existing `_CONCRETE_EVENT_MANIFEST` remains the sole policy
table for the same 20 exact Slice 3.1 concrete classes. Every row now names
an explicit family selector; no manifest row uses the former blind
`_base_knowledge_mask` fallback. The selectors are:

```text
WorldInitializedEvent       _world_initialized_mask
EntityCreatedEvent          _entity_created_mask
SpatialChangeEvent          _spatial_change_mask
SensoryUpdateEvent          _sensory_update_mask
EncounterStartEvent         _encounter_boundary_mask
RoundStartEvent             _round_boundary_mask
TurnStartEvent              _turn_boundary_mask
MovementEvent               _movement_action_mask
StepMovementEvent           _step_movement_mask
AttackEvent                 _attack_mask
AttackD20RollResultEvent    _attack_roll_mask
DamageRollResultEvent       _damage_roll_mask
TakeDamageEvent             _take_damage_mask
DamageAppliedEvent          _damage_applied_mask
ConditionApplicationEvent   _condition_lifecycle_mask
ConditionRemovalEvent      _condition_lifecycle_mask
SpellEvent                  _spell_action_mask
TurnEndEvent                _turn_boundary_mask
RoundEndEvent               _round_boundary_mask
EncounterEndEvent           _encounter_boundary_mask
```

Encounter start and end use the same identity/occurrence gate and never
admit the complete combatant roster. Movement separates public outcome from
requested/objective route, path, cost, and controller detail. Resolution
rolls, damage consequences, condition consequences, and spell save details
are independently gated: public outcomes remain readable, while controller,
roll, resulting-HP, and save mechanics are controlled-owner fields. The
existing semantic-key provenance retains only generation/source-index/existing
ReadPath references; subjective light remains a SensoryUpdateEvent fact.

Added public read proofs in
`tests/engine/test_event_knowledge_context.py`:

```text
test_slice_3_3_family_masks_keep_private_perceived_fields_unknown
test_slice_3_3_controlled_masks_admit_owned_roll_and_condition_consequences
```

The perceived-family proof covers symmetric encounter boundaries, enemy
movement, public damage amount versus resulting HP, and public spell identity
/ save outcome versus save DC/bonus. The controlled proof covers an exact
attack d20 result, condition identity/AC consequence, and controlled damage
HP/cap consequence. All assertions use `Known`/`Unknown` public knowledge
reads and exact concrete event classes; no live-world access, private
reducer state, mock, or caller-invented batch is used. The existing real-engine
wall/light/boundary and invisibility/special-sense/step proofs continue to
attach `EventReducer.on_event_batch` only through the public
`EventQueue.add_on_event_batch_callback` boundary.

Final current validation after these production/test bytes:

- Focused `tests/engine/test_event_knowledge_context.py` plus
  `tests/architecture/test_event_knowledge_context_architecture.py`:
  `55 passed in 4.85s`.
- Exact accepted path command, including complete `tests/architecture`:
  `299 passed in 115.03s (0:01:55)`.
- Recollected exact selector input (the ten paths used by the accepted
  E1/E2/Slice 3.2 union plus the unchanged scripted encounter) with
  `--collect-only -q`; filter `^tests/.*::`, C-bytewise sort, unique, and one
  terminal LF produced `299` unique node IDs and normalized SHA-256
  `241fcac683dfd0c8b549003a95e157f1bc7839ab8a51f553a76fd88cc1d7c287`.
  The exact sorted node list was passed as individual newline-safe pytest
  arguments and executed byte-identically: `299 passed in 114.64s
  (0:01:54)`.
- Complete architecture is included in the exact union and was green;
  focused architecture/policy tests are included in the `55 passed` result.
- Compileall for all changed/new active Python files exited `0`.
- `git diff --check` exited `0`; only the existing LF/CRLF normalization
  warning for accepted dirty `dnd/blocks/sensory.py` was emitted.
- Retired `_base_knowledge_mask`, obsolete resolution helper, caller-class
  injection, merged-batch heuristic, duplicate helper, compatibility-wrapper,
  live-world, and second-policy scans are empty.

Current governed active-file raw-byte SHA-256 values:

```text
2b4508ba1fe79309246f956e23c61560469f142169b735d862661bffdba858e8  dnd/event_reduction.py
f9347cdeb21591b051014b06a90d4d5604904abdfe1c0d40d4d55d2c7d433026  dnd/core/events/knowledge.py
9ccca8d2ec117b312f51589020123b177eb1f5a15e719f0fc6e707fc8ed96dff  dnd/blocks/sensory.py
02b28e124d163baedace1bbbb74fa08ffa2132ccae4c0ae33c8a3dd95f31523f  tests/engine/test_event_knowledge_context.py
d43dd829e7e6d43397b1a39d9af7f7c6ae5024c3f75e16152a68b6deb80dcd1e  tests/architecture/test_event_knowledge_context_architecture.py
8dd2d36c05dcbd7ab649d3a0d8b717533d102dc9861ceb1238e5947573294186  tests/engine/test_event_knowledge_scripted_encounter.py (accepted, unchanged)
```

No Slice 3.3 manifest is created because the accepted plan authorizes that
artifact only in a later certification slice. No Slice 4 work was started.
Final physical status:

`SLICE_3_3_DISCLOSURE_COMPLETE — READY_FOR_COORDINATOR_REVIEW`

## Slice 3.3 final superseding repair checkpoint

This is the final physical Slice 3.3 checkpoint. It supersedes all earlier
Slice 3.3 metadata and records the current bytes after the step/family policy
repair. The single 20-class concrete manifest uses explicit selectors for
every row. Uncontrolled located steps expose only `committed`, `trajectory`,
and event-time-known endpoint/elevation/disclosed geometry; path index, total
path length, movement cost, and provocation policy remain unreadable.
Condition removal admits identity and `expired` plus controlled consequences,
but not `application_disposition` or the live condition. Spell admission does
not include mutable `save_roll`. Connector provenance uses exact nested source
paths and no pseudo semantic roots. Encounter start/end use the same
identity/occurrence gate without roster disclosure.

The exact added/extended public proofs are:

```text
tests/engine/test_event_knowledge_context.py::test_committed_step_exposes_only_event_time_known_geometry
tests/engine/test_event_knowledge_context.py::test_slice_3_3_family_masks_keep_private_perceived_fields_unknown
tests/engine/test_event_knowledge_context.py::test_slice_3_3_controlled_masks_admit_owned_roll_and_condition_consequences
tests/engine/test_event_knowledge_context.py::test_slice_3_3_boundary_roll_and_removal_masks_are_explicit
```

The boundary proof directly covers RoundStartEvent, RoundEndEvent,
TurnStartEvent, TurnEndEvent, perceived and controlled DamageRollResultEvent,
and perceived and controlled ConditionRemovalEvent. It proves public
identity/outcomes while turn resources/usage, perceived damage packets,
private save/HP fields, application disposition, and condition objects remain
unreadable. Existing callback-bound real-engine wall/light,
invisibility/special-sense/step, provenance, loss/reacquisition, and exact
causative-terminal proofs remain unchanged.

Final validation after the last production/test edits:

- Corrected focused policy/provenance group plus event-knowledge architecture
  gate: `16 passed in 5.52s`.
- Exact ten-selector collection: `300` sorted unique node IDs; algorithm is
  filter `^tests/.*::`, C-bytewise sort, deduplicate, one terminal LF.
- Normalized node SHA-256:
  `232cdee29b051e56fda3a0fbf94ba8c813549c93e25657c3ac9284fe57832351`.
- Exact newline-safe execution of the collected node list: `300 passed in
  121.96s (0:02:01)`.
- Compileall for changed active Python files: exit `0`.
- `git diff --check`: exit `0`; only the pre-existing LF/CRLF normalization
  warning for accepted dirty `dnd/blocks/sensory.py`.
- Retired blind-mask/resolution helper, injected class, merged-batch heuristic,
  duplicate helper, compatibility-wrapper, and second-policy scans: empty.
- No Slice 4 work or Slice 3.3 manifest was started.

Current governed raw-byte SHA-256 values:

```text
243248b8e7756b0af06e6340d2cb95391733d3e0107cae4efdbcf19e73567e71  dnd/event_reduction.py
f9347cdeb21591b051014b06a90d4d5604904abdfe1c0d40d4d55d2c7d433026  dnd/core/events/knowledge.py
9ccca8d2ec117b312f51589020123b177eb1f5a15e719f0fc6e707fc8ed96dff  dnd/blocks/sensory.py (accepted, unchanged)
3e9860172f867066b424214ed72f3797528b09257edba5d61526fc7ada86fcd9  tests/engine/test_event_knowledge_context.py
d43dd829e7e6d43397b1a39d9af7f7c6ae5024c3f75e16152a68b6deb80dcd1e  tests/architecture/test_event_knowledge_context_architecture.py
8dd2d36c05dcbd7ab649d3a0d8b717533d102dc9861ceb1238e5947573294186  tests/engine/test_event_knowledge_scripted_encounter.py (accepted, unchanged)
```

Final physical status:

`SLICE_3_3_DISCLOSURE_COMPLETE — READY_FOR_COORDINATOR_REVIEW`

## Slice 3.3 residual step/spell policy correction checkpoint

This physical-tail checkpoint supersedes the immediately preceding Slice 3.3
validation metadata only for the two bounded policy corrections requested by
the coordinator. No production/test scope outside the existing Slice 3.3
manifest was opened, and no Slice 4 work was started.

The controlled `StepMovementEvent` policy now retains `committed` and
`trajectory`, plus exact event-time-known endpoints/elevations and authorized
`disclosed_path`; it does not admit `path_index`, `total_path_length`,
`movement_cost`, or `provocation_policy` for any party, including the
controlled mover. The public step proof asserts all four are
`Unknown(PATH_NOT_READABLE)` for both perceived and controlled deliveries.

The `_spell_action_mask` no longer admits mutable `save_roll`, including for a
controlled target. The sole `SpellEvent` manifest row likewise excludes
`save_roll`; the controlled public spell proof asserts `save_dc` and
`save_bonus` are readable while `save_roll` is
`Unknown(PATH_NOT_READABLE)`. The test fixture's `save_roll` occurrence is
only the constructed negative-proof input and assertion.

Validation after this final test-byte/selector correction:

- Corrected step/family/controlled-policy selectors plus the event-knowledge
  architecture gate: `13 passed in 5.27s`.
- Full `tests/engine/test_event_knowledge_context.py` together with the full
  architecture lane: `101 passed in 30.61s`.
- Full `tests/architecture`: `55 passed in 30.50s`.
- Exact ten-selector collection, using filter `^tests/.*::`, C-bytewise sort,
  deduplication, and one terminal LF: `300` sorted unique node IDs;
  normalized SHA-256
  `232cdee29b051e56fda3a0fbf94ba8c813549c93e25657c3ac9284fe57832351`.
- Exact newline-safe execution of that collected node list: `300 passed in
  121.87s (0:02:01)`.
- Compileall for the changed active Python files: exit `0`.
- `git diff --check`: exit `0`; the only output is the pre-existing
  LF/CRLF normalization warning for accepted dirty
  `dnd/blocks/sensory.py`.
- Retired blind-mask/resolution helper, injected-class,
  merged-batch-heuristic, duplicate-helper, compatibility-wrapper, and
  second-policy scans: no matches. The only remaining `save_roll` matches are
  the deliberate test negative proof described above.

Current governed raw-byte SHA-256 values:

```text
b38263ce6071f60b99ea204d65a7ff91a5bfc95e6dc45179f90327ba8a482d7a  dnd/event_reduction.py
f9347cdeb21591b051014b06a90d4d5604904abdfe1c0d40d4d55d2c7d433026  dnd/core/events/knowledge.py
9ccca8d2ec117b312f51589020123b177eb1f5a15e719f0fc6e707fc8ed96dff  dnd/blocks/sensory.py (accepted, unchanged)
51a9cf04fa094c4fd7023bd3a45577e63635831629b906506d0238e401ff552b  tests/engine/test_event_knowledge_context.py
d43dd829e7e6d43397b1a39d9af7f7c6ae5024c3f75e16152a68b6deb80dcd1e  tests/architecture/test_event_knowledge_context_architecture.py
8dd2d36c05dcbd7ab649d3a0d8b717533d102dc9861ceb1238e5947573294186  tests/engine/test_event_knowledge_scripted_encounter.py (accepted, unchanged)
```

No Slice 3.3 manifest is authorized at this checkpoint because the accepted
plan authorizes that artifact only in a later certification slice. No Slice 4
work was started.

Final physical status:

`SLICE_3_3_DISCLOSURE_COMPLETE — READY_FOR_COORDINATOR_REVIEW`

## Slice 4.0 presentation completion and shared plain-text formatting checkpoint

Authorization and scope:

- Governing implementation plan: `DND_EVENT_KNOWLEDGE_CONTEXT_E3_E6_IMPLEMENTATION_PLAN_2026-08-27.md`, raw SHA-256 `aaf75e26e3b1e13419caf3d0b7e8346ad8a86531bc155b90f6d37767a8328c98`.
- This is Slice 4.0 only. Slice 5 was not started. No excluded server, SDK,
  transport, renderer, pygame, content, game, or asynchronous scope was
  opened.
- The existing `dnd/event_reduction.py` remains the only reduction module and
  `_CONCRETE_EVENT_MANIFEST` remains the sole exact-class policy table. No new
  event/view/DTO/log model, wrapper hierarchy, formatter class, service,
  manager, cache, compatibility path, or second policy table was added.

Implementation checkpoint:

- Extended each of the 20 frozen exact concrete-class manifest rows from the
  accepted eight-value Slice 3.3 policy shape with one formatter callable.
  Exact-class dispatch remains manifest-bound; shared family helpers are used
  only through exact-class wrapper callables in those rows.
- Each formatter consumes only its `EventKnowledge[ExactEvent]` view and reads
  through `knowledge.read`/`knowledge.known_items`. It does not access live
  world state, event methods, combat-log data, queues, registries, or copied
  objective prose.
- `format_objective_event` wraps the same captured event with
  `KnowledgeMask.top()`, and `format_subjective_delivery` invokes the same
  manifest formatter on the delivery knowledge. The public proof verifies
  captured-event identity, exact class, UUID/lineage/phase alignment, and
  objective/subjective text equality for a fully readable occurrence.
- Known occurrences with no specialized readable fields produce the visible
  base-path fallback; hidden occurrences produce no party delivery or text.
  A child whose parent is hidden is formatted as a local text root. Unknown
  concrete classes fail with the existing policy diagnostic rather than
  falling through to a formatter.
- The real scripted encounter proof formats the captured public stream and
  routes subjective deliveries through the existing PartyKnowledge/event-batch
  boundary. It records nonempty objective/subjective rows and checks their
  real captured identity, class, UUID, lineage, and phase. The focused unit
  proofs cover shared formatter identity, hidden-parent local roots,
  known-base fallback, and hidden-occurrence silence.

Exact changed paths for this Slice 4.0 checkpoint:

```text
dnd/event_reduction.py
tests/engine/test_event_knowledge_context.py
tests/engine/test_event_knowledge_scripted_encounter.py
tests/architecture/test_event_knowledge_context_architecture.py
```

The accepted dirty `dnd/blocks/sensory.py` and the governing documents were
not edited in this slice.

Validation commands and results:

- Focused Slice 4 formatter proofs, real scripted encounter, and formatter
  architecture gate: `16 passed in 6.82s`.
- Full `tests/engine/test_event_knowledge_context.py`: `50 passed in 4.08s`.
- Complete `tests/architecture`: `56 passed in 30.37s`.
- Exact selector inputs for the integrated cut, in command order:

  ```text
  tests/engine/test_event_knowledge_context.py
  tests/engine/test_event_knowledge_scripted_encounter.py
  tests/engine/test_objective_state.py
  tests/engine/test_direct_scenario_deployment.py
  tests/engine/test_event_wire_visibility_contract.py
  tests/engine/test_move_settlement.py
  tests/engine/test_senses_light_stealth.py
  tests/engine/test_combat_actions.py
  tests/engine/test_action_cost_and_position_commit.py
  tests/architecture
  ```

  Collection used `-p no:cacheprovider --collect-only -q`, retained only
  `^tests/.*::` rows, sorted C-bytewise, deduplicated, and wrote one terminal
  LF. The resulting exact node list contained `305` sorted unique IDs and has
  normalized SHA-256
  `dc9b9c12e9374e6fc74cddaaa7f33c907e065944450da456648416e1db00c41e`.
  The exact newline-safe collected list was executed byte-identically:
  `305 passed in 197.96s (0:03:17)`.
- The accepted Slice 3.3 cut was 300 nodes. The five exact added nodes in
  this in-path Slice 4.0 union are:

  ```text
  tests/engine/test_event_knowledge_context.py::test_slice_4_objective_and_subjective_formatting_share_the_captured_event
  tests/engine/test_event_knowledge_context.py::test_slice_4_visible_child_with_hidden_parent_is_a_local_text_root
  tests/engine/test_event_knowledge_context.py::test_slice_4_known_base_only_occurrence_has_visible_fallback_text
  tests/engine/test_event_knowledge_context.py::test_slice_4_hidden_occurrence_has_no_subjective_badge_or_text
  tests/architecture/test_event_knowledge_context_architecture.py::test_slice_4_formatters_are_manifest_bound_and_detached
  ```

- Compileall for all four changed active Python files: exit `0`.
- `git diff --check`: exit `0`; the only output is the pre-existing
  LF/CRLF normalization warning for accepted dirty
  `dnd/blocks/sensory.py`.
- Production hard-cut scan for blind masks, injected E2 classes,
  merged-batch heuristics, duplicate helpers, compatibility wrappers,
  parallel policy markers, `CanonicalEventView`, `FactAtom`, event lookup,
  and production `save_roll`: clean. The architecture gate retains the
  forbidden spellings as its explicit negative assertions; these are test
  diagnostics, not production references.
- A first focused attempt exposed only the architecture self-check's overly
  literal requirement that every exact wrapper contain a direct read. The
  gate was bounded to accept the exact wrapper delegation to the shared
  manifest-bound reader; the rerun above is green. No production behavior
  defect or scope expansion was found.

Current governed raw-byte SHA-256 values:

```text
c8f6f91cba73e7188e1286654d208dab3495ffb3f48445522bb269d0e2c58d0a  dnd/event_reduction.py
f9347cdeb21591b051014b06a90d4d5604904abdfe1c0d40d4d55d2c7d433026  dnd/core/events/knowledge.py
9ccca8d2ec117b312f51589020123b177eb1f5a15e719f0fc6e707fc8ed96dff  dnd/blocks/sensory.py (accepted, unchanged)
89057116c411b877e1ea8d6cd53b3ed48f3a8b1bed75f25ed28a0167f56de27e  tests/engine/test_event_knowledge_context.py
6dfa578118df898c8a67fca459372052332d2b70a25181082967ef89ee83714d  tests/engine/test_event_knowledge_scripted_encounter.py
984d4c2ac1bf548716d3a48f1e81f45238472afcfd859ea07942341e8a4ab418  tests/architecture/test_event_knowledge_context_architecture.py
```

No Slice 4 manifest was created; the plan reserves final manifest work for a
later certification slice. The physical final status for this checkpoint is:

`SLICE_4_0_ADMISSION_AND_TEXT_COMPLETE — READY_FOR_COORDINATOR_REVIEW`

## Slice 4.0 bounded presentation-classification and delivery-tree correction

This supersedes the preceding Slice 4.0 checkpoint and invalidates its
305-node result because the formatter/tree test bytes changed. It remains
Slice 4.0 only; Slice 5 and all excluded scopes remain unopened.

Corrections:

- The existing fifth manifest value is now an operative reviewed presentation
  classification. Router admission rejects a missing/empty classification,
  an `intentionally_silent` classification returns no delivery, and the
  formatter boundary rejects a missing or intentionally silent exact row.
  Every one of the 20 frozen concrete classes has exactly one nonempty
  classification and one callable formatter in the same manifest. The base
  `Event` route is explicitly silent through
  `BASE_EVENT_INTENTIONALLY_SILENT_REASON`; its party delivery is absent and
  formatting raises that named reason. Unknown concrete classes remain fatal.
- Added `format_subjective_delivery_tree`, returning only ordered plain text
  strings. It reads each delivery's existing UUID, parent UUID, and parent
  lineage through `EventKnowledge`; delivered children attach only to a
  delivered parent with matching real identity/lineage, and a missing or
  mismatched parent remains a local root. No identity is synthesized or
  reparented. Each rendered row's `children_count` is computed only from the
  delivered child rows.
- The public tree proof uses one real parent with two real child events, hides
  one child through the existing party policy, and verifies the objective
  parent has both child UUIDs while the subjective tree has one indented child
  and `children_count=1`. The existing hidden-parent local-root proof remains
  green.
- Replaced the architecture formatter self-check's literal delegation string
  test with a bounded AST call-graph walk. Every manifest formatter must
  transitively reach `knowledge.read` or `knowledge.known_items`; every
  traversed formatter/helper is checked for snapshot, live-world/event,
  combat-log/data, queue, registry, and handler access. The gate also asserts
  exactly 20 unique operative row classifications and the explicit base-event
  silence reason.

Validation and repair record:

- The first correction-focused run exposed three bounded test-gate defects:
  an added base Event shifted the expected unknown-class source index, Event
  Queue parent propagation made the nominal hidden child visible, and the AST
  call graph rejected harmless local string/list operations. The test setup
  was corrected to assert the actual source index, register the hidden child
  before its parent so its public evidence remains absent, and restrict the
  AST attribute assertion to knowledge reads. No production behavior change
  was required for these test failures.
- Corrected role/base-silence/tree/architecture selectors: `5 passed in
  4.59s`.
- Full event-knowledge modules (`test_event_knowledge_context.py` and
  `test_event_knowledge_scripted_encounter.py`): `52 passed in 5.65s`.
- Complete `tests/architecture`: `56 passed in 31.72s`.
- Exact selector inputs remained the ten paths recorded in the preceding
  Slice 4.0 checkpoint. Collection retained `^tests/.*::` rows, sorted
  C-bytewise, deduplicated, and wrote one terminal LF. Recollection produced
  `306` sorted unique node IDs with normalized SHA-256
  `ea292f4848e94dd0996fb4a6483b86a726e01d280fbf2f58c62913d4e76313f5`.
  The exact collected list was executed byte-identically: `306 passed in
  119.29s (0:01:59)`.
- Added one exact node to the previous 305-node Slice 4 union:

  ```text
  tests/engine/test_event_knowledge_context.py::test_slice_4_subjective_tree_groups_real_parent_and_counts_delivered_children
  ```

- Compileall for all changed active Python files: exit `0`.
- `git diff --check`: exit `0`; only the pre-existing LF/CRLF normalization
  warning for accepted dirty `dnd/blocks/sensory.py` was reported.
- Production hard-cut scan for blind masks, injected classes, merged-batch
  heuristics, duplicate helpers, compatibility wrappers, parallel policy
  markers, `CanonicalEventView`, `FactAtom`, event lookup, and `save_roll`:
  clean. No new module, event path, DTO, or policy table was added.

Current governed raw-byte SHA-256 values:

```text
e2616a12e78a9096237a122044821f3379779468be20a348c76589069e9e8d13  dnd/event_reduction.py
f9347cdeb21591b051014b06a90d4d5604904abdfe1c0d40d4d55d2c7d433026  dnd/core/events/knowledge.py
9ccca8d2ec117b312f51589020123b177eb1f5a15e719f0fc6e707fc8ed96dff  dnd/blocks/sensory.py (accepted, unchanged)
fd61017666b8407769d328f0426380ec3afcadd227da7df69de88e700e8f7bed  tests/engine/test_event_knowledge_context.py
6dfa578118df898c8a67fca459372052332d2b70a25181082967ef89ee83714d  tests/engine/test_event_knowledge_scripted_encounter.py
1cb901cf3f772f893a0a599a24bb2ebd037fa891acd30a28ddd389cc5e0cdfb5  tests/architecture/test_event_knowledge_context_architecture.py
```

The Slice 4.0 manifest remains intentionally uncreated because final manifest
work is reserved for a later certification slice. Physical final status:

`SLICE_4_0_ADMISSION_AND_TEXT_COMPLETE — READY_FOR_COORDINATOR_REVIEW`

## Slice 5.0 deterministic async presentation-boundary checkpoint

This Slice 5.0 checkpoint is test-only. The only new implementation file is
`tests/engine/test_event_knowledge_async_boundary.py`; no production file and
no previously accepted test file was changed. The existing accepted Slice 4
ledger history above is preserved.

### Governing and accepted bytes

- Slice 5 governing plan:
  `DND_EVENT_KNOWLEDGE_CONTEXT_E3_E6_IMPLEMENTATION_PLAN_2026-08-27.md`,
  SHA-256 `aaf75e26e3b1e13419caf3d0b7e8346ad8a86531bc155b90f6d37767a8328c98`.
- Reduction authority:
  `DND_EVENT_KNOWLEDGE_CONTEXT_REDUCTION_PLAN_2026-08-27.md`,
  SHA-256 `7856a537f0b75063fe5bcb012fd7d020b2f92a1e018c17d1ccf6b5e830605c21`.
- E1/E2 implementation authority:
  `DND_EVENT_KNOWLEDGE_CONTEXT_IMPLEMENTATION_PLAN_2026-08-27.md`,
  SHA-256 `3f98f0b926fce8e9662c5718c01aa863734a563897bebe0b403173d8eba0a9ad`.
- Scripted-encounter authority:
  `DND_PYGAME_SCRIPTED_ENCOUNTER_MVP_IMPLEMENTATION_PLAN_2026-08-27.md`,
  SHA-256 `8e83dde4916ca3a6a4691bd9b25f720d3e381fe49e6458d4c0800007f9b390b9`.

Accepted production/test bytes verified at this checkpoint:

```text
e2616a12e78a9096237a122044821f3379779468be20a348c76589069e9e8d13  dnd/event_reduction.py
f9347cdeb21591b051014b06a90d4d5604904abdfe1c0d40d4d55d2c7d433026  dnd/core/events/knowledge.py
9ccca8d2ec117b312f51589020123b177eb1f5a15e719f0fc6e707fc8ed96dff  dnd/blocks/sensory.py
fd61017666b8407769d328f0426380ec3afcadd227da7df69de88e700e8f7bed  tests/engine/test_event_knowledge_context.py
6dfa578118df898c8a67fca459372052332d2b70a25181082967ef89ee83714d  tests/engine/test_event_knowledge_scripted_encounter.py
1cb901cf3f772f893a0a599a24bb2ebd037fa891acd30a28ddd389cc5e0cdfb5  tests/architecture/test_event_knowledge_context_architecture.py
23f36c8d9d3df3fd2001ccfc69645d7007522c2bc80efd7ee6b0fcad0bef5a47  tests/engine/test_event_knowledge_async_boundary.py
```

### Async boundary implementation and diagnosis

The new proof uses exactly two local queues: `game_to_presentation` carrying
the real `EventBatch` and `presentation_to_game` carrying test-local receipt
tuples or worker exceptions. The reducer is connected through the existing
`EventQueue.add_on_event_batch_callback` boundary, and the encounter is driven
through public initiative, controller-boundary, action-discovery/execution,
autonomous-turn, and `Encounter.end_encounter` APIs.

The first focused run exposed a deterministic test-worker failure rather than
an encounter ordering defect: the detached tree formatter was invoked for a
delivery whose public UUID/parent metadata was not readable. Because the
consumer had no error route, the presentation cursor wait remained asleep. The
bounded test repair limits tree formatting to deliveries whose three public
tree-identity reads are `Known`, and adds a done-callback that puts the worker
exception on `presentation_to_game`, records it, and wakes the cursor waiter.
The receipt loop therefore surfaces consumer failure instead of deadlocking;
no production seam or new queue/path was added.

The final direct public-boundary evidence is:

```text
source cursor: 31 -> 141
accepted contiguous receipt ranges: 18
disposed deliveries: 105
maximum game_to_presentation queue high-water: 6
maximum engine lead over presentation cursor: 38
tree-formatted batch count: 18
```

The consumer disposed every `SourceCoverage` slot, including hidden and
lifecycle-only slots, and the receipt validator rejected duplicate, coverage
gap, overlap, backwards, and wrong-generation receipts. The proof blocked the
first player command, the second same-turn player command, the next player
decision, and terminal encounter completion until the corresponding contiguous
presentation cursor was acknowledged. Two autonomous enemy boundaries reduced
and enqueued while presentation was gated. All detached formatting ran after
fatal test-local stubs for live Entity, EventQueue, and GridMap accessors.

### Commands and results

- Focused async selector:
  `.venv/bin/python -m pytest -q -p no:cacheprovider
  tests/engine/test_event_knowledge_async_boundary.py` — `1 passed in 4.81s`.
- Focused event-knowledge plus architecture selectors — `109 passed in
  33.80s`.
- Exact selector inputs for the integrated Slice 5 checkpoint were the ten
  paths already used by the accepted Slice 4 cut, with the new async module
  prepended: `test_event_knowledge_async_boundary.py`,
  `test_event_knowledge_context.py`,
  `test_event_knowledge_scripted_encounter.py`, `test_objective_state.py`,
  `test_direct_scenario_deployment.py`,
  `test_event_wire_visibility_contract.py`, `test_move_settlement.py`,
  `test_senses_light_stealth.py`, `test_combat_actions.py`,
  `test_action_cost_and_position_commit.py`, and `tests/architecture`.
- Collection retained `^tests/.*::` rows, sorted C-bytewise, deduplicated, and
  emitted one terminal LF: `307` sorted unique node IDs,
  SHA-256 `55b8da3627e6bf24aa76a441f3ace246cd0d2bd678deb1572d801f5e7cfda2d8`.
- The exact collected newline-safe node list was executed byte-identically:
  `307 passed in 115.50s (0:01:55)`.
- `.venv/bin/python -m compileall -q
  tests/engine/test_event_knowledge_async_boundary.py` — exit `0`.
- `git diff --check` — exit `0`; only the pre-existing LF/CRLF normalization
  warning for accepted dirty `dnd/blocks/sensory.py` was reported.
- The test-local hard-cut scan found exactly two `asyncio.Queue()` constructors
  and no dynamic imports, sleeps, timeout APIs, threads, server/pygame access,
  raw `captured._snapshot`, `CombatLogEntry`, or additional queue/bus path.

### Scope and status

The worktree still contains only the accepted prior dirty/untracked
event-knowledge artifacts plus the new async test and this ledger. No
production or prior-test byte changed. The final ledger SHA-256 is reported
after this append; the new async test SHA is
`23f36c8d9d3df3fd2001ccfc69645d7007522c2bc80efd7ee6b0fcad0bef5a47`.

`SLICE_5_0_ASYNC_PROOF_COMPLETE — READY_FOR_COORDINATOR_REVIEW`

## Slice 6.0 final certification — candidate frozen for independent review

Slice 6.0 certification was completed without any behavior or ontology
change. The coordinator-authorized type-contract correction preceding this
certification removed two unused imports, applied the permitted `Any` erasure
only at heterogeneous manifest/formatter callable boundaries, and corrected
existing sensory callback/neutral-position/optional-UUID annotations. It
preserved runtime logic and was validated before this freeze.

### Authorities and current active manifest

- Governing plan:
  `DND_EVENT_KNOWLEDGE_CONTEXT_E3_E6_IMPLEMENTATION_PLAN_2026-08-27.md`,
  SHA-256 `aaf75e26e3b1e13419caf3d0b7e8346ad8a86531bc155b90f6d37767a8328c98`.
- Reduction authority:
  `DND_EVENT_KNOWLEDGE_CONTEXT_REDUCTION_PLAN_2026-08-27.md`,
  SHA-256 `7856a537f0b75063fe5bcb012fd7d020b2f92a1e018c17d1ccf6b5e830605c21`.
- E1/E2 implementation authority:
  `DND_EVENT_KNOWLEDGE_CONTEXT_IMPLEMENTATION_PLAN_2026-08-27.md`,
  SHA-256 `3f98f0b926fce8e9662c5718c01aa863734a563897bebe0b403173d8eba0a9ad`.
- Scripted-encounter authority:
  `DND_PYGAME_SCRIPTED_ENCOUNTER_MVP_IMPLEMENTATION_PLAN_2026-08-27.md`,
  SHA-256 `8e83dde4916ca3a6a4691bd9b25f720d3e381fe49e6458d4c0800007f9b390b9`.
- Final active-only manifest:
  `DND_EVENT_KNOWLEDGE_CONTEXT_E3_E6_IMPLEMENTATION_MANIFEST_2026-08-27.json`,
  SHA-256 `fd9bd2055f67b48b2861ff1fe94d665e98a3d78341990d0e257af4ebbba13772`.

The manifest contains exactly seven sorted unique active members: three
production files and four test/architecture files. Its 20 exact concrete
event rows have zero missing and zero extra classes; every row records the
observed phases, scalar paths, collection paths, provenance paths, policy,
provenance callable, and formatter callable. Base `Event` remains the one
explicitly intentionally-silent route and is not an invented concrete row.

Current member hashes, verified against the final manifest:

```text
75d508f52156bd6d1ce73b0d5eafe25eee804cd4b3e1056b943c365435bec8ee  dnd/blocks/sensory.py
f9347cdeb21591b051014b06a90d4d5604904abdfe1c0d40d4d55d2c7d433026  dnd/core/events/knowledge.py
d262b6d1596a560a94094901821c89100ff5746fdbccbbd1d64f9cd25fd5d509  dnd/event_reduction.py
6b2d84b17578c61a32bcb0f83c60ddd95738c9465ba476406c1ac894189e08db  tests/architecture/test_event_knowledge_context_architecture.py
1d014da295dc4a812725a903cef996207e595439b37d892c9b9c3ffaa73d0f4e  tests/engine/test_event_knowledge_async_boundary.py
d4a3e8d1feec813c5497ff025377986c99997799efddd2101dbf51c87012d273  tests/engine/test_event_knowledge_context.py
7203b0a8430b74d3d5bb0e59638b1817d4da3407893f3951f0d0038d36fdb4f2  tests/engine/test_event_knowledge_scripted_encounter.py
```

The ledger, governing Markdown, and manifest are governance artifacts and are
excluded from active member scope. Server/deprecated-server, SDK, transport,
renderer, pygame, assets, editor, save/persistence/networking, game/, content
authoring, caches, temporary output, and unrelated dirty work are excluded.

### Exact source-node union and execution

The exact selector inputs were:

```text
tests/engine/test_event_knowledge_async_boundary.py
tests/engine/test_event_knowledge_context.py
tests/engine/test_event_knowledge_scripted_encounter.py
tests/engine/test_objective_state.py
tests/engine/test_direct_scenario_deployment.py
tests/engine/test_event_wire_visibility_contract.py
tests/engine/test_move_settlement.py
tests/engine/test_senses_light_stealth.py
tests/engine/test_combat_actions.py
tests/engine/test_action_cost_and_position_commit.py
tests/architecture
```

Collection used `pytest --collect-only -q -p no:cacheprovider`, retained only
`^tests/.*::` rows, sorted C-bytewise, deduplicated, and hashed the terminal-LF
newline stream. It produced exactly `309` unique node IDs with normalized
SHA-256
`f9a548aac09faf728ba330c1f7a12c2b4142eae851c5919a48aae54347409d80`.
The exact collected list was executed byte-identically:
`309 passed in 142.63s (0:02:22)` through the newline-to-NUL-safe `xargs`
invocation; measured command wall time was `152.23s`.

The complete real proving encounter was also run twice through the async test
helper, with a cold runtime reset between runs. The two public structures were
identical after excluding the fresh generation UUID:

```text
source_base=31, source_stop=141, accepted_ranges=18,
delivery_count=105, maximum_queue_high_water=6,
maximum_engine_lead=38, tree_batch_count=18
```

The separate full proving-encounter selector was also run through its own
twice-cold detached replay. It captured the complete source range `0..244`,
including the real combat-log listener seam, and installed fatal Entity,
EventQueue, and GridMap access stubs before reduction and formatting. Both
cold runs had identical public structure:

```text
source_base=0, source_stop=244, callback_range_count=45,
coverage_slots=244, formatted_delivery_count=248,
tree_batch_count=1, archive_count=1
```

Selector:
`tests/engine/test_event_knowledge_scripted_encounter.py::test_full_public_encounter_replays_and_consumes_detached_batches_deterministically`.

### Certification gates

- Context module: `51 passed in 6.37s`; all three event-knowledge modules:
  `54 passed in 9.93s`; complete `tests/architecture`: `57 passed in 38.50s`.
- The previously accepted proportional event-knowledge/sensory/architecture
  lane remains recorded as `152 passed in 54.48s`; the exact current 309-node
  union is the certification execution for all selector inputs.
- Pyright on all seven governed E3-E6 production/test surfaces with the
  project interpreter: `0 errors, 0 warnings, 0 informations`.
- Compileall for all seven governed E3-E6 production/test surfaces: exit `0`.
- `git diff --check`: exit `0`; only the pre-existing accepted sensory
  LF/CRLF normalization warning remained.
- Exact-class/policy gate: `20/20` rows, zero missing/extra handlers.
- Manifest-row verification: `20/20` live `_CONCRETE_EVENT_MANIFEST` rows
  matched exactly, including SensoryUpdateEvent and StepMovementEvent scalar
  and collection paths; mask/path containment was exact.
- Detached reducer/consumer gate: pass with fatal live Entity, EventQueue, and
  GridMap stubs installed after capture; reduction and formatting completed
  without live-world reads.
- Async hard-cut gate: exactly two `asyncio.Queue()` constructors; no dynamic
  imports, sleeps, timeout APIs, threads, server/pygame access, raw snapshot,
  CombatLogEntry, or extra queue/bus path.
- Receipt gate: duplicate, coverage-gap, overlap, backwards, and
  wrong-generation receipts all rejected.
- Dependency/ownership/hard-cut gates: complete architecture passed; the
  dependency-neutral knowledge module has no sensory/actions/entities/grid,
  encounter, content, renderer, or transport import; one reducer module and
  one concrete manifest remain.
- Final manifest verification: valid JSON; seven sorted unique members; all
  seven present and current with zero hash mismatches; no excluded member was
  included. The final manifest SHA is
  `fd9bd2055f67b48b2861ff1fe94d665e98a3d78341990d0e257af4ebbba13772`.

### Freeze status

No production or test bytes were changed during certification. The final
active-only manifest was revalidated as JSON, sorted/unique, present, and
hash-exact before this ledger update; the manifest itself and this ledger
remain outside the active member set. The final ledger hash is intentionally
not recorded inside the ledger.

`READY_FOR_INDEPENDENT_REVIEW`
