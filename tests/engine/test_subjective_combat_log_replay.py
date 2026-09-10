"""Public proofs for same-model subjective logs and sensory replay."""

from __future__ import annotations

import json
from uuid import UUID, uuid4

import pytest

from dnd.actions import JumpEvent, TraverseConnectorEvent
from dnd.blocks.sensory import Senses, capture_senses_snapshot
from dnd.core.action_execution import (
    MovementProvocationPolicy,
    MovementTerminationReason,
)
from dnd.core.combat_log import (
    CombatLogEntry,
    CombatLogEntryType,
    DamageRollDisplay,
    DiceRollDisplay,
    format_attack_compact,
    format_attack_detailed,
    format_attack_verbose,
    position_evidence_key,
)
from dnd.core.events import (
    EntityCreatedEvent,
    Event,
    EventPhase,
    EventQueue,
    EventType,
    MovementTrajectory,
    SensoryUpdateEvent,
    SensoryUpdateReason,
    StepMovementEvent,
    WorldInitializedEvent,
)
from dnd.core.traversal_connectors import (
    ConnectorProvocationPolicy,
    TraversalConnectorKind,
)
from dnd.encounter import Encounter
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.subjective_combat_log import project_combat_log
from dnd.types.senses import PerceivedContact, SenseMode, SensesType
from dnd.types.world import LightLevel


CONTROLLED_UUID = "00000000-0000-0000-0000-000000000001"
OBSERVER_UUID = "00000000-0000-0000-0000-000000000002"
VISIBLE_TARGET_UUID = "00000000-0000-0000-0000-000000000003"
HIDDEN_SOURCE_UUID = "00000000-0000-0000-0000-000000000004"
HIDDEN_TARGET_UUID = "00000000-0000-0000-0000-000000000005"


@pytest.fixture(autouse=True)
def _reset_runtime() -> None:
    reset_engine_runtime(grid_size=(8, 8))


def _log(
    entry_type: CombatLogEntryType,
    *,
    source_name: str = "Hidden Assassin",
    source_uuid: str = HIDDEN_SOURCE_UUID,
    target_name: str | None = "Controlled Hero",
    target_uuid: str | None = CONTROLLED_UUID,
    data: dict | None = None,
    sub_entries: list[CombatLogEntry] | None = None,
    perceiver_uuids: set[str] | None = None,
) -> CombatLogEntry:
    text = f"{source_name} ({source_uuid}) affects {target_name}"
    return CombatLogEntry(
        entry_type=entry_type,
        source_name=source_name,
        source_uuid=source_uuid,
        target_name=target_name,
        target_uuid=target_uuid,
        compact=text,
        verbose=text,
        detailed=text,
        data=dict(data or {}),
        sub_entries=list(sub_entries or []),
        perceiver_uuids=set(
            {CONTROLLED_UUID}
            if perceiver_uuids is None
            else perceiver_uuids
        ),
    )


def _project(log: CombatLogEntry) -> CombatLogEntry | None:
    return project_combat_log(
        log,
        controlled_entity_uuids=frozenset({CONTROLLED_UUID}),
        observer_entity_uuids=frozenset({OBSERVER_UUID}),
    )


@pytest.mark.parametrize(
    "entry_type",
    tuple(CombatLogEntryType),
    ids=lambda entry_type: entry_type.value,
)
def test_every_log_kind_uses_the_same_recursive_projection(
    entry_type: CombatLogEntryType,
) -> None:
    objective = _log(
        entry_type,
        data={
            "hidden_uuid": HIDDEN_SOURCE_UUID,
            f"secret/{HIDDEN_SOURCE_UUID}": "hidden key",
            "nested": {
                "rows": [
                    "Hidden Assassin",
                    {"identity": f"Hidden Assassin/{HIDDEN_SOURCE_UUID}"},
                ],
            },
        },
        perceiver_uuids={OBSERVER_UUID},
    )
    objective_before = objective.model_copy(deep=True)

    projected = _project(objective)

    assert isinstance(projected, CombatLogEntry)
    serialized = json.dumps(projected.model_dump(mode="json"), sort_keys=True)
    assert HIDDEN_SOURCE_UUID not in serialized
    assert "Hidden Assassin" not in serialized
    assert projected.perceiver_uuids == set()
    assert projected.revealed_entity_uuids == set()
    assert projected.identified_entity_observer_uuids == {}
    assert projected.located_entity_observer_uuids == {}
    assert projected.located_position_observer_uuids == {}
    assert objective == objective_before


