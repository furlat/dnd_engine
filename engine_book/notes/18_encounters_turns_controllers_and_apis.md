# 18. Encounters, Turns, Controllers, And APIs

## Purpose

This chapter documents the runtime layer that sits above entities and actions:
encounters, turn lifecycle, controller contracts, combat-log capture, and the
stable API-facing payload surfaces.

The examples are executable in both:

- `tests/engine_book/test_chapter_18_encounters_apis.py`
- `tests/engine_book/test_chapter_18_encounters_apis.py`

The pytest file calls the same example functions, so the book examples and the
`uv run pytest` suite stay in 1:1 parity.

## Source Files Studied

- `dnd/encounter.py`
- `dnd/controller.py`
- `dnd/actions_functional.py`
- `dnd/core/events.py`
- `dnd/core/combat_log.py`
- `server/api_models.py`
- `server/event_server.py`
- `server/event_stream.py`
- `server/spell_catalog.py`
- `server/mapeditor_support.py`
- `examples/test_available_actions.py`
- `examples/test_faction_system.py`
- `examples/test_serialization.py`
- `examples/test_spell_catalog_api.py`
- `examples/test_directional_event_stream.py`
- `examples/test_mapeditor_api.py`
- `tests/engine_book/test_chapter_18_encounters_apis.py`
- `tests/engine_book/test_chapter_18_encounters_apis.py`

Server tests under `examples/server_tests/` were inspected as reference only.
They are not run in batch because they can require live server setup and may
hang.

## Rules Relationship

Status: mixed.

- `SRD-aligned`: the encounter loop maps to
  `interactive_ruleset/Gameplay/Combat.md`: determine initiative, take turns in
  initiative order, advance rounds when all combatants have acted, and stop when
  the fight is over.
- `SRD-aligned`: `TurnContext` exposes the per-turn budgets described by the
  combat rules: actions, bonus actions, reactions, and movement.
- `SRD-aligned`: surprise is represented on `CombatantState.surprised`, and a
  surprised combatant is skipped in round 1.
- `Engine adaptation`: initiative is stored per combatant and sorted by total,
  then initiative bonus. The SRD leaves some tie handling to the GM/players.
- `Engine adaptation`: the encounter ends by faction survival rather than a GM
  narration hook.
- `Engine adaptation`: human and Codex-controlled turns pause for external API
  input; AI/pass controllers can be advanced automatically.
- `Engine extension`: `/events`, `/events/subscribe`, `/catalog/spells`, and
  mapeditor endpoints are API layers around the engine. They are not SRD rules,
  but they are now part of the documented engine surface.

## Encounter State

`Encounter` is a `BaseObject` with its own registry and one active encounter
pointer. It owns:

- `combatants`: entity UUID to `CombatantState`;
- `initiative_order`: entity UUIDs in turn order;
- `current_turn_index`;
- `round_number`;
- `state`: `not_started`, `active`, `paused`, or `ended`;
- `turn_state`: `not_started`, `in_progress`, or `ended`;
- `combat_log`: top-level `CombatLogEntry` values.

Starting an encounter:

1. validates that it has combatants;
2. rolls initiative if order is empty;
3. marks the encounter active;
4. sets round 1;
5. installs `EventQueue` combat-log and visibility callbacks;
6. notifies controllers;
7. fires an encounter-start event and round-start event.

Ending an encounter:

1. ends any in-progress turn;
2. marks the encounter ended;
3. clears the active encounter pointer;
4. unregisters combat-log and perceiver/reveal callbacks;
5. notifies controllers;
6. returns an encounter-end event.

Example EB-18-001 proves those runtime contracts:

```python
encounter = start_ordered_encounter(hero, monster, hero_controller, monster_controller, hero)

assert encounter.state == EncounterState.ACTIVE
assert Encounter.get_active() is encounter
assert encounter.round_number == 1
assert encounter.initiative_order == [hero.uuid, monster.uuid]
assert EventQueue._combat_log_callback == encounter._on_event_combat_log

end_event = encounter.end_encounter("chapter test complete")

assert end_event.reason == "chapter test complete"
assert encounter.state == EncounterState.ENDED
assert Encounter.get_active() is None
assert EventQueue._combat_log_callback is None
```

Parity tests:

- `tests/engine_book/test_chapter_18_encounters_apis.py::test_eb_18_001_encounter_start_sets_active_state_callbacks_and_round`
- `tests/engine_book/test_chapter_18_encounters_apis.py`

## Turn Lifecycle

An encounter turn is thin orchestration around entity-level turn hooks.

`start_turn()`:

- rejects non-active encounters;
- rejects double-starting an in-progress turn;
- skips surprised round-1 combatants;
- skips dead combatants;
- marks the turn in progress;
- calls `entity.on_turn_start()`;
- clears stale collision data;
- updates senses;
- builds a `TurnContext`;
- calls `controller.on_turn_start()`.

`end_turn()`:

- calls `entity.on_turn_end()`;
- calls `controller.on_turn_end()`;
- marks the combatant as having acted;
- increments the combatant turn count;
- marks the turn ended.

`next_turn()` ends the current turn if needed, increments the turn index, and
starts the next turn. If the index passes the end of initiative order,
`_advance_round()` fires round end, advances tile/floor item durations, resets
per-round combatant flags, increments `round_number`, and fires round start.

Surprise is stored on `CombatantState.surprised`. The SRD rule in
`interactive_ruleset/Gameplay/Combat.md` has two separate effects: the surprised
combatant cannot move or act on its first turn, and it cannot take reactions
until that turn ends. The encounter therefore spends surprised combatants'
starting reactions when combat starts, then runs the normal entity turn-start and
turn-end hooks for the skipped first turn. Those hooks define the exact point
where reactions recharge, while no controller action is requested for that turn.

Example EB-18-002 proves the lifecycle:

```python
start_event = encounter.start_turn()

assert encounter.turn_state == TurnState.IN_PROGRESS
assert encounter.get_current_entity() is hero

start_context = hero_controller.turn_start_contexts[-1]
assert start_context.entity_uuid == hero.uuid
assert start_context.actions_remaining == 1
assert monster.uuid in start_context.visible_enemies

encounter.end_turn()
encounter.next_turn()

assert encounter.get_current_entity() is monster

encounter.end_turn()
encounter.next_turn()

assert encounter.get_current_entity() is hero
assert encounter.round_number == 2
```

