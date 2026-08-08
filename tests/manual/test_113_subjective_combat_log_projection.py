"""Focused contracts for the dependency-clean subjective combat-log projector."""

import json

import pytest

from dnd.core.combat_log import (
    CombatLogEntry,
    CombatLogEntryType,
    position_evidence_key,
)
from server.combat_log_projection import (
    CombatLogProjectionContext,
    SUBJECTIVE_COMBAT_LOG_ENTRY_TYPES,
    make_combat_log_projection_context,
    project_combat_log,
)


CONTROLLED_UUID = "00000000-0000-0000-0000-000000000001"
VISIBLE_TARGET_UUID = "00000000-0000-0000-0000-000000000002"
HIDDEN_SOURCE_UUID = "00000000-0000-0000-0000-000000000003"
HIDDEN_TARGET_UUID = "00000000-0000-0000-0000-000000000004"
AUTHORIZED_OBSERVER_UUID = "00000000-0000-0000-0000-000000000005"


def _context() -> CombatLogProjectionContext:
    return make_combat_log_projection_context(
        controlled_entity_uuids={CONTROLLED_UUID},
    )


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
            {CONTROLLED_UUID} if perceiver_uuids is None else perceiver_uuids
        ),
    )


def test_every_combat_log_entry_type_has_an_explicit_subjective_policy() -> None:
    """A new objective entry type must not silently cross the projection boundary."""
    assert SUBJECTIVE_COMBAT_LOG_ENTRY_TYPES == frozenset(CombatLogEntryType)


@pytest.mark.parametrize(
    "entry_type",
    tuple(CombatLogEntryType),
    ids=lambda entry_type: entry_type.value,
)
def test_every_entry_type_recursively_scrubs_an_unknown_identity(
    entry_type: CombatLogEntryType,
) -> None:
    """Every reviewed entry family removes hidden identity from text and arbitrary data."""
    objective = _log(
        entry_type,
        data={
            "opaque_uuid": HIDDEN_SOURCE_UUID,
            "opaque_text": f"evidence from Hidden Assassin at {HIDDEN_SOURCE_UUID}",
            f"evidence/{HIDDEN_SOURCE_UUID}": "hidden identity in a field name",
            "Hidden Assassin evidence": "hidden identity in a field name",
            "nested": {
                "rows": [
                    HIDDEN_SOURCE_UUID,
                    "Hidden Assassin",
                    {"participant": f"Hidden Assassin/{HIDDEN_SOURCE_UUID}"},
                ],
            },
        },
        perceiver_uuids={CONTROLLED_UUID, HIDDEN_SOURCE_UUID},
    )

    projected = project_combat_log(objective, _context())

    assert projected is not None
    payload = projected.model_dump(mode="json")
    serialized = json.dumps(payload, sort_keys=True)
    assert HIDDEN_SOURCE_UUID not in serialized
    assert "Hidden Assassin" not in serialized
    assert projected.source_uuid == ""
    assert projected.source_name == "Unknown"
    assert projected.target_uuid == CONTROLLED_UUID


def test_fully_unobserved_log_tree_is_omitted() -> None:
    """Neither an objective root nor its hidden descendants create participant output."""
    hidden_child = _log(
        CombatLogEntryType.DAMAGE_TAKEN,
        target_name="Hidden Target",
        target_uuid=HIDDEN_TARGET_UUID,
        perceiver_uuids={HIDDEN_SOURCE_UUID},
    )
    hidden_root = _log(
        CombatLogEntryType.ACTION,
        target_name="Hidden Target",
        target_uuid=HIDDEN_TARGET_UUID,
        sub_entries=[hidden_child],
        perceiver_uuids={HIDDEN_SOURCE_UUID},
    )

    assert project_combat_log(hidden_root, _context()) is None


def test_roll_modification_child_uses_parent_visibility_and_scrubs_identity() -> None:
    """A modified-roll child remains causal while hidden actors stay anonymous."""
    modification = _log(
        CombatLogEntryType.ROLL_MODIFICATION,
        data={
            "roll_type": "attack",
            "modifications": [
                {
                    "operation": "replace",
                    "handler_name": "Hidden Assassin's Bless",
                    "packet_index": None,
                    "previous_total": 10,
                    "final_total": 13,
                    "reason": f"Hidden Assassin/{HIDDEN_SOURCE_UUID} added 1d4",
                    "packet_damage_type": None,
                    "packet_dice": None,
                }
            ],
        },
        perceiver_uuids={CONTROLLED_UUID},
    )
    parent = _log(
        CombatLogEntryType.ATTACK,
        sub_entries=[modification],
        perceiver_uuids={CONTROLLED_UUID},
    )

    projected = project_combat_log(parent, _context())

    assert projected is not None
    assert [child.entry_type for child in projected.sub_entries] == [
        CombatLogEntryType.ROLL_MODIFICATION,
    ]
    serialized = json.dumps(projected.model_dump(mode="json"), sort_keys=True)
    assert HIDDEN_SOURCE_UUID not in serialized
    assert "Hidden Assassin" not in serialized
    assert projected.sub_entries[0].data["modifications"][0]["final_total"] == 13


def test_multi_target_summary_is_rebuilt_from_projected_children_only() -> None:
    """Objective aggregate counts and damage cannot disclose a filtered target."""
    visible_child = _log(
        CombatLogEntryType.SPELL_SAVE,
        source_name="Controlled Hero",
        source_uuid=CONTROLLED_UUID,
        target_name="Visible Target",
        target_uuid=VISIBLE_TARGET_UUID,
        data={"save_success": False, "total_damage": 7},
    )
    visible_child.identified_entity_observer_uuids = {
        VISIBLE_TARGET_UUID: {CONTROLLED_UUID},
    }
    hidden_child = _log(
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
            "aoe_center": (99, 99),
            "future_objective_secret": "must not cross the reviewed boundary",
            "total_targets": 2,
            "target_names": ["Visible Target", "Secret Target"],
            "per_target_damage": [7, 999],
            "total_damage": 1006,
            "saves_succeeded": 1,
            "saves_failed": 1,
        },
        sub_entries=[visible_child, hidden_child],
    )
    objective.compact = "Controlled Hero hits 2 targets at (99, 99) for 1006 damage"
    objective.verbose = objective.compact
    objective.detailed = objective.compact

    projected = project_combat_log(objective, _context())

    assert projected is not None
    assert len(projected.sub_entries) == 1
    assert projected.sub_entries[0].target_uuid == VISIBLE_TARGET_UUID
    assert projected.sub_entries[0].data == visible_child.data
    assert projected.data["total_targets"] == 1
    assert projected.data["target_names"] == ["Visible Target"]
    assert projected.data["per_target_damage"] == [7]
    assert projected.data["total_damage"] == 7
    assert projected.data["saves_succeeded"] == 0
    assert projected.data["saves_failed"] == 1
    assert "aoe_center" not in projected.data
    assert "future_objective_secret" not in projected.data
    serialized = json.dumps(projected.model_dump(mode="json"))
    assert "Secret Target" not in serialized
    assert "1006" not in serialized
    assert "99, 99" not in serialized
    assert "99, 99" not in projected.compact
    assert "2 targets" not in projected.compact
    assert "7 observed damage" in projected.compact


