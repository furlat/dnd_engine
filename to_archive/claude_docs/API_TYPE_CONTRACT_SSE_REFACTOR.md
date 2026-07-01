# API Type Contract For SSE Refactor

Date: 2026-04-22

This document defines the clean type contract we should use before continuing
the SSE work. It exists because the previous equipment-rendering repair added a
server-side event serialization patch (`resulting_equipment`) that is convenient
but conceptually wrong for an event-sourced client.

The goal is one elegant rule across REST and SSE:

```text
Domain facts are domain Pydantic models.
REST responses are API Pydantic DTOs.
SSE frames are transport Pydantic envelopes around domain models.
No endpoint mutates or enriches historical events during serialization.
```

## The Problem We Found

`server/event_serialization.py` currently does this:

```python
event_data = event.model_dump(mode="json")

if isinstance(event, EquipmentEvent):
    entity = Entity.get(event.source_entity_uuid)
    event_data["resulting_equipment"] = APIEquipmentOverview.create(entity)
```

That was introduced so the client could update rendered equipment without
having a real equipment reducer. It is a hack.

Why it is wrong:

- the event stream no longer contains only original events;
- serializing an old event can read current entity state;
- replay becomes time-dependent;
- server API DTOs leak into domain event serialization;
- REST `/events`, WebSocket history, and SSE would all depend on an implicit
  lookup instead of immutable event facts.

The fix is not to make a better patch. The fix is to remove the category.

## Layer Contract

### 1. Domain Layer

Files:

- `dnd/core/events.py`
- `dnd/blocks/equipment.py`
- `dnd/core/combat_log.py`
- other `dnd/**` domain modules

Domain objects are Pydantic models. They are the canonical game facts.

Examples:

- `Event`
- `MovementEvent`
- `TakeDamageEvent`
- `WeaponEquipEvent`
- `ArmorUnequipEvent`
- `SensoryUpdateEvent`
- `CombatLogEntry`

Rule:

```text
If a fact is required to replay the event later, it belongs on the domain event
model at event creation/completion time.
```

Not allowed:

- importing `server.api_models` from `dnd`;
- adding API DTOs to domain event fields;
- looking up current `Entity` state while serializing a historical event;
- adding presentation-only fields such as `resulting_equipment` in a serializer.

Allowed:

- adding new domain event fields when they are true event facts;
- serializing domain models with `model_dump(mode="json")`;
- wrapping domain models in transport DTOs.

### 2. REST API Layer

Files:

- `server/api_models.py`
- `server/event_server.py`

REST endpoints return Pydantic API DTOs through FastAPI `response_model`.

REST is allowed to return current-state snapshots because REST query/command
responses are not the event log.

Examples:

- `APIGameState`
- `APIEntitySummary`
- `APIEquipmentOverview`
- `SessionPingResponse`
- `ActionResult`

Rule:

```text
REST responses may describe current state, but they must not pretend that
current-state snapshots are fields on historical events.
```

So this is fine:

```python
class EquipItemResponse(BaseModel):
    success: bool
    message: str
    equipment: APIEquipmentOverview
    event_cursor_after: int
    combat_log_cursor_after: int
```

This is not fine:

```python
class WeaponEquipEvent(Event):
    resulting_equipment: APIEquipmentOverview  # API DTO inside domain event
```

This is also not fine:

```python
def serialize_event(event):
    data = event.model_dump()
    data["resulting_equipment"] = APIEquipmentOverview.create(Entity.get(...))
```

### 3. SSE Transport Layer

Files:

- proposed `server/event_stream.py`

SSE frames are typed Pydantic envelopes.

SSE is a transport for already-existing facts. It adds cursor metadata but does
not rewrite the event.

Use Pydantic models like:

```python
from pydantic import BaseModel, SerializeAsAny

class GameEventFrame(BaseModel):
    event_index: int
    event_cursor: int
    combat_log_cursor: int
    event: SerializeAsAny[Event]

class CombatLogFrame(BaseModel):
    log_index: int
    event_cursor: int
    combat_log_cursor: int
    entry: CombatLogEntry
```