Parity tests:

- `tests/engine_book/test_chapter_18_encounters_apis.py::test_eb_18_002_turn_lifecycle_builds_context_and_advances_rounds`
- `tests/engine_book/test_chapter_18_encounters_apis.py`

Example EB-18-019 proves the surprise reaction edge with opportunity attacks:

```python
encounter.add_combatant(monster, PassController(source_entity_uuid=monster.uuid), surprised=True)
encounter.start_encounter()

assert monster.action_economy.reactions.normalized_score == 0

encounter.start_turn()
initial_hero_hp = get_hp(hero)
move_event = Move(source_entity_uuid=hero.uuid, end_position=(1, 3)).apply()

assert not move_event.canceled
assert get_hp(hero) == initial_hero_hp

encounter.end_turn()
encounter.next_turn()

assert encounter.round_number == 2
assert encounter.combatants[monster.uuid].turn_count == 1
assert monster.action_economy.reactions.normalized_score == 1
```

Parity tests:

- `tests/engine_book/test_chapter_18_encounters_apis.py::test_eb_18_019_surprise_blocks_reactions_until_skipped_turn_ends`
- `tests/engine_book/test_chapter_18_encounters_apis.py`

## Controller Contract

Controllers are registered `BaseObject`s. A controller does not own the entity;
the encounter's `CombatantState` links an entity UUID to a controller UUID.

The base controller protocol is:

- `get_next_action(entity, context) -> Optional[BaseAction]`;
- `on_turn_start(entity, context)`;
- `on_turn_end(entity, context)`;
- `on_encounter_start(entities)`;
- `on_encounter_end(entities)`;
- `can_continue_turn(entity, context) -> bool`.

The built-in controller types matter for automation:

- `PassController`: returns no actions and does not continue.
- `HumanController`: external API input drives the turn, so autonomous turn
  running stops immediately.
- `CodexController`: same external-input shape as `HumanController`, with a
  distinct controller type.
- `MeleeAIController`: queries available actions and returns a melee attack or
  movement when possible.
- `AIAgentController`: delegates to an external turn runner once, then stops.

`advance_until_player()` uses `controller_type` as a public contract. It runs
AI/pass turns and stops when the current controller is `"human"` or `"codex"`.

Example EB-18-003:

```python
result = encounter.advance_until_player()

assert result.status == "waiting_for_human"
assert result.entity_uuid == hero.uuid
assert encounter.get_current_entity() is hero
assert encounter.turn_state == TurnState.IN_PROGRESS
assert encounter.combatants[monster.uuid].turn_count == 1
```

Example EB-18-020 proves the same external-input boundary for
`CodexController`. It must stop with `waiting_for_codex`, leave the Codex
entity's turn in progress, and return no autonomous action from the controller:

```python
result = encounter.advance_until_player()
context = encounter._build_turn_context(hero)

assert result.status == "waiting_for_codex"
assert result.entity_uuid == hero.uuid
assert encounter.get_current_entity() is hero
assert encounter.turn_state == TurnState.IN_PROGRESS
assert not codex_controller.can_continue_turn(hero, context)
assert codex_controller.get_next_action(hero, context) is None
```

Example EB-18-028 proves the Codex orchestration boundary. The orchestrator
builds `codex exec --json` subprocess commands, sends the combined prompt over
stdin, and injects `--expect-entity` into the per-turn `cli.agent` command
prefix. That guard rejects stale commands if buffered output from an older
turn tries to execute after the active entity has changed. The book-integrity
suite also scans active runtime source roots (`cli/`, `dnd/`, and `server/`) so
Claude references cannot drift back into executable code:

```python
cmd, stdin_prompt = orchestrator.build_codex_exec_invocation(
    slot,
    "TURN PROMPT",
    allow_write=False,
    expected_entity_uuid="entity-uuid",
)

assert cmd[0:2] == ["codex", "exec"]
assert "python -m cli.agent --token abc123 --expect-entity entity-uuid <command>" in stdin_prompt
assert "claude" not in " ".join(cmd).lower()
```

Example EB-18-021 proves the `MeleeAIController` decision ladder with a
melee-only skeleton fixture. The fixture starts from the base skeleton factory
and unequips the ranged-main weapon so the example isolates melee AI behavior
instead of ranged attack choice. Adjacent targets must produce a weapon attack,
not another entity-targeted action such as Shove. Distant visible enemies
produce a `Move` that reduces distance, and no visible enemies produce `None`:

```python
melee_actor = create_melee_only_skeleton(position=(1, 1), faction="monsters")
attack_action = controller.get_next_action(melee_actor, adjacent_context)

assert isinstance(attack_action, Attack)
assert attack_action.name == "Attack_MELEE_MAIN"
assert attack_action.target_entity_uuid == adjacent_target.uuid

move_action = controller.get_next_action(melee_actor, distant_context)

assert isinstance(move_action, Move)
assert move_action.end_position is not None
assert moved_distance < current_distance

assert controller.get_next_action(lone_actor, empty_context) is None
```

Example EB-18-034 tightens the map-aware movement boundary. `MeleeAIController`
does not compute paths directly; it asks `get_available_actions()` for legal
Move targets and then instantiates a move to one of those positions. A
directional movement border blocks the direct east transition out of the AI's
starting tile, but the available-action pathfinder can still expose a legal
route around that border. The chosen move must use the same path from the
available-action target, avoid the blocked transition, validate every path step
with `GridMap.can_transition()`, and still reduce distance to the visible enemy:

```python
grid.set_tile_directional_border((1, 1), "movement", "east", False)
assert not grid.can_transition((1, 1), (2, 1))

move_info = next(
    action for action in melee_actor.get_available_actions().position_actions
    if action.template_name == "Move"
)
move_action = controller.get_next_action(melee_actor, context)

assert isinstance(move_action, Move)
assert move_action.end_position in legal_move_targets
assert move_action.path == legal_move_targets[move_action.end_position].path
assert ((1, 1), (2, 1)) not in zip(move_action.path, move_action.path[1:])
```

Parity tests:

- `tests/engine_book/test_chapter_18_encounters_apis.py::test_eb_18_003_run_turn_and_advance_until_player_respect_controller_types`
- `tests/engine_book/test_chapter_18_encounters_apis.py::test_eb_18_020_codex_controller_stops_as_external_input_turn`
- `tests/engine_book/test_chapter_18_encounters_apis.py::test_eb_18_028_codex_orchestrator_builds_guarded_codex_exec_invocation`
- `tests/engine_book/test_book_integrity.py::test_active_runtime_sources_do_not_reference_claude`
- `tests/engine_book/test_chapter_18_encounters_apis.py::test_eb_18_021_melee_ai_attacks_moves_or_passes_from_context`
- `tests/engine_book/test_chapter_18_encounters_apis.py::test_eb_18_034_melee_ai_uses_available_move_paths_across_directional_blockers`
- `tests/engine_book/test_chapter_18_encounters_apis.py`

## Action Execution And Combat Logs

`Encounter.execute_action(entity_uuid, template_name, target_index)` is the
HTTP-style execution path for externally controlled turns. It:

1. resolves the entity;
2. delegates to `execute_by_index()`;
3. lets event completion auto-capture combat logs through the active encounter
   callback;
4. calls `check_deaths()`;
5. returns the event.

Combat-log listeners can be registered globally on `Encounter`. They are
passive listeners: exceptions are swallowed, and they cannot modify the event
that already completed.

Example EB-18-004 proves the action/log path:

```python
listener_calls = []

def listener(active, index, entry, event):
    listener_calls.append((index, entry.entry_type.value))

Encounter.add_combat_log_listener(listener)
event = encounter.execute_action(hero.uuid, "Attack_MELEE_MAIN", 0)
Encounter.remove_combat_log_listener(listener)

assert event is not None
assert not event.canceled
assert encounter.combat_log
assert listener_calls[-1][0] == len(encounter.combat_log) - 1
```

Parity tests:

- `tests/engine_book/test_chapter_18_encounters_apis.py::test_eb_18_004_execute_action_captures_combat_log_and_listener_payload`
- `tests/engine_book/test_chapter_18_encounters_apis.py`

## Action API Error Details

The action endpoints use the available-action snapshot as the authoritative
correction surface. When a request names an unknown action, names an action for
the wrong endpoint shape, or names a valid indexed action with an invalid target
index, the HTTP 400 response keeps FastAPI's `detail` envelope but makes
`detail` a structured object:

- `code`: machine-readable error category;
- `message`: human-readable reason;
- `entity_uuid` and `entity_name`;
- `action_economy`: remaining actions, bonus actions, reactions, movement, and
  extra attacks;
- `valid_action_names`: executable template names from the current snapshot;
- `available_actions`: the same grouped action payload returned by
  `/entity/{uuid}/available-actions`.

Example EB-18-009 proves the structured correction payload:

```python
available_response = client.get(f"/entity/{hero.uuid}/available-actions")
assert available_response.status_code == 200

response = client.post(
    "/action/execute",
    json={
        "session_id": session_id,
        "entity_uuid": str(hero.uuid),
        "template_name": "NotARealAction",
        "target_index": 0,
    },
)

assert response.status_code == 400
detail = response.json()["detail"]
assert detail["code"] == "unknown_action"
assert detail["action_economy"]["actions"] == 1
assert "Attack_MELEE_MAIN" in detail["valid_action_names"]
assert detail["available_actions"]["entity_uuid"] == str(hero.uuid)
```

The same example submits `Attack_MELEE_MAIN` with an impossible target index and
asserts the `invalid_action_target` code.

Example EB-18-027 proves the positive `/available-actions` spell-variant
payload. Slot-specific spell rows use executable names such as
`Magic Missile__slot_3`, and expose spell metadata so clients can display the
variant without parsing that name:

```python
response = client.get(f"/entity/{caster.uuid}/available-actions")
payload = response.json()

missile_by_name = {
    action["template_name"]: action
    for action in payload["entity_actions"]
    if action.get("base_template_name") == "Magic Missile"
}
fireball_by_name = {
    action["template_name"]: action
    for action in payload["position_actions"]
    if action.get("base_template_name") == "Fireball"
}

assert {"Magic Missile__slot_1", "Magic Missile__slot_3"} <= set(missile_by_name)
assert "Fireball__slot_3" in fireball_by_name
assert missile_by_name["Magic Missile__slot_3"]["cast_at_level"] == 3
assert missile_by_name["Magic Missile__slot_3"]["num_projectiles"] == 5
assert fireball_by_name["Fireball__slot_3"]["is_spell_variant"] is True
```

Example EB-18-010 proves the named action endpoint family shares the same
structure:

```python
unknown_self_response = client.post(
    "/action/self",
    json={
        "session_id": session_id,
        "entity_uuid": str(hero.uuid),
        "action_name": "NotARealAction",
    },
)
unknown_self = unknown_self_response.json()["detail"]
assert unknown_self["code"] == "unknown_action"
assert "Dash" in unknown_self["valid_action_names"]

wrong_entity_response = client.post(
    "/action/entity",
    json={
        "session_id": session_id,
        "entity_uuid": str(hero.uuid),
        "action_name": "Dash",
        "target_uuid": str(monster.uuid),
    },
)
wrong_entity = wrong_entity_response.json()["detail"]
assert wrong_entity["code"] == "invalid_action_type"
assert wrong_entity["available_actions"]["entity_uuid"] == str(hero.uuid)
```

Example EB-18-023 covers the remaining entity-action target validation path.
Malformed and missing `target_uuid` values use the same correction payload and
also include `target_uuid` plus `known_entities`:

```python
invalid_target_response = client.post(
    "/action/entity",
    json={
        "session_id": session_id,
        "entity_uuid": str(hero.uuid),
        "action_name": "Attack_MELEE_MAIN",
        "target_uuid": "not-a-uuid",
    },
)
invalid_target = invalid_target_response.json()["detail"]
assert invalid_target["code"] == "invalid_target_uuid"
assert invalid_target["target_uuid"] == "not-a-uuid"
assert "Attack_MELEE_MAIN" in invalid_target["valid_action_names"]
assert {entity["uuid"] for entity in invalid_target["known_entities"]} >= {
    str(hero.uuid),
    str(monster.uuid),
}

missing_target_response = client.post(
    "/action/entity",
    json={
        "session_id": session_id,
        "entity_uuid": str(hero.uuid),
        "action_name": "Attack_MELEE_MAIN",
        "target_uuid": str(missing_target_uuid),
    },
)
missing_target = missing_target_response.json()["detail"]
assert missing_target["code"] == "target_not_found"
assert missing_target["action_economy"]["actions"] == 1
```