def test_fully_unobserved_tree_is_hidden() -> None:
    hidden_child = _log(
        CombatLogEntryType.DAMAGE_TAKEN,
        target_name="Hidden Target",
        target_uuid=HIDDEN_TARGET_UUID,
        perceiver_uuids={HIDDEN_SOURCE_UUID},
    )
    objective = _log(
        CombatLogEntryType.ACTION,
        target_name="Hidden Target",
        target_uuid=HIDDEN_TARGET_UUID,
        sub_entries=[hidden_child],
        perceiver_uuids={HIDDEN_SOURCE_UUID},
    )

    assert _project(objective) is None


def test_visible_child_retains_its_sanitized_hidden_parent() -> None:
    visible_child = _log(
        CombatLogEntryType.DAMAGE_TAKEN,
        source_name="Controlled Hero",
        source_uuid=CONTROLLED_UUID,
        data={"damage": 7},
        perceiver_uuids=set(),
    )
    objective = _log(
        CombatLogEntryType.ACTION,
        target_name="Hidden Target",
        target_uuid=HIDDEN_TARGET_UUID,
        sub_entries=[visible_child],
        perceiver_uuids={HIDDEN_SOURCE_UUID},
    )

    projected = _project(objective)

    assert isinstance(projected, CombatLogEntry)
    assert projected.entry_type is CombatLogEntryType.ACTION
    assert projected.source_name == "Unknown"
    assert projected.source_uuid == ""
    assert len(projected.sub_entries) == 1
    assert projected.sub_entries[0].entry_type is CombatLogEntryType.DAMAGE_TAKEN
    assert projected.sub_entries[0].data["damage"] == 7


def test_multi_target_summary_contains_only_projected_children() -> None:
    visible = _log(
        CombatLogEntryType.SPELL_SAVE,
        source_name="Controlled Hero",
        source_uuid=CONTROLLED_UUID,
        target_name="Visible Target",
        target_uuid=VISIBLE_TARGET_UUID,
        data={"save_success": False, "total_damage": 7},
        perceiver_uuids=set(),
    )
    visible.identified_entity_observer_uuids = {
        VISIBLE_TARGET_UUID: {OBSERVER_UUID},
    }
    hidden = _log(
        CombatLogEntryType.SPELL_SAVE,
        target_name="Secret Target",
        target_uuid=HIDDEN_TARGET_UUID,
        data={"save_success": True, "total_damage": 999},
        perceiver_uuids={HIDDEN_SOURCE_UUID},
    )
    objective = _log(
        CombatLogEntryType.MULTI_ENTITY_ACTION,
        source_name="Controlled Hero",
        source_uuid=CONTROLLED_UUID,
        target_name=None,
        target_uuid=None,
        data={
            "action_name": "Area Spell",
            "aoe_center": (91, 73),
            "total_targets": 2,
            "target_names": ["Visible Target", "Secret Target"],
            "per_target_damage": [7, 999],
            "total_damage": 1006,
            "saves_succeeded": 1,
            "saves_failed": 1,
        },
        sub_entries=[visible, hidden],
        perceiver_uuids=set(),
    )

    projected = _project(objective)

    assert isinstance(projected, CombatLogEntry)
    assert len(projected.sub_entries) == 1
    assert projected.data["total_targets"] == 1
    assert projected.data["target_names"] == ["Visible Target"]
    assert projected.data["per_target_damage"] == [7]
    assert projected.data["total_damage"] == 7
    assert projected.data["saves_succeeded"] == 0
    assert projected.data["saves_failed"] == 1
    assert "aoe_center" not in projected.data
    assert "Secret Target" not in projected.model_dump_json()


