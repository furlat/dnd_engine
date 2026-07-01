# Chapter 25 Plan: Live Replication Streams

## Reader Promise

Explain how a running game publishes state changes to clients and agents after
turn decisions resolve. The reader should understand event cursors, combat-log
cursors, composite stream IDs, sync frames, replay by cursor, live subscription
fan-out, heartbeat frames, and slow-subscriber eviction.

## Concepts Introduced

- Event cursor as the next unread position in `EventQueue` history.
- Combat-log cursor as the next unread position in an encounter log.
- Composite SSE IDs through `make_stream_id()`.
- `StreamSyncPayload`, `GameEventPayload`, `CombatLogPayload`,
  `HeartbeatPayload`, and `EvictedPayload`.
- `DndEventStream` as the fan-out bridge from events and combat logs to
  clients.
- Catch-up replay through `iter_game_events_since()` and
  `iter_combat_logs_since()`.
- Bounded subscription queues and eviction on overflow.

## Concepts Forbidden

- Repeating generic session creation and action execution from Chapter 18.
- Repeating controller ownership from Chapter 24.
- Treating stream frames as a second rules layer.
- Public references to internal planning, verification, or legacy tests.

## Required Visual

- Live replication diagram: engine event history, encounter combat log,
  cursor pairs, sync frame, catch-up replay, live fan-out, heartbeat, and
  eviction boundary.

## Source Files Verified

- `server/event_stream.py` for payload models, stream IDs, SSE formatting,
  subscriptions, replay, fan-out, and eviction.
- `server/event_server.py` for `/events`, `/combat-log`, and
  `/events/subscribe` stream behavior.
- `dnd/core/events.py` for event cursor and event-history iteration.
- `dnd/encounter.py` for combat-log listener registration and encounter-log
  cursor semantics.
- `tests/manual/test_18_sessions_api_client_contract.py` to avoid duplicating
  the generic client API chapter.
- `tests/engine_book/test_chapter_18_encounters_apis.py` and
  `examples/test_directional_event_stream.py` as legacy coverage references
  only.

## Public Example Contract

- One named MDX flow: `live-replication-streams`.
- The visible public code creates a deterministic stream scene, resolves one
  real attack, and asserts the exact stream payload behavior: sync frame
  cursors, cursor replay, subscription fan-out, completion/log ordering,
  heartbeat formatting, and eviction.

## Verification

- Focused manual checks:
  `uv run pytest tests/manual/test_25_live_replication_streams.py`
- Exact public snippet execution:
  `uv run pytest tests/book_examples/test_public_mdx_snippets.py`
- Combined manual gate:
  explicit manual files 01-25 plus `tests/book_examples/test_public_mdx_snippets.py`.