Parity tests:

- `tests/engine_book/test_chapter_18_encounters_apis.py::test_eb_18_009_action_execute_error_payload_reports_available_corrections`
- `tests/engine_book/test_chapter_18_encounters_apis.py::test_eb_18_010_named_action_endpoints_share_structured_error_payloads`
- `tests/engine_book/test_chapter_18_encounters_apis.py::test_eb_18_023_entity_action_target_errors_report_current_choices`
- `tests/engine_book/test_chapter_18_encounters_apis.py`

## Entity, Handler, And Equipment API Errors

The non-action entity endpoints follow the same recovery principle: an error
names the failure class and gives the caller enough current state to correct the
request without guessing. The successful DTOs remain `APIEntityFull`,
`APIEquipmentOverview`, and handler lists; only error `detail` bodies are
structured.

Entity lookup errors include:

- `code` and `message`;
- the requested `entity_uuid` string;
- `known_entities`, serialized through `APIEntitySummary`.

Example EB-18-011 proves both malformed and unknown entity lookups, then checks
handler-specific correction context:

```python
invalid_entity_response = client.get("/entity/not-a-uuid")
invalid_entity = invalid_entity_response.json()["detail"]
assert invalid_entity["code"] == "invalid_entity_uuid"
assert {entity["uuid"] for entity in invalid_entity["known_entities"]} >= {
    str(hero.uuid),
    str(monster.uuid),
}

missing_handler_response = client.post(
    f"/entity/{hero.uuid}/handlers/NotAHandler/toggle",
    json={"session_id": session_id, "entity_uuid": str(hero.uuid), "enabled": False},
)
missing_handler = missing_handler_response.json()["detail"]
assert missing_handler["code"] == "handler_not_found"
assert "Opportunity Attack Handler" in missing_handler["valid_handler_names"]
```

Handler errors include the acting entity, requested handler name, valid handler
names, and the serialized toggleable handler list. Equipment errors include the
acting entity, valid API slot names, current inventory item UUIDs, equipped item
UUIDs, and the current `APIEquipmentOverview` snapshot.

Example EB-18-012 proves item and slot correction surfaces:

```python
missing_item_response = client.get(f"/entity/{hero.uuid}/equipment/item/{uuid4()}")
missing_item = missing_item_response.json()["detail"]
assert missing_item["code"] == "item_not_found"
assert "weapon_melee_main" in missing_item["valid_slots"]
assert str(potion.uuid) in missing_item["inventory_item_uuids"]

invalid_slot_response = client.post(
    f"/entity/{hero.uuid}/equip",
    json={
        "session_id": session_id,
        "entity_uuid": str(hero.uuid),
        "item_uuid": str(dagger.uuid),
        "slot": "not_a_slot",
    },
)
invalid_slot = invalid_slot_response.json()["detail"]
assert invalid_slot["code"] == "invalid_slot"
assert "ring_left" in invalid_slot["valid_slots"]
```

Parity tests:

- `tests/engine_book/test_chapter_18_encounters_apis.py::test_eb_18_011_entity_and_handler_errors_report_current_choices`
- `tests/engine_book/test_chapter_18_encounters_apis.py::test_eb_18_012_equipment_errors_report_slots_inventory_and_loadout`
- `tests/engine_book/test_chapter_18_encounters_apis.py`

## Session, Event, And Simulation API Errors

Session and game errors expose both authority context and the current table
surface:

- `valid_player_types`;
- `known_sessions`, using the session object's API dictionary;
- `active_game_id` and `active_entity_uuid`, including explicit `None` when no
  active game exists;
- `known_entities`, serialized through `APIEntitySummary`;
- request-specific fields such as `requested_entity_uuids` and
  `requested_faction`.

Example EB-18-013 proves invalid player types, joining without an active game,
missing sessions, and malformed session UUIDs:

```python
invalid_player_response = client.post(
    "/session/create",
    json={"player_type": "dragon", "name": "Wrong Door"},
)
invalid_player = invalid_player_response.json()["detail"]
assert invalid_player["code"] == "invalid_player_type"
assert {"human", "codex", "ai"} <= set(invalid_player["valid_player_types"])

no_game_response = client.post(
    "/game/join",
    json={"session_id": session_id, "entity_uuids": [str(hero.uuid)]},
)
no_game = no_game_response.json()["detail"]
assert no_game["code"] == "no_active_game"
assert no_game["active_game_id"] is None
assert no_game["requested_entity_uuids"] == [str(hero.uuid)]
```

The positive session lifecycle is separate from game joining. EB-18-032 proves
that `POST /session/create`, `POST /session/{session_id}/ping`, and
`DELETE /session/{session_id}` share the same session manager state:

```python
create_response = client.post("/session/create", json={"player_type": "codex"})
created = create_response.json()
session_id = created["session_id"]

assert created["player_type"] == "codex"
assert created["name"] == "Codex"

pinged = client.post(f"/session/{session_id}/ping").json()
assert pinged["status"] == "ok"
assert pinged["connection_status"] == "connected"
assert pinged["controlled_entities"] == []

deleted = client.delete(f"/session/{session_id}").json()
assert deleted == {"status": "deleted", "session_id": session_id}
```

Joining a game assigns engine entities to sessions. EB-18-033 proves two join
paths and the readback endpoints that depend on the same ownership state:

```python
hero_join = client.post(
    "/game/join",
    json={"session_id": hero_session_id, "entity_uuids": [str(hero.uuid)]},
).json()
assert hero_join["controlled_entities"] == [str(hero.uuid)]

monster_join = client.post(
    "/game/join",
    json={"session_id": monster_session_id, "faction": "monsters"},
).json()
assert monster_join["controlled_entities"] == [str(monster.uuid)]

status = client.get("/game/status").json()
assert status["active_entity_uuid"] == str(hero.uuid)
assert status["sessions"][0]["is_their_turn"] is True

entities = client.get(f"/session/{hero_session_id}/entities").json()
assert entities["controlled_entities"][0]["uuid"] == str(hero.uuid)
```

