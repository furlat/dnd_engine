"""Manual Chapter 25 checks for live replication streams."""

import asyncio
import inspect
from threading import Event as ThreadEvent, Thread

import pytest

from dnd.actions.standard import (
    Dodge,
    Shove,
)
from dnd.core.events.action_events import (
    ShoveEvent,
)
from dnd.core.combat_log import CombatLogEntry, CombatLogEntryType
from dnd.core.dice import fixed_dice_faces
from dnd.core.events.events_registry import (
    Event,
    EventPhase,
    EventQueue,
    EventType,
)
from dnd.encounters.encounter import Encounter
from tests.manual import live_replication_support as live_replication
from server.event_stream import (
    BoundedSubscription,
    HeartbeatPayload,
    StreamSyncPayload,
    event_stream,
    format_sse,
    make_stream_id,
)
from server.api_models import SessionPingResponse
from server.combat_log_source import CombatLogSourceError, CombatLogSourceSlot
from tests.manual.live_replication_support import (
    create_stream_scene,
    drain_subscription,
    execute_stream_attack,
    parse_sse_data,
    reset_live_stream_state,
)


def test_live_stream_surface_exposes_payloads_subscriptions_and_scene(capsys) -> None:
    """The live replication surface exposes stream payloads and scene helpers."""
    scene = create_stream_scene()

    assert scene.hero.name == "Stream Hero"
    assert scene.monster.name == "Stream Skeleton"
    assert scene.encounter.name == "Stream Encounter"
    assert event_stream.current_stream_id(scene.encounter).startswith("e=")
    assert callable(execute_stream_attack)
    assert callable(parse_sse_data)
    assert callable(drain_subscription)
    assert callable(make_stream_id)
    assert callable(reset_live_stream_state)
    assert StreamSyncPayload is not None
    assert HeartbeatPayload is not None
    assert BoundedSubscription is not None

    readout_lines = [
        f"scene: hero={scene.hero.name}, monster={scene.monster.name}, encounter={scene.encounter.name}",
        (
            "stream: "
            f"id={event_stream.current_stream_id(scene.encounter)}, "
            f"event_cursor={event_stream.current_event_cursor()}, "
            f"combat_log_cursor={event_stream.current_combat_log_cursor(scene.encounter)}"
        ),
        (
            "surfaces: "
            f"sync={StreamSyncPayload.__name__}, "
            f"heartbeat={HeartbeatPayload.__name__}, "
            f"subscription={BoundedSubscription.__name__}, "
            f"attack={callable(execute_stream_attack)}, "
            f"parse={callable(parse_sse_data)}, "
            f"drain={callable(drain_subscription)}"
        ),
    ]
    expected_lines = [
        "scene: hero=Stream Hero, monster=Stream Skeleton, encounter=Stream Encounter",
        "stream: id=e=42;l=1, event_cursor=42, combat_log_cursor=1",
        "surfaces: sync=StreamSyncPayload, heartbeat=HeartbeatPayload, subscription=BoundedSubscription, attack=True, parse=True, drain=True",
    ]

    print("\n".join(readout_lines))

    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_sync_frame_reports_the_current_cursor_pair(capsys) -> None:
    """A stream sync frame gives clients the current event and log cursors."""
    scene = create_stream_scene()

    sync_payload = StreamSyncPayload(
        generation_id=str(EventQueue.generation_id()),
        event_cursor=event_stream.current_event_cursor(),
        combat_log_cursor=event_stream.current_combat_log_cursor(scene.encounter),
        session=SessionPingResponse(
            status="ok",
            session_id="stream-session",
            connection_status="connected",
            is_my_turn=True,
            active_entity_uuid=str(scene.hero.uuid),
            active_entity_name=scene.hero.name,
            controlled_entities=[str(scene.hero.uuid)],
        ),
    )
    stream_id = event_stream.current_stream_id(scene.encounter)
    frame = format_sse("sync", sync_payload, stream_id)
    data = parse_sse_data(frame)
    starts_with_id = frame.startswith(f"id: {stream_id}\n")

    assert stream_id == make_stream_id(EventQueue.event_cursor(), len(scene.encounter.combat_log))
    assert starts_with_id
    assert "\nevent: sync\n" in frame
    assert data["event_cursor"] == EventQueue.event_cursor()
    assert data["combat_log_cursor"] == len(scene.encounter.combat_log)
    assert data["session"]["active_entity_name"] == scene.hero.name
    assert data["generation_id"] == str(EventQueue.generation_id())
    assert scene.monster.name == "Stream Skeleton"

    readout_lines = [
        (
            "sync frame: "
            f"id={stream_id}, "
            "event=sync, "
            f"starts_with_id={starts_with_id}"
        ),
        (
            "sync data: "
            f"event_cursor={data['event_cursor']}, "
            f"combat_log_cursor={data['combat_log_cursor']}, "
            f"active_entity={data['session']['active_entity_name']}"
        ),
        (
            "cursor check: "
            f"expected={make_stream_id(EventQueue.event_cursor(), len(scene.encounter.combat_log))}, "
            f"monster={scene.monster.name}"
        ),
    ]
    expected_lines = [
        "sync frame: id=e=42;l=1, event=sync, starts_with_id=True",
        "sync data: event_cursor=42, combat_log_cursor=1, active_entity=Stream Hero",
        "cursor check: expected=e=42;l=1, monster=Stream Skeleton",
    ]

    print("\n".join(readout_lines))

    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_live_stream_reset_composes_engine_and_stream_owned_state(capsys) -> None:
    """The stream reset composes the engine reset with stream-specific hooks."""
    source = inspect.getsource(live_replication.reset_live_stream_state)
    required_fragments = [
        "event_stream.stop()",
        "reset_engine_runtime(grid_size=(width, height))",
        "event_stream.ensure_attached()",
    ]

    assert "reset_combat_state" not in source
    for fragment in required_fragments:
        assert fragment in source

    scene = create_stream_scene()

    assert event_stream.current_event_cursor() == EventQueue.event_cursor()
    assert event_stream.current_combat_log_cursor(scene.encounter) == len(scene.encounter.combat_log)

    readout_lines = [
        (
            "reset source: "
            f"reset_combat_state={'reset_combat_state' in source}, "
            f"required={sum(fragment in source for fragment in required_fragments)}/{len(required_fragments)}"
        ),
        (
            "post reset: "
            f"event_cursor={event_stream.current_event_cursor()}, "
            f"queue_cursor={EventQueue.event_cursor()}, "
            f"log_cursor={event_stream.current_combat_log_cursor(scene.encounter)}, "
            f"logs={len(scene.encounter.combat_log)}"
        ),
    ]
    expected_lines = [
        "reset source: reset_combat_state=False, required=3/3",
        "post reset: event_cursor=42, queue_cursor=42, log_cursor=1, logs=1",
    ]

    print("\n".join(readout_lines))

    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_exact_combat_log_window_retains_original_causal_event_cursor() -> None:
    """Later events cannot move a stored combat-log slot's causal barrier."""
    scene = create_stream_scene()
    combat_log_cursor_before = len(scene.encounter.combat_log)
    subscription = event_stream.subscribe(max_depth=64)
    try:
        execute_stream_attack(scene.hero, scene.monster, scene.encounter)
        envelopes = asyncio.run(drain_subscription(subscription))
    finally:
        event_stream.unsubscribe(subscription)

    live_log = next(
        envelope["data"]
        for envelope in envelopes
        if envelope["event"] == "combat_log"
        and envelope["data"].combat_log_cursor == combat_log_cursor_before + 1
    )
    causal_event_cursor = live_log.event_cursor

    unrelated = Event(
        event_type=EventType.BASE_ACTION,
        source_entity_uuid=scene.hero.uuid,
    )
    unrelated.phase_to(EventPhase.COMPLETION)

    assert EventQueue.event_cursor() > causal_event_cursor

    source = event_stream.capture_combat_log_source_window(
        scene.encounter,
        from_cursor=combat_log_cursor_before,
    )

    assert len(source.slots) == 1
    assert source.generation_id == str(EventQueue.generation_id())
    assert source.slots[0].combat_log_cursor == combat_log_cursor_before + 1
    assert source.slots[0].event_cursor == causal_event_cursor