The important part is `SerializeAsAny[Event]`: the envelope field is typed as
the domain base event, but serialization keeps subclass fields.

For SSE, FastAPI cannot use a normal JSON `response_model` because the response
is `text/event-stream`. That does not mean the payload becomes untyped. The
server should instantiate the Pydantic frame model and write
`frame.model_dump_json()` into `data:`.

## REST Contract

### Query Endpoints

REST query endpoints should be typed DTOs.

Target shapes:

```python
class EventHistoryResponse(BaseModel):
    events: list[SerializeAsAny[Event]]
    count: int
    total: int

class CombatLogHistoryResponse(BaseModel):
    entries: list[CombatLogEntry]
    count: int
    total: int
```

Rules:

- `/events` returns original domain events, not enriched dicts.
- `/combat-log` returns original `CombatLogEntry` models.
- `/state` returns `APIGameState`.
- `/visibility` returns a visibility DTO.
- `/entity/{uuid}/equipment` returns `APIEquipmentOverview`.
- `/entity/{uuid}/equippable-items` should have a DTO, not a raw dict.

Current problem areas to clean up:

- `/events` uses `serialize_event(e)`.
- `/combat-log` returns raw dict shape.
- several endpoints return anonymous dicts without `response_model`.

### Command Endpoints

Command responses should be small typed DTOs. They are acknowledgements and
handoffs, not miniature event streams.

Target `ActionResult` direction:

```python
class ActionResult(BaseModel):
    success: bool
    message: str
    turn_continues: bool
    encounter_ended: bool
    available_actions: Optional[AvailableActionsDTO] = None
    state: Optional[APIGameState] = None  # fallback/resync only
    event_cursor_after: int
    combat_log_cursor_after: int
```

Fields to remove or demote from normal browser flow:

- `event_data`
- `combat_log_entries`
- `triggered_reactions`
- duplicated HP/death summaries when they are only restating event/log facts

Those fields were useful for CLI and pre-SSE UI. The browser should instead wait
for `event_cursor_after` and `combat_log_cursor_after` on the SSE stream.

Equipment commands can return a snapshot because they are REST commands:

```python
class EquipmentMutationResult(BaseModel):
    success: bool
    message: str
    equipment: APIEquipmentOverview
    event_cursor_after: int
    combat_log_cursor_after: int
```

That snapshot updates the equipment panel immediately. It is not injected into
the event stream.

## SSE Contract

Endpoint:

```text
GET /events/subscribe?session_id=<uuid>&since_event=<n>&since_log=<m>
```

Frame models:

```python
class StreamSyncFrame(BaseModel):
    event_cursor: int
    combat_log_cursor: int
    session: Optional[SessionPingResponse]

class GameEventFrame(BaseModel):
    event_index: int
    event_cursor: int
    combat_log_cursor: int
    event: SerializeAsAny[Event]

class CombatLogFrame(BaseModel):
    log_index: int
    event_cursor: int
    combat_log_cursor: int
    entry: CombatLogEntry

class SessionFrame(BaseModel):
    session: SessionPingResponse

class HeartbeatFrame(BaseModel):
    server_time: str
    event_cursor: int
    combat_log_cursor: int
    session: Optional[SessionPingResponse]

class EvictedFrame(BaseModel):
    reason: str
```

Frame names:

- `sync`
- `game_event`
- `combat_log`
- `session`
- `heartbeat`
- `evicted`

Cursor rules:

- `event_cursor` is the raw `EventQueue` cursor.
- It counts all phases, not only completion events.
- `combat_log_cursor` is the index after the last emitted log entry.
- Duplicate frames across reconnect are allowed.
- Missing frames are not allowed.

Event rule:

```text
GameEventFrame.event is the original Pydantic event model.
```

No `resulting_equipment`. No transport-injected event fields.

## Equipment Contract