Session action validation has its own structured authority payload. This is the
guard used by action endpoints before action-template validation. It reports
the requested session/entity, known sessions, active game/entity, encounter and
turn state, the session's controlled entities, connection status, and the
entity's owning session when known. Example EB-18-026 proves these codes:

- `invalid_session`;
- `session_disconnected`;
- `no_active_game`;
- `entity_not_controlled`;
- `not_entity_turn`;
- `turn_not_in_progress`.

```python
invalid_session_response = client.post(
    "/action/self",
    json={"session_id": str(invalid_session_uuid), "entity_uuid": str(hero.uuid), "action_name": "Dash"},
)
invalid_session = invalid_session_response.json()["detail"]
assert invalid_session["code"] == "invalid_session"
assert invalid_session["active_entity_uuid"] == str(hero.uuid)

wrong_turn_response = client.post(
    "/action/self",
    json={"session_id": monster_session_id, "entity_uuid": str(monster.uuid), "action_name": "Dash"},
)
wrong_turn = wrong_turn_response.json()["detail"]
assert wrong_turn["code"] == "not_entity_turn"
assert wrong_turn["controlled_entities"] == [str(monster.uuid)]
```

Event-history filter errors expose valid enum choices and cursor state. Simulation
control errors expose whether an encounter exists, pause state, encounter state,
round number, current delay, and the accepted delay range.

Example EB-18-014 proves those recovery payloads:

```python
invalid_event_response = client.get("/events", params={"event_type": "not_an_event"})
invalid_event = invalid_event_response.json()["detail"]
assert invalid_event["code"] == "unknown_event_type"
assert "attack" in invalid_event["valid_event_types"]
assert invalid_event["event_count"] == EventQueue.event_cursor()

resume_response = client.post("/simulation/resume")
resume_detail = resume_response.json()["detail"]
assert resume_detail["code"] == "simulation_not_started"
assert resume_detail["has_encounter"] is False
assert resume_detail["min_delay"] == 0.1
```

Example EB-18-025 covers the `/action/end-turn` drift guard. If a session and
active game still exist but `sim.encounter` has been cleared, the endpoint
returns `no_active_encounter` with both session/game context and simulation
context:

```python
client, session_id, hero, _monster = create_action_api_session()
active_game_id = str(sim.game.game_id) if sim.game else None
sim.encounter = None

response = client.post(
    "/action/end-turn",
    json={"session_id": session_id, "entity_uuid": str(hero.uuid)},
)
detail = response.json()["detail"]
assert detail["code"] == "no_active_encounter"
assert detail["active_game_id"] == active_game_id
assert detail["active_entity_uuid"] == str(hero.uuid)
assert detail["has_encounter"] is False
```

Parity tests:

- `tests/engine_book/test_chapter_18_encounters_apis.py::test_eb_18_013_session_and_game_errors_report_valid_sessions_and_entities`
- `tests/engine_book/test_chapter_18_encounters_apis.py::test_eb_18_032_session_create_ping_and_delete_are_stateful`
- `tests/engine_book/test_chapter_18_encounters_apis.py::test_eb_18_033_game_join_status_and_session_entities_are_stateful`
- `tests/engine_book/test_chapter_18_encounters_apis.py::test_eb_18_026_session_authority_errors_report_action_context`
- `tests/engine_book/test_chapter_18_encounters_apis.py::test_eb_18_014_event_filter_and_simulation_errors_report_valid_ranges`
- `tests/engine_book/test_chapter_18_encounters_apis.py::test_eb_18_025_end_turn_without_active_encounter_reports_state_context`
- `tests/engine_book/test_chapter_18_encounters_apis.py`
- `tests/engine_book/test_book_integrity.py::test_server_http_errors_do_not_use_bare_string_details`

## Death And Encounter End

`check_deaths()` is the encounter-level safety pass for combatants whose HP has
fallen to 0 outside the direct `receive_damage()` path. For each newly dead
combatant it:

- marks `CombatantState.is_dead`;
- fires a `DeathEvent`;
- allows the `Dead` condition tree to apply;
- checks whether only one faction remains alive.

The active encounter ends when zero or one faction has survivors. Factionless
entities are treated as separate UUID-based factions.

Example EB-18-005:

```python
set_hp(monster, 0)
death_events = encounter.check_deaths()

assert death_events
assert encounter.combatants[monster.uuid].is_dead
assert "Dead" in monster.active_conditions
assert encounter.state == EncounterState.ENDED
assert len(encounter.get_alive_combatants()) == 1
```

Parity tests:

- `tests/engine_book/test_chapter_18_encounters_apis.py::test_eb_18_005_check_deaths_marks_dead_and_ends_single_faction_encounter`
- `tests/engine_book/test_chapter_18_encounters_apis.py`

## Serialization Boundary

Raw engine objects are Pydantic models, so `model_dump(mode="json")` is the
low-level serialization path. That is useful for persistence/debugging, but the
server uses API DTOs for stable public payloads because raw entities include
live blocks, handlers, modifiers, conditions, and action templates.

Chapter 18 treats both as contracts:

- raw entity/encounter dumps must be JSON-compatible;
- event JSON is domain event data, while combat logs are delivered separately;
- `server/api_models.py` defines explicit web-facing DTOs;
- `server/spell_catalog.py` builds catalog metadata without mutating
  `BaseObject._registry`.

Example EB-18-006:

```python
entity_dump = hero.model_dump(mode="json")
encounter_dump = encounter.model_dump(mode="json")
json.dumps(entity_dump)
json.dumps(encounter_dump)

before_registry_count = len(BaseObject._registry)
catalog = build_spell_catalog()
after_registry_count = len(BaseObject._registry)

assert after_registry_count == before_registry_count
assert any(spell.id == "fire_bolt" and spell.attack_roll for spell in catalog.spells)
```

The same example calls `GET /catalog/spells` with `TestClient` and checks that
Fire Bolt, Magic Missile, and Fireball are exposed.

The root health endpoint is intentionally small: it reports server status,
listener count, event count, encounter presence, and pause state. EB-18-030
locks the listener count as a JSON scalar from the `EventMonitor` property.

Example EB-18-030:

```python
response = TestClient(app).get("/")
payload = response.json()

assert payload["status"] == "running"
assert payload["listeners"] == event_monitor.listener_count
assert isinstance(payload["listeners"], int)
assert payload["has_encounter"] is False
```