def test_standalone_combat_log_slot_retains_its_append_cursor() -> None:
    """Standalone informational logs keep the cursor visible at append time."""
    scene = create_stream_scene()
    combat_log_cursor_before = len(scene.encounter.combat_log)
    event_cursor_at_append = EventQueue.event_cursor()
    standalone = CombatLogEntry(
        entry_type=CombatLogEntryType.ACTION,
        source_name=scene.hero.name,
        source_uuid=str(scene.hero.uuid),
        compact="Standalone evidence",
        verbose="Standalone evidence",
        detailed="Standalone evidence",
    )

    EventQueue.push_combat_log(standalone, scene.hero.uuid)
    event_stream.stop()
    event_stream.ensure_attached()
    Event(
        event_type=EventType.BASE_ACTION,
        source_entity_uuid=scene.hero.uuid,
    ).phase_to(EventPhase.COMPLETION)

    assert EventQueue.event_cursor() > event_cursor_at_append

    source = event_stream.capture_combat_log_source_window(
        scene.encounter,
        from_cursor=combat_log_cursor_before,
    )

    assert len(source.slots) == 1
    assert source.slots[0].entry == standalone
    assert source.slots[0].event_cursor == event_cursor_at_append


def test_exact_combat_log_source_window_preserves_finalized_causal_barriers() -> None:
    """Canonical source capture returns one exact finalized page."""
    scene = create_stream_scene()
    from_cursor = len(scene.encounter.combat_log)
    execute_stream_attack(scene.hero, scene.monster, scene.encounter)
    first_total = len(scene.encounter.combat_log)
    later_log = CombatLogEntry(
        entry_type=CombatLogEntryType.ACTION,
        source_name=scene.hero.name,
        source_uuid=str(scene.hero.uuid),
        compact="Later exact source slot",
        verbose="Later exact source slot",
        detailed="Later exact source slot",
    )
    EventQueue.push_combat_log(later_log, scene.hero.uuid)

    window = event_stream.capture_combat_log_source_window(
        scene.encounter,
        from_cursor=from_cursor,
        through_cursor=first_total,
        expected_generation_id=str(EventQueue.generation_id()),
    )

    assert window.source_stream_id == str(scene.encounter.uuid)
    assert window.from_cursor == from_cursor
    assert window.through_cursor == first_total
    assert window.total == len(scene.encounter.combat_log)
    assert [slot.combat_log_cursor for slot in window.slots] == list(
        range(from_cursor + 1, first_total + 1)
    )
    assert all(slot.finalized and slot.causal_cursor_exact for slot in window.slots)
    assert [slot.event_cursor for slot in window.slots] == sorted(
        slot.event_cursor for slot in window.slots
    )

    empty = event_stream.capture_combat_log_source_window(
        scene.encounter,
        from_cursor=first_total,
        through_cursor=first_total,
    )
    assert empty.slots == ()
    assert empty.total > empty.through_cursor