def test_event_time_identification_grant_is_used_but_never_serialized() -> None:
    """Internal perception evidence authorizes identity without becoming wire data."""
    objective = _log(CombatLogEntryType.ATTACK)
    objective.identified_entity_observer_uuids = {
        HIDDEN_SOURCE_UUID: {CONTROLLED_UUID},
    }
    objective.located_entity_observer_uuids = {
        HIDDEN_SOURCE_UUID: {CONTROLLED_UUID},
    }
    objective.perceiver_uuids = {CONTROLLED_UUID, HIDDEN_TARGET_UUID}
    objective.revealed_entity_uuids = {HIDDEN_SOURCE_UUID, HIDDEN_TARGET_UUID}

    projected = project_combat_log(objective, _context())

    assert projected is not None
    assert projected is not objective
    assert projected.source_uuid == HIDDEN_SOURCE_UUID
    assert projected.perceiver_uuids == set()
    assert projected.revealed_entity_uuids == set()
    assert projected.identified_entity_observer_uuids == {}
    assert projected.located_entity_observer_uuids == {}
    assert objective.revealed_entity_uuids == {
        HIDDEN_SOURCE_UUID,
        HIDDEN_TARGET_UUID,
    }
    payload = projected.model_dump(mode="json")
    assert "identified_entity_observer_uuids" not in payload
    assert "located_entity_observer_uuids" not in payload


def test_global_reveal_metadata_does_not_grant_subjective_identity() -> None:
    """A global reveal fact cannot identify a participant to every observer."""
    objective = _log(CombatLogEntryType.ACTION)
    objective.revealed_entity_uuids = {HIDDEN_SOURCE_UUID}

    projected = project_combat_log(objective, _context())

    assert projected is not None
    assert projected.source_uuid == ""
    assert projected.source_name == "Unknown"
    assert projected.revealed_entity_uuids == set()


def test_authorized_noncontrolled_observer_uses_evidence_not_ownership() -> None:
    """Observer authority grants recorded perception but not direct involvement."""
    context = make_combat_log_projection_context(
        controlled_entity_uuids={CONTROLLED_UUID},
        observer_entity_uuids={AUTHORIZED_OBSERVER_UUID},
    )
    observed = _log(
        CombatLogEntryType.ACTION,
        target_name=None,
        target_uuid=None,
        perceiver_uuids=set(),
    )
    observed.identified_entity_observer_uuids = {
        HIDDEN_SOURCE_UUID: {AUTHORIZED_OBSERVER_UUID},
    }

    projected = project_combat_log(observed, context)

    assert projected is not None
    assert projected.source_uuid == HIDDEN_SOURCE_UUID
    assert projected.source_name == "Hidden Assassin"
    assert projected.perceiver_uuids == set()

    merely_involved = _log(
        CombatLogEntryType.ACTION,
        source_name="Authorized Scout",
        source_uuid=AUTHORIZED_OBSERVER_UUID,
        target_name=None,
        target_uuid=None,
        perceiver_uuids=set(),
    )
    assert project_combat_log(merely_involved, context) is None


def test_noncontrolled_step_location_grant_does_not_reveal_hidden_origin() -> None:
    """Entity-level location evidence cannot authorize either step coordinate."""
    context = make_combat_log_projection_context(
        controlled_entity_uuids={CONTROLLED_UUID},
        observer_entity_uuids={AUTHORIZED_OBSERVER_UUID},
    )
    objective = _log(
        CombatLogEntryType.MOVEMENT,
        target_name=None,
        target_uuid=None,
        data={
            "type": "step_movement",
            "from_position": (91, 73),
            "to_position": (2, 3),
            "movement_cost": 5,
            "path_index": 4,
        },
        perceiver_uuids=set(),
    )
    objective.identified_entity_observer_uuids = {
        HIDDEN_SOURCE_UUID: {AUTHORIZED_OBSERVER_UUID},
    }
    objective.located_entity_observer_uuids = {
        HIDDEN_SOURCE_UUID: {AUTHORIZED_OBSERVER_UUID},
    }

    projected = project_combat_log(objective, context)

    assert projected is not None
    assert projected.source_uuid == HIDDEN_SOURCE_UUID
    assert projected.data == {
        "type": "movement",
        "observation_complete": False,
    }
    serialized = json.dumps(projected.model_dump(mode="json"), sort_keys=True)
    assert "from_position" not in serialized
    assert "to_position" not in serialized
    assert "91" not in serialized
    assert "73" not in serialized


def test_controlled_step_retains_owned_movement_geometry() -> None:
    """A controller may receive the exact path of its own actor."""
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
            "path_index": 0,
        },
    )

    projected = project_combat_log(objective, _context())

    assert projected is not None
    assert projected.data["from_position"] == (1, 2)
    assert projected.data["to_position"] == (2, 2)


def test_noncontrolled_step_retains_geometry_seen_at_both_endpoints() -> None:
    """One authorized observer's pre/post grants preserve visible enemy motion."""
    context = make_combat_log_projection_context(
        controlled_entity_uuids={CONTROLLED_UUID},
        observer_entity_uuids={AUTHORIZED_OBSERVER_UUID},
    )
    objective = _log(
        CombatLogEntryType.MOVEMENT,
        target_name=None,
        target_uuid=None,
        data={
            "type": "step_movement",
            "from_position": (4, 4),
            "to_position": (5, 4),
            "movement_cost": 5,
            "path_index": 1,
        },
        perceiver_uuids=set(),
    )
    objective.identified_entity_observer_uuids = {
        HIDDEN_SOURCE_UUID: {AUTHORIZED_OBSERVER_UUID},
    }
    objective.located_position_observer_uuids = {
        position_evidence_key((4, 4)): {AUTHORIZED_OBSERVER_UUID},
        position_evidence_key((5, 4)): {AUTHORIZED_OBSERVER_UUID},
    }

    projected = project_combat_log(objective, context)

    assert projected is not None
    assert projected.data["from_position"] == (4, 4)
    assert projected.data["to_position"] == (5, 4)
    assert projected.located_position_observer_uuids == {}


