"""Manual checks for strict session-subjective AI observation streams."""

import asyncio
from uuid import UUID, uuid4
import json

from fastapi.testclient import TestClient

import server.agent_runtime.observation_projector as observation_projector
from ai.knowledge import derive_agent_facts
from dnd.ai.contracts.observation_replay import (
    apply_observation_frame,
    materialize_snapshot,
)
from dnd.ai.contracts.observation import ObservationFrame
from dnd.actions_functional import execute_use_action
from dnd.conditions import Invisible
from dnd.controller import Controller, HumanController, PassController
from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import (
    BaseCondition,
    SpellProtectionRegistry,
)
from dnd.core.condition_types import ConditionAgencyDenial, ConditionRemovalTrigger
from dnd.core.base_object import BaseObject
from dnd.core.combat_log import CombatLogEntry, CombatLogEntryType
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import (
    Event,
    EventPhase,
    EventQueue,
    SensesUpdateHint,
    EventType,
    SensoryUpdateEvent,
    SensoryUpdateReason,
    SpatialChangeEvent,
    TakeDamageEvent,
    _enrich_multi_entity_log_from_children,
)
from dnd.core.gridmap import GridMap, get_map
from dnd.core.life_types import LifeState
from dnd.core.modifiers import AutoHitModifier, AutoHitStatus, DamageType
from dnd.core.values import BaseValue
from dnd.encounter import Encounter
from dnd.entity import Entity
from dnd.items.test_items import PullLeverAction, TrapLever
from dnd.monsters.bestiary import create_goblin, create_skeleton
from dnd.scenarios.ai_validation_arenas import create_ai_validation_arena
from dnd.spells import MagicMissile
from dnd.spells.enchantment import HoldPersonEffect
from dnd.spells.illusion import HypnoticPatternEffect
from dnd.spells.abjuration import ShieldBuff
from dnd.spells.effect_ids import MAGIC_MISSILE_DAMAGE_EFFECT_ID
from dnd.utils import set_hp
from dnd.tiles import create_spike_zone
from server.agent_runtime.observation_projector import (
    _projection_cache,
    _completion_sequence_needs_immediate_projection,
    _event_should_patch_entity_hit_points,
    _event_should_patch_referenced_entities,
    observation_wakeup_stream,
)
from server.combat_log_projection import _sanitize_multi_entity_log_summary
from dnd.actions import MovementEvent
from dnd.blocks.base_item import ItemChargeConsumptionEvent
from server.event_server import app, sim
from server.event_stream import event_stream
from server.session import PlayerType
from dnd.blocks.sensory import SpatialSensesCallback
from dnd.content_system.item_bindings import ItemRuntimeOrigin
from dnd.content_system.item_materialization import materialize_item
from dnd.items.consumables import HEALING_POTION_RECIPE


def reset_observation_state(width: int = 16, height: int = 10) -> None:
    """Clear runtime state for one observation-stream scenario."""
    event_stream.stop()
    EventQueue.reset()
    EventQueue.set_combat_log_callback(None)
    EventQueue.set_perceiver_computer(None)
    EventQueue.set_revealed_computer(None)
    SpellProtectionRegistry.reset()
    BaseObject._registry.clear()
    BaseBlock._registry.clear()
    BaseCondition._registry.clear()
    BaseValue._registry.clear()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()
    Controller.clear_registry()
    Encounter.clear_registry()
    Encounter._combat_log_listeners.clear()
    GridMap.reset()
    get_map().create_rectangle(0, 0, width, height)
    sim.reset()


def create_observation_game(
    hidden_monster: bool = False,
    second_hero: bool = False,
) -> tuple[TestClient, str, Entity, Entity, Encounter]:
    """Create an active game with one session controlling the hero side."""
    reset_observation_state()
    hero = create_goblin(name="Observation Hero", position=(1, 1), faction="heroes")
    monster = create_skeleton(name="Observation Skeleton", position=(2, 1), faction="monsters")
    extra_hero = None
    if second_hero:
        extra_hero = create_goblin(name="Observation Ally", position=(1, 2), faction="heroes")
    if hidden_monster:
        monster.add_condition(Invisible(source_entity_uuid=monster.uuid, target_entity_uuid=monster.uuid))

    Entity.update_all_entities_senses(max_distance=20)

    encounter = Encounter(name="Observation Encounter", source_entity_uuid=uuid4())
    encounter.add_combatant(hero, HumanController(source_entity_uuid=hero.uuid))
    if extra_hero is not None:
        encounter.add_combatant(extra_hero, HumanController(source_entity_uuid=extra_hero.uuid))
    encounter.add_combatant(monster, PassController(source_entity_uuid=monster.uuid))
    encounter.roll_initiative()
    encounter.initiative_order = [hero.uuid] + ([extra_hero.uuid] if extra_hero else []) + [monster.uuid]
    encounter.current_turn_index = 0
    encounter.start_encounter()
    encounter.start_turn()
    sim.encounter = encounter
    game = sim.create_game_session(encounter)

    manager = sim.get_session_manager()
    session = manager.create_session(PlayerType.AI, "Observation Agent")
    game.add_player(session)
    game.assign_entity(hero.uuid, session.session_id)
    if extra_hero is not None:
        game.assign_entity(extra_hero.uuid, session.session_id)

    return TestClient(app), str(session.session_id), hero, monster, encounter


def bootstrap_player_replication(client: TestClient, session_id: str) -> dict:
    """Bind one canonical subjective partition and return its exact identities."""
    response = client.get(
        "/replication/bootstrap",
        params={"session_id": session_id},
    )
    assert response.status_code == 200, response.text
    return response.json()