Simulation-control endpoints expose a stateful but small REST surface around the
demo encounter:

- `POST /simulation/reset` creates a fresh paused demo encounter;
- `GET /simulation/status` reports encounter presence, pause state, encounter
  state, round, and turn delay;
- `POST /simulation/set-delay` validates and stores the automated-turn delay;
- `POST /simulation/pause` sets the paused flag;
- `POST /simulation/step` manually starts or advances one encounter turn.

Example EB-18-031 exercises that surface without starting the continuous
background loop:

```python
assert client.get("/encounter").json() == {"active": False, "encounter": None}
assert client.get("/combat-log").json() == {"entries": [], "count": 0, "total": 0}

reset_payload = client.post("/simulation/reset").json()
status_payload = client.get("/simulation/status").json()

assert status_payload["has_encounter"] is True
assert status_payload["paused"] is True
assert status_payload["encounter_state"] == EncounterState.NOT_STARTED.value

encounter_payload = client.get("/encounter").json()
assert encounter_payload["encounter"]["uuid"] == reset_payload["encounter_uuid"]

assert client.post("/simulation/set-delay", params={"delay": 0.25}).json() == {
    "status": "delay_set",
    "turn_delay": 0.25,
}
assert client.post("/simulation/step").json()["status"] == "stepped"
```

`GET /state` returns the public game-state DTO: `APIGrid`, lightweight entity
summaries, optional `APIEncounter`, and floor object summaries. It is used for
both entity-free mapeditor maps and active encounters.

Example EB-18-016 proves the state DTO at both boundaries:

```python
empty_state = client.get("/state").json()
assert empty_state["entities"] == []
assert empty_state["encounter"] is None
assert empty_state["floor_objects"] == []

client.post("/mapeditor/map/objects", json={"catalog_id": "door", "position": [1, 1]})
editor_state = client.get("/state").json()
assert editor_state["floor_objects"][0]["name"] == "Door"
assert "is_open" in editor_state["floor_objects"][0]["state"]

active_state = client.get("/state").json()
assert active_state["encounter"]["current_entity_uuid"] == str(hero.uuid)
assert {entity["uuid"] for entity in active_state["entities"]} == {str(hero.uuid), str(monster.uuid)}
```

Parity tests:

- `tests/engine_book/test_chapter_18_encounters_apis.py::test_eb_18_006_serialization_and_spell_catalog_api_do_not_mutate_registry`
- `tests/engine_book/test_chapter_18_encounters_apis.py::test_eb_18_030_health_endpoint_reports_scalar_listener_count`
- `tests/engine_book/test_chapter_18_encounters_apis.py::test_eb_18_031_simulation_reset_status_delay_and_step_are_stateful`
- `tests/engine_book/test_chapter_18_encounters_apis.py::test_eb_18_016_state_endpoint_serializes_editor_and_active_encounter_state`
- `tests/engine_book/test_chapter_18_encounters_apis.py`

## Event History And SSE

`EventQueue` is the event history source. The server exposes that through:

- `GET /events`;
- `GET /events/subscribe`;
- `server/event_stream.py`.

The stream uses two cursors:

- event cursor: index after the last event;
- combat-log cursor: index after the last combat-log entry.

`make_stream_id(event_cursor, combat_log_cursor)` combines them as
`e=<event>;l=<log>`.

`GameEventPayload` uses `SerializeAsAny[Event]`, which preserves subclass
fields. This matters for spatial/directional events: a generic event response
must not erase fields such as `directional_position`,
`directional_directions`, `directional_channels`, or
`directional_blocks_vision`.

Example EB-18-007 proves `/events` and SSE parity for directional spatial
metadata:

```python
cursor = EventQueue.event_cursor()
get_map().set_tile_directional_border((1, 1), "vision", "east", False)

response = TestClient(app).get(f"/events?since={cursor}&limit=0")
event_payload = response.json()["events"][-1]

assert event_payload["directional_position"] == [1, 1]
assert event_payload["directional_directions"] == ["east"]
assert event_payload["directional_channels"] == ["vision"]
assert event_payload["directional_blocks_vision"]["east"] is True
```

`GET /combat-log` is the combat-log polling DTO. The `since` query is an index,
not an event UUID: clients pass the previous `total` to receive only new entries.

Example EB-18-017 proves cursor-addressed polling:

```python
before = client.get("/combat-log").json()
before_total = before["total"]
assert client.get("/combat-log", params={"since": before_total}).json()["entries"] == []

client.post("/action/self", json={"session_id": session_id, "entity_uuid": str(hero.uuid), "action_name": "Dash"})
new_logs = client.get("/combat-log", params={"since": before_total}).json()
assert new_logs["count"] == 1
assert new_logs["entries"][0]["data"]["action_name"] == "Dash"

repeated = client.get("/combat-log", params={"since": new_logs["total"]}).json()
assert repeated["entries"] == []
```

For live SSE clients, a combat-log envelope must follow the matching completion
`game_event`. The event stream receives combat-log callbacks before the
completion event has been stored, so it keeps pending combat-log payloads by
event lineage and publishes them only after the completion `game_event`.

Example EB-18-018 proves the live ordering:

```python
subscription = event_stream.subscribe()
client.post("/action/self", json={"session_id": session_id, "entity_uuid": str(hero.uuid), "action_name": "Dash"})
envelopes = asyncio.run(drain_stream_subscription(subscription))

dash_log_index = next(
    index for index, envelope in enumerate(envelopes)
    if envelope["event"] == "combat_log"
    and envelope["data"].entry.data.get("action_name") == "Dash"
)
prior_envelope = envelopes[dash_log_index - 1]
assert prior_envelope["event"] == "game_event"
assert prior_envelope["data"].event.phase.value == "completion"
assert envelopes[dash_log_index]["id"] == make_stream_id(
    prior_envelope["data"].event_cursor,
    envelopes[dash_log_index]["data"].combat_log_cursor,
)
```

The CLI displays those same entries through `filter_combat_log()`. The filter
applies temporal visibility from `perceiver_uuids`, then identity visibility
from the caller's current visible-entity set. `revealed_entity_uuids` is treated
as visible for the current log tree, so a hidden creature revealed during an
AoE can be named in its descendant entries without exposing other hidden
targets.

Example EB-18-029 freezes that mixed AoE edge:

```python
parent_entry = {
    "source_uuid": hero_uuid,
    "source_name": "Hero Wizard",
    "revealed_entity_uuids": [revealed_uuid],
    "sub_entries": [
        {"target_uuid": revealed_uuid, "target_name": "Revealed Rogue", ...},
        {"target_uuid": still_hidden_uuid, "target_name": "Still Hidden", ...},
    ],
}

filtered = filter_combat_log([parent_entry], [hero_uuid], {hero_uuid})

assert filtered[0]["sub_entries"][0]["target_name"] == "Revealed Rogue"
assert filtered[0]["sub_entries"][1]["target_name"] == "???"
```

The parent reveal set is inherited by descendants. It does not globally reveal
other hidden targets that happened to be affected by the same AoE.

Parity tests:

- `tests/engine_book/test_chapter_18_encounters_apis.py::test_eb_18_007_event_history_and_sse_payloads_preserve_directional_spatial_fields`
- `tests/engine_book/test_chapter_18_encounters_apis.py::test_eb_18_017_combat_log_endpoint_uses_since_cursor_without_duplication`
- `tests/engine_book/test_chapter_18_encounters_apis.py::test_eb_18_018_combat_log_sse_follows_matching_completion_event`
- `tests/engine_book/test_chapter_18_encounters_apis.py::test_eb_18_029_combat_log_filter_reveals_only_parent_marked_aoe_targets`
- `tests/engine_book/test_chapter_18_encounters_apis.py`

## Mapeditor API

The mapeditor API is a map-state surface, not a full game save. It can create
scratch maps, patch tiles, place/delete floor objects, inspect walkability,
visibility, and light, and save/load map documents.

The important boundary: mapeditor saves should not serialize live entities or
encounter state.

Example EB-18-008 uses a narrow endpoint smoke test:

```python
response = client.post(
    "/mapeditor/maps",
    json={"source": "scratch", "width": 3, "height": 2, "origin": [0, 0], "default_light": 1},
)
snapshot = response.json()

assert snapshot["grid_bounds"] == {"min_x": 0, "min_y": 0, "max_x": 2, "max_y": 1}
assert len(snapshot["tiles"]) == 6

response = client.post("/mapeditor/map/objects", json={"catalog_id": "door", "position": [2, 1]})
assert response.json()["name"] == "Door"

assert client.get("/entities").json()["entities"] == []
```

Example EB-18-022 proves the durable save/load boundary:

```python
client.post("/mapeditor/map/tiles", json={
    "tiles": [
        {"x": 1, "y": 0, "type": "Wall", "light_level": 4},
        {"x": 0, "y": 0, "directional_channel": "movement", "direction": "east", "passable": False},
    ]
})
client.post("/mapeditor/map/objects", json={"catalog_id": "door", "position": [2, 1]})

save_response = client.post("/mapeditor/saves", json={"id": "book_roundtrip", "name": "Book Roundtrip"})
assert save_response.json()["floor_object_count"] == 1

document = client.get("/mapeditor/saves/book_roundtrip").json()
assert set(document["snapshot"]) == {"grid_bounds", "tiles", "floor_objects"}
assert document["object_placements"][0]["catalog_id"] == "door"

client.post("/mapeditor/maps", json={"source": "scratch", "width": 1, "height": 1, "origin": [9, 9]})
loaded = client.post("/mapeditor/saves/book_roundtrip/load").json()
loaded_tiles = {(tile["x"], tile["y"]): tile for tile in loaded["tiles"]}

assert loaded["grid_bounds"] == {"min_x": 0, "min_y": 0, "max_x": 2, "max_y": 1}
assert loaded_tiles[(0, 0)]["directional_blocks_movement"]["east"] is True
assert client.get("/state").json()["entities"] == []
```

Mapeditor failures use the same structured `detail` principle as other Chapter
18 API errors. They include catalog IDs, saved map IDs, current map bounds and
counts when available, and request-specific fields such as `requested_map_id`,
`requested_catalog_id`, `requested_position`, or `requested_tiles`.

Example EB-18-015 proves invalid preset, catalog, tile patch, object delete,
duplicate-save, and missing-save payloads:

```python
unknown_object_response = client.post(
    "/mapeditor/map/objects",
    json={"catalog_id": "unknown_object", "position": [0, 0]},
)
unknown_object = unknown_object_response.json()["detail"]
assert unknown_object["code"] == "mapeditor_object_place_failed"
assert "door" in unknown_object["valid_objects"]
assert "healing_potion" in unknown_object["valid_loot"]
assert unknown_object["current_map"]["tile_count"] == 4

duplicate_response = client.post(
    "/mapeditor/saves",
    json={"id": "book_map", "name": "Book Map"},
)
duplicate = duplicate_response.json()["detail"]
assert duplicate["code"] == "mapeditor_save_failed"
assert "book_map" in duplicate["saved_map_ids"]
```

The raw tile lookup endpoint now follows the same recovery contract. A missing
`/tile/{x}/{y}` request returns `tile_not_found` with the requested position,
current grid bounds, tile count, entity count, and object count. Example
EB-18-024 proves the successful tile payload and the structured 404 shape:

```python
existing_response = client.get("/tile/1/1")
assert existing_response.status_code == 200
assert existing_response.json()["position"] == [1, 1]

missing_response = client.get("/tile/9/9")
detail = missing_response.json()["detail"]
assert detail["code"] == "tile_not_found"
assert detail["requested_position"] == [9, 9]
assert detail["grid_bounds"] == {"min_x": 0, "min_y": 0, "max_x": 1, "max_y": 1}
assert detail["tile_count"] == 4
```

The broader mapeditor baseline lives in `examples/test_mapeditor_api.py`.

Parity tests:

- `tests/engine_book/test_chapter_18_encounters_apis.py::test_eb_18_008_mapeditor_api_saves_map_state_without_entities_or_encounter`
- `tests/engine_book/test_chapter_18_encounters_apis.py::test_eb_18_015_mapeditor_errors_report_catalog_map_and_save_context`
- `tests/engine_book/test_chapter_18_encounters_apis.py::test_eb_18_022_mapeditor_save_load_roundtrip_restores_entity_free_state`
- `tests/engine_book/test_chapter_18_encounters_apis.py::test_eb_18_024_tile_lookup_error_reports_grid_context`
- `tests/engine_book/test_chapter_18_encounters_apis.py`