def test_bare_coordinates_without_event_time_grants_are_scrubbed_recursively() -> None:
    objective = _log(
        CombatLogEntryType.ACTION,
        source_name="Controlled Hero",
        source_uuid=CONTROLLED_UUID,
        target_name=None,
        target_uuid=None,
        data={
            "position": (91, 73),
            "nested": {"path": [(91, 73)], "value": "91,73"},
            "91,73": "reached 91,73",
        },
        perceiver_uuids=set(),
    )
    objective.compact = "Controlled Hero acts at 91,73"
    objective.verbose = "Controlled Hero acts at (91, 73)"
    objective.detailed = "Controlled Hero acts at [91,73]"

    projected = _project(objective)

    assert isinstance(projected, CombatLogEntry)
    serialized = projected.model_dump_json()
    assert "91" not in serialized
    assert "73" not in serialized
    assert "position" not in projected.data
    assert projected.data["nested"]["path"] == []


def test_controlled_mover_retains_its_owned_geometry() -> None:
    objective = _log(
        CombatLogEntryType.MOVEMENT,
        source_name="Controlled Hero",
        source_uuid=CONTROLLED_UUID,
        target_name=None,
        target_uuid=None,
        data={
            "type": "step_movement",
            "from_position": (1, 2),
            "to_position": (2, 2),
            "movement_cost": 5,
            "path_index": 1,
            "nested_secret": (91, 73),
        },
        perceiver_uuids=set(),
    )

    projected = _project(objective)

    assert isinstance(projected, CombatLogEntry)
    assert projected.data["from_position"] == (1, 2)
    assert projected.data["to_position"] == (2, 2)
    assert "nested_secret" not in projected.data
    assert "91" not in projected.model_dump_json()
    assert "73" not in projected.model_dump_json()


def test_two_roll_arrays_are_not_misclassified_as_positions() -> None:
    attack_roll = DiceRollDisplay(
        dice_str="d20",
        results=[15, 8],
        bonus=5,
        total=20,
        all_d20_rolls=[15, 8],
        d20_used=15,
        advantage_status="advantage",
    )
    damage_roll = DamageRollDisplay(
        dice_str="2d6",
        dice_results=[3, 4],
        bonus=0,
        total=7,
        damage_type="slashing",
    )
    objective = _log(
        CombatLogEntryType.ATTACK,
        source_name="Controlled Hero",
        source_uuid=CONTROLLED_UUID,
        data={
            "attack_roll": {
                "results": [15, 8],
                "all_d20_rolls": [15, 8],
                "total": 23,
            },
        },
        perceiver_uuids=set(),
    )
    objective.compact = format_attack_compact(
        "Controlled Hero",
        "Training Dummy",
        "hit",
        7,
    )
    objective.verbose = format_attack_verbose(
        "Controlled Hero",
        "Training Dummy",
        "Greatsword",
        attack_roll,
        12,
        "hit",
        [damage_roll],
        7,
    )
    objective.detailed = format_attack_detailed(
        "Controlled Hero",
        "Training Dummy",
        "Greatsword",
        attack_roll,
        [],
        12,
        [],
        "hit",
        [damage_roll],
        7,
    )

    projected = _project(objective)

    assert isinstance(projected, CombatLogEntry)
    assert projected.data == objective.data
    assert projected.compact == objective.compact
    assert projected.verbose == objective.verbose
    assert projected.detailed == objective.detailed