def test_exact_combat_log_source_window_rejects_uncaptured_history() -> None:
    """A missed source append cannot silently acquire an invented barrier."""
    scene = create_stream_scene()
    from_cursor = len(scene.encounter.combat_log)
    standalone = CombatLogEntry(
        entry_type=CombatLogEntryType.ACTION,
        source_name=scene.hero.name,
        source_uuid=str(scene.hero.uuid),
        compact="Missed by exact listener",
        verbose="Missed by exact listener",
        detailed="Missed by exact listener",
    )

    event_stream.stop()
    try:
        EventQueue.push_combat_log(standalone, scene.hero.uuid)
    finally:
        event_stream.ensure_attached()

    with pytest.raises(CombatLogSourceError, match="exact combat-log source slot"):
        event_stream.capture_combat_log_source_window(
            scene.encounter,
            from_cursor=from_cursor,
        )


def test_live_subscription_fans_out_game_events_and_combat_logs() -> None:
    """Subscribers receive queued game-event and combat-log envelopes."""
    scene = create_stream_scene()
    subscription = event_stream.subscribe(max_depth=64)
    try:
        execute_stream_attack(scene.hero, scene.monster, scene.encounter)
        envelopes = asyncio.run(drain_subscription(subscription))
    finally:
        event_stream.unsubscribe(subscription)

    event_names = [envelope["event"] for envelope in envelopes]
    game_event_envelopes = [envelope for envelope in envelopes if envelope["event"] == "game_event"]
    combat_log_envelopes = [envelope for envelope in envelopes if envelope["event"] == "combat_log"]

    assert "game_event" in event_names
    assert "combat_log" in event_names
    assert game_event_envelopes
    assert combat_log_envelopes

    latest_game_event = game_event_envelopes[-1]
    latest_game_payload = latest_game_event["data"]

    assert latest_game_event["id"] == make_stream_id(
        latest_game_payload.event_cursor,
        latest_game_payload.combat_log_cursor,
    )
    assert latest_game_payload.event.phase == EventPhase.COMPLETION.value

    latest_log = combat_log_envelopes[-1]
    latest_log_payload = latest_log["data"]

    assert latest_log["id"] == make_stream_id(
        latest_log_payload.event_cursor,
        latest_log_payload.combat_log_cursor,
    )
    assert latest_log_payload.combat_log_cursor <= len(scene.encounter.combat_log)

