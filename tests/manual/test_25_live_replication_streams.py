"""Manual Chapter 25 checks for live replication streams."""

import asyncio
import inspect

from dnd.core.events import EventPhase, EventQueue
from server import live_replication
from server.event_stream import (
    BoundedSubscription,
    CombatLogPayload,
    HeartbeatPayload,
    StreamSyncPayload,
    event_stream,
    format_sse,
    make_stream_id,
)
from server.live_replication import (
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
        "stream: id=e=52;l=1, event_cursor=52, combat_log_cursor=1",
        "surfaces: sync=StreamSyncPayload, heartbeat=HeartbeatPayload, subscription=BoundedSubscription, attack=True, parse=True, drain=True",
    ]

    print("\n".join(readout_lines))

    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_sync_frame_reports_the_current_cursor_pair(capsys) -> None:
    """A stream sync frame gives clients the current event and log cursors."""
    scene = create_stream_scene()

    sync_payload = StreamSyncPayload(
        event_cursor=event_stream.current_event_cursor(),
        combat_log_cursor=event_stream.current_combat_log_cursor(scene.encounter),
        session={"active_entity": scene.hero.name},
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
    assert data["session"]["active_entity"] == scene.hero.name
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
            f"active_entity={data['session']['active_entity']}"
        ),
        (
            "cursor check: "
            f"expected={make_stream_id(EventQueue.event_cursor(), len(scene.encounter.combat_log))}, "
            f"monster={scene.monster.name}"
        ),
    ]
    expected_lines = [
        "sync frame: id=e=52;l=1, event=sync, starts_with_id=True",
        "sync data: event_cursor=52, combat_log_cursor=1, active_entity=Stream Hero",
        "cursor check: expected=e=52;l=1, monster=Stream Skeleton",
    ]

    print("\n".join(readout_lines))

    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_live_stream_reset_owns_the_stream_runtime_state(capsys) -> None:
    """The stream scene reset names its own runtime state instead of delegating to test helpers."""
    source = inspect.getsource(live_replication.reset_live_stream_state)
    required_fragments = [
        "event_stream.stop()",
        "EventQueue.reset()",
        "SpellProtectionRegistry.reset()",
        "Controller.clear_registry()",
        "Encounter.clear_registry()",
        "GridMap.reset()",
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
        "reset source: reset_combat_state=False, required=7/7",
        "post reset: event_cursor=52, queue_cursor=52, log_cursor=1, logs=1",
    ]

    print("\n".join(readout_lines))

    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_cursor_replay_returns_events_and_logs_after_saved_cursors(capsys) -> None:
    """Saved cursors replay only the game events and combat logs after them."""
    scene = create_stream_scene()
    event_cursor_before, combat_log_cursor_before = execute_stream_attack(
        scene.hero,
        scene.monster,
        scene.encounter,
    )

    game_events = event_stream.iter_game_events_since(event_cursor_before, scene.encounter)
    combat_logs = event_stream.iter_combat_logs_since(scene.encounter, combat_log_cursor_before)

    assert game_events
    assert combat_logs
    assert game_events[0].event_index == event_cursor_before
    assert game_events[-1].event_cursor == EventQueue.event_cursor()
    assert all(payload.event_cursor == payload.event_index + 1 for payload in game_events)
    assert any(payload.event.phase == EventPhase.COMPLETION for payload in game_events)
    assert combat_logs[0].log_index == combat_log_cursor_before
    assert combat_logs[-1].combat_log_cursor == len(scene.encounter.combat_log)
    assert all(isinstance(payload, CombatLogPayload) for payload in combat_logs)

    completion_count = sum(
        payload.event.phase == EventPhase.COMPLETION for payload in game_events
    )
    readout_lines = [
        f"saved cursors: event={event_cursor_before}, log={combat_log_cursor_before}",
        (
            "replay: "
            f"game_events={len(game_events)}, "
            f"combat_logs={len(combat_logs)}, "
            f"completions={completion_count}"
        ),
        (
            "cursor range: "
            f"first_event={game_events[0].event_index}, "
            f"last_cursor={game_events[-1].event_cursor}, "
            f"log_cursor={combat_logs[-1].combat_log_cursor}"
        ),
        (
            "payload types: "
            f"logs_are_combat={all(isinstance(payload, CombatLogPayload) for payload in combat_logs)}"
        ),
    ]
    expected_lines = [
        "saved cursors: event=52, log=1",
        "replay: game_events=26, combat_logs=1, completions=6",
        "cursor range: first_event=52, last_cursor=78, log_cursor=2",
        "payload types: logs_are_combat=True",
    ]

    print("\n".join(readout_lines))

    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_live_subscription_fans_out_game_events_and_combat_logs(capsys) -> None:
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
    assert latest_game_payload.event.phase == EventPhase.COMPLETION

    latest_log = combat_log_envelopes[-1]
    latest_log_payload = latest_log["data"]

    assert latest_log["id"] == make_stream_id(
        latest_log_payload.event_cursor,
        latest_log_payload.combat_log_cursor,
    )
    assert latest_log_payload.combat_log_cursor <= len(scene.encounter.combat_log)

    readout_lines = [
        (
            "fanout: "
            f"total={len(envelopes)}, "
            f"game_events={len(game_event_envelopes)}, "
            f"combat_logs={len(combat_log_envelopes)}"
        ),
        (
            "latest game: "
            f"id={latest_game_event['id']}, "
            f"phase={latest_game_payload.event.phase.value}, "
            f"cursor={latest_game_payload.event_cursor}"
        ),
        (
            "latest log: "
            f"id={latest_log['id']}, "
            f"log_cursor={latest_log_payload.combat_log_cursor}, "
            f"within_log={latest_log_payload.combat_log_cursor <= len(scene.encounter.combat_log)}"
        ),
    ]
    expected_lines = [
        "fanout: total=27, game_events=26, combat_logs=1",
        "latest game: id=e=78;l=2, phase=completion, cursor=78",
        "latest log: id=e=78;l=2, log_cursor=2, within_log=True",
    ]

    print("\n".join(readout_lines))

    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_combat_log_frames_follow_completion_events_in_the_queue(capsys) -> None:
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
        and envelope["data"].event.phase == EventPhase.COMPLETION
    ]

    assert completion_indexes
    assert first_log_index > completion_indexes[-1]

    readout_lines = [
        (
            "ordering: "
            f"first_log_index={first_log_index}, "
            f"last_completion_before_log={completion_indexes[-1]}, "
            f"completions_before_log={len(completion_indexes)}"
        ),
        f"log_after_completion={first_log_index > completion_indexes[-1]}",
    ]
    expected_lines = [
        "ordering: first_log_index=26, last_completion_before_log=25, completions_before_log=6",
        "log_after_completion=True",
    ]

    print("\n".join(readout_lines))

    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_heartbeat_frame_carries_current_cursors(capsys) -> None:
    """Heartbeat frames keep idle stream clients synchronized with cursors."""
    scene = create_stream_scene()

    heartbeat = HeartbeatPayload(
        server_time=100.0,
        event_cursor=event_stream.current_event_cursor(),
        combat_log_cursor=event_stream.current_combat_log_cursor(scene.encounter),
        session={"waiting_for_input": True},
    )
    frame = format_sse("heartbeat", heartbeat, event_stream.current_stream_id(scene.encounter))
    data = parse_sse_data(frame)

    assert "\nevent: heartbeat\n" in frame
    assert data["server_time"] == 100.0
    assert data["event_cursor"] == EventQueue.event_cursor()
    assert data["combat_log_cursor"] == len(scene.encounter.combat_log)
    assert data["session"]["waiting_for_input"] is True

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
            f"waiting={data['session']['waiting_for_input']}"
        ),
    ]
    expected_lines = [
        "heartbeat frame: event=heartbeat, server_time=100.0, id=e=52;l=1",
        "heartbeat cursors: event=52, log=1, waiting=True",
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