def test_noncontrolled_move_root_is_rebuilt_from_committed_steps_only() -> None:
    """Even complete observation cannot inherit requested or forced geometry."""
    context = make_combat_log_projection_context(
        controlled_entity_uuids={CONTROLLED_UUID},
        observer_entity_uuids={AUTHORIZED_OBSERVER_UUID},
    )
    step = _log(
        CombatLogEntryType.MOVEMENT,
        target_name=None,
        target_uuid=None,
        data={
            "type": "step_movement",
            "from_position": (4, 4),
            "to_position": (5, 4),
            "movement_cost": 5,
            "path_index": 1,
            "trajectory": "path",
            "committed": True,
        },
        perceiver_uuids=set(),
    )
    step.identified_entity_observer_uuids = {
        HIDDEN_SOURCE_UUID: {AUTHORIZED_OBSERVER_UUID},
    }
    step.located_position_observer_uuids = {
        position_evidence_key((4, 4)): {AUTHORIZED_OBSERVER_UUID},
        position_evidence_key((5, 4)): {AUTHORIZED_OBSERVER_UUID},
    }
    objective = _log(
        CombatLogEntryType.MOVEMENT,
        target_name=None,
        target_uuid=None,
        data={
            "entity_name": "Hidden Assassin",
            "entity_uuid": HIDDEN_SOURCE_UUID,
            "start_position": (4, 4),
            "end_position": (5, 4),
            "path": [(4, 4), (5, 4)],
            "movement_cost": 5,
            "requested_end_position": (91, 73),
            "objective_end_position": (88, 72),
        },
        sub_entries=[step],
        perceiver_uuids={AUTHORIZED_OBSERVER_UUID},
    )
    objective.identified_entity_observer_uuids = {
        HIDDEN_SOURCE_UUID: {AUTHORIZED_OBSERVER_UUID},
    }

    projected = project_combat_log(objective, context)

    assert projected is not None
    assert projected.data["observation_complete"] is True
    assert projected.data["path"] == [(4, 4), (5, 4)]
    assert projected.data["end_position"] == (5, 4)
    assert "requested_end_position" not in projected.data
    assert "objective_end_position" not in projected.data


def _current_jump_log(
    arc_path: list[tuple[int, int]],
    *,
    authorized_positions: set[tuple[int, int]],
) -> tuple[CombatLogEntry, dict[str, object]]:
    step = _log(
        CombatLogEntryType.MOVEMENT,
        target_name=None,
        target_uuid=None,
        data={
            "type": "step_movement",
            "from_position": arc_path[0],
            "to_position": arc_path[-1],
            "movement_cost": 15.0,
            "path_index": 1,
            "trajectory": "direct_arc",
            "disclosed_path": arc_path,
            "from_elevation_feet": 0,
            "to_elevation_feet": 10,
            "committed": True,
        },
        perceiver_uuids=set(),
    )
    step.identified_entity_observer_uuids = {
        HIDDEN_SOURCE_UUID: {AUTHORIZED_OBSERVER_UUID},
    }
    step.located_position_observer_uuids = {
        position_evidence_key(position): {AUTHORIZED_OBSERVER_UUID}
        for position in authorized_positions
    }
    root_data: dict[str, object] = {
        "movement_type": "jump",
        "entity_name": "Hidden Assassin",
        "entity_uuid": HIDDEN_SOURCE_UUID,
        "start_position": arc_path[0],
        "end_position": arc_path[-1],
        "requested_end_position": arc_path[-1],
        "objective_end_position": arc_path[-1],
        "path": arc_path,
        "distance_feet": 15,
        "movement_cost": 15,
        "start_elevation_feet": 0,
        "requested_end_elevation_feet": 10,
        "end_elevation_feet": 10,
    }
    jump = _log(
        CombatLogEntryType.MOVEMENT,
        target_name=None,
        target_uuid=None,
        data=root_data,
        sub_entries=[step],
        perceiver_uuids={AUTHORIZED_OBSERVER_UUID},
    )
    jump.identified_entity_observer_uuids = {
        HIDDEN_SOURCE_UUID: {AUTHORIZED_OBSERVER_UUID},
    }
    return jump, root_data


def test_current_jump_hides_arc_and_elevations_when_one_disclosed_cell_is_unseen() -> None:
    """Endpoint visibility cannot authorize a hidden cell under a direct arc."""
    context = make_combat_log_projection_context(
        controlled_entity_uuids={CONTROLLED_UUID},
        observer_entity_uuids={AUTHORIZED_OBSERVER_UUID},
    )
    arc_path = [(4, 4), (5, 4), (6, 4), (7, 4)]
    jump, _root_data = _current_jump_log(
        arc_path,
        authorized_positions={arc_path[0], arc_path[-1]},
    )

    projected = project_combat_log(jump, context)

    assert projected is not None
    assert projected.data.get("path") is None
    assert projected.data.get("requested_end_position") is None
    assert projected.data.get("objective_end_position") is None
    assert projected.data.get("start_elevation_feet") is None
    assert projected.data.get("end_elevation_feet") is None
    assert "(7, 4)" not in projected.compact


def test_current_jump_preserves_arc_only_when_every_cell_is_authorized() -> None:
    """A complete per-cell grant proves one current atomic Jump root."""
    context = make_combat_log_projection_context(
        controlled_entity_uuids={CONTROLLED_UUID},
        observer_entity_uuids={AUTHORIZED_OBSERVER_UUID},
    )
    arc_path = [(4, 4), (5, 4), (6, 4), (7, 4)]
    jump, root_data = _current_jump_log(
        arc_path,
        authorized_positions=set(arc_path),
    )

    projected = project_combat_log(jump, context)

    assert projected is not None
    assert projected.data == root_data
    assert projected.sub_entries[0].data["disclosed_path"] == arc_path
    assert projected.sub_entries[0].data["to_elevation_feet"] == 10
    assert "91" not in json.dumps(projected.model_dump(mode="json"))
    assert "88" not in json.dumps(projected.model_dump(mode="json"))


def test_noncontrolled_difficult_step_separates_distance_from_cost() -> None:
    """One adjacent observed edge is 5ft even when terrain costs 10ft."""
    context = make_combat_log_projection_context(
        controlled_entity_uuids={CONTROLLED_UUID},
        observer_entity_uuids={AUTHORIZED_OBSERVER_UUID},
    )
    step = _log(
        CombatLogEntryType.MOVEMENT,
        target_name=None,
        target_uuid=None,
        data={
            "type": "step_movement",
            "from_position": (4, 4),
            "to_position": (5, 4),
            "movement_cost": 10,
            "path_index": 1,
            "trajectory": "path",
            "committed": True,
        },
        perceiver_uuids=set(),
    )
    step.identified_entity_observer_uuids = {
        HIDDEN_SOURCE_UUID: {AUTHORIZED_OBSERVER_UUID},
    }
    step.located_position_observer_uuids = {
        position_evidence_key((4, 4)): {AUTHORIZED_OBSERVER_UUID},
        position_evidence_key((5, 4)): {AUTHORIZED_OBSERVER_UUID},
    }
    objective = _log(
        CombatLogEntryType.MOVEMENT,
        target_name=None,
        target_uuid=None,
        data={
            "entity_name": "Hidden Assassin",
            "entity_uuid": HIDDEN_SOURCE_UUID,
            "start_position": (4, 4),
            "end_position": (5, 4),
            "path": [(4, 4), (5, 4)],
            "distance_feet": 5,
            "movement_cost": 10,
            "requested_end_position": (5, 4),
            "objective_end_position": (5, 4),
        },
        sub_entries=[step],
        perceiver_uuids={AUTHORIZED_OBSERVER_UUID},
    )
    objective.identified_entity_observer_uuids = {
        HIDDEN_SOURCE_UUID: {AUTHORIZED_OBSERVER_UUID},
    }

    projected = project_combat_log(objective, context)

    assert projected is not None
    assert projected.data["observed_distance_feet"] == 5
    assert projected.data["distance_feet"] == 5
    assert projected.data["movement_cost"] == 10
    assert "5ft" in projected.compact
    assert "10ft" not in projected.compact