def test_enemy_shove_burst_streams_forced_movement_and_trajectory_log() -> None:
    """A server-ahead monster turn retains forced motion and its child log."""
    scene = create_stream_scene()
    scene.hero.weight = 100
    subscription = event_stream.subscribe(max_depth=128)
    event_cursor_before = EventQueue.event_cursor()
    combat_log_cursor_before = len(scene.encounter.combat_log)

    try:
        with fixed_dice_faces(20):
            shove_event = Shove(
                source_entity_uuid=scene.monster.uuid,
                target_entity_uuid=scene.hero.uuid,
            ).apply()
        dodge_event = Dodge(source_entity_uuid=scene.monster.uuid).apply()
        envelopes = asyncio.run(drain_subscription(subscription, limit=128))
    finally:
        event_stream.unsubscribe(subscription)

    assert isinstance(shove_event, ShoveEvent)
    assert shove_event.contest_success is True
    assert dodge_event is not None

    game_event_envelopes = [
        envelope for envelope in envelopes if envelope["event"] == "game_event"
    ]
    completion_envelopes = [
        envelope
        for envelope in game_event_envelopes
        if envelope["data"].event.phase == EventPhase.COMPLETION.value
    ]
    forced_envelope = next(
        envelope
        for envelope in completion_envelopes
        if envelope["data"].event.wire_type
        == "dnd.core.events.ForcedMovementEvent"
    )
    shove_envelope = next(
        envelope
        for envelope in completion_envelopes
        if envelope["data"].event.wire_type == "dnd.actions.standard.ShoveEvent"
    )

    forced_wire = forced_envelope["data"].model_dump(mode="json")["event"]
    assert forced_wire["source_entity_uuid"] == str(scene.monster.uuid)
    assert forced_wire["target_entity_uuid"] == str(scene.hero.uuid)
    assert forced_wire["start_position"] != forced_wire["end_position"]
    assert forced_wire["end_position"] == list(scene.hero.position)
    assert forced_wire["cause"] == "shove"
    assert forced_wire["wire_type"] == "dnd.core.events.ForcedMovementEvent"
    assert forced_wire["event_type"] == "forced_movement"
    assert forced_envelope["data"].event_index < shove_envelope["data"].event_index
    assert game_event_envelopes[-1]["data"].event_cursor == EventQueue.event_cursor()

    assert all(
        envelope["data"].event_index >= event_cursor_before
        for envelope in game_event_envelopes
    )

    source = event_stream.capture_combat_log_source_window(
        scene.encounter,
        from_cursor=combat_log_cursor_before,
    )
    shove_log = next(
        slot.entry
        for slot in source.slots
        if slot.entry.data.get("action_type") == "shove"
    )
    forced_logs = [
        entry
        for entry in shove_log.sub_entries
        if entry.data.get("type") == "forced_movement"
    ]
    assert len(forced_logs) == 1
    assert forced_logs[0].data["start_position"] == forced_wire["start_position"]
    assert forced_logs[0].data["end_position"] == forced_wire["end_position"]
    assert str(tuple(forced_wire["start_position"])) in forced_logs[0].verbose
    assert str(tuple(forced_wire["end_position"])) in forced_logs[0].verbose


