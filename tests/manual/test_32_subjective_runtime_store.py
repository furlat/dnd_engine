"""Local materialization-store checks for subjective runtime clients."""

from uuid import uuid4

from dnd.core.life_types import LifeState
from server.agent_protocol.observation import (
    KnowledgeState,
    ObservationEntityFact,
    ObservationFrame,
    ObservationFrameType,
    ObservationPatch,
    ObservationPatchType,
    ObservationSessionState,
    SubjectiveWorldState,
)
from server.agent_protocol.control import CommandResult, CommandResultStatus
from server.agent_protocol.semantics import ActionSemantics, action_semantics_ref
from ai.subjective.store import ApplyResultKind, SubjectiveStore
from tests.manual.test_28_subjective_observation_stream import create_observation_game


def test_store_loads_snapshot_and_ignores_duplicate_frames() -> None:
    """Snapshots seed the store and duplicate old frames are idempotent."""
    client, session_id, _hero, _monster, _encounter = create_observation_game()
    snapshot = client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()
    store = SubjectiveStore()
    world = store.load_snapshot(snapshot)
    duplicate = ObservationFrame(
        observation_cursor=snapshot["observation_cursor"],
        frame_type=ObservationFrameType.PATCH,
        patches=[],
    )

    result = store.apply_frame(duplicate)

    assert world.observation_cursor == snapshot["observation_cursor"]
    assert world.current_epoch is not None
    assert result.kind == ApplyResultKind.DUPLICATE
    assert store.world is world


def test_store_owns_one_typed_subjective_world() -> None:
    """The store owns one canonical typed subjective world."""
    client, session_id, _hero, _monster, _encounter = create_observation_game()
    snapshot = client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()
    store = SubjectiveStore()

    world = store.load_snapshot(snapshot)

    assert isinstance(world, SubjectiveWorldState)
    assert store.world is world
    assert isinstance(world.session, ObservationSessionState)
    assert world.current_epoch is not None
    assert world.known_entities
    assert isinstance(world.known_objects, dict)
    assert isinstance(world.known_tiles, dict)
    assert not hasattr(store, "history")


def test_cursor_gap_triggers_resync_required_result() -> None:
    """A non-contiguous frame is reported as a gap instead of being applied."""
    client, session_id, _hero, _monster, _encounter = create_observation_game()
    snapshot = client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()
    store = SubjectiveStore()
    store.load_snapshot(snapshot)
    gap_frame = ObservationFrame(
        observation_cursor=snapshot["observation_cursor"] + 2,
        frame_type=ObservationFrameType.PATCH,
        patches=[],
    )

    result = store.apply_frame(gap_frame)

    assert result.kind == ApplyResultKind.GAP
    assert result.expected_cursor == snapshot["observation_cursor"] + 1
    assert result.actual_cursor == snapshot["observation_cursor"] + 2


def test_observer_patch_updates_position_and_passive_perception() -> None:
    """Sensory deltas keep the controlled observer record aligned with its entity."""
    client, session_id, hero, _monster, _encounter = create_observation_game()
    snapshot = client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()
    store = SubjectiveStore()
    store.load_snapshot(snapshot)
    observer_uuid = str(hero.uuid)
    assert store.world is not None
    original = store.world.observers[observer_uuid]
    destination = (original.position[0] + 1, original.position[1] + 2)

    result = store.apply_frame(ObservationFrame(
        observation_cursor=snapshot["observation_cursor"] + 1,
        frame_type=ObservationFrameType.PATCH,
        patches=[ObservationPatch(
            patch_type=ObservationPatchType.OBSERVER,
            reason="movement",
            data={
                "observer_uuid": observer_uuid,
                "position": list(destination),
                "passive_perception": original.passive_perception + 1,
            },
        )],
    ))

    assert result.kind is ApplyResultKind.APPLIED
    assert store.world is not None
    updated = store.world.observers[observer_uuid]
    assert updated.position == destination
    assert updated.passive_perception == original.passive_perception + 1


