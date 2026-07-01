# Chapter 18 Plan: Sessions, APIs, And Client Payloads

## Reader Promise

This chapter teaches how the running encounter becomes a client-facing game:
player sessions, controlled entities, turn ownership, state snapshots,
available-action payloads, indexed action execution, event/log cursors, and
catalog metadata.

## Concepts Introduced For The First Time

- `PlayerSession`
- `GameSession`
- `SessionManager`
- `CreateSessionRequest` / `CreateSessionResponse`
- `JoinGameRequest` / `JoinGameResponse`
- `APIGameState`
- `APICurrentTurn`
- `ActionResult`
- `EventHistoryResponse`
- `CombatLogHistoryResponse`
- `SpellCatalogResponse`
- SSE stream IDs through `make_stream_id()`

## Concepts Kept Out Of This Chapter

- Map-editor authoring endpoints.
- Equipment mutation routes.
- Handler toggling routes.
- WebSocket internals.
- Codex orchestration subprocess execution.
- Full server deployment.

Those are follow-on chapters once the client contract is clear.

## Runtime Sources Studied

- `server/session.py`
- `server/api_models.py`
- `server/event_server.py`
- `server/event_stream.py`
- `server/spell_catalog.py`
- `dnd/encounter.py`
- `dnd/actions_functional.py`
- `dnd/core/events.py`
- `dnd/core/combat_log.py`

## Game Meaning

The previous chapter established the encounter as the runtime table manager.
This chapter exposes that table to a client. The client does not mutate engine
internals directly. It joins a game through a session, receives entity and turn
payloads, discovers available choices, submits an indexed action, and consumes
event/log deltas through cursors.

## Visual

Add `/diagrams/sessions-api-client-contract.svg` and matching Excalidraw source.
The diagram should show:

- browser/tool client;
- session creation;
- game join and entity ownership;
- state/current-turn/action reads;
- action execution;
- event and combat-log cursors;
- catalog metadata.

## Public Example Contract

Use one named exact-execution group:

- `client-api-contract`

Example blocks:

- EB-18-001: create a session, join the game, ping, and read game status.
- EB-18-002: read state, current turn, and available action payloads.
- EB-18-003: execute an indexed action through `/action/execute`.
- EB-18-004: read event and combat-log history through cursors and format an SSE
  combat-log frame.
- EB-18-005: read spell catalog metadata for UI and VFX planning.

Public setup helpers must be visible and tutorial-facing:

- `reset_client_api_state`
- `create_api_pair`
- `start_api_game`
- `create_session_and_join_hero`
- `create_joined_client_game`
- `make_melee_attack_auto_hit`
- `clear_melee_attack_modifier`
- `attack_target_index`
- `execute_manual_attack`

## Verification

Focused test:

```bash
uv run pytest tests/manual/test_18_sessions_api_client_contract.py tests/book_examples/test_public_mdx_snippets.py
```

The focused manual test passed before publication:

- `tests/manual/test_18_sessions_api_client_contract.py`: 5 passed.

After public page and harness enrollment, the exact public snippet runner should
increase by one example group.