def test_combat_log_frames_follow_completion_events_in_the_queue() -> None:
    """Combat-log envelopes are released after completion events are visible."""
    scene = create_stream_scene()
    subscription = event_stream.subscribe(max_depth=64)
    try:
        execute_stream_attack(scene.hero, scene.monster, scene.encounter)
        envelopes = asyncio.run(drain_subscription(subscription))
    finally:
        event_stream.unsubscribe(subscription)

    first_log_index = next(
        index for index, envelope in enumerate(envelopes)
        if envelope["event"] == "combat_log"
    )
    completion_indexes = [
        index for index, envelope in enumerate(envelopes[:first_log_index])
        if envelope["event"] == "game_event"
        and envelope["data"].event.phase == EventPhase.COMPLETION.value
    ]

    assert completion_indexes
    assert first_log_index > completion_indexes[-1]

def test_hot_event_envelopes_carry_the_finalized_causal_log_barrier() -> None:
    """Early events cannot see a log waiting on a later completion cursor."""
    scene = create_stream_scene()
    combat_log_cursor_before = len(scene.encounter.combat_log)
    subscription = event_stream.subscribe(max_depth=64)
    try:
        execute_stream_attack(scene.hero, scene.monster, scene.encounter)
        envelopes = asyncio.run(drain_subscription(subscription))
    finally:
        event_stream.unsubscribe(subscription)

    game_payloads = [
        envelope["data"]
        for envelope in envelopes
        if envelope["event"] == "game_event"
    ]
    log_payload = next(
        envelope["data"]
        for envelope in envelopes
        if envelope["event"] == "combat_log"
        and envelope["data"].combat_log_cursor == combat_log_cursor_before + 1
    )

    assert game_payloads
    assert all(
        payload.combat_log_cursor == combat_log_cursor_before
        for payload in game_payloads
        if payload.event_cursor < log_payload.event_cursor
    )
    causal_completion = next(
        payload
        for payload in game_payloads
        if payload.event_cursor == log_payload.event_cursor
    )
    assert causal_completion.event.phase == EventPhase.COMPLETION.value
    assert causal_completion.combat_log_cursor == log_payload.combat_log_cursor


def test_terminal_event_keeps_the_bound_encounter_source_identity() -> None:
    """Clearing Encounter.active before an end event cannot orphan its stream."""
    scene = create_stream_scene()
    subscription = event_stream.subscribe(max_depth=64)
    active_encounter = Encounter.get_active()
    try:
        Encounter._active_encounter = None
        terminal = Event(
            name="Terminal objective event",
            source_entity_uuid=scene.encounter.uuid,
            event_type=EventType.ENCOUNTER_END,
            phase=EventPhase.COMPLETION,
        )
        envelopes = asyncio.run(drain_subscription(subscription))
    finally:
        Encounter._active_encounter = active_encounter
        event_stream.unsubscribe(subscription)

    payload = next(
        envelope["data"]
        for envelope in envelopes
        if envelope["event"] == "game_event"
        and envelope["data"].event.uuid == str(terminal.uuid)
    )
    assert payload.source_stream_id == str(scene.encounter.uuid)