def test_apply_frame_can_skip_previous_world_capture_for_replay_batches() -> None:
    """Replay batches can avoid deep-copying the world for every frame."""
    client, session_id, _hero, _monster, _encounter = create_observation_game()
    snapshot = client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()
    store = SubjectiveStore()
    store.load_snapshot(snapshot)
    frame = ObservationFrame(
        observation_cursor=snapshot["observation_cursor"] + 1,
        frame_type=ObservationFrameType.PATCH,
        patches=[],
    )

    result = store.apply_frame(frame, capture_previous=False)

    assert result.kind == ApplyResultKind.APPLIED
    assert result.previous_world is None
    assert store.world is not None
    assert store.world.observation_cursor == snapshot["observation_cursor"] + 1


def test_store_retains_only_applied_subjective_envelopes_after_snapshot() -> None:
    """Decision deltas can use causal local history without retaining objective events."""
    client, session_id, _hero, _monster, _encounter = create_observation_game()
    snapshot = client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()
    store = SubjectiveStore()
    store.load_snapshot(snapshot)
    first = ObservationFrame(
        observation_cursor=snapshot["observation_cursor"] + 1,
        frame_type=ObservationFrameType.PATCH,
        patches=[],
    )
    second = ObservationFrame(
        observation_cursor=snapshot["observation_cursor"] + 2,
        frame_type=ObservationFrameType.PATCH,
        patches=[],
    )

    assert store.apply_frame(first).kind is ApplyResultKind.APPLIED
    assert store.apply_frame(first).kind is ApplyResultKind.DUPLICATE
    assert store.apply_frame(second).kind is ApplyResultKind.APPLIED

    assert store.snapshot_observation_cursor == snapshot["observation_cursor"]
    assert store.frames_after(snapshot["observation_cursor"]) == (first, second)
    assert store.frames_after(first.observation_cursor) == (second,)

    store.load_snapshot(snapshot)
    assert store.observation_frames == []
    assert store.frames_after(0) == tuple()


def test_previous_world_capture_reuses_the_immutable_world_snapshot() -> None:
    """Hooks receive the stable prior world without deep-cloning epoch contracts."""
    client, session_id, _hero, _monster, _encounter = create_observation_game()
    snapshot = client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()
    store = SubjectiveStore()
    previous = store.load_snapshot(snapshot)
    frame = ObservationFrame(
        observation_cursor=snapshot["observation_cursor"] + 1,
        frame_type=ObservationFrameType.PATCH,
        patches=[],
    )

    result = store.apply_frame(frame)

    assert result.kind == ApplyResultKind.APPLIED
    assert result.previous_world is previous
    assert previous.observation_cursor == snapshot["observation_cursor"]
    assert result.world is not previous
    assert result.world.current_epoch is previous.current_epoch


def test_gap_frame_does_not_mutate_the_semantic_contract_pool() -> None:
    """Rejected future data cannot alter local semantic knowledge or LRU state."""
    client, session_id, _hero, _monster, _encounter = create_observation_game()
    snapshot = client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()
    store = SubjectiveStore()
    store.load_snapshot(snapshot)
    semantics = ActionSemantics(semantic_id="probe.gap")
    reference = action_semantics_ref(semantics)
    gap_frame = {
        "observation_cursor": snapshot["observation_cursor"] + 2,
        "frame_type": ObservationFrameType.DECISION_EPOCH.value,
        "patches": [],
        "decision_epoch": {
            **snapshot["current_epoch"],
            "affordances": {
                **snapshot["current_epoch"]["affordances"],
                "semantic_catalog": {reference: semantics.model_dump(mode="json")},
            },
        },
    }

    result = store.apply_frame(gap_frame)

    assert result.kind == ApplyResultKind.GAP
    assert store.semantic_contracts.get(reference) is None