def _completed_atomic_movement_log(
    *,
    movement_type: str,
    trajectory: str,
    path: list[tuple[int, int]],
    start_elevation: int,
    end_elevation: int,
    movement_cost: int,
) -> CombatLogEntry:
    steps: list[CombatLogEntry] = []
    for index, (origin, destination) in enumerate(
        zip(path, path[1:]),
        start=1,
    ):
        from_elevation = start_elevation + (
            (end_elevation - start_elevation) * (index - 1)
            // (len(path) - 1)
        )
        to_elevation = start_elevation + (
            (end_elevation - start_elevation) * index
            // (len(path) - 1)
        )
        step_event = StepMovementEvent(
            source_entity_uuid=UUID(HIDDEN_SOURCE_UUID),
            source_entity_name="Hidden Assassin",
            from_position=origin,
            to_position=destination,
            path_index=index,
            total_path_length=len(path),
            movement_cost=movement_cost // (len(path) - 1),
            trajectory=MovementTrajectory(trajectory),
            disclosed_path=(origin, destination),
            from_elevation_feet=from_elevation,
            to_elevation_feet=to_elevation,
            provocation_policy=MovementProvocationPolicy.ORDINARY_EXIT,
            committed=True,
            phase=EventPhase.COMPLETION,
            use_register=False,
        )
        step = step_event.generate_combat_log()
        assert isinstance(step, CombatLogEntry)
        step.perceiver_uuids = {OBSERVER_UUID}
        step.identified_entity_observer_uuids = {
            HIDDEN_SOURCE_UUID: {OBSERVER_UUID},
        }
        step.located_position_observer_uuids = {
            position_evidence_key(origin): {OBSERVER_UUID},
            position_evidence_key(destination): {OBSERVER_UUID},
        }
        steps.append(step)

    if movement_type == "jump":
        event = JumpEvent(
            source_entity_uuid=UUID(HIDDEN_SOURCE_UUID),
            source_entity_name="Hidden Assassin",
            start_position=path[0],
            requested_end_position=path[-1],
            objective_end_position=path[-1],
            end_position=path[-1],
            start_elevation_feet=start_elevation,
            requested_end_elevation_feet=end_elevation,
            end_elevation_feet=end_elevation,
            jump_distance=movement_cost,
            path=path,
            phase=EventPhase.COMPLETION,
            use_register=False,
        )
    else:
        event = TraverseConnectorEvent(
            source_entity_uuid=UUID(HIDDEN_SOURCE_UUID),
            source_entity_name="Hidden Assassin",
            target_entity_uuid=UUID(HIDDEN_SOURCE_UUID),
            connector_uuid=UUID("00000000-0000-0000-0000-000000000777"),
            connector_authored_id="connector.test",
            connector_kind=TraversalConnectorKind.VERTICAL_STAIRS,
            connector_presentation_key="stairs",
            connector_revision=1,
            connector_digest="0" * 64,
            connector_provocation_policy=(
                ConnectorProvocationPolicy.PROVOKES_SOURCE_EXIT
            ),
            connector_bidirectional=True,
            start_position=path[0],
            requested_end_position=path[-1],
            end_position=path[-1],
            objective_end_position=path[-1],
            start_elevation_feet=start_elevation,
            requested_end_elevation_feet=end_elevation,
            end_elevation_feet=end_elevation,
            movement_cost_feet=movement_cost,
            termination_reason=MovementTerminationReason.COMPLETED,
            phase=EventPhase.COMPLETION,
            use_register=False,
        )
    root = event.generate_combat_log()
    root.sub_entries = steps
    root.perceiver_uuids = {OBSERVER_UUID}
    root.identified_entity_observer_uuids = {
        HIDDEN_SOURCE_UUID: {OBSERVER_UUID},
    }
    return root