def test_noncontrolled_elevated_path_step_uses_support_distance() -> None:
    """Authorized PATH geometry reports its 10ft support distance, not flat 5ft."""
    context = make_combat_log_projection_context(
        controlled_entity_uuids={CONTROLLED_UUID},
        observer_entity_uuids={AUTHORIZED_OBSERVER_UUID},
    )
    step = _log(
        CombatLogEntryType.MOVEMENT,
        target_name=None,
        target_uuid=None,
        data={
            "type": "step_movement",
            "from_position": (4, 4),
            "to_position": (5, 4),
            "from_elevation_feet": 0,
            "to_elevation_feet": 10,
            "movement_cost": 10,
            "path_index": 1,
            "trajectory": "path",
            "committed": True,
        },
        perceiver_uuids=set(),
    )
    step.identified_entity_observer_uuids = {
        HIDDEN_SOURCE_UUID: {AUTHORIZED_OBSERVER_UUID},
    }
    step.located_position_observer_uuids = {
        position_evidence_key((4, 4)): {AUTHORIZED_OBSERVER_UUID},
        position_evidence_key((5, 4)): {AUTHORIZED_OBSERVER_UUID},
    }
    objective = _log(
        CombatLogEntryType.MOVEMENT,
        target_name=None,
        target_uuid=None,
        data={
            "entity_name": "Hidden Assassin",
            "entity_uuid": HIDDEN_SOURCE_UUID,
            "start_position": (4, 4),
            "end_position": (5, 4),
            "start_elevation_feet": 0,
            "end_elevation_feet": 10,
            "path": [(4, 4), (5, 4)],
            "distance_feet": 10,
            "movement_cost": 10,
            "requested_end_position": (5, 4),
            "objective_end_position": (5, 4),
        },
        sub_entries=[step],
        perceiver_uuids={AUTHORIZED_OBSERVER_UUID},
    )
    objective.identified_entity_observer_uuids = {
        HIDDEN_SOURCE_UUID: {AUTHORIZED_OBSERVER_UUID},
    }

    projected = project_combat_log(objective, context)

    assert projected is not None
    assert projected.data["observed_distance_feet"] == 10
    assert projected.data["distance_feet"] == 10
    assert projected.data["movement_cost"] == 10
    assert "10ft" in projected.compact


def test_authorized_connector_transfer_preserves_exact_atomic_contract() -> None:
    context = make_combat_log_projection_context(
        controlled_entity_uuids={CONTROLLED_UUID},
        observer_entity_uuids={AUTHORIZED_OBSERVER_UUID},
    )
    step = _log(
        CombatLogEntryType.MOVEMENT,
        target_name=None,
        target_uuid=None,
        data={
            "type": "step_movement",
            "from_position": (4, 4),
            "to_position": (5, 4),
            "from_elevation_feet": 0,
            "to_elevation_feet": 10,
            "movement_cost": 10,
            "path_index": 1,
            "trajectory": "connector_transfer",
            "committed": True,
        },
        perceiver_uuids=set(),
    )
    step.identified_entity_observer_uuids = {
        HIDDEN_SOURCE_UUID: {AUTHORIZED_OBSERVER_UUID},
    }
    step.located_position_observer_uuids = {
        position_evidence_key((4, 4)): {AUTHORIZED_OBSERVER_UUID},
        position_evidence_key((5, 4)): {AUTHORIZED_OBSERVER_UUID},
    }
    root_data = {
        "entity_name": "Hidden Assassin",
        "entity_uuid": HIDDEN_SOURCE_UUID,
        "movement_type": "connector",
        "start_position": (4, 4),
        "end_position": (5, 4),
        "requested_end_position": (5, 4),
        "objective_end_position": (5, 4),
        "path": [(4, 4), (5, 4)],
        "start_elevation_feet": 0,
        "requested_end_elevation_feet": 10,
        "end_elevation_feet": 10,
        "distance_feet": 10,
        "movement_cost": 10,
        "connector_uuid": "00000000-0000-0000-0000-000000000777",
        "connector_authored_id": "connector.test.authorized",
    }
    root = _log(
        CombatLogEntryType.MOVEMENT,
        target_name=None,
        target_uuid=None,
        data=root_data,
        sub_entries=[step],
        perceiver_uuids={AUTHORIZED_OBSERVER_UUID},
    )
    root.identified_entity_observer_uuids = {
        HIDDEN_SOURCE_UUID: {AUTHORIZED_OBSERVER_UUID},
    }

    projected = project_combat_log(root, context)

    assert projected is not None
    assert projected.data == root_data
    assert len(projected.sub_entries) == 1
    assert projected.sub_entries[0].data["trajectory"] == "connector_transfer"


def test_partial_connector_transfer_removes_hidden_endpoint_and_identity() -> None:
    context = make_combat_log_projection_context(
        controlled_entity_uuids={CONTROLLED_UUID},
        observer_entity_uuids={AUTHORIZED_OBSERVER_UUID},
    )
    secret_destination = (91, 73)
    step = _log(
        CombatLogEntryType.MOVEMENT,
        target_name=None,
        target_uuid=None,
        data={
            "type": "step_movement",
            "from_position": (4, 4),
            "to_position": secret_destination,
            "from_elevation_feet": 0,
            "to_elevation_feet": 25,
            "movement_cost": 10,
            "path_index": 1,
            "trajectory": "connector_transfer",
            "committed": True,
        },
        perceiver_uuids=set(),
    )
    step.identified_entity_observer_uuids = {
        HIDDEN_SOURCE_UUID: {AUTHORIZED_OBSERVER_UUID},
    }
    step.located_position_observer_uuids = {
        position_evidence_key((4, 4)): {AUTHORIZED_OBSERVER_UUID},
    }
    root = _log(
        CombatLogEntryType.MOVEMENT,
        target_name=None,
        target_uuid=None,
        data={
            "entity_name": "Hidden Assassin",
            "entity_uuid": HIDDEN_SOURCE_UUID,
            "movement_type": "connector",
            "start_position": (4, 4),
            "end_position": secret_destination,
            "requested_end_position": secret_destination,
            "objective_end_position": secret_destination,
            "path": [(4, 4), secret_destination],
            "start_elevation_feet": 0,
            "requested_end_elevation_feet": 25,
            "end_elevation_feet": 25,
            "distance_feet": 25,
            "movement_cost": 10,
            "connector_uuid": "00000000-0000-0000-0000-000000000999",
            "connector_authored_id": "connector.secret.destination",
        },
        sub_entries=[step],
        perceiver_uuids={AUTHORIZED_OBSERVER_UUID},
    )
    root.identified_entity_observer_uuids = {
        HIDDEN_SOURCE_UUID: {AUTHORIZED_OBSERVER_UUID},
    }

    projected = project_combat_log(root, context)

    assert projected is not None
    payload = json.dumps(projected.model_dump(mode="json"), sort_keys=True)
    assert "91" not in payload
    assert "73" not in payload
    assert "25" not in payload
    assert "00000000-0000-0000-0000-000000000999" not in payload
    assert "connector.secret.destination" not in payload
    assert projected.data.get("observed_path_segments") == []
    assert projected.data.get("observation_complete") is False