def test_command_result_frame_updates_world_cursor_and_command_history() -> None:
    """Command-result frames are retained without clearing epochs by themselves."""
    client, session_id, _hero, _monster, _encounter = create_observation_game()
    snapshot = client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()
    store = SubjectiveStore()
    store.load_snapshot(snapshot)
    result_payload = CommandResult(
        status=CommandResultStatus.ACCEPTED,
        session_id=session_id,
        actor_uuid=snapshot["current_epoch"]["actor_uuid"],
        requested_epoch_id=snapshot["current_epoch"]["epoch_id"],
        current_epoch_id=None,
        row_id="special|End Turn|index=0",
        message="Turn ended.",
        resync_required=False,
    )
    frame = ObservationFrame(
        observation_cursor=snapshot["observation_cursor"] + 1,
        frame_type=ObservationFrameType.COMMAND_RESULT,
        event_uuid=str(uuid4()),
        patches=[
            ObservationPatch(
                patch_type=ObservationPatchType.COMMAND_RESULT,
                reason="command_result",
                data={"status": result_payload.status.value},
            )
        ],
        command_result=result_payload,
        decision_epoch=None,
    )

    apply_result = store.apply_frame(frame)

    assert apply_result.kind == ApplyResultKind.APPLIED
    assert store.world is not None
    assert store.world.observation_cursor == snapshot["observation_cursor"] + 1
    assert store.world.current_epoch is not None
    assert store.command_results == [result_payload]


def test_epoch_clear_frame_explicitly_clears_current_epoch() -> None:
    """Epoch lifetime is controlled by DECISION_EPOCH frames, not incidental frames."""
    client, session_id, _hero, _monster, _encounter = create_observation_game()
    snapshot = client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()
    store = SubjectiveStore()
    store.load_snapshot(snapshot)
    frame = ObservationFrame(
        observation_cursor=snapshot["observation_cursor"] + 1,
        frame_type=ObservationFrameType.DECISION_EPOCH,
        patches=[
            ObservationPatch(
                patch_type=ObservationPatchType.DECISION_EPOCH,
                reason="turn_ended",
                data={"decision_epoch": None},
            )
        ],
        decision_epoch=None,
    )

    apply_result = store.apply_frame(frame)

    assert apply_result.kind == ApplyResultKind.APPLIED
    assert store.world is not None
    assert store.world.current_epoch is None


def test_known_death_survives_redaction_but_not_visible_resurrection() -> None:
    """Unknown replacement data cannot erase death, while visible life can."""
    client, session_id, _hero, monster, _encounter = create_observation_game()
    snapshot = client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()
    store = SubjectiveStore()
    store.load_snapshot(snapshot)
    entity_uuid = str(monster.uuid)
    visible = ObservationEntityFact.model_validate(
        next(entity for entity in snapshot["known_entities"] if entity["uuid"] == entity_uuid)
    )
    known_dead = visible.model_copy(update={
        "life_state": LifeState.DEAD,
        "is_dead": True,
    })
    remembered_unknown = known_dead.model_copy(update={
        "knowledge_state": KnowledgeState.REMEMBERED,
        "hp": None,
        "max_hp": None,
        "life_state": None,
        "is_dead": None,
    })
    resurrected = visible.model_copy(update={
        "life_state": LifeState.ALIVE,
        "is_dead": False,
    })

    for offset, fact in enumerate((known_dead, remembered_unknown, resurrected), start=1):
        result = store.apply_frame(ObservationFrame(
            observation_cursor=snapshot["observation_cursor"] + offset,
            frame_type=ObservationFrameType.PATCH,
            patches=[ObservationPatch(
                patch_type=ObservationPatchType.ENTITY,
                reason="knowledge_transition",
                data={"entity": fact.model_dump(mode="json")},
            )],
        ))
        assert result.kind == ApplyResultKind.APPLIED

        assert store.world is not None
        if offset < 3:
            assert store.world.known_entities[entity_uuid].life_state is LifeState.DEAD
            assert store.world.known_entities[entity_uuid].is_dead is True

    assert store.world is not None
    assert store.world.known_entities[entity_uuid].knowledge_state is KnowledgeState.VISIBLE
    assert store.world.known_entities[entity_uuid].life_state is LifeState.ALIVE
    assert store.world.known_entities[entity_uuid].is_dead is False