def test_heartbeat_frame_carries_current_cursors(capsys) -> None:
    """Heartbeat frames keep idle stream clients synchronized with cursors."""
    scene = create_stream_scene()

    heartbeat = HeartbeatPayload(
        generation_id=str(EventQueue.generation_id()),
        server_time=100.0,
        event_cursor=event_stream.current_event_cursor(),
        combat_log_cursor=event_stream.current_combat_log_cursor(scene.encounter),
        session=SessionPingResponse(
            status="ok",
            session_id="stream-session",
            connection_status="connected",
            is_my_turn=True,
            active_entity_uuid=str(scene.hero.uuid),
            active_entity_name=scene.hero.name,
            controlled_entities=[str(scene.hero.uuid)],
        ),
    )
    frame = format_sse("heartbeat", heartbeat, event_stream.current_stream_id(scene.encounter))
    data = parse_sse_data(frame)

    assert "\nevent: heartbeat\n" in frame
    assert data["server_time"] == 100.0
    assert data["event_cursor"] == EventQueue.event_cursor()
    assert data["combat_log_cursor"] == len(scene.encounter.combat_log)
    assert data["session"]["is_my_turn"] is True
    assert data["generation_id"] == str(EventQueue.generation_id())

    readout_lines = [
        (
            "heartbeat frame: "
            "event=heartbeat, "
            f"server_time={data['server_time']}, "
            f"id={event_stream.current_stream_id(scene.encounter)}"
        ),
        (
            "heartbeat cursors: "
            f"event={data['event_cursor']}, "
            f"log={data['combat_log_cursor']}, "
            f"waiting={data['session']['is_my_turn']}"
        ),
    ]
    expected_lines = [
        "heartbeat frame: event=heartbeat, server_time=100.0, id=e=42;l=1",
        "heartbeat cursors: event=42, log=1, waiting=True",
    ]

    print("\n".join(readout_lines))

    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_bounded_subscription_evicts_slow_consumers(capsys) -> None:
    """A full subscription queue emits an eviction envelope instead of growing."""
    subscription = BoundedSubscription(max_depth=1)

    first_enqueued = subscription.try_enqueue({
        "event": "game_event",
        "data": {"event_cursor": 1, "combat_log_cursor": 0},
        "id": "e=1;l=0",
    })
    second_enqueued = subscription.try_enqueue({
        "event": "game_event",
        "data": {"event_cursor": 2, "combat_log_cursor": 0},
        "id": "e=2;l=0",
    })
    envelopes = asyncio.run(drain_subscription(subscription))

    assert first_enqueued is True
    assert second_enqueued is False
    assert subscription.evicted
    assert len(envelopes) == 1
    assert envelopes[0]["event"] == "evicted"
    assert envelopes[0]["data"].reason == "subscriber_queue_overflow"

    readout_lines = [
        (
            "enqueue: "
            f"first={first_enqueued}, "
            f"second={second_enqueued}, "
            f"evicted={subscription.evicted}, "
            f"envelopes={len(envelopes)}"
        ),
        (
            "eviction: "
            f"event={envelopes[0]['event']}, "
            f"reason={envelopes[0]['data'].reason}, "
            f"id={envelopes[0]['id']}"
        ),
    ]
    expected_lines = [
        "enqueue: first=True, second=False, evicted=True, envelopes=1",
        "eviction: event=evicted, reason=subscriber_queue_overflow, id=None",
    ]

    print("\n".join(readout_lines))

    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_finalized_source_listeners_run_after_the_source_lock_is_released() -> None:
    """Passive consumers cannot deadlock against runtime attachment lock order."""
    scene = create_stream_scene()
    entry = CombatLogEntry(
        entry_type=CombatLogEntryType.ACTION,
        source_name="Lock probe",
        source_uuid=str(scene.hero.uuid),
        compact="Lock probe acts",
        verbose="Lock probe acts",
        detailed="Lock probe acts",
    )
    event = Event(
        name="Lock probe",
        source_entity_uuid=scene.hero.uuid,
        event_type=EventType.BASE_ACTION,
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    scene.encounter.combat_log.append(entry)
    acquired = ThreadEvent()
    observed_during_callback: list[bool] = []
    threads: list[Thread] = []

    def listener(_slot: CombatLogSourceSlot) -> None:
        thread = Thread(
            target=lambda: (
                event_stream.current_event_cursor(),
                acquired.set(),
            ),
            daemon=True,
        )
        threads.append(thread)
        thread.start()
        observed_during_callback.append(acquired.wait(timeout=1.0))

    event_stream.add_finalized_combat_log_source_listener(listener)
    try:
        event_stream._on_combat_log(
            scene.encounter,
            len(scene.encounter.combat_log) - 1,
            entry,
            event,
        )
    finally:
        event_stream.remove_finalized_combat_log_source_listener(listener)
        for thread in threads:
            thread.join(timeout=1.0)

    assert observed_during_callback == [True]
    assert acquired.is_set()