@pytest.mark.parametrize(
    ("movement_type", "trajectory", "path", "end_elevation", "cost"),
    (
        ("jump", "direct_arc", [(4, 4), (5, 4), (6, 4)], 10, 10),
        ("connector", "connector_transfer", [(1, 1), (2, 1)], 10, 10),
    ),
)
def test_atomic_geometry_requires_exact_event_time_position_evidence(
    movement_type: str,
    trajectory: str,
    path: list[tuple[int, int]],
    end_elevation: int,
    cost: int,
) -> None:
    objective = _completed_atomic_movement_log(
        movement_type=movement_type,
        trajectory=trajectory,
        path=path,
        start_elevation=0,
        end_elevation=end_elevation,
        movement_cost=cost,
    )

    projected = _project(objective)

    assert isinstance(projected, CombatLogEntry)
    assert projected.data == objective.data
    assert projected.sub_entries[0].data == objective.sub_entries[0].data

    hidden_position = path[len(path) // 2]
    for step in objective.sub_entries:
        step.located_position_observer_uuids.pop(
            position_evidence_key(hidden_position),
            None,
        )
    hidden_geometry = _project(objective)

    assert isinstance(hidden_geometry, CombatLogEntry)
    serialized = hidden_geometry.model_dump_json()
    assert hidden_geometry.data["observation_complete"] is False
    if movement_type == "jump":
        assert f"[{hidden_position[0]},{hidden_position[1]}]" not in serialized
    else:
        assert "connector_uuid" not in hidden_geometry.data
        assert "connector_authored_id" not in hidden_geometry.data


def test_sensory_updates_replay_independently_for_two_observers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_uuid = UUID(CONTROLLED_UUID)
    second_uuid = UUID(OBSERVER_UUID)
    first_contact_uuid = uuid4()
    second_contact_uuid = uuid4()
    first = Senses.create(source_entity_uuid=first_uuid, position=(0, 0))
    second = Senses.create(source_entity_uuid=second_uuid, position=(7, 7))
    first_event = SensoryUpdateEvent(
        source_entity_uuid=first_uuid,
        observer_uuid=first_uuid,
        observer_position=(1, 1),
        observer_position_changed=True,
        cause_event_uuid=uuid4(),
        update_reason=SensoryUpdateReason.SELF_MOVEMENT,
        visible_cells_added=[(1, 1), (2, 1)],
        seen_cells_added=[(1, 1), (2, 1)],
        effective_light_levels_changed={"1,1": LightLevel.DIM_LIGHT.value},
        entity_contacts_changed={
            first_contact_uuid: PerceivedContact(
                position=(2, 1),
                visual=True,
            ),
        },
        sense_modes_changed=True,
        sense_modes=[
            SenseMode(sense_type=SensesType.DARKVISION, range_feet=60),
        ],
        passive_perception_changed=True,
        passive_perception=14,
        visual_access_changed=True,
        visual_access=1,
        paths_dirty=True,
        use_register=False,
    )
    second_event = SensoryUpdateEvent(
        source_entity_uuid=second_uuid,
        observer_uuid=second_uuid,
        observer_position=(6, 7),
        observer_position_changed=True,
        cause_event_uuid=uuid4(),
        update_reason=SensoryUpdateReason.SELF_MOVEMENT,
        visible_cells_added=[(6, 7)],
        seen_cells_added=[(6, 7)],
        entity_contacts_changed={
            second_contact_uuid: PerceivedContact(
                position=(6, 6),
                visual=False,
                special_senses=(SensesType.TREMORSENSE,),
            ),
        },
        use_register=False,
    )
    monkeypatch.setattr(
        "dnd.blocks.sensory.get_map",
        lambda: (_ for _ in ()).throw(AssertionError("live world read")),
    )

    first.apply_sensory_update(first_event)
    second.apply_sensory_update(second_event)

    assert first.position == (1, 1)
    assert set(first.visible) == {(1, 1), (2, 1)}
    assert first.seen == {(1, 1), (2, 1)}
    assert set(first.entities) == {first_contact_uuid}
    assert first.effective_light_levels == {(1, 1): LightLevel.DIM_LIGHT}
    assert first.get_sense_modes() == [
        SenseMode(sense_type=SensesType.DARKVISION, range_feet=60),
    ]
    assert first._last_passive_perception == 14
    assert first._paths_dirty is True
    assert second.position == (6, 7)
    assert set(second.visible) == {(6, 7)}
    assert second.seen == {(6, 7)}
    assert set(second.entities) == {second_contact_uuid}
    assert first_contact_uuid not in second.entities
    assert second_contact_uuid not in first.entities
    assert set(first.visible) | set(second.visible) == {
        (1, 1),
        (2, 1),
        (6, 7),
    }
    with pytest.raises(ValueError, match="different observer"):
        first.apply_sensory_update(second_event)


def _event_with_log(log: CombatLogEntry) -> Event:
    """Return one unregistered completed carrier for an objective log."""
    return Event(
        source_entity_uuid=UUID(log.source_uuid),
        event_type=EventType.BASE_ACTION,
        phase=EventPhase.COMPLETION,
        combat_log=log,
        use_register=False,
    )


def test_generation_range_preserves_three_authoritative_nullable_slots() -> None:
    """Nested, standalone, and hidden logs retain their objective indexes."""
    encounter = Encounter(source_entity_uuid=uuid4())
    visible_child = _log(
        CombatLogEntryType.DAMAGE_TAKEN,
        source_name="Controlled Hero",
        source_uuid=CONTROLLED_UUID,
        data={"damage": 7},
        perceiver_uuids=set(),
    )
    nested_root = _log(
        CombatLogEntryType.ACTION,
        target_name="Hidden Target",
        target_uuid=HIDDEN_TARGET_UUID,
        sub_entries=[visible_child],
        perceiver_uuids={HIDDEN_SOURCE_UUID},
    )
    standalone = _log(
        CombatLogEntryType.ACTION,
        source_name="Controlled Hero",
        source_uuid=CONTROLLED_UUID,
        target_name=None,
        target_uuid=None,
        perceiver_uuids=set(),
    )
    hidden = _log(
        CombatLogEntryType.ACTION,
        target_name="Hidden Target",
        target_uuid=HIDDEN_TARGET_UUID,
        perceiver_uuids={HIDDEN_SOURCE_UUID},
    )

    assert encounter.add_event_to_combat_log(_event_with_log(nested_root)) == 0
    EventQueue.set_combat_log_callback(encounter._on_event_combat_log)
    try:
        EventQueue.push_combat_log(
            standalone,
            source_entity_uuid=UUID(CONTROLLED_UUID),
        )
    finally:
        EventQueue.set_combat_log_callback(None)
    assert encounter.add_event_to_combat_log(_event_with_log(hidden)) == 2
    objective_before = tuple(
        entry.model_copy(deep=True) for entry in encounter.combat_log
    )
    generation = EventQueue.generation_id()

    returned_generation, slots = encounter.project_combat_log_range(
        requested_generation=generation,
        since=0,
        controlled_entity_uuids=frozenset({CONTROLLED_UUID}),
        observer_entity_uuids=frozenset({OBSERVER_UUID}),
    )

    assert returned_generation == generation
    assert tuple(index for index, _entry in slots) == (0, 1, 2)
    first = slots[0][1]
    assert isinstance(first, CombatLogEntry)
    assert len(first.sub_entries) == 1
    assert first.sub_entries[0].entry_type is CombatLogEntryType.DAMAGE_TAKEN
    assert isinstance(slots[1][1], CombatLogEntry)
    assert slots[2][1] is None
    assert tuple(encounter.combat_log) == objective_before


def test_surviving_encounter_rejects_old_logs_after_generation_reset() -> None:
    """A reset cannot relabel or append to an Encounter's old log indexes."""
    encounter = Encounter(source_entity_uuid=uuid4())
    first = _log(
        CombatLogEntryType.ACTION,
        source_name="Controlled Hero",
        source_uuid=CONTROLLED_UUID,
        perceiver_uuids=set(),
    )
    second = _log(
        CombatLogEntryType.DAMAGE_TAKEN,
        source_name="Controlled Hero",
        source_uuid=CONTROLLED_UUID,
        data={"damage": 3},
        perceiver_uuids=set(),
    )
    assert encounter.add_event_to_combat_log(_event_with_log(first)) == 0
    assert encounter.add_event_to_combat_log(_event_with_log(second)) == 1
    old_generation = EventQueue.generation_id()
    assert len(encounter.get_combat_log(
        requested_generation=old_generation,
    )) == 2
    assert not hasattr(encounter, "clear_combat_log")

    EventQueue.reset()
    new_generation = EventQueue.generation_id()

    for requested_generation in (old_generation, new_generation):
        with pytest.raises(RuntimeError, match="generation does not match"):
            encounter.project_combat_log_range(
                requested_generation=requested_generation,
                since=0,
                controlled_entity_uuids=frozenset({CONTROLLED_UUID}),
                observer_entity_uuids=frozenset({OBSERVER_UUID}),
            )
        with pytest.raises(RuntimeError, match="generation does not match"):
            encounter.get_combat_log(
                requested_generation=requested_generation,
            )
    with pytest.raises(RuntimeError, match="stale EventQueue generation"):
        encounter.add_event_to_combat_log(_event_with_log(first))
    assert encounter.combat_log == [first, second]


def test_projection_failure_returns_no_partial_batch_or_source_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One projector failure leaves the append-only objective source intact."""
    encounter = Encounter(source_entity_uuid=uuid4())
    for entry_type in (CombatLogEntryType.ACTION, CombatLogEntryType.ATTACK):
        encounter.add_event_to_combat_log(_event_with_log(_log(
            entry_type,
            source_name="Controlled Hero",
            source_uuid=CONTROLLED_UUID,
            perceiver_uuids=set(),
        )))
    objective_before = tuple(
        entry.model_copy(deep=True) for entry in encounter.combat_log
    )
    real_project = project_combat_log
    calls = 0

    def fail_second(log: CombatLogEntry, **kwargs) -> CombatLogEntry | None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("forced projection failure")
        return real_project(log, **kwargs)

    monkeypatch.setattr("dnd.encounter.project_combat_log", fail_second)

    with pytest.raises(RuntimeError, match="forced projection failure"):
        encounter.project_combat_log_range(
            requested_generation=EventQueue.generation_id(),
            since=0,
            controlled_entity_uuids=frozenset({CONTROLLED_UUID}),
            observer_entity_uuids=frozenset({OBSERVER_UUID}),
        )
    assert tuple(encounter.combat_log) == objective_before


def test_reset_during_projection_rejects_the_complete_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A batch cannot escape when its EventQueue generation changes mid-read."""
    encounter = Encounter(source_entity_uuid=uuid4())
    encounter.add_event_to_combat_log(_event_with_log(_log(
        CombatLogEntryType.ACTION,
        source_name="Controlled Hero",
        source_uuid=CONTROLLED_UUID,
        perceiver_uuids=set(),
    )))
    generation = EventQueue.generation_id()
    objective_before = encounter.combat_log[0].model_copy(deep=True)
    real_project = project_combat_log

    def reset_then_project(
        log: CombatLogEntry,
        **kwargs,
    ) -> CombatLogEntry | None:
        EventQueue.reset()
        return real_project(log, **kwargs)

    monkeypatch.setattr("dnd.encounter.project_combat_log", reset_then_project)

    with pytest.raises(RuntimeError, match="reset during combat-log projection"):
        encounter.project_combat_log_range(
            requested_generation=generation,
            since=0,
            controlled_entity_uuids=frozenset({CONTROLLED_UUID}),
            observer_entity_uuids=frozenset({OBSERVER_UUID}),
        )
    assert encounter.combat_log == [objective_before]


def test_log_projection_does_not_consume_unsupported_objective_events() -> None:
    """The narrow log read never acknowledges or alters objective Events."""
    encounter = Encounter(source_entity_uuid=uuid4())
    encounter.add_event_to_combat_log(_event_with_log(_log(
        CombatLogEntryType.ACTION,
        source_name="Controlled Hero",
        source_uuid=CONTROLLED_UUID,
        perceiver_uuids=set(),
    )))
    cursor = EventQueue.event_cursor()
    unsupported = Event(
        source_entity_uuid=uuid4(),
        event_type=EventType.ABILITY_CHECK,
        status_message="No presentation mapping exists yet",
    )
    cursor_after_event = EventQueue.event_cursor()

    encounter.project_combat_log_range(
        requested_generation=EventQueue.generation_id(),
        since=0,
        controlled_entity_uuids=frozenset({CONTROLLED_UUID}),
        observer_entity_uuids=frozenset({OBSERVER_UUID}),
    )

    assert cursor_after_event == cursor + 1
    assert EventQueue.event_cursor() == cursor_after_event
    assert tuple(EventQueue.iter_events_since(cursor)) == ((cursor, unsupported),)


def test_sensory_replay_rejects_runtime_values_before_state_changes() -> None:
    """Schema revalidation excludes a live owner or callable from replay."""
    observer_uuid = UUID(CONTROLLED_UUID)
    contact_uuid = uuid4()
    senses = Senses.create(source_entity_uuid=observer_uuid, position=(0, 0))
    event = SensoryUpdateEvent(
        source_entity_uuid=observer_uuid,
        observer_uuid=observer_uuid,
        observer_position=(1, 1),
        observer_position_changed=True,
        cause_event_uuid=uuid4(),
        use_register=False,
    )
    before = capture_senses_snapshot(senses)
    bad_values = (
        lambda: None,
        Senses(source_entity_uuid=uuid4(), use_register=False),
        event,
    )

    for bad_value in bad_values:
        malformed = event.model_copy(update={
            "entity_contacts_changed": {contact_uuid: bad_value},
        })
        with pytest.raises(ValueError, match="runtime value"):
            senses.apply_sensory_update(malformed)
        assert capture_senses_snapshot(senses) == before


def test_cold_world_creation_logs_and_two_senses_replay_match_live_values() -> None:
    """The exact test-local presentation tuple reproduces one live run."""
    reset_engine_runtime()
    build_battlefield("battlefield.open_floor_bright")
    game = Game()
    actors = (
        Entity.create(
            source_entity_uuid=uuid4(),
            name="First controlled actor",
            config=EntityConfig(position=(2, 2), faction="heroes"),
        ),
        Entity.create(
            source_entity_uuid=uuid4(),
            name="Second controlled actor",
            config=EntityConfig(position=(4, 2), faction="heroes"),
        ),
    )
    initial_senses = tuple(
        capture_senses_snapshot(actor.senses) for actor in actors
    )
    for actor in actors:
        actor.compose_entity()
    for actor in actors:
        game.deploy_entity(actor, actor.position)

    objective_events = tuple(
        event for _index, event in EventQueue.iter_events_since(0)
    )
    world = next(
        event for event in objective_events
        if isinstance(event, WorldInitializedEvent)
    )
    creations = tuple(
        event for event in objective_events
        if isinstance(event, EntityCreatedEvent)
    )
    sensory_events = tuple(
        event for event in objective_events
        if isinstance(event, SensoryUpdateEvent)
    )
    assert tuple(event.entity_uuid for event in creations) == tuple(
        actor.uuid for actor in actors
    )
    assert {event.observer_uuid for event in sensory_events} == {
        actor.uuid for actor in actors
    }

    encounter = Encounter(source_entity_uuid=uuid4())
    controlled = frozenset(str(actor.uuid) for actor in actors)
    objective_logs = (
        _log(
            CombatLogEntryType.ACTION,
            source_name=actors[0].name,
            source_uuid=str(actors[0].uuid),
            target_name=actors[1].name,
            target_uuid=str(actors[1].uuid),
            perceiver_uuids=set(),
        ),
        _log(
            CombatLogEntryType.ACTION,
            target_name="Hidden Target",
            target_uuid=HIDDEN_TARGET_UUID,
            perceiver_uuids={HIDDEN_SOURCE_UUID},
        ),
    )
    for log in objective_logs:
        encounter.add_event_to_combat_log(_event_with_log(log))
    generation, projected_slots = encounter.project_combat_log_range(
        requested_generation=EventQueue.generation_id(),
        since=0,
        controlled_entity_uuids=controlled,
        observer_entity_uuids=controlled,
    )
    assert generation == EventQueue.generation_id()

    expected = (
        world.model_copy(deep=True),
        tuple(event.model_copy(deep=True) for event in creations),
        tuple(
            (
                index,
                project_combat_log(
                    log,
                    controlled_entity_uuids=controlled,
                    observer_entity_uuids=controlled,
                ),
            )
            for index, log in enumerate(objective_logs)
        ),
        tuple(capture_senses_snapshot(actor.senses) for actor in actors),
    )

    EventQueue.reset()
    replay_senses = tuple(
        Senses(
            source_entity_uuid=actor.uuid,
            position=actor.position,
            use_register=False,
        )
        for actor in actors
    )
    for replay, initial in zip(replay_senses, initial_senses):
        replay.sense_modes = list(initial.sense_modes)
        replay.snapshot_perception(initial.passive_perception)
        assert capture_senses_snapshot(replay) == initial
    replay_by_uuid = {
        replay.source_entity_uuid: replay for replay in replay_senses
    }
    for sensory_event in sensory_events:
        replay_by_uuid[sensory_event.observer_uuid].apply_sensory_update(
            sensory_event,
        )

    replayed = (
        world.model_copy(deep=True),
        tuple(event.model_copy(deep=True) for event in creations),
        projected_slots,
        tuple(capture_senses_snapshot(replay) for replay in replay_senses),
    )
    assert replayed == expected
    assert set(replay_senses[0].visible) | set(replay_senses[1].visible) == (
        set(actors[0].senses.visible) | set(actors[1].senses.visible)
    )