def test_noncontrolled_legacy_root_uses_only_authorized_legacy_step() -> None:
    """A pre-versioned root cannot retain geometry beyond a visible old Step."""
    context = make_combat_log_projection_context(
        controlled_entity_uuids={CONTROLLED_UUID},
        observer_entity_uuids={AUTHORIZED_OBSERVER_UUID},
    )
    step = _log(
        CombatLogEntryType.MOVEMENT,
        target_name=None,
        target_uuid=None,
        data={
            "type": "step_movement",
            "from_position": (4, 4),
            "to_position": (5, 4),
            "movement_cost": 5,
            "path_index": 1,
        },
        perceiver_uuids=set(),
    )
    step.identified_entity_observer_uuids = {
        HIDDEN_SOURCE_UUID: {AUTHORIZED_OBSERVER_UUID},
    }
    step.located_position_observer_uuids = {
        position_evidence_key((4, 4)): {AUTHORIZED_OBSERVER_UUID},
        position_evidence_key((5, 4)): {AUTHORIZED_OBSERVER_UUID},
    }
    objective = _log(
        CombatLogEntryType.MOVEMENT,
        target_name=None,
        target_uuid=None,
        data={
            "entity_name": "Hidden Assassin",
            "entity_uuid": HIDDEN_SOURCE_UUID,
            "start_position": (4, 4),
            "end_position": (91, 73),
            "path": [(4, 4), (5, 4), (91, 73)],
            "distance_feet": 10,
            "movement_cost": 10,
        },
        sub_entries=[step],
        perceiver_uuids={AUTHORIZED_OBSERVER_UUID},
    )
    objective.identified_entity_observer_uuids = {
        HIDDEN_SOURCE_UUID: {AUTHORIZED_OBSERVER_UUID},
    }

    projected = project_combat_log(objective, context)

    assert projected is not None
    assert projected.data["path"] == [(4, 4), (5, 4)]
    assert projected.data["end_position"] == (5, 4)
    assert projected.data["observation_complete"] is True
    assert "91" not in json.dumps(projected.model_dump(mode="json"))
    assert "73" not in json.dumps(projected.model_dump(mode="json"))


def test_authorized_noncontrolled_forced_movement_keeps_its_own_contract() -> None:
    """A controlled target may receive forced geometry without Move rewriting."""
    context = make_combat_log_projection_context(
        controlled_entity_uuids={CONTROLLED_UUID},
        observer_entity_uuids={AUTHORIZED_OBSERVER_UUID},
    )
    forced = _log(
        CombatLogEntryType.MOVEMENT,
        target_name="Controlled Hero",
        target_uuid=CONTROLLED_UUID,
        data={
            "type": "forced_movement",
            "cause": "shove",
            "direction": [1, 0],
            "intended_distance": 5,
            "actual_distance": 5,
            "blocked": False,
            "blocked_by": None,
            "start_position": [4, 4],
            "end_position": [5, 4],
        },
        perceiver_uuids={AUTHORIZED_OBSERVER_UUID},
    )
    forced.identified_entity_observer_uuids = {
        HIDDEN_SOURCE_UUID: {AUTHORIZED_OBSERVER_UUID},
    }

    projected = project_combat_log(forced, context)

    assert projected is not None
    assert projected.data == forced.data
    assert projected.compact == forced.compact
    assert projected.target_uuid == CONTROLLED_UUID


def test_authorized_noncontrolled_jump_root_keeps_direct_arc_contract() -> None:
    """DIRECT_ARC Step evidence prevents Jump from becoming a PATH summary."""
    context = make_combat_log_projection_context(
        controlled_entity_uuids={CONTROLLED_UUID},
        observer_entity_uuids={AUTHORIZED_OBSERVER_UUID},
    )
    step = _log(
        CombatLogEntryType.MOVEMENT,
        target_name=None,
        target_uuid=None,
        data={
            "type": "step_movement",
            "from_position": (4, 4),
            "to_position": (5, 4),
            "movement_cost": 5.0,
            "path_index": 1,
            "trajectory": "direct_arc",
            "committed": True,
        },
        perceiver_uuids=set(),
    )
    step.identified_entity_observer_uuids = {
        HIDDEN_SOURCE_UUID: {AUTHORIZED_OBSERVER_UUID},
    }
    step.located_position_observer_uuids = {
        position_evidence_key((4, 4)): {AUTHORIZED_OBSERVER_UUID},
        position_evidence_key((5, 4)): {AUTHORIZED_OBSERVER_UUID},
    }
    jump = _log(
        CombatLogEntryType.MOVEMENT,
        target_name=None,
        target_uuid=None,
        data={
            "entity_name": "Hidden Assassin",
            "entity_uuid": HIDDEN_SOURCE_UUID,
            "start_position": (4, 4),
            "end_position": (5, 4),
            "path": [(4, 4), (5, 4)],
            "distance_feet": 5,
            "movement_cost": 5,
        },
        sub_entries=[step],
        perceiver_uuids={AUTHORIZED_OBSERVER_UUID},
    )
    jump.compact = "Hidden Assassin jumps 5ft to (5, 4)"
    jump.identified_entity_observer_uuids = {
        HIDDEN_SOURCE_UUID: {AUTHORIZED_OBSERVER_UUID},
    }

    projected = project_combat_log(jump, context)

    assert projected is not None
    assert projected.data == jump.data
    assert "jumps" in projected.compact
    assert projected.sub_entries[0].data["trajectory"] == "direct_arc"