Equipment has three separate concepts that should stay separate.

### Domain Event

Current equipment events carry:

- `event_type`
- `source_entity_uuid`
- `item_uuid`
- `slot`
- normal event lifecycle fields

That is the event.

If we later discover this is insufficient for replay, we add domain fields to
the equipment events. For example, a true domain field like
`previous_item_uuid` could make swap replay clearer. But we do not add
`APIEquipmentOverview` to the event.

### REST Snapshot

`APIEquipmentOverview` is a current-state snapshot for UI/query purposes.

It is valid in:

- `GET /entity/{uuid}/equipment`
- equip/unequip command response
- bootstrap snapshots if we decide to include equipment there later

It is not valid as a dynamic field appended to historical events.

### Client State

The client should keep an equipment cache by entity:

```text
entitiesEquipmentById: Map<EntityUuid, APIEquipmentOverview>
```

It can be updated from:

- bootstrap equipment queries;
- the REST equip/unequip response for the controlled entity;
- original equipment events, reduced against the known item cache.

If the client cannot reduce an equipment event because it lacks item metadata,
that is not a reason to enrich event serialization. It means the event/item
domain contract is missing a real fact, and we should add that fact properly.

## Current Violations To Remove

Backend:

- `server/event_serialization.py`
  - remove `resulting_equipment` enrichment;
  - likely delete the file or reduce it to a trivial compatibility helper.

- `server/event_server.py`
  - `/events` should not call `serialize_event`;
  - WebSocket, if still present temporarily, should not call `serialize_event`;
  - REST endpoints that return anonymous dicts should gain Pydantic response
    models as we touch them.

- `examples/test_appearance_api.py`
  - remove or replace `test_equipment_event_serializer_has_resulting_equipment`.

Frontend:

- `app/src/engine/events.ts`
  - remove `resulting_equipment` from `EquipmentEvent`.

- `app/src/engine/applyEventsToStore.ts`
  - stop applying equipment snapshots from event payloads.
  - replace with a real equipment reducer or a deliberate command-response
    update path.

- comments/docs mentioning "backend resulting_equipment" should be deleted.

## Clean Implementation Direction

1. Define API DTOs in `server/api_models.py`:
   - `EventHistoryResponse`
   - `CombatLogHistoryResponse`
   - `EquipmentMutationResult`
   - any missing command/query response models.

2. Define SSE DTOs in `server/event_stream.py` or a dedicated
   `server/stream_models.py`:
   - `GameEventFrame`
   - `CombatLogFrame`
   - `StreamSyncFrame`
   - `SessionFrame`
   - `HeartbeatFrame`
   - `EvictedFrame`

3. Make event history and stream frames wrap original Pydantic events:

   ```python
   event: SerializeAsAny[Event]
   ```

4. Remove `server/event_serialization.py` enrichment and all client reliance on
   `resulting_equipment`.

5. Make command responses cursor-based:

   ```text
   event_cursor_after
   combat_log_cursor_after
   ```

6. Move equipment rendering correctness to a real reducer/cache decision:
   - for now, REST equip/unequip response updates the local actor equipment;
   - original equipment events can update known equipment caches;
   - if replay needs more item facts, add domain event fields, not serializer
     patches.

## Definition Of Correct

The contract is correct when:

- serializing an old event never reads current entity state;
- `/events` and SSE `game_event` expose the same original event facts;
- REST snapshots are typed API DTOs and not confused with event facts;
- SSE frames are typed Pydantic envelopes;
- equipment rendering no longer depends on `resulting_equipment`;
- action processing waits on cursors, not duplicated `event_data` or inline
  combat logs;
- no server serializer mutates event shape for presentation convenience.

This gives us one clean system:

```text
dnd domain Pydantic events
        |
        | wrapped, not patched
        v
SSE frame Pydantic models

dnd/domain current state
        |
        | projected intentionally
        v
REST API Pydantic DTOs
```

No hidden serializer magic. No current-state lookups while replaying history.
No duplicate truths.