def get_player_combat_log_window(
    client: TestClient,
    session_id: str,
    bootstrap: dict,
    *,
    from_cursor: int,
) -> dict:
    """Read one exact identity-bound subjective combat-log cursor window."""
    protocol = bootstrap["protocol"]
    perspective = bootstrap["perspective"]
    response = client.get(
        "/replication/combat-log",
        params={
            "session_id": session_id,
            "expected_source_stream_id": protocol["source_stream_id"],
            "expected_generation_id": protocol["generation_id"],
            "expected_perspective_epoch_id": perspective["perspective_epoch_id"],
            "from_combat_log_cursor": from_cursor,
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["source_stream_id"] == protocol["source_stream_id"]
    assert payload["generation_id"] == protocol["generation_id"]
    assert payload["perspective_epoch_id"] == perspective["perspective_epoch_id"]
    assert payload["from_cursor"] == from_cursor
    return payload


def add_auto_hit(entity: Entity) -> UUID:
    """Add an auto-hit attack modifier for deterministic replay checks."""
    modifier = AutoHitModifier(
        name="Observation Auto Hit",
        value=AutoHitStatus.AUTOHIT,
        source_entity_uuid=entity.uuid,
        target_entity_uuid=entity.uuid,
    )
    return entity.equipment.melee_attack_bonus.self_static.add_auto_hit_modifier(modifier)


def attack_target_index(actions: dict, target_uuid: UUID) -> int:
    """Return the target index for a visible melee target."""
    for action in actions["entity_actions"]:
        if action["template_name"] != "Attack_MELEE_MAIN":
            continue
        for target in action["valid_targets"]:
            if target.get("target_uuid") == str(target_uuid):
                return target["index"]
    raise AssertionError("Target was not present in available melee attacks")


def move_target_with_long_path(actions: dict) -> int:
    """Return a movement target index with at least two path steps."""
    for action in actions["position_actions"]:
        if action["template_name"] != "Move":
            continue
        for target in action["valid_targets"]:
            if len(target.get("path") or []) >= 3:
                return target["index"]
    raise AssertionError("Long movement target was not present")


def move_target_for_position(actions: dict, position: tuple[int, int]) -> int:
    """Return a movement target index for a specific position."""
    for action in actions["position_actions"]:
        if action["template_name"] != "Move":
            continue
        for target in action["valid_targets"]:
            if tuple(target.get("position") or ()) == position:
                return target["index"]
    raise AssertionError(f"Move target {position} was not present")


def complete_event(event):
    """Register an event through the normal lifecycle."""
    current = EventQueue.register(event)
    current = EventQueue.register(current.phase_to(EventPhase.EXECUTION))
    current = EventQueue.register(current.phase_to(EventPhase.EFFECT))
    return EventQueue.register(current.phase_to(EventPhase.COMPLETION))


def test_ai_observation_snapshot_contains_subjective_data() -> None:
    """A session snapshot contains controlled observers and visible facts."""
    client, session_id, hero, monster, encounter = create_observation_game()

    response = client.get(f"/ai/sessions/{session_id}/observation/snapshot")
    payload = response.json()
    known_names = {entity["name"] for entity in payload["known_entities"]}
    skeleton_fact = next(entity for entity in payload["known_entities"] if entity["uuid"] == str(monster.uuid))
    observer = payload["observers"][0]

    assert response.status_code == 200
    assert payload["session"]["session_id"] == session_id
    assert payload["session"]["controlled_entity_uuids"] == [str(hero.uuid)]
    assert payload["session"]["is_my_turn"] is True
    assert payload["encounter"]["uuid"] == str(encounter.uuid)
    assert observer["observer_uuid"] == str(hero.uuid)
    assert observer["visible_cells"]
    assert observer["seen_cells"]
    assert str(monster.uuid) in observer["visible_entity_uuids"]
    assert {"Observation Hero", "Observation Skeleton"} <= known_names
    assert skeleton_fact["creature_type"] == "undead"
    assert "Bludgeoning" in skeleton_fact["damage_vulnerabilities"]
    assert "Poison" in skeleton_fact["damage_immunities"]
    assert payload["observation_cursor"] == 0


def test_subjective_tiles_disclose_local_domain_boundaries_without_remote_map_shape() -> None:
    """Known tiles classify adjacent void while existing neighbors remain unknown."""
    client, session_id, _hero, _monster, _encounter = create_observation_game()

    payload = client.get(
        f"/ai/sessions/{session_id}/observation/snapshot"
    ).json()
    tiles = {tile["key"]: tile for tile in payload["known_tiles"]}

    assert tiles["0,0"]["adjacent_domain"]["-1,0"] == "invalid"
    assert tiles["0,0"]["adjacent_domain"]["0,-1"] == "invalid"
    assert tiles["0,0"]["adjacent_domain"]["1,0"] == "unknown"
    assert tiles["1,1"]["adjacent_domain"]["1,0"] == "unknown"


def test_subjective_health_separates_normal_temporary_and_blocked_healing() -> None:
    """Healing policy inputs preserve normal HP beneath temporary protection."""
    client, session_id, hero, _monster, _encounter = create_observation_game()
    max_hp = hero.get_max_hp()
    set_hp(hero, max_hp - 6)
    hero.health.add_temporary_hit_points(4, hero.uuid)
    hero.health.healing_blocked = True

    payload = client.get(
        f"/ai/sessions/{session_id}/observation/snapshot"
    ).json()
    fact = next(
        entity
        for entity in payload["known_entities"]
        if entity["uuid"] == str(hero.uuid)
    )

    assert fact["hp"] == max_hp - 2
    assert fact["normal_hp"] == max_hp - 6
    assert fact["temporary_hp"] == 4
    assert fact["max_hp"] == max_hp
    assert fact["healing_blocked"] is True


def test_new_session_does_not_receive_retroactively_projected_event_history() -> None:
    """A bootstrap snapshot starts the session timeline at the current engine cursor."""
    client, session_id, _hero, _monster, _encounter = create_observation_game()

    snapshot = client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()
    history = client.get(
        f"/ai/sessions/{session_id}/observation/frames",
        params={"since": 0, "limit": 0},
    ).json()

    assert snapshot["source_event_cursor"] == EventQueue.event_cursor()
    assert snapshot["observation_cursor"] == 0
    assert history["frames"] == []
    assert history["total"] == 0
    assert history["next_observation_cursor"] == 0


def test_child_projection_captures_at_its_completion_boundary() -> None:
    """A child completion is captured before later mutable state can replace it."""
    client, session_id, hero, monster, _encounter = create_observation_game()
    client.get(f"/ai/sessions/{session_id}/observation/snapshot")
    parent = Event(
        name="Top-level action",
        event_type=EventType.BASE_ACTION,
        source_entity_uuid=hero.uuid,
        target_entity_uuid=monster.uuid,
        use_register=False,
        combat_log=CombatLogEntry(
            entry_type=CombatLogEntryType.ACTION,
            source_name=hero.name,
            source_uuid=str(hero.uuid),
            target_name=monster.name,
            target_uuid=str(monster.uuid),
            compact="Top-level action",
            verbose="Top-level action",
            detailed="Top-level action",
        ),
    )
    parent = EventQueue.register(parent)
    child = SensoryUpdateEvent(
        name="Causal sensory child",
        source_entity_uuid=hero.uuid,
        target_entity_uuid=hero.uuid,
        observer_uuid=hero.uuid,
        cause_event_uuid=parent.uuid,
        update_reason=SensoryUpdateReason.SPATIAL,
        visible_cells_added=[(5, 5)],
        parent_event=parent.uuid,
        use_register=False,
    )

    child = EventQueue.register(child)
    child = EventQueue.register(child.phase_to(EventPhase.EXECUTION))
    child = EventQueue.register(child.phase_to(EventPhase.EFFECT))
    child = EventQueue.register(child.phase_to(EventPhase.COMPLETION))

    assert len(_projection_cache[session_id].frames) == 1
    assert _projection_cache[session_id].frames[0].event_uuid == str(child.uuid)

    parent = EventQueue.register(parent.phase_to(EventPhase.EXECUTION))
    parent = EventQueue.register(parent.phase_to(EventPhase.EFFECT))
    EventQueue.register(parent.phase_to(EventPhase.COMPLETION))
    after_root = client.get(
        f"/ai/sessions/{session_id}/observation/frames",
        params={"since": 0, "limit": 0},
    ).json()

    assert after_root["frames"][0]["event_uuid"] == str(child.uuid)
    assert [frame["observation_cursor"] for frame in after_root["frames"]] == list(
        range(1, len(after_root["frames"]) + 1)
    )
    assert [frame["source_event_cursor"] for frame in after_root["frames"]] == sorted(
        frame["source_event_cursor"] for frame in after_root["frames"]
    )


def test_child_damage_frames_capture_hp_at_each_completion_boundary() -> None:
    """Each damage completion records the HP fact true at that event boundary."""
    client, session_id, hero, monster, _encounter = create_observation_game()
    set_hp(monster, 17)
    snapshot = client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()
    parent = Event(
        name="Two-hit action",
        event_type=EventType.BASE_ACTION,
        source_entity_uuid=hero.uuid,
        target_entity_uuid=monster.uuid,
        use_register=False,
    )
    parent = EventQueue.register(parent)

    monster.receive_damage(
        1,
        DamageType.FORCE,
        source_entity_uuid=hero.uuid,
        parent_event=parent.uuid,
    )
    monster.receive_damage(
        2,
        DamageType.FORCE,
        source_entity_uuid=hero.uuid,
        parent_event=parent.uuid,
    )
    parent = EventQueue.register(parent.phase_to(EventPhase.EXECUTION))
    parent = EventQueue.register(parent.phase_to(EventPhase.EFFECT))
    EventQueue.register(parent.phase_to(EventPhase.COMPLETION))

    frames = client.get(
        f"/ai/sessions/{session_id}/observation/frames",
        params={"since": snapshot["observation_cursor"], "limit": 0},
    ).json()["frames"]
    damage_hp = [
        patch["data"]["entity_update"]["hp"]
        for frame in frames
        if frame["event_type"] == EventType.DAMAGE_APPLIED.value
        for patch in frame["patches"]
        if patch["entity_uuid"] == str(monster.uuid)
        and "entity_update" in patch["data"]
    ]

    assert damage_hp == [16, 14]


def test_batched_child_damage_frames_keep_each_event_time_hp_fact() -> None:
    """Delivery batching cannot replace intermediate HP with final mutable state."""
    client, session_id, hero, monster, _encounter = create_observation_game()
    set_hp(monster, 17)
    snapshot = client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()

    with EventQueue.batch_on_event_callbacks():
        parent = EventQueue.register(Event(
            name="Batched two-hit action",
            event_type=EventType.BASE_ACTION,
            source_entity_uuid=hero.uuid,
            target_entity_uuid=monster.uuid,
            use_register=False,
        ))
        monster.receive_damage(
            1,
            DamageType.FORCE,
            source_entity_uuid=hero.uuid,
            parent_event=parent.uuid,
        )
        monster.receive_damage(
            2,
            DamageType.FORCE,
            source_entity_uuid=hero.uuid,
            parent_event=parent.uuid,
        )
        parent = EventQueue.register(parent.phase_to(EventPhase.EXECUTION))
        parent = EventQueue.register(parent.phase_to(EventPhase.EFFECT))
        EventQueue.register(parent.phase_to(EventPhase.COMPLETION))

    frames = client.get(
        f"/ai/sessions/{session_id}/observation/frames",
        params={"since": snapshot["observation_cursor"], "limit": 0},
    ).json()["frames"]
    damage_hp = [
        patch["data"]["entity_update"]["hp"]
        for frame in frames
        if frame["event_type"] == EventType.DAMAGE_APPLIED.value
        for patch in frame["patches"]
        if patch["entity_uuid"] == str(monster.uuid)
        and "entity_update" in patch["data"]
    ]

    assert damage_hp == [16, 14]


def test_batched_healing_frames_keep_each_event_time_hp_fact() -> None:
    """Healing envelopes carry event-time HP instead of final batch state."""
    client, session_id, hero, monster, _encounter = create_observation_game()
    set_hp(monster, 5)
    snapshot = client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()

    with EventQueue.batch_on_event_callbacks():
        monster.receive_healing(1, hero.uuid, source_description="First heal")
        monster.receive_healing(2, hero.uuid, source_description="Second heal")

    frames = client.get(
        f"/ai/sessions/{session_id}/observation/frames",
        params={"since": snapshot["observation_cursor"], "limit": 0},
    ).json()["frames"]
    healing_hp = [
        patch["data"]["entity_update"]["hp"]
        for frame in frames
        if frame["event_type"] == EventType.HEAL.value
        for patch in frame["patches"]
        if patch["entity_uuid"] == str(monster.uuid)
        and "entity_update" in patch["data"]
    ]

    assert healing_hp == [6, 8]


def test_non_movement_batch_projection_waits_for_batch_boundary(monkeypatch) -> None:
    """Non-HP condition-style events project once after the causal batch closes."""
    client, session_id, hero, monster, _encounter = create_observation_game()
    client.get(f"/ai/sessions/{session_id}/observation/snapshot")
    published: list[tuple[str, ObservationFrame]] = []

    def capture_publish(published_session_id: str, frame: ObservationFrame) -> None:
        published.append((published_session_id, frame))

    monkeypatch.setattr(
        observation_projector.observation_wakeup_stream,
        "publish",
        capture_publish,
    )
    with EventQueue.batch_on_event_callbacks():
        completion = EventQueue.register(Event(
            name="Batched condition marker",
            event_type=EventType.CONDITION_APPLICATION,
            phase=EventPhase.COMPLETION,
            source_entity_uuid=hero.uuid,
            target_entity_uuid=monster.uuid,
            use_register=False,
        ))
        assert _projection_cache[session_id].frames == []
        assert published == []

    frames = _projection_cache[session_id].frames
    assert len(frames) == 1
    assert frames[0].event_uuid == str(completion.uuid)
    assert [(published_session_id, frame.event_uuid) for published_session_id, frame in published] == [
        (session_id, str(completion.uuid)),
    ]


def test_projection_immediacy_classifier_preserves_movement_sensory_and_hp_boundaries() -> None:
    """Only event-time-sensitive completions should project inside action batches."""
    source_uuid = uuid4()

    condition = Event(
        event_type=EventType.CONDITION_APPLICATION,
        phase=EventPhase.COMPLETION,
        source_entity_uuid=source_uuid,
        target_entity_uuid=source_uuid,
        use_register=False,
    )
    damage = Event(
        event_type=EventType.DAMAGE_APPLIED,
        source_entity_uuid=source_uuid,
        target_entity_uuid=source_uuid,
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    movement = MovementEvent(
        source_entity_uuid=source_uuid,
        target_entity_uuid=source_uuid,
        start_position=(0, 0),
        end_position=(1, 0),
        path=[(0, 0), (1, 0)],
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    sensory = SensoryUpdateEvent(
        source_entity_uuid=source_uuid,
        target_entity_uuid=source_uuid,
        observer_uuid=source_uuid,
        cause_event_uuid=source_uuid,
        update_reason=SensoryUpdateReason.SPATIAL,
        visible_cells_added=[(1, 1)],
        phase=EventPhase.COMPLETION,
        use_register=False,
    )

    assert _completion_sequence_needs_immediate_projection([condition]) is False
    assert _completion_sequence_needs_immediate_projection([damage]) is False
    assert _completion_sequence_needs_immediate_projection([movement]) is True
    assert _completion_sequence_needs_immediate_projection([sensory]) is True


def test_late_child_after_completed_parent_wakes_subjective_stream() -> None:
    """A late child remains an independent immutable observation boundary."""
    client, session_id, hero, monster, _encounter = create_observation_game()
    client.get(f"/ai/sessions/{session_id}/observation/snapshot")
    parent = Event(
        name="Already completed parent",
        event_type=EventType.BASE_ACTION,
        source_entity_uuid=hero.uuid,
        target_entity_uuid=monster.uuid,
        use_register=False,
    )
    complete_event(parent)
    subscription = observation_wakeup_stream.subscribe(session_id)
    try:
        child = Event(
            name="Late healing child",
            event_type=EventType.HEAL,
            source_entity_uuid=hero.uuid,
            target_entity_uuid=monster.uuid,
            parent_event=parent.uuid,
            use_register=False,
        )
        completed_child = complete_event(child)

        async def receive_late_child():
            for _ in range(8):
                candidate = await asyncio.wait_for(subscription.get(), timeout=1.0)
                if candidate["data"].event_type == EventType.HEAL.value:
                    return candidate
            raise AssertionError("Late child frame was not published")

        envelope = asyncio.run(receive_late_child())
    finally:
        observation_wakeup_stream.unsubscribe(session_id, subscription)

    frame = envelope["data"]
    assert envelope["event"] == "observation_frame"
    assert frame.event_uuid == str(completed_child.uuid)
    assert frame.event_type == EventType.HEAL.value


def test_condition_application_frame_matches_post_application_snapshot() -> None:
    """Condition completion carries the condition indexed immediately afterward."""
    client, session_id, hero, monster, _encounter = create_observation_game()
    snapshot = client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()
    replayed = materialize_snapshot(snapshot)
    hold = HoldPersonEffect(
        source_entity_uuid=hero.uuid,
        target_entity_uuid=monster.uuid,
        caster_uuid=hero.uuid,
        spell_dc=12,
    )

    application = monster.add_condition(hold)
    frames = client.get(
        f"/ai/sessions/{session_id}/observation/frames",
        params={"since": snapshot["observation_cursor"], "limit": 0},
    ).json()["frames"]
    for frame in frames:
        replayed = apply_observation_frame(replayed, frame)
    fresh = materialize_snapshot(
        client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()
    )

    expected = {"Paralyzed", "Hold Person"}
    expected_semantic_keys = {
        f"{type(condition).__module__}.{type(condition).__qualname__}"
        for condition in monster.active_conditions.values()
        if condition.name in expected
    }
    assert application is not None
    assert application.phase == EventPhase.COMPLETION
    assert expected <= set(monster.active_conditions)
    assert "Incapacitated" not in monster.active_conditions
    assert expected <= set(replayed.known_entities[str(monster.uuid)].conditions)
    assert "Incapacitated" not in replayed.known_entities[str(monster.uuid)].conditions
    assert expected_semantic_keys <= set(
        replayed.known_entities[str(monster.uuid)].condition_semantic_keys or []
    )
    assert replayed.known_entities[str(monster.uuid)].conditions == fresh.known_entities[
        str(monster.uuid)
    ].conditions
    assert replayed.known_entities[str(monster.uuid)].condition_semantic_keys == fresh.known_entities[
        str(monster.uuid)
    ].condition_semantic_keys
    assert replayed.known_entities[str(hero.uuid)].conditions == fresh.known_entities[
        str(hero.uuid)
    ].conditions
    assert "Hold Person" not in replayed.known_entities[str(hero.uuid)].conditions


def test_standalone_spotted_log_wakes_and_replays_once() -> None:
    """Standalone perceptual logs enter the live subjective event stream once."""
    client, session_id, hero, monster, encounter = create_observation_game()
    snapshot = client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()
    replayed = materialize_snapshot(snapshot)
    event_cursor = EventQueue.event_cursor()
    combat_log_cursor = len(encounter.combat_log)
    subscription = observation_wakeup_stream.subscribe(session_id)
    spotted = CombatLogEntry(
        entry_type=CombatLogEntryType.ENTITY_SPOTTED,
        source_name=hero.name,
        source_uuid=str(hero.uuid),
        target_name=monster.name,
        target_uuid=str(monster.uuid),
        compact=f"{hero.name} spots {monster.name}",
        verbose=f"{hero.name} spots {monster.name}",
        detailed=f"{hero.name} spots {monster.name}",
        perceiver_uuids={str(hero.uuid)},
        identified_entity_observer_uuids={
            str(monster.uuid): {str(hero.uuid)},
        },
    )

    try:
        EventQueue.push_combat_log(spotted, hero.uuid)
        envelope = asyncio.run(
            asyncio.wait_for(subscription.get(), timeout=1.0)
        )
    finally:
        observation_wakeup_stream.unsubscribe(session_id, subscription)

    frame = envelope["data"]
    frames = client.get(
        f"/ai/sessions/{session_id}/observation/frames",
        params={"since": snapshot["observation_cursor"], "limit": 0},
    ).json()["frames"]
    for projected in frames:
        replayed = apply_observation_frame(replayed, projected)
    fresh = materialize_snapshot(
        client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()
    )

    assert envelope["event"] == "observation_frame"
    assert EventQueue.event_cursor() == event_cursor
    assert len(encounter.combat_log) == combat_log_cursor + 1
    assert frame.frame_type.value == "combat_log"
    assert frame.source_kind.value == "combat_log"
    assert frame.source_event_cursor == event_cursor
    assert frame.source_combat_log_cursor == combat_log_cursor + 1
    assert frame.event_type is None
    assert frame.event_uuid is None
    assert frame.lineage_uuid is None
    assert frame.phase is None
    assert frame.combat_log["target_uuid"] == str(monster.uuid)
    assert len(frames) == 1
    assert len(replayed.combat_logs) == len(snapshot["combat_logs"]) + 1
    assert replayed.combat_logs == fresh.combat_logs


def test_registered_completion_log_is_not_duplicated_by_log_listener() -> None:
    """Registered event logs remain owned by the EventQueue projection path."""
    client, session_id, hero, monster, _encounter = create_observation_game()
    snapshot = client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()
    action_log = CombatLogEntry(
        entry_type=CombatLogEntryType.ACTION,
        source_name=hero.name,
        source_uuid=str(hero.uuid),
        target_name=monster.name,
        target_uuid=str(monster.uuid),
        compact=f"{hero.name} tests one action",
        verbose=f"{hero.name} tests one action",
        detailed=f"{hero.name} tests one action",
        perceiver_uuids={str(hero.uuid)},
    )
    event = Event(
        name="Registered logged action",
        event_type=EventType.BASE_ACTION,
        source_entity_uuid=hero.uuid,
        target_entity_uuid=monster.uuid,
        combat_log=action_log,
    )

    event.phase_to(EventPhase.EXECUTION).phase_to(EventPhase.EFFECT).phase_to(
        EventPhase.COMPLETION
    )
    frames = client.get(
        f"/ai/sessions/{session_id}/observation/frames",
        params={"since": snapshot["observation_cursor"], "limit": 0},
    ).json()["frames"]
    logged_frames = [frame for frame in frames if frame["combat_log"] is not None]

    assert len(logged_frames) == 1
    assert logged_frames[0]["source_kind"] == "engine_event"
    assert logged_frames[0]["combat_log"]["compact"] == action_log.compact


def test_standalone_hazard_log_reaches_only_its_perceiver_session() -> None:
    """Perceiver metadata filters standalone hazard logs between sessions."""
    client, hero_session_id, hero, monster, _encounter = create_observation_game()
    manager = sim.get_session_manager()
    game = manager.get_active_game()
    assert game is not None
    monster_session = manager.create_session(PlayerType.AI, "Hazard-Unaware Agent")
    game.add_player(monster_session)
    game.assign_entity(monster.uuid, monster_session.session_id)
    monster_session_id = str(monster_session.session_id)
    hero_snapshot = client.get(
        f"/ai/sessions/{hero_session_id}/observation/snapshot"
    ).json()
    monster_snapshot = client.get(
        f"/ai/sessions/{monster_session_id}/observation/snapshot"
    ).json()
    hazard = CombatLogEntry(
        entry_type=CombatLogEntryType.HAZARD_DETECTED,
        source_name=hero.name,
        source_uuid=str(hero.uuid),
        compact=f"{hero.name} detects a hidden hazard",
        verbose=f"{hero.name} detects a hidden hazard",
        detailed=f"{hero.name} detects a hidden hazard",
        perceiver_uuids={str(hero.uuid)},
    )

    EventQueue.push_combat_log(hazard, hero.uuid)
    hero_frames = client.get(
        f"/ai/sessions/{hero_session_id}/observation/frames",
        params={"since": hero_snapshot["observation_cursor"], "limit": 0},
    ).json()["frames"]
    monster_frames = client.get(
        f"/ai/sessions/{monster_session_id}/observation/frames",
        params={"since": monster_snapshot["observation_cursor"], "limit": 0},
    ).json()["frames"]

    assert len(hero_frames) == 1
    assert hero_frames[0]["combat_log"]["entry_type"] == "hazard_detected"
    assert monster_frames == []


def test_sensory_completion_projects_only_its_observer_session(monkeypatch) -> None:
    """Observer-specific sensory events bypass unrelated session projection."""
    client, hero_session_id, hero, monster, _encounter = create_observation_game()
    manager = sim.get_session_manager()
    game = manager.get_active_game()
    assert game is not None
    monster_session = manager.create_session(PlayerType.AI, "Other Observer")
    game.add_player(monster_session)
    game.assign_entity(monster.uuid, monster_session.session_id)
    monster_session_id = str(monster_session.session_id)
    hero_snapshot = client.get(
        f"/ai/sessions/{hero_session_id}/observation/snapshot"
    ).json()
    monster_snapshot = client.get(
        f"/ai/sessions/{monster_session_id}/observation/snapshot"
    ).json()
    original_update = observation_projector._update_projection_cache
    projected_session_ids: list[str] = []

    def record_projection(session, game, encounter, **kwargs):
        projected_session_ids.append(str(session.session_id))
        return original_update(session, game, encounter, **kwargs)

    monkeypatch.setattr(
        observation_projector,
        "_update_projection_cache",
        record_projection,
    )
    sensory = SensoryUpdateEvent(
        source_entity_uuid=hero.uuid,
        target_entity_uuid=hero.uuid,
        observer_uuid=hero.uuid,
        cause_event_uuid=uuid4(),
        update_reason=SensoryUpdateReason.SPATIAL,
        visible_cells_added=[(3, 3)],
        seen_cells_added=[(3, 3)],
        phase=EventPhase.DECLARATION,
    )

    sensory.phase_to(EventPhase.EXECUTION).phase_to(EventPhase.EFFECT).phase_to(
        EventPhase.COMPLETION
    )
    completion_projected_session_ids = list(projected_session_ids)
    hero_frames = client.get(
        f"/ai/sessions/{hero_session_id}/observation/frames",
        params={"since": hero_snapshot["observation_cursor"], "limit": 0},
    ).json()["frames"]
    monster_frames = client.get(
        f"/ai/sessions/{monster_session_id}/observation/frames",
        params={"since": monster_snapshot["observation_cursor"], "limit": 0},
    ).json()["frames"]

    assert completion_projected_session_ids == [hero_session_id]
    assert len(hero_frames) == 1
    assert hero_frames[0]["source_kind"] == "sensory_event"
    assert monster_frames == []


def test_position_only_sensory_update_projects_and_replays_observer_position() -> None:
    """Observer movement remains stream-visible even when no FOV set changes."""
    client, session_id, hero, _monster, _encounter = create_observation_game()
    snapshot = client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()
    destination = (hero.position[0] + 1, hero.position[1])
    complete_event(SensoryUpdateEvent(
        source_entity_uuid=hero.uuid,
        target_entity_uuid=hero.uuid,
        observer_uuid=hero.uuid,
        observer_position=destination,
        observer_position_changed=True,
        cause_event_uuid=uuid4(),
        update_reason=SensoryUpdateReason.SPATIAL,
        phase=EventPhase.DECLARATION,
    ))

    frames = client.get(
        f"/ai/sessions/{session_id}/observation/frames",
        params={"since": snapshot["observation_cursor"], "limit": 0},
    ).json()["frames"]
    state = materialize_snapshot(snapshot)
    for frame in frames:
        state = apply_observation_frame(state, frame)

    assert len(frames) == 1
    observer_patch = next(
        patch
        for patch in frames[0]["patches"]
        if patch["patch_type"] == "observer"
    )
    assert observer_patch["data"]["position"] == list(destination)
    assert state.observers[str(hero.uuid)].position == destination


def test_sensory_moved_entity_uses_partial_position_update() -> None:
    """Movement deltas should not rebuild full HP, AC, and affinity facts."""
    client, session_id, hero, monster, _encounter = create_observation_game()
    snapshot = client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()
    sensory = SensoryUpdateEvent(
        source_entity_uuid=hero.uuid,
        target_entity_uuid=hero.uuid,
        observer_uuid=hero.uuid,
        cause_event_uuid=uuid4(),
        update_reason=SensoryUpdateReason.SPATIAL,
        visible_entities_moved={monster.uuid: ((7, 5), (8, 5))},
        phase=EventPhase.DECLARATION,
    )

    sensory.phase_to(EventPhase.EXECUTION).phase_to(EventPhase.EFFECT).phase_to(
        EventPhase.COMPLETION
    )
    frames = client.get(
        f"/ai/sessions/{session_id}/observation/frames",
        params={"since": snapshot["observation_cursor"], "limit": 0},
    ).json()["frames"]
    moved_updates = [
        patch["data"]["entity_update"]
        for frame in frames
        if frame["source_kind"] == "sensory_event"
        for patch in frame["patches"]
        if patch["entity_uuid"] == str(monster.uuid)
        and "entity_update" in patch["data"]
    ]
    state = materialize_snapshot(snapshot)
    for frame in frames:
        state = apply_observation_frame(state, frame)
    snapshot_monster = next(
        entity for entity in snapshot["known_entities"]
        if entity["uuid"] == str(monster.uuid)
    )

    assert moved_updates == [
        {
            "uuid": str(monster.uuid),
            "knowledge_state": "visible",
            "position": [8, 5],
        }
    ]
    assert all("entity" not in patch["data"] for frame in frames for patch in frame["patches"])
    assert state.known_entities[str(monster.uuid)].position == (8, 5)
    assert state.known_entities[str(monster.uuid)].hp == snapshot_monster["hp"]


def test_movement_completion_uses_partial_position_update() -> None:
    """Movement completion frames should avoid full entity fact rebuilds."""
    client, session_id, hero, _monster, _encounter = create_observation_game()
    snapshot = client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()
    movement = MovementEvent(
        source_entity_uuid=hero.uuid,
        source_entity_name=hero.name,
        start_position=hero.position,
        end_position=(hero.position[0] + 1, hero.position[1]),
        path=[hero.position, (hero.position[0] + 1, hero.position[1])],
        phase=EventPhase.COMPLETION,
        use_register=False,
    )

    EventQueue.register(movement)
    frames = client.get(
        f"/ai/sessions/{session_id}/observation/frames",
        params={"since": snapshot["observation_cursor"], "limit": 0},
    ).json()["frames"]
    movement_updates = [
        patch["data"]["entity_update"]
        for frame in frames
        if frame["event_type"] == EventType.MOVEMENT.value
        for patch in frame["patches"]
        if patch["entity_uuid"] == str(hero.uuid)
        and "entity_update" in patch["data"]
    ]

    assert movement_updates == [
        {
            "uuid": str(hero.uuid),
            "knowledge_state": "visible",
            "position": [hero.position[0] + 1, hero.position[1]],
        }
    ]
    assert all(
        "entity" not in patch["data"]
        for frame in frames
        if frame["event_type"] == EventType.MOVEMENT.value
        for patch in frame["patches"]
    )


def test_hidden_enemy_is_not_leaked_in_strict_snapshot() -> None:
    """Unperceived invisible enemies are absent from known entity facts."""
    client, session_id, _hero, monster, _encounter = create_observation_game(hidden_monster=True)

    response = client.get(f"/ai/sessions/{session_id}/observation/snapshot")
    payload = response.json()
    known_names = {entity["name"] for entity in payload["known_entities"]}
    initiative_names = [row["name"] for row in payload["encounter"]["initiative_order"]]
    initiative_uuids = {
        row["uuid"]
        for row in payload["encounter"]["initiative_order"]
        if row["uuid"] is not None
    }

    assert response.status_code == 200
    assert "Observation Skeleton" not in known_names
    assert str(monster.uuid) not in {
        entity["uuid"] for entity in payload["known_entities"]
    }
    assert "Unknown Combatant" not in initiative_names
    assert str(monster.uuid) not in initiative_uuids


def test_current_senses_do_not_retroactively_authorize_legacy_combat_logs() -> None:
    """Current visibility cannot supply missing event-time perception evidence."""
    client, session_id, hero, monster, encounter = create_observation_game()
    assert monster.uuid in hero.senses.entities
    encounter.combat_log.append(CombatLogEntry(
        entry_type=CombatLogEntryType.ACTION,
        source_name=monster.name,
        source_uuid=str(monster.uuid),
        compact="RETROACTIVE-LEGACY-LOG",
        verbose="RETROACTIVE-LEGACY-LOG",
        detailed="RETROACTIVE-LEGACY-LOG",
    ))

    snapshot = client.get(
        f"/ai/sessions/{session_id}/observation/snapshot"
    ).json()

    assert "RETROACTIVE-LEGACY-LOG" not in json.dumps(snapshot["combat_logs"])


def test_multi_entity_session_uses_one_stream_with_observer_tags() -> None:
    """A multi-entity controller receives one stream tagged by observer."""
    client, session_id, hero, monster, _encounter = create_observation_game(second_hero=True)

    response = client.get(f"/ai/sessions/{session_id}/observation/snapshot")
    payload = response.json()
    observer_ids = {observer["observer_uuid"] for observer in payload["observers"]}
    skeleton_fact = next(
        entity for entity in payload["known_entities"]
        if entity["uuid"] == str(monster.uuid)
    )

    assert response.status_code == 200
    assert len(payload["session"]["controlled_entity_uuids"]) == 2
    assert str(hero.uuid) in observer_ids
    assert len(observer_ids) == 2
    assert set(skeleton_fact["observer_uuids"]) <= observer_ids
    assert skeleton_fact["observer_uuids"]


def test_sensory_updates_project_only_for_the_matching_session() -> None:
    """Observer-specific sensory events are filtered by controlled entity."""
    client, session_id, hero, monster, _encounter = create_observation_game()
    before = client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()

    visible_event = SensoryUpdateEvent(
        source_entity_uuid=hero.uuid,
        target_entity_uuid=hero.uuid,
        observer_uuid=hero.uuid,
        cause_event_uuid=uuid4(),
        update_reason=SensoryUpdateReason.SPATIAL,
        visible_cells_added=[(3, 3)],
        seen_cells_added=[(3, 3)],
        visible_entities_added={monster.uuid: monster.position},
        phase=EventPhase.DECLARATION,
    )
    complete_event(visible_event)

    unrelated_event = SensoryUpdateEvent(
        source_entity_uuid=monster.uuid,
        target_entity_uuid=monster.uuid,
        observer_uuid=monster.uuid,
        cause_event_uuid=uuid4(),
        update_reason=SensoryUpdateReason.SPATIAL,
        visible_cells_added=[(4, 4)],
        seen_cells_added=[(4, 4)],
        phase=EventPhase.DECLARATION,
    )
    complete_event(unrelated_event)

    frames = client.get(
        f"/ai/sessions/{session_id}/observation/frames",
        params={"since": before["observation_cursor"], "limit": 0},
    ).json()["frames"]
    observer_frames = [
        frame for frame in frames
        if any(patch["patch_type"] == "observer" for patch in frame["patches"])
    ]

    assert observer_frames
    assert all(
        patch.get("observer_uuid") == str(hero.uuid)
        for frame in observer_frames
        for patch in frame["patches"]
        if patch["patch_type"] == "observer"
    )
    assert all(
        patch.get("observer_uuid") != str(monster.uuid)
        for frame in frames
        for patch in frame["patches"]
    )


def test_empty_sensory_updates_do_not_create_subjective_frames() -> None:
    """Path-cache-only sensory invalidations do not carry new agent facts."""
    client, session_id, hero, _monster, _encounter = create_observation_game()
    before = client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()

    empty_event = SensoryUpdateEvent(
        source_entity_uuid=hero.uuid,
        target_entity_uuid=hero.uuid,
        observer_uuid=hero.uuid,
        cause_event_uuid=uuid4(),
        update_reason=SensoryUpdateReason.SPATIAL,
        paths_dirty=True,
        phase=EventPhase.DECLARATION,
    )
    complete_event(empty_event)

    frames = client.get(
        f"/ai/sessions/{session_id}/observation/frames",
        params={"since": before["observation_cursor"], "limit": 0},
    ).json()["frames"]

    assert frames == []


def test_dense_sensory_tile_updates_are_batched_and_replayable() -> None:
    """Dense reveal events should carry all tile facts without per-cell patches."""
    client, session_id, hero, _monster, _encounter = create_observation_game()
    revealed_positions = [(9, 8), (10, 8), (11, 8), (12, 8)]
    for position in revealed_positions:
        hero.senses.visible.pop(position, None)
        hero.senses.seen.discard(position)
    before = client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()
    state = materialize_snapshot(before)

    for position in revealed_positions:
        hero.senses.visible[position] = True
        hero.senses.seen.add(position)
    sensory_event = SensoryUpdateEvent(
        source_entity_uuid=hero.uuid,
        target_entity_uuid=hero.uuid,
        observer_uuid=hero.uuid,
        cause_event_uuid=uuid4(),
        update_reason=SensoryUpdateReason.SPATIAL,
        visible_cells_added=revealed_positions,
        seen_cells_added=revealed_positions,
        phase=EventPhase.DECLARATION,
    )
    complete_event(sensory_event)

    frames = client.get(
        f"/ai/sessions/{session_id}/observation/frames",
        params={"since": before["observation_cursor"], "limit": 0},
    ).json()["frames"]
    tile_patches = [
        patch
        for frame in frames
        for patch in frame["patches"]
        if patch["patch_type"] == "tile"
    ]
    for frame in frames:
        state = apply_observation_frame(state, frame)
    fresh = materialize_snapshot(
        client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()
    )

    assert len(tile_patches) == 1
    assert len(tile_patches[0]["data"]["tiles"]) == len(revealed_positions)
    assert "tile" not in tile_patches[0]["data"]
    for position in revealed_positions:
        key = f"{position[0]},{position[1]}"
        assert state.known_tiles[key] == fresh.known_tiles[key]
        assert state.known_tiles[key].knowledge_state.value == "visible"


def test_removed_visible_tile_delta_reuses_materialized_boundary_memory() -> None:
    """Sparse seen-tile deltas replay with the same boundary facts as snapshots."""
    client, session_id, hero, monster, _encounter = create_observation_game()
    removed_position = next(
        position
        for position, visible in hero.senses.visible.items()
        if visible and position not in {hero.position, monster.position}
    )
    before = client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()
    state = materialize_snapshot(before)
    tile_key = f"{removed_position[0]},{removed_position[1]}"
    before_tile = state.known_tiles[tile_key]
    assert before_tile.knowledge_state.value == "visible"
    assert before_tile.adjacent_domain

    hero.senses.visible.pop(removed_position, None)
    hero.senses.seen.add(removed_position)
    sensory_event = SensoryUpdateEvent(
        source_entity_uuid=hero.uuid,
        target_entity_uuid=hero.uuid,
        observer_uuid=hero.uuid,
        cause_event_uuid=uuid4(),
        update_reason=SensoryUpdateReason.SPATIAL,
        visible_cells_removed=[removed_position],
        phase=EventPhase.DECLARATION,
    )
    complete_event(sensory_event)

    frames = client.get(
        f"/ai/sessions/{session_id}/observation/frames",
        params={"since": before["observation_cursor"], "limit": 0},
    ).json()["frames"]
    tile_payloads = [
        patch["data"].get("tile") or tile
        for frame in frames
        for patch in frame["patches"]
        if patch["patch_type"] == "tile"
        for tile in patch["data"].get("tiles", [patch["data"].get("tile")])
        if tile is not None
    ]
    removed_payload = next(tile for tile in tile_payloads if tile["key"] == tile_key)
    for frame in frames:
        state = apply_observation_frame(state, frame)
    fresh = materialize_snapshot(
        client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()
    )

    assert removed_payload["knowledge_state"] == "seen"
    assert removed_payload["adjacent_domain"] == {}
    assert state.known_tiles[tile_key] == fresh.known_tiles[tile_key]
    assert state.known_tiles[tile_key].knowledge_state.value == "seen"
    assert state.known_tiles[tile_key].adjacent_domain == before_tile.adjacent_domain


def test_lit_to_lit_light_changes_do_not_refilter_visible_occupants(monkeypatch) -> None:
    """Light level changes that stay visible should not churn entity facts."""
    _client, _session_id, hero, monster, _encounter = create_observation_game()
    assert hero.senses.visible.get(monster.position) is True
    assert hero.senses.entities[monster.uuid] == monster.position
    callback = SpatialSensesCallback(hero.senses, hero.uuid)
    refresh_calls: list[set[tuple[int, int]]] = []

    def track_refresh(positions: set[tuple[int, int]]) -> None:
        refresh_calls.append(set(positions))

    monkeypatch.setattr(callback, "_update_visibility_for_light_positions", track_refresh)
    tile = get_map().get_tile(*monster.position)
    assert tile is not None
    hint = SensesUpdateHint(light_changed_positions={monster.position})
    event = SpatialChangeEvent.light_changed(
        monster.position,
        tile.uuid,
        senses_hint=hint,
    )

    callback._apply_hint(hint, event)

    assert refresh_calls == []
    assert hero.senses.entities[monster.uuid] == monster.position


def test_snapshot_plus_frames_replays_to_fresh_subjective_state() -> None:
    """Snapshot plus frames rebuilds the same known HP as a fresh snapshot."""
    client, session_id, hero, monster, _encounter = create_observation_game()
    before_snapshot = client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()
    state = materialize_snapshot(before_snapshot)
    actions = client.get(
        f"/entity/{hero.uuid}/available-actions",
        params={"session_id": session_id},
    ).json()
    target_index = attack_target_index(actions, monster.uuid)
    modifier_uuid = add_auto_hit(hero)
    try:
        with fixed_dice_faces(12, 4):
            execute = client.post(
                "/action/execute",
                json={
                    "session_id": session_id,
                    "entity_uuid": str(hero.uuid),
                    "template_name": "Attack_MELEE_MAIN",
                    "target_index": target_index,
                },
            )
    finally:
        hero.equipment.melee_attack_bonus.self_static.remove_modifier(modifier_uuid)

    assert execute.status_code == 200

    frames_payload = client.get(
        f"/ai/sessions/{session_id}/observation/frames",
        params={"since": before_snapshot["observation_cursor"], "limit": 0},
    ).json()
    roll_frames = [
        frame
        for frame in frames_payload["frames"]
        if frame.get("event_type") in {"attack_d20_roll", "save_d20_roll", "d20_roll_result"}
    ]
    damage_frames = [
        frame
        for frame in frames_payload["frames"]
        if frame.get("event_type") == "damage_applied"
    ]
    for frame in frames_payload["frames"]:
        state = apply_observation_frame(state, frame)
        state = apply_observation_frame(state, frame)

    fresh_snapshot = client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()
    fresh_state = materialize_snapshot(fresh_snapshot)

    assert frames_payload["frames"]
    assert all(
        patch["patch_type"] != "entity"
        for frame in roll_frames
        for patch in frame["patches"]
    )
    assert damage_frames
    assert any(
        "entity_update" in patch["data"]
        for frame in damage_frames
        for patch in frame["patches"]
        if patch["patch_type"] == "entity"
    )
    assert all(
        "entity" not in patch["data"]
        for frame in damage_frames
        for patch in frame["patches"]
        if patch["patch_type"] == "entity"
    )
    assert state.known_entities[str(monster.uuid)].hp == fresh_state.known_entities[str(monster.uuid)].hp
    assert state.observation_cursor == frames_payload["next_observation_cursor"]
    assert state.combat_logs
    assert fresh_state.combat_logs
    assert state.combat_logs == fresh_state.combat_logs


def test_obsolete_ai_polling_routes_are_not_exposed() -> None:
    """AI controllers use decision epochs and session-scoped runtime commands."""
    client, session_id, hero, _monster, _encounter = create_observation_game()

    actions_response = client.get(
        f"/ai/sessions/{session_id}/entities/{hero.uuid}/available-actions"
    )
    ping_response = client.post("/agent/ping")

    assert actions_response.status_code == 404
    assert ping_response.status_code == 404


def test_roll_result_events_do_not_force_redundant_entity_fact_patches() -> None:
    """Roll result bookkeeping should not refresh full entity facts."""
    assert _event_should_patch_referenced_entities(EventType.ATTACK_D20_ROLL_RESULT) is False
    assert _event_should_patch_referenced_entities(EventType.SAVE_D20_ROLL_RESULT) is False
    assert _event_should_patch_referenced_entities(EventType.D20_ROLL_RESULT) is False
    assert _event_should_patch_referenced_entities(EventType.TAKE_DAMAGE) is False
    assert _event_should_patch_entity_hit_points(EventType.TAKE_DAMAGE) is False
    assert _event_should_patch_entity_hit_points(EventType.DAMAGE_APPLIED) is True
    assert _event_should_patch_entity_hit_points(EventType.HEAL) is True
    assert _event_should_patch_referenced_entities(EventType.CONDITION_APPLICATION) is True
    assert _event_should_patch_referenced_entities(EventType.MOVEMENT) is True


def test_fresh_snapshot_preserves_remembered_entity_from_projected_history() -> None:
    """Snapshot resync keeps last-known facts for an entity that left perception."""
    client, session_id, hero, monster, _encounter = create_observation_game()
    before_snapshot = client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()
    state = materialize_snapshot(before_snapshot)

    assert state.known_entities[str(monster.uuid)].knowledge_state.value == "visible"
    assert state.known_entities[str(monster.uuid)].position == monster.position

    hero.senses.entities.pop(monster.uuid, None)
    sensory_event = SensoryUpdateEvent(
        source_entity_uuid=hero.uuid,
        target_entity_uuid=hero.uuid,
        observer_uuid=hero.uuid,
        cause_event_uuid=uuid4(),
        update_reason=SensoryUpdateReason.PERCEIVABILITY,
        visible_entities_removed={monster.uuid: monster.position},
        phase=EventPhase.DECLARATION,
    )
    complete_event(sensory_event)

    frames_payload = client.get(
        f"/ai/sessions/{session_id}/observation/frames",
        params={"since": before_snapshot["observation_cursor"], "limit": 0},
    ).json()
    for frame in frames_payload["frames"]:
        state = apply_observation_frame(state, frame)

    fresh_snapshot = client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()
    fresh_state = materialize_snapshot(fresh_snapshot)
    replayed = state.known_entities[str(monster.uuid)]
    remembered = fresh_state.known_entities[str(monster.uuid)]
    replayed_contacts = derive_agent_facts(state).facts.contacts
    fresh_contacts = derive_agent_facts(fresh_state).facts.contacts

    assert replayed.knowledge_state.value == "remembered"
    assert replayed.faction == "monsters"
    assert replayed.hp is None
    assert remembered.knowledge_state.value == "remembered"
    assert remembered.position == monster.position
    assert remembered.faction == "monsters"
    assert remembered.hp is None
    assert replayed_contacts.remembered_hostile_uuids == (str(monster.uuid),)
    assert fresh_contacts.remembered_hostile_uuids == (str(monster.uuid),)
    assert replayed_contacts.remembered_unknown_relationship_uuids == tuple()
    assert fresh_contacts.remembered_unknown_relationship_uuids == tuple()


def test_visible_lever_charge_and_linked_tile_removals_replay_from_events() -> None:
    """Item and tile mutation events keep the local subjective world coherent."""
    client, session_id, hero, _monster, _encounter = create_observation_game()
    grid = get_map()
    spike_tiles, spike_handler = create_spike_zone({(3, 2), (4, 2)})
    for tile in spike_tiles:
        grid.set_tile(*tile.position, tile=tile, fire_event=False)
    lever_action = PullLeverAction(
        source_entity_uuid=uuid4(),
        trap_handler_uuid=spike_handler.uuid,
        trap_tile_uuids=[tile.uuid for tile in spike_tiles],
        template=True,
    )
    lever = TrapLever(
        source_entity_uuid=uuid4(),
        use_action_templates=[lever_action],
        charges=1,
    )
    grid.place_object(lever.uuid, (1, 2))
    Entity.update_all_entities_senses(max_distance=20)
    before = client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()
    state = materialize_snapshot(before)

    event = execute_use_action(hero, lever.uuid, "Pull Lever")
    frames = client.get(
        f"/ai/sessions/{session_id}/observation/frames",
        params={"since": before["observation_cursor"], "limit": 0},
    ).json()["frames"]
    for frame in frames:
        state = apply_observation_frame(state, frame)
    fresh = materialize_snapshot(
        client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()
    )

    assert event is not None
    assert lever.charges == 0
    assert state.known_objects[str(lever.uuid)].state["charges"] == 0
    assert fresh.known_objects[str(lever.uuid)].state["charges"] == 0
    for tile in spike_tiles:
        key = f"{tile.position[0]},{tile.position[1]}"
        assert state.known_tiles[key].is_hazardous is False
        assert state.known_tiles[key].conditions == []
        assert state.known_tiles[key] == fresh.known_tiles[key]


def test_visible_enemy_item_use_does_not_invent_inventory_item_position() -> None:
    """Perceived item use must not turn an inventory item into a floor object."""
    client, session_id, hero, monster, _encounter = create_observation_game()
    potion = materialize_item(
        HEALING_POTION_RECIPE,
        monster.uuid,
        origin=ItemRuntimeOrigin.STARTER,
    )
    assert monster.inventory.add_item(potion)
    assert hero.senses.visible.get((0, 0)) is True

    before = client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()
    assert str(potion.uuid) not in {row["uuid"] for row in before["known_objects"]}

    complete_event(ItemChargeConsumptionEvent(
        source_entity_uuid=monster.uuid,
        target_entity_uuid=monster.uuid,
        item_uuid=potion.uuid,
        charges_before=1,
        charges_after=0,
        stack_count_before=1,
        stack_count_after=1,
    ))
    frames = client.get(
        f"/ai/sessions/{session_id}/observation/frames",
        params={"since": before["observation_cursor"], "limit": 0},
    ).json()["frames"]
    object_patches = [
        patch
        for frame in frames
        for patch in frame["patches"]
        if patch["patch_type"] == "object"
    ]
    fresh = client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()

    assert all(patch.get("object_uuid") != str(potion.uuid) for patch in object_patches)
    assert str(potion.uuid) not in {row["uuid"] for row in fresh["known_objects"]}


def test_visible_condition_protections_replay_and_clear_when_contact_is_remembered() -> None:
    """Live typed protections are visible facts, never remembered-contact facts."""
    client, session_id, hero, monster, _encounter = create_observation_game()
    before = client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()
    state = materialize_snapshot(before)

    monster.add_condition(ShieldBuff(
        source_entity_uuid=monster.uuid,
        target_entity_uuid=monster.uuid,
    ))
    application_frames = client.get(
        f"/ai/sessions/{session_id}/observation/frames",
        params={"since": before["observation_cursor"], "limit": 0},
    ).json()["frames"]
    for frame in application_frames:
        state = apply_observation_frame(state, frame)

    visible = state.known_entities[str(monster.uuid)]
    assert visible.effect_protections is not None
    assert len(visible.effect_protections) == 1
    assert visible.effect_protections[0].blocked_effect_ids == [
        "dnd.spells.evocation.MagicMissile.damage"
    ]

    hero.senses.entities.pop(monster.uuid, None)
    sensory_event = SensoryUpdateEvent(
        source_entity_uuid=hero.uuid,
        target_entity_uuid=hero.uuid,
        observer_uuid=hero.uuid,
        cause_event_uuid=uuid4(),
        update_reason=SensoryUpdateReason.PERCEIVABILITY,
        visible_entities_removed={monster.uuid: monster.position},
        phase=EventPhase.DECLARATION,
    )
    complete_event(sensory_event)
    visibility_frames = client.get(
        f"/ai/sessions/{session_id}/observation/frames",
        params={"since": state.observation_cursor, "limit": 0},
    ).json()["frames"]
    for frame in visibility_frames:
        state = apply_observation_frame(state, frame)
    fresh = materialize_snapshot(
        client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()
    )

    replayed = state.known_entities[str(monster.uuid)]
    resynced = fresh.known_entities[str(monster.uuid)]
    assert replayed.knowledge_state.value == "remembered"
    assert replayed.effect_protections is None
    assert resynced.knowledge_state.value == "remembered"
    assert resynced.effect_protections is None


def test_damage_ending_control_semantics_replay_and_redact_with_visibility() -> None:
    """Condition lifecycle truth follows the same subjective replay boundary."""
    client, session_id, hero, monster, encounter = create_observation_game()
    before = client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()
    state = materialize_snapshot(before)

    condition = HypnoticPatternEffect(
        source_entity_uuid=hero.uuid,
        target_entity_uuid=monster.uuid,
    )
    monster.add_condition(condition)
    application_frames = client.get(
        f"/ai/sessions/{session_id}/observation/frames",
        params={"since": before["observation_cursor"], "limit": 0},
    ).json()["frames"]
    for frame in application_frames:
        state = apply_observation_frame(state, frame)
    fresh = materialize_snapshot(
        client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()
    )

    semantic_key = "dnd.spells.illusion.HypnoticPatternEffect"
    for visible in (state.known_entities[str(monster.uuid)], fresh.known_entities[str(monster.uuid)]):
        assert visible.condition_facts is not None
        fact = next(row for row in visible.condition_facts if row.semantic_key == semantic_key)
        assert fact.removal_triggers == [
            ConditionRemovalTrigger.POSITIVE_DAMAGE_APPLIED,
            ConditionRemovalTrigger.SHAKE_AWAKE,
        ]
        assert fact.agency_denial is ConditionAgencyDenial.FULL_TURN
        assert fact.applied_source_event_cursor is not None
        assert encounter.current_turn_started_source_event_cursor is not None
        assert fact.applied_source_event_cursor > encounter.current_turn_started_source_event_cursor

    hero.senses.entities.pop(monster.uuid, None)
    complete_event(SensoryUpdateEvent(
        source_entity_uuid=hero.uuid,
        target_entity_uuid=hero.uuid,
        observer_uuid=hero.uuid,
        cause_event_uuid=uuid4(),
        update_reason=SensoryUpdateReason.PERCEIVABILITY,
        visible_entities_removed={monster.uuid: monster.position},
        phase=EventPhase.DECLARATION,
    ))
    visibility_frames = client.get(
        f"/ai/sessions/{session_id}/observation/frames",
        params={"since": state.observation_cursor, "limit": 0},
    ).json()["frames"]
    for frame in visibility_frames:
        state = apply_observation_frame(state, frame)
    fresh = materialize_snapshot(
        client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()
    )

    assert state.known_entities[str(monster.uuid)].condition_facts is None
    assert fresh.known_entities[str(monster.uuid)].condition_facts is None


def test_movement_projection_skips_redundant_child_breadcrumbs() -> None:
    """Parent movement frames carry path facts without separate step breadcrumbs."""
    client, session_id, hero, _monster, _encounter = create_observation_game()
    before_snapshot = client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()
    state = materialize_snapshot(before_snapshot)
    actions = client.get(
        f"/entity/{hero.uuid}/available-actions",
        params={"session_id": session_id},
    ).json()
    target_index = move_target_with_long_path(actions)

    execute = client.post(
        "/action/execute",
        json={
            "session_id": session_id,
            "entity_uuid": str(hero.uuid),
            "template_name": "Move",
            "target_index": target_index,
        },
    )

    assert execute.status_code == 200
    assert "event_data" not in execute.json()

    frames_payload = client.get(
        f"/ai/sessions/{session_id}/observation/frames",
        params={"since": before_snapshot["observation_cursor"], "limit": 0},
    ).json()
    frame_event_types = {frame.get("event_type") for frame in frames_payload["frames"]}

    for frame in frames_payload["frames"]:
        state = apply_observation_frame(state, frame)

    fresh_snapshot = client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()
    fresh_state = materialize_snapshot(fresh_snapshot)

    assert "movement" in frame_event_types
    assert "step_movement" not in frame_event_types
    assert "spatial_entity_entered" not in frame_event_types
    assert "spatial_entity_left" not in frame_event_types
    assert state.known_entities[str(hero.uuid)].position == fresh_state.known_entities[str(hero.uuid)].position
    assert state.combat_logs == fresh_state.combat_logs


def test_unseen_enemy_movement_does_not_leak_live_position_or_identity() -> None:
    """Seeing a movement event area must not reveal an unseen moving entity."""
    reset_observation_state()
    client = TestClient(app)
    hero = create_goblin(name="Hidden Observation Hero", position=(1, 1), faction="heroes")
    monster = create_skeleton(name="Observation Skeleton", position=(4, 1), faction="monsters")
    hero.add_condition(Invisible(source_entity_uuid=hero.uuid, target_entity_uuid=hero.uuid))
    Entity.update_all_entities_senses(max_distance=20)

    encounter = Encounter(name="Hidden Movement Observation", source_entity_uuid=uuid4())
    encounter.add_combatant(hero, HumanController(source_entity_uuid=hero.uuid))
    encounter.add_combatant(monster, PassController(source_entity_uuid=monster.uuid))
    encounter.roll_initiative()
    encounter.initiative_order = [hero.uuid, monster.uuid]
    encounter.current_turn_index = 0
    encounter.start_encounter()
    encounter.start_turn()
    sim.encounter = encounter
    game = sim.create_game_session(encounter)
    manager = sim.get_session_manager()
    hero_session = manager.create_session(PlayerType.HUMAN, "Hero Session")
    monster_session = manager.create_session(PlayerType.AI, "Monster Observer")
    game.add_player(hero_session)
    game.add_player(monster_session)
    game.assign_entity(hero.uuid, hero_session.session_id)
    game.assign_entity(monster.uuid, monster_session.session_id)

    assert hero.uuid not in monster.senses.entities
    assert monster.senses.visible.get((1, 1), False)
    assert monster.senses.visible.get((1, 2), False)

    before_snapshot = client.get(f"/ai/sessions/{monster_session.session_id}/observation/snapshot").json()
    state = materialize_snapshot(before_snapshot)
    assert str(hero.uuid) not in state.known_entities
    before_logs_text = json.dumps(state.combat_logs)
    assert str(hero.uuid) not in before_logs_text
    assert "Hidden Observation Hero" not in before_logs_text
    replication_bootstrap = bootstrap_player_replication(
        client,
        str(monster_session.session_id),
    )
    combat_log_cursor = replication_bootstrap["combat_log_frames"]["through_cursor"]

    hero_actions = client.get(
        f"/entity/{hero.uuid}/available-actions",
        params={"session_id": str(hero_session.session_id)},
    ).json()
    target_index = move_target_for_position(hero_actions, (1, 2))
    execute = client.post(
        "/action/execute",
        json={
            "session_id": str(hero_session.session_id),
            "entity_uuid": str(hero.uuid),
            "template_name": "Move",
            "target_index": target_index,
        },
    )
    assert execute.status_code == 200

    subjective_logs = get_player_combat_log_window(
        client,
        str(monster_session.session_id),
        replication_bootstrap,
        from_cursor=combat_log_cursor,
    )
    assert subjective_logs["through_cursor"] > combat_log_cursor
    movement_entries = [
        frame["entry"]
        for frame in subjective_logs["frames"]
        if frame["entry"] is not None
        and frame["entry"]["entry_type"] == CombatLogEntryType.MOVEMENT.value
    ]
    assert movement_entries
    for entry in movement_entries:
        assert entry["source_uuid"] == ""
        assert entry["source_name"] == "Unknown"
        assert entry["compact"] == "Something moves nearby"
        assert entry["data"] == {"type": "movement", "observed": True}
    subjective_logs_text = json.dumps(subjective_logs["frames"])
    assert str(hero.uuid) not in subjective_logs_text
    assert "Hidden Observation Hero" not in subjective_logs_text

    frames_payload = client.get(
        f"/ai/sessions/{monster_session.session_id}/observation/frames",
        params={"since": before_snapshot["observation_cursor"], "limit": 0},
    ).json()
    assert "movement" in {frame.get("event_type") for frame in frames_payload["frames"]}
    for frame in frames_payload["frames"]:
        state = apply_observation_frame(state, frame)

    assert str(hero.uuid) not in state.known_entities
    logs_text = json.dumps(state.combat_logs)
    assert str(hero.uuid) not in logs_text
    assert "Hidden Observation Hero" not in logs_text
    for log in state.combat_logs:
        if log.get("event_type") == "movement" or log.get("entry_type") == "movement":
            assert log.get("source_uuid") != str(hero.uuid)
            assert "path" not in log.get("data", {})
            assert "end_position" not in log.get("data", {})


def test_known_enemy_movement_log_stops_at_last_perceived_step() -> None:
    """A known mover's parent log cannot reveal steps hidden after contact is lost."""
    client, session_id, hero, monster, _encounter = create_observation_game()
    client.get(f"/ai/sessions/{session_id}/observation/snapshot")
    hero.senses.entities.pop(monster.uuid, None)

    visible_step = CombatLogEntry(
        entry_type=CombatLogEntryType.MOVEMENT,
        source_name=monster.name,
        source_uuid=str(monster.uuid),
        compact=f"{monster.name} steps to (3, 1)",
        verbose=f"{monster.name} (2, 1) -> (3, 1)",
        detailed=f"{monster.name} (2, 1) -> (3, 1) (step 1/3, 5ft)",
        data={
            "type": "step_movement",
            "from_position": (2, 1),
            "to_position": (3, 1),
            "path_index": 1,
            "movement_cost": 5.0,
        },
        perceiver_uuids={str(hero.uuid)},
        identified_entity_observer_uuids={str(monster.uuid): {str(hero.uuid)}},
        located_entity_observer_uuids={str(monster.uuid): {str(hero.uuid)}},
    )
    hidden_steps = [
        CombatLogEntry(
            entry_type=CombatLogEntryType.MOVEMENT,
            source_name=monster.name,
            source_uuid=str(monster.uuid),
            compact=f"{monster.name} steps to {destination}",
            verbose=f"{monster.name} {origin} -> {destination}",
            detailed=f"{monster.name} {origin} -> {destination}",
            data={
                "type": "step_movement",
                "from_position": origin,
                "to_position": destination,
                "path_index": index,
                "movement_cost": 5.0,
            },
            perceiver_uuids={str(monster.uuid)},
        )
        for index, origin, destination in (
            (2, (3, 1), (4, 1)),
            (3, (4, 1), (5, 1)),
        )
    ]
    parent_log = CombatLogEntry(
        entry_type=CombatLogEntryType.MOVEMENT,
        source_name=monster.name,
        source_uuid=str(monster.uuid),
        compact=f"{monster.name} moves 15ft to (5, 1)",
        verbose=f"{monster.name} moves (2, 1) -> (5, 1) (15ft)",
        detailed=f"{monster.name} moves (2, 1) -> (5, 1)\nPath: (2, 1) -> (3, 1) -> (4, 1) -> (5, 1)",
        data={
            "entity_name": monster.name,
            "entity_uuid": str(monster.uuid),
            "start_position": (2, 1),
            "end_position": (5, 1),
            "path": [(2, 1), (3, 1), (4, 1), (5, 1)],
            "distance_feet": 15,
            "movement_cost": 15,
        },
        sub_entries=[visible_step, *hidden_steps],
        perceiver_uuids={str(hero.uuid), str(monster.uuid)},
        identified_entity_observer_uuids={str(monster.uuid): {str(hero.uuid)}},
    )
    EventQueue.push_combat_log(parent_log, monster.uuid)

    snapshot = client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()
    movement = next(
        log
        for log in reversed(snapshot["combat_logs"])
        if log["entry_type"] == CombatLogEntryType.MOVEMENT.value
        and log["source_uuid"] == str(monster.uuid)
    )
    movement_text = json.dumps(movement)

    assert len(movement["sub_entries"]) == 1
    assert movement["data"]["observation_complete"] is False
    assert movement["data"]["observed_path_segments"] == []
    assert "start_position" not in movement["data"]
    assert "end_position" not in movement["data"]
    assert "path" not in movement["data"]
    safe_step = movement["sub_entries"][0]
    assert safe_step["entry_type"] == CombatLogEntryType.MOVEMENT.value
    assert safe_step["source_uuid"] == str(monster.uuid)
    assert safe_step["data"] == {
        "type": "movement",
        "observation_complete": False,
    }
    for hidden_position in ("(2, 1)", "(3, 1)", "(4, 1)", "(5, 1)"):
        assert hidden_position not in movement_text
    for hidden_position in ("[2, 1]", "[3, 1]", "[4, 1]", "[5, 1]"):
        assert hidden_position not in movement_text


def test_subjective_combat_logs_scrub_nested_hidden_identity_payloads() -> None:
    """Nested combat-log data cannot smuggle unknown entity identities."""
    client, session_id, hero, monster, _encounter = create_observation_game(hidden_monster=True)
    replication_bootstrap = bootstrap_player_replication(client, session_id)
    combat_log_cursor = replication_bootstrap["combat_log_frames"]["through_cursor"]
    child_log = CombatLogEntry(
        entry_type=CombatLogEntryType.SPELL_DAMAGE,
        source_name=monster.name,
        source_uuid=str(monster.uuid),
        target_name=monster.name,
        target_uuid=str(monster.uuid),
        compact=f"{monster.name} nested child",
        verbose=f"{monster.name} nested child verbose",
        detailed=f"{monster.name} nested child detailed",
        data={
            "target_name": monster.name,
            "target_uuid": str(monster.uuid),
            "nested": {
                "entity_uuid": str(monster.uuid),
                "entity_name": monster.name,
                "targets": [
                    {"target_uuid": str(monster.uuid), "target_name": monster.name},
                    str(monster.uuid),
                    monster.name,
                ],
            },
        },
        perceiver_uuids={str(hero.uuid)},
    )
    parent_log = CombatLogEntry(
        entry_type=CombatLogEntryType.MULTI_ENTITY_ACTION,
        source_name=monster.name,
        source_uuid=str(monster.uuid),
        target_name=None,
        target_uuid=None,
        compact=f"{monster.name} uses nested leakage",
        verbose=f"{monster.name} uses nested leakage verbose",
        detailed=f"{monster.name} uses nested leakage detailed",
        data={
            "action_name": "Nested Leakage",
            "caster_name": monster.name,
            "total_targets": 1,
            "target_names": [monster.name],
            "per_target_logs": [
                {
                    "target_name": monster.name,
                    "target_uuid": str(monster.uuid),
                    "deeper": [{"entity_uuid": str(monster.uuid), "entity_name": monster.name}],
                }
            ],
        },
        sub_entries=[child_log],
        perceiver_uuids={str(hero.uuid)},
    )
    raw_log_text = parent_log.model_dump_json()
    assert str(monster.uuid) in raw_log_text
    assert monster.name in raw_log_text
    EventQueue.push_combat_log(parent_log, monster.uuid)

    subjective_logs = get_player_combat_log_window(
        client,
        session_id,
        replication_bootstrap,
        from_cursor=combat_log_cursor,
    )
    assert subjective_logs["through_cursor"] == combat_log_cursor + 1
    canonical_logs_text = json.dumps(subjective_logs["frames"])
    snapshot = client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()
    logs_text = json.dumps(snapshot["combat_logs"])

    assert str(monster.uuid) not in canonical_logs_text
    assert monster.name not in canonical_logs_text
    assert "Unknown" in canonical_logs_text
    assert str(monster.uuid) not in logs_text
    assert monster.name not in logs_text
    assert "Unknown" in logs_text


def test_repeated_projectile_keeps_declared_target_identity_after_lethal_hit() -> None:
    """Later projectiles retain a target identified when the cast was declared."""
    arena = create_ai_validation_arena("multi_projectile_no_aoe_lab")
    sim.encounter = arena.encounter
    game = sim.create_game_session(arena.encounter)
    session = sim.get_session_manager().create_session(PlayerType.AI, "Projectile Agent")
    game.add_player(session)
    game.assign_entity(arena.hero.uuid, session.session_id)
    client = TestClient(app)
    snapshot = client.get(
        f"/ai/sessions/{session.session_id}/observation/snapshot"
    ).json()
    archer = next(monster for monster in arena.monsters if "Archer" in monster.name)
    goblin = next(monster for monster in arena.monsters if "Goblin" in monster.name)

    with fixed_dice_faces(1, 2, 2):
        event = MagicMissile(
            source_entity_uuid=arena.hero.uuid,
            target_entity_uuid=archer.uuid,
            extra_target_entity_uuids=[goblin.uuid, goblin.uuid],
            cast_at_level=1,
        ).apply()

    assert event is not None
    assert goblin.health.life_state is LifeState.DEAD
    frames = client.get(
        f"/ai/sessions/{session.session_id}/observation/frames",
        params={"since": snapshot["observation_cursor"], "limit": 0},
    ).json()["frames"]
    cast_log = next(
        frame["combat_log"]
        for frame in frames
        if frame.get("event_type") == "cast_spell" and frame.get("combat_log")
    )
    goblin_darts = [
        child
        for child in cast_log["sub_entries"]
        if child["data"].get("spell_name") == "Magic Missile"
        and child["data"].get("damage") == 3
    ]

    assert len(goblin_darts) == 2
    assert [dart["target_uuid"] for dart in goblin_darts] == [
        str(goblin.uuid),
        str(goblin.uuid),
    ]
    assert [dart["target_name"] for dart in goblin_darts] == [
        goblin.name,
        goblin.name,
    ]


def test_multi_projectile_summary_ignores_non_target_causal_descendants() -> None:
    """Repeated direct targets are not replaced by targets of nested consequences."""
    def log(
        entry_type: CombatLogEntryType,
        target_name: str,
        target_uuid: str,
        *,
        damage: int | None = None,
        children: list[CombatLogEntry] | None = None,
    ) -> CombatLogEntry:
        data = {"total_damage": damage} if damage is not None else {}
        return CombatLogEntry(
            entry_type=entry_type,
            source_name="Sorcerer",
            source_uuid="sorcerer",
            target_name=target_name,
            target_uuid=target_uuid,
            compact=f"{entry_type.value} -> {target_name}",
            verbose=f"{entry_type.value} -> {target_name}",
            detailed=f"{entry_type.value} -> {target_name}",
            data=data,
            sub_entries=list(children or []),
        )

    hero_cleanup = log(CombatLogEntryType.CONDITION_REMOVED, "Hero", "hero")
    warrior_cleanup = log(
        CombatLogEntryType.CONDITION_REMOVED,
        "Skeleton Warrior",
        "warrior",
    )
    direct_children = [
        log(
            CombatLogEntryType.SPELL_DAMAGE,
            "Skeleton Warlock",
            "warlock",
            damage=12,
            children=[hero_cleanup],
        ),
        log(
            CombatLogEntryType.SPELL_DAMAGE,
            "Skeleton Warlock",
            "warlock",
            damage=4,
        ),
        log(
            CombatLogEntryType.SPELL_DAMAGE,
            "Skeleton Warlock",
            "warlock",
            damage=5,
            children=[warrior_cleanup],
        ),
    ]
    parent = CombatLogEntry(
        entry_type=CombatLogEntryType.MULTI_ENTITY_ACTION,
        source_name="Sorcerer",
        source_uuid="sorcerer",
        compact="Sorcerer uses Scorching Ray",
        verbose="Sorcerer uses Scorching Ray",
        detailed="Sorcerer uses Scorching Ray",
        data={"action_name": "Scorching Ray", "total_targets": 3},
        sub_entries=direct_children,
    )

    _enrich_multi_entity_log_from_children(parent, direct_children)
    subjective_data = _sanitize_multi_entity_log_summary(
        parent,
        direct_children,
        dict(parent.data),
    )

    assert parent.data["target_names"] == ["Skeleton Warlock"]
    assert parent.data["per_target_damage"] == [12, 4, 5]
    assert subjective_data["target_names"] == ["Skeleton Warlock"]
    assert len(parent.sub_entries) == 3
    assert parent.sub_entries[0].sub_entries == [hero_cleanup]
    assert parent.sub_entries[2].sub_entries == [warrior_cleanup]


def test_ai_observation_snapshot_includes_visible_combat_logs() -> None:
    """Fresh snapshots include visible combat logs for Codex briefs and turns."""
    client, session_id, hero, monster, _encounter = create_observation_game()
    actions = client.get(
        f"/entity/{hero.uuid}/available-actions",
        params={"session_id": session_id},
    ).json()
    target_index = attack_target_index(actions, monster.uuid)
    modifier_uuid = add_auto_hit(hero)

    try:
        with fixed_dice_faces(12, 4):
            response = client.post(
                "/action/execute",
                json={
                    "session_id": session_id,
                    "entity_uuid": str(hero.uuid),
                    "template_name": "Attack_MELEE_MAIN",
                    "target_index": target_index,
                },
            )
    finally:
        hero.equipment.melee_attack_bonus.self_static.remove_modifier(modifier_uuid)

    snapshot = client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()
    state = materialize_snapshot(snapshot)

    assert response.status_code == 200
    assert snapshot["combat_logs"]
    assert state.combat_logs == snapshot["combat_logs"]
    assert any(
        entry["entry_type"] in {"attack", "damage_taken"}
        for entry in snapshot["combat_logs"]
    )


def test_subjective_blocked_damage_log_exposes_exact_effect_id() -> None:
    """A perceived blocked effect retains its stable identity for its controller."""
    client, session_id, hero, monster, _encounter = create_observation_game()
    monster.add_condition(ShieldBuff(
        source_entity_uuid=monster.uuid,
        target_entity_uuid=monster.uuid,
    ))
    client.get(f"/ai/sessions/{session_id}/observation/snapshot")

    actual_damage = monster.receive_damage(
        5,
        DamageType.FORCE,
        hero.uuid,
        effect_id=MAGIC_MISSILE_DAMAGE_EFFECT_ID,
    )
    snapshot = client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()
    damage_log = next(
        entry
        for entry in reversed(snapshot["combat_logs"])
        if entry["entry_type"] == CombatLogEntryType.DAMAGE_TAKEN.value
        and entry["source_uuid"] == str(hero.uuid)
        and entry["target_uuid"] == str(monster.uuid)
    )

    assert monster.uuid in hero.senses.entities
    assert actual_damage == 0
    assert damage_log["perceiver_uuids"] == []
    assert damage_log["success"] is False
    assert damage_log["data"]["blocked"] is True
    assert damage_log["data"]["effect_id"] == MAGIC_MISSILE_DAMAGE_EFFECT_ID


def test_subjective_successful_damage_log_exposes_exact_effect_id() -> None:
    """A perceived successful effect retains its stable identity for its controller."""
    client, session_id, hero, monster, _encounter = create_observation_game()
    effect_id = "tests.subjective_observation.successful_damage"
    client.get(f"/ai/sessions/{session_id}/observation/snapshot")

    actual_damage = monster.receive_damage(
        3,
        DamageType.FORCE,
        hero.uuid,
        effect_id=effect_id,
    )
    snapshot = client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()
    damage_log = next(
        entry
        for entry in reversed(snapshot["combat_logs"])
        if entry["entry_type"] == CombatLogEntryType.DAMAGE_TAKEN.value
        and entry["source_uuid"] == str(hero.uuid)
        and entry["target_uuid"] == str(monster.uuid)
    )

    assert actual_damage == 3
    assert damage_log["success"] is True
    assert damage_log["data"]["damage"] == 3
    assert damage_log["data"]["effect_id"] == effect_id


def test_subjective_damage_evidence_respects_sanitization_and_perception() -> None:
    """Typed effect evidence cannot reveal hidden identities or unseen events."""
    client, session_id, hero, monster, _encounter = create_observation_game(hidden_monster=True)
    client.get(f"/ai/sessions/{session_id}/observation/snapshot")

    hidden_identity_log = TakeDamageEvent(
        source_entity_uuid=monster.uuid,
        target_entity_uuid=hero.uuid,
        source_entity_name=monster.name,
        target_entity_name=hero.name,
        total_damage=1,
        damages=[],
        effect_id=str(monster.uuid),
        use_register=False,
    ).generate_combat_log().model_copy(update={
        "perceiver_uuids": {str(hero.uuid)},
    })
    unperceived_effect_id = "tests.subjective_observation.unperceived_damage"
    unperceived_log = TakeDamageEvent(
        source_entity_uuid=monster.uuid,
        target_entity_uuid=monster.uuid,
        source_entity_name=monster.name,
        target_entity_name=monster.name,
        total_damage=1,
        damages=[],
        effect_id=unperceived_effect_id,
        use_register=False,
    ).generate_combat_log().model_copy(update={
        "perceiver_uuids": {str(monster.uuid)},
    })

    assert hidden_identity_log.data["effect_id"] == str(monster.uuid)
    assert unperceived_log.data["effect_id"] == unperceived_effect_id
    EventQueue.push_combat_log(hidden_identity_log, monster.uuid)
    EventQueue.push_combat_log(unperceived_log, monster.uuid)

    snapshot = client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()
    logs_json = json.dumps(snapshot["combat_logs"])
    perceived_damage = next(
        entry
        for entry in reversed(snapshot["combat_logs"])
        if entry["entry_type"] == CombatLogEntryType.DAMAGE_TAKEN.value
        and entry["target_uuid"] == str(hero.uuid)
    )

    assert perceived_damage["source_uuid"] == ""
    assert perceived_damage["source_name"] == "Unknown"
    assert "effect_id" not in perceived_damage["data"]
    assert str(monster.uuid) not in logs_json
    assert monster.name not in logs_json
    assert unperceived_effect_id not in logs_json


def test_lethal_log_retains_identity_known_when_event_started() -> None:
    """A visible victim remains identified throughout its lethal log tree."""
    client, session_id, hero, monster, _encounter = create_observation_game()
    actions = client.get(
        f"/entity/{hero.uuid}/available-actions",
        params={"session_id": session_id},
    ).json()
    target_index = attack_target_index(actions, monster.uuid)
    modifier_uuid = add_auto_hit(hero)
    set_hp(monster, 1)

    assert monster.uuid in hero.senses.entities
    try:
        with fixed_dice_faces(12, 4):
            response = client.post(
                "/action/execute",
                json={
                    "session_id": session_id,
                    "entity_uuid": str(hero.uuid),
                    "template_name": "Attack_MELEE_MAIN",
                    "target_index": target_index,
                },
            )
    finally:
        hero.equipment.melee_attack_bonus.self_static.remove_modifier(modifier_uuid)

    snapshot = client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()
    pending = list(snapshot["combat_logs"])
    flattened = []
    while pending:
        entry = pending.pop()
        flattened.append(entry)
        pending.extend(entry.get("sub_entries", []))

    attack = next(entry for entry in flattened if entry["entry_type"] == "attack")
    damage = next(entry for entry in flattened if entry["entry_type"] == "damage_taken")
    death = next(entry for entry in flattened if entry["entry_type"] == "death")

    assert response.status_code == 200
    assert monster.uuid not in hero.senses.entities
    assert attack["target_uuid"] == str(monster.uuid)
    assert attack["target_name"] == monster.name
    assert attack["data"]["target_uuid"] == str(monster.uuid)
    assert attack["data"]["target_name"] == monster.name
    assert damage["target_uuid"] == str(monster.uuid)
    assert damage["target_name"] == monster.name
    assert damage["data"]["target_name"] == monster.name
    assert death["source_uuid"] == str(monster.uuid)
    assert death["source_name"] == monster.name
    assert death["data"]["entity_name"] == monster.name


def test_observed_death_survives_visibility_loss_replay_and_snapshot_resync() -> None:
    """A proven death remains known after the corpse leaves current perception."""
    client, session_id, hero, monster, _encounter = create_observation_game()
    before = client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()
    state = materialize_snapshot(before)
    actions = client.get(
        f"/entity/{hero.uuid}/available-actions",
        params={"session_id": session_id},
    ).json()
    target_index = attack_target_index(actions, monster.uuid)
    modifier_uuid = add_auto_hit(hero)
    set_hp(monster, 1)

    try:
        with fixed_dice_faces(12, 4):
            response = client.post(
                "/action/execute",
                json={
                    "session_id": session_id,
                    "entity_uuid": str(hero.uuid),
                    "template_name": "Attack_MELEE_MAIN",
                    "target_index": target_index,
                },
            )
    finally:
        hero.equipment.melee_attack_bonus.self_static.remove_modifier(modifier_uuid)

    frames = client.get(
        f"/ai/sessions/{session_id}/observation/frames",
        params={"since": before["observation_cursor"], "limit": 0},
    ).json()["frames"]
    for frame in frames:
        state = apply_observation_frame(state, frame)

    fresh_state = materialize_snapshot(
        client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()
    )
    replayed = state.known_entities[str(monster.uuid)]
    resynced = fresh_state.known_entities[str(monster.uuid)]
    contacts = derive_agent_facts(fresh_state).facts.contacts

    assert response.status_code == 200
    assert monster.uuid not in hero.senses.entities
    assert replayed.knowledge_state.value == "remembered"
    assert replayed.position == monster.position
    assert replayed.life_state is LifeState.DEAD
    assert replayed.is_dead is True
    assert resynced.knowledge_state.value == "remembered"
    assert resynced.position == monster.position
    assert resynced.life_state is LifeState.DEAD
    assert resynced.is_dead is True
    assert contacts.known_dead_entity_uuids == (str(monster.uuid),)
    assert str(monster.uuid) not in contacts.remembered_hostile_uuids


def test_child_log_inherits_identity_established_by_its_causal_parent() -> None:
    """A causal child keeps identities known when the parent event began."""
    client, session_id, hero, monster, _encounter = create_observation_game()
    parent = Event(
        name="Known parent",
        event_type=EventType.BASE_ACTION,
        source_entity_uuid=hero.uuid,
        target_entity_uuid=monster.uuid,
        combat_log=CombatLogEntry(
            entry_type=CombatLogEntryType.ACTION,
            source_name=hero.name,
            source_uuid=str(hero.uuid),
            target_name=monster.name,
            target_uuid=str(monster.uuid),
            compact=f"{hero.name} begins an action against {monster.name}",
            verbose=f"{hero.name} begins an action against {monster.name}",
            detailed=f"{hero.name} begins an action against {monster.name}",
        ),
    )

    assert parent.identified_entity_observer_uuids[str(monster.uuid)] == {str(hero.uuid), str(monster.uuid)}

    hero.senses.entities.pop(monster.uuid, None)
    child = Event(
        name="Late causal child",
        event_type=EventType.TAKE_DAMAGE,
        source_entity_uuid=hero.uuid,
        target_entity_uuid=monster.uuid,
        parent_event=parent.uuid,
        combat_log=CombatLogEntry(
            entry_type=CombatLogEntryType.DAMAGE_TAKEN,
            source_name=hero.name,
            source_uuid=str(hero.uuid),
            target_name=monster.name,
            target_uuid=str(monster.uuid),
            compact=f"{monster.name} takes damage",
            verbose=f"{monster.name} takes damage",
            detailed=f"{monster.name} takes damage",
            data={"target_name": monster.name, "target_uuid": str(monster.uuid)},
        ),
    )

    assert str(hero.uuid) in child.identified_entity_observer_uuids[str(monster.uuid)]

    child.phase_to(EventPhase.EXECUTION).phase_to(EventPhase.EFFECT).phase_to(EventPhase.COMPLETION)
    parent.phase_to(EventPhase.EXECUTION).phase_to(EventPhase.EFFECT).phase_to(EventPhase.COMPLETION)
    snapshot = client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()
    pending = list(snapshot["combat_logs"])
    flattened = []
    while pending:
        entry = pending.pop()
        flattened.append(entry)
        pending.extend(entry.get("sub_entries", []))

    damage = next(entry for entry in flattened if entry["entry_type"] == "damage_taken")
    assert damage["target_uuid"] == str(monster.uuid)
    assert damage["target_name"] == monster.name
    assert damage["data"]["target_uuid"] == str(monster.uuid)
    assert damage["data"]["target_name"] == monster.name