def test_authorized_jump_step_cannot_lend_authority_to_secret_root_endpoints() -> None:
    """Authorized arc geometry does not authorize independent root claims."""
    context = make_combat_log_projection_context(
        controlled_entity_uuids={CONTROLLED_UUID},
        observer_entity_uuids={AUTHORIZED_OBSERVER_UUID},
    )
    step = _log(
        CombatLogEntryType.MOVEMENT,
        target_name=None,
        target_uuid=None,
        data={
            "type": "step_movement",
            "from_position": (4, 4),
            "to_position": (7, 4),
            "movement_cost": 15.0,
            "path_index": 1,
            "trajectory": "direct_arc",
            "committed": True,
            "disclosed_path": [(4, 4), (5, 4), (6, 4), (7, 4)],
        },
        perceiver_uuids=set(),
    )
    step.identified_entity_observer_uuids = {
        HIDDEN_SOURCE_UUID: {AUTHORIZED_OBSERVER_UUID},
    }
    step.located_position_observer_uuids = {
        position_evidence_key(position): {AUTHORIZED_OBSERVER_UUID}
        for position in ((4, 4), (5, 4), (6, 4), (7, 4))
    }
    jump = _log(
        CombatLogEntryType.MOVEMENT,
        target_name=None,
        target_uuid=None,
        data={
            "movement_type": "jump",
            "entity_name": "Hidden Assassin",
            "entity_uuid": HIDDEN_SOURCE_UUID,
            "start_position": (4, 4),
            "end_position": (7, 4),
            "path": [(4, 4), (5, 4), (6, 4), (7, 4)],
            "distance_feet": 15,
            "movement_cost": 15,
            "requested_end_position": (91, 73),
            "objective_end_position": (88, 72),
        },
        sub_entries=[step],
        perceiver_uuids={AUTHORIZED_OBSERVER_UUID},
    )
    jump.compact = "Hidden Assassin jumps to secret 91/73"
    jump.verbose = "Hidden Assassin jumps toward secret 88/72"
    jump.detailed = "Hidden Assassin arc ends at secret 91/73 and 88/72"
    jump.identified_entity_observer_uuids = {
        HIDDEN_SOURCE_UUID: {AUTHORIZED_OBSERVER_UUID},
    }

    projected = project_combat_log(jump, context)

    assert projected is not None
    serialized = json.dumps(projected.model_dump(mode="json"))
    for secret in ("91", "73", "88", "72"):
        assert secret not in serialized
    assert "requested_end_position" not in projected.data
    assert "objective_end_position" not in projected.data


def test_current_jump_cannot_rebuild_from_authorized_path_child() -> None:
    """A failed DIRECT_ARC proof cannot borrow PATH movement geometry."""
    context = make_combat_log_projection_context(
        controlled_entity_uuids={CONTROLLED_UUID},
        observer_entity_uuids={AUTHORIZED_OBSERVER_UUID},
    )
    arc_path = [(4, 4), (5, 4)]
    jump, _root_data = _current_jump_log(
        arc_path,
        authorized_positions=set(arc_path),
    )
    jump.data["requested_end_position"] = (91, 73)
    jump.data["objective_end_position"] = (88, 72)
    jump.compact = "Hidden Assassin jumps to secret 91/73"
    jump.verbose = "Hidden Assassin jumps toward secret 88/72"
    jump.detailed = "Hidden Assassin arc ends at secret 91/73 and 88/72"
    path_child = jump.sub_entries[0].model_copy(deep=True)
    path_child.data["trajectory"] = "path"
    path_child.data.pop("disclosed_path", None)
    jump.sub_entries = [path_child]

    projected = project_combat_log(jump, context)

    assert projected is not None
    assert projected.data["observation_complete"] is False
    assert "path" not in projected.data
    assert "start_position" not in projected.data
    assert "end_position" not in projected.data
    serialized = json.dumps(projected.model_dump(mode="json"))
    for secret in ("91", "73", "88", "72"):
        assert secret not in serialized


def test_authorized_multi_edge_jump_reconstructs_root_geometry() -> None:
    """A complete authorized arc chain preserves its matching Jump root."""
    context = make_combat_log_projection_context(
        controlled_entity_uuids={CONTROLLED_UUID},
        observer_entity_uuids={AUTHORIZED_OBSERVER_UUID},
    )

    def arc_step(
        origin: tuple[int, int],
        destination: tuple[int, int],
        path_index: int,
    ) -> CombatLogEntry:
        step = _log(
            CombatLogEntryType.MOVEMENT,
            target_name=None,
            target_uuid=None,
            data={
                "type": "step_movement",
                "from_position": origin,
                "to_position": destination,
                "movement_cost": 5.0,
                "path_index": path_index,
                "trajectory": "direct_arc",
                "committed": True,
            },
            perceiver_uuids=set(),
        )
        step.identified_entity_observer_uuids = {
            HIDDEN_SOURCE_UUID: {AUTHORIZED_OBSERVER_UUID},
        }
        step.located_position_observer_uuids = {
            position_evidence_key(origin): {AUTHORIZED_OBSERVER_UUID},
            position_evidence_key(destination): {AUTHORIZED_OBSERVER_UUID},
        }
        return step

    jump = _log(
        CombatLogEntryType.MOVEMENT,
        target_name=None,
        target_uuid=None,
        data={
            "entity_name": "Hidden Assassin",
            "entity_uuid": HIDDEN_SOURCE_UUID,
            "start_position": (4, 4),
            "end_position": (6, 4),
            "path": [(4, 4), (5, 4), (6, 4)],
            "distance_feet": 10,
            "movement_cost": 10,
        },
        sub_entries=[
            arc_step((4, 4), (5, 4), 1),
            arc_step((5, 4), (6, 4), 2),
        ],
        perceiver_uuids={AUTHORIZED_OBSERVER_UUID},
    )
    jump.compact = "Hidden Assassin jumps 10ft to (6, 4)"
    jump.identified_entity_observer_uuids = {
        HIDDEN_SOURCE_UUID: {AUTHORIZED_OBSERVER_UUID},
    }

    projected = project_combat_log(jump, context)

    assert projected is not None
    assert projected.data == jump.data
    assert projected.compact == jump.compact
    assert len(projected.sub_entries) == 2


def test_same_actor_unrelated_arc_cannot_authorize_root_geometry() -> None:
    """An authorized same-mover arc must reconstruct the root it preserves."""
    context = make_combat_log_projection_context(
        controlled_entity_uuids={CONTROLLED_UUID},
        observer_entity_uuids={AUTHORIZED_OBSERVER_UUID},
    )
    unrelated_step = _log(
        CombatLogEntryType.MOVEMENT,
        target_name=None,
        target_uuid=None,
        data={
            "type": "step_movement",
            "from_position": (8, 8),
            "to_position": (9, 8),
            "movement_cost": 5,
            "path_index": 1,
            "trajectory": "direct_arc",
            "committed": True,
        },
        perceiver_uuids=set(),
    )
    unrelated_step.identified_entity_observer_uuids = {
        HIDDEN_SOURCE_UUID: {AUTHORIZED_OBSERVER_UUID},
    }
    unrelated_step.located_position_observer_uuids = {
        position_evidence_key((8, 8)): {AUTHORIZED_OBSERVER_UUID},
        position_evidence_key((9, 8)): {AUTHORIZED_OBSERVER_UUID},
    }
    movement = _log(
        CombatLogEntryType.MOVEMENT,
        target_name=None,
        target_uuid=None,
        data={
            "entity_name": "Hidden Assassin",
            "entity_uuid": HIDDEN_SOURCE_UUID,
            "start_position": (4, 4),
            "end_position": (91, 73),
            "path": [(4, 4), (91, 73)],
            "distance_feet": 5,
            "movement_cost": 5,
        },
        sub_entries=[unrelated_step],
        perceiver_uuids={AUTHORIZED_OBSERVER_UUID},
    )
    movement.compact = "Hidden Assassin moves to secret (91, 73)"
    movement.identified_entity_observer_uuids = {
        HIDDEN_SOURCE_UUID: {AUTHORIZED_OBSERVER_UUID},
    }

    projected = project_combat_log(movement, context)

    assert projected is not None
    assert projected.data["observed_path_segments"] == []
    assert "end_position" not in projected.data
    assert "path" not in projected.data
    serialized = json.dumps(projected.model_dump(mode="json"))
    assert "91" not in serialized
    assert "73" not in serialized