## Coverage Added

Chapter 18 adds executable coverage for:

- active encounter registration and callback setup/cleanup;
- controller encounter and turn lifecycle callbacks;
- `TurnContext` contents;
- round advancement;
- surprise reaction lockout until the skipped first turn ends;
- `advance_until_player()` stopping on human- and Codex-controlled turns;
- `MeleeAIController` attack, move-closer, pass, and directional-border legal
  Move path decisions;
- API-style action execution and combat-log listener notifications;
- death detection and faction-based encounter ending;
- raw entity/encounter JSON compatibility;
- spell catalog registry non-mutation and endpoint payload;
- root health, encounter wrapper, empty combat-log, and positive
  simulation-control reset/status/delay/pause/step endpoint payloads;
- `/state` DTO boundaries for empty editor maps, floor objects, entities, and
  active encounters;
- event history and SSE directional spatial payloads;
- combat-log polling with `since` cursor semantics and no duplicate entries;
- combat-log SSE ordering after the matching completion game event;
- CLI combat-log filtering for mixed revealed and still-hidden AoE sub-entries;
- a narrow mapeditor API state boundary;
- mapeditor save/load round trips for tiles, directional borders, and floor
  objects without entities or encounter state;
- structured action-endpoint HTTP 400/404 details with action-economy,
  target-validation, and available-action correction context;
- serialized available-action spell slot variants with base spell names, spell
  levels, cast levels, projectile counts, and executable slot-specific names;
- structured entity, handler, and equipment HTTP error details with current
  entity summaries, valid handler names, valid equipment slots, inventory IDs,
  equipped item IDs, and equipment snapshots;
- positive session create/ping/delete lifecycle payloads plus game join,
  game-status, and controlled-entity readback payloads;
- structured session/game, event-filter, SSE session UUID, and simulation-control
  HTTP error details with valid player types, known sessions, known entities,
  event enum choices, cursor state, and delay bounds;
- structured session action-authority HTTP details with requested session/entity,
  known sessions, active game state, controlled entities, and owning session;
- structured `/action/end-turn` encounter-state drift details with session/game
  and simulation context;
- structured mapeditor failure details with valid preset/tile/object/loot IDs,
  saved map IDs, current map summary, directional-patch required fields, and
  request-specific context.
- structured raw tile lookup 404 details with requested position and current
  grid summary.

## Documentation Hygiene Notes

The Chapter 18 pass reviewed encounter/controller/API surfaces from runtime
code and executable examples. The active Codex orchestration path is guarded by
both EB-18-028 and the book-integrity runtime scan, so Claude references cannot
return to executable `cli/`, `dnd/`, or `server/` sources unnoticed.

Server API hygiene is currently enforced at the structured-error and DTO
contract boundaries:
`tests/engine_book/test_book_integrity.py::test_server_http_errors_do_not_use_bare_string_details`
guards the primary action/session API files against bare string
`HTTPException.detail` payloads. The guarded `server/api_models.py` DTO surface
now covers equipment, inventory, appearance, entity-summary/full-entity,
encounter, game-state, grid, floor-object, map-editor map/catalog/layer,
simulation-status, current-turn, spell-catalog, session/join, controlled-entity,
AoE preview, action request, execute-by-index, handler-toggle, action-result,
advance-encounter, event-history, and combat-log-history models. Those 61 API
model classes expose all 320 reviewed public fields through described
`Field(...)` metadata and Google-style class docstrings with field-level
`Attributes:` entries. The map-state pass also removed late imports from the
serializer methods it touched, the map-editor catalog helper now uses the same
stability literal exposed by its DTO, and the spell-catalog pass tightened the
catalog helper return types to the same literal unions exposed by the DTOs. The
SSE/event-stream DTO slice in
`server/event_stream.py` is also guarded: `StreamSyncPayload`,
`GameEventPayload`, `CombatLogPayload`, `HeartbeatPayload`, and `EvictedPayload`
expose all 16 public payload fields through described `Field(...)` metadata and
Google-style class docstrings. The session-authority dataclasses in
`server/session.py` are guarded as well: `PlayerSession` and `GameSession` now
carry dataclass `metadata["description"]` for all 10 public fields, with
matching Google-style class docstrings. Controller model hygiene is guarded for
`dnd/controller.py`: `TurnContext`, `Controller`, `PassController`,
`HumanController`, `CodexController`, `MeleeAIController`, and
`AIAgentController` expose all 21 reviewed public fields through described
`Field(...)` metadata, carry Google-style `Attributes:` docstrings, and the
module is token-scanned to stay comment-free. Encounter model hygiene is guarded
for `dnd/encounter.py`: `AdvanceResult`, `CombatantState`, and `Encounter`
expose all 26 reviewed public fields through described `Field(...)` metadata,
carry Google-style `Attributes:` docstrings, and the module is token-scanned to
stay comment-free. The guarded `server/event_server.py` cleanup slice now covers
`EventMonitor`, `SimulationState`, `setup_combat`, `setup_arena_combat`,
`setup_aoe_test_arena`, `create_dex_fighter`, `create_barbarian_hero`,
`advance_encounter`, the shared structured-error/context helpers, session-action
validation, combat-loop/lifespan helpers, timing middleware, and exception
handlers, plus the root health endpoint, `/state`, map-editor/catalog route
helpers, visibility/entity/grid endpoints, `/tile/{x}/{y}`, `/encounter`,
`/combat-log`, and simulation-control route helpers; those nodes are scanned to
prevent print-debugging and inline comments from returning.
The first guarded session-management slice now also covers session creation,
shared ping/status building, ping, deletion, game joining, game status, and
session-controlled entity readback.
`EventMonitor` and `SimulationState` keep Google-style `Attributes:` docstrings,
while the guarded setup/factory/helper/middleware/route functions keep
Google-style `Args:` plus `Returns:` or `Yields:` docstrings as appropriate. The
equipment-slot helper import is also now module scoped instead of hidden inside
the helper body, and floor-object state filtering now uses named internal/top
level field sets instead of comment-dependent constants.
Broader live-server behavior cleanup remains a later scoped pass.

## Remaining Work

Later tests should cover:

- selected `examples/server_tests/*` only with explicit live-server setup;
- broader controller edge matrices once the live-server setup is part of the
  engine-book test harness.