def test_noncontrolled_jump_hides_root_when_arc_endpoint_is_unseen() -> None:
    """A visible Jump root cannot lend authority to its hidden landing Step."""
    context = make_combat_log_projection_context(
        controlled_entity_uuids={CONTROLLED_UUID},
        observer_entity_uuids={AUTHORIZED_OBSERVER_UUID},
    )
    hidden_step = _log(
        CombatLogEntryType.MOVEMENT,
        target_name=None,
        target_uuid=None,
        data={
            "type": "step_movement",
            "from_position": (4, 4),
            "to_position": (91, 73),
            "movement_cost": 5,
            "path_index": 1,
            "trajectory": "direct_arc",
            "committed": True,
        },
        perceiver_uuids={AUTHORIZED_OBSERVER_UUID},
    )
    hidden_step.identified_entity_observer_uuids = {
        HIDDEN_SOURCE_UUID: {AUTHORIZED_OBSERVER_UUID},
    }
    jump = _log(
        CombatLogEntryType.MOVEMENT,
        target_name=None,
        target_uuid=None,
        data={
            "entity_name": "Hidden Assassin",
            "entity_uuid": HIDDEN_SOURCE_UUID,
            "start_position": (4, 4),
            "end_position": (91, 73),
            "path": [(4, 4), (91, 73)],
            "distance_feet": 5,
            "movement_cost": 5,
        },
        sub_entries=[hidden_step],
        perceiver_uuids={AUTHORIZED_OBSERVER_UUID},
    )
    jump.compact = "Hidden Assassin jumps 5ft to secret (91, 73)"
    jump.identified_entity_observer_uuids = {
        HIDDEN_SOURCE_UUID: {AUTHORIZED_OBSERVER_UUID},
    }

    projected = project_combat_log(jump, context)

    assert projected is not None
    assert projected.data["observation_complete"] is False
    assert projected.data["observed_path_segments"] == []
    assert "end_position" not in projected.data
    assert "path" not in projected.data
    serialized = json.dumps(projected.model_dump(mode="json"))
    assert "91" not in serialized
    assert "73" not in serialized
    assert projected.sub_entries[0].data == {
        "type": "movement",
        "observation_complete": False,
    }


def test_path_child_keeps_mixed_root_under_move_privacy_rebuilding() -> None:
    """A DIRECT_ARC child cannot exempt its parent Move root from sanitizing."""
    context = make_combat_log_projection_context(
        controlled_entity_uuids={CONTROLLED_UUID},
        observer_entity_uuids={AUTHORIZED_OBSERVER_UUID},
    )

    def observed_step(
        origin: tuple[int, int],
        destination: tuple[int, int],
        trajectory: str,
    ) -> CombatLogEntry:
        step = _log(
            CombatLogEntryType.MOVEMENT,
            target_name=None,
            target_uuid=None,
            data={
                "type": "step_movement",
                "from_position": origin,
                "to_position": destination,
                "movement_cost": 5,
                "path_index": 1,
                "trajectory": trajectory,
                "committed": True,
            },
            perceiver_uuids=set(),
        )
        step.identified_entity_observer_uuids = {
            HIDDEN_SOURCE_UUID: {AUTHORIZED_OBSERVER_UUID},
        }
        step.located_position_observer_uuids = {
            position_evidence_key(origin): {AUTHORIZED_OBSERVER_UUID},
            position_evidence_key(destination): {AUTHORIZED_OBSERVER_UUID},
        }
        return step

    path_step = observed_step((4, 4), (5, 4), "path")
    arc_step = observed_step((8, 8), (9, 8), "direct_arc")
    movement = _log(
        CombatLogEntryType.MOVEMENT,
        target_name=None,
        target_uuid=None,
        data={
            "entity_name": "Hidden Assassin",
            "entity_uuid": HIDDEN_SOURCE_UUID,
            "start_position": (4, 4),
            "end_position": (5, 4),
            "path": [(4, 4), (5, 4)],
            "distance_feet": 5,
            "movement_cost": 5,
            "requested_end_position": (91, 73),
            "objective_end_position": (88, 72),
        },
        sub_entries=[path_step, arc_step],
        perceiver_uuids={AUTHORIZED_OBSERVER_UUID},
    )
    movement.identified_entity_observer_uuids = {
        HIDDEN_SOURCE_UUID: {AUTHORIZED_OBSERVER_UUID},
    }

    projected = project_combat_log(movement, context)

    assert projected is not None
    assert projected.data["path"] == [(4, 4), (5, 4)]
    assert "requested_end_position" not in projected.data
    assert "objective_end_position" not in projected.data
    serialized = json.dumps(projected.model_dump(mode="json"))
    assert "91" not in serialized
    assert "88" not in serialized


@pytest.mark.parametrize(
    "move_marker",
    ("requested_end_position", "objective_end_position"),
)
def test_current_move_marker_outranks_authorized_direct_arc_child(
    move_marker: str,
) -> None:
    """An unrelated authorized arc cannot reclassify a current Move root."""
    context = make_combat_log_projection_context(
        controlled_entity_uuids={CONTROLLED_UUID},
        observer_entity_uuids={AUTHORIZED_OBSERVER_UUID},
    )
    arc_step = _log(
        CombatLogEntryType.MOVEMENT,
        target_name=None,
        target_uuid=None,
        data={
            "type": "step_movement",
            "from_position": (8, 8),
            "to_position": (9, 8),
            "movement_cost": 5,
            "path_index": 1,
            "trajectory": "direct_arc",
            "committed": True,
        },
        perceiver_uuids=set(),
    )
    arc_step.identified_entity_observer_uuids = {
        HIDDEN_SOURCE_UUID: {AUTHORIZED_OBSERVER_UUID},
    }
    arc_step.located_position_observer_uuids = {
        position_evidence_key((8, 8)): {AUTHORIZED_OBSERVER_UUID},
        position_evidence_key((9, 8)): {AUTHORIZED_OBSERVER_UUID},
    }
    movement_data = {
        "entity_name": "Hidden Assassin",
        "entity_uuid": HIDDEN_SOURCE_UUID,
        "start_position": (4, 4),
        "end_position": (88, 72),
        "path": [(4, 4), (88, 72)],
        "distance_feet": 5,
        "movement_cost": 0,
        "termination_reason": "position_diverged",
        move_marker: (91, 73),
    }
    movement = _log(
        CombatLogEntryType.MOVEMENT,
        target_name=None,
        target_uuid=None,
        data=movement_data,
        sub_entries=[arc_step],
        perceiver_uuids={AUTHORIZED_OBSERVER_UUID},
    )
    movement.identified_entity_observer_uuids = {
        HIDDEN_SOURCE_UUID: {AUTHORIZED_OBSERVER_UUID},
    }

    projected = project_combat_log(movement, context)

    assert projected is not None
    assert projected.data["observed_path_segments"] == []
    assert "end_position" not in projected.data
    assert "path" not in projected.data
    assert "requested_end_position" not in projected.data
    assert "objective_end_position" not in projected.data
    serialized = json.dumps(projected.model_dump(mode="json"))
    assert "91" not in serialized
    assert "88" not in serialized


def test_other_actor_direct_arc_cannot_authorize_root_geometry() -> None:
    """A child from another mover cannot lend Jump authority to this root."""
    context = make_combat_log_projection_context(
        controlled_entity_uuids={CONTROLLED_UUID},
        observer_entity_uuids={AUTHORIZED_OBSERVER_UUID},
    )
    other_actor_step = _log(
        CombatLogEntryType.MOVEMENT,
        source_name="Other Actor",
        source_uuid=VISIBLE_TARGET_UUID,
        target_name=None,
        target_uuid=None,
        data={
            "type": "step_movement",
            "from_position": (8, 8),
            "to_position": (9, 8),
            "movement_cost": 5,
            "path_index": 1,
            "trajectory": "direct_arc",
            "committed": True,
        },
        perceiver_uuids=set(),
    )
    other_actor_step.identified_entity_observer_uuids = {
        VISIBLE_TARGET_UUID: {AUTHORIZED_OBSERVER_UUID},
    }
    other_actor_step.located_position_observer_uuids = {
        position_evidence_key((8, 8)): {AUTHORIZED_OBSERVER_UUID},
        position_evidence_key((9, 8)): {AUTHORIZED_OBSERVER_UUID},
    }
    movement = _log(
        CombatLogEntryType.MOVEMENT,
        target_name=None,
        target_uuid=None,
        data={
            "entity_name": "Hidden Assassin",
            "entity_uuid": HIDDEN_SOURCE_UUID,
            "start_position": (4, 4),
            "end_position": (91, 73),
            "path": [(4, 4), (91, 73)],
            "distance_feet": 5,
            "movement_cost": 5,
        },
        sub_entries=[other_actor_step],
        perceiver_uuids={AUTHORIZED_OBSERVER_UUID},
    )
    movement.compact = "Hidden Assassin moves to secret (91, 73)"
    movement.identified_entity_observer_uuids = {
        HIDDEN_SOURCE_UUID: {AUTHORIZED_OBSERVER_UUID},
    }

    projected = project_combat_log(movement, context)

    assert projected is not None
    assert projected.data["observed_path_segments"] == []
    assert "end_position" not in projected.data
    assert "path" not in projected.data
    serialized = json.dumps(projected.model_dump(mode="json"))
    assert "91" not in serialized
    assert "73" not in serialized


def test_known_legacy_move_without_steps_fails_closed() -> None:
    """An ambiguous old known root cannot retain objective geometry."""
    context = make_combat_log_projection_context(
        controlled_entity_uuids={CONTROLLED_UUID},
        observer_entity_uuids={AUTHORIZED_OBSERVER_UUID},
    )
    movement = _log(
        CombatLogEntryType.MOVEMENT,
        target_name=None,
        target_uuid=None,
        data={
            "entity_name": "Hidden Assassin",
            "entity_uuid": HIDDEN_SOURCE_UUID,
            "start_position": (4, 4),
            "end_position": (91, 73),
            "path": [(4, 4), (91, 73)],
            "distance_feet": 5,
            "movement_cost": 5,
            "requested_end_position": (91, 73),
        },
        perceiver_uuids={AUTHORIZED_OBSERVER_UUID},
    )
    movement.identified_entity_observer_uuids = {
        HIDDEN_SOURCE_UUID: {AUTHORIZED_OBSERVER_UUID},
    }

    projected = project_combat_log(movement, context)

    assert projected is not None
    assert projected.data["observation_complete"] is False
    assert projected.data["observed_path_segments"] == []
    assert "start_position" not in projected.data
    assert "end_position" not in projected.data
    assert "path" not in projected.data
    assert "requested_end_position" not in projected.data
    serialized = json.dumps(projected.model_dump(mode="json"))
    assert "91" not in serialized
    assert "73" not in serialized


def test_noncontrolled_move_root_ignores_uncommitted_step_geometry() -> None:
    """A rejected Step is attempt evidence, never a traversed root segment."""
    context = make_combat_log_projection_context(
        controlled_entity_uuids={CONTROLLED_UUID},
        observer_entity_uuids={AUTHORIZED_OBSERVER_UUID},
    )
    false_step = _log(
        CombatLogEntryType.MOVEMENT,
        target_name=None,
        target_uuid=None,
        data={
            "type": "step_movement",
            "from_position": (4, 4),
            "to_position": (91, 73),
            "movement_cost": 5,
            "path_index": 1,
            "trajectory": "path",
            "committed": False,
        },
        perceiver_uuids=set(),
    )
    false_step.identified_entity_observer_uuids = {
        HIDDEN_SOURCE_UUID: {AUTHORIZED_OBSERVER_UUID},
    }
    false_step.located_position_observer_uuids = {
        position_evidence_key((4, 4)): {AUTHORIZED_OBSERVER_UUID},
        position_evidence_key((91, 73)): {AUTHORIZED_OBSERVER_UUID},
    }
    objective = _log(
        CombatLogEntryType.MOVEMENT,
        target_name=None,
        target_uuid=None,
        data={
            "entity_name": "Hidden Assassin",
            "entity_uuid": HIDDEN_SOURCE_UUID,
            "start_position": (4, 4),
            "end_position": (4, 4),
            "path": [(4, 4)],
            "movement_cost": 0,
            "requested_end_position": (91, 73),
            "objective_end_position": (4, 4),
        },
        sub_entries=[false_step],
        perceiver_uuids={AUTHORIZED_OBSERVER_UUID},
    )
    objective.identified_entity_observer_uuids = {
        HIDDEN_SOURCE_UUID: {AUTHORIZED_OBSERVER_UUID},
    }

    projected = project_combat_log(objective, context)

    assert projected is not None
    assert projected.data["observed_path_segments"] == []
    assert "path" not in projected.data
    assert "end_position" not in projected.data
    assert "requested_end_position" not in projected.data
    assert "objective_end_position" not in projected.data
